"""Tests for the batch email queue system."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

from src.engine.batch import (
    CLUSTER_SIZE,
    _split_into_clusters,
    create_batch_job,
    process_next_cluster,
    cancel_batch,
    resume_pending_batches,
)


# ---------------------------------------------------------------------------
# Cluster splitting (pure logic, no mocking)
# ---------------------------------------------------------------------------

class TestSplitIntoClusters:
    def test_50_recipients_gives_3_clusters(self):
        recipients = [f"user{i}@example.com" for i in range(50)]
        clusters = _split_into_clusters(recipients)
        assert len(clusters) == 3
        assert len(clusters[0]) == 20
        assert len(clusters[1]) == 20
        assert len(clusters[2]) == 10

    def test_20_recipients_gives_1_cluster(self):
        recipients = [f"user{i}@example.com" for i in range(20)]
        clusters = _split_into_clusters(recipients)
        assert len(clusters) == 1
        assert len(clusters[0]) == 20

    def test_1_recipient_gives_1_cluster(self):
        clusters = _split_into_clusters(["solo@example.com"])
        assert len(clusters) == 1
        assert clusters[0] == ["solo@example.com"]

    def test_40_recipients_gives_2_clusters(self):
        recipients = [f"user{i}@example.com" for i in range(40)]
        clusters = _split_into_clusters(recipients)
        assert len(clusters) == 2
        assert len(clusters[0]) == 20
        assert len(clusters[1]) == 20


# ---------------------------------------------------------------------------
# Blocklist pre-validation
# ---------------------------------------------------------------------------

class TestBlocklistValidation:
    @pytest.mark.asyncio
    @patch("src.engine.batch.get_blocklist", new_callable=AsyncMock, return_value=["blocked@example.com"])
    @patch("src.engine.batch.async_session")
    async def test_rejects_entire_batch_if_any_blocked(self, mock_session, mock_blocklist):
        recipients = [f"user{i}@example.com" for i in range(25)] + ["blocked@example.com"]
        with pytest.raises(ValueError, match="Blocked recipients"):
            await create_batch_job(
                to_list=recipients,
                subject="Test",
                body="Hello",
            )

    @pytest.mark.asyncio
    @patch("src.engine.batch.get_blocklist", new_callable=AsyncMock, return_value=[])
    @patch("src.engine.batch.scheduler")
    @patch("src.engine.batch.log_action", new_callable=AsyncMock)
    @patch("src.engine.batch.process_next_cluster", new_callable=AsyncMock)
    @patch("src.engine.batch.async_session")
    async def test_accepts_batch_when_no_blocked(
        self, mock_session_maker, mock_process, mock_log, mock_scheduler, mock_blocklist
    ):
        """Batch creation succeeds when no recipients are blocked."""
        # Set up session mock chain
        mock_session = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.total_recipients = 25
        mock_job.total_clusters = 2

        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()
        mock_session.add = MagicMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        recipients = [f"user{i}@example.com" for i in range(25)]
        result = await create_batch_job(
            to_list=recipients,
            subject="Test",
            body="Hello",
        )
        assert result.total_recipients == 25
        assert result.total_clusters == 2
        mock_process.assert_called_once()


# ---------------------------------------------------------------------------
# process_next_cluster
# ---------------------------------------------------------------------------

class TestProcessNextCluster:
    @pytest.mark.asyncio
    @patch("src.engine.batch.publish_event", new_callable=AsyncMock)
    @patch("src.engine.batch.increment_rate", new_callable=AsyncMock)
    @patch("src.engine.batch.async_session")
    async def test_sends_20_emails_and_increments_rate(self, mock_session_maker, mock_rate, mock_publish):
        """process_next_cluster sends each recipient individually and calls increment_rate."""
        recipients = [f"user{i}@example.com" for i in range(20)]

        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = "in_progress"
        mock_job.subject = "Test"
        mock_job.body = "Hello"
        mock_job.cc = None
        mock_job.bcc = None
        mock_job.actor = "user"
        mock_job.clusters_sent = 0
        mock_job.clusters_failed = 0
        mock_job.error_log = None

        mock_item = MagicMock()
        mock_item.id = 10
        mock_item.recipients = recipients
        mock_item.cluster_index = 0
        mock_item.status = "pending"

        mock_session = AsyncMock()
        # First call: get job; second: query item; third: get item for update; fourth: get job for update
        call_count = [0]

        async def mock_get(model, id_val):
            call_count[0] += 1
            if model is type(mock_job) or call_count[0] in (1, 4, 5):
                return mock_job
            return mock_item

        mock_session.get = AsyncMock(side_effect=[mock_job, mock_item, mock_job])
        mock_session.commit = AsyncMock()

        # Mock the execute for finding pending items and checking remaining
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_result2 = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []  # no pending items left
        mock_result2.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_result2])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        mock_send = AsyncMock(return_value={"id": "gmail_123"})
        with patch("src.engine.batch.send_new", mock_send):
            from src.engine.batch import process_next_cluster as pnc
            # Need to reimport to get patched version
            await process_next_cluster(1)

        assert mock_send.call_count == 20
        assert mock_rate.call_count == 20
        mock_publish.assert_called_once()


# ---------------------------------------------------------------------------
# Scheduler scheduling (next cluster 1 hour later)
# ---------------------------------------------------------------------------

class TestScheduling:
    @pytest.mark.asyncio
    @patch("src.engine.batch.get_blocklist", new_callable=AsyncMock, return_value=[])
    @patch("src.engine.batch.process_next_cluster", new_callable=AsyncMock)
    @patch("src.engine.batch.log_action", new_callable=AsyncMock)
    @patch("src.engine.batch.scheduler")
    @patch("src.engine.batch.async_session")
    async def test_schedules_remaining_clusters_1_hour_apart(
        self, mock_session_maker, mock_scheduler, mock_log, mock_process, mock_blocklist
    ):
        mock_session = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = 5
        mock_job.total_recipients = 50
        mock_job.total_clusters = 3

        # Simulate flush() assigning an ID to the added job
        added_objects = []
        def capture_add(obj):
            added_objects.append(obj)
        mock_session.add = MagicMock(side_effect=capture_add)

        async def mock_flush():
            # Simulate DB assigning ID on flush
            for obj in added_objects:
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = 5
        mock_session.flush = AsyncMock(side_effect=mock_flush)

        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        recipients = [f"user{i}@example.com" for i in range(50)]
        await create_batch_job(to_list=recipients, subject="Test", body="Hello")

        # Should have scheduled cluster 1 and cluster 2 (cluster 0 sent immediately)
        add_job_calls = mock_scheduler.add_job.call_args_list
        assert len(add_job_calls) == 2
        # Check job IDs contain the correct cluster indices
        assert "_cluster_1" in add_job_calls[0].kwargs["id"]
        assert "_cluster_2" in add_job_calls[1].kwargs["id"]


# ---------------------------------------------------------------------------
# API integration: >20 returns batch, <=20 sends immediately
# ---------------------------------------------------------------------------

class TestComposeRouteIntegration:
    @pytest.mark.asyncio
    @patch("src.api.routes.compose.is_blocked", new_callable=AsyncMock, return_value=False)
    async def test_compose_over_20_returns_batch(self, mock_is_blocked, client, auth_headers):
        """POST /api/compose with >20 recipients should return batch response."""
        recipients = [f"user{i}@example.com" for i in range(25)]
        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.total_recipients = 25
        mock_job.total_clusters = 2

        with patch("src.api.routes.compose.create_batch_job", new_callable=AsyncMock, return_value=mock_job) as mock_create:
            # Need to patch the import inside the route
            resp = await client.post(
                "/api/compose",
                json={"to": recipients, "subject": "Batch Test", "body": "Hello all"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Batch queued"
        assert data["batch_id"] == 1
        assert data["total_recipients"] == 25
        assert data["total_clusters"] == 2

    @pytest.mark.asyncio
    async def test_compose_under_20_sends_immediately(self, client, auth_headers):
        """POST /api/compose with <=20 recipients should send immediately (no batch)."""
        mock_check = AsyncMock(return_value={"allowed": True, "reasons": [], "warnings": []})
        mock_send = AsyncMock(return_value={"id": "gmail_abc"})
        mock_rate = AsyncMock()

        with patch("src.api.routes.compose.check_send_allowed", mock_check), \
             patch("src.gmail.send.send_new", mock_send), \
             patch("src.api.routes.compose.increment_rate", mock_rate):
            resp = await client.post(
                "/api/compose",
                json={"to": ["test@example.com"], "subject": "Single", "body": "Hi"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "Email sent"
        assert "batch_id" not in data


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class TestCancelBatch:
    @pytest.mark.asyncio
    @patch("src.engine.batch.log_action", new_callable=AsyncMock)
    @patch("src.engine.batch.scheduler")
    @patch("src.engine.batch.async_session")
    async def test_cancel_sets_status_and_removes_jobs(self, mock_session_maker, mock_scheduler, mock_log):
        mock_job = MagicMock()
        mock_job.id = 3
        mock_job.status = "in_progress"
        mock_job.total_clusters = 3

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_job)
        mock_session.commit = AsyncMock()
        mock_session.refresh = AsyncMock()

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        result = await cancel_batch(3)
        assert mock_job.status == "cancelled"
        assert mock_job.next_send_at is None
        # Should have tried to remove scheduler jobs for all clusters
        assert mock_scheduler.remove_job.call_count == 3


# ---------------------------------------------------------------------------
# Resume after restart
# ---------------------------------------------------------------------------

class TestResumePendingBatches:
    @pytest.mark.asyncio
    @patch("src.engine.batch.scheduler")
    @patch("src.engine.batch.async_session")
    async def test_reschedules_in_progress_jobs(self, mock_session_maker, mock_scheduler):
        mock_job1 = MagicMock()
        mock_job1.id = 1
        mock_job1.status = "in_progress"
        mock_job1.next_send_at = datetime.now(timezone.utc) + timedelta(hours=1)

        mock_job2 = MagicMock()
        mock_job2.id = 2
        mock_job2.status = "in_progress"
        mock_job2.next_send_at = None  # No scheduled time — should schedule soon

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_job1, mock_job2]
        mock_result.scalars.return_value = mock_scalars

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        count = await resume_pending_batches()
        assert count == 2
        assert mock_scheduler.add_job.call_count == 2


# ---------------------------------------------------------------------------
# Partial failure handling
# ---------------------------------------------------------------------------

class TestPartialFailure:
    @pytest.mark.asyncio
    @patch("src.engine.batch.publish_event", new_callable=AsyncMock)
    @patch("src.engine.batch.increment_rate", new_callable=AsyncMock)
    @patch("src.engine.batch.async_session")
    async def test_partial_failure_marks_sent_with_errors(self, mock_session_maker, mock_rate, mock_publish):
        """If some recipients fail, the cluster is still marked 'sent' with error info."""
        recipients = ["good@example.com", "bad@example.com", "good2@example.com"]

        mock_job = MagicMock()
        mock_job.id = 1
        mock_job.status = "in_progress"
        mock_job.subject = "Test"
        mock_job.body = "Hello"
        mock_job.cc = None
        mock_job.bcc = None
        mock_job.actor = "user"
        mock_job.clusters_sent = 0
        mock_job.clusters_failed = 0
        mock_job.error_log = None

        mock_item = MagicMock()
        mock_item.id = 10
        mock_item.recipients = recipients
        mock_item.cluster_index = 0
        mock_item.status = "pending"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(side_effect=[mock_job, mock_item, mock_job])
        mock_session.commit = AsyncMock()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_item
        mock_result2 = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result2.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_result2])

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_maker.return_value = mock_ctx

        # send_new succeeds for good@, fails for bad@, succeeds for good2@
        async def mock_send_new(to, subject, body, cc=None, bcc=None, actor="user"):
            if to == "bad@example.com":
                raise Exception("Gmail API error")
            return {"id": f"gmail_{to}"}

        with patch("src.engine.batch.send_new", side_effect=mock_send_new):
            await process_next_cluster(1)

        # Item should be marked sent (not failed) since some succeeded
        assert mock_item.status == "sent"
        assert mock_item.error is not None
        assert "bad@example.com" in mock_item.error
        # 2 successful sends + 2 rate increments
        assert mock_rate.call_count == 2
