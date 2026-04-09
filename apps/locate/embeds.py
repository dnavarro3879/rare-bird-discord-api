import discord

from apps.locate.schemas import RegionResult


def build_locate_embed(city: str, results: list[RegionResult]) -> discord.Embed:
    """Build a Discord embed listing eBird region codes that match a city."""
    embed = discord.Embed(
        title=f"Regions matching '{city}'",
        description="Click a button below to search that region for rare birds.",
        color=discord.Color.blurple(),
    )

    for i, r in enumerate(results, start=1):
        region_code = r.get("regionCode", "")
        display_name = r.get("displayName") or region_code
        name = f"{i}. {display_name}"
        description = r.get("description")
        if description:
            value = f"`{region_code}`\n{description}"
        else:
            value = f"`{region_code}`"
        embed.add_field(name=name, value=value, inline=False)

    return embed
