import pytest

PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

INVOICE_PAYLOAD = {
    "direction": "ISSUED",
    "invoice_number": "2024/DOC1",
    "invoice_date": "2024-03-15",
    "duzp": "2024-03-10",
    "counterparty_name": "Zákazník s.r.o.",
    "counterparty_dic": "CZ12345678",
    "lines": [
        {
            "description": "Služby",
            "unit_price_net": "1000.00",
            "vat_rate": "21.00",
            "account_number": "602",
        }
    ],
}


async def _login(client):
    login = await client.post(
        "/auth/login",
        data={"email": "admin@medicianalytica.cz", "password": "changeme123"},
        follow_redirects=False,
    )
    client.cookies.set("access_token", login.cookies.get("access_token"))


@pytest.mark.asyncio
async def test_upload_and_download_document(client, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "document_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "xai_api_key", None)

    create = await client.post("/api/v1/invoices/", json=INVOICE_PAYLOAD)
    assert create.status_code == 200
    invoice_id = create.json()["id"]

    await _login(client)

    upload = await client.post(
        f"/api/v1/invoices/{invoice_id}/document",
        files={"file": ("scan.pdf", PDF_BYTES, "application/pdf")},
    )
    assert upload.status_code == 200
    assert upload.json()["document_path"]

    download = await client.get(f"/api/v1/invoices/{invoice_id}/document")
    assert download.status_code == 200
    assert download.content == PDF_BYTES


@pytest.mark.asyncio
async def test_upload_rejects_bad_type(client, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "document_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "xai_api_key", None)

    create = await client.post("/api/v1/invoices/", json={**INVOICE_PAYLOAD, "invoice_number": "2024/DOC2"})
    invoice_id = create.json()["id"]
    await _login(client)

    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/document",
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_upload_requires_auth(client, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "document_storage_dir", str(tmp_path))
    monkeypatch.setattr(settings, "xai_api_key", None)

    create = await client.post("/api/v1/invoices/", json={**INVOICE_PAYLOAD, "invoice_number": "2024/DOC3"})
    invoice_id = create.json()["id"]

    resp = await client.post(
        f"/api/v1/invoices/{invoice_id}/document",
        files={"file": ("scan.pdf", PDF_BYTES, "application/pdf")},
        follow_redirects=False,
    )
    assert resp.status_code in (401, 303, 307)
