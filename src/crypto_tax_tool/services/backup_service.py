import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from crypto_tax_tool.database.sqlite_store import get_db_path
from crypto_tax_tool.settings import get_settings


@dataclass(frozen=True)
class BackupResult:
    created: bool
    path: Path | None
    message: str


class BackupService:
    def create_backup(self, reason: str) -> BackupResult:
        db_path = get_db_path()
        if not db_path.exists():
            return BackupResult(created=False, path=None, message="No database file exists yet.")

        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        safe_reason = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in reason.lower())
        backup_dir = get_settings().data_dir / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"crypto_tax_{timestamp}_{safe_reason}.sqlite3"
        shutil.copy2(db_path, backup_path)
        return BackupResult(created=True, path=backup_path, message=f"Backup created: {backup_path}")
