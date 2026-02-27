"""Tests for CSV batch import parser and validation.

Covers:
- Smart column detection (EN + PT aliases)
- Header vs positional fallback
- Email validation
- Deduplication
- 100-company cap
- Empty/malformed CSV handling
- File reading (UTF-8 + Latin-1 fallback)
"""

import os
import tempfile

import pytest

from src.research.batch_import import (
    MAX_COMPANIES,
    ParseResult,
    detect_header_mapping,
    parse_csv,
    parse_csv_file,
    validate_companies,
)


# ---------------------------------------------------------------------------
# detect_header_mapping
# ---------------------------------------------------------------------------

class TestDetectHeaderMapping:
    def test_english_headers(self):
        mapping = detect_header_mapping(["company", "goal", "email", "role"])
        assert mapping == {
            "company": "company_name",
            "goal": "goal",
            "email": "contact_email",
            "role": "contact_role",
        }

    def test_portuguese_headers(self):
        mapping = detect_header_mapping(["empresa", "objetivo", "cargo", "país"])
        assert mapping == {
            "empresa": "company_name",
            "objetivo": "goal",
            "cargo": "contact_role",
            "país": "country",
        }

    def test_mixed_case_whitespace(self):
        mapping = detect_header_mapping(["  Company Name  ", "GOAL", " Email "])
        assert mapping == {
            "  Company Name  ": "company_name",
            "GOAL": "goal",
            " Email ": "contact_email",
        }

    def test_unrecognized_columns_excluded(self):
        mapping = detect_header_mapping(["company", "revenue", "founded"])
        assert mapping == {"company": "company_name"}

    def test_empty_headers(self):
        assert detect_header_mapping([]) == {}

    def test_all_aliases_for_company_name(self):
        for alias in ["company_name", "company", "name", "empresa", "company name"]:
            mapping = detect_header_mapping([alias])
            assert list(mapping.values()) == ["company_name"], f"Failed for alias: {alias}"


# ---------------------------------------------------------------------------
# parse_csv — header detection
# ---------------------------------------------------------------------------

class TestParseCSVHeaders:
    def test_standard_csv(self):
        csv = "company,contact_name,email,role,goal,industry,country\nAcme,John,john@acme.pt,CEO,Sell,Tech,PT\n"
        result = parse_csv(csv)
        assert len(result.companies) == 1
        assert result.companies[0]["company_name"] == "Acme"
        assert result.companies[0]["contact_email"] == "john@acme.pt"
        assert result.companies[0]["contact_role"] == "CEO"
        assert not result.errors

    def test_pt_headers(self):
        csv = "empresa,objetivo,cargo,país\nAcme,Vender,CEO,Portugal\n"
        result = parse_csv(csv)
        assert len(result.companies) == 1
        assert result.companies[0]["company_name"] == "Acme"
        assert result.companies[0]["goal"] == "Vender"
        assert result.companies[0]["country"] == "Portugal"

    def test_unrecognized_columns_warning(self):
        csv = "company,revenue,goal\nAcme,1M,Sell\n"
        result = parse_csv(csv)
        assert any("revenue" in w for w in result.warnings)
        assert result.companies[0]["company_name"] == "Acme"
        assert result.companies[0]["goal"] == "Sell"

    def test_extra_context_aliases(self):
        for header in ["notes", "notas", "observações", "context", "extra_context"]:
            csv = f"company,goal,{header}\nAcme,Sell,Some notes\n"
            result = parse_csv(csv)
            assert result.companies[0].get("extra_context") == "Some notes", f"Failed for {header}"


# ---------------------------------------------------------------------------
# parse_csv — positional fallback
# ---------------------------------------------------------------------------

class TestParseCSVPositional:
    def test_no_header_row(self):
        csv = "Acme Corp,Partnership outreach,John Silva,john@acme.pt,CEO,Tech,PT\n"
        result = parse_csv(csv)
        assert any("positional" in w.lower() for w in result.warnings)
        assert result.companies[0]["company_name"] == "Acme Corp"
        assert result.companies[0]["goal"] == "Partnership outreach"
        assert result.companies[0]["contact_name"] == "John Silva"


# ---------------------------------------------------------------------------
# parse_csv — edge cases
# ---------------------------------------------------------------------------

class TestParseCSVEdgeCases:
    def test_empty_csv(self):
        result = parse_csv("")
        assert result.errors
        assert "empty" in result.errors[0].lower()

    def test_single_col_treated_as_data(self):
        # With 2+ match heuristic, single "company" is treated as data, not header
        result = parse_csv("company\n")
        assert len(result.companies) == 1
        assert result.companies[0]["company_name"] == "company"

    def test_header_only_two_cols(self):
        result = parse_csv("company,goal\n")
        assert result.errors
        assert "no data" in result.errors[0].lower()

    def test_empty_cells_become_none(self):
        csv = "company,goal,email\nAcme,,\n"
        result = parse_csv(csv)
        assert result.companies[0]["goal"] is None
        assert result.companies[0]["contact_email"] is None

    def test_skip_blank_rows(self):
        csv = "company,goal\nAcme,Sell\n\n\nBeta,Buy\n"
        result = parse_csv(csv)
        assert len(result.companies) == 2

    def test_whitespace_only_rows_skipped(self):
        csv = "company,goal\nAcme,Sell\n , , \nBeta,Buy\n"
        result = parse_csv(csv)
        assert len(result.companies) == 2

    def test_multiple_rows(self):
        rows = ["company,goal"] + [f"Company{i},Goal{i}" for i in range(50)]
        result = parse_csv("\n".join(rows))
        assert len(result.companies) == 50


# ---------------------------------------------------------------------------
# validate_companies
# ---------------------------------------------------------------------------

class TestValidateCompanies:
    def test_missing_company_name(self):
        result = validate_companies([{"goal": "Sell"}])
        assert len(result.errors) == 1
        assert "company_name" in result.errors[0]
        assert len(result.companies) == 0

    def test_deduplication(self):
        companies = [
            {"company_name": "Acme", "goal": "Sell"},
            {"company_name": "acme", "goal": "Buy"},
        ]
        result = validate_companies(companies)
        assert len(result.companies) == 1
        assert any("duplicate" in w.lower() for w in result.warnings)

    def test_invalid_email_nullified(self):
        result = validate_companies([{"company_name": "Acme", "contact_email": "not-an-email"}])
        assert result.companies[0]["contact_email"] is None
        assert any("invalid email" in w.lower() for w in result.warnings)

    def test_valid_email_kept(self):
        result = validate_companies([{"company_name": "Acme", "contact_email": "john@acme.pt"}])
        assert result.companies[0]["contact_email"] == "john@acme.pt"

    def test_cc_validation(self):
        result = validate_companies([{"company_name": "Acme", "cc": "good@a.com, bad-email, ok@b.com"}])
        assert result.companies[0]["cc"] == "good@a.com, ok@b.com"
        assert any("invalid CC" in w for w in result.warnings)

    def test_cap_at_100(self):
        companies = [{"company_name": f"Co{i}", "goal": "Test"} for i in range(150)]
        result = validate_companies(companies)
        assert len(result.companies) == MAX_COMPANIES
        assert any("capped" in w.lower() for w in result.warnings)

    def test_goal_fallback_warning(self):
        result = validate_companies([{"company_name": "Acme"}])
        assert len(result.companies) == 1
        assert any("no goal" in w.lower() for w in result.warnings)

    def test_goal_from_defaults_no_warning(self):
        result = validate_companies([{"company_name": "Acme"}], defaults={"goal": "Default Goal"})
        assert len(result.companies) == 1
        # No "no goal" warning when defaults provide it
        assert not any("no goal" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# parse_csv with defaults
# ---------------------------------------------------------------------------

class TestParseCSVWithDefaults:
    def test_defaults_applied(self):
        csv = "company,goal\nAcme,\n"
        result = parse_csv(csv, defaults={"goal": "Default Goal", "identity": "athena"})
        assert len(result.companies) == 1
        assert result.companies[0]["company_name"] == "Acme"
        # Goal is None in the row — defaults are merged at batch creation time
        assert not any("no goal" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# parse_csv_file
# ---------------------------------------------------------------------------

class TestParseCSVFile:
    def test_read_utf8_file(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("company,goal\nAcme,Sell\n", encoding="utf-8")
        result = parse_csv_file(str(csv_file))
        assert len(result.companies) == 1

    def test_read_latin1_file(self, tmp_path):
        csv_file = tmp_path / "test.csv"
        csv_file.write_bytes("company,goal\nCafé Corp,Vender\n".encode("latin-1"))
        result = parse_csv_file(str(csv_file))
        assert len(result.companies) == 1

    def test_file_not_found(self):
        result = parse_csv_file("/nonexistent/path.csv")
        assert len(result.errors) == 1
        assert "not found" in result.errors[0].lower()


# ---------------------------------------------------------------------------
# Integration: full CSV -> ParseResult
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_realistic_csv(self):
        csv = """company_name,contact_name,contact_email,contact_role,goal,industry,country
Acme Corp,John Silva,john@acme.pt,CEO,Partnership outreach,Technology,PT
Beta Lda,Sara Costa,sara@beta.io,CTO,Tech collaboration,SaaS,PT
Gamma SA,,,,Market research,Finance,BR
Delta Inc,Bob Smith,invalid-email,VP Sales,Sales demo,Retail,US"""

        result = parse_csv(csv)

        assert len(result.companies) == 4
        assert result.companies[0]["company_name"] == "Acme Corp"
        assert result.companies[0]["contact_email"] == "john@acme.pt"
        assert result.companies[2]["contact_name"] is None
        # Delta's invalid email should be nullified
        assert result.companies[3]["contact_email"] is None
        assert any("invalid email" in w.lower() for w in result.warnings)
        assert not result.errors
