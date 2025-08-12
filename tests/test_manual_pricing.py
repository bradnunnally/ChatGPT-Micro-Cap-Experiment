import pytest
import services.manual_pricing as mp


def test_manual_pricing_basic(monkeypatch):
    # Ensure clean state
    mp.manual_pricing_service.clear_all()
    assert mp.manual_pricing_service.get_all_prices() == {}

    mp.set_manual_price('abc', 12.34)
    assert mp.get_manual_price('ABC') == 12.34
    assert mp.manual_pricing_service.has_price('abc') is True

    mp.manual_pricing_service.remove_price('ABC')
    assert mp.manual_pricing_service.has_price('ABC') is False


def test_manual_pricing_validation(monkeypatch):
    mp.manual_pricing_service.clear_all()
    with pytest.raises(ValueError):
        mp.set_manual_price('X', 0)
    with pytest.raises(ValueError):
        mp.set_manual_price('Y', -5)


def test_manual_pricing_clear_all():
    mp.manual_pricing_service.clear_all()
    mp.set_manual_price('ZZZ', 1.23)
    assert mp.manual_pricing_service.get_all_prices() == {'ZZZ': 1.23}
    mp.manual_pricing_service.clear_all()
    assert mp.manual_pricing_service.get_all_prices() == {}
