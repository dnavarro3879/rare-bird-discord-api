# rare-bird-discord-api

A Discord bot that surfaces recent rare bird sightings for a given region. Users post `!rares US-CA` in a channel; the bot replies with embed cards for each rare species, including location, date/time, and links to the eBird checklist, Google Maps, and All About Birds.

The bot itself does not call eBird directly — all data fetching, parsing, and shaping is delegated to an [Anthropic Managed Agent](https://docs.anthropic.com/) that the bot communicates with via the `client.beta.sessions` API. The Discord layer is responsible only for routing messages, presenting results, and surfacing errors.

## Architecture at a glance

```
main.py                  composition root: load config → build bot → register apps → run
core/                    cross-cutting infrastructure (config, logging, anthropic client factory)
apps/search/             the !rares feature, self-contained and registered into the bot
    services.py          business logic — managed-agent session lifecycle (sync, dependency-injected)
    handlers.py          Discord-facing layer; owns the run_in_executor boundary
    embeds.py            pure dict → discord.Embed
    schemas.py           TypedDicts for the agent contract
    __init__.py          register(bot, deps) entry point
tests/                   pytest suite, mirrors source layout
```

Architectural rules and the rationale behind them are documented in [`CLAUDE.md`](CLAUDE.md). The short version: `main.py` is a thin composition root, each feature lives in its own `apps/<name>/` package exposing one `register(bot, deps)` function, and services are constructor-injected so they're fully unit-testable without touching the network.

## Prerequisites

- **Python 3.12+** (the project pins `>=3.12` in `pyproject.toml` and ships a `.python-version` file)
- **[uv](https://docs.astral.sh/uv/)** for dependency and environment management — `brew install uv` on macOS, or see the upstream install instructions
- A **Discord application + bot token** with the `Message Content Intent` enabled ([Discord Developer Portal](https://discord.com/developers/applications))
- An **Anthropic API key** with access to the Managed Agents beta
- A **pre-created Anthropic Managed Agent** that knows how to fetch rare bird sightings and return them in the expected JSON shape (see "Agent contract" below). You'll need its agent ID and environment ID.

## Setup

```bash
git clone <this-repo>
cd rare-bird-discord-api

# 1. Create the virtual environment FIRST (always uv venv before any other uv command)
uv venv

# 2. Install dependencies (including dev tools)
uv sync

# 3. Create your .env file
cp .env.example .env   # if an example exists; otherwise create .env from scratch
```

Required environment variables in `.env`:

```
DISCORD_TOKEN=...
ANTHROPIC_API_KEY=...
AGENT_ID=...
ENVIRONMENT_ID=...
```

The bot will fail at startup if any of these are missing — there is no silent fallback.

## Running locally

```bash
uv run python main.py
```

Then, in a Discord channel where the bot has been invited and granted message access, post:

```
!rares US-CA
```

The bot will reply with `Searching for rare birds in **US-CA**...` and then post one embed per species. If the agent returns no sightings, you'll get a "no rare bird sightings found" message instead. If the agent errors out or times out (6-minute ceiling), you'll get a friendly error reply.

Region codes follow the eBird convention: country (`US`), state/subnational1 (`US-CA`), or county/subnational2 (`US-CA-001`).

## Commands

### `!rares <region>`

Look up rare bird sightings in a known eBird region code. Example:

```
!rares US-TX-453
```

Returns one embed per species as described above.

### `!targets <countyRegionCode>`

Look up species seen in a county in the last 72 hours that are **not** on
the configured eBird life list (life-list "targets"). County-level region
codes only (e.g. `US-CO-013`); state- or country-level codes are rejected
up front with a friendly error and no agent call is made. Example:

```
!targets US-CO-013
```

Returns one embed per unsighted species with up to ten most-recent
checklists each. If the agent has no targets to report, the bot replies
with a "no life-list targets found" message. The underlying eBird life-list
fetch is handled by the managed agent, so `EBIRD_API_KEY` must be
configured on the agent side — the bot does not read it.

### `!locate <city>`

Resolve a free-form city name into up to three eBird region codes (the region containing the city plus up to two nearby regions), then click a button to run `!rares` or `!targets` against the region you want. Example:

```
!locate Austin
```

The bot replies with a single embed listing up to three candidates. Each result gets a Rares button; county-level results also get a Targets button on the same row. Clicking a button runs the same flow that the typed command uses and posts the species embeds back in the same channel.

`!locate` is implemented via `client.messages.create` with Anthropic's server-side `web_search` tool (capped at 3 web searches per request) because county-level FIPS codes are not reliably recallable from parametric knowledge and must be verified online. This makes `!locate` more expensive per call than `!rares`; use it for discovery and `!rares` directly when you already know the region code.

The default model is `claude-sonnet-4-5`. To override, set the optional `CLAUDE_MODEL` environment variable in your `.env` file — this is the only new env var for `!locate` and it is not required.

## Testing

The test suite uses `pytest` + `pytest-cov` + `pytest-asyncio`. Coverage is enforced at **≥85%** on `apps/` and `core/` (the composition root in `main.py` is excluded).

```bash
# Run the full suite with coverage
uv run pytest

# Run a single test file
uv run pytest tests/apps/search/test_services.py

# Run a single test
uv run pytest tests/apps/search/test_services.py::test_search_returns_species_list_on_first_poll

# HTML coverage report (writes to htmlcov/)
uv run pytest --cov-report=html
```

Tests are hermetic: zero network, zero `time.sleep`, and the Anthropic SDK is faked at the dependency boundary. The injected sleeper in `SearchService` means polling-loop tests run instantly with deterministic event sequences.

## Linting and formatting

```bash
uv run ruff check          # lint
uv run ruff format         # apply formatting
uv run ruff format --check # verify formatting without writing
```

Ruff is configured in `pyproject.toml` with the `E`, `F`, `I`, and `UP` rule sets.

## Deployment

The bot runs as a long-lived process — there is no HTTP surface. The included `Procfile` declares a single `worker` dyno:

```
worker: python main.py
```

Any platform that supports Procfile-style worker processes (Heroku, Railway, Fly.io, Render background workers, etc.) can run the bot directly. Set the four environment variables in the platform's config and deploy.

## Agent contract

The Managed Agent must accept a region code as a `user.message` and respond with a single `agent.message` whose text content is a JSON document. Two shapes are accepted:

**Success** — a JSON list of species:

```json
[
  {
    "commonName": "California Condor",
    "scientificName": "Gymnogyps californianus",
    "allAboutBirdsUrl": "https://www.allaboutbirds.org/...",
    "sightings": [
      {
        "locationName": "Pinnacles National Park",
        "dateTime": "2026-04-08 14:32",
        "checklistUrl": "https://ebird.org/checklist/...",
        "googleMapsUrl": "https://maps.google.com/..."
      }
    ]
  }
]
```

**Failure** — a JSON object with an `error` key:

```json
{ "error": "invalid region code" }
```

Changes to this contract must be coordinated with the agent's prompt/tools, not just the embed builder on the Discord side. Field shapes are defined as `TypedDict`s in `apps/search/schemas.py`.
