from core.dispatch import register_command


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


class FakeBot:
    def __init__(self) -> None:
        self.user = "bot-user"
        self.registered: dict = {}

    def event(self, fn):
        self.registered[fn.__name__] = fn
        return fn


def _make_capturing_handler():
    calls: list = []

    async def handler(message):
        calls.append(message)

    return handler, calls


def test_register_command_attaches_on_message_once():
    bot = FakeBot()
    handler, _ = _make_capturing_handler()
    register_command(bot, "!search", handler)  # type: ignore[arg-type]
    assert "on_message" in bot.registered
    first_on_message = bot.registered["on_message"]
    # Re-register the same prefix; should not re-attach.
    register_command(bot, "!search", handler)  # type: ignore[arg-type]
    assert bot.registered["on_message"] is first_on_message


def test_register_command_two_prefixes_share_single_on_message():
    bot = FakeBot()
    search_handler, _ = _make_capturing_handler()
    locate_handler, _ = _make_capturing_handler()
    register_command(bot, "!search", search_handler)  # type: ignore[arg-type]
    first_on_message = bot.registered["on_message"]
    register_command(bot, "!locate", locate_handler)  # type: ignore[arg-type]
    assert bot.registered["on_message"] is first_on_message


async def test_dispatcher_routes_prefixes_to_their_handlers():
    bot = FakeBot()
    search_handler, search_calls = _make_capturing_handler()
    locate_handler, locate_calls = _make_capturing_handler()
    register_command(bot, "!search", search_handler)  # type: ignore[arg-type]
    register_command(bot, "!locate", locate_handler)  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]

    search_msg = FakeMessage("!search US-CA")
    locate_msg = FakeMessage("!locate Austin")
    await on_message(search_msg)
    await on_message(locate_msg)

    assert len(search_calls) == 1
    assert search_calls[0] is search_msg
    assert len(locate_calls) == 1
    assert locate_calls[0] is locate_msg


async def test_dispatcher_ignores_messages_authored_by_bot():
    bot = FakeBot()
    handler, calls = _make_capturing_handler()
    register_command(bot, "!search", handler)  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]

    msg = FakeMessage("!search US-CA", author="bot-user")
    await on_message(msg)
    assert calls == []


async def test_dispatcher_returns_silently_on_unmatched_prefix():
    bot = FakeBot()
    handler, calls = _make_capturing_handler()
    register_command(bot, "!search", handler)  # type: ignore[arg-type]
    on_message = bot.registered["on_message"]

    msg = FakeMessage("hello there")
    await on_message(msg)
    assert calls == []
    assert msg.channel.sent == []


async def test_two_separate_bots_have_independent_registries():
    bot_a = FakeBot()
    bot_b = FakeBot()
    handler_a, calls_a = _make_capturing_handler()
    handler_b, calls_b = _make_capturing_handler()

    register_command(bot_a, "!search", handler_a)  # type: ignore[arg-type]
    register_command(bot_b, "!locate", handler_b)  # type: ignore[arg-type]

    # Each bot has its own on_message and registry.
    assert bot_a._command_registry is not bot_b._command_registry  # type: ignore[attr-defined]
    assert "!search" in bot_a._command_registry  # type: ignore[attr-defined]
    assert "!locate" not in bot_a._command_registry  # type: ignore[attr-defined]
    assert "!locate" in bot_b._command_registry  # type: ignore[attr-defined]
    assert "!search" not in bot_b._command_registry  # type: ignore[attr-defined]

    # Firing a !locate message on bot_a should not reach handler_b.
    on_message_a = bot_a.registered["on_message"]
    await on_message_a(FakeMessage("!locate Austin"))
    assert calls_a == []
    assert calls_b == []

    # Firing a !locate on bot_b routes correctly.
    on_message_b = bot_b.registered["on_message"]
    msg = FakeMessage("!locate Austin")
    await on_message_b(msg)
    assert len(calls_b) == 1
