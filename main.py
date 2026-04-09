import discord
from dotenv import load_dotenv
from loguru import logger

from apps.search import AppDeps
from apps.search import register as register_search
from core.anthropic_client import build_anthropic_client
from core.config import load_config
from core.logging import configure_logging


def main() -> None:
    load_dotenv()
    configure_logging()
    config = load_config()
    anthropic_client = build_anthropic_client(config)

    intents = discord.Intents.default()
    intents.message_content = True
    bot = discord.Client(intents=intents)

    deps = AppDeps(config=config, anthropic_client=anthropic_client, logger=logger)
    register_search(bot, deps)

    bot.run(config.discord_token)


if __name__ == "__main__":
    main()
