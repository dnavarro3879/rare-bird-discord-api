import asyncio
from collections.abc import Callable
from typing import Any

import discord

from apps.locate.schemas import RegionResult
from apps.search.embeds import build_species_embed
from apps.search.services import SearchError, SearchService, SearchTimeout

_MAX_LABEL_LEN = 80


class RegionButtonsView(discord.ui.View):
    def __init__(
        self,
        results: list[RegionResult],
        make_search_service: Callable[[], SearchService],
        logger: Any,
        *,
        timeout: float = 600.0,
    ) -> None:
        super().__init__(timeout=timeout)
        self._make_search_service = make_search_service
        self._logger = logger
        for i, r in enumerate(results, start=1):
            self.add_item(_RegionButton(index=i, result=r, parent=self))


class _RegionButton(discord.ui.Button):
    def __init__(
        self,
        *,
        index: int,
        result: RegionResult,
        parent: RegionButtonsView,
    ) -> None:
        region_code = result.get("regionCode", "")
        display_name = result.get("displayName") or region_code
        label = f"{index}. {display_name}"[:_MAX_LABEL_LEN]
        custom_id = f"locate:{region_code}:{index}"
        super().__init__(
            label=label,
            custom_id=custom_id,
            style=discord.ButtonStyle.primary,
        )
        self._parent = parent
        self._region_code = region_code

    async def callback(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)
        service = self._parent._make_search_service()
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(None, service.search, self._region_code)
        except SearchError as e:
            await interaction.followup.send(f"Agent error: {e}")
            return
        except SearchTimeout:
            await interaction.followup.send("Agent timed out. Try again shortly.")
            return
        except Exception:
            self._parent._logger.exception(
                "locate-button search failed for region={}", self._region_code
            )
            await interaction.followup.send("Something went wrong querying the agent.")
            return

        if not data:
            await interaction.followup.send(
                f"No rare bird sightings found in {self._region_code}."
            )
            return
        for species in data:
            await interaction.followup.send(embed=build_species_embed(species))
