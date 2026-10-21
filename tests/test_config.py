import importlib
import os

import pytest

import config


def reload_with(monkeypatch, **env):
    for key in ("ANTHROPIC_API_KEY", "INFORMALID_MODE", "CLAUDE_MODEL"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(config, "_load_dotenv", lambda path: None)  # ignore a developer's real .env
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def restore_config(monkeypatch):
    yield
    monkeypatch.undo()
    monkeypatch.setenv("INFORMALID_MODE", "mock")
    importlib.reload(config)


def test_auto_without_key_is_mock(monkeypatch):
    assert reload_with(monkeypatch).is_mock_mode() is True


def test_auto_with_key_is_live(monkeypatch):
    assert reload_with(monkeypatch, ANTHROPIC_API_KEY="sk-ant-test").is_mock_mode() is False


def test_placeholder_key_from_env_example_counts_as_unset(monkeypatch):
    cfg = reload_with(monkeypatch, ANTHROPIC_API_KEY="your_key_here")
    assert cfg.ANTHROPIC_API_KEY == "" and cfg.is_mock_mode() is True


def test_live_without_key_fails_loudly(monkeypatch):
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        reload_with(monkeypatch, INFORMALID_MODE="live").is_mock_mode()


def test_mock_wins_even_with_a_key(monkeypatch):
    assert reload_with(monkeypatch, ANTHROPIC_API_KEY="sk-ant-test", INFORMALID_MODE="mock").is_mock_mode() is True


def test_bad_mode_rejected(monkeypatch):
    with pytest.raises(ValueError):
        reload_with(monkeypatch, INFORMALID_MODE="turbo")


def test_default_model(monkeypatch):
    assert reload_with(monkeypatch).CLAUDE_MODEL == "claude-sonnet-5-5"
    assert reload_with(monkeypatch, CLAUDE_MODEL="claude-haiku-5-5").CLAUDE_MODEL == "claude-haiku-5-5"


def test_dotenv_parsing(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "environ", {})  # a throwaway environment so nothing leaks into other tests
    env = tmp_path / ".env"
    env.write_text('# comment\nANTHROPIC_API_KEY="sk-ant-quoted"\nexport CLAUDE_MODEL=claude-opus-5-5\nEMPTY=\n')
    config._load_dotenv(env)
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-quoted"
    assert os.environ["CLAUDE_MODEL"] == "claude-opus-5-5"


def test_dotenv_does_not_override_real_env(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("CLAUDE_MODEL=from-file\n")
    monkeypatch.setattr(os, "environ", {"CLAUDE_MODEL": "from-env"})
    config._load_dotenv(env)
    assert os.environ["CLAUDE_MODEL"] == "from-env"
