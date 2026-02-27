"""Tests for src/security/safeguards.py — blocklist, rate limiter, sensitive topics, pre-send check."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.security.safeguards import (
    check_rate_limit,
    check_send_allowed,
    check_sensitive_topics,
    get_blocklist,
    get_never_auto_reply,
    increment_rate,
    is_blocked,
)


# ---------------------------------------------------------------------------
# check_sensitive_topics (synchronous — no mocking needed)
# ---------------------------------------------------------------------------

class TestCheckSensitiveTopics:
    def test_empty_string_returns_empty(self) -> None:
        assert check_sensitive_topics("") == []

    def test_clean_body_returns_empty(self) -> None:
        # Deliberately avoids substrings that contain sensitive keywords (e.g. "nda" inside "Monday")
        result = check_sensitive_topics("Hi, thanks for getting back to me. Talk soon.")
        assert result == []

    def test_detects_legal_keyword(self) -> None:
        result = check_sensitive_topics("We may need to consult a lawyer about this matter.")
        assert "lawyer" in result

    def test_detects_lawsuit(self) -> None:
        result = check_sensitive_topics("This could turn into a lawsuit if not handled carefully.")
        assert "lawsuit" in result

    def test_detects_irs(self) -> None:
        result = check_sensitive_topics("The IRS sent a notice about the missing return.")
        assert "irs" in result

    def test_detects_hipaa(self) -> None:
        result = check_sensitive_topics("This information is subject to HIPAA regulations.")
        assert "hipaa" in result

    def test_detects_nda(self) -> None:
        result = check_sensitive_topics("Please sign the NDA before we proceed.")
        assert "nda" in result

    def test_detects_termination(self) -> None:
        result = check_sensitive_topics("We need to discuss the termination of the contract.")
        assert "termination" in result

    def test_detects_harassment(self) -> None:
        result = check_sensitive_topics("The harassment complaint has been filed with HR.")
        assert "harassment" in result

    def test_detects_multiple_topics(self) -> None:
        result = check_sensitive_topics("The lawyer filed a lawsuit in court today.")
        for keyword in ("lawyer", "lawsuit", "court"):
            assert keyword in result

    def test_case_insensitive(self) -> None:
        result = check_sensitive_topics("Please consult your ATTORNEY before signing.")
        assert "attorney" in result

    def test_returns_only_matched_keywords(self) -> None:
        # Only "audit" is present
        result = check_sensitive_topics("The audit report was submitted last week.")
        assert "audit" in result
        assert "medical" not in result


# ---------------------------------------------------------------------------
# is_blocked / get_blocklist — mocked DB
# ---------------------------------------------------------------------------

class TestBlocklist:
    @pytest.mark.asyncio
    async def test_is_blocked_returns_true_for_blocked_address(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=["bad@evil.com"])):
            result = await is_blocked("bad@evil.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_is_blocked_returns_false_for_clean_address(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=["bad@evil.com"])):
            result = await is_blocked("good@example.com")
        assert result is False

    @pytest.mark.asyncio
    async def test_is_blocked_case_insensitive(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=["BAD@EVIL.COM"])):
            result = await is_blocked("bad@evil.com")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_blocklist_returns_list(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=["a@b.com", "c@d.com"])):
            result = await get_blocklist()
        assert result == ["a@b.com", "c@d.com"]

    @pytest.mark.asyncio
    async def test_get_blocklist_returns_empty_when_unset(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=[])):
            result = await get_blocklist()
        assert result == []


# ---------------------------------------------------------------------------
# get_never_auto_reply — mocked DB
# ---------------------------------------------------------------------------

class TestNeverAutoReply:
    @pytest.mark.asyncio
    async def test_get_never_auto_reply_returns_list(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=["noreply@example.com"])):
            result = await get_never_auto_reply()
        assert result == ["noreply@example.com"]

    @pytest.mark.asyncio
    async def test_get_never_auto_reply_returns_empty_when_unset(self) -> None:
        with patch("src.security.safeguards._get_setting", AsyncMock(return_value=[])):
            result = await get_never_auto_reply()
        assert result == []


# ---------------------------------------------------------------------------
# check_rate_limit / increment_rate — mocked Redis
# ---------------------------------------------------------------------------

class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed_when_under_limit(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"5")
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="system", limit=20)

        assert result["allowed"] is True
        assert result["count"] == 5
        assert result["limit"] == 20

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked_when_at_limit(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"20")
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="system", limit=20)

        assert result["allowed"] is False
        assert result["count"] == 20

    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked_when_over_limit(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"25")
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="system", limit=20)

        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed_when_key_missing(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            result = await check_rate_limit(actor="system", limit=20)

        assert result["allowed"] is True
        assert result["count"] == 0

    @pytest.mark.asyncio
    async def test_increment_rate_returns_new_count(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=3)
        mock_redis.expire = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            count = await increment_rate(actor="system")

        assert count == 3

    @pytest.mark.asyncio
    async def test_increment_rate_sets_expiry_on_first_increment(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            await increment_rate(actor="system")

        mock_redis.expire.assert_called_once()
        # Expiry should be set to 3600 seconds
        call_args = mock_redis.expire.call_args
        assert call_args[0][1] == 3600

    @pytest.mark.asyncio
    async def test_increment_rate_does_not_set_expiry_on_subsequent_increments(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)
        mock_redis.expire = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("src.security.safeguards.aioredis.from_url", return_value=mock_redis):
            await increment_rate(actor="system")

        mock_redis.expire.assert_not_called()


# ---------------------------------------------------------------------------
# check_send_allowed — master pre-send check
# ---------------------------------------------------------------------------

class TestCheckSendAllowed:
    @pytest.mark.asyncio
    async def test_allows_clean_send(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 1, "limit": 20})),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="Hi Alice, hope you are well.",
            )

        assert result["allowed"] is True
        assert result["reasons"] == []

    @pytest.mark.asyncio
    async def test_blocks_when_recipient_is_on_blocklist(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=True)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(
                to="bad@evil.com",
                body="Hello.",
            )

        assert result["allowed"] is False
        assert any("blocklist" in r for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_blocks_multiple_blocked_recipients(self) -> None:
        async def fake_is_blocked(addr: str) -> bool:
            return addr in ("bad1@evil.com", "bad2@evil.com")

        with (
            patch("src.security.safeguards.is_blocked", side_effect=fake_is_blocked),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(
                to=["bad1@evil.com", "bad2@evil.com"],
                body="Hello.",
            )

        assert result["allowed"] is False
        assert len(result["reasons"]) == 2

    @pytest.mark.asyncio
    async def test_blocks_when_rate_limit_exceeded(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": False, "count": 20, "limit": 20})),
            patch("src.security.safeguards.log_security_event", AsyncMock()),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="Hello.",
            )

        assert result["allowed"] is False
        assert any("limit" in r.lower() for r in result["reasons"])

    @pytest.mark.asyncio
    async def test_logs_security_event_on_rate_limit_exceeded(self) -> None:
        mock_log = AsyncMock()
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": False, "count": 20, "limit": 20})),
            patch("src.security.safeguards.log_security_event", mock_log),
        ):
            await check_send_allowed(to="alice@example.com", body="Hello.")

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["event_type"] == "rate_limit_exceeded"
        assert call_kwargs["severity"] == "high"

    @pytest.mark.asyncio
    async def test_warns_on_commitment_in_body(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="I guarantee this will be done by Friday.",
            )

        # Should still be allowed but with a warning
        assert result["allowed"] is True
        assert any("commitment" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_warns_on_sensitive_topics(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="I need to consult my lawyer about the lawsuit.",
            )

        assert result["allowed"] is True
        assert any("sensitive" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_warns_on_low_thread_security_score(self) -> None:
        mock_thread = MagicMock()
        mock_thread.security_score_avg = 30

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
            patch("src.security.safeguards.async_session", return_value=mock_session),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="Hello.",
                thread_id=42,
            )

        assert result["allowed"] is True
        assert any("security score" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_no_security_score_warning_when_score_is_acceptable(self) -> None:
        mock_thread = MagicMock()
        mock_thread.security_score_avg = 80

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
            patch("src.security.safeguards.async_session", return_value=mock_session),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="Hello.",
                thread_id=42,
            )

        assert result["allowed"] is True
        assert not any("security score" in w.lower() for w in result["warnings"])

    @pytest.mark.asyncio
    async def test_no_security_score_check_when_no_thread_id(self) -> None:
        # When thread_id is None, DB should not be queried
        mock_session = AsyncMock()

        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
            patch("src.security.safeguards.async_session", return_value=mock_session),
        ):
            result = await check_send_allowed(
                to="alice@example.com",
                body="Hello.",
                thread_id=None,
            )

        mock_session.__aenter__.assert_not_called()
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_accepts_list_of_recipients(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(
                to=["alice@example.com", "bob@example.com"],
                body="Hello.",
            )

        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_allows_one_clean_recipient_when_other_is_not_blocked(self) -> None:
        async def fake_is_blocked(addr: str) -> bool:
            return addr == "bad@evil.com"

        with (
            patch("src.security.safeguards.is_blocked", side_effect=fake_is_blocked),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(
                to=["good@example.com", "bad@evil.com"],
                body="Hello.",
            )

        # bad@evil.com triggers a block — whole send is blocked
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_returns_dict_with_expected_keys(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(to="alice@example.com", body="Hi.")

        assert "allowed" in result
        assert "reasons" in result
        assert "warnings" in result
        assert isinstance(result["allowed"], bool)
        assert isinstance(result["reasons"], list)
        assert isinstance(result["warnings"], list)

    @pytest.mark.asyncio
    async def test_empty_body_produces_no_commitment_or_topic_warnings(self) -> None:
        with (
            patch("src.security.safeguards.is_blocked", AsyncMock(return_value=False)),
            patch("src.security.safeguards.check_rate_limit", AsyncMock(return_value={"allowed": True, "count": 0, "limit": 20})),
        ):
            result = await check_send_allowed(to="alice@example.com", body="")

        assert result["allowed"] is True
        assert result["warnings"] == []
