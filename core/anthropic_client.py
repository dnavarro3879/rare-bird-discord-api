import anthropic

from core.config import Config


def build_anthropic_client(config: Config) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=config.anthropic_api_key)
