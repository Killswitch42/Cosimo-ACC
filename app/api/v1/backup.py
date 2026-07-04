"""On-demand backup trigger (admin only). Nightly runs are scheduled in main."""
from fastapi import APIRouter, Depends, HTTPException

from app.models.user import User
from app.services.auth_service import require_role
from app.services.backup_service import BackupError, run_backup

router = APIRouter(prefix="/backup", tags=["backup"])


@router.post("/run")
async def trigger_backup(
    user: User = Depends(require_role("admin")),
):
    """Create a backup archive and upload it to Google Drive now."""
    try:
        return await run_backup()
    except BackupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
