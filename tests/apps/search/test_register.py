from apps.search import AppDeps, register
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
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, content=None, embed=None):
        self.sent.append({"content": content, "embed": embed})


class FakeMessage:
    def __init__(self, content: str, author: str) -> None:
        self.content = content
        self.author = author
        self.channel = FakeChannel()


def _deps() -> AppDeps:
    return AppDeps(
        config=Config(
            discord_token="tok",
            anthropic_api_key="akey",
            agent_id="agent",
            environment_id="env",
        ),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
        sleeper=lambda _s: None,
    )


def test_register_attaches_on_message_handler():
    bot = FakeBot()
    register(bot, _deps())  # type: ignore[arg-type]
    assert "on_message" in bot.registered
    assert callable(bot.registered["on_message"])


async def test_on_message_ignores_own_messages():
    bot = FakeBot()
    register(bot, _deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("!rares US-CA", author="bot-user")
    await on_message(msg)
    assert msg.channel.sent == []


async def test_on_message_ignores_non_search_messages():
    bot = FakeBot()
    register(bot, _deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("hello there", author="someone-else")
    await on_message(msg)
    assert msg.channel.sent == []


async def test_on_message_delegates_empty_search_to_handler():
    bot = FakeBot()
    register(bot, _deps())  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]
    msg = FakeMessage("!rares", author="someone-else")
    await on_message(msg)
    assert len(msg.channel.sent) == 1
    assert "region code" in msg.channel.sent[0]["content"]


def test_app_deps_defaults_sleeper_to_time_sleep():
    import time as time_module

    deps = AppDeps(
        config=Config(
            discord_token="tok",
            anthropic_api_key="akey",
            agent_id="agent",
            environment_id="env",
        ),
        anthropic_client=FakeAnthropicClient(),  # type: ignore[arg-type]
        logger=NoopLogger(),
    )
    assert deps.sleeper is time_module.sleep
