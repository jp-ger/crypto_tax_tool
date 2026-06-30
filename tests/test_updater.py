from crypto_tax_tool.updater import check_for_updates


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_update_checker_handles_missing_release(monkeypatch) -> None:
    import crypto_tax_tool.updater as updater

    monkeypatch.setattr(updater.requests, "get", lambda *args, **kwargs: _Response(404))

    info = check_for_updates()

    assert info.update_available is False
    assert info.latest_version is None


def test_update_checker_detects_newer_release(monkeypatch) -> None:
    import crypto_tax_tool.updater as updater

    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _Response(
            200,
            {
                "tag_name": "v9.9.9",
                "html_url": "https://github.com/jp-ger/crypto_tax_tool/releases/tag/v9.9.9",
                "assets": [
                    {
                        "name": "CryptoTaxTool.exe",
                        "browser_download_url": "https://example.com/CryptoTaxTool.exe",
                    }
                ],
            },
        ),
    )

    info = check_for_updates()

    assert info.update_available is True
    assert info.latest_version == "9.9.9"
    assert info.asset_url == "https://example.com/CryptoTaxTool.exe"
