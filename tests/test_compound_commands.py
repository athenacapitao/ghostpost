"""Tests for compound command options on GhostPost API routes and CLI.

Covers:
- POST /{thread_id}/reply?draft=true  — saves draft instead of sending
- POST /{thread_id}/reply             — default send path unaffected
- POST /{thread_id}/generate-reply?create_draft=true — generates + saves draft
- POST /{thread_id}/generate-reply                   — default path unaffected
- CLI reply_cmd --draft flag
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_thread_session(thread: object | None) -> AsyncMock:
    """Build a mock async_session that returns the given thread from session.get."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get = AsyncMock(return_value=thread)

    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_execute_result)

    return mock_session


def _make_thread(thread_id: int = 1, subject: str = "Test thread") -> MagicMock:
    thread = MagicMock()
    thread.id = thread_id
    thread.subject = subject
    thread.gmail_thread_id = f"gthread_{thread_id}"
    return thread


def _make_email(
    from_address: str = "sender@example.com",
    subject: str = "Test thread",
    message_id: str = "<msg1@example.com>",
) -> MagicMock:
    email = MagicMock()
    email.from_address = from_address
    email.subject = subject
    email.message_id = message_id
    return email


def _make_draft(draft_id: int = 99) -> MagicMock:
    draft = MagicMock()
    draft.id = draft_id
    return draft


# ---------------------------------------------------------------------------
# Tests: reply_to_thread with draft=True
# ---------------------------------------------------------------------------


class TestReplyEndpointDraftMode:
    """POST /{thread_id}/reply?draft=true should create a draft, not send."""

    @pytest.mark.asyncio
    async def test_draft_true_calls_create_draft_not_send_reply(self) -> None:
        """When draft=True, create_draft is called and send_reply is never called."""
        from src.api.routes.threads import reply_to_thread
        from src.api.schemas import ReplyRequest

        mock_thread = _make_thread()
        mock_email = _make_email()
        mock_draft = _make_draft(draft_id=77)

        # Two session calls: thread lookup, then email lookup
        session_calls = [
            _make_thread_session(mock_thread),
            _make_thread_session(mock_thread),
        ]
        session_calls[1].execute = AsyncMock(
            return_value=MagicMock(
                **{"scalar_one_or_none.return_value": mock_email}
            )
        )

        mock_create_draft = AsyncMock(return_value=mock_draft)
        mock_send_reply = AsyncMock()

        session_iter = iter(session_calls)

        def _session_factory():
            return next(session_iter)

        req = ReplyRequest(body="Draft reply body")

        with (
            patch("src.api.routes.threads.async_session", side_effect=_session_factory),
            patch("src.gmail.send.create_draft", mock_create_draft),
            patch("src.gmail.send.send_reply", mock_send_reply),
        ):
            result = await reply_to_thread(
                thread_id=1,
                req=req,
                draft=True,
                _user="test_user",
            )

        mock_create_draft.assert_awaited_once()
        mock_send_reply.assert_not_awaited()
        assert result["message"] == "Draft created"
        assert result["draft_id"] == 77

    @pytest.mark.asyncio
    async def test_draft_true_skips_safeguard_check(self) -> None:
        """When draft=True, check_send_allowed is never called."""
        from src.api.routes.threads import reply_to_thread
        from src.api.schemas import ReplyRequest

        mock_thread = _make_thread()
        mock_email = _make_email()
        mock_draft = _make_draft(draft_id=55)

        session_calls = [
            _make_thread_session(mock_thread),
            _make_thread_session(mock_thread),
        ]
        session_calls[1].execute = AsyncMock(
            return_value=MagicMock(
                **{"scalar_one_or_none.return_value": mock_email}
            )
        )

        mock_create_draft = AsyncMock(return_value=mock_draft)
        mock_check = AsyncMock(return_value={"allowed": True, "reasons": [], "warnings": []})

        session_iter = iter(session_calls)

        with (
            patch("src.api.routes.threads.async_session", side_effect=lambda: next(session_iter)),
            patch("src.gmail.send.create_draft", mock_create_draft),
            patch("src.security.safeguards.check_send_allowed", mock_check),
        ):
            await reply_to_thread(
                thread_id=1,
                req=ReplyRequest(body="Draft body"),
                draft=True,
                _user="test_user",
            )

        mock_check.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_draft_true_subject_gets_re_prefix(self) -> None:
        """When draft=True and subject lacks 'Re:', the prefix is added."""
        from src.api.routes.threads import reply_to_thread
        from src.api.schemas import ReplyRequest

        mock_thread = _make_thread()
        mock_email = _make_email(subject="Original subject")
        mock_draft = _make_draft()

        session_calls = [
            _make_thread_session(mock_thread),
            _make_thread_session(mock_thread),
        ]
        session_calls[1].execute = AsyncMock(
            return_value=MagicMock(
                **{"scalar_one_or_none.return_value": mock_email}
            )
        )

        captured_kwargs: list[dict] = []

        async def capturing_create_draft(*args, **kwargs) -> MagicMock:
            captured_kwargs.append({"args": args, "kwargs": kwargs})
            return mock_draft

        session_iter = iter(session_calls)

        with (
            patch("src.api.routes.threads.async_session", side_effect=lambda: next(session_iter)),
            patch("src.gmail.send.create_draft", side_effect=capturing_create_draft),
        ):
            await reply_to_thread(
                thread_id=1,
                req=ReplyRequest(body="Body text"),
                draft=True,
                _user="test_user",
            )

        call_kwargs = captured_kwargs[0]["kwargs"]
        # subject is passed as a keyword argument
        subject_passed = call_kwargs["subject"]
        assert subject_passed.startswith("Re:")

    @pytest.mark.asyncio
    async def test_draft_true_subject_not_double_prefixed(self) -> None:
        """When subject already starts with 'Re:', it is not doubled."""
        from src.api.routes.threads import reply_to_thread
        from src.api.schemas import ReplyRequest

        mock_thread = _make_thread()
        mock_email = _make_email(subject="Re: Already prefixed")
        mock_draft = _make_draft()

        session_calls = [
            _make_thread_session(mock_thread),
            _make_thread_session(mock_thread),
        ]
        session_calls[1].execute = AsyncMock(
            return_value=MagicMock(
                **{"scalar_one_or_none.return_value": mock_email}
            )
        )

        captured_kwargs: list[dict] = []

        async def capturing_create_draft(*args, **kwargs) -> MagicMock:
            captured_kwargs.append({"args": args, "kwargs": kwargs})
            return mock_draft

        session_iter = iter(session_calls)

        with (
            patch("src.api.routes.threads.async_session", side_effect=lambda: next(session_iter)),
            patch("src.gmail.send.create_draft", side_effect=capturing_create_draft),
        ):
            await reply_to_thread(
                thread_id=1,
                req=ReplyRequest(body="Body text"),
                draft=True,
                _user="test_user",
            )

        subject_passed = captured_kwargs[0]["kwargs"]["subject"]
        assert subject_passed == "Re: Already prefixed"

    @pytest.mark.asyncio
    async def test_draft_false_uses_send_reply_path(self) -> None:
        """When draft=False (default), send_reply is called as before."""
        from src.api.routes.threads import reply_to_thread
        from src.api.schemas import ReplyRequest

        mock_thread = _make_thread()
        mock_email = _make_email()

        session_calls = [
            _make_thread_session(mock_thread),
            _make_thread_session(mock_thread),
        ]
        session_calls[1].execute = AsyncMock(
            return_value=MagicMock(
                **{"scalar_one_or_none.return_value": mock_email}
            )
        )

        mock_send_reply = AsyncMock(return_value={"id": "gmail_sent_123"})
        mock_create_draft = AsyncMock()
        mock_check = AsyncMock(return_value={"allowed": True, "reasons": [], "warnings": []})
        mock_transition = AsyncMock()
        mock_increment = AsyncMock()

        session_iter = iter(session_calls)

        with (
            patch("src.api.routes.threads.async_session", side_effect=lambda: next(session_iter)),
            patch("src.gmail.send.send_reply", mock_send_reply),
            patch("src.gmail.send.create_draft", mock_create_draft),
            patch("src.security.safeguards.check_send_allowed", mock_check),
            patch("src.engine.state_machine.auto_transition_on_send", mock_transition),
            patch("src.security.safeguards.increment_rate", mock_increment),
        ):
            result = await reply_to_thread(
                thread_id=1,
                req=ReplyRequest(body="Send body"),
                draft=False,
                _user="test_user",
            )

        mock_send_reply.assert_awaited_once()
        mock_create_draft.assert_not_awaited()
        assert result["message"] == "Reply sent"
        assert result["gmail_id"] == "gmail_sent_123"

    @pytest.mark.asyncio
    async def test_thread_not_found_returns_404_in_draft_mode(self) -> None:
        """404 is raised when thread does not exist, even with draft=True."""
        from fastapi import HTTPException
        from src.api.routes.threads import reply_to_thread
        from src.api.schemas import ReplyRequest

        session = _make_thread_session(thread=None)

        with patch("src.api.routes.threads.async_session", return_value=session):
            with pytest.raises(HTTPException) as exc_info:
                await reply_to_thread(
                    thread_id=999,
                    req=ReplyRequest(body="Body"),
                    draft=True,
                    _user="test_user",
                )

        assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Tests: generate_thread_reply with create_draft=True
# ---------------------------------------------------------------------------


class TestGenerateReplyCreateDraftMode:
    """POST /{thread_id}/generate-reply?create_draft=true should generate + save draft."""

    def _make_generate_reply_result(self) -> dict:
        return {
            "body": "Generated reply body",
            "to": "recipient@example.com",
            "subject": "Re: Test thread",
            "style": "professional",
        }

    @pytest.mark.asyncio
    async def test_create_draft_true_saves_draft_and_returns_draft_id(self) -> None:
        """When create_draft=True, generate_reply result gains a draft_id key."""
        from src.api.routes.threads import generate_thread_reply

        mock_draft = _make_draft(draft_id=42)
        generated = self._make_generate_reply_result()

        mock_generate = AsyncMock(return_value=generated)
        mock_create_draft = AsyncMock(return_value=mock_draft)

        with (
            patch("src.engine.composer.generate_reply", mock_generate),
            patch("src.gmail.send.create_draft", mock_create_draft),
        ):
            result = await generate_thread_reply(
                thread_id=1,
                instructions=None,
                style=None,
                create_draft=True,
                _user="test_user",
            )

        mock_create_draft.assert_awaited_once()
        assert result["draft_id"] == 42
        # Original keys must still be present
        assert result["body"] == "Generated reply body"
        assert result["to"] == "recipient@example.com"
        assert result["subject"] == "Re: Test thread"

    @pytest.mark.asyncio
    async def test_create_draft_true_passes_generated_content_to_create_draft(self) -> None:
        """create_draft is called with the body/to/subject from generate_reply."""
        from src.api.routes.threads import generate_thread_reply

        mock_draft = _make_draft(draft_id=7)
        generated = self._make_generate_reply_result()
        captured: list[dict] = []

        mock_generate = AsyncMock(return_value=generated)

        async def capturing_create_draft(*args, **kwargs) -> MagicMock:
            captured.append({"args": args, "kwargs": kwargs})
            return mock_draft

        with (
            patch("src.engine.composer.generate_reply", mock_generate),
            patch("src.gmail.send.create_draft", side_effect=capturing_create_draft),
        ):
            await generate_thread_reply(
                thread_id=5,
                instructions=None,
                style=None,
                create_draft=True,
                _user="test_user",
            )

        assert len(captured) == 1
        call_args = captured[0]["args"]
        call_kwargs = captured[0]["kwargs"]
        # thread_id is the only positional argument
        assert call_args[0] == 5
        # to, subject, body are keyword arguments
        assert call_kwargs["to"] == ["recipient@example.com"]
        assert call_kwargs["subject"] == "Re: Test thread"
        assert call_kwargs["body"] == "Generated reply body"

    @pytest.mark.asyncio
    async def test_create_draft_false_does_not_call_create_draft(self) -> None:
        """When create_draft=False, create_draft is never called."""
        from src.api.routes.threads import generate_thread_reply

        generated = self._make_generate_reply_result()
        mock_generate = AsyncMock(return_value=generated)
        mock_create_draft = AsyncMock()

        with (
            patch("src.engine.composer.generate_reply", mock_generate),
            patch("src.gmail.send.create_draft", mock_create_draft),
        ):
            result = await generate_thread_reply(
                thread_id=1,
                instructions=None,
                style=None,
                create_draft=False,
                _user="test_user",
            )

        mock_create_draft.assert_not_awaited()
        assert "draft_id" not in result

    @pytest.mark.asyncio
    async def test_generate_reply_error_propagates_without_creating_draft(self) -> None:
        """When generate_reply returns an error, create_draft is never called."""
        from fastapi import HTTPException
        from src.api.routes.threads import generate_thread_reply

        mock_generate = AsyncMock(return_value={"error": "Thread not found"})
        mock_create_draft = AsyncMock()

        with (
            patch("src.engine.composer.generate_reply", mock_generate),
            patch("src.gmail.send.create_draft", mock_create_draft),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await generate_thread_reply(
                    thread_id=999,
                    instructions=None,
                    style=None,
                    create_draft=True,
                    _user="test_user",
                )

        mock_create_draft.assert_not_awaited()
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_draft_false_result_has_no_draft_id(self) -> None:
        """Default create_draft=False returns only the generated content fields."""
        from src.api.routes.threads import generate_thread_reply

        generated = self._make_generate_reply_result()
        mock_generate = AsyncMock(return_value=generated)

        with patch("src.engine.composer.generate_reply", mock_generate):
            result = await generate_thread_reply(
                thread_id=1,
                instructions=None,
                style=None,
                create_draft=False,
                _user="test_user",
            )

        assert set(result.keys()) == {"body", "to", "subject", "style"}


# ---------------------------------------------------------------------------
# Tests: CLI reply_cmd --draft flag
# ---------------------------------------------------------------------------


class TestReplyCmdDraftFlag:
    """CLI reply command --draft flag tests."""

    def _invoke(self, args: list[str]) -> object:
        from click.testing import CliRunner
        from src.cli.actions import reply_cmd

        runner = CliRunner()
        return runner.invoke(reply_cmd, args, catch_exceptions=False)

    def test_draft_flag_passes_draft_param_to_api(self) -> None:
        """--draft sends ?draft=true in the query params."""
        captured_params: list[dict] = []

        def mock_api_post(path: str, **kwargs) -> dict:
            captured_params.append(kwargs.get("params", {}))
            return {"draft_id": 11, "message": "Draft created"}

        with patch("src.cli.actions.api_post", side_effect=mock_api_post):
            result = self._invoke(["1", "--body", "Hello", "--draft"])

        assert result.exit_code == 0
        assert captured_params[0] == {"draft": "true"}

    def test_draft_flag_shows_draft_created_message(self) -> None:
        """--draft shows 'Draft created!' with the returned draft ID."""
        with patch("src.cli.actions.api_post", return_value={"draft_id": 55}):
            result = self._invoke(["1", "--body", "Hello", "--draft"])

        assert result.exit_code == 0
        assert "Draft created" in result.output
        assert "55" in result.output

    def test_no_draft_flag_shows_reply_sent_message(self) -> None:
        """Without --draft, the command still shows 'Reply sent!'."""
        with patch("src.cli.actions.api_post", return_value={"gmail_id": "gm123", "warnings": []}):
            result = self._invoke(["1", "--body", "Hello"])

        assert result.exit_code == 0
        assert "Reply sent" in result.output
        assert "gm123" in result.output

    def test_no_draft_flag_sends_empty_params(self) -> None:
        """Without --draft, params dict is empty (no draft key sent)."""
        captured_params: list[dict] = []

        def mock_api_post(path: str, **kwargs) -> dict:
            captured_params.append(kwargs.get("params", {}))
            return {"gmail_id": "gm456", "warnings": []}

        with patch("src.cli.actions.api_post", side_effect=mock_api_post):
            self._invoke(["1", "--body", "Hello"])

        assert captured_params[0] == {}

    def test_draft_flag_with_json_output(self) -> None:
        """--draft --json returns JSON envelope with draft_id."""
        import json

        with patch("src.cli.actions.api_post", return_value={"draft_id": 33, "message": "Draft created"}):
            result = self._invoke(["1", "--body", "Hello", "--draft", "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["ok"] is True
        assert data["data"]["draft_id"] == 33

    def test_draft_flag_warnings_not_shown(self) -> None:
        """In draft mode, warning display logic is skipped (no 'warnings' key expected)."""
        with patch("src.cli.actions.api_post", return_value={"draft_id": 7}):
            result = self._invoke(["1", "--body", "Hello", "--draft"])

        assert "Warning" not in result.output

    def test_reply_warnings_shown_without_draft_flag(self) -> None:
        """Without --draft, any warnings from the API are echoed to the user."""
        with patch(
            "src.cli.actions.api_post",
            return_value={"gmail_id": "gm789", "warnings": ["Rate limit approaching"]},
        ):
            result = self._invoke(["1", "--body", "Hello"])

        assert "Warning: Rate limit approaching" in result.output
