"""
Drive the REAL anthropic SDK client against an in-process HTTP transport, so the bytes that would go to
POST /v1/messages are checked without a network or an API key.
"""
import json

import httpx
import anthropic
import pytest

import config
from core import profiler
from core.mock import MEENA, RAMESH, ScriptedWorker
from core.profiler import conduct_interview, extract_profile, run_profiler
from core.questions import EXTRACTION_TOOL_NAME, INTERVIEW_QUESTIONS


RealAnthropic = anthropic.Anthropic  # keep a handle: one test monkeypatches anthropic.Anthropic


def sdk_client(handler):
    transport = httpx.MockTransport(handler)
    return RealAnthropic(api_key="sk-ant-test", http_client=httpx.Client(transport=transport), max_retries=0)


def api_message(body, content, stop_reason):
    return httpx.Response(200, json={
        "id": "msg_test", "type": "message", "role": "assistant", "model": body["model"], "content": content,
        "stop_reason": stop_reason, "stop_sequence": None, "usage": {"input_tokens": 1, "output_tokens": 1},
    })


def test_extraction_request_and_response_on_the_wire():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append((request.url.path, request.headers, body))
        tool_use = {"type": "tool_use", "id": "toolu_1", "name": EXTRACTION_TOOL_NAME,
                    "input": MEENA.profile.model_dump(mode="json")}
        return api_message(body, [tool_use], "tool_use")

    profile = extract_profile(sdk_client(handler), [("InformalID", "q"), ("Worker", "a")])
    assert profile == MEENA.profile

    path, headers, body = seen[0]
    assert path == "/v1/messages" and headers["x-api-key"] == "sk-ant-test"
    assert body["model"] == "claude-sonnet-5-5"
    assert body["tool_choice"] == {"type": "auto", "disable_parallel_tool_use": True}
    assert body["output_config"] == {"effort": "medium"}
    assert body["tools"][0]["strict"] is True
    assert body["tools"][0]["input_schema"]["additionalProperties"] is False
    assert body["messages"][0]["role"] == "user"
    assert "thinking" not in body  # defaults apply; no removed budget_tokens / disabled values are sent


def test_whole_interview_through_the_sdk_transport():
    persona = RAMESH
    worker = ScriptedWorker(persona)
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if "tools" in body:
            tool_use = {"type": "tool_use", "id": "toolu_1", "name": EXTRACTION_TOOL_NAME,
                        "input": persona.profile.model_dump(mode="json")}
            return api_message(body, [tool_use], "tool_use")
        # Adaptive thinking can put a thinking block first; the client must read the text block by type.
        return api_message(body, [{"type": "thinking", "thinking": "", "signature": "sig"},
                                  {"type": "text", "text": persona.clarifications[0][0]}], "end_turn")

    log, profile = conduct_interview(sdk_client(handler), worker, worker_label=persona.worker_name)
    assert profile == persona.profile
    assert len(log) == 16 and persona.clarifications[0][0] in [t for _, t in log]
    followups = [r for r in requests if "tools" not in r]
    assert len(followups) == 1 and followups[0]["output_config"] == {"effort": "low"}
    assert followups[0]["max_tokens"] >= 1024
    assert [m["role"] for m in followups[0]["messages"]][0] == "user"


def test_validation_error_roundtrip_serialises_tool_result_correctly():
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        data = MEENA.profile.model_dump(mode="json")
        if len(seen) == 1:
            data["age"] = 200
        block = {"type": "tool_use", "id": f"toolu_{len(seen)}", "name": EXTRACTION_TOOL_NAME, "input": data}
        return api_message(body, [block], "tool_use")

    assert extract_profile(sdk_client(handler), [("InformalID", "q"), ("Worker", "a")]) == MEENA.profile
    _, assistant, user = seen[1]["messages"]
    assert assistant["role"] == "assistant" and assistant["content"][0]["type"] == "tool_use"
    assert assistant["content"][0]["id"] == "toolu_1"
    assert user["role"] == "user"
    assert user["content"] == [{
        "type": "tool_result", "tool_use_id": "toolu_1", "is_error": True,
        "content": user["content"][0]["content"],
    }]
    assert "age" in user["content"][0]["content"]


def test_live_branch_of_run_profiler(monkeypatch, capsys):
    """run_profiler() with a key set builds an anthropic.Anthropic client and reads answers from stdin."""
    built = {}

    def handler(request):
        body = json.loads(request.content)
        tool_use = {"type": "tool_use", "id": "toolu_1", "name": EXTRACTION_TOOL_NAME,
                    "input": MEENA.profile.model_dump(mode="json")}
        return api_message(body, [tool_use], "tool_use")

    def fake_anthropic(api_key):
        built["key"] = api_key
        return sdk_client(handler)

    answers = iter(MEENA.answers[q["id"]] for q in INTERVIEW_QUESTIONS)
    monkeypatch.setattr(config, "is_mock_mode", lambda: False)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "sk-ant-live-test")
    monkeypatch.setattr(profiler.anthropic, "Anthropic", fake_anthropic)
    monkeypatch.setattr("builtins.input", lambda prompt="": next(answers))

    log, profile = run_profiler()
    assert built["key"] == "sk-ant-live-test"
    assert profile == MEENA.profile
    assert log[1][0] == "You"
    assert "[InformalID] " + INTERVIEW_QUESTIONS[0]["question"] in capsys.readouterr().out


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_unusable_stop_reasons_surface_as_extraction_error(stop_reason):
    def handler(request):
        return api_message(json.loads(request.content), [], stop_reason)

    with pytest.raises(profiler.ExtractionError):
        extract_profile(sdk_client(handler), [("InformalID", "q"), ("Worker", "a")])
