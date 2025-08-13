from __future__ import annotations

import zoneinfo
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional


@dataclass(frozen=True)
class Clock:
    """Deterministic, timezone-aware clock.

    Defaults to US/Eastern; override tz for other zones. Use now()/today()/utcnow().
    """

    tz: zoneinfo.ZoneInfo = zoneinfo.ZoneInfo("America/New_York")

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def today(self) -> date:
        return self.now().date()

    def utcnow(self) -> datetime:
        return datetime.now(timezone.utc)


# Module-level default clock for app-wide use and easy injection in tests.
_DEFAULT_CLOCK: Clock | None = None


def get_clock() -> Clock:
    """Return the process-wide default Clock instance.

    Tests can override via set_clock for deterministic behavior.
    """
    global _DEFAULT_CLOCK
    if _DEFAULT_CLOCK is None:
        _DEFAULT_CLOCK = Clock()
    return _DEFAULT_CLOCK


def set_clock(clock: Clock) -> None:
    """Override the default Clock (primarily for tests)."""
    global _DEFAULT_CLOCK
    _DEFAULT_CLOCK = clock


@dataclass
class TradingCalendar:
    """Simple US trading calendar with weekday checks and regular-hours window.

    Not a full holiday calendar; closed on weekends. Clients may extend for holidays.
    """

    clock: Clock
    market_open: time = time(9, 30)  # 9:30 AM ET
    market_close: time = time(16, 0)  # 4:00 PM ET

    # Optional simple US holiday set (YYYY-MM-DD strings) for closure awareness
    holidays: set[str] | None = None

    def is_trading_day(self, d: Optional[date] = None) -> bool:
        d = d or self.clock.today()
        # Monday=0 .. Sunday=6; trading days Mon-Fri
        if d.weekday() >= 5:
            return False
        if self.holidays:
            if d.strftime("%Y-%m-%d") in self.holidays:
                return False
        return True

    def is_market_open(self, at: Optional[datetime] = None) -> bool:
        ts = at or self.clock.now()
        if not self.is_trading_day(ts.date()):
            return False
        return self.market_open <= ts.timetz().replace(tzinfo=None) <= self.market_close

    def next_trading_day(self, d: Optional[date] = None) -> date:
        d = d or self.clock.today()
        nxt = d + timedelta(days=1)
        while nxt.weekday() >= 5:  # skip Sat/Sun
            nxt += timedelta(days=1)
        return nxt
