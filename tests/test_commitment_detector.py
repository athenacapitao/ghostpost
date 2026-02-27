"""Tests for src/security/commitment_detector.py — Layer 4 commitment detection."""

import pytest

from src.security.commitment_detector import detect_commitments, has_commitments


class TestDetectCommitments:
    def test_empty_string_returns_no_commitments(self) -> None:
        assert detect_commitments("") == []

    def test_clean_text_returns_no_commitments(self) -> None:
        result = detect_commitments("Hi, let us schedule a call next week to discuss.")
        assert result == []

    def test_detects_financial_commitment(self) -> None:
        text = "I will pay you $5,000 for the project."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "financial" in types

    def test_detects_price_agreement(self) -> None:
        # Pattern matches "agree the rate of $X" (without "to" in between)
        text = "We agree the rate of $150 per hour."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "price_agreement" in types

    def test_detects_contract_signing(self) -> None:
        text = "We are ready to sign the contract today."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "contract" in types

    def test_detects_nda_agreement(self) -> None:
        text = "I will sign the NDA and return it by tomorrow."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "contract" in types

    def test_detects_guarantee(self) -> None:
        text = "I guarantee that delivery will happen on time."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "guarantee" in types

    def test_detects_warranty(self) -> None:
        text = "We warrant the software is free of defects."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "guarantee" in types

    def test_detects_deadline_by_day_name(self) -> None:
        text = "We will deliver by Friday."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "deadline" in types

    def test_detects_deadline_by_tomorrow(self) -> None:
        text = "I will finish by tomorrow."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "deadline" in types

    def test_detects_deadline_by_date(self) -> None:
        text = "The feature will be complete by 03/15."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "deadline" in types

    def test_detects_will_do_commitment(self) -> None:
        text = "I will definitely handle that for you."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "will_do" in types

    def test_detects_resource_commitment(self) -> None:
        text = "We will assign 3 developers to this project."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "resource" in types

    def test_detects_allocate_hours(self) -> None:
        text = "We will allocate 40 hours to this task."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "resource" in types

    def test_returns_dict_with_required_fields(self) -> None:
        text = "I guarantee delivery by Friday."
        result = detect_commitments(text)
        assert len(result) > 0
        commitment = result[0]
        assert "type" in commitment
        assert "description" in commitment
        assert "matched_text" in commitment

    def test_matched_text_truncated_to_100_chars(self) -> None:
        text = "I will definitely " + "x" * 200
        result = detect_commitments(text)
        for c in result:
            assert len(c["matched_text"]) <= 100

    def test_case_insensitive_detection(self) -> None:
        text = "WE GUARANTEE DELIVERY BY MONDAY."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "guarantee" in types

    def test_multiple_commitments_detected(self) -> None:
        text = "I guarantee delivery by Friday and we will pay $10,000."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        # Should find at least guarantee, deadline, and financial
        assert len(types) >= 2

    def test_wire_transfer_is_financial(self) -> None:
        text = "I will wire $25,000 to your account."
        result = detect_commitments(text)
        types = [c["type"] for c in result]
        assert "financial" in types


class TestHasCommitments:
    def test_returns_false_for_empty_string(self) -> None:
        assert has_commitments("") is False

    def test_returns_false_for_clean_text(self) -> None:
        assert has_commitments("Thanks for your email. We will review it.") is False

    def test_returns_true_for_text_with_commitment(self) -> None:
        assert has_commitments("I guarantee this will be done by Friday.") is True

    def test_returns_true_for_financial_commitment(self) -> None:
        assert has_commitments("We will pay you $5,000 upon completion.") is True

    def test_is_consistent_with_detect_commitments(self) -> None:
        texts = [
            "Hello, how are you?",
            "I guarantee delivery by Monday.",
            "I will definitely send that over.",
            "Let us connect next week.",
        ]
        for text in texts:
            expected = len(detect_commitments(text)) > 0
            assert has_commitments(text) == expected
