# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

This project uses [uv](https://docs.astral.sh/uv/) for dependency management. All commands must be run via `uv run` so they pick up the locked environment.

- Install deps: `uv sync`
- Run the bot locally: `uv run python main.py`
- Lint: `uv run ruff check`
- Format: `uv run ruff format`
- Run all tests with coverage: `uv run pytest`
- Run a single test: `uv run pytest tests/apps/search/test_services.py::test_query_agent_returns_species`
- Run a single test file: `uv run pytest tests/apps/search/test_services.py`
- Coverage HTML report: `uv run pytest --cov-report=html` (writes to `htmlcov/`)

`pytest` and `pytest-cov` are required dev dependencies; coverage configuration (source roots, omit patterns, fail-under threshold) lives in `pyproject.toml` under `[tool.pytest.ini_options]` and `[tool.coverage.*]`. The coverage floor is enforced — `pytest` must exit non-zero if coverage drops below the configured threshold (target: **≥85%** line coverage on application code, excluding `main.py` composition root).

## Required environment variables

Loaded from `.env` via `python-dotenv`. Missing values must fail loudly at startup, not silently at first use.

- `DISCORD_TOKEN` — Discord bot token
- `ANTHROPIC_API_KEY`
- `AGENT_ID` — ID of the pre-created Anthropic Managed Agent
- `ENVIRONMENT_ID` — Managed Agent environment ID

Environment access must go through a single config module (e.g. `core/config.py`). **Do not** read `os.environ` from handlers, services, or embed builders — inject the resolved config object instead. This is what makes services testable without monkey-patching the environment.

## Architecture

### Big picture

The project is a long-lived Discord bot worker (see `Procfile` — deployed as a `worker` dyno, not a web service; an earlier Flask version was replaced in commit `2151b48`). The bot itself does **not** call eBird or any bird API directly — all data fetching, parsing, and shaping lives inside an Anthropic **Managed Agent**, accessed via `client.beta.sessions` with the beta header `managed-agents-2026-04-01`. That header must be passed on every call to the beta API.

The end-to-end flow for `!search <region>` is: Discord message → handler → search service → managed-agent session (create → send `user.message` → poll `events.list` until an `agent.message` arrives) → JSON parse → embed builder → Discord reply. The agent returns either a JSON **list** of species dicts (success) or a JSON **dict** with an `error` key (failure); both branches must be handled at the service layer, not in the Discord handler.

Expected species shape (this is the contract with the agent — changes must be coordinated with the agent's prompt/tools, not just the embed builder): `commonName`, `scientificName`, `allAboutBirdsUrl`, and a `sightings` list whose items have `locationName`, `dateTime`, `checklistUrl`, `googleMapsUrl`.

### Required module layout

`main.py` is a thin **composition root** only. It loads config, builds the Discord client, and registers apps. It must contain no business logic, no Discord event handlers, no Anthropic calls, and no JSON parsing. The current single-file `main.py` predates this rule and should be progressively decomposed as new work touches it.

Target layout:

```
main.py                          # composition root: load config → build bot → register apps → run
core/
    config.py                    # env loading, typed config object
    logging.py                   # loguru sink configuration
    anthropic_client.py          # factory for the Anthropic client
apps/
    search/
        __init__.py              # exposes `register(bot, deps)` — wires handlers into the bot
        handlers.py              # Discord event handlers (thin — parse, delegate, format reply)
        services.py              # business logic; takes deps via constructor
        embeds.py                # presentation: dict → discord.Embed
        schemas.py               # dataclasses / TypedDicts for the agent contract
tests/
    apps/search/
        test_services.py
        test_embeds.py
        test_handlers.py
    core/
        test_config.py
```

### App registration pattern

Each app is a self-contained package under `apps/` that exposes a single entry point:

```python
# apps/search/__init__.py
def register(bot: discord.Client, deps: AppDeps) -> None:
    """Wire this app's handlers into the given bot."""
```

`main.py` calls `register(...)` for every app it wants enabled. Adding a new feature means creating a new app package and adding one `register(...)` line — **never** editing handler code in `main.py`. This is the "apps merely registered into main.py" rule and it is load-bearing for keeping the composition root small and the apps independently testable.

### Scoped service/handler layering

Three layers, each with a strict responsibility:

1. **Handlers** (`handlers.py`) — Discord-facing. Parse the incoming message, validate inputs, call the service, format the result back into Discord primitives. Handlers must not import `anthropic`, must not call `json.loads`, and must not contain polling loops. Keep them thin enough to read in one screen.
2. **Services** (`services.py`) — Business logic. Own the Anthropic session lifecycle, polling, JSON parsing, and the success/error discrimination. Services receive their dependencies (Anthropic client, config, logger, clock/sleeper) via the constructor — **no module-level globals, no `os.environ` reads, no `time.sleep` imported at module scope**. This is what makes them unit-testable with fakes.
3. **Presentation** (`embeds.py`) — Pure functions: `dict → discord.Embed`. No I/O, no network, no logging side effects. Easy to test exhaustively.

"Scoped" means a fresh service instance is constructed per handler invocation (or per request scope), with its dependencies injected. Do not cache services as module-level singletons — that prevents per-request logging context and makes tests order-dependent.

The blocking polling loop in the search service must continue to run inside `bot.loop.run_in_executor(...)` so it does not block the Discord event loop. The executor boundary belongs in the handler, not the service — the service stays synchronous and ignorant of asyncio.

## Code quality standards

- **SOLID / DRY**: each module has one reason to change. If a service grows a second responsibility (e.g. search service starts handling user preferences), split it before adding more code. Extract a helper the second time you'd copy-paste a block, not the first.
- **Pythonic**: prefer dataclasses or `TypedDict` over raw dicts for anything that crosses a module boundary; use `pathlib`, f-strings, comprehensions, and context managers; raise specific exceptions, never bare `except:`. Type-hint every public function — `ruff` is configured with `UP` (pyupgrade) and `I` (isort) rules and they must pass.
- **No catch-all exception handling around business logic**. The Discord handler is the one place that catches broad exceptions (to keep the bot alive and surface a friendly message); services should let exceptions propagate so tests can assert on them.
- **Logging**: use `loguru`'s structured fields, not f-string interpolation, so log lines remain greppable. Tag every search-related log with the region and (where available) the session id so a single search can be traced end-to-end.

## Testing requirements

- **Framework**: `pytest` + `pytest-cov`. No `unittest.TestCase` subclasses.
- **Coverage**: enforced ≥85% on `apps/` and `core/` (configure `--cov=apps --cov=core --cov-fail-under=85` in `pyproject.toml`). `main.py` is excluded as a composition root.
- **Test layout** mirrors source layout under `tests/`. One test file per source file.
- **No network in tests**. The Anthropic client is injected, so services are tested with a fake client that returns canned event sequences. Do not use `responses`/`httpx_mock` against the real SDK — fake at the dependency boundary, not the HTTP boundary.
- **No `time.sleep` in tests**. Inject a sleeper (e.g. a `Callable[[float], None]`) into the service so polling loops can be tested instantly with a no-op sleeper and a deterministic event sequence.
- **Embed tests** assert on the constructed `discord.Embed` fields directly — no Discord client needed.
- **Handler tests** use a fake bot/message and assert on what the handler sends back; they should not exercise the real service.
- Every new service method and every new branch in an embed builder requires a test in the same PR. PRs that drop coverage below the threshold will fail CI.
