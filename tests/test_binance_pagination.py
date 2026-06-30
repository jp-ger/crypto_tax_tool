from crypto_tax_tool.api.binance.pagination import extract_rows, paginate_numbered


def test_extract_rows_supports_list_payload() -> None:
    assert extract_rows([{"id": 1}]) == [{"id": 1}]


def test_extract_rows_supports_rows_key() -> None:
    assert extract_rows({"rows": [{"id": 1}]}) == [{"id": 1}]


def test_paginate_numbered_stops_on_short_page() -> None:
    calls: list[int] = []

    def fetch(page: int):
        calls.append(page)
        if page == 1:
            return {"rows": [{"id": 1}, {"id": 2}]}
        return {"rows": [{"id": 3}]}

    rows = paginate_numbered(fetch, rows_key="rows", page_size=2)
    assert rows == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert calls == [1, 2]
