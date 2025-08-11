import pytest
from services.time import Clock, TradingCalendar
from datetime import date, time, datetime

def test_clock_now_and_today():
    c = Clock()
    now = c.now()
    today = c.today()
    assert isinstance(now, datetime)
    assert isinstance(today, date)
    assert now.date() == today

def test_trading_calendar_weekday():
    c = Clock()
    cal = TradingCalendar(clock=c)
    # Monday
    d = date(2025, 8, 11)
    assert cal.is_trading_day(d)
    # Saturday
    d = date(2025, 8, 9)
    assert not cal.is_trading_day(d)

def test_trading_calendar_holiday():
    c = Clock()
    cal = TradingCalendar(clock=c, holidays={"2025-08-11"})
    d = date(2025, 8, 11)
    assert not cal.is_trading_day(d)

def test_trading_calendar_market_open():
    c = Clock()
    cal = TradingCalendar(clock=c)
    dt = datetime(2025, 8, 11, 10, 0, tzinfo=c.tz)
    assert cal.is_market_open(dt)
    dt = datetime(2025, 8, 11, 8, 0, tzinfo=c.tz)
    assert not cal.is_market_open(dt)
