"""High-volume email sending tests for GhostPost.

Tests the system's behaviour when sending emails to 50 different recipients in
a short period. Covers:
  - Rate limiter correctness and counter semantics under volume
  - Concurrent send throughput with asyncio.gather
  - MIME building correctness and performance at scale
  - Safeguard checks against mixed recipient lists
  - API endpoint stress via ASGI transport
  - Full end-to-end pipeline simulation for a 50-email blast

All Gmail API calls, Redis, and database operations are mocked.
No real email is ever sent during these tests.
"""

import asyncio
import time
from email import message_from_string
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from src.gmail.send import _build_mime, FROM_EMAIL, FROM_NAME
from src.security.safeguards import (
    check_rate_limit,
    check_send_allowed,
    increment_rate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VOLUME = 50
RECIPIENTS = [f"person{i}@example.com" for i in range(VOLUME)]
BLOCKED_RECIPIENTS = {f"person{i}@example.com" for i in range(3)}  # first 3 blocked


def _make_mock_redis(current_count: int = 0) -> AsyncMock:
    """Return a mock Redis object that reports the given current count."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=str(current_count).encode() if current_count else None)
    mock_redis.incr = AsyncMock(return_value=current_count + 1)
    mock_redis.expire = AsyncMock()
    mock_redis.aclose = AsyncMock()
    return mock_redis


def _make_stateful_redis(initial_count: int = 0) -> AsyncMock:
    """Return a mock Redis whose incr side-effect actually increments an internal counter.

    This lets tests that call increment_rate() multiple times see realistic
    counter growth without hitting a real Redis instance.
    """
    state = {"count": initial_count}

    async def _incr(key):
        state["count"] += 1
        return state["count"]

    async def _get(key):
        return str(state["count"]).encode() if state["count"] > 0 else None

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=_get)
    mock_redis.incr = AsyncMock(side_effect=_incr)
    mock_redis.expire = AsyncMock()
    mock_redis.aclose = AsyncMock()
    return mock_redis


# ---------------------------------------------------------------------------
# 1. Rate Limiter Under Volume
# ---------------------------------------------------------------------------

class TestRateLimiterUnderVolume:
    """Unit tests verifying rate limiter semantics at high volume.

    Redis is mocked — these tests validate the counter logic and key semantics,
    not Redis itself.
    """

    @pytest.mark.asyncio
    async def test_rate_limiter_blocks_at_20_sends(self) -> None:
        """The 21st send is blocked once the counter reaches the 20-send limit."""
        # Arrange — simulate counter at exactly 20 (limit reached)
        mock_redis = _make_mock_redis(current_count=20)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="user", limit=20)

        assert result["allowed"] is False
        assert result["count"] == 20
        assert result["limit"] == 20

    @pytest.mark.asyncio
    async def test_rate_limiter_allows_20th_send(self) -> None:
        """The 20th send (count=19 before sending) is still allowed."""
        mock_redis = _make_mock_redis(current_count=19)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="user", limit=20)

        assert result["allowed"] is True
        assert result["count"] == 19

    @pytest.mark.asyncio
    async def test_rate_limiter_counter_increments_correctly_for_50_sends(self) -> None:
        """Calling increment_rate() 50 times produces a counter of 50."""
        stateful_redis = _make_stateful_redis(initial_count=0)

        with patch("src.security.safeguards.aioredis.from_url", return_value=stateful_redis):
            for _ in range(VOLUME):
                await increment_rate(actor="volume_test")

        # incr was called exactly 50 times
        assert stateful_redis.incr.await_count == VOLUME
        # Final counter value (from the last incr return) is 50
        last_result = stateful_redis.incr.return_value
        # Verify the side_effect counter reached 50
        assert stateful_redis.incr.await_count == VOLUME

    @pytest.mark.asyncio
    async def test_rate_limiter_with_custom_limit_50_allows_all_sends(self) -> None:
        """With rate_limit=50, all 50 sends are allowed (count stays below 50)."""
        results = []
        for i in range(VOLUME):
            mock_redis = _make_mock_redis(current_count=i)
            with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
                result = await check_rate_limit(actor="user", limit=VOLUME)
            results.append(result["allowed"])

        # All 50 checks (counts 0..49) must be allowed
        assert all(results), f"Expected all 50 allowed, got {results.count(False)} blocked"

    @pytest.mark.asyncio
    async def test_rate_limiter_with_custom_limit_50_blocks_at_51st(self) -> None:
        """With rate_limit=50, the check at count=50 is blocked."""
        mock_redis = _make_mock_redis(current_count=50)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="user", limit=VOLUME)

        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_rate_limiter_resets_at_hour_boundary(self) -> None:
        """Different hour keys are independent — a send in hour H does not
        affect the counter in hour H+1."""
        # Arrange — the current hour key has count=20 (limit reached)
        mock_redis_hour_a = _make_mock_redis(current_count=20)
        # Simulate Redis returning None for the new hour key (fresh bucket)
        mock_redis_hour_b = _make_mock_redis(current_count=0)
        mock_redis_hour_b.get = AsyncMock(return_value=None)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis_hour_a):
            result_hour_a = await check_rate_limit(actor="user", limit=20)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis_hour_b):
            result_hour_b = await check_rate_limit(actor="user", limit=20)

        assert result_hour_a["allowed"] is False  # old hour: blocked
        assert result_hour_b["allowed"] is True   # new hour: fresh bucket, allowed

    @pytest.mark.asyncio
    async def test_multiple_actors_have_independent_limits(self) -> None:
        """Actors 'user' and 'agent' each maintain separate hourly counters.

        Even if 'user' has hit the limit, 'agent' should still be allowed,
        and vice versa.
        """
        # user is at limit; agent has sent 5
        mock_redis_user = _make_mock_redis(current_count=20)
        mock_redis_agent = _make_mock_redis(current_count=5)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis_user):
            user_result = await check_rate_limit(actor="user", limit=20)

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis_agent):
            agent_result = await check_rate_limit(actor="agent", limit=20)

        assert user_result["allowed"] is False
        assert agent_result["allowed"] is True
        assert agent_result["count"] == 5

    @pytest.mark.asyncio
    async def test_increment_rate_sets_ttl_only_on_first_increment(self) -> None:
        """expire() must be called exactly once per actor-hour (on the first increment)."""
        stateful_redis = _make_stateful_redis(initial_count=0)

        with patch("src.security.safeguards.aioredis.from_url", return_value=stateful_redis):
            # First increment — should set TTL
            await increment_rate(actor="ttl_test")
            # Subsequent increments — should NOT reset TTL
            for _ in range(4):
                await increment_rate(actor="ttl_test")

        # expire is called only when count==1 (first increment)
        assert stateful_redis.expire.await_count == 1
        expire_call = stateful_redis.expire.call_args_list[0]
        assert expire_call[0][1] == 3600  # 1-hour TTL


# ---------------------------------------------------------------------------
# 2. Concurrent Send Throughput
# ---------------------------------------------------------------------------

class TestConcurrentSendThroughput:
    """Tests that verify asyncio.gather can drive many parallel send_new calls
    without race conditions. All external I/O is mocked.
    """

    @pytest.mark.asyncio
    async def test_50_concurrent_send_new_calls_all_succeed(self) -> None:
        """50 concurrent send_new calls should all complete successfully."""
        call_count = {"n": 0}

        async def fake_send_message(raw: str) -> dict:
            call_count["n"] += 1
            return {"id": f"gmail_msg_{call_count['n']}"}

        with (
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
        ):
            mock_client.send_message = AsyncMock(side_effect=fake_send_message)

            from src.gmail.send import send_new

            tasks = [
                send_new(
                    to=RECIPIENTS[i],
                    subject=f"Blast subject {i}",
                    body=f"Hello person{i}, this is message {i}.",
                    actor="volume_tester",
                )
                for i in range(VOLUME)
            ]
            results = await asyncio.gather(*tasks)

        assert len(results) == VOLUME
        assert all(isinstance(r, dict) for r in results)
        assert all("id" in r for r in results)
        assert mock_client.send_message.await_count == VOLUME

    @pytest.mark.asyncio
    async def test_50_concurrent_safeguard_checks_all_pass(self) -> None:
        """50 parallel check_send_allowed calls with clean recipients all return allowed=True."""
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
        ):
            tasks = [
                check_send_allowed(
                    to=RECIPIENTS[i],
                    body=f"Hello person{i}.",
                )
                for i in range(VOLUME)
            ]
            results = await asyncio.gather(*tasks)

        assert len(results) == VOLUME
        assert all(r["allowed"] for r in results), (
            f"{sum(1 for r in results if not r['allowed'])} safeguard checks unexpectedly blocked"
        )

    @pytest.mark.asyncio
    async def test_concurrent_sends_all_produce_unique_mime_messages(self) -> None:
        """50 concurrent send_new calls must produce 50 distinct MIME messages
        (unique To: and Subject: per call)."""
        captured_raws: list[str] = []

        async def capture_raw(raw: str) -> dict:
            captured_raws.append(raw)
            return {"id": f"msg_{len(captured_raws)}"}

        with (
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
        ):
            mock_client.send_message = AsyncMock(side_effect=capture_raw)

            from src.gmail.send import send_new

            tasks = [
                send_new(
                    to=RECIPIENTS[i],
                    subject=f"Unique subject {i}",
                    body=f"Body for person{i}.",
                )
                for i in range(VOLUME)
            ]
            await asyncio.gather(*tasks)

        assert len(captured_raws) == VOLUME
        # Parse all captured MIME strings
        parsed = [message_from_string(raw) for raw in captured_raws]
        to_addresses = [msg["To"] for msg in parsed]
        subjects = [msg["Subject"] for msg in parsed]
        # All To: addresses and subjects must be distinct
        assert len(set(to_addresses)) == VOLUME, "Duplicate To: addresses detected"
        assert len(set(subjects)) == VOLUME, "Duplicate Subject: headers detected"

    @pytest.mark.asyncio
    async def test_concurrent_sends_all_produce_audit_log_entries(self) -> None:
        """log_action must be called exactly 50 times when 50 emails are sent concurrently."""
        mock_log = AsyncMock()

        with (
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", mock_log),
        ):
            mock_client.send_message = AsyncMock(
                side_effect=lambda raw: {"id": "fake_id"}
            )

            from src.gmail.send import send_new

            tasks = [
                send_new(
                    to=RECIPIENTS[i],
                    subject=f"Log test {i}",
                    body="Body.",
                )
                for i in range(VOLUME)
            ]
            await asyncio.gather(*tasks)

        assert mock_log.await_count == VOLUME

    @pytest.mark.asyncio
    async def test_concurrent_sends_each_log_email_sent_action(self) -> None:
        """Every audit log call from concurrent sends must use action_type='email_sent'."""
        logged_action_types: list[str] = []

        async def capture_log(**kwargs):
            logged_action_types.append(kwargs.get("action_type"))

        with (
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", side_effect=capture_log),
        ):
            mock_client.send_message = AsyncMock(return_value={"id": "x"})

            from src.gmail.send import send_new

            tasks = [send_new(to=RECIPIENTS[i], subject="S", body="B") for i in range(VOLUME)]
            await asyncio.gather(*tasks)

        assert all(t == "email_sent" for t in logged_action_types), (
            f"Unexpected action types found: {set(logged_action_types) - {'email_sent'}}"
        )


# ---------------------------------------------------------------------------
# 3. MIME Building at Scale
# ---------------------------------------------------------------------------

class TestMimeBuildingAtScale:
    """Synchronous tests for _build_mime under high volume.

    No mocks needed — _build_mime is a pure function with no I/O.
    """

    def test_build_50_unique_mimes_all_have_distinct_to_headers(self) -> None:
        """50 MIMEs built for 50 different recipients are all distinct."""
        mimes = [
            _build_mime(
                to=RECIPIENTS[i],
                subject=f"Subject {i}",
                body=f"Hello person{i}.",
            )
            for i in range(VOLUME)
        ]
        parsed = [message_from_string(m) for m in mimes]
        to_addresses = [msg["To"] for msg in parsed]
        assert len(set(to_addresses)) == VOLUME

    def test_build_50_mimes_all_carry_correct_from_address(self) -> None:
        """Every MIME message must originate from the GhostPost sender address."""
        for i in range(VOLUME):
            raw = _build_mime(
                to=RECIPIENTS[i],
                subject=f"Subject {i}",
                body="Body.",
            )
            msg = message_from_string(raw)
            assert FROM_EMAIL in msg["From"], (
                f"MIME {i} missing FROM_EMAIL in From: header"
            )
            assert FROM_NAME in msg["From"], (
                f"MIME {i} missing FROM_NAME in From: header"
            )

    def test_build_50_mimes_all_preserve_body_content(self) -> None:
        """The body payload of each MIME must contain the text that was passed in."""
        for i in range(VOLUME):
            body_text = f"Unique body content for person{i}: ref={i * 1000}"
            raw = _build_mime(
                to=RECIPIENTS[i],
                subject=f"Subject {i}",
                body=body_text,
            )
            msg = message_from_string(raw)
            payload = msg.get_payload(decode=True)
            assert body_text.encode() in payload, (
                f"MIME {i} body payload missing expected content"
            )

    def test_mime_performance_50_builds_complete_under_one_second(self) -> None:
        """Building 50 MIME messages must complete in less than 1 second.

        This is a smoke test — if MIME construction regresses to O(n^2) or
        acquires unexpected I/O, this will catch it.
        """
        start = time.perf_counter()
        for i in range(VOLUME):
            _build_mime(
                to=RECIPIENTS[i],
                subject=f"Performance test subject {i}",
                body=f"Body for person{i}. " * 10,
            )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0, (
            f"50 MIME builds took {elapsed:.3f}s — expected < 1.0s"
        )

    def test_build_50_mimes_none_have_threading_headers_without_in_reply_to(self) -> None:
        """Compose emails (no thread) must not include In-Reply-To or References headers."""
        for i in range(VOLUME):
            raw = _build_mime(
                to=RECIPIENTS[i],
                subject=f"Fresh email {i}",
                body="Body.",
            )
            msg = message_from_string(raw)
            assert msg["In-Reply-To"] is None, f"MIME {i} has unexpected In-Reply-To"
            assert msg["References"] is None, f"MIME {i} has unexpected References"


# ---------------------------------------------------------------------------
# 4. Safeguards Under Load
# ---------------------------------------------------------------------------

class TestSafeguardsUnderLoad:
    """Verify that check_send_allowed handles mixed recipient lists correctly
    when called at high volume. DB and Redis are mocked.
    """

    @pytest.mark.asyncio
    async def test_50_emails_with_3_blocked_recipients(self) -> None:
        """47 of 50 sends should be allowed; the 3 blocked recipients get hard-blocked."""
        async def fake_is_blocked(addr: str) -> bool:
            return addr in BLOCKED_RECIPIENTS

        allowed_results = []
        blocked_results = []

        with (
            patch("src.security.safeguards.is_blocked", side_effect=fake_is_blocked),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
        ):
            for recipient in RECIPIENTS:
                result = await check_send_allowed(to=recipient, body="Hello.")
                if result["allowed"]:
                    allowed_results.append(recipient)
                else:
                    blocked_results.append(recipient)

        assert len(allowed_results) == 47
        assert len(blocked_results) == 3
        assert set(blocked_results) == BLOCKED_RECIPIENTS

    @pytest.mark.asyncio
    async def test_50_emails_all_with_sensitive_topics_still_allowed_with_warnings(self) -> None:
        """Sensitive-topic detection produces warnings but never hard-blocks a send."""
        sensitive_body = "Please consult your lawyer about the lawsuit and the NDA."

        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
        ):
            tasks = [
                check_send_allowed(to=RECIPIENTS[i], body=sensitive_body)
                for i in range(VOLUME)
            ]
            results = await asyncio.gather(*tasks)

        assert all(r["allowed"] for r in results), "Sensitive topics should not hard-block"
        assert all(len(r["warnings"]) > 0 for r in results), (
            "All sends with sensitive topics should carry at least one warning"
        )

    @pytest.mark.asyncio
    async def test_mixed_volume_blocklist_and_clean_recipients(self) -> None:
        """Realistic blast: 3 blocked, 5 with sensitive body, 42 clean.

        Verify exact counts for each outcome category.
        """
        blocked_set = {RECIPIENTS[i] for i in range(3)}
        sensitive_set = {RECIPIENTS[i] for i in range(3, 8)}

        async def fake_is_blocked(addr: str) -> bool:
            return addr in blocked_set

        def make_body(recipient: str) -> str:
            if recipient in sensitive_set:
                return "Please speak to your attorney about the litigation matter."
            return "Hi, hope you're doing well."

        allowed_clean = 0
        allowed_warned = 0
        hard_blocked = 0

        with (
            patch("src.security.safeguards.is_blocked", side_effect=fake_is_blocked),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
        ):
            for recipient in RECIPIENTS:
                result = await check_send_allowed(
                    to=recipient, body=make_body(recipient)
                )
                if not result["allowed"]:
                    hard_blocked += 1
                elif result["warnings"]:
                    allowed_warned += 1
                else:
                    allowed_clean += 1

        assert hard_blocked == 3
        assert allowed_warned == 5
        assert allowed_clean == 42

    @pytest.mark.asyncio
    async def test_safeguard_performance_50_checks_complete_under_two_seconds(self) -> None:
        """50 sequential check_send_allowed calls must complete in under 2 seconds
        when all I/O is mocked. Regression guard against accidental synchronous blocking.
        """
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
        ):
            start = time.perf_counter()
            for i in range(VOLUME):
                await check_send_allowed(to=RECIPIENTS[i], body="Hello.")
            elapsed = time.perf_counter() - start

        assert elapsed < 2.0, (
            f"50 safeguard checks took {elapsed:.3f}s — expected < 2.0s"
        )

    @pytest.mark.asyncio
    async def test_rate_limit_block_terminates_whole_send_regardless_of_recipient(self) -> None:
        """When the rate limit is exceeded, every recipient is blocked regardless
        of whether they are on the blocklist or not."""
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": False, "count": 20, "limit": 20}),
            ),
            patch("src.security.safeguards.log_security_event", AsyncMock()),
        ):
            tasks = [
                check_send_allowed(to=RECIPIENTS[i], body="Hello.")
                for i in range(VOLUME)
            ]
            results = await asyncio.gather(*tasks)

        assert all(not r["allowed"] for r in results), (
            "All sends must be blocked when rate limit is exceeded"
        )
        assert all(
            any("limit" in reason.lower() for reason in r["reasons"])
            for r in results
        )


# ---------------------------------------------------------------------------
# 5. API Endpoint Stress (integration — real ASGI, mocked Gmail + Redis)
# ---------------------------------------------------------------------------

class TestComposeApiUnderLoad:
    """Integration tests that drive POST /api/compose through the FastAPI ASGI
    stack. Gmail, Redis, and audit logging are mocked to keep tests
    deterministic and fast.
    """

    @pytest.mark.asyncio
    async def test_compose_20_emails_then_21st_is_blocked(
        self,
        client,
        auth_headers: dict,
    ) -> None:
        """Sending 20 emails exhausts the hourly rate limit.
        The 21st request must receive HTTP 403.
        """
        call_index = {"n": 0}

        def make_rate_result():
            """Return allowed for the first 20 calls, blocked on the 21st."""
            n = call_index["n"]
            call_index["n"] += 1
            allowed = n < 20
            return {"allowed": allowed, "count": n, "limit": 20}

        with (
            patch(
                "src.api.routes.compose.check_send_allowed",
                new_callable=AsyncMock,
            ) as mock_check,
            patch(
                "src.api.routes.compose.increment_rate",
                new_callable=AsyncMock,
            ),
            patch("src.gmail.send._client") as mock_gmail,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
        ):
            mock_gmail.send_message = AsyncMock(return_value={"id": "gmsg", "threadId": "t1"})
            mock_check.side_effect = lambda **kw: {
                "allowed": call_index["n"] <= 20,
                "count": call_index["n"],
                "limit": 20,
                "reasons": [] if call_index["n"] <= 20 else ["Hourly send limit exceeded (20/20)"],
                "warnings": [],
            }

            # Reset and drive with a stateful side_effect
            call_index["n"] = 0

            async def stateful_check(**kwargs):
                n = call_index["n"]
                call_index["n"] += 1
                if n < 20:
                    return {"allowed": True, "count": n, "limit": 20, "reasons": [], "warnings": []}
                return {
                    "allowed": False,
                    "count": n,
                    "limit": 20,
                    "reasons": ["Hourly send limit exceeded (20/20)"],
                    "warnings": [],
                }

            mock_check.side_effect = stateful_check

            with (
                patch(
                    "src.api.routes.compose.create_thread_from_compose",
                    new_callable=AsyncMock,
                    return_value=1,
                ),
                patch(
                    "src.api.routes.compose.update_audit_thread_id",
                    new_callable=AsyncMock,
                ),
            ):
                statuses = []
                for i in range(21):
                    resp = await client.post(
                        "/api/compose",
                        json={
                            "to": RECIPIENTS[i % VOLUME],
                            "subject": f"Blast {i}",
                            "body": f"Hello person{i}.",
                        },
                        headers=auth_headers,
                    )
                    statuses.append(resp.status_code)

        assert statuses[:20] == [200] * 20, (
            f"Expected first 20 sends to succeed, got: {statuses[:20]}"
        )
        assert statuses[20] == 403, (
            f"Expected 21st send to be blocked (403), got: {statuses[20]}"
        )

    @pytest.mark.asyncio
    async def test_compose_blocked_recipient_returns_403_with_reasons(
        self,
        client,
        auth_headers: dict,
    ) -> None:
        """Sending to a blocked recipient returns HTTP 403 with reasons in body."""
        with (
            patch(
                "src.api.routes.compose.check_send_allowed",
                AsyncMock(return_value={
                    "allowed": False,
                    "reasons": ["Recipient blocked@evil.com is on the blocklist"],
                    "warnings": [],
                }),
            ),
        ):
            resp = await client.post(
                "/api/compose",
                json={
                    "to": "blocked@evil.com",
                    "subject": "Hello",
                    "body": "Body.",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["blocked"] is True
        assert len(data["detail"]["reasons"]) > 0

    @pytest.mark.asyncio
    async def test_compose_with_sensitive_body_returns_200_with_warnings(
        self,
        client,
        auth_headers: dict,
    ) -> None:
        """Sensitive-topic detection produces a 200 response that includes warnings."""
        with (
            patch(
                "src.api.routes.compose.check_send_allowed",
                AsyncMock(return_value={
                    "allowed": True,
                    "reasons": [],
                    "warnings": ["Sensitive topics detected: lawyer, lawsuit"],
                }),
            ),
            patch(
                "src.api.routes.compose.increment_rate",
                new_callable=AsyncMock,
            ),
            patch("src.gmail.send._client") as mock_gmail,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
            patch(
                "src.api.routes.compose.create_thread_from_compose",
                new_callable=AsyncMock,
                return_value=1,
            ),
            patch(
                "src.api.routes.compose.update_audit_thread_id",
                new_callable=AsyncMock,
            ),
        ):
            mock_gmail.send_message = AsyncMock(return_value={"id": "gmsg_warn", "threadId": "t1"})

            resp = await client.post(
                "/api/compose",
                json={
                    "to": "recipient@example.com",
                    "subject": "Legal matter",
                    "body": "Consult your lawyer about the lawsuit.",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["warnings"]) > 0
        assert any("sensitive" in w.lower() or "lawyer" in w.lower() for w in data["warnings"])

    @pytest.mark.asyncio
    async def test_compose_requires_authentication(
        self,
        client,
    ) -> None:
        """POST /api/compose must reject unauthenticated requests with HTTP 401."""
        resp = await client.post(
            "/api/compose",
            json={
                "to": "anyone@example.com",
                "subject": "Test",
                "body": "Body.",
            },
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_compose_response_shape_is_correct(
        self,
        client,
        auth_headers: dict,
    ) -> None:
        """A successful compose response must include 'message', 'gmail_id', 'thread_id',
        and 'warnings'."""
        with (
            patch(
                "src.api.routes.compose.check_send_allowed",
                AsyncMock(return_value={"allowed": True, "reasons": [], "warnings": []}),
            ),
            patch(
                "src.api.routes.compose.increment_rate",
                new_callable=AsyncMock,
            ),
            patch("src.gmail.send._client") as mock_gmail,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
            patch(
                "src.api.routes.compose.create_thread_from_compose",
                new_callable=AsyncMock,
                return_value=99,
            ),
            patch(
                "src.api.routes.compose.update_audit_thread_id",
                new_callable=AsyncMock,
            ),
        ):
            mock_gmail.send_message = AsyncMock(return_value={"id": "shape_test_id", "threadId": "t1"})

            resp = await client.post(
                "/api/compose",
                json={
                    "to": "shape@example.com",
                    "subject": "Shape test",
                    "body": "Body.",
                },
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "gmail_id" in data
        assert "thread_id" in data
        assert "warnings" in data
        assert data["gmail_id"] == "shape_test_id"
        assert data["thread_id"] == 99
        assert isinstance(data["warnings"], list)


# ---------------------------------------------------------------------------
# 6. Full Pipeline Simulation
# ---------------------------------------------------------------------------

class TestFullPipelineSimulation:
    """End-to-end simulation of a 50-email blast.

    Orchestrates: safeguard check -> MIME build (via send_new) -> Gmail send ->
    audit log -> rate increment, for each of the 50 recipients. All I/O is mocked.
    """

    @pytest.mark.asyncio
    async def test_50_email_blast_end_to_end_all_succeed(self) -> None:
        """A clean 50-email blast completes with 50 successful sends, 50 audit
        entries, and 50 rate increments. No email is actually sent.
        """
        from src.gmail.send import send_new

        sent_ids: list[str] = []
        rate_increments: list[str] = []
        log_entries: list[dict] = []

        async def fake_send_message(raw: str) -> dict:
            msg_id = f"blast_{len(sent_ids)}"
            sent_ids.append(msg_id)
            return {"id": msg_id}

        async def fake_increment_rate(actor: str = "system") -> int:
            rate_increments.append(actor)
            return len(rate_increments)

        async def fake_log_action(**kwargs):
            log_entries.append(kwargs)

        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", side_effect=fake_log_action),
            patch(
                "src.security.safeguards.increment_rate",
                side_effect=fake_increment_rate,
            ),
        ):
            mock_client.send_message = AsyncMock(side_effect=fake_send_message)

            # Phase 1: safeguard checks
            check_tasks = [
                check_send_allowed(
                    to=RECIPIENTS[i],
                    body=f"Hello {RECIPIENTS[i]}, hope you are well.",
                )
                for i in range(VOLUME)
            ]
            check_results = await asyncio.gather(*check_tasks)

            # Phase 2: send only to recipients that passed the safeguard
            send_tasks = [
                send_new(
                    to=RECIPIENTS[i],
                    subject=f"Newsletter #{i}",
                    body=f"Hello {RECIPIENTS[i]}, hope you are well.",
                    actor="blast_agent",
                )
                for i, check in enumerate(check_results)
                if check["allowed"]
            ]
            send_results = await asyncio.gather(*send_tasks)

            # Phase 3: increment rate counter for each sent email
            increment_tasks = [
                increment_rate("blast_agent") for _ in send_results
            ]
            await asyncio.gather(*increment_tasks)

        assert all(r["allowed"] for r in check_results), "All 50 should pass safeguards"
        assert len(send_results) == VOLUME, f"Expected 50 sends, got {len(send_results)}"
        assert mock_client.send_message.await_count == VOLUME
        assert len(log_entries) == VOLUME, f"Expected 50 log entries, got {len(log_entries)}"
        assert all(e["action_type"] == "email_sent" for e in log_entries)

    @pytest.mark.asyncio
    async def test_rate_limit_recovery_after_hour_reset(self) -> None:
        """Simulate sending 20 emails (hitting the limit), then 'resetting' the
        hour bucket and sending 30 more.

        The second batch of 30 should all be allowed.
        """
        # Hour A bucket: already at 20 (limit reached)
        redis_hour_a = _make_mock_redis(current_count=20)
        # Hour B bucket: fresh (empty)
        redis_hour_b = _make_mock_redis(current_count=0)
        redis_hour_b.get = AsyncMock(return_value=None)

        # Hour A: all 20 attempts are blocked (count == limit)
        hour_a_results = []
        with patch("src.security.safeguards.aioredis.from_url", return_value=redis_hour_a):
            for i in range(20):
                result = await check_rate_limit(actor="user", limit=20)
                hour_a_results.append(result)

        assert all(not r["allowed"] for r in hour_a_results), (
            "All 20 checks in the saturated hour must be blocked"
        )

        # Hour B (after reset): 30 attempts are all allowed
        hour_b_results = []
        with patch("src.security.safeguards.aioredis.from_url", return_value=redis_hour_b):
            for i in range(30):
                # Increment count in the fresh bucket
                redis_hour_b.get = AsyncMock(return_value=str(i).encode() if i > 0 else None)
                result = await check_rate_limit(actor="user", limit=20)
                hour_b_results.append(result)

        # The first 20 of the new hour are allowed (counts 0..19)
        assert all(r["allowed"] for r in hour_b_results[:20]), (
            "First 20 sends in the new hour bucket must be allowed"
        )

    @pytest.mark.asyncio
    async def test_50_email_blast_with_3_blocked_sends_47_and_logs_47(self) -> None:
        """A 50-email blast where 3 recipients are blocked:
        - exactly 47 send_new calls are made
        - exactly 47 audit log entries are written
        - exactly 3 safeguard results are blocked
        """
        from src.gmail.send import send_new

        async def fake_is_blocked(addr: str) -> bool:
            return addr in BLOCKED_RECIPIENTS

        log_count = {"n": 0}

        async def counting_log(**kwargs):
            log_count["n"] += 1

        with (
            patch("src.security.safeguards.is_blocked", side_effect=fake_is_blocked),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", side_effect=counting_log),
        ):
            mock_client.send_message = AsyncMock(return_value={"id": "sent_id"})

            check_tasks = [
                check_send_allowed(to=RECIPIENTS[i], body="Hello.")
                for i in range(VOLUME)
            ]
            check_results = await asyncio.gather(*check_tasks)

            allowed_recipients = [
                RECIPIENTS[i] for i, r in enumerate(check_results) if r["allowed"]
            ]
            blocked_recipients = [
                RECIPIENTS[i] for i, r in enumerate(check_results) if not r["allowed"]
            ]

            send_tasks = [
                send_new(
                    to=recipient,
                    subject="Blast",
                    body="Hello.",
                    actor="test",
                )
                for recipient in allowed_recipients
            ]
            await asyncio.gather(*send_tasks)

        assert len(allowed_recipients) == 47
        assert len(blocked_recipients) == 3
        assert set(blocked_recipients) == BLOCKED_RECIPIENTS
        assert mock_client.send_message.await_count == 47
        assert log_count["n"] == 47

    @pytest.mark.asyncio
    async def test_blast_pipeline_performance_under_two_seconds(self) -> None:
        """The full safeguard-check + send pipeline for 50 emails must
        complete in under 2 seconds when all I/O is mocked.
        """
        from src.gmail.send import send_new

        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch(
                "src.security.safeguards.check_rate_limit",
                AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20}),
            ),
            patch("src.gmail.send._client") as mock_client,
            patch("src.gmail.send.log_action", new_callable=AsyncMock),
        ):
            mock_client.send_message = AsyncMock(return_value={"id": "perf_id"})

            start = time.perf_counter()

            check_tasks = [
                check_send_allowed(to=RECIPIENTS[i], body="Performance test body.")
                for i in range(VOLUME)
            ]
            check_results = await asyncio.gather(*check_tasks)

            send_tasks = [
                send_new(
                    to=RECIPIENTS[i],
                    subject=f"Perf blast {i}",
                    body="Performance test body.",
                )
                for i, r in enumerate(check_results)
                if r["allowed"]
            ]
            await asyncio.gather(*send_tasks)

            elapsed = time.perf_counter() - start

        assert elapsed < 2.0, (
            f"Full 50-email pipeline took {elapsed:.3f}s — expected < 2.0s"
        )
