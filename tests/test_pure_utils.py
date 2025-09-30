from services.pure_utils import within_range, compute_cost, validate_buy_price


def test_within_range():
    assert within_range(10, 5, 15) is True
    assert within_range(4, 5, 15) is False
    # Missing bounds -> always True
    assert within_range(10, None, 15) is True
    assert within_range(10, 5, None) is True


def test_compute_cost():
    assert compute_cost(10, 2.5) == 25.0


def test_validate_buy_price():
    ok = validate_buy_price(10, 5, 15)
    assert ok.valid is True
    bad = validate_buy_price(20, 5, 15)
    assert bad.valid is False and "range" in bad.reason
    no_bounds = validate_buy_price(10, None, None)
    assert no_bounds.valid is True
    stale = validate_buy_price(0.25, 25, 27)
    assert stale.valid is True and stale.reason


def test_validate_buy_price_tolerance():
    near_edge = validate_buy_price(105, 100, 104)
    assert near_edge.valid is True
