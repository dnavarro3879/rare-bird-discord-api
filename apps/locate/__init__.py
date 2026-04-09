import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
import discord

from apps.locate.handlers import handle_locate
from apps.locate.services import LocateService
from apps.search.services import SearchService
from core import dispatch
from core.config import Config


@dataclass(frozen=True)
class LocateDeps:
    config: Config
    anthropic_client: anthropic.Anthropic
    logger: Any
    make_search_service: Callable[[], SearchService]
    sleeper: Callable[[float], None] = field(default=time.sleep)


def register(bot: discord.Client, deps: LocateDeps) -> None:
    def make_service() -> LocateService:
        return LocateService(
            client=deps.anthropic_client,
            config=deps.config,
            logger=deps.logger,
        )

    async def on_locate(message: discord.Message) -> None:
        await handle_locate(
            message,
            make_service,
            deps.make_search_service,
            deps.logger,
        )

    dispatch.register_command(bot, "!locate", on_locate)
