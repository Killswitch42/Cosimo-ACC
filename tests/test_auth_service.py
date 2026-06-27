import uuid

import pytest

from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    hashed = hash_password("supersecret123")
    assert verify_password("supersecret123", hashed)
    assert not verify_password("wrongpassword", hashed)


def test_token_roundtrip():
    user_id = uuid.uuid4()
    company_id = uuid.uuid4()
    token = create_access_token(user_id, company_id, "admin")
    payload = decode_access_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["company_id"] == str(company_id)
    assert payload["role"] == "admin"


def test_invalid_token_raises():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        decode_access_token("not.a.valid.token")
