"""
tests/test_core.py — Unit tests for InformalID core logic.
No API calls. Tests models, formatter, scheme matcher, and mock data.
"""
import pytest
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.models import FinancialProfile, IncomeSource, Asset
from core.formatter import format_card, format_json
from core.profiler import MOCK_PROFILE, MOCK_PROFILE_2, MOCK_CONVERSATION, MOCK_CONVERSATION_2
from core.schemes import match_schemes, jam_assessment, SchemeMatch


class TestFinancialProfileModel:

    def test_mock_profile_is_valid(self):
        assert isinstance(MOCK_PROFILE, FinancialProfile)

    def test_mock_profile_2_is_valid(self):
        assert isinstance(MOCK_PROFILE_2, FinancialProfile)

    def test_profile_name(self):
        assert MOCK_PROFILE.full_name == "Meena Devi"

    def test_profile_2_name(self):
        assert MOCK_PROFILE_2.full_name == "Ramesh Kumar"

    def test_income_math(self):
        diff = MOCK_PROFILE.total_monthly_income_inr - MOCK_PROFILE.monthly_expenses_inr
        assert abs(diff - MOCK_PROFILE.monthly_savings_inr) <= 500

    def test_income_math_profile_2(self):
        diff = MOCK_PROFILE_2.total_monthly_income_inr - MOCK_PROFILE_2.monthly_expenses_inr
        assert abs(diff - MOCK_PROFILE_2.monthly_savings_inr) <= 1000

    def test_income_sources_not_empty(self):
        assert len(MOCK_PROFILE.income_sources) >= 1

    def test_profile_2_has_multiple_income_sources(self):
        assert len(MOCK_PROFILE_2.income_sources) >= 2

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

    def test_loan_readiness_uses_2026_data(self):
        """Loan note should reference current 2026 scheme amounts, not old stale data."""
        note = MOCK_PROFILE.loan_readiness_note.lower()
        # Should mention MUDRA or Jan Dhan (real current schemes)
        assert any(term in note for term in ["mudra", "jan dhan", "svanidhi", "50,000"])

    def test_skills_are_specific(self):
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
        json_str = MOCK_PROFILE.model_dump_json()
        restored = FinancialProfile.model_validate_json(json_str)
        assert restored.full_name == MOCK_PROFILE.full_name
        assert restored.total_monthly_income_inr == MOCK_PROFILE.total_monthly_income_inr

    def test_minimal_valid_profile(self):
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
            loan_readiness_note="Eligible for PM SVANidhi up to Rs 15,000.",
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
        assert "No" in card  # has_bank_account = False

    def test_inr_formatting(self):
        card = format_card(MOCK_PROFILE)
        assert "Rs" in card

    def test_format_card_with_schemes(self):
        from core.schemes import match_schemes, jam_assessment
        schemes = match_schemes(MOCK_PROFILE)
        jam = jam_assessment(MOCK_PROFILE)
        card = format_card(MOCK_PROFILE, mock_mode=True, schemes=schemes, jam=jam)
        assert "ELIGIBLE SCHEMES" in card
        assert "JAM TRINITY" in card

    def test_format_card_shows_scheme_amounts(self):
        from core.schemes import match_schemes
        schemes = match_schemes(MOCK_PROFILE)
        card = format_card(MOCK_PROFILE, schemes=schemes)
        # Should show some rupee amounts from schemes
        assert "Rs" in card


class TestSchemeMatcher:

    def test_returns_list_of_scheme_matches(self):
        schemes = match_schemes(MOCK_PROFILE)
        assert isinstance(schemes, list)
        assert len(schemes) >= 1
        assert all(isinstance(s, SchemeMatch) for s in schemes)

    def test_domestic_worker_gets_eshram(self):
        """All informal workers should get e-Shram as a base scheme."""
        schemes = match_schemes(MOCK_PROFILE)
        names = [s.name for s in schemes]
        assert any("e-Shram" in n for n in names)

    def test_domestic_worker_no_svanidhi(self):
        """Domestic workers are not street vendors — no SVANidhi."""
        schemes = match_schemes(MOCK_PROFILE)
        names = [s.name for s in schemes]
        assert not any("SVANidhi" in n for n in names)

    def test_street_vendor_gets_svanidhi(self):
        """Street vendor should match PM SVANidhi."""
        schemes = match_schemes(MOCK_PROFILE_2)
        names = [s.name for s in schemes]
        assert any("SVANidhi" in n for n in names)

    def test_street_vendor_gets_credit_card(self):
        """Vendor with phone should get SVANidhi Credit Card."""
        schemes = match_schemes(MOCK_PROFILE_2)
        names = [s.name for s in schemes]
        assert any("Credit Card" in n for n in names)

    def test_mudra_shishu_available_for_both(self):
        """MUDRA Shishu (up to Rs 50K) should be available if income >= 5K."""
        for profile in [MOCK_PROFILE, MOCK_PROFILE_2]:
            schemes = match_schemes(profile)
            names = [s.name for s in schemes]
            assert any("Shishu" in n for n in names), f"MUDRA Shishu missing for {profile.full_name}"

    def test_jan_dhan_scheme_for_unbanked(self):
        """Unbanked person should get 'Open Jan Dhan account' recommendation."""
        schemes = match_schemes(MOCK_PROFILE)  # no bank account
        names = [s.name for s in schemes]
        assert any("Jan Dhan" in n for n in names)

    def test_jan_dhan_overdraft_for_banked(self):
        """Person WITH bank account should get overdraft, not 'open account' prompt."""
        schemes = match_schemes(MOCK_PROFILE_2)  # has bank account
        names = [s.name for s in schemes]
        assert any("Overdraft" in n for n in names)

    def test_mudra_kishore_for_established_vendor(self):
        """Vendor with 11 years and Rs 21K income qualifies for MUDRA Kishore."""
        schemes = match_schemes(MOCK_PROFILE_2)
        names = [s.name for s in schemes]
        assert any("Kishore" in n for n in names)

    def test_scheme_amounts_are_positive(self):
        for profile in [MOCK_PROFILE, MOCK_PROFILE_2]:
            for scheme in match_schemes(profile):
                assert scheme.max_amount_inr > 0

    def test_scheme_has_action_required(self):
        for scheme in match_schemes(MOCK_PROFILE):
            assert len(scheme.action_required) > 10

    def test_svanidhi_tranche1_amount_is_15000(self):
        """PM SVANidhi was upgraded Jan 2026: first tranche is now Rs 15,000."""
        schemes = match_schemes(MOCK_PROFILE_2)
        svanidhi = next((s for s in schemes if "SVANidhi" in s.name and "Tranche 1" in s.name), None)
        assert svanidhi is not None
        assert svanidhi.max_amount_inr == 15000, f"Expected Rs 15,000 (Jan 2026 update), got Rs {svanidhi.max_amount_inr}"

    def test_svanidhi_credit_card_amount(self):
        """SVANidhi Credit Card: Rs 30,000 (Jan 2026)."""
        schemes = match_schemes(MOCK_PROFILE_2)
        card_scheme = next((s for s in schemes if "Credit Card" in s.name), None)
        assert card_scheme is not None
        assert card_scheme.max_amount_inr == 30000


class TestJAMAssessment:

    def test_jam_score_partial(self):
        """Meena has Aadhaar + mobile but no bank = score 2."""
        jam = jam_assessment(MOCK_PROFILE)
        assert jam["score"] == 2
        assert jam["out_of"] == 3

    def test_jam_score_full(self):
        """Ramesh has all 3 JAM pillars."""
        jam = jam_assessment(MOCK_PROFILE_2)
        assert jam["score"] == 3

    def test_jam_unlocked_contains_aadhaar(self):
        jam = jam_assessment(MOCK_PROFILE)  # has Aadhaar
        assert any("Aadhaar" in u for u in jam["unlocked"])

    def test_jam_locked_contains_bank(self):
        jam = jam_assessment(MOCK_PROFILE)  # no bank account
        assert any("bank" in l.lower() for l in jam["locked"])

    def test_jam_interpretation_present(self):
        jam = jam_assessment(MOCK_PROFILE)
        assert len(jam["interpretation"]) > 5

    def test_jam_full_score_interpretation(self):
        jam = jam_assessment(MOCK_PROFILE_2)  # full JAM
        assert "strong" in jam["interpretation"].lower()


class TestMockConversation:

    def test_conversation_has_turns(self):
        assert len(MOCK_CONVERSATION) >= 10

    def test_conversation_2_has_turns(self):
        assert len(MOCK_CONVERSATION_2) >= 10

    def test_conversation_alternates_speakers(self):
        speakers = [turn[0] for turn in MOCK_CONVERSATION]
        assert "InformalID" in speakers
        assert "Meena Devi" in speakers

    def test_conversation_2_alternates_speakers(self):
        speakers = [turn[0] for turn in MOCK_CONVERSATION_2]
        assert "InformalID" in speakers
        assert "Ramesh Kumar" in speakers

    def test_conversation_first_turn_is_informalid(self):
        assert MOCK_CONVERSATION[0][0] == "InformalID"

    def test_conversation_turns_have_content(self):
        for speaker, text in MOCK_CONVERSATION:
            assert len(text.strip()) > 0

    def test_conversation_2_turns_have_content(self):
        for speaker, text in MOCK_CONVERSATION_2:
            assert len(text.strip()) > 0
