from portfolio import (
    load_portfolio_state,
    save_portfolio_state,
    add_ticker,
    remove_ticker,
    ensure_dev_defaults,
)


def test_portfolio_state_cycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_portfolio_state() == []
    add_ticker("AAPL")
    add_ticker("MSFT")
    assert set(load_portfolio_state()) == {"AAPL", "MSFT"}
    remove_ticker("AAPL")
    assert load_portfolio_state() == ["MSFT"]
    save_portfolio_state(["NVDA", "MSFT"])
    assert sorted(load_portfolio_state()) == ["MSFT", "NVDA"]


def test_dev_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tickers = ensure_dev_defaults("dev_stage")
    assert len(tickers) >= 1
    again = ensure_dev_defaults("dev_stage")
    assert tickers == again
