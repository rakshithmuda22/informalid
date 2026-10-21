"""Scheme matcher: the published rules, boundary by boundary."""
import re

import pytest

from core.mock import MEENA, RAMESH
from core.schemes import (
    _is_street_vendor,
    _vishwakarma_trades,
    jam_assessment,
    match_schemes,
    unlocked_by_bank_account,
)

OFFICIAL_URL = re.compile(
    r"^https://(www\.)?(eshram\.gov\.in|pmsvanidhi\.mohua\.gov\.in|pmvishwakarma\.gov\.in|mudra\.org\.in|"
    r"pmjdy\.gov\.in|maandhan\.in|jansuraksha\.gov\.in|pmjay\.gov\.in)/?$"
)


def person(base=MEENA, **changes):
    return base.profile.model_copy(update=changes)


def by_name(schemes, fragment):
    return next((s for s in schemes if fragment in s.name), None)


# -- the two personas --------------------------------------------------------

def test_domestic_worker_without_bank_account():
    schemes = match_schemes(MEENA.profile)
    assert by_name(schemes, "e-Shram").eligibility_met
    assert by_name(schemes, "Open a Free Bank Account").eligibility_met
    assert not any("SVANidhi" in s.name or "Vishwakarma" in s.name for s in schemes)
    for fragment in ("PMSBY", "PMJJBY", "PM-SYM", "APY"):
        assert not by_name(schemes, fragment).eligibility_met, fragment  # all need the bank account


def test_wage_worker_is_not_matched_to_mudra():
    mudra = by_name(match_schemes(MEENA.profile), "Shishu")
    assert mudra is not None and not mudra.eligibility_met
    assert by_name(match_schemes(MEENA.profile), "Kishore") is None


def test_street_vendor_gets_svanidhi_ladder_and_mudra():
    schemes = match_schemes(RAMESH.profile)
    t1 = by_name(schemes, "Tranche 1")
    assert t1.max_amount_inr == 15000 and t1.eligibility_met
    assert "Rs 25,000" in t1.description and "Rs 50,000" in t1.description
    assert by_name(schemes, "Shishu").max_amount_inr == 50000
    assert by_name(schemes, "Kishore").eligibility_met
    assert by_name(schemes, "Overdraft").max_amount_inr == 10000


def test_vendor_not_matched_to_vishwakarma_by_spouse_trade():
    # RAMESH's wife tailors, which is an income source, not his trade.
    assert by_name(match_schemes(RAMESH.profile), "Vishwakarma") is None


def test_svanidhi_credit_card_waits_for_second_loan():
    card = by_name(match_schemes(RAMESH.profile), "Credit Card")
    assert card.max_amount_inr == 30000
    assert not card.eligibility_met
    assert "second" in card.eligibility_reason


def test_pm_jay_is_never_asserted_from_an_interview():
    jay = by_name(match_schemes(RAMESH.profile), "PM-JAY")
    assert jay.max_amount_inr == 500000 and not jay.eligibility_met and jay.verify


# -- age and income boundaries --------------------------------------------------

@pytest.mark.parametrize("age,expected", [(15, False), (16, True)])
def test_eshram_minimum_age(age, expected):
    assert by_name(match_schemes(person(age=age)), "e-Shram").eligibility_met is expected


@pytest.mark.parametrize("age,listed", [(17, False), (18, True), (40, True), (41, False)])
def test_apy_age_band(age, listed):
    assert (by_name(match_schemes(person(RAMESH, age=age)), "APY") is not None) is listed


@pytest.mark.parametrize("age,listed", [(17, False), (18, True), (50, True), (51, False)])
def test_pmjjby_age_band(age, listed):
    assert (by_name(match_schemes(person(RAMESH, age=age)), "PMJJBY") is not None) is listed


@pytest.mark.parametrize("age,listed", [(17, False), (18, True), (70, True), (71, False)])
def test_pmsby_age_band(age, listed):
    assert (by_name(match_schemes(person(RAMESH, age=age)), "PMSBY") is not None) is listed


@pytest.mark.parametrize("age,income,listed", [
    (30, 15000, True), (30, 15001, False), (18, 5000, True), (17, 5000, False), (40, 5000, True), (41, 5000, False),
])
def test_pm_sym_rules(age, income, listed):
    p = person(RAMESH, age=age, total_monthly_income_inr=income, monthly_savings_inr=0)
    assert (by_name(match_schemes(p), "PM-SYM") is not None) is listed


def test_pm_sym_and_insurance_unlock_with_a_bank_account():
    banked = person(has_bank_account=True)
    for fragment in ("PMSBY", "PMJJBY", "PM-SYM", "APY"):
        assert by_name(match_schemes(banked), fragment).eligibility_met, fragment
    assert set(unlocked_by_bank_account(MEENA.profile)) == {s.name for s in match_schemes(banked)
                                                            if s.kind in ("insurance", "pension")}
    assert unlocked_by_bank_account(RAMESH.profile) == []


def test_jan_dhan_overdraft_only_with_account():
    assert by_name(match_schemes(RAMESH.profile), "Overdraft")
    assert by_name(match_schemes(MEENA.profile), "Overdraft") is None


# -- occupation detection ---------------------------------------------------------

@pytest.mark.parametrize("occupation,expected", [
    ("Street food vendor (chaat stall)", True),
    ("Vegetable seller with a thela", True),
    ("Tea stall owner", True),
    ("Flower seller", True),
    ("Chair repair", False),        # 'chai' must not match inside 'chair'
    ("Cartographer", False),        # 'cart' must not match inside 'cartographer'
    ("Domestic worker", False),
])
def test_street_vendor_detection(occupation, expected):
    assert _is_street_vendor(person(occupation=occupation)) is expected


@pytest.mark.parametrize("skills,occupation,trade", [
    (["Tailoring"], "Tailor", "Tailor"),
    (["Carpentry"], "Odd jobs", "Carpenter"),
    (["Pottery"], "Odd jobs", "Potter"),
    ([], "Barber", "Barber"),
    (["Stone carving"], "Odd jobs", "Sculptor"),
])
def test_vishwakarma_trade_matching(skills, occupation, trade):
    trades = _vishwakarma_trades(person(skills=skills, occupation=occupation))
    assert any(t.startswith(trade) for t in trades)


@pytest.mark.parametrize("skill", ["Welding", "Cooking", "Weaving", "Cleaning"])
def test_non_listed_skills_do_not_match_vishwakarma(skill):
    assert _vishwakarma_trades(person(skills=[skill], occupation="Odd jobs")) == []


def test_vishwakarma_requires_self_employment():
    tailor = dict(skills=["Tailoring"], occupation="Tailor", age=30)
    own = by_name(match_schemes(person(work_type="self_employed", **tailor)), "Vishwakarma")
    wage = by_name(match_schemes(person(work_type="wage_worker", **tailor)), "Vishwakarma")
    assert own.eligibility_met and not wage.eligibility_met
    assert "Rs 2 lakh" in own.description and "Rs 3 lakh" in own.description and "Tranche 3" not in own.description


# -- hygiene ----------------------------------------------------------------------

@pytest.mark.parametrize("persona", [MEENA, RAMESH])
def test_every_scheme_has_complete_fields_and_an_official_url(persona):
    for s in match_schemes(persona.profile):
        assert s.name and s.description and len(s.action_required) > 10, s.name
        assert s.max_amount_inr is None or s.max_amount_inr > 0, s.name
        assert OFFICIAL_URL.match(s.scheme_url), (s.name, s.scheme_url)
        assert s.kind in {"credit", "insurance", "pension", "banking", "registration", "health"}


def test_no_stale_or_unverified_claims_in_scheme_text():
    text = " ".join(f"{s.name} {s.description} {s.eligibility_reason} {s.action_required} {s.verify}"
                    for p in (MEENA, RAMESH) for s in match_schemes(p.profile)).lower()
    for stale in ("interest-free", "35+ welfare", "jan 2026", "instantly", "approval in 7-10"):
        assert stale not in text, stale


# -- JAM ------------------------------------------------------------------------------

def test_jam_scores():
    assert jam_assessment(MEENA.profile)["score"] == 2
    assert jam_assessment(RAMESH.profile)["score"] == 3
    assert "strong" in jam_assessment(RAMESH.profile)["interpretation"].lower()
    assert any("bank" in item.lower() for item in jam_assessment(MEENA.profile)["locked"])
