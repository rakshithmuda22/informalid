"""
core/formatter.py — Formats a FinancialProfile into readable terminal output.
No API calls. Pure string formatting.
"""
from __future__ import annotations
from datetime import date
from core.models import FinancialProfile


def format_card(
    profile: FinancialProfile,
    mock_mode: bool = False,
    schemes: list | None = None,
    jam: dict | None = None,
) -> str:
    """Returns a formatted financial identity card as a string."""

    BORDER = "=" * 64
    THIN = "-" * 64

    def yes_no(b: bool) -> str:
        return "Yes" if b else "No"

    def fmt_inr(amount: int) -> str:
        return f"Rs {amount:,}"

    income_lines = "\n".join(
        f"    • {src.description} ({src.frequency}) — {fmt_inr(src.estimated_monthly_inr)}/mo"
        for src in profile.income_sources
    )

    asset_lines = "\n".join(
        f"    • {a.item} (est. {fmt_inr(a.estimated_value_inr)})"
        for a in profile.assets
    ) if profile.assets else "    • None reported"

    skills_str = ", ".join(profile.skills) if profile.skills else "Not specified"
    prev_jobs_str = ", ".join(profile.previous_occupations) if profile.previous_occupations else "None"
    languages_str = ", ".join(profile.languages_spoken)

    mock_banner = ""
    if mock_mode:
        mock_banner = (
            "\n  [DEMO MODE — running without API key]\n"
            "  [Set ANTHROPIC_API_KEY in .env to run a real interview]\n"
        )

    # JAM Trinity section
    jam_section = ""
    if jam:
        jam_icon = "✓" if jam["score"] == 3 else ("~" if jam["score"] >= 1 else "✗")
        jam_section = f"\n  JAM TRINITY SCORE: {jam_icon} {jam['score']}/3 — {jam['interpretation']}\n"
        if jam["unlocked"]:
            jam_section += "  Unlocked:\n"
            for item in jam["unlocked"]:
                jam_section += f"    [✓] {item}\n"
        if jam["locked"]:
            jam_section += "  Next steps:\n"
            for item in jam["locked"]:
                jam_section += f"    [ ] {item}\n"

    # Schemes section
    schemes_section = ""
    if schemes:
        eligible = [s for s in schemes if s.eligibility_met]
        check = [s for s in schemes if not s.eligibility_met]
        schemes_section = f"\n  ELIGIBLE SCHEMES ({len(eligible)} found)\n  {THIN}\n"
        for scheme in eligible:
            schemes_section += f"\n  ✓ {scheme.name}\n"
            schemes_section += f"    Max: {fmt_inr(scheme.max_amount_inr)} | {scheme.description[:80]}...\n" if len(scheme.description) > 80 else f"    Max: {fmt_inr(scheme.max_amount_inr)} | {scheme.description}\n"
            schemes_section += f"    → {scheme.action_required}\n"
        if check:
            schemes_section += f"\n  ADDITIONAL SCHEMES (after completing prerequisites)\n"
            for scheme in check:
                schemes_section += f"  ○ {scheme.name} (up to {fmt_inr(scheme.max_amount_inr)}) — {scheme.eligibility_reason}\n"

    card = f"""
{BORDER}
  INFORMALID — FINANCIAL IDENTITY CARD
  Generated: {date.today().isoformat()}  |  Method: AI Conversational Interview
{BORDER}{mock_banner}
  PERSONAL INFORMATION
  {THIN}
  Name:             {profile.full_name}
  Age:              {profile.age} years
  Location:         {profile.location_city_or_area}
  Occupation:       {profile.occupation}
  Years in work:    {profile.years_in_occupation} years
  Languages:        {languages_str}
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
  Aadhaar card:     {yes_no(profile.has_aadhaar)}
  Bank account:     {yes_no(profile.has_bank_account)}
  Mobile phone:     {yes_no(profile.has_mobile_phone)}
  Assets:
{asset_lines}

  WORK HISTORY & SKILLS
  {THIN}
  Previous jobs:    {prev_jobs_str}
  Skills:           {skills_str}
  Reference available: {yes_no(profile.references_available)}

  SUMMARY
  {THIN}
  {profile.summary_paragraph}

  LOAN READINESS (April 2026 scheme data)
  {THIN}
  {profile.loan_readiness_note}
{schemes_section}
{BORDER}
  IMPORTANT: This card was generated from a verbal interview only.
  It is NOT a credit score. It is a starting point for formal
  verification by a microfinance officer or loan counselor.
{BORDER}
"""
    return card


def format_json(profile: FinancialProfile) -> str:
    """Returns the profile as formatted JSON."""
    return profile.model_dump_json(indent=2)
