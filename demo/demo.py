"""
demo/demo.py — Shows InformalID's value in under 60 seconds.

Run:
    python demo/demo.py

Works WITHOUT an API key (mock mode shows a real example interview + card).
Set ANTHROPIC_API_KEY in .env to run a live interview with Claude.
"""
import sys
import os

# Make sure imports resolve from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.profiler import run_profiler
from core.formatter import format_card, format_json


def main():
    print("\n" + "=" * 62)
    print("  INFORMALID — AI Financial Profiler for Informal Workers")
    print("  Building financial identity from conversation alone.")
    print("=" * 62)

    mode_label = "MOCK (demo)" if config.is_mock_mode() else "LIVE (Claude API)"
    print(f"\n  Mode: {mode_label}")

    if config.is_mock_mode():
        print("\n  Replaying a sample interview with Meena Devi,")
        print("  a domestic worker in Bangalore with no bank account...\n")
        print("-" * 62)

    conversation, profile = run_profiler()

    if config.is_mock_mode():
        # Print the conversation
        for speaker, text in conversation:
            if speaker == "InformalID":
                print(f"\n  [InformalID] {text}")
            else:
                print(f"  [{speaker}] {text}")
        print("\n" + "-" * 62)
        print("\n  Extracting structured financial profile from conversation...\n")

    # Print the formatted card
    print(format_card(profile, mock_mode=config.is_mock_mode()))

    # Show a snippet of the JSON output
    print("\n  RAW JSON OUTPUT (for downstream systems):")
    print("-" * 62)
    json_str = format_json(profile)
    lines = json_str.split("\n")
    # Print first 20 lines then truncate
    if len(lines) > 20:
        print("\n".join(lines[:20]))
        print(f"  ... ({len(lines) - 20} more lines)")
    else:
        print(json_str)

    print("\n" + "=" * 62)
    print("  WHAT THIS ENABLES:")
    print("  • PM SVANidhi loan application (street vendors)")
    print("  • MUDRA micro-loan eligibility check")
    print("  • Microfinance institution intake packet")
    print("  • Employer reference document")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
