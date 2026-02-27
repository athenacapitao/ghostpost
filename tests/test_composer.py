"""Tests for src/engine/composer.py — LLM-powered reply generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session(
    thread: object = None,
    emails: list | None = None,
    contact: object = None,
    setting_value: str | None = None,
) -> AsyncMock:
    """Build a mock async_session context manager."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    # session.get: first call is the Setting (reply_style), later calls are Thread/Setting
    mock_session.get = AsyncMock(return_value=thread)

    # session.execute for email/contact queries
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = emails or []
    mock_scalars.scalar_one_or_none.return_value = contact

    mock_execute_result = MagicMock()
    mock_execute_result.scalars.return_value = mock_scalars

    mock_session.execute = AsyncMock(return_value=mock_execute_result)
    return mock_session


def _make_email(
    from_address: str = "sender@example.com",
    subject: str = "Hello",
    body_plain: str = "Hello there",
    is_sent: bool = False,
    date: object = None,
) -> MagicMock:
    email = MagicMock()
    email.from_address = from_address
    email.subject = subject
    email.body_plain = body_plain
    email.is_sent = is_sent
    email.date = date
    return email


def _make_thread(
    subject: str = "Test thread",
    goal: str | None = None,
    playbook: str | None = None,
) -> MagicMock:
    thread = MagicMock()
    thread.subject = subject
    thread.goal = goal
    thread.playbook = playbook
    return thread


# ---------------------------------------------------------------------------
# _get_reply_style
# ---------------------------------------------------------------------------

class TestGetReplyStyle:
    @pytest.mark.asyncio
    async def test_returns_setting_value_when_set(self) -> None:
        mock_setting = MagicMock()
        mock_setting.value = "formal"
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.composer.async_session", return_value=mock_session):
            from src.engine.composer import _get_reply_style
            result = await _get_reply_style()

        assert result == "formal"

    @pytest.mark.asyncio
    async def test_returns_default_when_setting_missing(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.composer.async_session", return_value=mock_session):
            from src.engine.composer import _get_reply_style
            result = await _get_reply_style()

        assert result == "professional"

    @pytest.mark.asyncio
    async def test_returns_default_when_setting_value_is_empty(self) -> None:
        mock_setting = MagicMock()
        mock_setting.value = ""
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.composer.async_session", return_value=mock_session):
            from src.engine.composer import _get_reply_style
            result = await _get_reply_style()

        assert result == "professional"


# ---------------------------------------------------------------------------
# _get_custom_style_prompt
# ---------------------------------------------------------------------------

class TestGetCustomStylePrompt:
    @pytest.mark.asyncio
    async def test_returns_custom_value_when_set(self) -> None:
        mock_setting = MagicMock()
        mock_setting.value = "Be very terse and bullet-point everything."
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_setting)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.composer.async_session", return_value=mock_session):
            from src.engine.composer import _get_custom_style_prompt
            result = await _get_custom_style_prompt()

        assert result == "Be very terse and bullet-point everything."

    @pytest.mark.asyncio
    async def test_falls_back_to_professional_prompt_when_missing(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.composer.async_session", return_value=mock_session):
            from src.engine.composer import _get_custom_style_prompt, STYLE_PROMPTS
            result = await _get_custom_style_prompt()

        assert result == STYLE_PROMPTS["professional"]


# ---------------------------------------------------------------------------
# generate_reply
# ---------------------------------------------------------------------------

class TestGenerateReplyLlmUnavailable:
    @pytest.mark.asyncio
    async def test_returns_error_when_llm_not_available(self) -> None:
        with patch("src.engine.composer.llm_available", return_value=False):
            from src.engine.composer import generate_reply
            result = await generate_reply(1)

        assert "error" in result
        assert result["error"] == "LLM not available"


class TestGenerateReplyThreadNotFound:
    @pytest.mark.asyncio
    async def test_returns_error_when_thread_missing(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                from src.engine.composer import generate_reply
                result = await generate_reply(999)

        assert result["error"] == "Thread not found"


class TestGenerateReplyNoEmails:
    @pytest.mark.asyncio
    async def test_returns_error_when_thread_has_no_emails(self) -> None:
        mock_thread = _make_thread()
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=mock_thread)

        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_execute_result = MagicMock()
        mock_execute_result.scalars.return_value = mock_scalars
        mock_session.execute = AsyncMock(return_value=mock_execute_result)

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                from src.engine.composer import generate_reply
                result = await generate_reply(1)

        assert result["error"] == "No emails in thread"


class TestGenerateReplySuccess:
    def _setup_session(
        self,
        thread: MagicMock,
        emails: list,
        contact: object = None,
    ) -> AsyncMock:
        """Build a session mock that serves both the thread+email query and the contact query."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.get = AsyncMock(return_value=thread)

        # Contact query
        mock_contact_scalars = MagicMock()
        mock_contact_scalars.scalar_one_or_none.return_value = contact

        # Email query
        mock_email_scalars = MagicMock()
        mock_email_scalars.all.return_value = emails

        def _execute_side_effect(query):
            result = MagicMock()
            result.scalars.return_value = mock_email_scalars
            result.scalar_one_or_none = mock_contact_scalars.scalar_one_or_none
            return result

        mock_session.execute = AsyncMock(side_effect=_execute_side_effect)
        return mock_session

    @pytest.mark.asyncio
    async def test_returns_body_subject_style_and_recipient(self) -> None:
        thread = _make_thread(subject="Deal update")
        email = _make_email(from_address="boss@acme.com", subject="Deal update")
        mock_session = self._setup_session(thread, [email])

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                    with patch("src.engine.composer.complete", new_callable=AsyncMock, return_value="Thanks for the update."):
                        from src.engine.composer import generate_reply
                        result = await generate_reply(1)

        assert result["body"] == "Thanks for the update."
        assert result["to"] == "boss@acme.com"
        assert result["subject"] == "Re: Deal update"
        assert result["style"] == "professional"

    @pytest.mark.asyncio
    async def test_subject_not_double_prefixed(self) -> None:
        """If subject already starts with 'Re:', it should not be doubled."""
        thread = _make_thread(subject="Re: Previous")
        email = _make_email(subject="Re: Previous")
        mock_session = self._setup_session(thread, [email])

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="casual"):
                    with patch("src.engine.composer.complete", new_callable=AsyncMock, return_value="Got it!"):
                        from src.engine.composer import generate_reply
                        result = await generate_reply(1)

        assert result["subject"] == "Re: Previous"

    @pytest.mark.asyncio
    async def test_style_override_is_used_instead_of_setting(self) -> None:
        thread = _make_thread()
        email = _make_email()
        mock_session = self._setup_session(thread, [email])

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                # _get_reply_style should NOT be called when style_override is provided
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock) as mock_style:
                    with patch("src.engine.composer.complete", new_callable=AsyncMock, return_value="Formal reply."):
                        from src.engine.composer import generate_reply
                        result = await generate_reply(1, style_override="formal")

        mock_style.assert_not_called()
        assert result["style"] == "formal"

    @pytest.mark.asyncio
    async def test_instructions_are_included_in_llm_call(self) -> None:
        thread = _make_thread()
        email = _make_email()
        mock_session = self._setup_session(thread, [email])
        captured_user_msg: list[str] = []

        async def _capture_complete(system: str, user_message: str, **kwargs: object) -> str:
            captured_user_msg.append(user_message)
            return "Generated reply."

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                    with patch("src.engine.composer.complete", side_effect=_capture_complete):
                        from src.engine.composer import generate_reply
                        await generate_reply(1, instructions="Keep it under 3 sentences.")

        assert "Keep it under 3 sentences." in captured_user_msg[0]

    @pytest.mark.asyncio
    async def test_goal_included_in_llm_prompt_when_set(self) -> None:
        thread = _make_thread(goal="Close the deal by EOQ")
        email = _make_email()
        mock_session = self._setup_session(thread, [email])
        captured_user_msg: list[str] = []

        async def _capture_complete(system: str, user_message: str, **kwargs: object) -> str:
            captured_user_msg.append(user_message)
            return "Reply body."

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                    with patch("src.engine.composer.complete", side_effect=_capture_complete):
                        from src.engine.composer import generate_reply
                        await generate_reply(1)

        assert "Close the deal by EOQ" in captured_user_msg[0]

    @pytest.mark.asyncio
    async def test_llm_exception_returns_error_dict(self) -> None:
        thread = _make_thread()
        email = _make_email()
        mock_session = self._setup_session(thread, [email])

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                    with patch(
                        "src.engine.composer.complete",
                        side_effect=Exception("timeout"),
                    ):
                        from src.engine.composer import generate_reply
                        result = await generate_reply(1)

        assert "error" in result
        assert "timeout" in result["error"]

    @pytest.mark.asyncio
    async def test_body_is_stripped_of_whitespace(self) -> None:
        thread = _make_thread()
        email = _make_email()
        mock_session = self._setup_session(thread, [email])

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="casual"):
                    with patch("src.engine.composer.complete", new_callable=AsyncMock, return_value="  Hey!  \n"):
                        from src.engine.composer import generate_reply
                        result = await generate_reply(1)

        assert result["body"] == "Hey!"

    @pytest.mark.asyncio
    async def test_contact_info_included_in_system_prompt_when_available(self) -> None:
        thread = _make_thread()
        email = _make_email(from_address="vip@client.com")

        contact = MagicMock()
        contact.name = "Alice"
        contact.preferred_style = "bullet points"
        contact.relationship_type = "client"

        mock_session = self._setup_session(thread, [email], contact=contact)
        captured_system: list[str] = []

        async def _capture_complete(system: str, user_message: str, **kwargs: object) -> str:
            captured_system.append(system)
            return "Reply."

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch("src.engine.composer._get_reply_style", new_callable=AsyncMock, return_value="professional"):
                    with patch("src.engine.composer.complete", side_effect=_capture_complete):
                        from src.engine.composer import generate_reply
                        await generate_reply(1)

        assert "Alice" in captured_system[0]
        assert "bullet points" in captured_system[0]
        assert "client" in captured_system[0]

    @pytest.mark.asyncio
    async def test_custom_style_fetches_custom_prompt(self) -> None:
        thread = _make_thread()
        email = _make_email()
        mock_session = self._setup_session(thread, [email])

        with patch("src.engine.composer.llm_available", return_value=True):
            with patch("src.engine.composer.async_session", return_value=mock_session):
                with patch(
                    "src.engine.composer._get_custom_style_prompt",
                    new_callable=AsyncMock,
                    return_value="My custom writing rules.",
                ) as mock_custom:
                    with patch("src.engine.composer.complete", new_callable=AsyncMock, return_value="Custom reply."):
                        from src.engine.composer import generate_reply
                        result = await generate_reply(1, style_override="custom")

        mock_custom.assert_called_once()
        assert result["style"] == "custom"


class TestStylePrompts:
    def test_all_four_styles_defined(self) -> None:
        from src.engine.composer import STYLE_PROMPTS
        assert "professional" in STYLE_PROMPTS
        assert "casual" in STYLE_PROMPTS
        assert "formal" in STYLE_PROMPTS
        assert "custom" in STYLE_PROMPTS

    def test_default_style_is_professional(self) -> None:
        from src.engine.composer import DEFAULT_STYLE
        assert DEFAULT_STYLE == "professional"
