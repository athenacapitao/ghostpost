"""LLM failure mode tests — validates graceful degradation.

Tests every engine function when LLM returns garbage, times out, is
unavailable, or returns oversized responses.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from src.engine.llm import complete, complete_json, _extract_json, llm_available
from src.engine.categorizer import categorize_thread
from src.engine.summarizer import summarize_thread
from src.engine.analyzer import analyze_email
from src.engine.goals import check_goal_met, set_goal
from src.engine.composer import generate_reply
from src.engine.contacts import enrich_contact
from src.engine.knowledge import extract_outcomes

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# LLM availability check
# ---------------------------------------------------------------------------

class TestLLMAvailability:
    def test_llm_available_with_token(self):
        """llm_available returns True when token is set."""
        with patch("src.engine.llm.settings") as mock_settings:
            mock_settings.LLM_GATEWAY_TOKEN = "test-token"
            assert llm_available() is True

    def test_llm_unavailable_without_token(self):
        """llm_available returns False when token is empty."""
        with patch("src.engine.llm.settings") as mock_settings:
            mock_settings.LLM_GATEWAY_TOKEN = ""
            assert llm_available() is False


# ---------------------------------------------------------------------------
# JSON extraction edge cases
# ---------------------------------------------------------------------------

class TestJSONExtraction:
    def test_extract_valid_json(self):
        """Valid JSON is extracted correctly."""
        result = _extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_extract_json_from_markdown(self):
        """JSON wrapped in markdown code fences."""
        result = _extract_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_extract_json_with_surrounding_text(self):
        """JSON embedded in surrounding text."""
        result = _extract_json('Here is the result: {"key": "value"} end.')
        assert result.get("key") == "value"

    def test_extract_empty_string(self):
        """Empty string returns empty dict."""
        result = _extract_json("")
        assert result == {}

    def test_extract_garbage_text(self):
        """Random text returns empty dict."""
        result = _extract_json("This is not JSON at all, just random text without any braces")
        assert result == {}

    def test_extract_nested_json(self):
        """Nested JSON object."""
        result = _extract_json('{"outer": {"inner": "value"}}')
        assert result.get("outer", {}).get("inner") == "value"


# ---------------------------------------------------------------------------
# Categorizer failure modes
# ---------------------------------------------------------------------------

class TestCategorizerFailures:
    async def test_categorizer_llm_returns_empty(self):
        """Categorizer when LLM returns empty JSON (no category key)."""
        with patch("src.engine.categorizer.llm_available", return_value=True), \
             patch("src.engine.categorizer.complete_json", new_callable=AsyncMock, return_value={}), \
             patch("src.engine.categorizer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock(
                subject="Test", body_plain="Test body", body_html=None
            )
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await categorize_thread(1)
            # Empty JSON response — category should be None or empty
            assert result is None or result == ""

    async def test_categorizer_llm_unavailable(self):
        """Categorizer when LLM is not available."""
        with patch("src.engine.categorizer.llm_available", return_value=False):
            result = await categorize_thread(1)
            assert result is None

    async def test_categorizer_llm_returns_very_long(self):
        """Categorizer when LLM returns 100-word category."""
        long_category = "word " * 100
        with patch("src.engine.categorizer.llm_available", return_value=True), \
             patch("src.engine.categorizer.complete_json", new_callable=AsyncMock, return_value={"category": long_category}), \
             patch("src.engine.categorizer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock(
                subject="Test", body_plain="Test body", body_html=None
            )
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.commit = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await categorize_thread(1)
            # Should handle long response without crashing
            assert isinstance(result, (str, type(None)))


# ---------------------------------------------------------------------------
# Summarizer failure modes
# ---------------------------------------------------------------------------

class TestSummarizerFailures:
    async def test_summarizer_llm_unavailable(self):
        """Summarizer when LLM is not available."""
        with patch("src.engine.summarizer.llm_available", return_value=False):
            result = await summarize_thread(1)
            assert result is None


# ---------------------------------------------------------------------------
# Analyzer failure modes
# ---------------------------------------------------------------------------

class TestAnalyzerFailures:
    async def test_analyzer_invalid_sentiment(self):
        """Analyzer when LLM returns invalid sentiment value."""
        invalid_response = {"sentiment": "confused", "urgency": "medium", "action_required": {"required": False, "description": ""}}
        with patch("src.engine.analyzer.llm_available", return_value=True), \
             patch("src.engine.analyzer.complete_json", new_callable=AsyncMock, return_value=invalid_response), \
             patch("src.engine.analyzer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_email = MagicMock()
            mock_email.subject = "Test"
            mock_email.body_plain = "Test body"
            mock_email.thread_id = 1
            mock_session.get = AsyncMock(return_value=mock_email)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            # Should not crash even with invalid sentiment
            result = await analyze_email(1)
            assert isinstance(result, (dict, type(None)))

    async def test_analyzer_invalid_urgency(self):
        """Analyzer when LLM returns invalid urgency value."""
        invalid_response = {"sentiment": "neutral", "urgency": "extreme", "action_required": {"required": False, "description": ""}}
        with patch("src.engine.analyzer.llm_available", return_value=True), \
             patch("src.engine.analyzer.complete_json", new_callable=AsyncMock, return_value=invalid_response), \
             patch("src.engine.analyzer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_email = MagicMock()
            mock_email.subject = "Test"
            mock_email.body_plain = "Test body"
            mock_email.thread_id = 1
            mock_session.get = AsyncMock(return_value=mock_email)
            mock_session.execute = AsyncMock()
            mock_session.commit = AsyncMock()
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await analyze_email(1)
            assert isinstance(result, (dict, type(None)))


# ---------------------------------------------------------------------------
# Goal checker failure modes
# ---------------------------------------------------------------------------

class TestGoalCheckerFailures:
    async def test_goal_check_llm_unavailable(self):
        """Goal check when LLM is not available."""
        with patch("src.engine.goals.llm_available", return_value=False):
            result = await check_goal_met(1)
            assert result["met"] is False
            assert "not available" in result["reason"].lower()

    async def test_goal_check_no_goal_set(self):
        """Goal check when no goal is set on thread."""
        with patch("src.engine.goals.llm_available", return_value=True), \
             patch("src.engine.goals.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_thread = MagicMock()
            mock_thread.goal = None
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await check_goal_met(1)
            assert result["met"] is False

    async def test_goal_check_ambiguous_answer(self):
        """Goal check when LLM returns ambiguous response."""
        with patch("src.engine.goals.llm_available", return_value=True), \
             patch("src.engine.goals.complete_json", new_callable=AsyncMock, return_value={"met": False, "reason": "Unclear"}), \
             patch("src.engine.goals.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_thread = MagicMock()
            mock_thread.goal = "Get a response"
            mock_thread.acceptance_criteria = "They reply"
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await check_goal_met(1)
            assert isinstance(result, dict)
            assert "met" in result


# ---------------------------------------------------------------------------
# Composer failure modes
# ---------------------------------------------------------------------------

class TestComposerFailures:
    async def test_composer_llm_unavailable(self):
        """Composer when LLM is not available."""
        with patch("src.engine.composer.llm_available", return_value=False):
            result = await generate_reply(1)
            assert "error" in result

    async def test_composer_thread_not_found(self):
        """Composer when thread doesn't exist."""
        with patch("src.engine.composer.llm_available", return_value=True), \
             patch("src.engine.composer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await generate_reply(999999)
            assert "error" in result

    async def test_composer_empty_reply(self):
        """Composer when LLM returns empty reply."""
        with patch("src.engine.composer.llm_available", return_value=True), \
             patch("src.engine.composer.complete", new_callable=AsyncMock, return_value=""), \
             patch("src.engine.composer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_thread = MagicMock()
            mock_thread.subject = "Test"
            mock_thread.goal = None
            mock_thread.playbook = None
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_result = MagicMock()
            mock_email = MagicMock()
            mock_email.from_address = "test@example.com"
            mock_email.subject = "Test"
            mock_email.is_sent = False
            mock_email.body_plain = "Hello"
            mock_email.date = "2024-01-01"
            mock_result.scalars.return_value.all.return_value = [mock_email]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                result = await generate_reply(1)
                # Should return the empty body, not crash
                assert "body" in result or "error" in result

    async def test_composer_llm_exception(self):
        """Composer when LLM call raises exception."""
        with patch("src.engine.composer.llm_available", return_value=True), \
             patch("src.engine.composer.complete", new_callable=AsyncMock, side_effect=httpx.TimeoutException("Timeout")), \
             patch("src.engine.composer.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_thread = MagicMock()
            mock_thread.subject = "Test"
            mock_thread.goal = None
            mock_thread.playbook = None
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_result = MagicMock()
            mock_email = MagicMock()
            mock_email.from_address = "test@example.com"
            mock_email.subject = "Test"
            mock_email.is_sent = False
            mock_email.body_plain = "Hello"
            mock_email.date = "2024-01-01"
            mock_result.scalars.return_value.all.return_value = [mock_email]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                result = await generate_reply(1)
                assert "error" in result


# ---------------------------------------------------------------------------
# Contact enrichment failure modes
# ---------------------------------------------------------------------------

class TestContactEnrichmentFailures:
    async def test_enrich_contact_llm_unavailable(self):
        """Contact enrichment when LLM is not available."""
        with patch("src.engine.contacts.llm_available", return_value=False):
            result = await enrich_contact(1)
            assert result is None or result is False

    async def test_enrich_contact_invalid_json(self):
        """Contact enrichment when LLM returns invalid JSON."""
        with patch("src.engine.contacts.llm_available", return_value=True), \
             patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value={}), \
             patch("src.engine.contacts.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_contact = MagicMock()
            mock_contact.email = "test@test.com"
            mock_contact.name = "Test"
            mock_session.get = AsyncMock(return_value=mock_contact)
            mock_session.commit = AsyncMock()
            # Mock execute().scalars().all() chain for the email query
            mock_scalars = MagicMock()
            mock_scalars.all.return_value = []
            mock_exec_result = MagicMock()
            mock_exec_result.scalars.return_value = mock_scalars
            mock_session.execute = AsyncMock(return_value=mock_exec_result)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await enrich_contact(1)
            # Should handle empty JSON gracefully (no emails = returns None)
            assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Knowledge extraction failure modes
# ---------------------------------------------------------------------------

class TestKnowledgeExtractionFailures:
    async def test_extraction_llm_unavailable(self):
        """Knowledge extraction when LLM is not available."""
        with patch("src.engine.knowledge.llm_available", return_value=False):
            result = await extract_outcomes(1)
            assert result is None

    async def test_extraction_nonexistent_thread(self):
        """Knowledge extraction for nonexistent thread."""
        with patch("src.engine.knowledge.llm_available", return_value=True), \
             patch("src.engine.knowledge.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_session.get = AsyncMock(return_value=None)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await extract_outcomes(999999)
            assert result is None

    async def test_extraction_no_emails(self):
        """Knowledge extraction for thread with no emails."""
        with patch("src.engine.knowledge.llm_available", return_value=True), \
             patch("src.engine.knowledge.async_session") as mock_ctx:
            mock_session = AsyncMock()
            mock_thread = MagicMock()
            mock_thread.subject = "Test"
            mock_thread.goal = None
            mock_thread.acceptance_criteria = None
            mock_thread.goal_status = None
            mock_session.get = AsyncMock(return_value=mock_thread)
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_ctx.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_ctx.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await extract_outcomes(1)
            assert result is None


# ---------------------------------------------------------------------------
# LLM complete function failure modes
# ---------------------------------------------------------------------------

class TestLLMCompleteFunctions:
    async def test_complete_json_garbage_response(self):
        """complete_json when LLM returns non-JSON garbage."""
        with patch("src.engine.llm._get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "This is not JSON at all, just random text"}}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await complete_json("system", "user message")
            assert result == {}

    async def test_complete_json_extremely_long_response(self):
        """complete_json when LLM returns 100KB response."""
        long_response = '{"key": "' + "a" * 100000 + '"}'
        with patch("src.engine.llm._get_client") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": long_response}}]
            }
            mock_response.raise_for_status = MagicMock()
            mock_client.return_value.post = AsyncMock(return_value=mock_response)

            result = await complete_json("system", "user message")
            assert isinstance(result, dict)

    async def test_complete_network_error(self):
        """complete when network error occurs."""
        with patch("src.engine.llm._get_client") as mock_client:
            mock_client.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            with pytest.raises(httpx.ConnectError):
                await complete("system", "user message")

    async def test_complete_timeout(self):
        """complete when request times out."""
        with patch("src.engine.llm._get_client") as mock_client:
            mock_client.return_value.post = AsyncMock(
                side_effect=httpx.TimeoutException("Timeout")
            )

            with pytest.raises(httpx.TimeoutException):
                await complete("system", "user message")
