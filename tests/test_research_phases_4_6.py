"""Tests for Ghost Research pipeline phases 6-8 (peer intel, value plan, email).

Covers:
- src/research/peer_intel.py  — Phase 6: Peer Intelligence
- src/research/value_plan.py  — Phase 7: Value Proposition Plan
- src/research/email_writer.py — Phase 8: Email Composition

All DB-dependent tests mock async_session to avoid a live DB requirement.
LLM and web-research calls are mocked so tests run fully offline.
"""

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.research.condenser import (
    _SYSTEM_PROMPT,
    _TEMPLATES,
    condense_phase,
    condensed_path_for,
    read_condensed_or_full,
)
from src.research.email_writer import _atomic_write, _get_language_instruction, compose_email
from src.research.peer_intel import gather_peer_intel
from src.research.value_plan import create_value_plan


# ---------------------------------------------------------------------------
# Helpers shared across all test classes
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
# _atomic_write (shared utility — tested once here)
# ---------------------------------------------------------------------------

class TestAtomicWrite:
    """Verify _atomic_write creates files correctly and handles errors."""

    def test_writes_content_to_path(self, tmp_path):
        target = str(tmp_path / "subdir" / "file.md")
        _atomic_write(target, "hello world")
        assert Path(target).read_text() == "hello world"

    def test_creates_missing_directories(self, tmp_path):
        target = str(tmp_path / "a" / "b" / "c" / "out.md")
        _atomic_write(target, "content")
        assert Path(target).exists()

    def test_overwrites_existing_file(self, tmp_path):
        target = str(tmp_path / "file.md")
        _atomic_write(target, "first")
        _atomic_write(target, "second")
        assert Path(target).read_text() == "second"

    def test_no_temp_file_left_on_success(self, tmp_path):
        target = str(tmp_path / "file.md")
        _atomic_write(target, "data")
        tmp_files = [f for f in os.listdir(tmp_path) if f.endswith(".tmp")]
        assert tmp_files == []


# ---------------------------------------------------------------------------
# _get_language_instruction
# ---------------------------------------------------------------------------

class TestGetLanguageInstruction:
    """Verify language instruction mapping and auto-detect behavior."""

    @pytest.mark.parametrize("lang,expected_fragment", [
        ("pt-PT", "European Portuguese"),
        ("pt-BR", "Brazilian Portuguese"),
        ("en", "in English"),
        ("es", "in Spanish"),
        ("fr", "in French"),
    ])
    def test_known_languages_return_correct_instruction(self, lang, expected_fragment):
        instruction, rationale = _get_language_instruction(lang, "Acme", "Portugal")
        assert expected_fragment in instruction
        assert rationale == ""

    def test_auto_mode_includes_company_and_country(self):
        instruction, rationale = _get_language_instruction("auto", "Acme Corp", "Brazil")
        assert "Acme Corp" in instruction
        assert "Brazil" in instruction
        assert rationale == "auto-detected"

    def test_unknown_language_falls_back_gracefully(self):
        instruction, rationale = _get_language_instruction("de", "Firma", "Germany")
        assert "de" in instruction
        assert rationale == ""


# ---------------------------------------------------------------------------
# Condenser module
# ---------------------------------------------------------------------------

class TestCondensedPathFor:
    """Verify condensed_path_for produces correct paths."""

    def test_adds_condensed_suffix(self):
        assert condensed_path_for("/a/b/01_company_dossier.md") == "/a/b/01_company_dossier_condensed.md"

    def test_works_with_different_extensions(self):
        assert condensed_path_for("/a/report.txt") == "/a/report_condensed.txt"


class TestReadCondensedOrFull:
    """Verify read_condensed_or_full with fallback logic."""

    def test_prefers_condensed_file(self, tmp_path):
        full = tmp_path / "report.md"
        condensed = tmp_path / "report_condensed.md"
        full.write_text("Full content " * 500)
        condensed.write_text("Condensed bullets")
        assert read_condensed_or_full(str(full)) == "Condensed bullets"

    def test_falls_back_to_full_when_no_condensed(self, tmp_path):
        full = tmp_path / "report.md"
        full.write_text("Full content only")
        assert read_condensed_or_full(str(full)) == "Full content only"

    def test_truncates_full_when_over_limit(self, tmp_path):
        full = tmp_path / "report.md"
        full.write_text("X" * 10000)
        result = read_condensed_or_full(str(full), fallback_limit=100)
        assert len(result) < 200
        assert "truncated" in result

    def test_returns_empty_when_no_file(self, tmp_path):
        assert read_condensed_or_full(str(tmp_path / "missing.md")) == ""


class TestCondensePhase:
    """Verify condense_phase LLM integration and file writing."""

    @pytest.mark.asyncio
    async def test_skips_when_llm_unavailable(self, tmp_path):
        with patch("src.research.condenser.llm_available", return_value=False):
            result = await condense_phase(2, "Full content", str(tmp_path / "report.md"))
        assert result == ""

    @pytest.mark.asyncio
    async def test_skips_unknown_phase(self, tmp_path):
        with patch("src.research.condenser.llm_available", return_value=True):
            result = await condense_phase(99, "Content", str(tmp_path / "report.md"))
        assert result == ""

    @pytest.mark.asyncio
    async def test_calls_llm_and_writes_condensed_file(self, tmp_path):
        full_path = str(tmp_path / "01_company_dossier.md")
        Path(full_path).write_text("Full dossier content")

        with patch("src.research.condenser.llm_available", return_value=True), \
             patch("src.research.condenser.complete", new_callable=AsyncMock) as mock_complete:
            mock_complete.return_value = "- Company: Acme\n- Industry: Retail"
            result = await condense_phase(2, "Full dossier content", full_path)

        assert result == "- Company: Acme\n- Industry: Retail"
        condensed = Path(str(tmp_path / "01_company_dossier_condensed.md"))
        assert condensed.exists()
        assert condensed.read_text() == result

    @pytest.mark.asyncio
    async def test_returns_empty_on_llm_failure(self, tmp_path):
        full_path = str(tmp_path / "report.md")

        with patch("src.research.condenser.llm_available", return_value=True), \
             patch("src.research.condenser.complete", new_callable=AsyncMock, side_effect=Exception("timeout")):
            result = await condense_phase(2, "Content", full_path)

        assert result == ""

    @pytest.mark.asyncio
    async def test_has_templates_for_phases_2_through_7(self):
        for phase in [2, 3, 4, 5, 6, 7]:
            assert phase in _TEMPLATES, f"Missing template for phase {phase}"


# ---------------------------------------------------------------------------
# Phase 6 — gather_peer_intel
# ---------------------------------------------------------------------------

class TestGatherPeerIntel:
    """Tests for Phase 6 peer intelligence module."""

    @pytest.mark.asyncio
    async def test_raises_if_campaign_not_found(self):
        """gather_peer_intel must raise ValueError when campaign is missing."""
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args):
                pass

        with patch("src.research.peer_intel.async_session", return_value=_Ctx()):
            with pytest.raises(ValueError, match="Campaign 99 not found"):
                await gather_peer_intel(99)

    @pytest.mark.asyncio
    async def test_no_llm_writes_raw_search_data(self, tmp_path):
        """When LLM is unavailable, raw search results are written to file."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=False),
            patch("src.research.peer_intel.web_search", new_callable=AsyncMock) as mock_search,
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock) as mock_fetch,
        ):
            mock_search.return_value = [
                {"title": "Case Study", "url": "https://example.com/cs", "snippet": "Results"},
            ]
            mock_fetch.return_value = "Fetched page content"

            result = await gather_peer_intel(42)

        assert result.endswith("04_peer_intelligence.md")
        content = Path(result).read_text()
        assert "Peer Intelligence Report" in content
        assert "LLM not available" in content

    @pytest.mark.asyncio
    async def test_with_llm_writes_synthesized_report(self, tmp_path):
        """When LLM is available, the synthesized report is written."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=True),
            patch("src.research.peer_intel.web_search", new_callable=AsyncMock) as mock_search,
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock) as mock_fetch,
            patch("src.research.peer_intel.complete", new_callable=AsyncMock) as mock_complete,
            patch("src.research.peer_intel.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            mock_search.return_value = [
                {"title": "Example", "url": "https://example.com", "snippet": "Good results"},
            ]
            mock_fetch.return_value = "Page body text"
            mock_complete.return_value = "# Peer Intelligence Report\n\nPeer 1: Competitor Co achieved 40% savings."

            result = await gather_peer_intel(42)

        content = Path(result).read_text()
        assert "Peer 1: Competitor Co" in content
        # Frontmatter should be present
        assert 'company: "Acme Corp"' in content
        assert "sources_consulted:" in content

    @pytest.mark.asyncio
    async def test_reads_prior_phase_files_when_present(self, tmp_path):
        """Phase 6 reads condensed prior phase files when they exist."""
        campaign = _make_campaign()
        # Pre-create condensed prior phase files (preferred over full)
        company_dir = tmp_path / "acme_corp"
        company_dir.mkdir(parents=True)
        (company_dir / "01_company_dossier_condensed.md").write_text("Condensed dossier here")
        (company_dir / "02_opportunity_analysis_condensed.md").write_text("Condensed opportunities here")

        session_ctx = _build_session_context(campaign)

        captured_prompts: list[str] = []

        async def mock_complete(system, user_message, max_tokens, temperature, **kwargs):
            captured_prompts.append(user_message)
            return "# Peer report\n\nSome peer data."

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=True),
            patch("src.research.peer_intel.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock, return_value=""),
            patch("src.research.peer_intel.complete", side_effect=mock_complete),
            patch("src.research.peer_intel.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            await gather_peer_intel(42)

        assert len(captured_prompts) == 1
        assert "Condensed dossier here" in captured_prompts[0]
        assert "Condensed opportunities here" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_falls_back_to_full_files_when_no_condensed(self, tmp_path):
        """Phase 6 falls back to full files when condensed versions don't exist."""
        campaign = _make_campaign()
        company_dir = tmp_path / "acme_corp"
        company_dir.mkdir(parents=True)
        (company_dir / "01_company_dossier.md").write_text("Full dossier content")
        (company_dir / "02_opportunity_analysis.md").write_text("Full opportunity content")

        session_ctx = _build_session_context(campaign)

        captured_prompts: list[str] = []

        async def mock_complete(system, user_message, max_tokens, temperature, **kwargs):
            captured_prompts.append(user_message)
            return "# Peer report\n\nSome peer data."

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=True),
            patch("src.research.peer_intel.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock, return_value=""),
            patch("src.research.peer_intel.complete", side_effect=mock_complete),
            patch("src.research.peer_intel.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            await gather_peer_intel(42)

        assert len(captured_prompts) == 1
        assert "Full dossier content" in captured_prompts[0]
        assert "Full opportunity content" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_goal_specific_queries_for_ai_keyword(self, tmp_path):
        """AI-related goals generate AI-specific peer search queries."""
        campaign = _make_campaign(goal="sell AI automation platform")
        session_ctx = _build_session_context(campaign)

        executed_queries: list[str] = []

        async def mock_search(query, num_results=8):
            executed_queries.append(query)
            return []

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=False),
            patch("src.research.peer_intel.web_search", side_effect=mock_search),
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            await gather_peer_intel(42)

        # At least one AI-related query should be present
        ai_queries = [q for q in executed_queries if "AI" in q or "automation" in q]
        assert len(ai_queries) > 0

    @pytest.mark.asyncio
    async def test_goal_specific_queries_for_partner_keyword(self, tmp_path):
        """Partner-related goals generate partnership-specific peer search queries."""
        campaign = _make_campaign(goal="build integration partnerships")
        session_ctx = _build_session_context(campaign)

        executed_queries: list[str] = []

        async def mock_search(query, num_results=8):
            executed_queries.append(query)
            return []

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=False),
            patch("src.research.peer_intel.web_search", side_effect=mock_search),
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            await gather_peer_intel(42)

        partner_queries = [q for q in executed_queries if "partner" in q.lower()]
        assert len(partner_queries) > 0

    @pytest.mark.asyncio
    async def test_updates_campaign_status_to_phase_6(self, tmp_path):
        """Phase 6 sets campaign status to 'phase_6' and phase to 6."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=False),
            patch("src.research.peer_intel.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            await gather_peer_intel(42)

        assert campaign.status == "phase_6"
        assert campaign.phase == 6

    @pytest.mark.asyncio
    async def test_output_file_has_valid_frontmatter(self, tmp_path):
        """Output markdown file must contain expected YAML frontmatter keys."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.peer_intel.async_session", return_value=session_ctx),
            patch("src.research.peer_intel.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.peer_intel.llm_available", return_value=False),
            patch("src.research.peer_intel.web_search", new_callable=AsyncMock, return_value=[]),
            patch("src.research.peer_intel.fetch_page", new_callable=AsyncMock, return_value=""),
        ):
            result = await gather_peer_intel(42)

        content = Path(result).read_text()
        assert content.startswith("---")
        assert 'company: "Acme Corp"' in content
        assert "peer_report_date:" in content


# ---------------------------------------------------------------------------
# Phase 7 — create_value_plan
# ---------------------------------------------------------------------------

class TestCreateValuePlan:
    """Tests for Phase 7 value proposition plan module."""

    @pytest.mark.asyncio
    async def test_raises_if_campaign_not_found(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args):
                pass

        with patch("src.research.value_plan.async_session", return_value=_Ctx()):
            with pytest.raises(ValueError, match="Campaign 77 not found"):
                await create_value_plan(77)

    @pytest.mark.asyncio
    async def test_no_llm_writes_research_context_fallback(self, tmp_path):
        """When LLM is unavailable, a fallback plan is written with char counts."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.value_plan.async_session", return_value=session_ctx),
            patch("src.research.value_plan.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.value_plan.llm_available", return_value=False),
            patch("src.research.value_plan.get_identity_context", return_value="Identity context"),
        ):
            result = await create_value_plan(42)

        content = Path(result).read_text()
        assert "LLM not available" in content
        assert "Value Proposition Plan" in content
        assert result.endswith("05_value_proposition_plan.md")

    @pytest.mark.asyncio
    async def test_with_llm_writes_synthesized_plan(self, tmp_path):
        """When LLM is available, synthesized plan content is written."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.value_plan.async_session", return_value=session_ctx),
            patch("src.research.value_plan.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.value_plan.llm_available", return_value=True),
            patch("src.research.value_plan.get_identity_context", return_value="Sender identity details"),
            patch("src.research.value_plan.complete", new_callable=AsyncMock) as mock_complete,
            patch("src.research.value_plan.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            mock_complete.return_value = "# Value Proposition Plan\n\nPhase 1: Quick Wins — 40% reduction."
            result = await create_value_plan(42)

        content = Path(result).read_text()
        assert "Phase 1: Quick Wins" in content
        assert 'company: "Acme Corp"' in content
        assert 'identity: "athena"' in content

    @pytest.mark.asyncio
    async def test_reads_all_prior_phase_files_condensed(self, tmp_path):
        """Phase 7 reads condensed versions of dossier, opportunity, contacts, peer intel, and person profile."""
        campaign = _make_campaign()
        company_dir = tmp_path / "acme_corp"
        company_dir.mkdir(parents=True)
        (company_dir / "01_company_dossier_condensed.md").write_text("Condensed dossier")
        (company_dir / "02_opportunity_analysis_condensed.md").write_text("Condensed opportunities")
        (company_dir / "03_contacts_search_condensed.md").write_text("Condensed contacts")
        (company_dir / "04_peer_intelligence_condensed.md").write_text("Condensed peer intel")

        session_ctx = _build_session_context(campaign)
        captured_prompts: list[str] = []

        async def mock_complete(system, user_message, max_tokens, temperature, **kwargs):
            captured_prompts.append(user_message)
            return "# Plan\n\nStrategic plan here."

        with (
            patch("src.research.value_plan.async_session", return_value=session_ctx),
            patch("src.research.value_plan.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.value_plan.llm_available", return_value=True),
            patch("src.research.value_plan.get_identity_context", return_value="Identity"),
            patch("src.research.value_plan.complete", side_effect=mock_complete),
            patch("src.research.value_plan.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            await create_value_plan(42)

        assert "Condensed dossier" in captured_prompts[0]
        assert "Condensed opportunities" in captured_prompts[0]
        assert "Condensed contacts" in captured_prompts[0]
        assert "Condensed peer intel" in captured_prompts[0]

    @pytest.mark.asyncio
    async def test_identity_not_found_uses_fallback_context(self, tmp_path):
        """When identity file is missing, a fallback string is used gracefully."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.value_plan.async_session", return_value=session_ctx),
            patch("src.research.value_plan.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.value_plan.llm_available", return_value=False),
            patch("src.research.value_plan.get_identity_context", side_effect=FileNotFoundError("not found")),
        ):
            result = await create_value_plan(42)

        assert Path(result).exists()

    @pytest.mark.asyncio
    async def test_updates_campaign_status_to_phase_7(self, tmp_path):
        """Phase 7 sets campaign status to 'phase_7' and phase to 7."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.value_plan.async_session", return_value=session_ctx),
            patch("src.research.value_plan.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.value_plan.llm_available", return_value=False),
            patch("src.research.value_plan.get_identity_context", return_value="context"),
        ):
            await create_value_plan(42)

        assert campaign.status == "phase_7"
        assert campaign.phase == 7

    @pytest.mark.parametrize("goal,expected_fragment", [
        ("sell AI consulting services", "ROI"),
        ("build integration partnerships", "win-win"),
        ("recruit engineering talent", "mission"),
        ("improve customer satisfaction", "consultative"),
    ])
    @pytest.mark.asyncio
    async def test_tone_instruction_matches_goal_type(self, tmp_path, goal, expected_fragment):
        """Tone instructions vary based on goal keywords."""
        campaign = _make_campaign(goal=goal)
        session_ctx = _build_session_context(campaign)

        captured_systems: list[str] = []

        async def mock_complete(system, user_message, max_tokens, temperature, **kwargs):
            captured_systems.append(system)
            return "# Plan"

        with (
            patch("src.research.value_plan.async_session", return_value=session_ctx),
            patch("src.research.value_plan.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.value_plan.llm_available", return_value=True),
            patch("src.research.value_plan.get_identity_context", return_value="identity"),
            patch("src.research.value_plan.complete", side_effect=mock_complete),
            patch("src.research.value_plan.condense_phase", new_callable=AsyncMock, return_value=""),
        ):
            await create_value_plan(42)

        assert len(captured_systems) == 1
        assert expected_fragment in captured_systems[0]


# ---------------------------------------------------------------------------
# Phase 8 — compose_email
# ---------------------------------------------------------------------------

class TestComposeEmail:
    """Tests for Phase 8 email composition module."""

    @pytest.mark.asyncio
    async def test_raises_if_campaign_not_found(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        session.commit = AsyncMock()

        class _Ctx:
            async def __aenter__(self):
                return session

            async def __aexit__(self, *args):
                pass

        with patch("src.research.email_writer.async_session", return_value=_Ctx()):
            with pytest.raises(ValueError, match="Campaign 55 not found"):
                await compose_email(55)

    @pytest.mark.asyncio
    async def test_no_llm_returns_fallback_email(self, tmp_path):
        """When LLM is unavailable, a manual-compose fallback email is returned."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=False),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "athena@test.com",
                "sender_title": "CEO",
                "company_name": "TestCo",
            }),
        ):
            result = await compose_email(42)

        assert result["subject"] == "Opportunity for Acme Corp"
        assert "LLM not available" in result["body"]
        assert result["language"] == "pt-PT"

    @pytest.mark.asyncio
    async def test_with_llm_parses_subject_and_body(self, tmp_path):
        """When LLM returns formatted output, subject and body are correctly parsed."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        llm_output = "SUBJECT: AI gains for Acme Corp\n---\nDear João,\n\nSomalia Energy saw 40% cost savings.\n\nBest,\nAthena\n---"

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=True),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "athena@test.com",
                "sender_title": "CEO",
                "company_name": "TestCo",
            }),
            patch("src.research.email_writer.complete", new_callable=AsyncMock, return_value=llm_output),
        ):
            result = await compose_email(42)

        assert result["subject"] == "AI gains for Acme Corp"
        assert "Dear João" in result["body"]
        assert "40% cost savings" in result["body"]

    @pytest.mark.asyncio
    async def test_fallback_subject_when_llm_output_lacks_subject_marker(self, tmp_path):
        """If LLM output has no SUBJECT: marker, fallback subject is used."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=True),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "a@b.com",
                "sender_title": "",
                "company_name": "",
            }),
            patch(
                "src.research.email_writer.complete",
                new_callable=AsyncMock,
                return_value="Just an email body without subject marker.",
            ),
        ):
            result = await compose_email(42)

        assert result["subject"] == "Opportunity for Acme Corp"

    @pytest.mark.asyncio
    async def test_writes_draft_markdown_file(self, tmp_path):
        """Phase 8 writes 06_email_draft.md with full email details."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=False),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "athena@test.com",
                "sender_title": "CEO",
                "company_name": "TestCo",
            }),
        ):
            await compose_email(42)

        draft_path = tmp_path / "acme_corp" / "06_email_draft.md"
        assert draft_path.exists()
        content = draft_path.read_text()
        assert "Email Body (this is what gets sent)" in content
        assert "Metadata (not sent)" in content
        assert "Phases | 1-8" in content

    @pytest.mark.asyncio
    async def test_updates_campaign_db_with_email_content(self, tmp_path):
        """Phase 8 saves email_subject and email_body to campaign in DB."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=False),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "athena@test.com",
                "sender_title": "CEO",
                "company_name": "TestCo",
            }),
        ):
            await compose_email(42)

        assert campaign.email_subject == "Opportunity for Acme Corp"
        assert campaign.email_body is not None

    @pytest.mark.asyncio
    async def test_updates_campaign_status_to_phase_8(self, tmp_path):
        """Phase 8 sets campaign status to 'phase_8' and phase to 8."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=False),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "a@b.com",
                "sender_title": "",
                "company_name": "",
            }),
        ):
            await compose_email(42)

        assert campaign.status == "phase_8"
        assert campaign.phase == 8

    @pytest.mark.asyncio
    async def test_identity_not_found_uses_default_sender(self, tmp_path):
        """When identity file is missing, defaults are used without crashing."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=False),
            patch("src.research.email_writer.load_identity", side_effect=FileNotFoundError("missing")),
        ):
            result = await compose_email(42)

        assert result["subject"] == "Opportunity for Acme Corp"
        # Default sender name should appear in the draft
        draft_path = tmp_path / "acme_corp" / "06_email_draft.md"
        content = draft_path.read_text()
        assert "Athena" in content

    @pytest.mark.asyncio
    async def test_reads_prior_phase_context_files_condensed(self, tmp_path):
        """Phase 8 reads condensed versions of prior phase files into context."""
        campaign = _make_campaign()
        company_dir = tmp_path / "acme_corp"
        company_dir.mkdir(parents=True)
        (company_dir / "05_value_proposition_plan_condensed.md").write_text("Condensed value plan")
        (company_dir / "04_peer_intelligence_condensed.md").write_text("Condensed peer intel")
        (company_dir / "03_contacts_search_condensed.md").write_text("Condensed contacts")
        (company_dir / "01_company_dossier_condensed.md").write_text("Condensed dossier")

        session_ctx = _build_session_context(campaign)
        captured_prompts: list[str] = []

        async def mock_complete(system, user_message, max_tokens, temperature, **kwargs):
            captured_prompts.append(user_message)
            return "SUBJECT: Test subject\n---\nEmail body\n---"

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=True),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "a@b.com",
                "sender_title": "",
                "company_name": "",
            }),
            patch("src.research.email_writer.complete", side_effect=mock_complete),
        ):
            await compose_email(42)

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "Condensed value plan" in prompt
        assert "Condensed peer intel" in prompt
        assert "Condensed dossier" in prompt

    @pytest.mark.asyncio
    async def test_draft_frontmatter_contains_expected_keys(self, tmp_path):
        """The 06_email_draft.md frontmatter contains all required metadata keys."""
        campaign = _make_campaign()
        session_ctx = _build_session_context(campaign)

        with (
            patch("src.research.email_writer.async_session", return_value=session_ctx),
            patch("src.research.email_writer.RESEARCH_BASE", str(tmp_path)),
            patch("src.research.email_writer.llm_available", return_value=False),
            patch("src.research.email_writer.load_identity", return_value={
                "sender_name": "Athena",
                "sender_email": "a@b.com",
                "sender_title": "",
                "company_name": "",
            }),
        ):
            await compose_email(42)

        content = (tmp_path / "acme_corp" / "06_email_draft.md").read_text()
        for key in ("company:", "contact:", "sender_identity:", "goal:", "language:", "tone:", "draft_date:", "status:"):
            assert key in content, f"Missing frontmatter key: {key}"
