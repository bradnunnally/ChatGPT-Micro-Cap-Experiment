from micro_portfolio import load_portfolio, save_portfolio, add_position, remove_position, update_stop_loss, PORTFOLIO_FILE


def test_portfolio_json_cycle(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert load_portfolio()["positions"] == []
    save_portfolio({"cash_balance": 50.0, "positions": []})
    p = load_portfolio()
    assert p["cash_balance"] == 50.0
    add_position("AAA", 10, 1.5)
    add_position("AAA", 10, 2.5)
    add_position("BBB", 5, 3.0, stop_loss=2.0)
    p = load_portfolio()
    assert len(p["positions"]) == 2
    update_stop_loss("BBB", 1.5)
    p = load_portfolio()
    sl = next(x for x in p["positions"] if x["ticker"] == "BBB")["stop_loss"]
    assert sl == 1.5
    remove_position("AAA")
    p = load_portfolio()
    assert [x["ticker"] for x in p["positions"]] == ["BBB"]
