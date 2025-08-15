import pandas as pd
from services.alerts import evaluate_alerts
from app_settings import settings

def test_evaluate_alerts_triggers_drawdown_and_concentration(monkeypatch):
    # Create synthetic history with big drawdown and high concentration
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    rows = []
    # TOTAL equity drops 20%
    eq_values = [100.0 - i*0.5 for i in range(30)]  # ends at 85 -> ~15% drawdown, adjust to force > threshold
    eq_values[-1] = 70.0  # larger drawdown
    for i,d in enumerate(dates):
        rows.append({"date": d, "ticker": "TOTAL", "total_equity": eq_values[i], "total_value": eq_values[i]})
        # One dominant ticker value
        rows.append({"date": d, "ticker": "BIG", "total_equity": eq_values[i], "total_value": eq_values[i]*0.9})
        rows.append({"date": d, "ticker": "SMALL", "total_equity": eq_values[i], "total_value": eq_values[i]*0.1})
    df = pd.DataFrame(rows)
    # Lower thresholds for test to guarantee triggers
    monkeypatch.setattr(settings, 'alert_drawdown_pct', 5.0)
    monkeypatch.setattr(settings, 'alert_concentration_top1_pct', 50.0)
    monkeypatch.setattr(settings, 'alert_var95_pct', 1.0)
    events = evaluate_alerts(df)
    assert any(e['type']=='drawdown_threshold' for e in events)
    assert any(e['type']=='concentration_top1' for e in events)
