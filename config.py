"""
config.py — Single source of truth for all environment variables.
Never load os.getenv() anywhere else in the codebase.
"""
import os
from pathlib import Path

# Load .env file if present (dev convenience only)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    with open(_env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
# "live" uses the real API; "mock" runs without any API key
INFORMALID_MODE: str = os.getenv("INFORMALID_MODE", "mock" if not ANTHROPIC_API_KEY else "live")

CLAUDE_MODEL: str = "claude-sonnet-4-6"

def is_mock_mode() -> bool:
    return INFORMALID_MODE == "mock" or not ANTHROPIC_API_KEY
