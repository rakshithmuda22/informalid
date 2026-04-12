"""
core/formatter.py — Formats a FinancialProfile into readable terminal output.
No API calls. Pure string formatting.
"""
from __future__ import annotations
from core.models import FinancialProfile


def format_card(profile: FinancialProfile, mock_mode: bool = False) -> str:
    """Returns a formatted financial identity card as a string."""

    BORDER = "=" * 62
    THIN  = "-" * 62

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

    card = f"""
{BORDER}
  INFORMALID — FINANCIAL IDENTITY CARD
  Generated: 2026-04-12  |  Method: AI Conversational Interview
{BORDER}{mock_banner}
  PERSONAL INFORMATION
  {THIN}
  Name:             {profile.full_name}
  Age:              {profile.age} years
  Location:         {profile.location_city_or_area}
  Occupation:       {profile.occupation}
  Years in work:    {profile.years_in_occupation} years
  Languages:        {languages_str}

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

  LOAN READINESS
  {THIN}
  {profile.loan_readiness_note}

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
