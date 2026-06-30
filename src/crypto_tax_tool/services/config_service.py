from pathlib import Path

from crypto_tax_tool.settings import get_settings


ENV_KEYS = {"BINANCE_API_KEY", "BINANCE_API_SECRET", "CRYPTO_TAX_DB_PATH"}


class ConfigService:
    def env_path(self) -> Path:
        return Path(".env")

    def save_binance_credentials(self, api_key: str, api_secret: str) -> Path:
        path = self.env_path()
        existing = self._read_existing_env(path)
        existing["BINANCE_API_KEY"] = api_key.strip()
        existing["BINANCE_API_SECRET"] = api_secret.strip()
        if "CRYPTO_TAX_DB_PATH" not in existing:
            existing["CRYPTO_TAX_DB_PATH"] = str(get_settings().db_path)
        self._write_env(path, existing)

        from crypto_tax_tool.settings import get_settings as cached_settings

        cached_settings.cache_clear()
        return path

    def load_binance_credentials(self) -> tuple[str, str]:
        settings = get_settings()
        return settings.binance_api_key, settings.binance_api_secret

    def _read_existing_env(self, path: Path) -> dict[str, str]:
        values: dict[str, str] = {}
        if not path.exists():
            return values
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"')
        return values

    def _write_env(self, path: Path, values: dict[str, str]) -> None:
        lines = [
            "# Crypto Tax Tool local configuration",
            "# Keep API credentials read-only in Binance.",
        ]
        for key in sorted(values):
            value = values[key]
            escaped = value.replace('"', '\\"')
            lines.append(f'{key}="{escaped}"')
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
