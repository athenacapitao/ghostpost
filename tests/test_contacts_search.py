"""Tests for Ghost Research pipeline Phase 4: Contacts Search.

Covers src/research/contacts_search.py — contact discovery and ranking.

All DB-dependent tests mock async_session to avoid a live DB requirement.
LLM and web-research calls are mocked so tests run fully offline.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.research.contacts_search import _extract_emails, search_contacts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_campaign(**overrides):
    """Return a minimal MagicMock campaign with sensible defaults."""
    campaign = MagicMock()
    campaign.id = 42
    campaign.company_name = "Acme Corp"
    campaign.company_slug = "acme_corp"
    campaign.goal = "sell AI consulting services"
    campaign.industry = "Retail"
    campaign.country = "Portugal"
    campaign.language = "pt-PT"
    campaign.email_tone = "direct-value"
    campaign.identity = "athena"
    campaign.contact_name = "João Silva"
    campaign.contact_email = "joao@acme.pt"
    campaign.contact_role = "CTO"
    campaign.auto_reply_mode = "draft-for-approval"
    campaign.research_data = {}
    for key, value in overrides.items():
        setattr(campaign, key, value)
    return campaign


def _build_session_context(campaign: MagicMock):
    """Return an async context manager mock that yields a session with the campaign."""
    session = AsyncMock()
    session.get = AsyncMock(return_value=campaign)
    session.commit = AsyncMock()

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *args):
            pass

    return _Ctx()


# ---------------------------------------------------------------------------
# _extract_emails unit tests
# ---------------------------------------------------------------------------

class TestExtractEmails:
    """Verify email extraction from text."""

    def test_extracts_valid_emails(self):
        text = "Contact us at ceo@acme.pt or info@acme.pt for details"
        result = _extract_emails(text)
        assert "ceo@acme.pt" in result
        assert "info@acme.pt" in result

    def test_excludes_example_domains(self):
        text = "Send to user@example.com or real@acme.pt"
        result = _extract_emails(text)
        assert "user@example.com" not in result
        assert "real@acme.pt" in result

    def test_deduplicates(self):
        text = "ceo@acme.pt and also CEO@ACME.PT again"
        result = _extract_emails(text)
        assert len(result) == 1

    def test_empty_text_returns_empty(self):
        assert _extract_emails("") == []
        assert _extract_emails("no emails here") == []


# ---------------------------------------------------------------------------
# search_contacts — Phase 4
# ---------------------------------------------------------------------------

class TestSearchContacts:
    """Tests for Phase 4 contacts search module."""

    @pytest.mark.asyncio
    async def test_raises_if_campaign_not_found(self):
        """search_contacts must raise ValueError when campaign is missing."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args):
                pass

        with patch("src.research.contacts_search.async_session", return_value=_Ctx()):
            with pytest.raises(ValueError, match="Campaign 99 not found"):
                await search_contacts(99)

    @pytest.mark.asyncio
    async def test_no_llm_writes_raw_contact_data(self, tmp_path):
        """When LLM is unavailable, raw search data with discovered emails is written."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=False),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock) as mock_search,
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_search.return_value = [
                {"title": "Acme Team", "url": "https://acme.pt/team", "snippet": "CEO: ceo@acme.pt"},
            ]
            mock_fetch.return_value = "Page with director@acme.pt contact info"

            result = await search_contacts(42)

        assert result.endswith("03_contacts_search.md")
        content = Path(result).read_text()
        assert "Contacts Search" in content
        assert "LLM not available" in content
        assert "ceo@acme.pt" in content

    @pytest.mark.asyncio
    async def test_with_llm_writes_ranked_report(self, tmp_path):
        """When LLM is available, the ranked contacts report is written."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=True),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock) as mock_search,
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock) as mock_fetch,
            patch("src.research.contacts_search.complete", new_callable=AsyncMock) as mock_complete,
            patch("src.research.contacts_search.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            mock_search.return_value = [
                {"title": "Acme LinkedIn", "url": "https://linkedin.com/acme", "snippet": "CTO at Acme"},
            ]
            mock_fetch.return_value = "Page content"
            mock_complete.return_value = "# Contacts Search Report\n\n## Recommended Primary Contact\nceo@acme.pt"

            result = await search_contacts(42)

        content = Path(result).read_text()
        assert "Contacts Search Report" in content
        assert 'company: "Acme Corp"' in content
        assert "sources_consulted:" in content

    @pytest.mark.asyncio
    async def test_user_provided_contact_preserved(self, tmp_path):
        """When user provides contact_email, it stays in the campaign (not overwritten)."""
        campaign = _make_campaign(contact_email="user@provided.com")
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=False),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            await search_contacts(42)

        # User's email should NOT be overwritten
        assert campaign.contact_email == "user@provided.com"

    @pytest.mark.asyncio
    async def test_no_user_contact_auto_selects_discovered(self, tmp_path):
        """When no user contact provided, best discovered email is set on campaign."""
        campaign = _make_campaign(contact_email=None, contact_name=None)
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=False),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock) as mock_search,
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_search.return_value = [
                {"title": "Team", "url": "https://acme.pt/team", "snippet": "Contact: cto@acme.pt"},
            ]
            mock_fetch.return_value = "Also info@acme.pt available"

            await search_contacts(42)

        # Should auto-select the named email (not info@)
        assert campaign.contact_email == "cto@acme.pt"

    @pytest.mark.asyncio
    async def test_generic_fallback_when_no_named_contacts(self, tmp_path):
        """When only generic emails found, the generic one is used as fallback."""
        campaign = _make_campaign(contact_email=None, contact_name=None)
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=False),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock) as mock_search,
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_search.return_value = [
                {"title": "Contact", "url": "https://acme.pt/contact", "snippet": "Email: info@acme.pt"},
            ]
            mock_fetch.return_value = ""

            await search_contacts(42)

        assert campaign.contact_email == "info@acme.pt"

    @pytest.mark.asyncio
    async def test_output_file_has_valid_frontmatter(self, tmp_path):
        """Output markdown file must contain expected YAML frontmatter keys."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=False),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            result = await search_contacts(42)

        content = Path(result).read_text()
        assert content.startswith("---")
        assert 'company: "Acme Corp"' in content
        assert "contacts_search_date:" in content
        assert "emails_discovered:" in content

    @pytest.mark.asyncio
    async def test_updates_campaign_status_to_phase_4(self, tmp_path):
        """Phase 4 sets campaign status to 'phase_4' and phase to 4."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.contacts_search.async_session", return_value=session_ctx),
            patch("src.research.contacts_search.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.contacts_search.llm_available", return_value=False),
            patch("src.research.contacts_search.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.contacts_search.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            await search_contacts(42)

        assert campaign.status == "phase_4"
        assert campaign.phase == 4
