import pandas as pd

from services.strategy import (
    StrategyContext,
    register_strategy,
    unregister_strategy,
    list_strategies,
    set_strategy_active,
    combine_strategy_targets,
    EqualWeightStrategy,
    TopNPriceMomentumStrategy,
)


def setup_function(_):
    # ensure clean registry between tests
    for s in list(list_strategies(active_only=False)):
        unregister_strategy(s.name)


def test_register_and_list_strategies():
    eq = EqualWeightStrategy()
    mom = TopNPriceMomentumStrategy(top_n=3)
    register_strategy(eq)
    register_strategy(mom)
    names = {s.name for s in list_strategies()}
    assert {eq.name, mom.name} <= names


def test_activate_deactivate():
    eq = EqualWeightStrategy()
    register_strategy(eq)
    set_strategy_active(eq.name, False)
    assert not list_strategies()  # active only empty
    # inactive listed when active_only=False
    assert list_strategies(active_only=False)
    set_strategy_active(eq.name, True)
    assert list_strategies()


def test_combine_strategy_targets_equal_capital_basic():
    # Two strategies produce non-overlapping tickers
    class StratA:
        name = "A"
        def target_weights(self, ctx):
            return {"AAA": 1, "BBB": 1}
    class StratB:
        name = "B"
        def target_weights(self, ctx):
            return {"CCC": 2}
    register_strategy(StratA())
    register_strategy(StratB())
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow())
    df = combine_strategy_targets([s for s in list_strategies(active_only=False)], ctx=ctx)
    # Composite weights should sum to 1 (normalization over positives)
    comp = df.drop_duplicates("ticker")["composite_weight"].sum()
    assert abs(comp - 1.0) < 1e-9
    # Check proportional: A's tickers each raw 1, B's ticker raw 2 -> after capital equalization
    # Raw contributions: A: AAA 1, BBB 1 ; B: CCC 2 -> totals by positive = 1+1+2=4 -> composite AAA=0.25, BBB=0.25, CCC=0.5
    comp_map = {r.ticker: r.composite_weight for r in df.drop_duplicates("ticker").itertuples()}
    assert comp_map == {"AAA": 0.25, "BBB": 0.25, "CCC": 0.5}


def test_combine_with_strategy_capital_weights():
    class StratA:
        name = "A"
        def target_weights(self, ctx):
            return {"AAA": 1, "BBB": 1}
    class StratB:
        name = "B"
        def target_weights(self, ctx):
            return {"BBB": 1, "CCC": 1}
    a = StratA(); b = StratB()
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow())
    df = combine_strategy_targets([a, b], ctx=ctx, strategy_capital={"A": 0.75, "B": 0.25})
    # Weighted contributions pre-normalization:
    # A: AAA 0.75, BBB 0.75 ; B: BBB 0.25, CCC 0.25 -> aggregated: AAA 0.75, BBB 1.0, CCC 0.25
    # Sum positives = 2.0 -> composite AAA 0.375, BBB 0.5, CCC 0.125
    agg = df.drop_duplicates("ticker")[ ["ticker","composite_weight"] ].set_index("ticker").to_dict()["composite_weight"]
    assert abs(sum(agg.values()) - 1.0) < 1e-9
    assert agg == {"AAA": 0.375, "BBB": 0.5, "CCC": 0.125}


def test_combine_all_negative_weights():
    class ShortOnly:
        name = "short"
        def target_weights(self, ctx):
            return {"XYZ": -1, "ABC": -2}
    ctx = StrategyContext(as_of=pd.Timestamp.utcnow())
    df = combine_strategy_targets([ShortOnly()], ctx=ctx)
    # abs sum = 3 -> weights: XYZ -1/3, ABC -2/3
    agg = df.drop_duplicates("ticker")[ ["ticker","composite_weight"] ].set_index("ticker").to_dict()["composite_weight"]
    assert agg == {"XYZ": -1/3, "ABC": -2/3}
