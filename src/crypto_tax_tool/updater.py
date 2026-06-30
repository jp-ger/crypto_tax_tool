from dataclasses import dataclass

import requests
from packaging.version import InvalidVersion, Version


CURRENT_VERSION = "0.1.0"
GITHUB_REPO = "jp-ger/crypto_tax_tool"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str | None
    update_available: bool
    release_url: str | None
    asset_url: str | None
    message: str


def check_for_updates(timeout_seconds: int = 10) -> UpdateInfo:
    try:
        response = requests.get(RELEASES_API_URL, timeout=timeout_seconds)
        if response.status_code == 404:
            return UpdateInfo(
                current_version=CURRENT_VERSION,
                latest_version=None,
                update_available=False,
                release_url=None,
                asset_url=None,
                message="No GitHub release found yet.",
            )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return UpdateInfo(
            current_version=CURRENT_VERSION,
            latest_version=None,
            update_available=False,
            release_url=None,
            asset_url=None,
            message=f"Update check failed: {exc}",
        )

    latest_tag = str(payload.get("tag_name") or "").lstrip("v")
    release_url = payload.get("html_url")
    asset_url = _find_windows_asset_url(payload.get("assets") or [])

    try:
        current = Version(CURRENT_VERSION)
        latest = Version(latest_tag)
    except InvalidVersion:
        return UpdateInfo(
            current_version=CURRENT_VERSION,
            latest_version=latest_tag or None,
            update_available=False,
            release_url=release_url,
            asset_url=asset_url,
            message=f"Could not compare versions. Current={CURRENT_VERSION}, latest={latest_tag}.",
        )

    update_available = latest > current
    if update_available:
        message = f"Update available: {latest_tag}. Download the latest release."
    else:
        message = f"You are using the latest version: {CURRENT_VERSION}."

    return UpdateInfo(
        current_version=CURRENT_VERSION,
        latest_version=latest_tag,
        update_available=update_available,
        release_url=release_url,
        asset_url=asset_url,
        message=message,
    )


def _find_windows_asset_url(assets: list[dict]) -> str | None:
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".exe") or name.endswith(".zip") or "windows" in name:
            return asset.get("browser_download_url")
    return None
