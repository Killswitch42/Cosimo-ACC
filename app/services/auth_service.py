"""
Authentication service — JWT issue/verify, password hashing, role checks.

Token strategy: short-lived access token (60 min) stored in an HttpOnly
cookie (not localStorage — avoids XSS token theft, works naturally with
server-rendered HTML + HTMX since the browser sends the cookie automatically).
"""
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.user import User

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(
    user_id: uuid.UUID, company_id: uuid.UUID, role: str
) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.app_secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Neplatný nebo expirovaný token. Přihlaste se znovu.",
        )


async def get_current_user(request: Request) -> User:
    """
    FastAPI dependency — extracts JWT from the 'access_token' cookie,
    validates it, and loads the User from the database.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nejste přihlášeni.",
        )
    payload = decode_access_token(token)
    user_id = uuid.UUID(payload["sub"])

    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Uživatel nenalezen nebo deaktivován.",
            )
        return user


def require_role(*allowed_roles: str):
    """
    Dependency factory — restricts an endpoint to specific roles.
    Usage: Depends(require_role("admin", "accountant"))
    """
    async def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Tato akce vyžaduje roli: {', '.join(allowed_roles)}. "
                    f"Vaše role: {user.role}."
                ),
            )
        return user
    return checker


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> User | None:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
