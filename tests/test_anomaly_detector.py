"""Tests for src/security/anomaly_detector.py — Layer 5 anomaly detection."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestCheckSendRate:
    @pytest.mark.asyncio
    async def test_returns_allowed_true_when_under_limit(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"5")
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            from src.security.anomaly_detector import check_send_rate
            result = await check_send_rate("user", limit=20)

        assert result["allowed"] is True
        assert result["count"] == 5
        assert result["limit"] == 20

    @pytest.mark.asyncio
    async def test_returns_allowed_false_when_at_limit(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"20")
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            from src.security.anomaly_detector import check_send_rate
            result = await check_send_rate("user", limit=20)

        assert result["allowed"] is False
        assert result["count"] == 20

    @pytest.mark.asyncio
    async def test_returns_count_zero_when_key_missing(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            from src.security.anomaly_detector import check_send_rate
            result = await check_send_rate("user", limit=20)

        assert result["count"] == 0
        assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_uses_correct_redis_key_format(self) -> None:
        from datetime import datetime, timezone
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            with patch("src.security.anomaly_detector.datetime") as mock_dt:
                fixed_now = datetime(2026, 2, 24, 15, 0, 0, tzinfo=timezone.utc)
                mock_dt.now.return_value = fixed_now
                from src.security.anomaly_detector import check_send_rate
                await check_send_rate("agent", limit=10)

        called_key = mock_redis.get.call_args[0][0]
        assert called_key == "ghostpost:rate:agent:2026022415"


class TestIncrementSendRate:
    @pytest.mark.asyncio
    async def test_increments_and_returns_new_count(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=3)
        mock_redis.expire = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            from src.security.anomaly_detector import increment_send_rate
            result = await increment_send_rate("user")

        assert result == 3

    @pytest.mark.asyncio
    async def test_sets_ttl_on_first_increment(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            from src.security.anomaly_detector import increment_send_rate
            await increment_send_rate("user")

        # expire should be set with 3600 seconds TTL when count is 1
        mock_redis.expire.assert_called_once()
        expire_args = mock_redis.expire.call_args[0]
        assert expire_args[1] == 3600

    @pytest.mark.asyncio
    async def test_does_not_set_ttl_on_subsequent_increments(self) -> None:
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=5)
        mock_redis.expire = AsyncMock()
        mock_redis.aclose = AsyncMock()

        with patch("src.security.anomaly_detector.aioredis.from_url", return_value=mock_redis):
            from src.security.anomaly_detector import increment_send_rate
            await increment_send_rate("user")

        # expire should not be called when count > 1
        mock_redis.expire.assert_not_called()


class TestCheckNewRecipient:
    @pytest.mark.asyncio
    async def test_returns_true_when_recipient_not_in_contacts(self) -> None:
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = 0
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.security.anomaly_detector.async_session", return_value=mock_session):
            from src.security.anomaly_detector import check_new_recipient
            result = await check_new_recipient("stranger@example.com")

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_recipient_exists_in_contacts(self) -> None:
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = 1
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.security.anomaly_detector.async_session", return_value=mock_session):
            from src.security.anomaly_detector import check_new_recipient
            result = await check_new_recipient("known@example.com")

        assert result is False

    @pytest.mark.asyncio
    async def test_handles_none_scalar_gracefully(self) -> None:
        mock_scalar_result = MagicMock()
        mock_scalar_result.scalar.return_value = None
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_scalar_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.security.anomaly_detector.async_session", return_value=mock_session):
            from src.security.anomaly_detector import check_new_recipient
            result = await check_new_recipient("someone@example.com")

        # None count defaults to 0, so recipient is considered new
        assert result is True


class TestCheckAnomalies:
    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_anomalies(self) -> None:
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": True, "count": 5, "limit": 20}):
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=False):
                from src.security.anomaly_detector import check_anomalies
                result = await check_anomalies("known@example.com", actor="user")

        assert result == []

    @pytest.mark.asyncio
    async def test_returns_rate_limit_anomaly_when_exceeded(self) -> None:
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": False, "count": 25, "limit": 20}):
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=False):
                with patch("src.security.anomaly_detector.log_security_event",
                           new_callable=AsyncMock):
                    from src.security.anomaly_detector import check_anomalies
                    result = await check_anomalies("known@example.com", actor="user")

        types = [a["type"] for a in result]
        assert "rate_limit_exceeded" in types
        rate_anomaly = next(a for a in result if a["type"] == "rate_limit_exceeded")
        assert rate_anomaly["severity"] == "high"

    @pytest.mark.asyncio
    async def test_logs_security_event_on_rate_limit(self) -> None:
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": False, "count": 21, "limit": 20}):
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=False):
                with patch("src.security.anomaly_detector.log_security_event",
                           new_callable=AsyncMock) as mock_log:
                    from src.security.anomaly_detector import check_anomalies
                    await check_anomalies("known@example.com", actor="agent")

        mock_log.assert_called_once()
        call_kwargs = mock_log.call_args.kwargs
        assert call_kwargs["event_type"] == "rate_limit_exceeded"
        assert call_kwargs["severity"] == "high"
        assert call_kwargs["details"]["actor"] == "agent"

    @pytest.mark.asyncio
    async def test_returns_new_recipient_anomaly_when_unknown(self) -> None:
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": True, "count": 1, "limit": 20}):
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=True):
                from src.security.anomaly_detector import check_anomalies
                result = await check_anomalies("newperson@example.com", actor="user")

        types = [a["type"] for a in result]
        assert "new_recipient" in types
        new_rec_anomaly = next(a for a in result if a["type"] == "new_recipient")
        assert new_rec_anomaly["severity"] == "medium"
        assert "newperson@example.com" in new_rec_anomaly["details"]

    @pytest.mark.asyncio
    async def test_returns_both_anomalies_when_both_triggered(self) -> None:
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": False, "count": 25, "limit": 20}):
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=True):
                with patch("src.security.anomaly_detector.log_security_event",
                           new_callable=AsyncMock):
                    from src.security.anomaly_detector import check_anomalies
                    result = await check_anomalies("stranger@example.com", actor="user")

        types = [a["type"] for a in result]
        assert "rate_limit_exceeded" in types
        assert "new_recipient" in types
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_does_not_log_security_event_for_new_recipient_only(self) -> None:
        # New recipient alone is medium severity — does not trigger a security log
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": True, "count": 0, "limit": 20}):
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=True):
                with patch("src.security.anomaly_detector.log_security_event",
                           new_callable=AsyncMock) as mock_log:
                    from src.security.anomaly_detector import check_anomalies
                    result = await check_anomalies("new@example.com", actor="user")

        mock_log.assert_not_called()
        assert len(result) == 1
        assert result[0]["type"] == "new_recipient"

    @pytest.mark.asyncio
    async def test_uses_custom_rate_limit(self) -> None:
        with patch("src.security.anomaly_detector.check_send_rate",
                   new_callable=AsyncMock,
                   return_value={"allowed": True, "count": 3, "limit": 5}) as mock_rate:
            with patch("src.security.anomaly_detector.check_new_recipient",
                       new_callable=AsyncMock, return_value=False):
                from src.security.anomaly_detector import check_anomalies
                await check_anomalies("known@example.com", actor="user", rate_limit=5)

        mock_rate.assert_called_once_with("user", limit=5)
