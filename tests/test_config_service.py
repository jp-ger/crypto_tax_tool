from crypto_tax_tool.services.config_service import ConfigService


def test_config_service_saves_credentials(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("CRYPTO_TAX_DB_PATH", str(tmp_path / "data" / "test.sqlite3"))

    from crypto_tax_tool.settings import get_settings

    get_settings.cache_clear()

    path = ConfigService().save_binance_credentials("key123", "secret456")

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert 'BINANCE_API_KEY="key123"' in content
    assert 'BINANCE_API_SECRET="secret456"' in content

    get_settings.cache_clear()
    api_key, api_secret = ConfigService().load_binance_credentials()
    assert api_key == "key123"
    assert api_secret == "secret456"
