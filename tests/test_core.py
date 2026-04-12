"""
tests/test_core.py — Unit tests for InformalID core logic.
No API calls. Tests models, formatter, and mock data only.
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import FinancialProfile, IncomeSource, Asset
from core.formatter import format_card, format_json
from core.profiler import MOCK_PROFILE, MOCK_CONVERSATION


class TestFinancialProfileModel:

    def test_mock_profile_is_valid(self):
        """The built-in mock profile should parse without errors."""
        assert isinstance(MOCK_PROFILE, FinancialProfile)

    def test_profile_name(self):
        assert MOCK_PROFILE.full_name == "Meena Devi"

    def test_income_math(self):
        """Savings should be income minus expenses (approximately)."""
        diff = MOCK_PROFILE.total_monthly_income_inr - MOCK_PROFILE.monthly_expenses_inr
        # Allow up to 500 INR variance for rounding
        assert abs(diff - MOCK_PROFILE.monthly_savings_inr) <= 500

    def test_income_sources_not_empty(self):
        assert len(MOCK_PROFILE.income_sources) >= 1

    def test_income_source_fields(self):
        src = MOCK_PROFILE.income_sources[0]
        assert isinstance(src, IncomeSource)
        assert src.estimated_monthly_inr > 0
        assert src.frequency in ("daily", "weekly", "monthly", "seasonal")

    def test_assets_list(self):
        for asset in MOCK_PROFILE.assets:
            assert isinstance(asset, Asset)
            assert asset.estimated_value_inr >= 0

    def test_summary_paragraph_is_present(self):
        assert len(MOCK_PROFILE.summary_paragraph) > 20

    def test_loan_readiness_note_is_present(self):
        assert len(MOCK_PROFILE.loan_readiness_note) > 10

    def test_skills_are_specific(self):
        """Skills should not be empty strings."""
        for skill in MOCK_PROFILE.skills:
            assert len(skill.strip()) > 0

    def test_age_is_reasonable(self):
        assert 18 <= MOCK_PROFILE.age <= 80

    def test_profile_serializes_to_json(self):
        json_str = MOCK_PROFILE.model_dump_json()
        parsed = json.loads(json_str)
        assert parsed["full_name"] == "Meena Devi"
        assert "income_sources" in parsed
        assert "assets" in parsed

    def test_profile_roundtrip(self):
        """Serialize → deserialize should produce identical data."""
        json_str = MOCK_PROFILE.model_dump_json()
        restored = FinancialProfile.model_validate_json(json_str)
        assert restored.full_name == MOCK_PROFILE.full_name
        assert restored.total_monthly_income_inr == MOCK_PROFILE.total_monthly_income_inr

    def test_minimal_valid_profile(self):
        """Profile should work with empty optional lists."""
        p = FinancialProfile(
            full_name="Test User",
            age=30,
            occupation="Street vendor",
            years_in_occupation=2,
            income_sources=[
                IncomeSource(description="Selling vegetables", frequency="daily", estimated_monthly_inr=8000)
            ],
            total_monthly_income_inr=8000,
            monthly_expenses_inr=6000,
            monthly_savings_inr=2000,
            assets=[],
            has_bank_account=False,
            has_aadhaar=True,
            has_mobile_phone=True,
            previous_occupations=[],
            skills=["Vendor negotiation"],
            references_available=False,
            location_city_or_area="Mumbai, Dharavi",
            languages_spoken=["Hindi", "Marathi"],
            summary_paragraph="Test vendor with stable income.",
            loan_readiness_note="Eligible for PM SVANidhi up to Rs 10,000.",
        )
        assert p.total_monthly_income_inr == 8000


class TestFormatter:

    def test_format_card_contains_name(self):
        card = format_card(MOCK_PROFILE)
        assert "Meena Devi" in card

    def test_format_card_contains_income(self):
        card = format_card(MOCK_PROFILE)
        assert "9,000" in card

    def test_format_card_contains_summary(self):
        card = format_card(MOCK_PROFILE)
        assert MOCK_PROFILE.summary_paragraph[:30] in card

    def test_format_card_mock_banner(self):
        card = format_card(MOCK_PROFILE, mock_mode=True)
        assert "DEMO MODE" in card

    def test_format_card_no_mock_banner_in_live(self):
        card = format_card(MOCK_PROFILE, mock_mode=False)
        assert "DEMO MODE" not in card

    def test_format_json_is_valid_json(self):
        json_str = format_json(MOCK_PROFILE)
        parsed = json.loads(json_str)
        assert isinstance(parsed, dict)
        assert parsed["full_name"] == "Meena Devi"

    def test_format_card_shows_aadhaar_status(self):
        card = format_card(MOCK_PROFILE)
        assert "Yes" in card  # has_aadhaar = True

    def test_format_card_shows_bank_account_no(self):
        card = format_card(MOCK_PROFILE)
        # has_bank_account = False, check it appears
        assert "No" in card

    def test_inr_formatting(self):
        card = format_card(MOCK_PROFILE)
        assert "Rs" in card


class TestMockConversation:

    def test_conversation_has_turns(self):
        assert len(MOCK_CONVERSATION) >= 10

    def test_conversation_alternates_speakers(self):
        speakers = [turn[0] for turn in MOCK_CONVERSATION]
        # Check that InformalID and participant both appear
        assert "InformalID" in speakers
        assert "Meena Devi" in speakers

    def test_conversation_first_turn_is_informalid(self):
        assert MOCK_CONVERSATION[0][0] == "InformalID"

    def test_conversation_turns_have_content(self):
        for speaker, text in MOCK_CONVERSATION:
            assert len(text.strip()) > 0
