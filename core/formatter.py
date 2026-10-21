"""
core/formatter.py - renders a FinancialProfile (plus scheme matches) as a terminal card or JSON.
No API calls; pure string formatting.
"""
from __future__ import annotations

import textwrap
from datetime import date

from core.models import FinancialProfile
from core.money import format_inr as fmt_inr
from core.schemes import SCHEME_DATA_CHECKED, SchemeMatch, unlocked_by_bank_account

WIDTH = 64
BORDER = "=" * WIDTH
THIN = "-" * WIDTH


def _wrap(text: str, indent: int = 4) -> str:
    pad = " " * indent
    return textwrap.fill(text, width=WIDTH + 4, initial_indent=pad, subsequent_indent=pad, break_on_hyphens=False)


def _yes_no(flag: bool) -> str:
    return "Yes" if flag else "No"


def _scheme_block(scheme: SchemeMatch, eligible: bool) -> str:
    amount = f" - up to {fmt_inr(scheme.max_amount_inr)}" if scheme.max_amount_inr else ""
    if not eligible:
        return f"\n  ○ {scheme.name}{amount}\n{_wrap('Why not yet: ' + scheme.eligibility_reason)}\n"
    lines = [f"\n  ✓ {scheme.name}{amount}", _wrap(scheme.description), _wrap("Next: " + scheme.action_required)]
    if scheme.verify:
        lines.append(_wrap("Confirm: " + scheme.verify))
    return "\n".join(lines) + "\n"


def format_card(
    profile: FinancialProfile,
    mock_mode: bool = False,
    schemes: list[SchemeMatch] | None = None,
    jam: dict | None = None,
) -> str:
    """Returns the financial identity card as a string."""
    income_lines = "\n".join(
        f"    • {src.description} ({src.frequency}) - {fmt_inr(src.estimated_monthly_inr)}/mo"
        for src in profile.income_sources
    )
    asset_lines = "\n".join(
        f"    • {a.item} (est. {fmt_inr(a.estimated_value_inr)})" for a in profile.assets
    ) or "    • None reported"
    skills = ", ".join(profile.skills) or "Not specified"
    previous = ", ".join(profile.previous_occupations) or "None"
    languages = ", ".join(profile.languages_spoken)

    banner = ""
    if mock_mode:
        banner = (
            "\n  [DEMO MODE - offline: scripted worker answers and scripted extraction, no API call]\n"
            "  [Set ANTHROPIC_API_KEY in .env to run a real interview]\n"
        )

    jam_section = ""
    if jam:
        icon = "✓" if jam["score"] == 3 else ("~" if jam["score"] >= 1 else "✗")
        jam_section = f"\n  JAM TRINITY SCORE: {icon} {jam['score']}/3 - {jam['interpretation']}\n"
        if jam["unlocked"]:
            jam_section += "  Unlocked:\n" + "".join(f"    [✓] {item}\n" for item in jam["unlocked"])
        if jam["locked"]:
            jam_section += "  Next steps:\n" + "".join(f"    [ ] {item}\n" for item in jam["locked"])

    schemes_section = ""
    if schemes:
        ready = [s for s in schemes if s.eligibility_met]
        later = [s for s in schemes if not s.eligibility_met]
        schemes_section = f"\n  LIKELY ELIGIBLE SCHEMES ({len(ready)}) - confirm the flagged items\n  {THIN}\n"
        schemes_section += "".join(_scheme_block(s, True) for s in ready) or "\n    None yet.\n"
        if later:
            schemes_section += f"\n  AFTER PREREQUISITES / TO VERIFY ({len(later)})\n  {THIN}"
            schemes_section += "".join(_scheme_block(s, False) for s in later)
        unlocked = unlocked_by_bank_account(profile)
        if unlocked:
            schemes_section += "\n" + _wrap("Opening a bank account would unlock: " + "; ".join(unlocked) + ".", 2) + "\n"
        schemes_section += f"\n  Scheme rules checked {SCHEME_DATA_CHECKED}; see core/schemes.py for sources.\n"

    return f"""
{BORDER}
  INFORMALID - FINANCIAL IDENTITY CARD
  Generated: {date.today().isoformat()}  |  Method: AI Conversational Interview
{BORDER}{banner}
  PERSONAL INFORMATION
  {THIN}
  Name:             {profile.full_name}
  Age:              {profile.age} years
  Location:         {profile.location_city_or_area}
  Occupation:       {profile.occupation}
  Years in work:    {profile.years_in_occupation} years
  Work type:        {profile.work_type.replace('_', ' ')}
  Languages:        {languages}
{jam_section}
  INCOME
  {THIN}
  Sources:
{income_lines}

  Total monthly income:   {fmt_inr(profile.total_monthly_income_inr)}
  Monthly expenses:       {fmt_inr(profile.monthly_expenses_inr)}
  Monthly savings:        {fmt_inr(profile.monthly_savings_inr)}

  FORMAL IDENTITY & ASSETS
  {THIN}
  Aadhaar card:     {_yes_no(profile.has_aadhaar)}
  Bank account:     {_yes_no(profile.has_bank_account)}
  Mobile phone:     {_yes_no(profile.has_mobile_phone)}
  Assets:
{asset_lines}

  WORK HISTORY & SKILLS
  {THIN}
  Previous jobs:    {previous}
  Skills:           {skills}
  Reference available: {_yes_no(profile.references_available)}

  SUMMARY
  {THIN}
{_wrap(profile.summary_paragraph, 2)}

  REPAYMENT READINESS
  {THIN}
{_wrap(profile.loan_readiness_note, 2)}
{schemes_section}
{BORDER}
  IMPORTANT: This card was generated from a verbal interview only.
  It is NOT a credit score. It is a starting point for formal
  verification by a microfinance officer or loan counselor.
{BORDER}
"""


def format_json(profile: FinancialProfile) -> str:
    """Returns the profile as formatted JSON."""
    return profile.model_dump_json(indent=2)
