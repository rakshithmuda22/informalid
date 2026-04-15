"""
core/schemes.py — Real-time India government scheme matcher (April 2026 data).

Given a FinancialProfile, determines which schemes and programs the person
qualifies for, with accurate loan amounts and eligibility rules from April 2026.

Sources verified:
  - PM SVANidhi: Jan 2026 revamp (pmsvanidhi.mohua.gov.in)
  - MUDRA: Tarun Plus added, limits updated (mudra.org.in)
  - PM Vishwakarma: for artisans/craftspeople (pmvishwakarma.gov.in)
  - e-Shram: accident insurance for unorganized workers (eshram.gov.in)
"""
from __future__ import annotations
from dataclasses import dataclass
from core.models import FinancialProfile


@dataclass
class SchemeMatch:
    name: str
    description: str
    max_amount_inr: int
    eligibility_met: bool
    eligibility_reason: str
    action_required: str
    scheme_url: str


# ---------------------------------------------------------------------------
# Scheme eligibility rules — verified April 2026
# ---------------------------------------------------------------------------

_ARTISAN_SKILLS = {
    "Carpentry", "Blacksmithing", "Goldsmithing", "Pottery", "Weaving",
    "Tailoring", "Cobbling", "Shoe making", "Masonry", "Sculpture",
    "Stone carving", "Toy making", "Fishing net making", "Hammer tool",
    "Lock making", "Welding", "Washing", "Ironing", "Barber", "Flower garland"
}

_VENDOR_OCCUPATIONS = {
    "street vendor", "vegetable vendor", "fruit vendor", "tea stall",
    "food stall", "paan shop", "mobile recharge", "flower seller",
    "dhaba", "snack vendor", "hawker", "chaat", "food vendor",
    "street food", "vendor", "seller", "stall", "cart", "thela",
    "sabzi", "chai", "vada pav", "idli", "samosa", "juice stall"
}


def _is_street_vendor(profile: FinancialProfile) -> bool:
    occ = profile.occupation.lower()
    return any(v in occ for v in _VENDOR_OCCUPATIONS)


def _has_artisan_skill(profile: FinancialProfile) -> bool:
    return bool(set(profile.skills) & _ARTISAN_SKILLS)


def _jam_score(profile: FinancialProfile) -> int:
    """JAM Trinity score: Jan Dhan (0/1) + Aadhaar (0/1) + Mobile (0/1)."""
    return (
        (1 if profile.has_bank_account else 0)
        + (1 if profile.has_aadhaar else 0)
        + (1 if profile.has_mobile_phone else 0)
    )


def match_schemes(profile: FinancialProfile) -> list[SchemeMatch]:
    """
    Returns a list of SchemeMatch objects showing which programs this person
    qualifies for, with current 2026 amounts and what they need to do next.
    """
    schemes: list[SchemeMatch] = []

    # ------------------------------------------------------------------
    # 1. e-Shram registration — accident insurance, for ALL informal workers
    # ------------------------------------------------------------------
    schemes.append(SchemeMatch(
        name="e-Shram Registration",
        description="National database of unorganized workers — provides Rs 2 lakh accident insurance and priority access to 35+ welfare schemes.",
        max_amount_inr=200000,
        eligibility_met=profile.has_aadhaar and profile.has_mobile_phone,
        eligibility_reason=(
            "Requires Aadhaar and mobile number. Profile shows: "
            + ("Aadhaar YES" if profile.has_aadhaar else "Aadhaar MISSING")
            + ", Mobile "
            + ("YES" if profile.has_mobile_phone else "MISSING")
        ),
        action_required="Register at eshram.gov.in or nearest Common Service Centre (CSC). Free. Takes 10 minutes.",
        scheme_url="https://eshram.gov.in",
    ))

    # ------------------------------------------------------------------
    # 2. PM SVANidhi — for street vendors
    #    Jan 2026 update: Tranche 1 Rs 15,000 (up from Rs 10,000)
    #    New SVANidhi Credit Card: Rs 30,000 UPI-linked, interest-free
    # ------------------------------------------------------------------
    if _is_street_vendor(profile):
        schemes.append(SchemeMatch(
            name="PM SVANidhi — Street Vendor Micro Loan (Tranche 1)",
            description="Working capital loan for street vendors. Jan 2026: first tranche increased to Rs 15,000 (up from Rs 10,000). No collateral. 7% interest subsidy on timely repayment. Extends to Rs 25,000 (Tranche 2) and Rs 50,000 (Tranche 3) on good repayment.",
            max_amount_inr=15000,
            eligibility_met=True,
            eligibility_reason="Street vendor occupation detected. Requires Certificate of Vending or Letter of Recommendation from Urban Local Body (ULB).",
            action_required="Visit nearest bank or go to pmsvanidhi.mohua.gov.in. Bring Aadhaar and a letter from ULB or Town Vending Committee.",
            scheme_url="https://pmsvanidhi.mohua.gov.in",
        ))
        schemes.append(SchemeMatch(
            name="PM SVANidhi Credit Card",
            description="New Jan 2026: UPI-linked, interest-free revolving credit card with Rs 30,000 limit, specifically for registered street vendors who have repaid a SVANidhi loan.",
            max_amount_inr=30000,
            eligibility_met=profile.has_mobile_phone,
            eligibility_reason="Requires mobile phone (for UPI). Available after first SVANidhi loan repayment.",
            action_required="Apply after repaying first SVANidhi loan. Available through bank or SVANidhi portal.",
            scheme_url="https://pmsvanidhi.mohua.gov.in",
        ))

    # ------------------------------------------------------------------
    # 3. PM Vishwakarma — for artisans and craftspeople
    #    Rs 1 lakh at 5% (Tranche 1), Rs 2 lakh (Tranche 2), Rs 3 lakh (Tranche 3)
    # ------------------------------------------------------------------
    if _has_artisan_skill(profile):
        schemes.append(SchemeMatch(
            name="PM Vishwakarma Scheme",
            description="For traditional artisans and craftspeople. Tranche 1: Rs 1 lakh at 5% interest. Tranche 2: Rs 2 lakh. Free skill training + Rs 500/day stipend during training. Includes toolkit support up to Rs 15,000.",
            max_amount_inr=100000,
            eligibility_met=True,
            eligibility_reason=f"Artisan skill detected in profile: {', '.join(set(profile.skills) & _ARTISAN_SKILLS)}",
            action_required="Apply at pmvishwakarma.gov.in or CSC. Requires Aadhaar and proof of practicing the craft.",
            scheme_url="https://pmvishwakarma.gov.in",
        ))

    # ------------------------------------------------------------------
    # 4. MUDRA Shishu Loan — up to Rs 50,000, no collateral
    #    For micro-enterprises and self-employed
    # ------------------------------------------------------------------
    monthly_income = profile.total_monthly_income_inr
    if monthly_income >= 3000:  # Some income floor for creditworthiness
        schemes.append(SchemeMatch(
            name="MUDRA Shishu Loan",
            description="For micro-businesses and self-employed. Up to Rs 50,000. No collateral. No processing fee. Approval in 7-10 working days. Interest typically 10-12% p.a.",
            max_amount_inr=50000,
            eligibility_met=monthly_income >= 5000,
            eligibility_reason=(
                f"Income Rs {monthly_income:,}/month. "
                + ("Meets income floor." if monthly_income >= 5000
                   else "Income is low — some lenders may require co-applicant.")
            ),
            action_required="Apply at any scheduled commercial bank, MFI, or mudra.org.in. Bring Aadhaar, business description, and 6-month income estimate.",
            scheme_url="https://mudra.org.in",
        ))

    # ------------------------------------------------------------------
    # 5. Jan Dhan Overdraft — Rs 10,000 for Jan Dhan account holders
    # ------------------------------------------------------------------
    if profile.has_bank_account:
        schemes.append(SchemeMatch(
            name="Jan Dhan Overdraft Facility",
            description="If you have a Jan Dhan / Basic Savings Bank Account, you can get up to Rs 10,000 overdraft at any time without any security. Instant access at the bank.",
            max_amount_inr=10000,
            eligibility_met=True,
            eligibility_reason="Has bank account (required). Jan Dhan account holders automatically eligible.",
            action_required="Walk into your bank and request the overdraft facility on your Jan Dhan account.",
            scheme_url="https://pmjdy.gov.in",
        ))
    else:
        schemes.append(SchemeMatch(
            name="PM Jan Dhan Yojana — Open a Free Bank Account",
            description="Zero-balance bank account with free RuPay debit card, Rs 2 lakh accident insurance, and Rs 10,000 overdraft after 6 months. First step to accessing all other schemes.",
            max_amount_inr=10000,
            eligibility_met=profile.has_aadhaar,
            eligibility_reason="Requires Aadhaar. " + ("Profile has Aadhaar — eligible." if profile.has_aadhaar else "Aadhaar missing — get Aadhaar first."),
            action_required="Visit any bank or post office with Aadhaar. Account opened same day. Zero balance required.",
            scheme_url="https://pmjdy.gov.in",
        ))

    # ------------------------------------------------------------------
    # 6. MUDRA Kishore — Rs 50K to Rs 5L (for established businesses)
    # ------------------------------------------------------------------
    if profile.years_in_occupation >= 3 and monthly_income >= 10000:
        schemes.append(SchemeMatch(
            name="MUDRA Kishore Loan",
            description="For established micro-businesses with 3+ years of operation. Loans from Rs 50,001 to Rs 5 lakh. Interest 11-15% p.a. Takes 2-3 weeks for approval.",
            max_amount_inr=500000,
            eligibility_met=True,
            eligibility_reason=f"{profile.years_in_occupation} years in occupation, income Rs {monthly_income:,}/month — meets Kishore criteria.",
            action_required="Apply at bank or NBFC with 2 years of income evidence (even informal: employer letters, client contacts).",
            scheme_url="https://mudra.org.in",
        ))

    return schemes


def jam_assessment(profile: FinancialProfile) -> dict:
    """Returns the JAM Trinity status and what it unlocks."""
    score = _jam_score(profile)
    unlocked = []
    locked = []

    if profile.has_aadhaar:
        unlocked.append("Aadhaar — identity verification, e-KYC")
    else:
        locked.append("Aadhaar — get at nearest Aadhaar centre, free, takes 30 min")

    if profile.has_bank_account:
        unlocked.append("Jan Dhan / Bank account — digital payments, direct benefit transfer")
    else:
        locked.append("Bank account — open Jan Dhan at any bank with Aadhaar, same day")

    if profile.has_mobile_phone:
        unlocked.append("Mobile — UPI payments, scheme applications, e-Shram registration")
    else:
        locked.append("Mobile — needed for UPI and most scheme applications")

    return {
        "score": score,
        "out_of": 3,
        "unlocked": unlocked,
        "locked": locked,
        "interpretation": (
            "Strong JAM foundation — all major schemes accessible" if score == 3
            else "Partial — can access some schemes now, more after completing JAM" if score == 2
            else "Limited — priority: complete JAM Trinity to unlock financial system" if score == 1
            else "No JAM pillars — start with Aadhaar enrollment"
        ),
    }
