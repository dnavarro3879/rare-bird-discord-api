from typing import Any

from apps.locate import LocateDeps
from apps.locate import register as register_locate
from apps.search import AppDeps
from apps.search import register as register_search
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

    async def send(
        self,
        content: Any = None,
        embed: Any = None,
        view: Any = None,
    ) -> None:
        self.sent.append({"content": content, "embed": embed, "view": view})


class FakeMessage:
    def __init__(self, content: str, author: str = "someone-else") -> None:
        self.content = content
        self.author = author
        self.channel = FakeChannel()


class StubSearchService:
    def search(self, region: str):
        return []


def _config() -> Config:
    return Config(
        discord_token="tok",
        anthropic_api_key="akey",
        agent_id="agent",
        environment_id="env",
    )


def _locate_deps() -> LocateDeps:
    return LocateDeps(
        config=_config(),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
    )


def _search_deps() -> AppDeps:
    return AppDeps(
        config=_config(),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
        sleeper=lambda _s: None,
    )


def test_register_attaches_locate_handler():
    bot = FakeBot()
    register_locate(bot, _locate_deps())  # type: ignore[arg-type]
    assert "on_message" in bot.registered
    assert callable(bot.registered["on_message"])


async def test_on_message_ignores_own_messages():
    bot = FakeBot()
    register_locate(bot, _locate_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("!locate Austin", author="bot-user")
    await on_message(msg)
    assert msg.channel.sent == []


async def test_on_message_ignores_non_locate_messages():
    bot = FakeBot()
    register_locate(bot, _locate_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("hello there")
    await on_message(msg)
    assert msg.channel.sent == []


async def test_on_message_delegates_empty_locate_to_handler():
    bot = FakeBot()
    register_locate(bot, _locate_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("!locate")
    await on_message(msg)
    assert len(msg.channel.sent) == 1
    assert "Please provide a city" in msg.channel.sent[0]["content"]


async def test_register_search_and_locate_coexist():
    bot = FakeBot()
    register_search(bot, _search_deps())  # type: ignore[arg-type]
    register_locate(bot, _locate_deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]

    # !search routes to the search handler (its empty-region path replies
    # with a "region code" rejection)
    search_msg = FakeMessage("!search")
    await on_message(search_msg)
    assert len(search_msg.channel.sent) == 1
    assert "region code" in search_msg.channel.sent[0]["content"]

    # !locate routes to the locate handler (its empty-city path replies
    # with a "Please provide a city" rejection)
    locate_msg = FakeMessage("!locate")
    await on_message(locate_msg)
    assert len(locate_msg.channel.sent) == 1
    assert "Please provide a city" in locate_msg.channel.sent[0]["content"]
