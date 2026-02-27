"""Tests for the playbook system."""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.engine.playbooks import apply_playbook, get_playbook, list_playbooks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_playbook(directory: str, filename: str, content: str) -> None:
    """Write a markdown file into the given directory."""
    Path(directory, filename).write_text(content)


# ---------------------------------------------------------------------------
# list_playbooks
# ---------------------------------------------------------------------------


def test_list_playbooks_empty_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = list_playbooks()
    assert result == []


def test_list_playbooks_returns_md_files_only():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "my-workflow.md", "# My Workflow\nContent here.")
        _write_playbook(tmpdir, "readme.txt", "This should be ignored.")
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = list_playbooks()
    assert len(result) == 1
    assert result[0]["name"] == "my-workflow"
    assert result[0]["title"] == "My Workflow"


def test_list_playbooks_sorted_alphabetically():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "zebra.md", "# Zebra\n")
        _write_playbook(tmpdir, "apple.md", "# Apple\n")
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = list_playbooks()
    assert [r["name"] for r in result] == ["apple", "zebra"]


def test_list_playbooks_extracts_title_from_first_line():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "plan.md", "# Great Plan\n\nSome body text.")
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = list_playbooks()
    assert result[0]["title"] == "Great Plan"


def test_list_playbooks_falls_back_to_name_when_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "empty.md", "")
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = list_playbooks()
    assert result[0]["title"] == "empty"


# ---------------------------------------------------------------------------
# get_playbook
# ---------------------------------------------------------------------------


def test_get_playbook_returns_none_for_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = get_playbook("nonexistent")
    assert result is None


def test_get_playbook_returns_content():
    content = "# Schedule Meeting\n\nSome steps here."
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "schedule-meeting.md", content)
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = get_playbook("schedule-meeting")
    assert result is not None
    assert result["name"] == "schedule-meeting"
    assert result["title"] == "Schedule Meeting"
    assert result["content"] == content


def test_get_playbook_does_not_allow_path_traversal():
    """Names with path separators should not resolve outside the playbooks dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = get_playbook("../etc/passwd")
    # The constructed path will not end in .md so it won't be a valid file
    assert result is None


# ---------------------------------------------------------------------------
# apply_playbook
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_apply_playbook_returns_false_for_missing_playbook():
    with tempfile.TemporaryDirectory() as tmpdir:
        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            result = await apply_playbook(thread_id=1, name="nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_apply_playbook_returns_false_for_missing_thread():
    content = "# My Playbook\n\nContent."
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "my-playbook.md", content)

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_session)

        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            with patch("src.engine.playbooks.async_session", mock_session_factory):
                result = await apply_playbook(thread_id=999, name="my-playbook")

    assert result is False


@pytest.mark.asyncio
async def test_apply_playbook_sets_playbook_field():
    content = "# My Playbook\n\nContent."
    with tempfile.TemporaryDirectory() as tmpdir:
        _write_playbook(tmpdir, "my-playbook.md", content)

        mock_thread = MagicMock()
        mock_thread.playbook = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_thread)
        mock_session.commit = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        mock_session_factory = MagicMock(return_value=mock_session)

        with patch("src.engine.playbooks.PLAYBOOKS_DIR", tmpdir):
            with patch("src.engine.playbooks.async_session", mock_session_factory):
                result = await apply_playbook(thread_id=1, name="my-playbook")

    assert result is True
    assert mock_thread.playbook == "my-playbook"
    mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Bundled playbook files exist and are well-formed
# ---------------------------------------------------------------------------

EXPECTED_PLAYBOOKS = [
    "close-deal",
    "follow-up-generic",
    "negotiate-price",
    "schedule-meeting",
]

REAL_PLAYBOOKS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "playbooks"
)


def test_bundled_playbooks_exist():
    for name in EXPECTED_PLAYBOOKS:
        path = os.path.join(REAL_PLAYBOOKS_DIR, f"{name}.md")
        assert os.path.isfile(path), f"Missing playbook file: {name}.md"


def test_bundled_playbooks_have_h1_title():
    for name in EXPECTED_PLAYBOOKS:
        path = os.path.join(REAL_PLAYBOOKS_DIR, f"{name}.md")
        with open(path) as f:
            first_line = f.readline().strip()
        assert first_line.startswith("# "), (
            f"Playbook '{name}' first line should start with '# '"
        )


def test_bundled_playbooks_have_nonempty_content():
    for name in EXPECTED_PLAYBOOKS:
        path = os.path.join(REAL_PLAYBOOKS_DIR, f"{name}.md")
        content = Path(path).read_text()
        assert len(content) > 100, (
            f"Playbook '{name}' seems too short — may be incomplete"
        )
