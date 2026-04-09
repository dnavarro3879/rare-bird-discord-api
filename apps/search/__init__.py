import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
import discord

from apps.search.handlers import handle_search
from apps.search.services import SearchService
from core.config import Config


@dataclass(frozen=True)
class AppDeps:
    config: Config
    anthropic_client: anthropic.Anthropic
    logger: Any
    sleeper: Callable[[float], None] = field(default=time.sleep)


def register(bot: discord.Client, deps: AppDeps) -> None:
    def make_service() -> SearchService:
        return SearchService(
            client=deps.anthropic_client,
            config=deps.config,
            sleeper=deps.sleeper,
            logger=deps.logger,
        )

    @bot.event
    async def on_message(message: discord.Message) -> None:
        if message.author == bot.user:
            return
        if not message.content.startswith("!search"):
            return
        await handle_search(message, make_service, deps.logger)
