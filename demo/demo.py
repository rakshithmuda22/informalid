"""
demo/demo.py — Shows InformalID's value in under 60 seconds.

Run:
    python demo/demo.py                     # both personas
    python demo/demo.py --persona vendor    # street vendor only
    python demo/demo.py --persona domestic  # domestic worker only

Works WITHOUT an API key (mock mode). Set ANTHROPIC_API_KEY in .env for live interviews.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from core.profiler import run_profiler
from core.formatter import format_card, format_json
from core.schemes import match_schemes, jam_assessment


def show_persona(persona_key: str, persona_label: str, mock_mode: bool):
    BORDER = "=" * 64
    THIN = "-" * 64

    print(f"\n{BORDER}")
    print(f"  PERSONA: {persona_label.upper()}")
    print(BORDER)

    conversation, profile = run_profiler(persona=persona_key)

    if mock_mode:
        print(f"\n  Replaying interview with {profile.full_name}...\n")
        print(THIN)
        for speaker, text in conversation:
            if speaker == "InformalID":
                print(f"\n  [InformalID] {text}")
            else:
                print(f"  [{speaker}] {text}")
        print(f"\n{THIN}")
        print("\n  Extracting profile + running scheme matcher...\n")

    # Run scheme matcher and JAM assessment with real 2026 data
    schemes = match_schemes(profile)
    jam = jam_assessment(profile)

    print(format_card(profile, mock_mode=mock_mode, schemes=schemes, jam=jam))

    eligible_count = sum(1 for s in schemes if s.eligibility_met)
    total_eligible_inr = sum(s.max_amount_inr for s in schemes if s.eligibility_met)
    print(f"  SCHEME SUMMARY: {eligible_count} schemes matched | Total potential access: Rs {total_eligible_inr:,}")
    print()


def main():
    parser = argparse.ArgumentParser(description="InformalID Demo")
    parser.add_argument("--persona", choices=["domestic", "vendor", "both"], default="both",
                        help="Which persona to show")
    args = parser.parse_args()

    print("\n" + "=" * 64)
    print("  INFORMALID — AI Financial Profiler for Informal Workers")
    print("  Conversation → Structured Profile → Scheme Eligibility")
    print("=" * 64)

    mode_label = "MOCK (demo)" if config.is_mock_mode() else "LIVE (Claude API)"
    print(f"\n  Mode: {mode_label}")
    if config.is_mock_mode():
        print("  No API key needed — showing realistic sample interviews.")

    personas_to_show = []
    if args.persona in ("domestic", "both"):
        personas_to_show.append(("domestic_worker", "Domestic Worker — Meena Devi, Bangalore"))
    if args.persona in ("vendor", "both"):
        personas_to_show.append(("street_vendor", "Street Vendor — Ramesh Kumar, Delhi"))

    for persona_key, persona_label in personas_to_show:
        show_persona(persona_key, persona_label, config.is_mock_mode())

    print("=" * 64)
    print("  WHAT INFORMALID ENABLES:")
    print("  • PM SVANidhi loan application packet (street vendors)")
    print("  • MUDRA micro-loan eligibility assessment")
    print("  • e-Shram registration intake (accident insurance)")
    print("  • PM Vishwakarma scheme for artisans")
    print("  • Microfinance institution onboarding document")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    main()
