"""Shared fixtures for GhostPost integration tests.

Design decisions:
- `client` is function-scoped: each test gets a fresh AsyncClient with no
  residual cookie state. The ASGI app lifespan (DB connect, Redis ping,
  scheduler start) runs once per test. This is slightly slower than a
  session-scoped client but avoids cookie contamination between tests.
- `auth_headers` is session-scoped: it only generates a JWT from settings,
  requires no DB call, and is safe to share across tests.
- Data fixtures (sample_thread, sample_email, sample_contact) are function-
  scoped: each test gets a fresh row and the row is deleted in teardown.
"""

import pytest
import pytest_asyncio
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from src.api.auth import create_access_token
from src.config import settings
from src.db.models import Thread, Email, Contact
from src.db.session import async_session
from src.main import app


# ---------------------------------------------------------------------------
# Global guard — prevent any test from writing to the real context/ALERTS.md
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _block_alerts_file_writes(request: pytest.FixtureRequest):
    """Patch _append_alert so no test can write to the real context/ALERTS.md.

    This is an autouse fixture that applies to every test in the suite. The
    real _append_alert opens and rewrites a production file on disk; calling it
    from tests with MagicMock arguments produces corrupt entries like
    "<MagicMock name='mock.subject' id='...'>". Blocking it at this level is
    simpler and more reliable than patching notify_goal_met in every callsite.

    Tests that deliberately exercise the file-writing path and already redirect
    ALERTS_FILE to a temp directory must opt out by marking themselves with
    @pytest.mark.allow_alerts_file_write.
    """
    if request.node.get_closest_marker("allow_alerts_file_write"):
        # Test handles file isolation itself — let _append_alert run normally
        yield
    else:
        with patch("src.engine.notifications._append_alert"):
            yield


# ---------------------------------------------------------------------------
# Auth headers — JWT only, no DB, safe to generate once per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def auth_headers():
    """Return X-API-Key header with a valid JWT for the admin user."""
    token = create_access_token(settings.ADMIN_USERNAME)
    return {"X-API-Key": token}


# ---------------------------------------------------------------------------
# HTTP client — fresh instance per test (no shared cookie jar)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired to the FastAPI app via ASGI transport.

    Function-scoped so each test starts with a clean cookie jar. The app
    lifespan (DB + Redis connectivity checks, scheduler) runs on each client
    open/close. Tests that do not call client fixtures avoid this cost.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Sample data fixtures — function-scoped; insert before test, delete after
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def sample_thread():
    """Insert a Thread row; delete it after the test completes."""
    async with async_session() as session:
        thread = Thread(
            gmail_thread_id="inttest_thread_001",
            subject="Integration Test Thread",
            state="ACTIVE",
            priority="medium",
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        thread_id = thread.id
        # Detach so the object is usable outside this session
        session.expunge(thread)

    yield thread

    async with async_session() as session:
        obj = await session.get(Thread, thread_id)
        if obj:
            await session.delete(obj)
            await session.commit()


@pytest_asyncio.fixture
async def sample_email(sample_thread: Thread):
    """Insert an Email row linked to sample_thread; delete it after the test."""
    from datetime import datetime, timezone

    async with async_session() as session:
        email = Email(
            gmail_id="inttest_email_001",
            thread_id=sample_thread.id,
            message_id="<inttest@example.com>",
            from_address="sender@example.com",
            to_addresses=["athenacapitao@gmail.com"],
            subject="Integration Test Thread",
            body_plain="Integration test email body.",
            date=datetime.now(timezone.utc),
            is_read=False,
            is_sent=False,
            is_draft=False,
        )
        session.add(email)
        await session.commit()
        await session.refresh(email)
        email_id = email.id
        session.expunge(email)

    yield email

    async with async_session() as session:
        obj = await session.get(Email, email_id)
        if obj:
            await session.delete(obj)
            await session.commit()


@pytest_asyncio.fixture
async def sample_contact():
    """Insert a Contact row; delete it after the test completes."""
    async with async_session() as session:
        contact = Contact(
            email="inttest_contact@example.com",
            name="Integration Tester",
            relationship_type="contact",
        )
        session.add(contact)
        await session.commit()
        await session.refresh(contact)
        contact_id = contact.id
        session.expunge(contact)

    yield contact

    async with async_session() as session:
        obj = await session.get(Contact, contact_id)
        if obj:
            await session.delete(obj)
            await session.commit()
