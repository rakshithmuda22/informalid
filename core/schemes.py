"""
core/schemes.py - rules-based matcher from a FinancialProfile to Indian government schemes.

This module is plain code, not a model call: the rules are explicit, testable and auditable.
It encodes what each scheme's *published* eligibility says and flags what an officer must still
confirm (`verify`). It is a screening aid, not an eligibility decision.

Scheme facts last checked: October 2026. Sources (P = primary government source, S = secondary):
  PM SVANidhi  P  PIB 27 Aug 2025 (Cabinet restructuring: Rs 15,000 / 25,000 / 50,000 tranches, UPI-linked
                  RuPay credit card for vendors who repaid the second loan, lending to Mar 2030),
                  PIB backgrounder 30 May 2026 (card up to Rs 30,000, 7% interest subsidy, cashback up to Rs 1,600)
  PM Vishwakarma  P  PIB 20 Sep 2023 salient features (18 trades, Rs 1 lakh + Rs 2 lakh at 5%, Rs 500/day stipend,
                  toolkit up to Rs 15,000); 5-year prior-loan exclusion is S (confirm at the CSC)
  e-Shram      P  eshram.gov.in FAQs (age 16+, not ESIC/EPFO); PIB 3 Aug 2026 (31.82 crore registered, 15 schemes linked)
  PM-SYM       P  PIB 4 Mar 2025 (age 18-40, income <= Rs 15,000, Rs 3,000/month pension, 1:1 government match)
  PMJJBY, PMSBY, APY  P  PIB 9 May 2023 (age bands, Rs 436 / Rs 20 premiums, pension Rs 1,000-5,000)
  PMJDY        P  pmjdy.gov.in (zero balance, Rs 2 lakh RuPay accident cover after 28.8.2018, overdraft up to Rs 10,000);
                  S  overdraft conditions (about 6 months of satisfactory operation, age 18-65) from bank pages
  MUDRA        S  tiers Shishu <= Rs 50,000, Kishore to Rs 5 lakh, Tarun to Rs 10 lakh, Tarun Plus to Rs 20 lakh
  PM-JAY       S  Rs 5 lakh per family per year; households identified from SECC-2011
Re-check the amounts before relying on this for a real deployment: scheme parameters change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from core.models import FinancialProfile
from core.money import format_inr as inr

SCHEME_DATA_CHECKED = "October 2026"


@dataclass
class SchemeMatch:
    name: str
    description: str
    max_amount_inr: int | None   # headline credit limit or insurance cover; None when not a money amount
    eligibility_met: bool        # the profile satisfies the published criteria we can check
    eligibility_reason: str
    action_required: str
    scheme_url: str
    kind: str = "credit"         # credit | insurance | pension | banking | registration | health
    verify: str = ""             # what an officer or the scheme office must still confirm


# ---------------------------------------------------------------------------
# Occupation detection
# ---------------------------------------------------------------------------

_VENDOR_TERMS = [
    "street vendor", "vendor", "hawker", "stall", "thela", "cart", "pani puri", "chaat", "sabzi",
    "chai", "tea seller", "vegetable seller", "fruit seller", "flower seller", "food seller",
]
_VENDOR_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in _VENDOR_TERMS) + r")s?\b")

# The 18 PM Vishwakarma trades (PIB, 20 Sep 2023) mapped from the words a worker is likely to use.
_VISHWAKARMA_TRADES: dict[str, list[str]] = {
    "Carpenter": ["carpenter", "carpentry", "suthar"],
    "Boat Maker": ["boat maker", "boat making", "boat building"],
    "Armourer": ["armourer", "armorer"],
    "Blacksmith": ["blacksmith", "blacksmithing", "lohar"],
    "Hammer and Tool Kit Maker": ["hammer", "tool kit"],
    "Locksmith": ["locksmith", "lock making"],
    "Goldsmith": ["goldsmith", "goldsmithing", "sonar"],
    "Potter": ["potter", "pottery", "kumhar"],
    "Sculptor / Stone carver / Stone breaker": ["sculptor", "sculpture", "stone carving", "stone carver", "stone breaker"],
    "Cobbler / Shoesmith / Footwear artisan": ["cobbler", "cobbling", "shoe making", "shoe maker", "shoesmith", "mochi"],
    "Mason": ["mason", "masonry", "rajmistri"],
    "Basket / Mat / Broom Maker / Coir Weaver": ["basket", "mat weaving", "broom", "coir"],
    "Doll and Toy Maker": ["toy making", "toy maker", "doll making", "doll maker"],
    "Barber": ["barber", "hair cutting", "naai"],
    "Garland Maker": ["garland", "malakaar"],
    "Washerman": ["washerman", "dhobi", "laundry"],
    "Tailor": ["tailor", "tailoring", "darzi"],
    "Fishing Net Maker": ["fishing net"],
}


# Only the worker's own occupation and skills are used. Income-source descriptions can describe
# someone else in the household (a spouse's tailoring), which must not qualify the worker.

def _is_street_vendor(profile: FinancialProfile) -> bool:
    return bool(_VENDOR_RE.search(profile.occupation.lower()))


def _vishwakarma_trades(profile: FinancialProfile) -> list[str]:
    blob = " ".join([profile.occupation, *profile.skills]).lower()
    return [
        trade for trade, words in _VISHWAKARMA_TRADES.items()
        if any(re.search(r"\b" + re.escape(w) + r"\b", blob) for w in words)
    ]


def _self_employed(profile: FinancialProfile) -> bool:
    return profile.work_type in ("self_employed", "both")


def _jam_score(profile: FinancialProfile) -> int:
    """JAM Trinity score: Jan Dhan / bank account + Aadhaar + Mobile, one point each."""
    return int(profile.has_bank_account) + int(profile.has_aadhaar) + int(profile.has_mobile_phone)


def _bank_reason(fits: str, has_bank: bool, need: str = "a bank or post-office account for auto-debit") -> str:
    return f"{fits}; has a bank account." if has_bank else f"Needs {need} ({fits})."


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------

def match_schemes(profile: FinancialProfile) -> list[SchemeMatch]:
    """
    Schemes the profile is not ruled out of. `eligibility_met=True` means the checkable criteria are
    satisfied now; False means a prerequisite is missing (bank account, a repaid loan, ...) or the
    scheme's own list decides (PM-JAY). Schemes ruled out by age, income or occupation are omitted.
    """
    age = profile.age
    income = profile.total_monthly_income_inr
    bank = profile.has_bank_account
    schemes: list[SchemeMatch] = []

    # -- Registration ------------------------------------------------------
    schemes.append(SchemeMatch(
        name="e-Shram Registration",
        description=(
            "National database of unorganised workers. Gives a Universal Account Number (UAN) card and one "
            "portal to reach 15 linked schemes, including PMSBY, PMJJBY, PM-JAY, PM SVANidhi and a PM-SYM "
            "pension link (Ministry of Labour, Aug 2026)."
        ),
        max_amount_inr=None,
        eligibility_met=profile.has_aadhaar and age >= 16,
        eligibility_reason=(
            f"Unorganised worker aged {age}; "
            + ("Aadhaar present." if profile.has_aadhaar else "Aadhaar missing - needed for e-KYC.")
        ),
        action_required=(
            "Self-register at eshram.gov.in with an Aadhaar-linked mobile number, or go to a Common Service "
            "Centre (biometric Aadhaar works without one). Free."
        ),
        scheme_url="https://eshram.gov.in",
        kind="registration",
        verify="Not open to EPFO/ESIC members or income-tax payers (portal FAQs).",
    ))

    # -- Banking -----------------------------------------------------------
    if bank:
        schemes.append(SchemeMatch(
            name="Jan Dhan Overdraft Facility",
            description=(
                "Overdraft of up to Rs 10,000 for eligible PM Jan Dhan account holders, with no collateral."
            ),
            max_amount_inr=10000,
            eligibility_met=True,
            eligibility_reason="Has a bank account. The overdraft applies only if it is a PMJDY account.",
            action_required="Ask the branch about the overdraft on your Jan Dhan account.",
            scheme_url="https://pmjdy.gov.in",
            kind="credit",
            verify=(
                "Banks typically need about 6 months of satisfactory account operation, age 18-65, one "
                "overdraft per household; the first Rs 2,000 carries no conditions."
            ),
        ))
    else:
        schemes.append(SchemeMatch(
            name="PM Jan Dhan Yojana - Open a Free Bank Account",
            description=(
                "Zero-balance account with a RuPay debit card that carries Rs 2 lakh accident cover "
                "(accounts opened after 28 Aug 2018). Opens the door to the insurance and pension schemes "
                "below and, later, an overdraft of up to Rs 10,000."
            ),
            max_amount_inr=None,
            eligibility_met=True,
            eligibility_reason="No bank account yet. Open with Aadhaar or other KYC documents; no minimum balance.",
            action_required="Visit any bank branch or Bank Mitra (business correspondent) with Aadhaar.",
            scheme_url="https://pmjdy.gov.in",
            kind="banking",
            verify="Only for people who do not already hold another bank account.",
        ))

    # -- Credit ------------------------------------------------------------
    if _is_street_vendor(profile):
        schemes.append(SchemeMatch(
            name="PM SVANidhi - Street Vendor Micro Loan (Tranche 1)",
            description=(
                "Collateral-free working-capital loans of Rs 15,000, then Rs 25,000, then Rs 50,000 as each is "
                "repaid on time. 7% p.a. interest subsidy on timely repayment; digital-payment cashback up to "
                "Rs 1,600. Lending period runs to March 2030."
            ),
            max_amount_inr=15000,
            eligibility_met=True,
            eligibility_reason="Street-vending occupation detected.",
            action_required="Apply on the PM SVANidhi portal or app, or through your Urban Local Body (ULB).",
            scheme_url="https://pmsvanidhi.mohua.gov.in",
            kind="credit",
            verify="Needs a Certificate of Vending or Letter of Recommendation from the Urban Local Body.",
        ))
        schemes.append(SchemeMatch(
            name="PM SVANidhi UPI-linked RuPay Credit Card",
            description="Credit card with a limit of up to Rs 30,000 for vendors who have repaid their second SVANidhi loan.",
            max_amount_inr=30000,
            eligibility_met=False,
            eligibility_reason="Unlocks only after the second SVANidhi loan (Rs 25,000) is repaid.",
            action_required="Repay the first and second SVANidhi loans on time, then ask your bank.",
            scheme_url="https://pmsvanidhi.mohua.gov.in",
            kind="credit",
        ))

    trades = _vishwakarma_trades(profile)
    if trades and age >= 18:
        schemes.append(SchemeMatch(
            name="PM Vishwakarma Scheme",
            description=(
                "For artisans in 18 traditional trades. Collateral-free loans of Rs 1 lakh, then Rs 2 lakh "
                "(Rs 3 lakh in all) at 5% interest; skills training with a Rs 500/day stipend; toolkit "
                "incentive up to Rs 15,000."
            ),
            max_amount_inr=100000,
            eligibility_met=_self_employed(profile),
            eligibility_reason=(
                f"Trade match: {', '.join(trades)}. "
                + ("Self-employed." if _self_employed(profile) else "The scheme is for self-employed artisans; wage work does not qualify.")
            ),
            action_required="Register at a Common Service Centre with Aadhaar biometric authentication (pmvishwakarma.gov.in).",
            scheme_url="https://pmvishwakarma.gov.in",
            kind="credit",
            verify=(
                "Verified by the Gram Panchayat/ULB, a district committee and a screening committee. Reported "
                "exclusions: PMEGP, PM SVANidhi or MUDRA loans in the past 5 years, and government employees' families."
            ),
        ))

    repay = f"Income {inr(income)}/month against expenses {inr(profile.monthly_expenses_inr)}; the lender assesses repayment capacity."
    schemes.append(SchemeMatch(
        name="MUDRA Shishu Loan",
        description=(
            "Collateral-free loans up to Rs 50,000 for non-farm micro-businesses, through banks, NBFCs and "
            "MFIs. Interest rates are set by each lender."
        ),
        max_amount_inr=50000,
        eligibility_met=_self_employed(profile),
        eligibility_reason=(
            ("Runs own income-generating activity. " if _self_employed(profile)
             else "MUDRA funds a business; as a wage worker the person would need their own micro-business plan. ")
            + repay
        ),
        action_required="Apply at a bank, NBFC or MFI, or through the Udyamimitra portal. Bring Aadhaar and a short description of the business.",
        scheme_url="https://www.mudra.org.in",
        kind="credit",
    ))

    if _self_employed(profile) and profile.years_in_occupation >= 3 and income >= 10000:
        schemes.append(SchemeMatch(
            name="MUDRA Kishore Loan",
            description="The next MUDRA tier: Rs 50,001 to Rs 5 lakh, collateral-free, lender-priced.",
            max_amount_inr=500000,
            eligibility_met=True,
            eligibility_reason=(
                f"{profile.years_in_occupation} years in the trade and {inr(income)}/month of income. "
                "This 3-year / Rs 10,000 screen is this tool's heuristic, not a scheme rule."
            ),
            action_required="Ask the lender about the Kishore tier; income evidence (even informal: client or employer letters) helps.",
            scheme_url="https://www.mudra.org.in",
            kind="credit",
            verify="The lender decides loan size from business scale and repayment capacity.",
        ))

    # -- Insurance ---------------------------------------------------------
    if 18 <= age <= 70:
        schemes.append(SchemeMatch(
            name="PMSBY - Accident Insurance",
            description="Rs 2 lakh for accidental death or total disability (Rs 1 lakh partial) for Rs 20 a year, auto-debited from the bank account.",
            max_amount_inr=200000,
            eligibility_met=bank,
            eligibility_reason=_bank_reason(f"age {age} fits 18-70", bank),
            action_required="Enrol at your bank or post office (jansuraksha.gov.in). Cover runs 1 June to 31 May and renews yearly.",
            scheme_url="https://jansuraksha.gov.in",
            kind="insurance",
        ))
    if 18 <= age <= 50:
        schemes.append(SchemeMatch(
            name="PMJJBY - Life Insurance",
            description="Rs 2 lakh life cover for Rs 436 a year, auto-debited. Joining before 50 allows renewal up to age 55.",
            max_amount_inr=200000,
            eligibility_met=bank,
            eligibility_reason=_bank_reason(f"age {age} fits 18-50", bank),
            action_required="Enrol at your bank or post office (jansuraksha.gov.in). Cover runs 1 June to 31 May and renews yearly.",
            scheme_url="https://jansuraksha.gov.in",
            kind="insurance",
        ))

    # -- Pensions ----------------------------------------------------------
    if 18 <= age <= 40 and income <= 15000:
        schemes.append(SchemeMatch(
            name="PM-SYM - Shram Yogi Maan-dhan Pension",
            description="Rs 3,000 a month pension from age 60. The worker pays Rs 55-200 a month by entry age and the Government matches it 1:1.",
            max_amount_inr=None,
            eligibility_met=bank and profile.has_aadhaar,
            eligibility_reason=(
                f"Age {age} fits 18-40 and income {inr(income)} is within the Rs 15,000 limit; "
                + ("has the bank account and Aadhaar needed for auto-debit."
                   if bank and profile.has_aadhaar else "needs a savings or Jan Dhan account and Aadhaar first.")
            ),
            action_required="Enrol at a Common Service Centre with Aadhaar and a bank passbook, or at maandhan.in.",
            scheme_url="https://maandhan.in",
            kind="pension",
            verify="Not for EPFO/ESIC/NPS members, income-tax payers or people on another government pension. Pick PM-SYM or APY, not both.",
        ))
    if 18 <= age <= 40:
        schemes.append(SchemeMatch(
            name="APY - Atal Pension Yojana",
            description="Guaranteed pension of Rs 1,000-5,000 a month (your choice) from age 60; the contribution depends on entry age and the pension chosen.",
            max_amount_inr=None,
            eligibility_met=bank,
            eligibility_reason=_bank_reason(f"age {age} fits 18-40", bank, "a savings bank or post-office account"),
            action_required="Enrol at your bank or post office (jansuraksha.gov.in).",
            scheme_url="https://jansuraksha.gov.in",
            kind="pension",
            verify="Not open to income-tax payers. Pick APY or PM-SYM, not both.",
        ))

    # -- Health ------------------------------------------------------------
    schemes.append(SchemeMatch(
        name="PM-JAY (Ayushman Bharat) - Health Cover",
        description="Cashless hospital cover of up to Rs 5 lakh per family per year at empanelled hospitals.",
        max_amount_inr=500000,
        eligibility_met=False,
        eligibility_reason=(
            "Eligibility comes from the household lists (SECC-2011 deprivation and occupation criteria), "
            "which an interview cannot establish."
        ),
        action_required="Check by mobile number or Aadhaar under 'Am I Eligible' at pmjay.gov.in, or ask a Common Service Centre.",
        scheme_url="https://pmjay.gov.in",
        kind="health",
        verify="Check the household against the PM-JAY beneficiary list.",
    ))

    order = {"registration": 0, "banking": 1, "credit": 2, "insurance": 3, "pension": 4, "health": 5}
    return sorted(schemes, key=lambda s: order[s.kind])  # stable: keeps insertion order within a kind


def unlocked_by_bank_account(profile: FinancialProfile) -> list[str]:
    """Names of schemes that move from 'not yet' to 'likely eligible' once the worker has a bank account."""
    if profile.has_bank_account:
        return []
    now = {s.name for s in match_schemes(profile) if s.eligibility_met}
    after = match_schemes(profile.model_copy(update={"has_bank_account": True}))
    return [s.name for s in after if s.eligibility_met and s.name not in now and s.kind != "credit"]


def jam_assessment(profile: FinancialProfile) -> dict:
    """Returns the JAM Trinity (Jan Dhan, Aadhaar, Mobile) status and what it unlocks."""
    score = _jam_score(profile)
    unlocked: list[str] = []
    locked: list[str] = []

    if profile.has_aadhaar:
        unlocked.append("Aadhaar - identity verification, e-KYC")
    else:
        locked.append("Aadhaar - enrol at an Aadhaar centre; most schemes need it")

    if profile.has_bank_account:
        unlocked.append("Bank / Jan Dhan account - direct benefit transfers, insurance and pension auto-debit")
    else:
        locked.append("Bank account - open a Jan Dhan account with Aadhaar; insurance and pensions need it")

    if profile.has_mobile_phone:
        unlocked.append("Mobile - UPI payments, scheme applications, e-Shram registration")
    else:
        locked.append("Mobile - needed for UPI and most online scheme applications")

    return {
        "score": score,
        "out_of": 3,
        "unlocked": unlocked,
        "locked": locked,
        "interpretation": (
            "Strong JAM foundation - all major schemes accessible" if score == 3
            else "Partial - can access some schemes now, more after completing JAM" if score == 2
            else "Limited - priority: complete JAM Trinity to unlock financial system" if score == 1
            else "No JAM pillars - start with Aadhaar enrollment"
        ),
    }
