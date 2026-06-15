"""Trading schedule — manages market hours, expiry days, and session timing."""

from __future__ import annotations

from datetime import datetime, timedelta

# NSE market hours in IST
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 30

# Weekly option expiry: Thursday (0=Mon, 3=Thu)
WEEKLY_EXPIRY_DAY = 3

# UTC offset for IST
IST_OFFSET = timedelta(hours=5, minutes=30)


def now_ist() -> datetime:
    return datetime.utcnow() + IST_OFFSET


def is_market_open() -> bool:
    ist = now_ist()
    if ist.weekday() >= 5:  # Sat/Sun
        return False
    open_time = ist.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    close_time = ist.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return open_time <= ist <= close_time


def minutes_to_close() -> int:
    ist = now_ist()
    close_time = ist.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    delta = close_time - ist
    return max(0, int(delta.total_seconds() / 60))


def is_expiry_day() -> bool:
    return now_ist().weekday() == WEEKLY_EXPIRY_DAY


def next_expiry_date() -> str:
    """Return next Thursday (weekly expiry) as YYYY-MM-DD."""
    ist = now_ist()
    days_ahead = WEEKLY_EXPIRY_DAY - ist.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    next_thu = ist + timedelta(days=days_ahead)
    return next_thu.strftime("%Y-%m-%d")


def is_pre_market() -> bool:
    ist = now_ist()
    if ist.weekday() >= 5:
        return False
    pre_open = ist.replace(hour=9, minute=0, second=0)
    market_open = ist.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    return pre_open <= ist < market_open


def session_info() -> dict:
    """Get current session information."""
    ist = now_ist()
    return {
        "ist_time": ist.strftime("%H:%M:%S"),
        "market_open": is_market_open(),
        "pre_market": is_pre_market(),
        "expiry_day": is_expiry_day(),
        "minutes_to_close": minutes_to_close(),
        "next_expiry": next_expiry_date(),
        "day": ist.strftime("%A"),
    }
