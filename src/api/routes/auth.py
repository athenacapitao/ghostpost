"""Authentication routes — login, logout, me."""

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from src.api.auth import create_access_token, verify_password
from src.api.dependencies import get_current_user
from src.config import settings

logger = logging.getLogger("ghostpost.auth")

LOGIN_RATE_LIMIT = 5  # max attempts
LOGIN_RATE_WINDOW = 900  # 15 minutes

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    message: str
    token: str


class UserResponse(BaseModel):
    username: str


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request, response: Response):
    # Rate limit by IP: 5 attempts per 15 minutes
    client_ip = request.client.host if request.client else "unknown"
    r = aioredis.from_url(settings.REDIS_URL)
    try:
        rate_key = f"ghostpost:login_rate:{client_ip}"
        attempts = await r.get(rate_key)
        attempts = int(attempts) if attempts else 0
        if attempts >= LOGIN_RATE_LIMIT:
            logger.warning(f"Login rate limit exceeded for {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts. Try again later.",
            )
    finally:
        await r.aclose()

    if body.username != settings.ADMIN_USERNAME or not verify_password(
        body.password, settings.ADMIN_PASSWORD_HASH
    ):
        # Increment failed attempt counter
        r = aioredis.from_url(settings.REDIS_URL)
        try:
            rate_key = f"ghostpost:login_rate:{client_ip}"
            count = await r.incr(rate_key)
            if count == 1:
                await r.expire(rate_key, LOGIN_RATE_WINDOW)
        finally:
            await r.aclose()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(subject=body.username)

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=86400,
    )

    return LoginResponse(message="Login successful", token=token)


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserResponse)
async def me(username: str = Depends(get_current_user)):
    return UserResponse(username=username)
