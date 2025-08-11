import pytest
from typing import Tuple  # Add missing import
from services.core.validation_service import ValidationService


def test_validate_ticker_valid():
    """Test valid ticker validation."""
    valid, error = ValidationService.validate_ticker("AAPL")
    assert valid is True
    assert error is None


def test_validate_ticker_empty():
    """Test empty ticker validation."""
    valid, error = ValidationService.validate_ticker("")
    assert valid is False
    assert "cannot be empty" in error


def test_validate_ticker_too_long():
    """Test too long ticker validation."""
    valid, error = ValidationService.validate_ticker("TOOLONG")
    assert valid is False
    assert "too long" in error


def test_validate_ticker_non_alpha():
    """Test non-alphabetic ticker validation."""
    valid, error = ValidationService.validate_ticker("APL1")
    assert valid is False
    assert "only letters" in error


def test_validate_shares_valid():
    """Test valid shares validation."""
    valid, error = ValidationService.validate_shares(100)
    assert valid is True
    assert error is None


def test_validate_shares_negative():
    """Test negative shares validation."""
    valid, error = ValidationService.validate_shares(-10)
    assert valid is False
    assert "must be positive" in error


def test_validate_price_valid():
    """Test valid price validation."""
    valid, error = ValidationService.validate_price(150.50)
    assert valid is True
    assert error is None


def test_validate_price_negative():
    """Test negative price validation."""
    valid, error = ValidationService.validate_price(-10.0)
    assert valid is False
    assert "must be positive" in error
