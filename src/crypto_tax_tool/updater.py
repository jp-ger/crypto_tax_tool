import subprocess
from dataclasses import dataclass
from pathlib import Path

import requests
from packaging.version import InvalidVersion, Version


CURRENT_VERSION = "0.1.1"
GITHUB_REPO = "jp-ger/crypto_tax_tool"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
MAIN_COMMIT_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str | None
    update_available: bool
    release_url: str | None
    asset_url: str | None
    message: str


def check_for_updates(timeout_seconds: int = 10) -> UpdateInfo:
    release_info = _check_latest_release(timeout_seconds=timeout_seconds)
    if release_info.latest_version is not None or "failed" in release_info.message.lower():
        return release_info

    return _check_main_branch(timeout_seconds=timeout_seconds)


def _check_latest_release(timeout_seconds: int) -> UpdateInfo:
    try:
        response = requests.get(RELEASES_API_URL, timeout=timeout_seconds)
        if response.status_code == 404:
            return UpdateInfo(
                current_version=CURRENT_VERSION,
                latest_version=None,
                update_available=False,
                release_url=None,
                asset_url=None,
                message="No GitHub release found yet. Checking main branch instead...",
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
        message = f"Release update available: {latest_tag}. Download the latest release."
    else:
        message = f"You are using the latest release version: {CURRENT_VERSION}."

    return UpdateInfo(
        current_version=CURRENT_VERSION,
        latest_version=latest_tag,
        update_available=update_available,
        release_url=release_url,
        asset_url=asset_url,
        message=message,
    )


def _check_main_branch(timeout_seconds: int) -> UpdateInfo:
    try:
        response = requests.get(MAIN_COMMIT_API_URL, timeout=timeout_seconds)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001
        return UpdateInfo(
            current_version=CURRENT_VERSION,
            latest_version=None,
            update_available=False,
            release_url=None,
            asset_url=None,
            message=f"Main branch update check failed: {exc}",
        )

    latest_sha = str(payload.get("sha") or "")
    short_latest_sha = latest_sha[:7] if latest_sha else "unknown"
    commit_url = payload.get("html_url")
    commit_date = (payload.get("commit") or {}).get("committer", {}).get("date")
    local_sha = _get_local_git_commit_sha()

    if local_sha:
        short_local_sha = local_sha[:7]
        update_available = bool(latest_sha and latest_sha != local_sha)
        if update_available:
            message = (
                f"Main branch update available. Local commit: {short_local_sha}; "
                f"latest main: {short_latest_sha}. Run: git pull origin main"
            )
        else:
            message = f"You are up to date with main: {short_local_sha}."
    else:
        update_available = True
        message = (
            f"No GitHub release found yet. Latest main commit: {short_latest_sha}"
            + (f" from {commit_date}" if commit_date else "")
            + ". If you installed from source, run: git pull origin main"
        )

    return UpdateInfo(
        current_version=CURRENT_VERSION,
        latest_version=short_latest_sha,
        update_available=update_available,
        release_url=commit_url,
        asset_url=None,
        message=message,
    )


def _get_local_git_commit_sha() -> str | None:
    for path in [Path.cwd(), Path(__file__).resolve().parents[2]]:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=path,
                capture_output=True,
                check=True,
                text=True,
                timeout=5,
            )
        except Exception:  # noqa: BLE001
            continue
        sha = result.stdout.strip()
        if sha:
            return sha
    return None


def _find_windows_asset_url(assets: list[dict]) -> str | None:
    for asset in assets:
        name = str(asset.get("name") or "").lower()
        if name.endswith(".exe") or name.endswith(".zip") or "windows" in name:
            return asset.get("browser_download_url")
    return None
