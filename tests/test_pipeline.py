"""Whole pipeline, as the demo runs it: interview -> tool-use extraction -> schemes -> card."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from core.formatter import format_card, format_json
from core.profiler import run_profiler
from core.schemes import jam_assessment, match_schemes

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("persona,name,jam,min_likely", [
    ("domestic_worker", "Meena Devi", 2, 2),
    ("street_vendor", "Ramesh Kumar", 3, 6),
])
def test_full_offline_pipeline(persona, name, jam, min_likely):
    log, profile = run_profiler(persona=persona)
    schemes = match_schemes(profile)
    card = format_card(profile, mock_mode=True, schemes=schemes, jam=jam_assessment(profile))
    assert profile.full_name == name and jam_assessment(profile)["score"] == jam
    assert sum(s.eligibility_met for s in schemes) >= min_likely
    assert name in card and json.loads(format_json(profile))["full_name"] == name
    assert len(log) >= 14


def test_jam_gates_scheme_eligibility():
    _, meena = run_profiler(persona="domestic_worker")
    _, ramesh = run_profiler(persona="street_vendor")
    assert not next(s for s in match_schemes(meena) if "PMSBY" in s.name).eligibility_met
    assert next(s for s in match_schemes(ramesh) if "PMSBY" in s.name).eligibility_met


def test_demo_script_runs_offline_from_a_clean_environment():
    env = {"PATH": "/usr/bin:/bin", "INFORMALID_MODE": "mock"}
    out = subprocess.run([sys.executable, str(ROOT / "demo" / "demo.py"), "--persona", "both"],
                         capture_output=True, text=True, env=env, timeout=60, check=True).stdout
    for needle in ("Mode: OFFLINE", "MEENA DEVI", "RAMESH KUMAR", "SCHEMES:", "largest single credit line"):
        assert needle in out, needle
