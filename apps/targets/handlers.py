import asyncio
from collections.abc import Callable
from typing import Any

import discord

from apps.search.embeds import build_species_embed
from apps.targets.region import is_county_region
from apps.targets.services import TargetsError, TargetsService, TargetsTimeout


async def handle_targets(
    message: discord.Message,
    make_service: Callable[[], TargetsService],
    logger: Any,
) -> None:
    region = message.content.removeprefix("!targets").strip()
    if not region:
        await message.channel.send(
            "Please provide a county-level region code: `!targets US-CO-013`"
        )
        return
    if not is_county_region(region):
        await message.channel.send(
            f"`!targets` only works at the county level (e.g. `US-CO-013`). "
            f"`{region}` is too broad. Use `!locate <city>` to find a county code."
        )
        return

    await message.channel.send(
        f"Finding life-list targets in **{region}** (last 72h)..."
    )
    service = make_service()  # fresh per invocation (CLAUDE.md rule)
    loop = asyncio.get_running_loop()
    try:
        data = await loop.run_in_executor(None, service.targets, region)
    except TargetsError as e:
        await message.channel.send(f"Agent error: {e}")
        return
    except TargetsTimeout:
        await message.channel.send("Agent timed out. Try again shortly.")
        return
    except Exception:
        logger.exception("targets failed for region={}", region)
        await message.channel.send("Something went wrong querying the agent.")
        return

    if not data:
        await message.channel.send(f"No life-list targets found in **{region}**.")
        return
    for species in data:
        await message.channel.send(embed=build_species_embed(species, max_sightings=10))
