from typing import Any

from apps.locate import LocateDeps
from apps.locate import register as register_locate
from apps.search import AppDeps
from apps.search import register as register_search
from apps.targets import TargetsDeps
from apps.targets import register as register_targets
from core.config import Config


class FakeBot:
    def __init__(self) -> None:
        self.user = "bot-user"
        self.registered: dict = {}

    def event(self, fn):
        self.registered[fn.__name__] = fn
        return fn


class FakeAnthropicClient:
    pass


class NoopLogger:
    def info(self, *args: Any, **kwargs: Any) -> None:
        pass

    def debug(self, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, *args: Any, **kwargs: Any) -> None:
        pass

    def exception(self, *args: Any, **kwargs: Any) -> None:
        pass


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, content=None, embed=None, view=None):
        self.sent.append({"content": content, "embed": embed, "view": view})


class FakeMessage:
    def __init__(self, content: str, author: str = "someone-else") -> None:
        self.content = content
        self.author = author
        self.channel = FakeChannel()


class StubSearchService:
    def search(self, region: str):
        return []


class StubTargetsService:
    def targets(self, region: str):
        return []


def _config() -> Config:
    return Config(
        discord_token="tok",
        anthropic_api_key="akey",
        agent_id="agent",
        environment_id="env",
    )


def _targets_deps() -> TargetsDeps:
    return TargetsDeps(
        config=_config(),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
        sleeper=lambda _s: None,
    )


def _search_deps() -> AppDeps:
    return AppDeps(
        config=_config(),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
        sleeper=lambda _s: None,
    )


def _locate_deps() -> LocateDeps:
    return LocateDeps(
        config=_config(),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        make_targets_service=lambda: StubTargetsService(),  # type: ignore[return-value]
    )


def test_register_attaches_targets_handler():
    bot = FakeBot()
    register_targets(bot, _targets_deps())  # type: ignore[arg-type]
    assert "on_message" in bot.registered
    assert callable(bot.registered["on_message"])


async def test_on_message_ignores_own_messages():
    bot = FakeBot()
    register_targets(bot, _targets_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("!targets US-CO-013", author="bot-user")
    await on_message(msg)
    assert msg.channel.sent == []


async def test_on_message_ignores_non_targets_messages():
    bot = FakeBot()
    register_targets(bot, _targets_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("hello there")
    await on_message(msg)
    assert msg.channel.sent == []


async def test_on_message_delegates_empty_targets_to_handler():
    bot = FakeBot()
    register_targets(bot, _targets_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("!targets")
    await on_message(msg)
    assert len(msg.channel.sent) == 1
    assert "county-level" in msg.channel.sent[0]["content"]


async def test_register_targets_coexists_with_rares_and_locate():
    bot = FakeBot()
    register_search(bot, _search_deps())  # type: ignore[arg-type]
    register_targets(bot, _targets_deps())  # type: ignore[arg-type]
    register_locate(bot, _locate_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]

    # !rares routes to search handler -> empty-region rejection
    rares_msg = FakeMessage("!rares")
    await on_message(rares_msg)
    assert len(rares_msg.channel.sent) == 1
    assert "region code" in rares_msg.channel.sent[0]["content"]

    # !targets routes to targets handler -> empty-region rejection
    targets_msg = FakeMessage("!targets")
    await on_message(targets_msg)
    assert len(targets_msg.channel.sent) == 1
    assert "county-level" in targets_msg.channel.sent[0]["content"]

    # !locate routes to locate handler -> empty-city rejection
    locate_msg = FakeMessage("!locate")
    await on_message(locate_msg)
    assert len(locate_msg.channel.sent) == 1
    assert "Please provide a city" in locate_msg.channel.sent[0]["content"]


def test_targets_deps_defaults_sleeper_to_time_sleep():
    import time as time_module

    deps = TargetsDeps(
        config=_config(),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
    )
    assert deps.sleeper is time_module.sleep
