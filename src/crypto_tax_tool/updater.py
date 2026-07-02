import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests
from packaging.version import InvalidVersion, Version


CURRENT_VERSION = "0.1.3"
GITHUB_REPO = "jp-ger/crypto_tax_tool"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
MAIN_COMMIT_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits/main"
MAIN_ZIP_URL = f"https://github.com/{GITHUB_REPO}/archive/refs/heads/main.zip"
PROTECTED_LOCAL_ITEMS = {
    ".env",
    ".git",
    "data",
    "backups",
    "reports",
    "logs",
    "dist",
    "build",
    "__pycache__",
}


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str | None
    update_available: bool
    release_url: str | None
    asset_url: str | None
    message: str


@dataclass(frozen=True)
class InstallUpdateResult:
    success: bool
    message: str
    used_method: str
    restart_required: bool = True


def check_for_updates(timeout_seconds: int = 10) -> UpdateInfo:
    release_info = _check_latest_release(timeout_seconds=timeout_seconds)
    if release_info.latest_version is not None or "failed" in release_info.message.lower():
        return release_info

    return _check_main_branch(timeout_seconds=timeout_seconds)


def install_update_from_main(
    progress_callback: Callable[[str], None] | None = None,
    timeout_seconds: int = 30,
) -> InstallUpdateResult:
    """Install latest main branch into the folder of the running app/source checkout."""

    def log(message: str) -> None:
        if progress_callback:
            progress_callback(message)

    project_root = _find_project_root()
    if project_root is None:
        return InstallUpdateResult(
            success=False,
            used_method="none",
            message="Could not find the project root. Automatic update is not available for this installation.",
            restart_required=False,
        )

    log(f"Project root: {project_root}")
    log(f"Running location: {_running_location()}")

    if _is_git_checkout(project_root):
        log("Git checkout detected. Running: git pull origin main")
        result = _run_git_pull(project_root)
        if result.success:
            return result
        log(result.message)
        log("Git pull failed. Trying ZIP update fallback...")

    return _install_from_main_zip(project_root, log=log, timeout_seconds=timeout_seconds)


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
                f"latest main: {short_latest_sha}. Click update again to install automatically."
            )
        else:
            message = f"You are up to date with main: {short_local_sha}."
    else:
        update_available = True
        message = (
            f"No GitHub release found yet. Latest main commit: {short_latest_sha}"
            + (f" from {commit_date}" if commit_date else "")
            + ". Click update to download and install main.zip automatically."
        )

    return UpdateInfo(
        current_version=CURRENT_VERSION,
        latest_version=short_latest_sha,
        update_available=update_available,
        release_url=commit_url,
        asset_url=None,
        message=message,
    )


def _run_git_pull(project_root: Path) -> InstallUpdateResult:
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=project_root,
            capture_output=True,
            check=False,
            text=True,
            timeout=120,
        )
    except Exception as exc:  # noqa: BLE001
        return InstallUpdateResult(
            success=False,
            used_method="git",
            message=f"Git pull could not be started: {exc}",
            restart_required=False,
        )

    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    if result.returncode == 0:
        return InstallUpdateResult(
            success=True,
            used_method="git",
            message="Update installed via git pull. Restart the tool and rebuild the EXE if needed."
            + (f"\n{output}" if output else ""),
        )

    return InstallUpdateResult(
        success=False,
        used_method="git",
        message=f"Git pull failed with exit code {result.returncode}." + (f"\n{output}" if output else ""),
        restart_required=False,
    )


def _install_from_main_zip(
    project_root: Path,
    log: Callable[[str], None],
    timeout_seconds: int,
) -> InstallUpdateResult:
    try:
        with tempfile.TemporaryDirectory(prefix="crypto_tax_tool_update_") as tmp_dir:
            tmp_path = Path(tmp_dir)
            zip_path = tmp_path / "main.zip"
            extract_path = tmp_path / "extract"

            log("Downloading latest main.zip from GitHub...")
            with requests.get(MAIN_ZIP_URL, stream=True, timeout=timeout_seconds) as response:
                response.raise_for_status()
                with zip_path.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            handle.write(chunk)

            log("Extracting update package...")
            with zipfile.ZipFile(zip_path) as archive:
                archive.extractall(extract_path)

            source_dirs = [item for item in extract_path.iterdir() if item.is_dir()]
            if not source_dirs:
                raise RuntimeError("Downloaded ZIP did not contain a project folder.")
            source_root = source_dirs[0]

            log(f"Copying update files to: {project_root}")
            log("Preserving local .env, data, backups, reports, logs, dist and build folders...")
            copied = _copy_update_files(source_root=source_root, target_root=project_root)
            log(f"Updated {copied} files/folders.")

    except Exception as exc:  # noqa: BLE001
        return InstallUpdateResult(
            success=False,
            used_method="zip",
            message=f"ZIP update failed: {type(exc).__name__}: {exc}",
            restart_required=False,
        )

    return InstallUpdateResult(
        success=True,
        used_method="zip",
        message=(
            f"Update installed from GitHub main.zip into {project_root}. "
            "Preserved .env, data, backups, reports and logs. "
            "Restart the tool and rebuild the EXE if needed."
        ),
    )


def _copy_update_files(source_root: Path, target_root: Path) -> int:
    copied = 0
    for item in source_root.iterdir():
        if item.name in PROTECTED_LOCAL_ITEMS:
            continue
        target = target_root / item.name
        if item.is_dir():
            _replace_dir(source=item, target=target)
        else:
            shutil.copy2(item, target)
        copied += 1
    return copied


def _replace_dir(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    shutil.copytree(source, target, ignore=_ignore_generated_files)


def _ignore_generated_files(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name == "__pycache__" or name.endswith(".pyc") or name.endswith(".pyo")}


def _running_location() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _find_project_root() -> Path | None:
    """Find the actual running app/source folder, not an arbitrary current working directory."""
    running_location = _running_location()
    candidates = [
        running_location,
        *running_location.parents,
    ]

    # Last-resort fallback only. This is intentionally after the running location so
    # a Desktop shell working directory cannot override a D:\ installation.
    cwd = Path.cwd().resolve()
    candidates.extend([cwd, *cwd.parents])

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if (candidate / "pyproject.toml").exists() or (candidate / ".git").exists():
            return candidate
    return running_location if running_location.exists() else None


def _is_git_checkout(path: Path) -> bool:
    return (path / ".git").exists()


def _get_local_git_commit_sha() -> str | None:
    project_root = _find_project_root()
    candidates = [candidate for candidate in [project_root, Path.cwd().resolve()] if candidate is not None]
    for path in candidates:
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
