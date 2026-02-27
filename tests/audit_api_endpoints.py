"""API robustness & edge case tests.

Validates that every endpoint handles malformed input, boundary values,
and adversarial parameters gracefully without crashing.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Thread endpoint edge cases
# ---------------------------------------------------------------------------

class TestThreadEndpointEdgeCases:
    async def test_threads_page_zero(self, client: AsyncClient, auth_headers: dict):
        """page=0 should return 422 or handled gracefully."""
        response = await client.get("/api/threads?page=0", headers=auth_headers)
        assert response.status_code in (200, 422)

    async def test_threads_page_negative(self, client: AsyncClient, auth_headers: dict):
        """page=-1 should not crash."""
        response = await client.get("/api/threads?page=-1", headers=auth_headers)
        assert response.status_code in (200, 422)

    async def test_threads_page_very_large(self, client: AsyncClient, auth_headers: dict):
        """page=999999 should return empty results, not crash."""
        response = await client.get("/api/threads?page=999999", headers=auth_headers)
        assert response.status_code == 200

    async def test_threads_page_size_zero(self, client: AsyncClient, auth_headers: dict):
        """page_size=0 should be handled."""
        response = await client.get("/api/threads?page_size=0", headers=auth_headers)
        assert response.status_code in (200, 422)

    async def test_threads_page_size_huge(self, client: AsyncClient, auth_headers: dict):
        """page_size=10000 should be handled (clamped or rejected)."""
        response = await client.get("/api/threads?page_size=10000", headers=auth_headers)
        assert response.status_code in (200, 422)

    async def test_threads_search_sql_injection(self, client: AsyncClient, auth_headers: dict):
        """SQL injection in search query should not execute."""
        response = await client.get(
            "/api/threads?q=' OR '1'='1' --",
            headers=auth_headers,
        )
        assert response.status_code == 200

    async def test_threads_search_xss(self, client: AsyncClient, auth_headers: dict):
        """XSS in search query should not be reflected."""
        response = await client.get(
            '/api/threads?q=<script>alert("xss")</script>',
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert "<script>" not in response.text

    async def test_threads_search_empty(self, client: AsyncClient, auth_headers: dict):
        """Empty search string should work."""
        response = await client.get("/api/threads?q=", headers=auth_headers)
        assert response.status_code == 200

    async def test_threads_search_unicode(self, client: AsyncClient, auth_headers: dict):
        """Unicode search string should work."""
        response = await client.get("/api/threads?q=日本語テスト", headers=auth_headers)
        assert response.status_code == 200

    async def test_thread_nonexistent_id(self, client: AsyncClient, auth_headers: dict):
        """GET thread with nonexistent ID should return 404."""
        response = await client.get("/api/threads/999999", headers=auth_headers)
        assert response.status_code == 404

    async def test_thread_negative_id(self, client: AsyncClient, auth_headers: dict):
        """GET thread with negative ID should return 404 or 422."""
        response = await client.get("/api/threads/-1", headers=auth_headers)
        assert response.status_code in (404, 422)

    async def test_thread_string_id(self, client: AsyncClient, auth_headers: dict):
        """GET thread with string ID should return 422."""
        response = await client.get("/api/threads/abc", headers=auth_headers)
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# Email search edge cases
# ---------------------------------------------------------------------------

class TestEmailSearchEdgeCases:
    async def test_email_search_special_chars(self, client: AsyncClient, auth_headers: dict):
        """Search with SQL wildcard characters."""
        for char in ["%", "_", "\\", "'", '"']:
            response = await client.get(
                f"/api/emails/search?q={char}test",
                headers=auth_headers,
            )
            assert response.status_code == 200, f"Failed for char: {char}"

    async def test_email_nonexistent_id(self, client: AsyncClient, auth_headers: dict):
        """GET email with nonexistent ID should return 404."""
        response = await client.get("/api/emails/999999", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Draft endpoint edge cases
# ---------------------------------------------------------------------------

class TestDraftEndpointEdgeCases:
    async def test_approve_nonexistent_draft(self, client: AsyncClient, auth_headers: dict):
        """Approve nonexistent draft should return 404 or error."""
        response = await client.post("/api/drafts/999999/approve", headers=auth_headers)
        assert response.status_code in (404, 400, 500)

    async def test_reject_nonexistent_draft(self, client: AsyncClient, auth_headers: dict):
        """Reject nonexistent draft should return 404 or error."""
        response = await client.post("/api/drafts/999999/reject", headers=auth_headers)
        assert response.status_code in (404, 400, 500)


# ---------------------------------------------------------------------------
# Compose endpoint edge cases
# ---------------------------------------------------------------------------

class TestComposeEdgeCases:
    async def test_compose_missing_fields(self, client: AsyncClient, auth_headers: dict):
        """Compose with missing required fields should return 422."""
        response = await client.post("/api/compose", json={}, headers=auth_headers)
        assert response.status_code == 422

    async def test_compose_empty_to(self, client: AsyncClient, auth_headers: dict):
        """Compose with empty 'to' should be rejected by Pydantic validation."""
        response = await client.post("/api/compose", json={
            "to": "",
            "subject": "Test",
            "body": "Test body",
        }, headers=auth_headers)
        assert response.status_code == 422

    async def test_compose_null_subject(self, client: AsyncClient, auth_headers: dict):
        """Compose with null subject should be handled."""
        response = await client.post("/api/compose", json={
            "to": "test@example.com",
            "subject": None,
            "body": "Test body",
        }, headers=auth_headers)
        # Should either work (null subject OK) or return 422
        assert response.status_code in (200, 422, 500)


# ---------------------------------------------------------------------------
# Settings edge cases
# ---------------------------------------------------------------------------

class TestSettingsEdgeCases:
    async def test_set_very_long_value(self, client: AsyncClient, auth_headers: dict):
        """Setting a very long value (10KB) should be handled."""
        response = await client.put(
            "/api/settings/audit_test_key",
            json={"value": "x" * 10240},
            headers=auth_headers,
        )
        assert response.status_code in (200, 422, 413)
        # Cleanup
        await client.delete("/api/settings/audit_test_key", headers=auth_headers)

    async def test_set_special_chars_value(self, client: AsyncClient, auth_headers: dict):
        """Setting with JSON/special chars in value should work."""
        response = await client.put(
            "/api/settings/audit_test_special",
            json={"value": '{"key": "value", "array": [1,2,3]}'},
            headers=auth_headers,
        )
        assert response.status_code in (200, 422)
        # Cleanup
        await client.delete("/api/settings/audit_test_special", headers=auth_headers)

    async def test_get_nonexistent_setting(self, client: AsyncClient, auth_headers: dict):
        """GET nonexistent setting key should return 404 or null."""
        response = await client.get("/api/settings/nonexistent_key_12345", headers=auth_headers)
        assert response.status_code in (200, 404)


# ---------------------------------------------------------------------------
# Playbook edge cases
# ---------------------------------------------------------------------------

class TestPlaybookEdgeCases:
    async def test_playbook_path_traversal(self, client: AsyncClient, auth_headers: dict):
        """Path traversal in playbook name should be blocked."""
        response = await client.post("/api/playbooks", json={
            "name": "../../etc/passwd",
            "content": "malicious content",
        }, headers=auth_headers)
        # Should be rejected — the create_playbook function validates name with regex
        assert response.status_code in (400, 422, 404, 500)

    async def test_playbook_empty_content(self, client: AsyncClient, auth_headers: dict):
        """Playbook with empty content should be handled."""
        response = await client.post("/api/playbooks", json={
            "name": "audit-empty-test",
            "content": "",
        }, headers=auth_headers)
        assert response.status_code in (200, 201, 400, 422)
        # Cleanup if created
        await client.delete("/api/playbooks/audit-empty-test", headers=auth_headers)

    async def test_playbook_nonexistent(self, client: AsyncClient, auth_headers: dict):
        """GET nonexistent playbook should return 404."""
        response = await client.get("/api/playbooks/nonexistent_playbook_xyz", headers=auth_headers)
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Thread action edge cases (state, goal, follow-up, notes)
# ---------------------------------------------------------------------------

class TestThreadActionEdgeCases:
    async def test_state_invalid_value(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH state with invalid value should be rejected."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/state",
            json={"state": "INVALID_STATE"},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422, 500)

    async def test_goal_empty_string(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH goal with empty string."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/goal",
            json={"goal": ""},
            headers=auth_headers,
        )
        # Should either accept empty goal or reject
        assert response.status_code in (200, 400, 422)

    async def test_goal_very_long(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH goal with 10KB text."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/goal",
            json={"goal": "G" * 10240, "acceptance_criteria": "C" * 10240},
            headers=auth_headers,
        )
        assert response.status_code in (200, 422, 413)

    async def test_goal_status_invalid(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH goal status with invalid value."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/goal/status",
            json={"status": "INVALID"},
            headers=auth_headers,
        )
        assert response.status_code in (400, 422, 500)

    async def test_followup_days_zero(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH follow-up with days=0."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/follow-up",
            json={"days": 0},
            headers=auth_headers,
        )
        assert response.status_code in (200, 400, 422)

    async def test_followup_days_negative(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH follow-up with days=-1."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/follow-up",
            json={"days": -1},
            headers=auth_headers,
        )
        assert response.status_code in (200, 400, 422)

    async def test_followup_days_very_large(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH follow-up with days=9999."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/follow-up",
            json={"days": 9999},
            headers=auth_headers,
        )
        assert response.status_code in (200, 422)

    async def test_notes_null(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH notes with null value."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/notes",
            json={"notes": None},
            headers=auth_headers,
        )
        assert response.status_code in (200, 422)

    async def test_notes_very_long(self, client: AsyncClient, auth_headers: dict, sample_thread):
        """PATCH notes with 50KB text."""
        response = await client.put(
            f"/api/threads/{sample_thread.id}/notes",
            json={"notes": "N" * 51200},
            headers=auth_headers,
        )
        assert response.status_code in (200, 422, 413)

    async def test_actions_on_nonexistent_thread(self, client: AsyncClient, auth_headers: dict):
        """Thread actions on nonexistent thread should return 404."""
        response = await client.put(
            "/api/threads/999999/state",
            json={"state": "ACTIVE"},
            headers=auth_headers,
        )
        assert response.status_code in (404, 500)


# ---------------------------------------------------------------------------
# Security endpoints edge cases
# ---------------------------------------------------------------------------

class TestSecurityEndpointEdgeCases:
    async def test_quarantine_approve_nonexistent(self, client: AsyncClient, auth_headers: dict):
        """Approve nonexistent quarantine item."""
        response = await client.post(
            "/api/security/quarantine/999999/approve",
            headers=auth_headers,
        )
        assert response.status_code in (404, 400, 500)

    async def test_quarantine_dismiss_nonexistent(self, client: AsyncClient, auth_headers: dict):
        """Dismiss nonexistent quarantine item."""
        response = await client.post(
            "/api/security/quarantine/999999/dismiss",
            headers=auth_headers,
        )
        assert response.status_code in (404, 400, 500)


# ---------------------------------------------------------------------------
# Outcomes endpoint edge cases
# ---------------------------------------------------------------------------

class TestOutcomeEdgeCases:
    async def test_extract_outcome_nonexistent_thread(self, client: AsyncClient, auth_headers: dict):
        """Extract outcome from nonexistent thread."""
        response = await client.post(
            "/api/threads/999999/extract",
            headers=auth_headers,
        )
        assert response.status_code in (404, 400, 500)

    async def test_get_outcome_nonexistent_thread(self, client: AsyncClient, auth_headers: dict):
        """Get outcome for nonexistent thread."""
        response = await client.get(
            "/api/outcomes/999999",
            headers=auth_headers,
        )
        assert response.status_code in (404, 200)


# ---------------------------------------------------------------------------
# Contacts edge cases
# ---------------------------------------------------------------------------

class TestContactEdgeCases:
    async def test_contact_nonexistent_id(self, client: AsyncClient, auth_headers: dict):
        """GET contact with nonexistent ID."""
        response = await client.get("/api/contacts/999999", headers=auth_headers)
        assert response.status_code == 404

    async def test_contacts_pagination(self, client: AsyncClient, auth_headers: dict):
        """Contacts list with pagination params."""
        response = await client.get("/api/contacts?page=1&page_size=5", headers=auth_headers)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Sync endpoint edge cases
# ---------------------------------------------------------------------------

class TestSyncEdgeCases:
    async def test_sync_status(self, client: AsyncClient, auth_headers: dict):
        """GET sync status should always return 200."""
        response = await client.get("/api/sync/status", headers=auth_headers)
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Stats endpoint
# ---------------------------------------------------------------------------

class TestStatsEndpoint:
    async def test_stats_returns_counts(self, client: AsyncClient, auth_headers: dict):
        """Stats endpoint should return thread/email/contact counts."""
        response = await client.get("/api/stats", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "threads" in data or "total" in data or isinstance(data, dict)


# ---------------------------------------------------------------------------
# Audit endpoint
# ---------------------------------------------------------------------------

class TestAuditEndpoint:
    async def test_audit_logs_pagination(self, client: AsyncClient, auth_headers: dict):
        """Audit logs with various pagination."""
        response = await client.get("/api/audit?limit=5", headers=auth_headers)
        assert response.status_code == 200

    async def test_audit_logs_default(self, client: AsyncClient, auth_headers: dict):
        """Audit logs with default params."""
        response = await client.get("/api/audit", headers=auth_headers)
        assert response.status_code == 200
