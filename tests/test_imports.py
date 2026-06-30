def test_package_import() -> None:
    import crypto_tax_tool

    assert crypto_tax_tool.__version__ == "0.1.0"


def test_settings_import() -> None:
    from crypto_tax_tool.settings import get_settings

    assert get_settings().app_name == "Crypto Tax Tool"
