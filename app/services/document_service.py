"""
Document storage — attach scanned invoices (PDF / image) to invoice records.

Files land on disk under settings.document_storage_dir, namespaced by company
and invoice; the path is stored on Invoice.document_path (a field that already
existed, unused, since Phase 03). No new table — one document per invoice.
"""
from __future__ import annotations

import os
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.invoice import Invoice

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024  # 10 MB

# content-type → canonical extension for the formats we accept.
ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
}
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}


class DocumentError(Exception):
    pass


def _safe_filename(filename: str) -> str:
    base = os.path.basename(filename or "").strip()
    base = re.sub(r"[^A-Za-z0-9._-]", "_", base)
    return base or "document"


def _extension(filename: str, content_type: str | None) -> str:
    _, ext = os.path.splitext(filename or "")
    ext = ext.lower()
    if ext in ALLOWED_EXTENSIONS:
        return ext
    if content_type and content_type.lower() in ALLOWED_CONTENT_TYPES:
        return ALLOWED_CONTENT_TYPES[content_type.lower()]
    raise DocumentError(
        "Nepodporovaný typ souboru. Povolené formáty: PDF, PNG, JPG."
    )


def save_invoice_document(
    company_id: uuid.UUID,
    invoice_id: uuid.UUID,
    filename: str,
    content: bytes,
    content_type: str | None = None,
) -> str:
    """Validate and persist an invoice document. Returns the stored path."""
    if not content:
        raise DocumentError("Soubor je prázdný.")
    if len(content) > MAX_DOCUMENT_BYTES:
        raise DocumentError("Soubor je příliš velký (max 10 MB).")

    ext = _extension(filename, content_type)
    safe = _safe_filename(filename)
    if not safe.lower().endswith(ext):
        safe = f"{safe}{ext}"

    target_dir = os.path.join(
        settings.document_storage_dir, str(company_id), str(invoice_id)
    )
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, safe)
    with open(path, "wb") as f:
        f.write(content)
    return path


async def get_invoice_document(
    session: AsyncSession, invoice_id: uuid.UUID, company_id: uuid.UUID
) -> tuple[str, str]:
    """Return (path, content_type) for an invoice's stored document."""
    result = await session.execute(
        select(Invoice).where(
            Invoice.id == invoice_id, Invoice.company_id == company_id
        )
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise DocumentError("Faktura nenalezena.")
    if not invoice.document_path or not os.path.exists(invoice.document_path):
        raise DocumentError("K faktuře není přiložen žádný dokument.")

    ext = os.path.splitext(invoice.document_path)[1].lower()
    content_type = {
        ".pdf": "application/pdf",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
    return invoice.document_path, content_type
