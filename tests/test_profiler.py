"""The interview + tool-use extraction flow, run against the scripted client (no network)."""
import pytest

import config
from core.mock import MEENA, PERSONAS, RAMESH, ScriptedClient, ScriptedWorker
from core.models import FinancialProfile
from core.profiler import (
    MAX_ATTEMPTS,
    ExtractionError,
    build_extraction_tool,
    conduct_interview,
    extract_profile,
    needs_clarification,
    run_profiler,
)
from core.questions import EXTRACTION_TOOL_NAME, INTERVIEW_QUESTIONS


def run(persona):
    client = ScriptedClient(persona)
    log, profile = conduct_interview(client, ScriptedWorker(persona), worker_label=persona.worker_name)
    return client, log, profile


# -- the interview --------------------------------------------------------------

def test_all_seven_questions_are_asked_in_order():
    _, log, _ = run(MEENA)
    asked = [text for speaker, text in log if speaker == "InformalID"]
    assert asked == [q["question"] for q in INTERVIEW_QUESTIONS]
    assert len(INTERVIEW_QUESTIONS) == 7


def test_answers_come_from_the_script():
    _, log, _ = run(MEENA)
    assert [t for s, t in log if s == "Meena Devi"] == [MEENA.answers[q["id"]] for q in INTERVIEW_QUESTIONS]


def test_conversation_alternates_speakers():
    for persona in PERSONAS.values():
        _, log, _ = run(persona)
        assert [s == "InformalID" for s, _ in log] == [i % 2 == 0 for i in range(len(log))]


def test_vague_money_answer_triggers_exactly_one_claude_followup():
    client, log, _ = run(RAMESH)
    followup_calls = [c for c in client.messages.calls if not c.get("tools")]
    assert len(followup_calls) == 1
    assert len(log) == 2 * (7 + 1)                       # 7 questions + 1 clarification, each with an answer
    assert RAMESH.clarifications[0][0] in [t for _, t in log]
    assert followup_calls[0]["output_config"] == {"effort": "low"}


def test_clear_answers_need_no_followup():
    client, log, _ = run(MEENA)
    assert not [c for c in client.messages.calls if not c.get("tools")]
    assert len(log) == 14


@pytest.mark.parametrize("qid,answer,expected", [
    ("income", "Business is okay", True),
    ("income", "about 9,000 a month", False),
    ("income", "nau hazaar", False),            # transliterated number word counts as a figure
    ("income", "some money, not much", True),
    ("income", "nine thousand", False),
    ("income", "2 lakh", False),
    ("expenses_savings", "I spend some, save little", True),
    ("name_age_location", "Meena", False),      # only money questions are checked
])
def test_needs_clarification(qid, answer, expected):
    assert needs_clarification(qid, answer) is expected


def test_empty_answer_is_recorded_not_dropped():
    persona = MEENA
    worker = ScriptedWorker(persona)

    def ask(prompt):
        return "   " if prompt == INTERVIEW_QUESTIONS[5]["question"] else worker(prompt)

    log, _ = conduct_interview(ScriptedClient(persona), ask, worker_label="Meena Devi")
    assert ("Meena Devi", "(no answer given)") in log


# -- the request shape the API receives -----------------------------------------------

def test_extraction_request_uses_current_tool_use_shape():
    client, _, _ = run(MEENA)
    call = client.messages.calls[-1]
    tool = call["tools"][0]
    assert tool["name"] == EXTRACTION_TOOL_NAME and tool["strict"] is True
    assert tool["input_schema"]["additionalProperties"] is False
    assert call["tool_choice"]["type"] == "auto"                       # forced tool_choice 400s on current models
    assert call["messages"][0]["role"] == "user"
    content = call["messages"][0]["content"]
    assert "<transcript>" in content and "Interviewer:" in content and "Worker:" in content
    assert call["max_tokens"] >= 4096
    assert call["output_config"]["effort"] in {"low", "medium", "high"}
    assert call["model"] == config.CLAUDE_MODEL


def test_default_model_id_is_a_current_undated_id():
    assert config.CLAUDE_MODEL in {"claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"}


def test_conversation_history_starts_with_user_and_roles_alternate():
    client, _, _ = run(RAMESH)
    followup = next(c for c in client.messages.calls if not c.get("tools"))
    roles = [m["role"] for m in followup["messages"]]
    assert roles[0] == "user" and roles[-1] == "user"
    assert all(a != b for a, b in zip(roles, roles[1:]))


def test_scripted_client_rejects_forced_tool_choice():
    client = ScriptedClient(MEENA)
    with pytest.raises(ValueError, match="tool_choice"):
        client.messages.create(model="m", max_tokens=1, messages=[{"role": "user", "content": "x"}],
                               tool_choice={"type": "tool", "name": EXTRACTION_TOOL_NAME})


def test_scripted_client_rejects_leading_assistant_turn():
    with pytest.raises(ValueError, match="first message"):
        ScriptedClient(MEENA).messages.create(model="m", max_tokens=1, messages=[{"role": "assistant", "content": "x"}])


def test_tool_schema_matches_model():
    schema = build_extraction_tool()["input_schema"]
    assert set(schema["properties"]) == set(FinancialProfile.model_fields)


# -- extraction results ----------------------------------------------------------------

def test_scripted_flow_returns_validated_profile():
    for persona in PERSONAS.values():
        _, _, profile = run(persona)
        assert profile == persona.profile


def _transcript():
    return [("InformalID", "q"), ("Worker", "a")]


def test_invalid_tool_input_is_fed_back_as_error_tool_result_and_corrected():
    client = ScriptedClient(MEENA)
    bad = MEENA.profile.model_dump(mode="json") | {"monthly_savings_inr": 99999}
    client.messages._extraction_inputs = [bad]
    profile = extract_profile(client, _transcript())
    assert profile == MEENA.profile
    first, second = client.messages.calls
    assert len(second["messages"]) == len(first["messages"]) + 2
    assistant_turn, tool_turn = second["messages"][-2:]
    assert assistant_turn["role"] == "assistant" and tool_turn["role"] == "user"
    result = tool_turn["content"][0]
    assert result["type"] == "tool_result" and result["is_error"] is True
    assert result["tool_use_id"] == assistant_turn["content"][0].id
    assert "larger than" in result["content"]


def test_gives_up_after_max_attempts_with_a_clear_error():
    client = ScriptedClient(MEENA)
    bad = MEENA.profile.model_dump(mode="json") | {"age": 3}
    client.messages._extraction_inputs = [dict(bad) for _ in range(MAX_ATTEMPTS)]
    with pytest.raises(ExtractionError, match="after 3 attempts"):
        extract_profile(client, _transcript())
    assert len(client.messages.calls) == MAX_ATTEMPTS


def test_extra_keys_in_tool_input_are_rejected():
    client = ScriptedClient(MEENA)
    client.messages._extraction_inputs = [MEENA.profile.model_dump(mode="json") | {"credit_score": 700}]
    assert extract_profile(client, _transcript()) == MEENA.profile   # second attempt is clean
    assert len(client.messages.calls) == 2


class _OneShot:
    """Minimal client returning canned Message objects."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _msg(content, stop_reason):
    from core.mock import _message
    return _message(content, stop_reason)


def test_refusal_raises():
    with pytest.raises(ExtractionError, match="declined"):
        extract_profile(_OneShot(_msg([], "refusal")), _transcript())


def test_truncation_raises():
    with pytest.raises(ExtractionError, match="max_tokens"):
        extract_profile(_OneShot(_msg([], "max_tokens")), _transcript())


def test_text_reply_without_tool_call_is_nudged_then_succeeds():
    from anthropic.types import TextBlock, ToolUseBlock
    ok = ToolUseBlock(type="tool_use", id="toolu_1", name=EXTRACTION_TOOL_NAME, input=MEENA.profile.model_dump(mode="json"))
    client = _OneShot(_msg([TextBlock(type="text", text="Here is the profile...", citations=None)], "end_turn"),
                      _msg([ok], "tool_use"))
    assert extract_profile(client, _transcript()) == MEENA.profile
    nudge = client.calls[1]["messages"][-1]
    assert nudge["role"] == "user" and EXTRACTION_TOOL_NAME in nudge["content"]


def test_wrong_tool_name_counts_as_no_call():
    from anthropic.types import ToolUseBlock
    other = ToolUseBlock(type="tool_use", id="t", name="something_else", input={})
    client = _OneShot(*[_msg([other], "tool_use")] * MAX_ATTEMPTS)
    with pytest.raises(ExtractionError, match="text instead of calling"):
        extract_profile(client, _transcript())


# -- entry point -----------------------------------------------------------------------

def test_run_profiler_offline_end_to_end():
    for key, persona in PERSONAS.items():
        log, profile = run_profiler(persona=key)
        assert profile == persona.profile
        assert len(log) >= 14


def test_say_callback_sees_every_turn():
    seen = []
    log, _ = run_profiler(persona="domestic_worker", say=lambda s, t: seen.append((s, t)))
    assert seen == log
