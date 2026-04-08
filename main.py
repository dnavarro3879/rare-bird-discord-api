import os
import time

import anthropic
import discord
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ["DISCORD_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
AGENT_ID = os.environ["AGENT_ID"]
ENVIRONMENT_ID = os.environ["ENVIRONMENT_ID"]

anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)


def query_agent(region: str) -> str:
    session = anthropic_client.beta.sessions.create(
        agent=AGENT_ID,
        environment_id=ENVIRONMENT_ID,
        betas=["managed-agents-2026-04-01"],
    )

    anthropic_client.beta.sessions.events.send(
        session.id,
        events=[
            {"type": "user.message", "content": [{"type": "text", "text": region}]}
        ],
        betas=["managed-agents-2026-04-01"],
    )

    while True:
        events = anthropic_client.beta.sessions.events.list(
            session.id, betas=["managed-agents-2026-04-01"]
        )
        for event in events.data:
            if event.type == "agent.message":
                return event.content[0].text
        time.sleep(3)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if not message.content.startswith("!search"):
        return

    region = message.content.removeprefix("!search").strip()
    if not region:
        await message.channel.send("Please provide a region code: `!search US-CA`")
        return

    await message.channel.send(f"Searching for rare birds in **{region}**...")

    response_text = await bot.loop.run_in_executor(None, query_agent, region)

    # Split response into bird cards
    entries = [e.strip() for e in response_text.split("\n\n") if e.strip()]

    for entry in entries:
        embed = discord.Embed(
            description=entry,
            color=discord.Color.green(),
        )
        await message.channel.send(embed=embed)

    if not entries:
        await message.channel.send("No results found for that region.")


bot.run(DISCORD_TOKEN)
