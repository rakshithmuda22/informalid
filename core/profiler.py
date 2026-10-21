"""
core/profiler.py - the interview + extraction engine.

Flow (identical live and offline; offline swaps in core.mock.ScriptedClient):
  1. Ask the 7 fixed questions. If a money answer has no number, Claude writes ONE short follow-up.
  2. Send the transcript to Claude with the `extract_financial_profile` tool and let it call the tool.
  3. Validate the tool input with Pydantic. On ValidationError, answer the tool_use with an
     `is_error` tool_result describing the problem and let Claude correct it (up to MAX_ATTEMPTS).

tool_choice is left on "auto" rather than forced: current Claude models reject forced tool use
({"type": "tool"} / {"type": "any"}) with a 400. The tool is declared `strict` (schema-valid input),
the prompt asks for exactly one call, and the code checks that a call happened.
"""
from __future__ import annotations

import re
from typing import Callable, Literal

import anthropic
from pydantic import ValidationError

import config
from core.mock import PERSONAS, ScriptedClient, ScriptedWorker
from core.models import FinancialProfile
from core.questions import (
    EXTRACTION_PROMPT,
    EXTRACTION_TOOL_NAME,
    EXTRACTION_USER_TEMPLATE,
    FOLLOWUP_PROMPT,
    INTERVIEW_QUESTIONS,
    MONEY_QUESTION_IDS,
    OPENER,
)

MAX_ATTEMPTS = 3
Conversation = list[tuple[str, str]]  # (speaker, text)

_NUMBER_WORD_RE = re.compile(r"\b(hundred|thousand|lakh|lac|hazaar|hazar|sau)\b", re.IGNORECASE)


class ExtractionError(RuntimeError):
    """The model did not return a valid profile (refusal, truncation, or repeated invalid output)."""


def build_extraction_tool() -> dict:
    """The FinancialProfile model, as a strict Claude tool definition."""
    return {
        "name": EXTRACTION_TOOL_NAME,
        "description": "Record the structured financial profile extracted from the interview transcript.",
        "input_schema": anthropic.transform_schema(FinancialProfile),
        "strict": True,
    }


def needs_clarification(question_id: str, answer: str) -> bool:
    """A money question answered without any number ('business is okay') needs one follow-up."""
    if question_id not in MONEY_QUESTION_IDS:
        return False
    return not (re.search(r"\d", answer) or _NUMBER_WORD_RE.search(answer))


def _text_of(response) -> str:
    return "".join(b.text for b in response.content if getattr(b, "type", None) == "text").strip()


def conduct_interview(
    client,
    ask: Callable[[str], str],
    *,
    worker_label: str = "Worker",
    model: str | None = None,
    say: Callable[[str, str], None] | None = None,
) -> tuple[Conversation, FinancialProfile]:
    """
    Run the whole interview. `ask(prompt)` returns the worker's answer (input() when live, a script offline).
    `say(speaker, text)` is called for every turn so a UI can print it as it happens.
    """
    model = model or config.CLAUDE_MODEL
    say = say or (lambda speaker, text: None)
    log: Conversation = []
    messages: list[dict] = [{"role": "user", "content": OPENER}]

    def worker_turn(prompt: str) -> str:
        say("InformalID", prompt)
        log.append(("InformalID", prompt))
        messages.append({"role": "assistant", "content": prompt})
        answer = ask(prompt).strip() or "(no answer given)"
        say(worker_label, answer)
        log.append((worker_label, answer))
        messages.append({"role": "user", "content": answer})
        return answer

    for q in INTERVIEW_QUESTIONS:
        answer = worker_turn(q["question"])
        if needs_clarification(q["id"], answer):
            reply = client.messages.create(
                model=model,
                max_tokens=1024,                       # thinking tokens count toward max_tokens
                system=FOLLOWUP_PROMPT,
                output_config={"effort": "low"},
                messages=messages,
            )
            followup = _text_of(reply) if reply.stop_reason != "refusal" else ""
            if followup:
                worker_turn(followup)

    profile = extract_profile(client, log, worker_label=worker_label, model=model)
    return log, profile


def extract_profile(
    client, conversation: Conversation, *, worker_label: str = "Worker", model: str | None = None
) -> FinancialProfile:
    """One tool-use extraction with validation feedback. Raises ExtractionError on failure."""
    model = model or config.CLAUDE_MODEL
    transcript = "\n".join(
        f"{'Interviewer' if speaker == 'InformalID' else 'Worker'}: {text}" for speaker, text in conversation
    )
    tool = build_extraction_tool()
    messages: list[dict] = [{"role": "user", "content": EXTRACTION_USER_TEMPLATE.format(transcript=transcript)}]
    last_problem = "no attempt made"

    for _ in range(MAX_ATTEMPTS):
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            system=EXTRACTION_PROMPT,
            tools=[tool],
            tool_choice={"type": "auto", "disable_parallel_tool_use": True},
            output_config={"effort": "medium"},
            messages=messages,
        )
        if response.stop_reason == "refusal":
            raise ExtractionError("the model declined to process this transcript")
        if response.stop_reason == "max_tokens":
            raise ExtractionError("extraction was cut off by max_tokens")

        calls = [b for b in response.content
                 if getattr(b, "type", None) == "tool_use" and b.name == EXTRACTION_TOOL_NAME]
        if not calls:
            last_problem = "the model answered in text instead of calling the tool"
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": f"Call the {EXTRACTION_TOOL_NAME} tool now with the full profile."})
            continue

        call = calls[0]
        try:
            return FinancialProfile.model_validate(call.input)
        except ValidationError as err:
            last_problem = _summarise(err)
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": call.id, "is_error": True,
                 "content": f"Invalid profile: {last_problem}. Call the tool again with corrected values."}
            ]})

    raise ExtractionError(f"no valid profile after {MAX_ATTEMPTS} attempts ({last_problem})")


def _summarise(err: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'profile'}: {e['msg']}" for e in err.errors()[:8])


def run_profiler(
    persona: Literal["domestic_worker", "street_vendor"] = "domestic_worker",
    *,
    say: Callable[[str, str], None] | None = None,
) -> tuple[Conversation, FinancialProfile]:
    """Entry point. Live (stdin + real API) or offline (scripted persona), per config."""
    if config.is_mock_mode():
        p = PERSONAS[persona]
        return conduct_interview(ScriptedClient(p), ScriptedWorker(p), worker_label=p.worker_name, say=say)

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    def ask_stdin(_prompt: str) -> str:
        return input("[You] ")

    def echo_question_only(speaker: str, text: str) -> None:
        if speaker == "InformalID":
            print(f"\n[InformalID] {text}")

    return conduct_interview(client, ask_stdin, worker_label="You", say=say or echo_question_only)
