import json

import pytest

from core.formatter import format_card, format_json
from core.mock import MEENA, RAMESH
from core.money import format_inr
from core.schemes import jam_assessment, match_schemes


@pytest.mark.parametrize("amount,text", [
    (0, "Rs 0"), (999, "Rs 999"), (1000, "Rs 1,000"), (9000, "Rs 9,000"), (15000, "Rs 15,000"),
    (100000, "Rs 1,00,000"), (500000, "Rs 5,00,000"), (12345678, "Rs 1,23,45,678"), (-2500, "-Rs 2,500"),
])
def test_indian_digit_grouping(amount, text):
    assert format_inr(amount) == text


def card(persona, **kw):
    p = persona.profile
    return format_card(p, mock_mode=kw.get("mock", True), schemes=match_schemes(p), jam=jam_assessment(p))


def test_card_contains_core_fields():
    text = card(MEENA)
    for needle in ("INFORMALID", "Meena Devi", "Rs 9,000", "JAM TRINITY SCORE", "LIKELY ELIGIBLE SCHEMES",
                   "AFTER PREREQUISITES", "NOT a credit score", "Opening a bank account would unlock"):
        assert needle in text, needle


def test_demo_banner_only_in_mock_mode():
    assert "DEMO MODE" in card(MEENA, mock=True)
    assert "DEMO MODE" not in card(MEENA, mock=False)


def test_card_without_schemes_still_renders():
    text = format_card(MEENA.profile)
    assert "LIKELY ELIGIBLE" not in text and "Meena Devi" in text


def test_card_shows_scheme_names_amounts_and_confirm_lines():
    text = card(RAMESH)
    assert "PM SVANidhi - Street Vendor Micro Loan (Tranche 1) - up to Rs 15,000" in text
    assert "Confirm:" in text and "Certificate of Vending" in text
    assert "Rs 5,00,000" in text


def test_unbanked_card_shows_no_account():
    assert "Bank account:     No" in card(MEENA)
    assert "Bank account:     Yes" in card(RAMESH)


def test_json_output_is_valid_and_complete():
    parsed = json.loads(format_json(MEENA.profile))
    assert parsed["full_name"] == "Meena Devi" and parsed["work_type"] == "wage_worker"
    assert len(parsed["income_sources"]) == 1
