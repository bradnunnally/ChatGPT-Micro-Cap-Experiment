import os
from services.fundamentals import get_fundamentals, batch_get_fundamentals


def test_get_fundamentals_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("FINNHUB_API_KEY", "")  # ensure offline path
    # Redirect cache dir
    from services import fundamentals as fund_mod
    fund_mod._FUND_DIR = tmp_path / "fundamentals"  # type: ignore
    fund_mod._FUND_DIR.mkdir(parents=True, exist_ok=True)
    f1 = get_fundamentals("ABC")
    f2 = get_fundamentals("abc")  # reuse same day cached
    assert f1.ticker == "ABC"
    assert f1.updated == f2.updated
    assert f1.cash_per_share == f2.cash_per_share


def test_batch_get_fundamentals_dedup(monkeypatch, tmp_path):
    monkeypatch.setenv("FINNHUB_API_KEY", "")
    from services import fundamentals as fund_mod
    fund_mod._FUND_DIR = tmp_path / "fundamentals"  # type: ignore
    fund_mod._FUND_DIR.mkdir(parents=True, exist_ok=True)
    funds = batch_get_fundamentals(["AAA", "aaa", "TOTAL"])  # duplicate + TOTAL filtered
    assert len(funds) == 1
    assert funds[0].ticker == "AAA"
