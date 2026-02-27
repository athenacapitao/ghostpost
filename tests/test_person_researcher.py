"""Tests for Ghost Research Phase 5 — Person Research.

Covers:
- src/research/person_researcher.py — research_person()
- Query generation, LLM synthesis, file output, DB updates
- Skip behavior when no contact_name (tested via pipeline integration)

All DB-dependent tests mock async_session. LLM and web-research calls are mocked.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.research.person_researcher import research_person


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
    campaign.contact_name = "João Silva"
    campaign.contact_role = "CTO"
    campaign.contact_email = "joao@acme.pt"
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
# Tests
# ---------------------------------------------------------------------------

class TestResearchPerson:
    """Tests for Phase 5 person research module."""

    @pytest.mark.asyncio
    async def test_raises_if_campaign_not_found(self):
        """research_person must raise ValueError when campaign is missing."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args):
                pass

        with patch("src.research.person_researcher.async_session", return_value=_Ctx()):
            with pytest.raises(ValueError, match="Campaign 99 not found"):
                await research_person(99)

    @pytest.mark.asyncio
    async def test_no_llm_writes_raw_search_data(self, tmp_path):
        """When LLM is unavailable, raw search results are written to file."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=False),
            patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
        ):
            mock_research.return_value = {
                "search_results": [
                    {"title": "João LinkedIn", "url": "https://linkedin.com/joao", "snippet": "CTO at Acme"},
                ],
                "fetched_pages": [
                    {"title": "João LinkedIn", "url": "https://linkedin.com/joao", "content": "Full profile text"},
                ],
                "sources": ["https://linkedin.com/joao"],
            }

            result = await research_person(42)

        assert result.endswith("04b_person_profile.md")
        content = Path(result).read_text()
        assert "Person Profile" in content or "LLM not available" in content

    @pytest.mark.asyncio
    async def test_with_llm_writes_synthesized_profile(self, tmp_path):
        """When LLM is available, the synthesized profile is written."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=True),
            patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
            patch("src.research.person_researcher.complete", new_callable=AsyncMock) as mock_complete,
            patch("src.research.person_researcher.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            mock_research.return_value = {
                "search_results": [
                    {"title": "João Talk", "url": "https://example.com/talk", "snippet": "AI keynote"},
                ],
                "fetched_pages": [
                    {"title": "João Talk", "url": "https://example.com/talk", "content": "Full talk transcript"},
                ],
                "sources": ["https://example.com/talk"],
            }
            mock_complete.return_value = "# Person Profile: João Silva\n\n## Executive Summary\nCTO at Acme Corp with 15 years experience."

            result = await research_person(42)

        content = Path(result).read_text()
        assert "João Silva" in content
        assert 'person: "João Silva"' in content
        assert "sources_consulted:" in content

    @pytest.mark.asyncio
    async def test_updates_campaign_status_to_phase_5(self, tmp_path):
        """Phase 5 sets campaign status to 'phase_5' and phase to 5."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=False),
            patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
        ):
            mock_research.return_value = {
                "search_results": [],
                "fetched_pages": [],
                "sources": [],
            }
            await research_person(42)

        assert campaign.status == "phase_5"
        assert campaign.phase == 5

    @pytest.mark.asyncio
    async def test_output_file_has_valid_frontmatter(self, tmp_path):
        """Output markdown file must contain expected YAML frontmatter keys."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=False),
            patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
        ):
            mock_research.return_value = {
                "search_results": [],
                "fetched_pages": [],
                "sources": [],
            }
            result = await research_person(42)

        content = Path(result).read_text()
        assert content.startswith("---")
        assert 'person: "João Silva"' in content
        assert 'company: "Acme Corp"' in content
        assert "research_date:" in content
        assert "confidence_level:" in content

    @pytest.mark.asyncio
    async def test_generates_correct_search_queries(self, tmp_path):
        """Verify all 4 rounds of search queries are generated with correct terms."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        captured_queries = None

        async def mock_research_topic(queries, fetch_top=2):
            nonlocal captured_queries
            captured_queries = queries
            return {"search_results": [], "fetched_pages": [], "sources": []}

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=False),
            patch("src.research.person_researcher.research_topic", side_effect=mock_research_topic),
        ):
            await research_person(42)

        assert captured_queries is not None
        assert len(captured_queries) == 8  # 4 rounds × 2 queries each

        # Round 1 — Professional profile
        assert any("LinkedIn" in q for q in captured_queries)
        assert any("João Silva" in q and "Acme Corp" in q for q in captured_queries)

        # Round 2 — Thought leadership
        assert any("interview" in q or "podcast" in q for q in captured_queries)

        # Round 3 — Social presence
        assert any("Twitter" in q or "GitHub" in q for q in captured_queries)

        # Round 4 — Recent activity
        assert any("news" in q or "award" in q for q in captured_queries)

    @pytest.mark.asyncio
    async def test_reads_prior_phase_files_when_present(self, tmp_path):
        """Phase 5 reads condensed prior phase files for context."""
        campaign = _make_campaign()
        company_dir = tmp_path / "acme_corp"
        company_dir.mkdir(parents=True)
        (company_dir / "01_company_dossier_condensed.md").write_text("Condensed dossier here")
        (company_dir / "03_contacts_search_condensed.md").write_text("Condensed contacts here")

        session_ctx = _build_session_context(campaign)
        captured_prompts: list[str] = []

        async def mock_complete(system, user_message, max_tokens, temperature, **kwargs):
            captured_prompts.append(user_message)
            return "# Person Profile\n\nSome profile data."

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=True),
            patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
            patch("src.research.person_researcher.complete", side_effect=mock_complete),
            patch("src.research.person_researcher.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            mock_research.return_value = {"search_results": [], "fetched_pages": [], "sources": []}
            await research_person(42)

        assert len(captured_prompts) == 1
        assert "Condensed dossier here" in captured_prompts[0]
        assert "Condensed contacts here" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_saves_person_profile_to_campaign_research_data(self, tmp_path):
        """Phase 5 saves person_profile data to campaign.research_data in DB."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.person_researcher.async_session", return_value=session_ctx),
            patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.person_researcher.llm_available", return_value=False),
            patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
        ):
            mock_research.return_value = {
                "search_results": [{"title": "T", "url": "https://x.com", "snippet": "S"}],
                "fetched_pages": [],
                "sources": ["https://x.com"],
            }
            await research_person(42)

        assert "person_profile" in campaign.research_data
        pp = campaign.research_data["person_profile"]
        assert pp["sources_count"] == 1
        assert "confidence" in pp
        assert "searched_at" in pp

    @pytest.mark.asyncio
    async def test_confidence_levels(self, tmp_path):
        """Verify confidence is high/medium/low based on pages fetched."""
        for pages_count, expected_confidence in [(5, "high"), (3, "medium"), (2, "medium"), (1, "low"), (0, "low")]:
            campaign = _make_campaign()
            session_ctx = _build_session_context(campaign)

            pages = [{"title": f"P{i}", "url": f"https://x.com/{i}", "content": "text"} for i in range(pages_count)]

            with (
                patch("src.research.person_researcher.async_session", return_value=session_ctx),
                patch("src.research.person_researcher.RESEARCH_BASE", str(tmp_path)),
                patch("src.research.person_researcher.llm_available", return_value=False),
                patch("src.research.person_researcher.research_topic", new_callable=AsyncMock) as mock_research,
            ):
                mock_research.return_value = {
                    "search_results": [],
                    "fetched_pages": pages,
                    "sources": [p["url"] for p in pages],
                }
                await research_person(42)

            assert campaign.research_data["person_profile"]["confidence"] == expected_confidence, \
                f"Expected {expected_confidence} for {pages_count} pages"


class TestPipelineSkipBehavior:
    """Test that pipeline correctly skips person research when no contact_name."""

    @pytest.mark.asyncio
    async def test_pipeline_includes_person_research_with_contact(self):
        """When contact_name + contact_email set, skips contacts search, includes person research (7 phases)."""
        from src.research.pipeline import run_pipeline

        campaign = _make_campaign(contact_name="João Silva", contact_email="joao@acme.pt")
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.pipeline.async_session", return_value=session_ctx),
            patch("src.research.pipeline.verbose_log", new_callable=AsyncMock),
            patch("src.research.pipeline.log_action", new_callable=AsyncMock),
            patch("src.research.pipeline.collect_input", new_callable=AsyncMock),
            patch("src.research.pipeline.research_company", new_callable=AsyncMock),
            patch("src.research.pipeline.analyze_opportunities", new_callable=AsyncMock),
            patch("src.research.pipeline.search_contacts", new_callable=AsyncMock) as p4,
            patch("src.research.pipeline.research_person", new_callable=AsyncMock) as p5,
            patch("src.research.pipeline.gather_peer_intel", new_callable=AsyncMock),
            patch("src.research.pipeline.create_value_plan", new_callable=AsyncMock),
            patch("src.research.pipeline.compose_email", new_callable=AsyncMock),
        ):
            result = await run_pipeline(42)

        assert result["phases_completed"] == 7
        p4.assert_not_called()
        p5.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_pipeline_runs_contacts_search_when_no_email(self):
        """When contact_name set but no email, runs contacts search + person research (8 phases)."""
        from src.research.pipeline import run_pipeline

        campaign = _make_campaign(contact_name="João Silva", contact_email=None)
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.pipeline.async_session", return_value=session_ctx),
            patch("src.research.pipeline.verbose_log", new_callable=AsyncMock),
            patch("src.research.pipeline.log_action", new_callable=AsyncMock),
            patch("src.research.pipeline.collect_input", new_callable=AsyncMock),
            patch("src.research.pipeline.research_company", new_callable=AsyncMock),
            patch("src.research.pipeline.analyze_opportunities", new_callable=AsyncMock),
            patch("src.research.pipeline.search_contacts", new_callable=AsyncMock) as p4,
            patch("src.research.pipeline.research_person", new_callable=AsyncMock) as p5,
            patch("src.research.pipeline.gather_peer_intel", new_callable=AsyncMock),
            patch("src.research.pipeline.create_value_plan", new_callable=AsyncMock),
            patch("src.research.pipeline.compose_email", new_callable=AsyncMock),
        ):
            result = await run_pipeline(42)

        assert result["phases_completed"] == 8
        p4.assert_called_once_with(42)
        p5.assert_called_once_with(42)

    @pytest.mark.asyncio
    async def test_pipeline_skips_person_research_without_contact(self):
        """When no contact_name and no email, runs contacts search but skips person research (7 phases)."""
        from src.research.pipeline import run_pipeline

        campaign = _make_campaign(contact_name=None, contact_email=None)
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.pipeline.async_session", return_value=session_ctx),
            patch("src.research.pipeline.verbose_log", new_callable=AsyncMock),
            patch("src.research.pipeline.log_action", new_callable=AsyncMock),
            patch("src.research.pipeline.collect_input", new_callable=AsyncMock),
            patch("src.research.pipeline.research_company", new_callable=AsyncMock),
            patch("src.research.pipeline.analyze_opportunities", new_callable=AsyncMock),
            patch("src.research.pipeline.search_contacts", new_callable=AsyncMock) as p4,
            patch("src.research.pipeline.research_person", new_callable=AsyncMock) as p5,
            patch("src.research.pipeline.gather_peer_intel", new_callable=AsyncMock),
            patch("src.research.pipeline.create_value_plan", new_callable=AsyncMock),
            patch("src.research.pipeline.compose_email", new_callable=AsyncMock),
        ):
            result = await run_pipeline(42)

        assert result["phases_completed"] == 7
        p4.assert_called_once_with(42)
        p5.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_skips_both_with_email_no_name(self):
        """When contact_email set but no name, skips both contacts search and person research (6 phases)."""
        from src.research.pipeline import run_pipeline

        campaign = _make_campaign(contact_name=None, contact_email="joao@acme.pt")
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.pipeline.async_session", return_value=session_ctx),
            patch("src.research.pipeline.verbose_log", new_callable=AsyncMock),
            patch("src.research.pipeline.log_action", new_callable=AsyncMock),
            patch("src.research.pipeline.collect_input", new_callable=AsyncMock),
            patch("src.research.pipeline.research_company", new_callable=AsyncMock),
            patch("src.research.pipeline.analyze_opportunities", new_callable=AsyncMock),
            patch("src.research.pipeline.search_contacts", new_callable=AsyncMock) as p4,
            patch("src.research.pipeline.research_person", new_callable=AsyncMock) as p5,
            patch("src.research.pipeline.gather_peer_intel", new_callable=AsyncMock),
            patch("src.research.pipeline.create_value_plan", new_callable=AsyncMock),
            patch("src.research.pipeline.compose_email", new_callable=AsyncMock),
        ):
            result = await run_pipeline(42)

        assert result["phases_completed"] == 6
        p4.assert_not_called()
        p5.assert_not_called()
