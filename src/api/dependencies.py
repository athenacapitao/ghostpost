"""FastAPI dependencies for auth and database sessions."""

from fastapi import Cookie, Depends, Header, HTTPException, status

from src.api.auth import decode_token
from src.config import settings


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    x_api_key: str | None = Header(default=None),
) -> str:
    """Authenticate via httpOnly cookie JWT or X-API-Key header.

    Returns the username string.
    """
    token = None

    # Try X-API-Key header first (for CLI/agent use) — it's a JWT
    if x_api_key:
        token = x_api_key
    elif access_token:
        token = access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = decode_token(token)
        username: str = payload.get("sub", "")
        if username != settings.ADMIN_USERNAME:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        return username
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
