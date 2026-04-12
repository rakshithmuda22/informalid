"""
core/profiler.py — The conversation engine.

Two modes:
  live: uses Claude API to conduct the interview and extract the profile
  mock: uses a hardcoded sample conversation (no API key required)
"""
from __future__ import annotations
import json
from typing import Generator

from core.models import FinancialProfile
from core.questions import INTERVIEW_QUESTIONS, SYSTEM_PROMPT, EXTRACTION_PROMPT
import config


# ---------------------------------------------------------------------------
# Mock data — used when no API key is present
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
        "Eligible for a PM SVANidhi-style micro-loan up to Rs 10,000 or a MUDRA Shishu loan up to Rs 50,000 "
        "based on 8 years of stable income and available employer reference."
    ),
)


# ---------------------------------------------------------------------------
# Live mode — actual Claude API interview
# ---------------------------------------------------------------------------
def conduct_interview_live() -> tuple[list[tuple[str, str]], FinancialProfile]:
    """
    Conducts a real interview via the Claude API.
    Returns: (conversation_log, profile)
    """
    import anthropic
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    messages: list[dict] = []
    conversation_log: list[tuple[str, str]] = []

    for q_data in INTERVIEW_QUESTIONS:
        # Add the question as an assistant turn (Claude asks the question)
        question = q_data["question"]
        messages.append({"role": "assistant", "content": question})
        conversation_log.append(("InformalID", question))

        # Get user answer via input() — in demo mode we simulate this
        print(f"\n[InformalID] {question}")
        answer = input("[You] ").strip()
        if not answer:
            answer = "(no answer given)"

        messages.append({"role": "user", "content": answer})
        conversation_log.append(("You", answer))

        # If answer is vague on a financial question, ask for clarification
        if q_data["id"] in ("income", "expenses_savings") and any(
            vague in answer.lower() for vague in ["little", "some", "not much", "okay", "fine"]
        ):
            clarification_response = client.messages.create(
                model=config.CLAUDE_MODEL,
                max_tokens=150,
                system=SYSTEM_PROMPT,
                messages=messages + [
                    {"role": "user", "content": answer},
                    {"role": "assistant", "content": "Could you give me a rough number in rupees per month? Even an estimate is fine."}
                ]
            )
            followup = clarification_response.content[0].text
            messages.append({"role": "assistant", "content": followup})
            conversation_log.append(("InformalID", followup))
            print(f"\n[InformalID] {followup}")
            followup_answer = input("[You] ").strip()
            messages.append({"role": "user", "content": followup_answer})
            conversation_log.append(("You", followup_answer))

    # Extract the structured profile
    conversation_text = "\n".join(
        f"{speaker}: {text}" for speaker, text in conversation_log
    )

    extraction_response = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=2000,
        system=EXTRACTION_PROMPT,
        messages=[{"role": "user", "content": f"Interview transcript:\n\n{conversation_text}"}]
    )

    raw_json = extraction_response.content[0].text.strip()
    # Strip markdown code fences if present
    if raw_json.startswith("```"):
        raw_json = raw_json.split("```")[1]
        if raw_json.startswith("json"):
            raw_json = raw_json[4:]
    raw_json = raw_json.strip()

    profile_data = json.loads(raw_json)
    profile = FinancialProfile(**profile_data)
    return conversation_log, profile


def run_profiler() -> tuple[list[tuple[str, str]], FinancialProfile]:
    """
    Entry point. Picks live or mock mode based on config.
    """
    if config.is_mock_mode():
        return MOCK_CONVERSATION, MOCK_PROFILE
    return conduct_interview_live()
