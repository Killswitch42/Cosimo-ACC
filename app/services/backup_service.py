"""
Off-site backup to Google Drive.

A backup is a single timestamped .tar.gz containing:
  * db.sql          — full pg_dump of the accounting database
  * documents/      — uploaded invoice/receipt scans
  * filings/        — generated XML/PDF filings

The DB dump uses the host `pg_dump` if available, otherwise `docker exec
<pg_container_name> pg_dump` (handy when Postgres runs only in a container).
Upload uses a Google service account — no interactive OAuth — so it works
headless on a home/Tailscale box. Everything is gated on GDRIVE_BACKUP_ENABLED;
until configured, run_backup() is a no-op that reports "disabled".

Google libraries are imported lazily so the module stays importable without them.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

from app.config import settings

BACKUP_PREFIX = "medici-backup-"


class BackupError(Exception):
    pass


def _db_params() -> dict:
    """Extract connection params from DATABASE_URL."""
    parsed = urlparse(str(settings.database_url))
    return {
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": (parsed.path or "/").lstrip("/"),
    }


def dump_database(dest_sql_path: str) -> None:
    """Write a pg_dump of the database to dest_sql_path."""
    p = _db_params()
    env = {**os.environ, "PGPASSWORD": p["password"]}

    if shutil.which("pg_dump"):
        cmd = [
            "pg_dump", "-h", p["host"], "-p", p["port"],
            "-U", p["user"], "-d", p["dbname"], "--no-owner", "--no-privileges",
        ]
        with open(dest_sql_path, "wb") as out:
            proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, env=env)
    elif settings.pg_container_name:
        cmd = [
            "docker", "exec", "-e", f"PGPASSWORD={p['password']}",
            settings.pg_container_name,
            "pg_dump", "-U", p["user"], "-d", p["dbname"],
            "--no-owner", "--no-privileges",
        ]
        with open(dest_sql_path, "wb") as out:
            proc = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE)
    else:
        raise BackupError(
            "No pg_dump available. Install postgresql-client or set "
            "PG_CONTAINER_NAME to the Postgres container name."
        )

    if proc.returncode != 0:
        raise BackupError(f"pg_dump failed: {proc.stderr.decode(errors='replace')[:400]}")


def create_backup_archive(work_dir: str) -> str:
    """Build the .tar.gz backup in work_dir. Returns the archive path."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive_path = os.path.join(work_dir, f"{BACKUP_PREFIX}{stamp}.tar.gz")

    sql_path = os.path.join(work_dir, "db.sql")
    dump_database(sql_path)

    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(sql_path, arcname="db.sql")
        if os.path.isdir(settings.document_storage_dir):
            tar.add(settings.document_storage_dir, arcname="documents")
        if os.path.isdir(settings.filing_output_dir):
            tar.add(settings.filing_output_dir, arcname="filings")
    return archive_path


def _drive_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        settings.gdrive_service_account_file,
        scopes=["https://www.googleapis.com/auth/drive.file"],
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def upload_to_drive(file_path: str, folder_id: str) -> str:
    """Upload a file into the Drive folder. Returns the Drive file id."""
    from googleapiclient.http import MediaFileUpload

    service = _drive_service()
    metadata = {"name": os.path.basename(file_path), "parents": [folder_id]}
    media = MediaFileUpload(file_path, mimetype="application/gzip", resumable=True)
    created = service.files().create(
        body=metadata, media_body=media, fields="id"
    ).execute()
    return created["id"]


def prune_old_backups(keep: int, folder_id: str) -> int:
    """Delete all but the newest `keep` backup archives in the folder."""
    service = _drive_service()
    resp = service.files().list(
        q=f"'{folder_id}' in parents and name contains '{BACKUP_PREFIX}' and trashed=false",
        orderBy="name desc",
        fields="files(id,name)",
        pageSize=1000,
    ).execute()
    files = resp.get("files", [])
    removed = 0
    for f in files[keep:]:
        service.files().delete(fileId=f["id"]).execute()
        removed += 1
    return removed


async def run_backup() -> dict:
    """Create a backup archive and upload it to Google Drive."""
    if not settings.gdrive_backup_enabled:
        return {"status": "disabled",
                "detail": "Set GDRIVE_BACKUP_ENABLED=true and configure the service account."}
    if not settings.gdrive_service_account_file or not settings.gdrive_backup_folder_id:
        raise BackupError(
            "Backup is enabled but GDRIVE_SERVICE_ACCOUNT_FILE / "
            "GDRIVE_BACKUP_FOLDER_ID are not set."
        )

    def _work() -> dict:
        with tempfile.TemporaryDirectory(prefix="medici-backup-") as work_dir:
            archive = create_backup_archive(work_dir)
            size = os.path.getsize(archive)
            file_id = upload_to_drive(archive, settings.gdrive_backup_folder_id)
            pruned = prune_old_backups(
                settings.backup_keep_count, settings.gdrive_backup_folder_id
            )
            return {
                "status": "ok",
                "archive": os.path.basename(archive),
                "size_bytes": size,
                "drive_file_id": file_id,
                "pruned": pruned,
            }

    return await asyncio.to_thread(_work)
