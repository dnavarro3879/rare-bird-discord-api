import os
from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Config:
    discord_token: str
    anthropic_api_key: str
    agent_id: str
    environment_id: str
    claude_model: str = ""


class MissingEnvError(RuntimeError):
    pass


_REQUIRED = ("DISCORD_TOKEN", "ANTHROPIC_API_KEY", "AGENT_ID", "ENVIRONMENT_ID")


def load_config(env: Mapping[str, str] | None = None) -> Config:
    env = env if env is not None else os.environ
    missing = [k for k in _REQUIRED if not env.get(k)]
    if missing:
        raise MissingEnvError(f"Missing env vars: {', '.join(missing)}")
    return Config(
        discord_token=env["DISCORD_TOKEN"],
        anthropic_api_key=env["ANTHROPIC_API_KEY"],
        agent_id=env["AGENT_ID"],
        environment_id=env["ENVIRONMENT_ID"],
        claude_model=env.get("CLAUDE_MODEL", ""),
    )
