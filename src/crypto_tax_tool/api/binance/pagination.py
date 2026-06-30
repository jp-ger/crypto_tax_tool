from collections.abc import Callable
from typing import Any


def extract_rows(payload: dict | list, key: str = "rows") -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    rows = payload.get(key)
    if isinstance(rows, list):
        return rows
    for fallback_key in ("list", "data"):
        fallback_rows = payload.get(fallback_key)
        if isinstance(fallback_rows, list):
            return fallback_rows
    return []


def paginate_numbered(
    fetch_page: Callable[[int], dict | list],
    rows_key: str = "rows",
    page_size: int = 100,
    max_pages: int = 10_000,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    page = 1
    while page <= max_pages:
        payload = fetch_page(page)
        rows = extract_rows(payload, rows_key)
        if not rows:
            break
        result.extend(rows)
        if len(rows) < page_size:
            break
        page += 1
    return result
