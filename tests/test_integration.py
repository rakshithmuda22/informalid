"""
tests/test_integration.py — Integration tests for full InformalID pipeline.
No API calls. Tests profiler → formatter → schemes pipeline end-to-end.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.profiler import run_profiler, MOCK_PROFILE, MOCK_PROFILE_2
from core.formatter import format_card, format_json
from core.schemes import match_schemes, jam_assessment


def test_full_pipeline_domestic_worker():
    """Run full mock pipeline for domestic worker persona."""
    os.environ["INFORMALID_MODE"] = "mock"
    import importlib
    import config
    importlib.reload(config)

    conversation, profile = run_profiler(persona="domestic_worker")
    schemes = match_schemes(profile)
    jam = jam_assessment(profile)
    card = format_card(profile, mock_mode=True, schemes=schemes, jam=jam)
    json_output = format_json(profile)

    assert len(conversation) >= 10
    assert "INFORMALID" in card
    assert "DEMO MODE" in card
    assert "JAM TRINITY" in card
    assert "ELIGIBLE SCHEMES" in card
    assert profile.total_monthly_income_inr > 0

    parsed = json.loads(json_output)
    assert "full_name" in parsed
    assert len(schemes) >= 2


def test_full_pipeline_street_vendor():
    """Run full mock pipeline for street vendor persona."""
    os.environ["INFORMALID_MODE"] = "mock"
    import importlib
    import config
    importlib.reload(config)

    conversation, profile = run_profiler(persona="street_vendor")
    schemes = match_schemes(profile)
    jam = jam_assessment(profile)
    card = format_card(profile, mock_mode=True, schemes=schemes, jam=jam)

    assert "Ramesh Kumar" in card
    assert any("SVANidhi" in s.name for s in schemes)
    assert jam["score"] == 3  # Full JAM


def test_scheme_data_is_2026_accurate():
    """Verify scheme amounts match April 2026 government data."""
    schemes = match_schemes(MOCK_PROFILE_2)  # street vendor with full JAM

    # PM SVANidhi Tranche 1: Rs 15,000 (upgraded Jan 2026 from Rs 10,000)
    svanidhi_t1 = next((s for s in schemes if "SVANidhi" in s.name and "Tranche 1" in s.name), None)
    assert svanidhi_t1 is not None, "SVANidhi Tranche 1 should match for street vendor"
    assert svanidhi_t1.max_amount_inr == 15000, "Jan 2026 upgrade: SVANidhi T1 = Rs 15,000"

    # SVANidhi Credit Card: Rs 30,000 (new Jan 2026)
    credit_card = next((s for s in schemes if "Credit Card" in s.name), None)
    assert credit_card is not None, "SVANidhi Credit Card should match for vendor with mobile"
    assert credit_card.max_amount_inr == 30000, "SVANidhi Credit Card = Rs 30,000"

    # MUDRA Shishu: Rs 50,000
    mudra = next((s for s in schemes if "Shishu" in s.name), None)
    assert mudra is not None
    assert mudra.max_amount_inr == 50000


def test_profile_values_are_internally_consistent():
    """Income - expenses should be close to savings for both profiles."""
    for profile in [MOCK_PROFILE, MOCK_PROFILE_2]:
        gap = profile.total_monthly_income_inr - profile.monthly_expenses_inr
        assert abs(gap - profile.monthly_savings_inr) <= 1000, (
            f"{profile.full_name}: income - expenses = {gap}, savings = {profile.monthly_savings_inr}"
        )


def test_jam_gates_scheme_eligibility():
    """JAM status should affect which schemes are flagged as eligible vs not."""
    # MOCK_PROFILE: no bank account → Jan Dhan 'open account' should be suggested
    # MOCK_PROFILE_2: has bank → Jan Dhan overdraft should be available
    schemes_1 = match_schemes(MOCK_PROFILE)
    schemes_2 = match_schemes(MOCK_PROFILE_2)

    open_account = next((s for s in schemes_1 if "Open" in s.name and "Jan Dhan" in s.name), None)
    overdraft = next((s for s in schemes_2 if "Overdraft" in s.name), None)

    assert open_account is not None, "Unbanked person should get Jan Dhan account recommendation"
    assert open_account.eligibility_met is True  # Meena has Aadhaar so eligible to open
    assert overdraft is not None, "Banked person should get overdraft scheme"
    assert overdraft.eligibility_met is True


def test_all_schemes_have_required_fields():
    """Every scheme must have non-empty action_required and valid amount."""
    for profile in [MOCK_PROFILE, MOCK_PROFILE_2]:
        for scheme in match_schemes(profile):
            assert scheme.name, "Scheme must have name"
            assert scheme.description, "Scheme must have description"
            assert scheme.max_amount_inr > 0, f"{scheme.name}: amount must be positive"
            assert len(scheme.action_required) > 10, f"{scheme.name}: action_required too short"
            assert scheme.scheme_url.startswith("https://"), f"{scheme.name}: invalid URL"
