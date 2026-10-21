"""
core/mock.py - offline mode: scripted workers and a stand-in for the Anthropic client.

`ScriptedClient` exposes `.messages.create(...)` and returns real `anthropic.types.Message` objects
(text blocks for follow-ups, a `tool_use` block for extraction), so `core.profiler` runs the SAME code
path offline and live: question loop, clarification, tool-use request, validation, retry.

What this does and does not test:
  * It exercises the plumbing: request shape, tool-use handling, Pydantic validation, scheme matching.
  * It does NOT test extraction quality. The "extraction" it returns is each persona's hand-written
    profile, not a model reading the transcript. Quality needs the live API.
It also refuses requests the current API would refuse (forced tool_choice, first message not from the
user, a tool_result that does not answer a tool_use), so a regression there fails offline.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from anthropic.types import Message, TextBlock, ToolUseBlock, Usage

from core.models import FinancialProfile
from core.questions import EXTRACTION_TOOL_NAME, INTERVIEW_QUESTIONS


@dataclass(frozen=True)
class Persona:
    key: str
    label: str
    worker_name: str
    answers: dict[str, str]                          # question id -> the worker's answer
    clarifications: tuple[tuple[str, str], ...]      # (Claude's follow-up, the worker's reply), in order used
    profile: FinancialProfile                        # what the scripted "extraction" returns


MEENA = Persona(
    key="domestic_worker",
    label="Domestic Worker - Meena Devi, Bangalore",
    worker_name="Meena Devi",
    answers={
        "name_age_location": "My name is Meena Devi. I am 34 years old. I work in Koramangala, Bangalore.",
        "current_work": "I clean houses. I go to 3 houses every day. I have been doing this for 8 years.",
        "income": "I earn around 9,000 rupees per month. No other work.",
        "expenses_savings": "I spend around 6,500 rupees. I save maybe 2,000 to 2,500 rupees.",
        "assets_accounts": "I have Aadhaar. No bank account yet. I have my mobile phone, it cost 4,000 rupees.",
        "skills_history": "Before this I worked in a garment factory for 2 years. I am good at cleaning, cooking, and taking care of children.",
        "languages_references": "I speak Hindi and some Kannada. Yes, my employer Mrs. Sharma can tell you about my work.",
    },
    clarifications=(),
    profile=FinancialProfile(
        full_name="Meena Devi",
        age=34,
        occupation="Domestic worker (house cleaning)",
        years_in_occupation=8,
        work_type="wage_worker",
        income_sources=[
            {"description": "House cleaning - 3 households in Koramangala", "frequency": "monthly", "estimated_monthly_inr": 9000}
        ],
        total_monthly_income_inr=9000,
        monthly_expenses_inr=6500,
        monthly_savings_inr=2000,
        assets=[{"item": "Mobile phone", "estimated_value_inr": 4000}],
        has_bank_account=False,
        has_aadhaar=True,
        has_mobile_phone=True,
        previous_occupations=["Garment factory worker (2 years)"],
        skills=["Cleaning", "Cooking", "Child care"],
        references_available=True,
        location_city_or_area="Koramangala, Bangalore",
        languages_spoken=["Hindi", "Kannada (basic)"],
        summary_paragraph=(
            "Meena Devi is a domestic worker with 8 years of steady work across 3 households in Koramangala, "
            "earning Rs 9,000 a month. She saves about Rs 2,000 a month, has Aadhaar and a phone, and has a "
            "named employer who can vouch for her."
        ),
        loan_readiness_note=(
            "Income covers her spending with a regular surplus, and 8 years with the same kind of clients points "
            "to stable demand. She has no bank account yet, so opening one is the first step before any formal credit."
        ),
    ),
)

RAMESH = Persona(
    key="street_vendor",
    label="Street Vendor - Ramesh Kumar, Delhi",
    worker_name="Ramesh Kumar",
    answers={
        "name_age_location": "My name is Ramesh Kumar. I am 42 years old. I have a chaat stall near Lajpat Nagar metro, Delhi.",
        "current_work": "I sell pani puri and chaat. I have been doing this for 11 years. Same spot.",
        "income": "Business is okay. Good months are better and the rainy season is less. My wife also does some stitching work.",
        "expenses_savings": "Rent for our room is 4,500. Food and gas for the stall maybe 8,000. Total spending around 15,000. I save maybe 3,000 to 5,000.",
        "assets_accounts": "Yes I have Jan Dhan account in SBI. Aadhaar also I have. I have a second-hand refrigerator for the stall, I paid 8,000 for it. Mobile phone also.",
        "skills_history": "Before I used to work in a restaurant as helper for 4 years. I know cooking, especially chaat and street food. I also know how to talk to customers and manage cash.",
        "languages_references": "Hindi and a little Punjabi. Yes, the shopkeeper next to my stall, Mr. Verma, he knows me for 10 years.",
    },
    clarifications=(
        (
            "Roughly how many rupees does the stall bring in during a good month, and during the rainy season?",
            "On a good month I earn about 18,000 to 20,000 rupees. Rainy season is less, maybe 12,000. "
            "My wife's stitching is maybe 3,000 per month.",
        ),
    ),
    profile=FinancialProfile(
        full_name="Ramesh Kumar",
        age=42,
        occupation="Street food vendor (chaat stall)",
        years_in_occupation=11,
        work_type="self_employed",
        income_sources=[
            {"description": "Chaat stall near Lajpat Nagar metro", "frequency": "monthly", "estimated_monthly_inr": 18000},
            {"description": "Wife's tailoring work", "frequency": "monthly", "estimated_monthly_inr": 3000},
        ],
        total_monthly_income_inr=21000,
        monthly_expenses_inr=18000,
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
            "Ramesh Kumar has run the same chaat stall in Lajpat Nagar for 11 years, and household income is "
            "about Rs 21,000 a month including his wife's tailoring. He has a Jan Dhan account, Aadhaar and a "
            "phone, and a neighbouring shopkeeper has known him for 10 years."
        ),
        loan_readiness_note=(
            "Eleven years at one location and a regular surplus of about Rs 3,000 a month point to stable, "
            "repayable cash flow. Aadhaar, a bank account and a phone are all in place, so formal credit and "
            "digital-payment routes are open to him."
        ),
    ),
)

PERSONAS: dict[str, Persona] = {MEENA.key: MEENA, RAMESH.key: RAMESH}


class ScriptedWorker:
    """Answers the interviewer's prompts from a Persona's script."""

    def __init__(self, persona: Persona):
        self._by_prompt = {q["question"]: persona.answers[q["id"]] for q in INTERVIEW_QUESTIONS}
        self._by_prompt.update(dict(persona.clarifications))

    def __call__(self, prompt: str) -> str:
        return self._by_prompt[prompt]


@dataclass
class _ScriptedMessages:
    persona: Persona
    calls: list[dict] = field(default_factory=list)   # every request received, for assertions
    _clarifications_used: int = 0
    _extraction_inputs: list[dict] | None = None      # tests can queue invalid inputs first

    def create(self, **kwargs) -> Message:
        self._validate_request(kwargs)
        # Snapshot: the caller keeps appending to its messages list after the call returns.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        if kwargs.get("tools"):
            return self._extraction_reply()
        return self._followup_reply()

    # -- replies -----------------------------------------------------------
    def _followup_reply(self) -> Message:
        if self._clarifications_used >= len(self.persona.clarifications):
            raise AssertionError("profiler asked for a follow-up the persona script has no answer for")
        text = self.persona.clarifications[self._clarifications_used][0]
        self._clarifications_used += 1
        return _message([TextBlock(type="text", text=text, citations=None)], "end_turn")

    def _extraction_reply(self) -> Message:
        queued = self._extraction_inputs
        payload = queued.pop(0) if queued else self.persona.profile.model_dump(mode="json")
        block = ToolUseBlock(
            type="tool_use", id=f"toolu_mock_{len(self.calls)}", name=EXTRACTION_TOOL_NAME, input=payload
        )
        return _message([block], "tool_use")

    # -- the API's rules, as far as this app can break them ---------------------
    @staticmethod
    def _validate_request(kw: dict) -> None:
        for required in ("model", "max_tokens", "messages"):
            if required not in kw:
                raise TypeError(f"messages.create() missing {required}")
        messages = kw["messages"]
        if not messages or messages[0]["role"] != "user":
            raise ValueError("first message must have role 'user'")
        if (kw.get("tool_choice") or {}).get("type") in ("any", "tool"):
            raise ValueError('tool_choice "any"/"tool" is rejected by current models; use "auto"')
        for tool in kw.get("tools") or []:
            if not {"name", "description", "input_schema"} <= set(tool):
                raise ValueError("a tool needs name, description and input_schema")
        for prev, nxt in zip(messages, messages[1:]):
            wanted = _tool_use_ids(prev)
            if wanted and wanted != _tool_result_ids(nxt):
                raise ValueError("every tool_use block must be answered by a tool_result in the next user message")


def _tool_use_ids(message: dict) -> set[str]:
    if message["role"] != "assistant" or isinstance(message["content"], str):
        return set()
    return {b.id for b in message["content"] if getattr(b, "type", None) == "tool_use"}


def _tool_result_ids(message: dict) -> set[str]:
    if message["role"] != "user" or isinstance(message["content"], str):
        return set()
    return {b["tool_use_id"] for b in message["content"] if isinstance(b, dict) and b.get("type") == "tool_result"}


def _message(content: list, stop_reason: str) -> Message:
    return Message(
        id="msg_mock", type="message", role="assistant", model="claude-sonnet-5-5",
        content=content, stop_reason=stop_reason, stop_sequence=None,
        usage=Usage(input_tokens=0, output_tokens=0),
    )


class ScriptedClient:
    """Drop-in for `anthropic.Anthropic()` as far as this app uses it."""

    def __init__(self, persona: Persona):
        self.persona = persona
        self.messages = _ScriptedMessages(persona)
