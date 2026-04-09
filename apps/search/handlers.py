import asyncio
from collections.abc import Callable
from typing import Any

import discord

from apps.search.embeds import build_species_embed
from apps.search.services import SearchError, SearchService, SearchTimeout


async def handle_search(
    message: discord.Message,
    make_service: Callable[[], SearchService],
    logger: Any,
) -> None:
    region = message.content.removeprefix("!search").strip()
    if not region:
        await message.channel.send("Please provide a region code: `!search US-CA`")
        return

    await message.channel.send(f"Searching for rare birds in **{region}**...")
    service = make_service()  # fresh per invocation (CLAUDE.md rule)
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, service.search, region)
    except SearchError as e:
        await message.channel.send(f"Agent error: {e}")
        return
    except SearchTimeout:
        await message.channel.send("Agent timed out. Try again shortly.")
        return
    except Exception:
        logger.exception("search failed for region={}", region)
        await message.channel.send("Something went wrong querying the agent.")
        return

    if not data:
        await message.channel.send(f"No rare bird sightings found in **{region}**.")
        return
    for species in data:
        await message.channel.send(embed=build_species_embed(species))
