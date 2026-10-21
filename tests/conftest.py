import os
import sys

# Tests never touch the network: force offline mode before `config` is imported anywhere.
os.environ["INFORMALID_MODE"] = "mock"
os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
