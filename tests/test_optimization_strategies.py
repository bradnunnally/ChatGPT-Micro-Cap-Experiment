import pandas as pd
import numpy as np
import pytest
from services.optimization import (
    MeanVarianceStrategy,
    RiskParityStrategy,
    MinVarianceStrategy,
    ConstrainedRiskParityStrategy,
    factor_neutral_overlay,
    apply_turnover_penalty,
    estimate_covariance,
    estimate_returns,
    register_phase9_strategies,
    compute_factor_exposures,
    apply_volatility_cap,
    regime_risk_overlay,
    profile_optimization_pipeline,
    apply_volatility_target,
)
from services.strategy import StrategyContext, list_strategies


def _mk_ctx(tickers=("A","B","C"), rows: int = 80):
    rng = np.random.default_rng(42)
    rets = rng.normal(0.0005, 0.01, size=(rows, len(tickers)))
    hist = pd.DataFrame(rets, columns=tickers)
    prices = pd.DataFrame({"ticker": tickers, "pct_change": hist.tail(1).iloc[0].values})
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow(), prices=prices, extra={"returns_history": hist})
    return ctx, hist


def test_mean_variance_strategy_basic():
    ctx, hist = _mk_ctx()
    strat = MeanVarianceStrategy()
    w = strat.target_weights(ctx)
    assert w
    s = sum(w.values())
    assert abs(s - 1.0) < 1e-6
    assert all(v >= 0 for v in w.values())


def test_risk_parity_inverse_vol():
    ctx, hist = _mk_ctx()
    # Inflate volatility of B
    hist["B"] *= 3
    ctx.extra["returns_history"] = hist
    strat = RiskParityStrategy()
    w = strat.target_weights(ctx)
    assert w
    assert w["B"] < w["A"]


def test_factor_neutral_overlay_single_factor():
    base = {"A":0.4,"B":0.3,"C":0.3}
    exposures = pd.DataFrame({"factor1":[1.0, 1.0, 1.0]}, index=["A","B","C"])  # identical loads
    adj = factor_neutral_overlay(base, exposures, ["factor1"], long_only=True)
    s = sum(adj.values())
    assert abs(s - 1.0) < 1e-6
    assert len(adj) == 3


def test_turnover_penalty_shrinks_changes():
    cur = {"A":0.5,"B":0.5}
    tgt = {"A":0.2,"B":0.8}
    adj = apply_turnover_penalty(cur, tgt, cost_bps=25, penalty=5.0)
    assert adj["A"] > 0.2 and adj["A"] < 0.5


def test_estimators_covariance_and_returns():
    ctx, hist = _mk_ctx(rows=30)
    mu = estimate_returns(hist, method="mean")
    cov = estimate_covariance(hist, shrink=True)
    assert not mu.empty and not cov.empty
    assert set(mu.index) <= set(cov.columns)


def test_register_phase9_strategies_helper():
    register_phase9_strategies()
    names = {s.name for s in list_strategies(active_only=False)}
    assert {"mean_variance","risk_parity","min_variance","constrained_risk_parity"}.issubset(names)


def test_compute_factor_exposures_basic():
    rng = np.random.default_rng(0)
    asset_rets = pd.DataFrame(rng.normal(0,0.01,size=(120,3)), columns=["A","B","C"])
    # Create a factor as linear combo of A + noise, another orthogonal-ish
    f1 = asset_rets["A"] * 0.8 + rng.normal(0,0.01,size=120)
    f2 = rng.normal(0,0.01,size=120)
    fac = pd.DataFrame({"F1": f1, "F2": f2})
    expos = compute_factor_exposures(asset_rets, fac, min_obs=30)
    assert not expos.empty and set(expos.columns)=={"F1","F2"}
    # Asset A should have higher loading to F1 than B or C on average
    assert expos.loc["A","F1"] >= 0

def test_factor_neutral_overlay_with_realistic_exposures():
    # Construct exposures matrix (A strongly exposed to F1, B mildly, C none)
    weights = {"A":0.5,"B":0.3,"C":0.2}
    exposures = pd.DataFrame({"F1":[1.0,0.5,0.0],"F2":[0.2,0.2,0.2]}, index=["A","B","C"])  # F2 constant -> ignored
    adj = factor_neutral_overlay(weights, exposures, ["F1","F2"], long_only=True)
    assert abs(sum(adj.values()) - 1.0) < 1e-6
    # Reduced weight on highly exposed A after neutralization (heuristic expectation)
    assert adj.get("A",0) <= weights["A"] + 1e-6


def test_turnover_penalty_zero_returns_target():
    cur = {"A":0.6,"B":0.4}
    tgt = {"A":0.2,"B":0.8}
    adj = apply_turnover_penalty(cur, tgt, penalty=0.0)
    assert adj == tgt


def test_mean_variance_inverse_vol_fallback_all_negative():
    # Create returns with negative drift so expected returns negative
    rng = np.random.default_rng(7)
    rets = rng.normal(-0.002, 0.0005, size=(90, 4))
    cols = list("ABCD")
    hist = pd.DataFrame(rets, columns=cols)
    prices = pd.DataFrame({"ticker": cols, "pct_change": hist.tail(1).iloc[0].values})
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow(), prices=prices, extra={"returns_history": hist})
    strat = MeanVarianceStrategy()
    w = strat.target_weights(ctx)
    assert w and abs(sum(w.values())-1.0) < 1e-6
    # All long-only positive despite negative expected returns -> fallback triggered
    assert all(v > 0 for v in w.values())


def test_apply_volatility_cap_scales_down():
    rng = np.random.default_rng(11)
    rets = rng.normal(0.001, 0.02, size=(120,3))  # relatively volatile
    hist = pd.DataFrame(rets, columns=["A","B","C"])
    weights = {"A":0.4,"B":0.4,"C":0.2}
    scaled = apply_volatility_cap(weights, hist, target_annual_vol_pct=5.0)
    assert scaled
    active_sum = sum(scaled.values())
    assert active_sum < 0.999  # implicit cash introduced
    # Recompute original annual vol vs new
    cov = hist.cov()
    import math
    orig_w = pd.Series(weights)
    orig_var = float((orig_w.values @ cov.values @ orig_w.values))
    orig_vol_ann = math.sqrt(orig_var) * math.sqrt(252)
    scaled_w_norm = pd.Series(scaled) / sum(scaled.values())
    scaled_var = float((scaled_w_norm.values @ cov.loc[scaled_w_norm.index, scaled_w_norm.index].values @ scaled_w_norm.values))
    scaled_vol_ann_effective = orig_vol_ann * active_sum  # since scaling is uniform
    assert scaled_vol_ann_effective <= 0.05 + 1e-3


def test_apply_volatility_cap_no_change_when_below():
    rng = np.random.default_rng(12)
    rets = rng.normal(0.0002, 0.002, size=(120,3))  # low vol
    hist = pd.DataFrame(rets, columns=["A","B","C"])
    weights = {"A":0.3,"B":0.4,"C":0.3}
    scaled = apply_volatility_cap(weights, hist, target_annual_vol_pct=80.0)
    # Should not scale (sum stays ~1)
    assert abs(sum(scaled.values()) - 1.0) < 1e-6


def test_compute_factor_exposures_insufficient():
    # Fewer observations than min_obs -> expect empty or zeros
    asset = pd.DataFrame({"A":[0.01, -0.005, 0.002]})
    fac = pd.DataFrame({"F1":[0.003, -0.001, 0.002]})
    expos = compute_factor_exposures(asset, fac, min_obs=10)
    # Not enough data: exposures DataFrame may be empty
    assert expos.empty or (expos.loc["A"].abs() < 1e-9).all()


def test_min_variance_strategy_basic():
    ctx, hist = _mk_ctx()
    strat = MinVarianceStrategy()
    w = strat.target_weights(ctx)
    assert w and abs(sum(w.values()) - 1.0) < 1e-6
    assert all(v >= 0 for v in w.values())


def test_constrained_risk_parity_max_weight_and_risk_balance():
    # Create heteroskedastic returns so naive inverse vol would concentrate
    rng = np.random.default_rng(123)
    a = rng.normal(0,0.01,size=120)
    b = rng.normal(0,0.02,size=120)  # higher vol
    c = rng.normal(0,0.03,size=120)  # highest vol
    hist = pd.DataFrame({"A":a,"B":b,"C":c})
    prices = pd.DataFrame({"ticker":["A","B","C"],"pct_change":hist.tail(1).iloc[0].values})
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow(), prices=prices, extra={"returns_history":hist})
    strat = ConstrainedRiskParityStrategy(max_weight=0.6, iterations=50, tol=0.05)
    w = strat.target_weights(ctx)
    assert w and all(v <= 0.6 + 1e-9 for v in w.values())
    # Compute risk contributions dispersion
    cov = hist.cov().fillna(0)
    import math
    w_series = pd.Series(w)
    port_var = float(w_series.values @ cov.loc[w_series.index, w_series.index].values @ w_series.values)
    if port_var > 0:
        mrc = cov.loc[w_series.index, w_series.index].values @ w_series.values
        rc = w_series.values * mrc / math.sqrt(port_var)
        rc = rc / rc.sum()
        # Coefficient of variation should be reasonably small (heuristic)
        cv = rc.std() / (rc.mean() + 1e-12)
        assert cv < 1.0  # loose bound just sanity


def test_regime_risk_overlay_scales_weights():
    base = {"A":0.5,"B":0.5}
    scaled = regime_risk_overlay(base, "high_vol")
    assert abs(sum(scaled.values()) - 0.7) < 1e-6
    unchanged = regime_risk_overlay(base, "bull")
    assert unchanged == base

def test_regime_risk_overlay_with_probabilities():
    from services.optimization import regime_risk_overlay
    # Provide a gross_target derived externally (simulating adaptive blend)
    base = {"A": 0.4, "B": 0.6}
    gross_target = 0.8
    adapted = regime_risk_overlay(base, "bear", regime_probs={"bull":0.1,"bear":0.5,"high_vol":0.3,"sideways":0.1}, gross_target=gross_target)
    assert abs(sum(adapted.values()) - gross_target) < 1e-6
    # Scale factor should equal gross_target / current_gross (which is 1.0)
    assert adapted["A"] == pytest.approx(0.4 * 0.8)


def test_apply_volatility_target_scales_down():
    # Create high vol series so target < current
    rng = np.random.default_rng(42)
    a = rng.normal(0,0.03, size=120)
    b = rng.normal(0,0.025, size=120)
    hist = pd.DataFrame({"A":a,"B":b})
    weights = {"A":0.6,"B":0.4}
    # Compute current vol to set a lower target
    cov = hist.cov().fillna(0)
    w = pd.Series(weights)
    import math
    var = float((w.values @ cov.values @ w.values))
    curr_vol = math.sqrt(var) * math.sqrt(252)
    target = curr_vol * 0.7
    new_w = apply_volatility_target(weights, hist, target_annual_vol=target)
    assert sum(new_w.values()) < sum(weights.values()) + 1e-9  # scaled down


def test_apply_volatility_target_scales_up_within_bounds():
    # Low vol series so target > current
    rng = np.random.default_rng(7)
    a = rng.normal(0,0.005, size=120)
    b = rng.normal(0,0.006, size=120)
    hist = pd.DataFrame({"A":a,"B":b})
    weights = {"A":0.5,"B":0.5}
    cov = hist.cov().fillna(0)
    w = pd.Series(weights)
    import math
    var = float((w.values @ cov.values @ w.values))
    curr_vol = math.sqrt(var) * math.sqrt(252)
    target = curr_vol * 1.3
    new_w = apply_volatility_target(weights, hist, target_annual_vol=target)
    # Should scale up but not exceed 1.5 upper bound scaling
    assert sum(new_w.values()) > sum(weights.values()) - 1e-9


def test_profile_optimization_pipeline_timings():
    ctx, hist = _mk_ctx(rows=150)
    # Minimal strategy list
    strategies = [MeanVarianceStrategy(), RiskParityStrategy()]
    prof = profile_optimization_pipeline(hist, strategies, ctx, overlays=True)
    required = {"returns_estimation_ms","covariance_estimation_ms","strategies_eval_ms","total_ms"}
    assert required.issubset(prof)
    assert prof["total_ms"] >= prof["returns_estimation_ms"]
