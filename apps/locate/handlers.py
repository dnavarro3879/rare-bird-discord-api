import asyncio
from collections.abc import Callable
from typing import Any

import discord

from apps.locate.embeds import build_locate_embed
from apps.locate.services import LocateError, LocateService, LocateTimeout
from apps.locate.views import RegionButtonsView
from apps.search.services import SearchService
from apps.targets.services import TargetsService


async def handle_locate(
    message: discord.Message,
    make_service: Callable[[], LocateService],
    make_search_service: Callable[[], SearchService],
    make_targets_service: Callable[[], TargetsService],
    logger: Any,
) -> None:
    city = message.content.removeprefix("!locate").strip()
    if not city:
        await message.channel.send("Please provide a city: `!locate Austin`")
        return

    await message.channel.send(f"Looking up eBird regions for **{city}**...")
    service = make_service()  # fresh per invocation (CLAUDE.md rule)
    loop = asyncio.get_running_loop()
    try:
        results = await loop.run_in_executor(None, service.locate, city)
    except LocateError as e:
        await message.channel.send(f"Locate error: {e}")
        return
    except LocateTimeout:
        await message.channel.send("Locate timed out. Try again shortly.")
        return
    except Exception:
        logger.exception("locate failed for city={}", city)
        await message.channel.send("Something went wrong looking up the city.")
        return

    if not results:
        await message.channel.send(f"No regions found for **{city}**.")
        return

    embed = build_locate_embed(city, results)
    view = RegionButtonsView(
        results=results,
        make_search_service=make_search_service,
        make_targets_service=make_targets_service,
        logger=logger,
    )
    await message.channel.send(embed=embed, view=view)
