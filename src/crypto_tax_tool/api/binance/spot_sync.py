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
        window_end = min(current + timedelta(days=1), end)
        windows.append(TimeWindow(start=current, end=window_end))
        current = window_end
    return windows


def split_into_monthly_windows(start: datetime, end: datetime) -> list[TimeWindow]:
    windows: list[TimeWindow] = []
    current = start
    while current < end:
        next_month = _add_one_month(current)
        window_end = min(next_month, end)
        windows.append(TimeWindow(start=current, end=window_end))
        current = window_end
    return windows


def _add_one_month(value: datetime) -> datetime:
    if value.month == 12:
        return value.replace(year=value.year + 1, month=1)
    return value.replace(month=value.month + 1)
