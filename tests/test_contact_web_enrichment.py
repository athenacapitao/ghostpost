"""Tests for enrich_contact_web in src/engine/contacts.py."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestEnrichContactWebLlmUnavailable:
    @pytest.mark.asyncio
    async def test_returns_none_when_llm_unavailable(self) -> None:
        with patch("src.engine.contacts.llm_available", return_value=False):
            from src.engine.contacts import enrich_contact_web
            result = await enrich_contact_web(1)

        assert result is None


class TestEnrichContactWebContactNotFound:
    @pytest.mark.asyncio
    async def test_returns_none_when_contact_not_found(self) -> None:
        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=None)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                from src.engine.contacts import enrich_contact_web
                result = await enrich_contact_web(999)

        assert result is None


class TestEnrichContactWebLlmReturnsEmpty:
    @pytest.mark.asyncio
    async def test_returns_none_when_llm_returns_empty_dict(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Jane Smith"
        mock_contact.email = "jane@example.com"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value={}):
                    from src.engine.contacts import enrich_contact_web
                    result = await enrich_contact_web(1)

        assert result is None


class TestEnrichContactWebSuccessfulEnrichment:
    @pytest.mark.asyncio
    async def test_returns_data_from_llm(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Jane Smith"
        mock_contact.email = "jane@acme.com"
        mock_contact.notes = None
        mock_contact.enrichment_source = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Acme Corp",
            "role": None,
            "industry": "Technology",
            "company_size": "medium",
            "location": "US",
            "linkedin_likely": True,
            "notes": "acme.com is a well-known tech company",
        }

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value=llm_response):
                    from src.engine.contacts import enrich_contact_web
                    result = await enrich_contact_web(1)

        assert result == llm_response

    @pytest.mark.asyncio
    async def test_sets_enrichment_source_to_web_for_new_contact(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Bob Lee"
        mock_contact.email = "bob@startup.io"
        mock_contact.notes = None
        mock_contact.enrichment_source = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Startup IO",
            "role": "CTO",
            "industry": "SaaS",
            "company_size": "startup",
            "location": "US",
            "linkedin_likely": True,
            "notes": None,
        }

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value=llm_response):
                    from src.engine.contacts import enrich_contact_web
                    await enrich_contact_web(1)

        assert mock_contact.enrichment_source == "web"

    @pytest.mark.asyncio
    async def test_sets_enrichment_source_to_combined_when_already_email_history(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Alice"
        mock_contact.email = "alice@corp.com"
        mock_contact.notes = "Some previous notes"
        mock_contact.enrichment_source = "email_history"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Corp Inc",
            "role": None,
            "industry": "Finance",
            "company_size": "large",
            "location": "UK",
            "linkedin_likely": True,
            "notes": None,
        }

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value=llm_response):
                    from src.engine.contacts import enrich_contact_web
                    await enrich_contact_web(1)

        assert mock_contact.enrichment_source == "email_history+web"

    @pytest.mark.asyncio
    async def test_appends_web_enrichment_note_to_existing_notes(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Alice"
        mock_contact.email = "alice@corp.com"
        mock_contact.notes = "Old notes"
        mock_contact.enrichment_source = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Corp Inc",
            "role": "Engineer",
            "industry": "Finance",
            "company_size": "large",
            "location": "UK",
            "linkedin_likely": False,
            "notes": None,
        }

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value=llm_response):
                    from src.engine.contacts import enrich_contact_web
                    await enrich_contact_web(1)

        assert "Web enrichment:" in mock_contact.notes
        assert "Old notes" in mock_contact.notes

    @pytest.mark.asyncio
    async def test_does_not_duplicate_web_enrichment_note(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Alice"
        mock_contact.email = "alice@corp.com"
        # Already has a web enrichment note
        mock_contact.notes = "Web enrichment: Company: Corp Inc"
        mock_contact.enrichment_source = "web"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Corp Inc",
            "role": None,
            "industry": "Finance",
            "company_size": "large",
            "location": "UK",
            "linkedin_likely": True,
            "notes": None,
        }

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value=llm_response):
                    from src.engine.contacts import enrich_contact_web
                    await enrich_contact_web(1)

        # Note should not be appended again since "Web enrichment:" already present
        assert mock_contact.notes.count("Web enrichment:") == 1

    @pytest.mark.asyncio
    async def test_domain_extracted_from_email_for_llm_prompt(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Test User"
        mock_contact.email = "user@example.org"
        mock_contact.notes = None
        mock_contact.enrichment_source = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Example Org",
            "role": None,
            "industry": "Education",
            "company_size": None,
            "location": None,
            "linkedin_likely": False,
            "notes": None,
        }

        captured_user_msg = []

        async def capturing_complete_json(system, user_message, **kwargs):
            captured_user_msg.append(user_message)
            return llm_response

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", side_effect=capturing_complete_json):
                    from src.engine.contacts import enrich_contact_web
                    await enrich_contact_web(1)

        assert len(captured_user_msg) == 1
        assert "example.org" in captured_user_msg[0]
        assert "user@example.org" in captured_user_msg[0]

    @pytest.mark.asyncio
    async def test_uses_unknown_name_when_contact_name_is_none(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = None
        mock_contact.email = "anon@domain.com"
        mock_contact.notes = None
        mock_contact.enrichment_source = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Domain Co",
            "role": None,
            "industry": None,
            "company_size": None,
            "location": None,
            "linkedin_likely": False,
            "notes": None,
        }

        captured_user_msg = []

        async def capturing_complete_json(system, user_message, **kwargs):
            captured_user_msg.append(user_message)
            return llm_response

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", side_effect=capturing_complete_json):
                    from src.engine.contacts import enrich_contact_web
                    await enrich_contact_web(1)

        assert "Unknown" in captured_user_msg[0]


class TestEnrichContactWebExceptionHandling:
    @pytest.mark.asyncio
    async def test_returns_none_on_llm_exception(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Jane"
        mock_contact.email = "jane@example.com"

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch(
                    "src.engine.contacts.complete_json",
                    new_callable=AsyncMock,
                    side_effect=RuntimeError("LLM timeout"),
                ):
                    from src.engine.contacts import enrich_contact_web
                    result = await enrich_contact_web(1)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_db_commit_exception(self) -> None:
        mock_contact = MagicMock()
        mock_contact.name = "Jane"
        mock_contact.email = "jane@example.com"
        mock_contact.notes = None
        mock_contact.enrichment_source = None

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=mock_contact)
        mock_session.commit = AsyncMock(side_effect=RuntimeError("DB error"))
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        llm_response = {
            "company": "Example",
            "role": "Dev",
            "industry": "Tech",
            "company_size": "small",
            "location": "US",
            "linkedin_likely": True,
            "notes": None,
        }

        with patch("src.engine.contacts.llm_available", return_value=True):
            with patch("src.engine.contacts.async_session", return_value=mock_session):
                with patch("src.engine.contacts.complete_json", new_callable=AsyncMock, return_value=llm_response):
                    from src.engine.contacts import enrich_contact_web
                    result = await enrich_contact_web(1)

        assert result is None
