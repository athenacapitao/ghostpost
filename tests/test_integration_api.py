"""Integration tests for GhostPost API endpoints.

These tests hit the real FastAPI app via ASGI transport with real PostgreSQL
and Redis. They verify routing, auth enforcement, response shapes, and basic
data flow — things unit tests with mocks cannot catch.

Each test class targets a specific router. Tests are ordered from simplest
(no auth needed) to most complex (data-dependent CRUD).
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:
    async def test_health_returns_ok_with_all_services_up(self, client: AsyncClient):
        """Health endpoint should confirm DB and Redis are reachable."""
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["db"] is True
        assert data["redis"] is True

    async def test_health_returns_json_content_type(self, client: AsyncClient):
        response = await client.get("/api/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class TestAuthEndpoints:
    async def test_login_with_valid_credentials_returns_token(self, client: AsyncClient):
        """Successful login must return a JWT token in the response body."""
        response = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "ghostpost",
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert len(data["token"]) > 20  # real JWT, not empty

    async def test_login_wrong_password_returns_401(self, client: AsyncClient):
        response = await client.post("/api/auth/login", json={
            "username": "athena",
            "password": "wrong_password",
        })
        assert response.status_code == 401

    async def test_login_wrong_username_returns_401(self, client: AsyncClient):
        response = await client.post("/api/auth/login", json={
            "username": "notauser",
            "password": "ghostpost",
        })
        assert response.status_code == 401

    async def test_protected_endpoint_without_auth_returns_401(self, client: AsyncClient):
        """Any protected endpoint must reject unauthenticated requests."""
        response = await client.get("/api/threads")
        assert response.status_code == 401

    async def test_me_endpoint_returns_current_user(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["username"] == "athena"

    async def test_invalid_token_returns_401(self, client: AsyncClient):
        response = await client.get("/api/auth/me", headers={"X-API-Key": "not.a.jwt"})
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Threads
# ---------------------------------------------------------------------------

class TestThreadListEndpoint:
    async def test_list_threads_returns_pagination_envelope(self, client: AsyncClient, auth_headers: dict):
        """Thread list must return items + total + page metadata."""
        response = await client.get("/api/threads", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "page_size" in data
        assert "pages" in data

    async def test_list_threads_total_is_non_negative(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/threads", headers=auth_headers)
        data = response.json()
        assert data["total"] >= 0

    async def test_list_threads_state_filter_limits_results(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        """Filtering by state=ACTIVE must only return threads in that state."""
        response = await client.get("/api/threads?state=ACTIVE", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["state"] == "ACTIVE"

    async def test_list_threads_page_size_is_respected(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/threads?page_size=3", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 3

    async def test_list_threads_invalid_page_size_returns_422(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/threads?page_size=0", headers=auth_headers)
        assert response.status_code == 422


class TestThreadDetailEndpoint:
    async def test_get_existing_thread_returns_detail(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        """Fetching a thread that exists must return full thread data."""
        response = await client.get(f"/api/threads/{sample_thread.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_thread.id
        assert data["subject"] == sample_thread.subject
        assert data["state"] == "ACTIVE"

    async def test_get_nonexistent_thread_returns_404(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/threads/999999999", headers=auth_headers)
        assert response.status_code == 404

    async def test_thread_detail_includes_emails_list(
        self, client: AsyncClient, auth_headers: dict, sample_thread, sample_email
    ):
        """Thread detail must expose the emails relationship."""
        response = await client.get(f"/api/threads/{sample_thread.id}", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "emails" in data
        assert isinstance(data["emails"], list)
        email_ids = [e["id"] for e in data["emails"]]
        assert sample_email.id in email_ids


class TestThreadStateEndpoint:
    async def test_update_thread_state_to_valid_state(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        """State transition to a valid state must succeed and return old+new states."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/state",
            json={"state": "ARCHIVED", "reason": "integration test"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_state"] == "ARCHIVED"
        assert "old_state" in data

    async def test_update_thread_state_invalid_state_returns_400(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        response = await client.put(
            f"/api/threads/{sample_thread.id}/state",
            json={"state": "INVALID"},
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_update_state_nonexistent_thread_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.put(
            "/api/threads/999999999/state",
            json={"state": "ACTIVE"},
            headers=auth_headers,
        )
        assert response.status_code == 404


class TestThreadGoalEndpoint:
    async def test_set_goal_on_existing_thread(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        """Setting a goal must succeed and be visible on subsequent GET."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/goal",
            json={"goal": "Close the deal", "acceptance_criteria": "Written confirmation"},
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["goal"] == "Close the deal"

    async def test_set_goal_on_nonexistent_thread_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.put(
            "/api/threads/999999999/goal",
            json={"goal": "Some goal"},
            headers=auth_headers,
        )
        assert response.status_code == 404

    async def test_delete_goal_on_existing_thread(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        """Clearing a goal must succeed."""
        # First set a goal
        await client.put(
            f"/api/threads/{sample_thread.id}/goal",
            json={"goal": "Temp goal"},
            headers=auth_headers,
        )
        # Then clear it
        response = await client.delete(
            f"/api/threads/{sample_thread.id}/goal",
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_update_notes_on_thread(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        response = await client.put(
            f"/api/threads/{sample_thread.id}/notes",
            json={"notes": "These are integration test notes."},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["notes"] == "These are integration test notes."


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStatsEndpoint:
    async def test_stats_returns_expected_fields(self, client: AsyncClient, auth_headers: dict):
        """Stats endpoint must return counts and DB size."""
        response = await client.get("/api/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_threads" in data
        assert "total_emails" in data
        assert "total_contacts" in data
        assert "total_attachments" in data
        assert "unread_emails" in data
        assert "db_size_mb" in data

    async def test_stats_counts_are_non_negative(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/stats", headers=auth_headers)
        data = response.json()
        assert data["total_threads"] >= 0
        assert data["total_emails"] >= 0
        assert data["db_size_mb"] >= 0


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class TestSettingsEndpoints:
    async def test_list_settings_returns_all_defaults(self, client: AsyncClient, auth_headers: dict):
        """Settings list must include all configured default keys."""
        response = await client.get("/api/settings", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "reply_style" in data
        assert "default_follow_up_days" in data
        assert "notification_new_email" in data
        assert "notification_goal_met" in data

    async def test_update_setting_persists_value(self, client: AsyncClient, auth_headers: dict):
        """Updated setting value must be retrievable immediately after write."""
        await client.put(
            "/api/settings/reply_style",
            json={"value": "casual"},
            headers=auth_headers,
        )
        response = await client.get("/api/settings/reply_style", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["value"] == "casual"

        # Reset to default to avoid polluting other tests
        await client.put(
            "/api/settings/reply_style",
            json={"value": "professional"},
            headers=auth_headers,
        )

    async def test_bulk_update_rejects_unknown_keys(self, client: AsyncClient, auth_headers: dict):
        """Bulk update with an unknown key must return 400."""
        response = await client.put(
            "/api/settings/bulk",
            json={"settings": {"totally_unknown_key": "value"}},
            headers=auth_headers,
        )
        assert response.status_code == 400

    async def test_bulk_update_valid_keys_succeeds(self, client: AsyncClient, auth_headers: dict):
        response = await client.put(
            "/api/settings/bulk",
            json={"settings": {"reply_style": "professional", "default_follow_up_days": "5"}},
            headers=auth_headers,
        )
        assert response.status_code == 200
        # Restore default
        await client.put(
            "/api/settings/bulk",
            json={"settings": {"default_follow_up_days": "3"}},
            headers=auth_headers,
        )

    async def test_get_unknown_setting_returns_404(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/settings/no_such_setting", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Playbooks
# ---------------------------------------------------------------------------

class TestPlaybookEndpoints:
    async def test_list_playbooks_returns_list(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/playbooks", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_create_read_delete_playbook_lifecycle(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Full playbook lifecycle: create -> read -> delete."""
        name = "inttest-playbook"
        content = "# Integration Test Playbook\n\nStep 1: Verify things work."

        # Create
        create_resp = await client.post(
            f"/api/playbooks?name={name}",
            json={"content": content},
            headers=auth_headers,
        )
        assert create_resp.status_code == 200

        # Read back
        get_resp = await client.get(f"/api/playbooks/{name}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert "Integration Test Playbook" in get_resp.text

        # Delete
        del_resp = await client.delete(f"/api/playbooks/{name}", headers=auth_headers)
        assert del_resp.status_code == 200

        # Confirm gone
        gone_resp = await client.get(f"/api/playbooks/{name}", headers=auth_headers)
        assert gone_resp.status_code == 404

    async def test_create_duplicate_playbook_returns_400(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Creating a playbook with an existing name must fail."""
        name = "inttest-dup-playbook"
        payload = {"content": "# Duplicate"}

        await client.post(f"/api/playbooks?name={name}", json=payload, headers=auth_headers)
        dup_resp = await client.post(f"/api/playbooks?name={name}", json=payload, headers=auth_headers)
        assert dup_resp.status_code == 400

        # Cleanup
        await client.delete(f"/api/playbooks/{name}", headers=auth_headers)

    async def test_get_nonexistent_playbook_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/playbooks/does-not-exist", headers=auth_headers)
        assert response.status_code == 404

    async def test_delete_nonexistent_playbook_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.delete("/api/playbooks/does-not-exist", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

class TestSecurityEndpoints:
    async def test_list_quarantine_events_returns_list(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/security/quarantine", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_list_security_events_returns_list(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/security/events", headers=auth_headers)
        assert response.status_code == 200

    async def test_list_blocklist_returns_dict_with_blocklist_key(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Blocklist endpoint returns {"blocklist": [...]} not a bare list."""
        response = await client.get("/api/security/blocklist", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "blocklist" in data
        assert isinstance(data["blocklist"], list)

    async def test_blocklist_add_and_remove(self, client: AsyncClient, auth_headers: dict):
        """Adding then removing an address from the blocklist must round-trip cleanly."""
        address = "inttest-block@example.com"

        add_resp = await client.post(
            "/api/security/blocklist",
            json={"email": address},
            headers=auth_headers,
        )
        assert add_resp.status_code == 200

        # Confirm it is in the list
        list_resp = await client.get("/api/security/blocklist", headers=auth_headers)
        blocklist = list_resp.json()["blocklist"]
        assert address in blocklist

        # Remove it (httpx DELETE does not support json= keyword; use content + header)
        import json as json_lib
        del_resp = await client.request(
            "DELETE",
            "/api/security/blocklist",
            content=json_lib.dumps({"email": address}),
            headers={**auth_headers, "content-type": "application/json"},
        )
        assert del_resp.status_code == 200

        # Confirm it is gone
        list_resp2 = await client.get("/api/security/blocklist", headers=auth_headers)
        assert address not in list_resp2.json()["blocklist"]


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

class TestAuditEndpoint:
    async def test_audit_log_returns_list(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/audit", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)


# ---------------------------------------------------------------------------
# Outcomes
# ---------------------------------------------------------------------------

class TestOutcomeEndpoints:
    async def test_list_outcomes_returns_list(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/outcomes", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    async def test_extract_nonexistent_thread_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.post("/api/threads/999999999/extract", headers=auth_headers)
        assert response.status_code == 404

    async def test_extract_active_thread_returns_400(
        self, client: AsyncClient, auth_headers: dict, sample_thread
    ):
        """Outcome extraction is only allowed for GOAL_MET or ARCHIVED threads."""
        # sample_thread is in ACTIVE state
        response = await client.post(
            f"/api/threads/{sample_thread.id}/extract",
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "state" in response.json()["detail"].lower()

    async def test_get_outcome_nonexistent_thread_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/outcomes/999999999", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

class TestContactsEndpoints:
    async def test_list_contacts_returns_paginated_envelope(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Contacts list returns a paginated envelope, not a bare list."""
        response = await client.get("/api/contacts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert isinstance(data["items"], list)

    async def test_get_nonexistent_contact_returns_404(
        self, client: AsyncClient, auth_headers: dict
    ):
        response = await client.get("/api/contacts/999999999", headers=auth_headers)
        assert response.status_code == 404

    async def test_created_contact_appears_in_list(
        self, client: AsyncClient, auth_headers: dict, sample_contact
    ):
        """A contact inserted directly into the DB must be visible via the API."""
        response = await client.get("/api/contacts", headers=auth_headers)
        assert response.status_code == 200
        # Search across all pages by email — use search query param to filter
        search_resp = await client.get(
            f"/api/contacts?q={sample_contact.email}", headers=auth_headers
        )
        assert search_resp.status_code == 200
        items = search_resp.json()["items"]
        emails = [c["email"] for c in items]
        assert sample_contact.email in emails


# ---------------------------------------------------------------------------
# Drafts
# ---------------------------------------------------------------------------

class TestDraftsEndpoint:
    async def test_list_drafts_returns_list(self, client: AsyncClient, auth_headers: dict):
        response = await client.get("/api/drafts", headers=auth_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)
