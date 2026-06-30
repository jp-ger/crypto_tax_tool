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
