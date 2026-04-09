import dataclasses

import pytest

from core.config import Config, MissingEnvError, load_config

_FULL_ENV = {
    "DISCORD_TOKEN": "tok",
    "ANTHROPIC_API_KEY": "akey",
    "AGENT_ID": "agent",
    "ENVIRONMENT_ID": "env",
}


def test_load_config_reads_all_four_vars():
    config = load_config(_FULL_ENV)
    assert config.discord_token == "tok"
    assert config.anthropic_api_key == "akey"
    assert config.agent_id == "agent"
    assert config.environment_id == "env"


@pytest.mark.parametrize(
    "missing_var",
    ["DISCORD_TOKEN", "ANTHROPIC_API_KEY", "AGENT_ID", "ENVIRONMENT_ID"],
)
def test_load_config_raises_missing_env_error_when_any_missing(missing_var):
    env = {k: v for k, v in _FULL_ENV.items() if k != missing_var}
    with pytest.raises(MissingEnvError) as excinfo:
        load_config(env)
    assert missing_var in str(excinfo.value)


def test_load_config_raises_on_empty_string():
    env = {**_FULL_ENV, "DISCORD_TOKEN": ""}
    with pytest.raises(MissingEnvError) as excinfo:
        load_config(env)
    assert "DISCORD_TOKEN" in str(excinfo.value)


def test_config_is_frozen():
    config = load_config(_FULL_ENV)
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.discord_token = "other"  # type: ignore[misc]


def test_load_config_defaults_to_os_environ(monkeypatch):
    for key, value in _FULL_ENV.items():
        monkeypatch.setenv(key, value)
    config = load_config()
    assert isinstance(config, Config)
    assert config.discord_token == "tok"


def test_load_config_defaults_claude_model_to_empty_string():
    config = load_config(_FULL_ENV)
    assert config.claude_model == ""


def test_load_config_reads_claude_model_when_set():
    env = {**_FULL_ENV, "CLAUDE_MODEL": "claude-sonnet-4-5"}
    config = load_config(env)
    assert config.claude_model == "claude-sonnet-4-5"
