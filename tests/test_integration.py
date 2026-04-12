"""
tests/test_integration.py — Integration test for the full mock pipeline.
Runs the complete profiler → formatter pipeline without an API key.
"""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_full_mock_pipeline():
    """Run profiler in mock mode, verify the output card is non-empty."""
    os.environ["INFORMALID_MODE"] = "mock"
    # Re-import config so mode is picked up
    import importlib
    import config
    importlib.reload(config)

    from core.profiler import run_profiler
    from core.formatter import format_card, format_json

    conversation, profile = run_profiler()
    card = format_card(profile, mock_mode=True)
    json_output = format_json(profile)

    assert len(conversation) >= 10
    assert "INFORMALID" in card
    assert "DEMO MODE" in card
    assert profile.total_monthly_income_inr > 0

    parsed = json.loads(json_output)
    assert "full_name" in parsed
    assert "income_sources" in parsed
    assert len(parsed["income_sources"]) >= 1


def test_profile_values_are_internally_consistent():
    """Income - expenses should be close to savings."""
    from core.profiler import MOCK_PROFILE
    gap = MOCK_PROFILE.total_monthly_income_inr - MOCK_PROFILE.monthly_expenses_inr
    assert abs(gap - MOCK_PROFILE.monthly_savings_inr) <= 1000, (
        f"Income {MOCK_PROFILE.total_monthly_income_inr} - "
        f"expenses {MOCK_PROFILE.monthly_expenses_inr} = {gap}, "
        f"but savings is {MOCK_PROFILE.monthly_savings_inr}"
    )
