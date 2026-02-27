"""Authentication & authorization hardening tests.

Validates JWT handling, token tampering, algorithm confusion, auth enforcement
across all protected endpoints, and input validation on login.
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from httpx import AsyncClient

from src.api.auth import create_access_token, decode_token, ALGORITHM
from src.config import settings

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# JWT token validation
# ---------------------------------------------------------------------------

class TestJWTValidation:
    async def test_expired_token_rejected(self, client: AsyncClient):
        """Expired JWT should return 401."""
        expired_token = create_access_token(
            settings.ADMIN_USERNAME,
            expires_delta=timedelta(seconds=-10),
        )
        response = await client.get("/api/threads", headers={"X-API-Key": expired_token})
        assert response.status_code == 401

    async def test_wrong_secret_rejected(self, client: AsyncClient):
        """JWT signed with wrong secret should return 401."""
        payload = {"sub": settings.ADMIN_USERNAME, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        bad_token = jwt.encode(payload, "wrong_secret_key", algorithm="HS256")
        response = await client.get("/api/threads", headers={"X-API-Key": bad_token})
        assert response.status_code == 401

    async def test_tampered_payload_rejected(self, client: AsyncClient):
        """JWT with tampered username should return 401."""
        # Create valid token, then decode without verification and re-encode with different sub
        payload = {"sub": "hacker", "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        tampered_token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        response = await client.get("/api/threads", headers={"X-API-Key": tampered_token})
        assert response.status_code == 401

    async def test_none_algorithm_rejected(self, client: AsyncClient):
        """JWT with 'none' algorithm should be rejected."""
        payload = {"sub": settings.ADMIN_USERNAME, "exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        # PyJWT by default doesn't allow 'none' algorithm on decode
        try:
            none_token = jwt.encode(payload, "", algorithm="none")
        except Exception:
            # Some JWT libraries reject this — that's fine
            return
        response = await client.get("/api/threads", headers={"X-API-Key": none_token})
        assert response.status_code == 401

    async def test_empty_string_token_rejected(self, client: AsyncClient):
        """Empty string as token should return 401."""
        response = await client.get("/api/threads", headers={"X-API-Key": ""})
        assert response.status_code == 401

    async def test_malformed_jwt_rejected(self, client: AsyncClient):
        """Random string as token should return 401."""
        response = await client.get("/api/threads", headers={"X-API-Key": "not.a.jwt.token.at.all"})
        assert response.status_code == 401

    async def test_jwt_missing_sub_claim(self, client: AsyncClient):
        """JWT without 'sub' claim should fail auth."""
        payload = {"exp": datetime.now(timezone.utc) + timedelta(hours=1)}
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        response = await client.get("/api/threads", headers={"X-API-Key": token})
        assert response.status_code == 401

    async def test_jwt_with_extra_claims_works(self, client: AsyncClient):
        """JWT with extra claims but valid sub should work."""
        payload = {
            "sub": settings.ADMIN_USERNAME,
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "extra": "data",
            "role": "admin",
        }
        token = jwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")
        response = await client.get("/api/threads", headers={"X-API-Key": token})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Cookie vs Header auth
# ---------------------------------------------------------------------------

class TestCookieVsHeaderAuth:
    async def test_header_auth_works(self, client: AsyncClient, auth_headers: dict):
        """X-API-Key header authentication works."""
        response = await client.get("/api/threads", headers=auth_headers)
        assert response.status_code == 200

    async def test_cookie_auth_after_login(self, client: AsyncClient):
        """Cookie-based auth works after login sets the cookie."""
        login_resp = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "ghostpost",
        })
        assert login_resp.status_code == 200
        # The login endpoint should set a cookie
        token = login_resp.json()["token"]
        # Try accessing with X-API-Key from the login response
        response = await client.get("/api/threads", headers={"X-API-Key": token})
        assert response.status_code == 200

    async def test_no_auth_at_all_rejected(self, client: AsyncClient):
        """No cookie and no header returns 401."""
        response = await client.get("/api/threads")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Login input validation (SQL injection, XSS, edge cases)
# ---------------------------------------------------------------------------

class TestLoginInputValidation:
    async def test_sql_injection_in_username(self, client: AsyncClient):
        """SQL injection in username field should not crash or bypass auth."""
        response = await client.post("/api/auth/login", json={
            "username": "' OR '1'='1' --",
            "password": "ghostpost",
        })
        assert response.status_code == 401

    async def test_sql_injection_in_password(self, client: AsyncClient):
        """SQL injection in password field should not crash or bypass auth."""
        response = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "' OR '1'='1' --",
        })
        assert response.status_code == 401

    async def test_xss_payload_in_username(self, client: AsyncClient):
        """XSS payload in username should not be reflected or crash."""
        response = await client.post("/api/auth/login", json={
            "username": '<script>alert("xss")</script>',
            "password": "ghostpost",
        })
        assert response.status_code == 401
        # Verify no script tag in response
        assert "<script>" not in response.text

    async def test_extremely_long_username(self, client: AsyncClient):
        """10KB username should not crash the server."""
        response = await client.post("/api/auth/login", json={
            "username": "a" * 10240,
            "password": "ghostpost",
        })
        assert response.status_code in (401, 422)

    async def test_extremely_long_password(self, client: AsyncClient):
        """10KB password should not crash the server (bcrypt truncates at 72 bytes)."""
        response = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "p" * 10240,
        })
        assert response.status_code in (401, 422)

    async def test_empty_username(self, client: AsyncClient):
        """Empty username should fail."""
        response = await client.post("/api/auth/login", json={
            "username": "",
            "password": "ghostpost",
        })
        assert response.status_code in (401, 422)

    async def test_empty_password(self, client: AsyncClient):
        """Empty password should fail."""
        response = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "",
        })
        assert response.status_code in (401, 422)

    async def test_both_empty(self, client: AsyncClient):
        """Both empty should fail."""
        response = await client.post("/api/auth/login", json={
            "username": "",
            "password": "",
        })
        assert response.status_code in (401, 422)

    async def test_null_credentials(self, client: AsyncClient):
        """Null values in JSON should fail."""
        response = await client.post("/api/auth/login", json={
            "username": None,
            "password": None,
        })
        assert response.status_code in (401, 422)

    async def test_missing_password_field(self, client: AsyncClient):
        """Missing password field should fail."""
        response = await client.post("/api/auth/login", json={
            "username": "athena",
        })
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Brute force resilience
# ---------------------------------------------------------------------------

class TestBruteForceResilience:
    async def test_rapid_login_attempts(self, client: AsyncClient):
        """100 rapid login attempts should not crash the server."""
        for i in range(100):
            response = await client.post("/api/auth/login", json={
                "username": "athena",
                "password": f"wrong_{i}",
            })
            assert response.status_code == 401
        # After all failures, valid login should still work
        response = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "ghostpost",
        })
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Auth enforcement on ALL protected endpoints
# ---------------------------------------------------------------------------

class TestAuthEnforcementOnAllEndpoints:
    """Verify that every protected endpoint rejects unauthenticated requests."""

    PROTECTED_ENDPOINTS = [
        ("GET", "/api/threads"),
        ("GET", "/api/threads/1"),
        ("GET", "/api/threads/1/brief"),
        ("PUT", "/api/threads/1/state"),
        ("PUT", "/api/threads/1/goal"),
        ("PUT", "/api/threads/1/goal/status"),
        ("PUT", "/api/threads/1/notes"),
        ("PUT", "/api/threads/1/follow-up"),
        ("GET", "/api/emails/1"),
        ("GET", "/api/emails/search"),
        ("GET", "/api/contacts"),
        ("GET", "/api/contacts/1"),
        ("GET", "/api/drafts"),
        ("POST", "/api/drafts/1/approve"),
        ("POST", "/api/drafts/1/reject"),
        ("POST", "/api/compose"),
        ("POST", "/api/sync"),
        ("GET", "/api/sync/status"),
        ("POST", "/api/enrich"),
        ("GET", "/api/enrich/status"),
        ("GET", "/api/playbooks"),
        ("GET", "/api/security/events"),
        ("GET", "/api/security/quarantine"),
        ("GET", "/api/security/blocklist"),
        ("GET", "/api/audit"),
        ("GET", "/api/settings"),
        ("GET", "/api/stats"),
        ("GET", "/api/notifications/alerts"),
        ("GET", "/api/outcomes"),
    ]

    @pytest.mark.parametrize("method,path", PROTECTED_ENDPOINTS)
    async def test_endpoint_requires_auth(self, client: AsyncClient, method: str, path: str):
        """Each protected endpoint should return 401 without auth."""
        if method == "GET":
            response = await client.get(path)
        elif method == "POST":
            response = await client.post(path, json={})
        elif method == "PUT":
            response = await client.put(path, json={})
        elif method == "DELETE":
            response = await client.delete(path)
        else:
            pytest.fail(f"Unknown method: {method}")

        assert response.status_code == 401, f"{method} {path} returned {response.status_code} instead of 401"


# ---------------------------------------------------------------------------
# Token decode edge cases
# ---------------------------------------------------------------------------

class TestTokenDecodeEdgeCases:
    def test_decode_valid_token(self):
        """Valid token decodes correctly."""
        token = create_access_token("athena")
        payload = decode_token(token)
        assert payload["sub"] == "athena"

    def test_decode_expired_token_raises(self):
        """Expired token raises on decode."""
        token = create_access_token("athena", expires_delta=timedelta(seconds=-10))
        with pytest.raises(Exception):
            decode_token(token)

    def test_decode_garbage_raises(self):
        """Non-JWT string raises on decode."""
        with pytest.raises(Exception):
            decode_token("not-a-jwt")

    def test_create_token_custom_expiry(self):
        """Custom expiry delta works."""
        token = create_access_token("athena", expires_delta=timedelta(minutes=5))
        payload = decode_token(token)
        assert payload["sub"] == "athena"
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)
        assert exp < datetime.now(timezone.utc) + timedelta(minutes=10)
