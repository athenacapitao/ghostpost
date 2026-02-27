"""Tests for src/research/identities.py — sender identity management."""

import pytest
from pathlib import Path

from src.research.identities import (
    _parse_frontmatter,
    list_identities,
    load_identity,
    validate_identity,
    get_identity_context,
    save_identity,
    IDENTITIES_DIR,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_identity(tmp_path: Path, name: str, content: str) -> Path:
    """Write a raw identity file into tmp_path and return its path."""
    path = tmp_path / f"{name}.md"
    path.write_text(content, encoding="utf-8")
    return path


_FULL_IDENTITY = """\
---
identity_id: "acme"
company_name: "Acme Corp"
website: "https://acme.com"
industry: "AI Consulting"
tagline: "We build smart things"
sender_name: "Jane Doe"
sender_title: "CEO"
sender_email: "jane@acme.com"
sender_phone: "+351 912 345 678"
sender_linkedin: "https://linkedin.com/in/janedoe"
calendar_link: "https://cal.com/janedoe"
created: "2026-01-01"
last_updated: "2026-02-01"
---

# Company Overview
Acme Corp builds AI-powered tools.

# Signature Block
Jane Doe | CEO | Acme Corp
"""

_MINIMAL_IDENTITY = """\
---
identity_id: "minimal"
company_name: "Minimal Co"
sender_name: "Bob"
sender_title: "Founder"
sender_email: "bob@minimal.co"
---

Just a body.
"""


# ---------------------------------------------------------------------------
# _parse_frontmatter
# ---------------------------------------------------------------------------

class TestParseFrontmatter:
    def test_returns_empty_dict_when_no_frontmatter(self) -> None:
        metadata, body = _parse_frontmatter("No frontmatter here.")
        assert metadata == {}
        assert body == "No frontmatter here."

    def test_parses_string_fields(self) -> None:
        content = '---\nname: "Alice"\ntitle: "Engineer"\n---\nBody text'
        metadata, body = _parse_frontmatter(content)
        assert metadata["name"] == "Alice"
        assert metadata["title"] == "Engineer"

    def test_strips_quotes_from_values(self) -> None:
        content = "---\nkey: \"quoted\"\n---\n"
        metadata, _ = _parse_frontmatter(content)
        assert metadata["key"] == "quoted"

    def test_parses_boolean_true(self) -> None:
        content = "---\nflag: true\n---\n"
        metadata, _ = _parse_frontmatter(content)
        assert metadata["flag"] is True

    def test_parses_boolean_false(self) -> None:
        content = "---\nflag: false\n---\n"
        metadata, _ = _parse_frontmatter(content)
        assert metadata["flag"] is False

    def test_returns_body_after_frontmatter(self) -> None:
        content = "---\nkey: val\n---\nThis is the body."
        _, body = _parse_frontmatter(content)
        assert body == "This is the body."

    def test_incomplete_frontmatter_returns_empty_dict(self) -> None:
        # Only one --- delimiter
        content = "---\nkey: val\n"
        metadata, body = _parse_frontmatter(content)
        assert metadata == {}
        assert body == content

    def test_value_with_colon_in_url(self) -> None:
        content = '---\nwebsite: "https://example.com"\n---\n'
        metadata, _ = _parse_frontmatter(content)
        assert metadata["website"] == "https://example.com"


# ---------------------------------------------------------------------------
# list_identities
# ---------------------------------------------------------------------------

class TestListIdentities:
    def test_returns_empty_list_when_dir_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path / "nonexistent")
        result = list_identities()
        assert result == []

    def test_excludes_template_files(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "_template", "---\n---\n")
        _write_identity(tmp_path, "real_identity", "---\n---\n")
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = list_identities()
        assert "_template" not in result
        assert "real_identity" in result

    def test_returns_sorted_list(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "zebra", "---\n---\n")
        _write_identity(tmp_path, "alpha", "---\n---\n")
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = list_identities()
        assert result == sorted(result)

    def test_returns_stems_not_filenames(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", "---\n---\n")
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = list_identities()
        assert "acme" in result
        assert "acme.md" not in result


# ---------------------------------------------------------------------------
# load_identity
# ---------------------------------------------------------------------------

class TestLoadIdentity:
    def test_raises_file_not_found_for_missing_identity(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="Identity 'ghost' not found"):
            load_identity("ghost")

    def test_loads_metadata_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = load_identity("acme")
        assert result["identity_id"] == "acme"
        assert result["company_name"] == "Acme Corp"
        assert result["sender_email"] == "jane@acme.com"

    def test_loads_body_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = load_identity("acme")
        assert "Company Overview" in result["body"]
        assert "Acme Corp builds AI-powered tools" in result["body"]

    def test_returns_dict_with_body_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "minimal", _MINIMAL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = load_identity("minimal")
        assert "body" in result


# ---------------------------------------------------------------------------
# validate_identity
# ---------------------------------------------------------------------------

class TestValidateIdentity:
    def test_valid_identity_returns_true_with_no_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        is_valid, missing = validate_identity("acme")
        assert is_valid is True
        assert missing == []

    def test_minimal_valid_identity(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "minimal", _MINIMAL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        is_valid, missing = validate_identity("minimal")
        assert is_valid is True

    def test_missing_file_returns_false_with_message(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        is_valid, missing = validate_identity("nonexistent")
        assert is_valid is False
        assert len(missing) == 1
        assert "not found" in missing[0]

    def test_identity_missing_required_fields_returns_false(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        partial = "---\nidentity_id: \"partial\"\ncompany_name: \"Partial Co\"\n---\nBody."
        _write_identity(tmp_path, "partial", partial)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        is_valid, missing = validate_identity("partial")
        assert is_valid is False
        assert "sender_name" in missing
        assert "sender_email" in missing
        assert "sender_title" in missing

    def test_reports_all_missing_required_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        empty_fm = "---\n---\nBody."
        _write_identity(tmp_path, "empty", empty_fm)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        is_valid, missing = validate_identity("empty")
        assert is_valid is False
        assert len(missing) == 5  # all 5 required fields missing


# ---------------------------------------------------------------------------
# get_identity_context
# ---------------------------------------------------------------------------

class TestGetIdentityContext:
    def test_includes_company_name_in_header(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        context = get_identity_context("acme")
        assert "Acme Corp" in context

    def test_includes_sender_email(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        context = get_identity_context("acme")
        assert "jane@acme.com" in context

    def test_includes_body_content(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        context = get_identity_context("acme")
        assert "Company Overview" in context

    def test_omits_empty_optional_fields(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "minimal", _MINIMAL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        context = get_identity_context("minimal")
        # Fields not present in minimal identity should not appear as label lines
        assert "**Website:**" not in context
        assert "**Phone:**" not in context

    def test_raises_for_missing_identity(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        with pytest.raises(FileNotFoundError):
            get_identity_context("missing")

    def test_returns_markdown_formatted_string(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        _write_identity(tmp_path, "acme", _FULL_IDENTITY)
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        context = get_identity_context("acme")
        assert context.startswith("## Sender Identity:")
        assert "**" in context  # bold markdown labels


# ---------------------------------------------------------------------------
# save_identity
# ---------------------------------------------------------------------------

class TestSaveIdentity:
    def test_creates_file_in_identities_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        metadata = {
            "identity_id": "newco",
            "company_name": "New Co",
            "sender_name": "Alice",
            "sender_title": "CTO",
            "sender_email": "alice@newco.io",
        }
        path = save_identity("newco", metadata, "# Overview\nWe build things.")
        assert path.exists()
        assert path.name == "newco.md"

    def test_saved_file_is_loadable(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        metadata = {
            "identity_id": "roundtrip",
            "company_name": "Roundtrip Inc",
            "sender_name": "Carol",
            "sender_title": "VP Sales",
            "sender_email": "carol@roundtrip.com",
        }
        save_identity("roundtrip", metadata, "# Overview\nRoundtrip body.")
        loaded = load_identity("roundtrip")
        assert loaded["company_name"] == "Roundtrip Inc"
        assert loaded["sender_email"] == "carol@roundtrip.com"
        assert "Roundtrip body." in loaded["body"]

    def test_saves_boolean_fields_as_lowercase(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        metadata = {"active": True, "archived": False}
        path = save_identity("booltest", metadata, "body")
        raw = path.read_text()
        assert "active: true" in raw
        assert "archived: false" in raw

    def test_saves_numeric_fields_without_quotes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        metadata = {"max_replies": 3, "weight": 1.5}
        path = save_identity("numtest", metadata, "body")
        raw = path.read_text()
        assert "max_replies: 3" in raw
        assert "weight: 1.5" in raw

    def test_overwrites_existing_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        metadata_v1 = {"company_name": "Version One"}
        save_identity("overwrite", metadata_v1, "old body")
        metadata_v2 = {"company_name": "Version Two"}
        save_identity("overwrite", metadata_v2, "new body")
        loaded = load_identity("overwrite")
        assert loaded["company_name"] == "Version Two"
        assert "new body" in loaded["body"]

    def test_creates_directory_if_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        nested_dir = tmp_path / "config" / "identities"
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", nested_dir)
        assert not nested_dir.exists()
        save_identity("test", {"key": "val"}, "body")
        assert nested_dir.exists()

    def test_returns_path_object(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("src.research.identities.IDENTITIES_DIR", tmp_path)
        result = save_identity("pathtest", {"key": "val"}, "body")
        assert isinstance(result, Path)
