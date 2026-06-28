"""
Backup and restore — full data export/import.
Backs up: SQLite DB + uploaded resumes + .env config (without secrets).
Lets you migrate to a new machine or recover after crash.
"""
import json
import logging
import os
import shutil
import tarfile
from datetime import datetime

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
_BACKUP_DIR = os.path.join(_DATA_DIR, "backups")
os.makedirs(_BACKUP_DIR, exist_ok=True)


def create_backup() -> dict:
    """Create a tar.gz backup. Returns path to backup file."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_name = f"getajob_backup_{timestamp}.tar.gz"
    backup_path = os.path.join(_BACKUP_DIR, backup_name)

    files_to_backup = []
    db_path = os.path.join(_DATA_DIR, "jobs.db")
    if os.path.exists(db_path):
        files_to_backup.append(("jobs.db", db_path))

    resumes_dir = os.path.join(_DATA_DIR, "resumes")
    if os.path.exists(resumes_dir):
        files_to_backup.append(("resumes/", resumes_dir))

    # Add config (without secrets) — just structure
    config_snapshot = {
        "backup_created": datetime.utcnow().isoformat(),
        "version": "1.0",
    }
    try:
        from database import SessionLocal, Job, Application, ResumeProfile
        db = SessionLocal()
        config_snapshot["stats"] = {
            "total_jobs": db.query(Job).count(),
            "applications": db.query(Application).count(),
            "resumes": db.query(ResumeProfile).count(),
        }
        db.close()
    except Exception:
        pass

    with tarfile.open(backup_path, "w:gz") as tar:
        for arcname, path in files_to_backup:
            tar.add(path, arcname=arcname)
        # Write metadata
        meta_path = os.path.join(_BACKUP_DIR, "metadata.json")
        with open(meta_path, "w") as f:
            json.dump(config_snapshot, f, indent=2)
        tar.add(meta_path, arcname="metadata.json")
        os.remove(meta_path)

    size_mb = os.path.getsize(backup_path) / (1024 * 1024)
    logger.info(f"Backup created: {backup_path} ({size_mb:.1f}MB)")

    # Prune old backups (keep last 10)
    backups = sorted(
        [f for f in os.listdir(_BACKUP_DIR) if f.endswith(".tar.gz")],
        reverse=True,
    )
    for old in backups[10:]:
        try:
            os.remove(os.path.join(_BACKUP_DIR, old))
        except Exception:
            pass

    return {
        "ok": True,
        "path": backup_path,
        "filename": backup_name,
        "size_mb": round(size_mb, 2),
        "metadata": config_snapshot,
    }


def list_backups() -> list:
    """List available backups."""
    if not os.path.exists(_BACKUP_DIR):
        return []
    files = [f for f in os.listdir(_BACKUP_DIR) if f.endswith(".tar.gz")]
    result = []
    for f in sorted(files, reverse=True):
        path = os.path.join(_BACKUP_DIR, f)
        result.append({
            "filename": f,
            "size_mb": round(os.path.getsize(path) / (1024 * 1024), 2),
            "created_at": datetime.fromtimestamp(os.path.getmtime(path)).isoformat(),
        })
    return result


def restore_backup(backup_filename: str) -> dict:
    """Restore from a backup file. DANGER: overwrites current data."""
    backup_path = os.path.join(_BACKUP_DIR, backup_filename)
    if not os.path.exists(backup_path):
        return {"ok": False, "error": "Backup file not found"}

    # Safety: backup current state first
    safety = create_backup()
    logger.info(f"Safety backup before restore: {safety['filename']}")

    try:
        with tarfile.open(backup_path, "r:gz") as tar:
            tar.extractall(path=_DATA_DIR)
        return {
            "ok": True,
            "restored_from": backup_filename,
            "safety_backup": safety["filename"],
            "note": "Restart server to load restored DB",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}
