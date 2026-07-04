import os

import pytest

from app.config import settings
from app.services import backup_service
from app.services.backup_service import BackupError, run_backup


@pytest.mark.asyncio
async def test_run_backup_disabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "gdrive_backup_enabled", False)
    result = await run_backup()
    assert result["status"] == "disabled"


@pytest.mark.asyncio
async def test_run_backup_enabled_missing_config_raises(monkeypatch):
    monkeypatch.setattr(settings, "gdrive_backup_enabled", True)
    monkeypatch.setattr(settings, "gdrive_service_account_file", None)
    monkeypatch.setattr(settings, "gdrive_backup_folder_id", None)
    with pytest.raises(BackupError):
        await run_backup()


@pytest.mark.asyncio
async def test_run_backup_happy_path_mocked(monkeypatch):
    monkeypatch.setattr(settings, "gdrive_backup_enabled", True)
    monkeypatch.setattr(settings, "gdrive_service_account_file", "/tmp/fake-sa.json")
    monkeypatch.setattr(settings, "gdrive_backup_folder_id", "FOLDER123")

    def fake_archive(work_dir):
        path = os.path.join(work_dir, "medici-backup-test.tar.gz")
        with open(path, "wb") as f:
            f.write(b"x" * 10)
        return path

    captured = {}

    def fake_upload(path, folder_id):
        captured["uploaded"] = (os.path.basename(path), folder_id)
        return "DRIVEFILEID"

    monkeypatch.setattr(backup_service, "create_backup_archive", fake_archive)
    monkeypatch.setattr(backup_service, "upload_to_drive", fake_upload)
    monkeypatch.setattr(backup_service, "prune_old_backups", lambda keep, folder_id: 3)

    result = await run_backup()
    assert result["status"] == "ok"
    assert result["drive_file_id"] == "DRIVEFILEID"
    assert result["size_bytes"] == 10
    assert result["pruned"] == 3
    assert captured["uploaded"][1] == "FOLDER123"
