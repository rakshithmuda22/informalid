"""
config.py - the one place that reads environment variables.

INFORMALID_MODE
    auto (default)  live if ANTHROPIC_API_KEY is set, otherwise offline mock
    live            always call the Claude API (error if there is no key)
    mock            never call the API; replay a scripted interview
CLAUDE_MODEL
    A current model ID: claude-sonnet-5-5 (default), claude-opus-5-5 or
    claude-haiku-5-5. Requests use `output_config.effort` and do not force
    tool_choice, which current models require; older IDs may be retired.
"""
from __future__ import annotations

import os
from pathlib import Path

_PLACEHOLDER_KEYS = {"", "your_key_here", "your-api-key", "your_api_key_here"}


def _load_dotenv(path: Path) -> None:
    """Minimal .env reader (KEY=value, optional quotes, # comments). Never overrides real env vars."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key.strip(), value)


_load_dotenv(Path(__file__).parent / ".env")

_raw_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
ANTHROPIC_API_KEY: str = "" if _raw_key.lower() in _PLACEHOLDER_KEYS else _raw_key

INFORMALID_MODE: str = os.getenv("INFORMALID_MODE", "auto").strip().lower()
if INFORMALID_MODE not in {"auto", "live", "mock"}:
    raise ValueError(f"INFORMALID_MODE must be auto, live or mock (got {INFORMALID_MODE!r})")

CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")


def is_mock_mode() -> bool:
    if INFORMALID_MODE == "mock":
        return True
    if INFORMALID_MODE == "live":
        if not ANTHROPIC_API_KEY:
            raise RuntimeError("INFORMALID_MODE=live but ANTHROPIC_API_KEY is not set")
        return False
    return not ANTHROPIC_API_KEY
