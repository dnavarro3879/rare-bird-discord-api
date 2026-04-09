import time

import discord
from dotenv import load_dotenv
from loguru import logger

from apps.locate import LocateDeps
from apps.locate import register as register_locate
from apps.search import AppDeps
from apps.search import register as register_search
from apps.search.services import SearchService
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

    def make_search_service() -> SearchService:
        return SearchService(
            client=anthropic_client,
            config=config,
            sleeper=time.sleep,
            logger=logger,
        )

    search_deps = AppDeps(
        config=config,
        anthropic_client=anthropic_client,
        logger=logger,
    )
    locate_deps = LocateDeps(
        config=config,
        anthropic_client=anthropic_client,
        logger=logger,
        make_search_service=make_search_service,
    )
    register_search(bot, search_deps)
    register_locate(bot, locate_deps)

    bot.run(config.discord_token)


if __name__ == "__main__":
    main()
