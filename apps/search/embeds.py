import discord

from apps.search.schemas import Species

MAX_SIGHTINGS = 5


def build_species_embed(species: Species) -> discord.Embed:
    """Build a Discord embed card from a species dict."""
    common_name = species.get("commonName", "Unknown Species")
    sci_name = species.get("scientificName", "")
    bird_url = species.get("allAboutBirdsUrl", "")
    sightings = species.get("sightings", [])

    embed = discord.Embed(
        title=common_name,
        url=bird_url or None,
        description=f"*{sci_name}*" if sci_name else None,
        color=discord.Color.green(),
    )

    for s in sightings[:MAX_SIGHTINGS]:
        location = s.get("locationName", "Unknown location")
        date_time = s.get("dateTime", "")
        checklist_url = s.get("checklistUrl", "")
        maps_url = s.get("googleMapsUrl", "")

        links = []
        if checklist_url:
            links.append(f"[Checklist]({checklist_url})")
        if maps_url:
            links.append(f"[Map]({maps_url})")
        link_text = " | ".join(links)

        value = f"{date_time}"
        if link_text:
            value += f"\n{link_text}"

        embed.add_field(name=location, value=value, inline=False)

    if len(sightings) > MAX_SIGHTINGS:
        embed.set_footer(text=f"+{len(sightings) - MAX_SIGHTINGS} more sighting(s)")

    return embed
