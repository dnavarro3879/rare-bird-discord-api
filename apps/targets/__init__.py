import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import anthropic
import discord

from apps.targets.handlers import handle_targets
from apps.targets.services import TargetsService
from core import dispatch
from core.config import Config


@dataclass(frozen=True)
class TargetsDeps:
    config: Config
    anthropic_client: anthropic.Anthropic
    logger: Any
    sleeper: Callable[[float], None] = field(default=time.sleep)


def register(bot: discord.Client, deps: TargetsDeps) -> None:
    def make_service() -> TargetsService:
        return TargetsService(
            client=deps.anthropic_client,
            config=deps.config,
            sleeper=deps.sleeper,
            logger=deps.logger,
        )

    async def on_targets(message: discord.Message) -> None:
        await handle_targets(message, make_service, deps.logger)

    dispatch.register_command(bot, "!targets", on_targets)
