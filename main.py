import json
import os
import time

import anthropic
import discord
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
AGENT_ID = os.environ["AGENT_ID"]
ENVIRONMENT_ID = os.environ["ENVIRONMENT_ID"]

logger.info("Environment variables loaded")

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


def query_agent(region: str) -> list | dict:
    """Returns a list of species dicts, an error dict, or raises on timeout."""
    logger.info("Creating agent session for region={}", region)
    session = anthropic_client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
        betas=["managed-agents-2026-04-01"],
    )
    logger.info("Session created: {}", session.id)

    anthropic_client.beta.sessions.events.send(
        session.id,
        events=[
            {"type": "user.message", "content": [{"type": "text", "text": region}]}
        ],
        betas=["managed-agents-2026-04-01"],
    )
    logger.info("Region code sent to agent")

    poll_count = 0
    while True:
        poll_count += 1
        events = anthropic_client.beta.sessions.events.list(
            session.id, betas=["managed-agents-2026-04-01"]
        )
        for event in events.data:
            if event.type == "agent.message":
                raw = event.content[0].text
                logger.info(
                    "Agent responded after {} polls ({} chars)",
                    poll_count,
                    len(raw),
                )
                return json.loads(raw)
        logger.debug("Poll {} — no response yet, waiting 3s", poll_count)
        time.sleep(3)


def build_embed(species: dict) -> discord.Embed:
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

    for s in sightings[:5]:
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

    if len(sightings) > 5:
        embed.set_footer(text=f"+{len(sightings) - 5} more sighting(s)")

    return embed


@bot.event
async def on_ready():
    logger.info("Logged in as {} (ID: {})", bot.user, bot.user.id)


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not message.content.startswith("!search"):
        return

    region = message.content.removeprefix("!search").strip()
    logger.info(
        "Search request from {}#{} in #{}: region={}",
        message.author,
        message.author.discriminator,
        message.channel,
        region,
    )

    if not region:
        logger.warning("Empty region code provided")
        await message.channel.send("Please provide a region code: `!search US-CA`")
        return

    await message.channel.send(f"Searching for rare birds in **{region}**...")

    try:
        data = await bot.loop.run_in_executor(None, query_agent, region)
    except Exception:
        logger.exception("Agent query failed for region={}", region)
        await message.channel.send("Something went wrong querying the agent.")
        return

    # Handle error responses from the agent
    if isinstance(data, dict):
        error_msg = data.get("error", "Unknown error from agent")
        logger.error("Agent returned error for region={}: {}", region, error_msg)
        await message.channel.send(f"Agent error: {error_msg}")
        return

    logger.info("Got {} species for region={}", len(data), region)

    if not data:
        await message.channel.send(f"No rare bird sightings found in **{region}**.")
        return

    for species in data:
        embed = build_embed(species)
        await message.channel.send(embed=embed)


bot.run(DISCORD_TOKEN)
