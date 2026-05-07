from __future__ import annotations

from datetime import datetime, time


AM_START = time(9, 30)
AM_END = time(11, 30)
PM_START = time(13, 0)
PM_END = time(15, 0)


def is_trading_day(moment: datetime) -> bool:
    return moment.weekday() < 5


def is_trading_time(moment: datetime) -> bool:
    if not is_trading_day(moment):
        return False
    current = moment.time()
    return AM_START <= current <= AM_END or PM_START <= current <= PM_END
