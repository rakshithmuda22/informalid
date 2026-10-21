"""
demo/demo.py - run the full InformalID flow end to end.

    python demo/demo.py                     # offline: scripted worker + scripted extraction (no API key)
    python demo/demo.py --persona vendor    # one persona only (vendor | domestic | both)
    python demo/demo.py --json              # also print the validated profile as JSON
    ANTHROPIC_API_KEY=... python demo/demo.py   # live: you answer the 7 questions, Claude extracts

Offline mode runs the same code path as live mode (question loop, Claude-written follow-up, tool-use
extraction, Pydantic validation, scheme matching) against core.mock.ScriptedClient.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
from core.formatter import format_card, format_json  # noqa: E402
from core.mock import PERSONAS  # noqa: E402
from core.money import format_inr  # noqa: E402
from core.profiler import run_profiler  # noqa: E402
from core.schemes import jam_assessment, match_schemes  # noqa: E402

BORDER = "=" * 64

PERSONA_KEYS = {"domestic": "domestic_worker", "vendor": "street_vendor"}


def show_persona(key: str, mock_mode: bool, as_json: bool) -> None:
    label = PERSONAS[key].label if mock_mode else "Live interview"
    print(f"\n{BORDER}\n  {label.upper()}\n{BORDER}")

    def say(speaker: str, text: str) -> None:
        print(f"\n  [{speaker}] {text}" if speaker == "InformalID" else f"  [{speaker}] {text}")

    conversation, profile = run_profiler(persona=key, say=say if mock_mode else None)
    print("\n\n  Profile extracted via tool use and validated by Pydantic. Matching schemes...")

    schemes = match_schemes(profile)
    jam = jam_assessment(profile)
    print(format_card(profile, mock_mode=mock_mode, schemes=schemes, jam=jam))

    ready = [s for s in schemes if s.eligibility_met]
    credit = [s.max_amount_inr for s in ready if s.kind == "credit" and s.max_amount_inr]
    largest = f" | largest single credit line: {format_inr(max(credit))}" if credit else ""
    print(f"  SCHEMES: {len(ready)} likely eligible, {len(schemes) - len(ready)} after prerequisites or to verify{largest}")
    print("  (credit lines are alternatives, not additive; insurance cover is separate)\n")
    if as_json:
        print(format_json(profile))


def main() -> None:
    parser = argparse.ArgumentParser(description="InformalID demo")
    parser.add_argument("--persona", choices=["domestic", "vendor", "both"], default="both",
                        help="Which scripted persona to run (offline mode only)")
    parser.add_argument("--json", action="store_true", help="Also print the validated profile as JSON")
    args = parser.parse_args()

    mock_mode = config.is_mock_mode()
    print(f"\n{BORDER}\n  INFORMALID - AI Financial Profiler for Informal Workers")
    print(f"  Mode: {'OFFLINE (scripted)' if mock_mode else 'LIVE'}  |  model: {config.CLAUDE_MODEL}\n{BORDER}")

    if mock_mode:
        keys = [PERSONA_KEYS[args.persona]] if args.persona != "both" else list(PERSONAS)
    else:
        keys = ["live"]
    for key in keys:
        show_persona(key, mock_mode, args.json)


if __name__ == "__main__":
    main()
