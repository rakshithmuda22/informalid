"""
core/profiler.py — The conversation engine.

Two modes:
  live: uses Claude API to conduct the interview and extract the profile
  mock: uses hardcoded sample conversations (no API key required)

Extraction uses tool-use forcing — Claude MUST call the extraction tool,
so the JSON is guaranteed to match the schema. No regex or markdown stripping.
"""
from __future__ import annotations
import json
from typing import Literal

from core.models import FinancialProfile
from core.questions import INTERVIEW_QUESTIONS, SYSTEM_PROMPT, EXTRACTION_PROMPT
import config


# ---------------------------------------------------------------------------
# Mock data — two realistic personas for demo
# ---------------------------------------------------------------------------

MOCK_CONVERSATION = [
    ("InformalID", "What is your name, roughly how old are you, and which area do you live or work in?"),
    ("Meena Devi", "My name is Meena Devi. I am 34 years old. I work in Koramangala, Bangalore."),
    ("InformalID", "What kind of work do you do right now? How long have you been doing this work?"),
    ("Meena Devi", "I clean houses. I go to 3 houses every day. I have been doing this for 8 years."),
    ("InformalID", "How much money do you earn in a typical month? Do you earn from any other sources too?"),
    ("Meena Devi", "I earn around 9,000 rupees per month. No other work."),
    ("InformalID", "About how much do you spend each month on rent, food, travel, and other things? Do you manage to save anything?"),
    ("Meena Devi", "I spend around 6,500 rupees. I save maybe 2,000 to 2,500 rupees."),
    ("InformalID", "Do you have a bank account or a Jan Dhan account? Do you have an Aadhaar card? Do you own anything valuable?"),
    ("Meena Devi", "I have Aadhaar. No bank account yet. I have my mobile phone, it cost 4,000 rupees."),
    ("InformalID", "What other kinds of work have you done before this? What are you good at?"),
    ("Meena Devi", "Before this I worked in a garment factory for 2 years. I am good at cleaning, cooking, and taking care of children."),
    ("InformalID", "Which languages do you speak? Is there someone who can vouch for your work?"),
    ("Meena Devi", "I speak Hindi and some Kannada. Yes, my employer Mrs. Sharma can tell you about my work."),
]

MOCK_PROFILE = FinancialProfile(
    full_name="Meena Devi",
    age=34,
    occupation="Domestic worker (house cleaning)",
    years_in_occupation=8,
    income_sources=[
        {"description": "House cleaning — 3 households in Koramangala", "frequency": "monthly", "estimated_monthly_inr": 9000}
    ],
    total_monthly_income_inr=9000,
    monthly_expenses_inr=6500,
    monthly_savings_inr=2000,
    assets=[
        {"item": "Mobile phone", "estimated_value_inr": 4000}
    ],
    has_bank_account=False,
    has_aadhaar=True,
    has_mobile_phone=True,
    previous_occupations=["Garment factory worker (2 years)"],
    skills=["Cleaning", "Cooking", "Child care"],
    references_available=True,
    location_city_or_area="Koramangala, Bangalore",
    languages_spoken=["Hindi", "Kannada (basic)"],
    summary_paragraph=(
        "Meena Devi is a domestic worker with 8 years of consistent income serving 3 households "
        "in Koramangala, Bangalore, earning Rs 9,000 per month. "
        "She saves approximately Rs 2,000 per month, holds an Aadhaar card, and has a reliable employer reference."
    ),
    loan_readiness_note=(
        "Eligible for MUDRA Shishu loan up to Rs 50,000 (no collateral required). "
        "Opening a Jan Dhan account (free, same-day with Aadhaar) would unlock Rs 10,000 overdraft immediately "
        "and direct benefit transfer access."
    ),
)

# Second persona: Ramesh Kumar, a street vendor with a Jan Dhan account
MOCK_CONVERSATION_2 = [
    ("InformalID", "What is your name, roughly how old are you, and which area do you live or work in?"),
    ("Ramesh Kumar", "My name is Ramesh Kumar. I am 42 years old. I have a chaat stall near Lajpat Nagar metro, Delhi."),
    ("InformalID", "What kind of work do you do right now? How long have you been doing this work?"),
    ("Ramesh Kumar", "I sell pani puri and chaat. I have been doing this for 11 years. Same spot."),
    ("InformalID", "How much money do you earn in a typical month? Do you earn from any other sources too?"),
    ("Ramesh Kumar", "On a good month I earn about 18,000 to 20,000 rupees. Rainy season is less, maybe 12,000. My wife also does some stitching work, maybe 3,000 per month."),
    ("InformalID", "About how much do you spend each month on rent, food, travel, and other things? Do you manage to save anything?"),
    ("Ramesh Kumar", "Rent for our room is 4,500. Food and gas for the stall maybe 8,000. Total spending around 15,000. I save maybe 3,000 to 5,000."),
    ("InformalID", "Do you have a bank account or a Jan Dhan account? Do you have an Aadhaar card? Do you own anything valuable?"),
    ("Ramesh Kumar", "Yes I have Jan Dhan account in SBI. Aadhaar also I have. I have a second-hand refrigerator for the stall, I paid 8,000 for it. Mobile phone also."),
    ("InformalID", "What other kinds of work have you done before this? What are you good at?"),
    ("Ramesh Kumar", "Before I used to work in a restaurant as helper for 4 years. I know cooking, especially chaat and street food. I also know how to talk to customers and manage cash."),
    ("InformalID", "Which languages do you speak? Is there someone who can vouch for your work?"),
    ("Ramesh Kumar", "Hindi and a little Punjabi. Yes, the shopkeeper next to my stall, Mr. Verma, he knows me for 10 years."),
]

MOCK_PROFILE_2 = FinancialProfile(
    full_name="Ramesh Kumar",
    age=42,
    occupation="Street food vendor (chaat stall)",
    years_in_occupation=11,
    income_sources=[
        {"description": "Chaat stall near Lajpat Nagar metro", "frequency": "monthly", "estimated_monthly_inr": 18000},
        {"description": "Wife's tailoring work", "frequency": "monthly", "estimated_monthly_inr": 3000},
    ],
    total_monthly_income_inr=21000,
    monthly_expenses_inr=18000,  # Rs 15K household + ~Rs 3K stall restocking
    monthly_savings_inr=3000,
    assets=[
        {"item": "Second-hand refrigerator (for stall)", "estimated_value_inr": 8000},
        {"item": "Mobile phone", "estimated_value_inr": 5000},
    ],
    has_bank_account=True,
    has_aadhaar=True,
    has_mobile_phone=True,
    previous_occupations=["Restaurant helper (4 years)"],
    skills=["Street food cooking", "Customer management", "Cash handling"],
    references_available=True,
    location_city_or_area="Lajpat Nagar, Delhi",
    languages_spoken=["Hindi", "Punjabi (basic)"],
    summary_paragraph=(
        "Ramesh Kumar is a street food vendor with 11 years of stable operation at the same location "
        "in Lajpat Nagar, Delhi, with combined household income of Rs 21,000 per month. "
        "He has a Jan Dhan account, Aadhaar, and a long-standing neighbor reference — strong JAM foundation."
    ),
    loan_readiness_note=(
        "Top candidate for PM SVANidhi Tranche 1 (Rs 15,000, no collateral) and the new SVANidhi Credit Card "
        "(Rs 30,000 UPI-linked, interest-free, Jan 2026). Also eligible for MUDRA Shishu (Rs 50,000) "
        "and Jan Dhan overdraft (Rs 10,000 instant). With 11 years tenure and all JAM pillars complete, "
        "qualifies for MUDRA Kishore (up to Rs 5 lakh) with 2 years of income evidence."
    ),
)

MOCK_PERSONAS: dict[str, tuple[list, FinancialProfile]] = {
    "domestic_worker": (MOCK_CONVERSATION, MOCK_PROFILE),
    "street_vendor": (MOCK_CONVERSATION_2, MOCK_PROFILE_2),
}


# ---------------------------------------------------------------------------
# Extraction tool definition — production-grade structured extraction
# ---------------------------------------------------------------------------

def _build_extraction_tool() -> dict:
    """
    Build an Anthropic tool definition from the FinancialProfile schema.
    Using tool-use forcing guarantees Claude returns valid JSON matching the schema —
    no regex, no markdown stripping, no json.loads fallbacks needed.
    """
    schema = FinancialProfile.model_json_schema()
    # Remove the example from the schema to keep token count low
    schema.pop("examples", None)
    return {
        "name": "extract_financial_profile",
        "description": "Extract a structured financial profile from the interview transcript",
        "input_schema": schema,
    }


# ---------------------------------------------------------------------------
# Live mode — actual Claude API interview with tool-use extraction
# ---------------------------------------------------------------------------

def conduct_interview_live() -> tuple[list[tuple[str, str]], FinancialProfile]:
    """
    Conducts a real interview via Claude API, then extracts profile using tool-use.

    Why tool-use forcing for extraction (not raw JSON prompting):
      - Claude MUST call the tool → schema is enforced by the API layer
      - No markdown fences to strip, no json.loads fallbacks
      - If schema changes, tool definition auto-updates from Pydantic model
      - Cleaner than prompting for JSON and hoping Claude cooperates
    """
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    messages: list[dict] = []
    conversation_log: list[tuple[str, str]] = []

    for q_data in INTERVIEW_QUESTIONS:
        question = q_data["question"]
        messages.append({"role": "assistant", "content": question})
        conversation_log.append(("InformalID", question))

        print(f"\n[InformalID] {question}")
        answer = input("[You] ").strip()
        if not answer:
            answer = "(no answer given)"

        messages.append({"role": "user", "content": answer})
        conversation_log.append(("You", answer))

        # Gentle clarification for vague financial answers
        if q_data["id"] in ("income", "expenses_savings") and any(
            vague in answer.lower() for vague in ["little", "some", "not much", "okay", "fine"]
        ):
            followup_response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=150,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            followup = followup_response.content[0].text
            messages.append({"role": "assistant", "content": followup})
            conversation_log.append(("InformalID", followup))
            print(f"\n[InformalID] {followup}")
            followup_answer = input("[You] ").strip()
            messages.append({"role": "user", "content": followup_answer})
            conversation_log.append(("You", followup_answer))

    # --- Structured extraction via tool-use forcing ---
    conversation_text = "\n".join(
        f"{speaker}: {text}" for speaker, text in conversation_log
    )
    extraction_tool = _build_extraction_tool()

    extraction_response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=EXTRACTION_PROMPT,
        tools=[extraction_tool],
        tool_choice={"type": "tool", "name": "extract_financial_profile"},
        messages=[{"role": "user", "content": f"Interview transcript:\n\n{conversation_text}"}],
    )

    # With tool_choice forcing, content[0] is always a ToolUseBlock
    tool_block = extraction_response.content[0]
    profile_data = tool_block.input  # Already a dict — no JSON parsing needed
    profile = FinancialProfile(**profile_data)
    return conversation_log, profile


def run_profiler(
    persona: Literal["domestic_worker", "street_vendor"] = "domestic_worker"
) -> tuple[list[tuple[str, str]], FinancialProfile]:
    """
    Entry point. Picks live or mock mode based on config.
    In mock mode, 'persona' selects which sample profile to show.
    """
    if config.is_mock_mode():
        return MOCK_PERSONAS[persona]
    return conduct_interview_live()
