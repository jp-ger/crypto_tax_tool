from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class TimeWindow:
    start: datetime
    end: datetime


def split_into_daily_windows(start: datetime, end: datetime) -> list[TimeWindow]:
    windows: list[TimeWindow] = []
    current = start
    while current < end:
        stop = min(current + timedelta(days=1), end)
        windows.append(TimeWindow(start=current, end=stop))
        current = stop
    return windows


def split_into_monthly_windows(start: datetime, end: datetime) -> list[TimeWindow]:
    windows: list[TimeWindow] = []
    if start < end:
        windows.append(TimeWindow(start=start, end=end))
    return windows


def _add_one_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)
