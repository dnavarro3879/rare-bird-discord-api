from apps.search.handlers import handle_search
from apps.search.services import SearchError, SearchTimeout


class FakeChannel:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, content=None, embed=None):
        self.sent.append({"content": content, "embed": embed})


class FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content
        self.channel = FakeChannel()


class NoopLogger:
    def __init__(self) -> None:
        self.exceptions: list = []

    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        self.exceptions.append((args, kwargs))


class StubService:
    """A plain sync service with a .search method that matches SearchService."""

    def __init__(self, *, result=None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc
        self.calls: list[str] = []

    def search(self, region: str):
        self.calls.append(region)
        if self._exc is not None:
            raise self._exc
        return self._result


def _make_service_factory(service):
    return lambda: service


async def test_handler_rejects_empty_region():
    message = FakeMessage("!rares")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_search(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "region code" in message.channel.sent[0]["content"]
    assert called["count"] == 0  # should not build a service at all


async def test_handler_sends_searching_message_then_embeds_on_success():
    species = [
        {"commonName": "Robin", "sightings": []},
        {"commonName": "Kestrel", "sightings": []},
    ]
    service = StubService(result=species)
    message = FakeMessage("!rares US-CA")
    logger = NoopLogger()

    await handle_search(message, _make_service_factory(service), logger)

    sent = message.channel.sent
    assert len(sent) == 3  # searching + 2 embeds
    assert "Searching for rare birds" in sent[0]["content"]
    assert sent[1]["embed"] is not None
    assert sent[1]["embed"].title == "Robin"
    assert sent[2]["embed"].title == "Kestrel"
    assert service.calls == ["US-CA"]


async def test_handler_sends_no_results_message_on_empty_list():
    service = StubService(result=[])
    message = FakeMessage("!rares US-CA")
    logger = NoopLogger()

    await handle_search(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "Searching" in message.channel.sent[0]["content"]
    assert "No rare bird sightings" in message.channel.sent[1]["content"]


async def test_handler_reports_search_error_as_friendly_message():
    service = StubService(exc=SearchError("agent blew up"))
    message = FakeMessage("!rares US-CA")
    logger = NoopLogger()

    await handle_search(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "Agent error" in message.channel.sent[1]["content"]
    assert "agent blew up" in message.channel.sent[1]["content"]


async def test_handler_reports_search_timeout_as_friendly_message():
    service = StubService(exc=SearchTimeout("no message"))
    message = FakeMessage("!rares US-CA")
    logger = NoopLogger()

    await handle_search(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "timed out" in message.channel.sent[1]["content"]


async def test_handler_catches_unknown_exception_and_replies_generically():
    service = StubService(exc=RuntimeError("kaboom"))
    message = FakeMessage("!rares US-CA")
    logger = NoopLogger()

    await handle_search(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "Something went wrong" in message.channel.sent[1]["content"]
    assert len(logger.exceptions) == 1


async def test_handler_constructs_fresh_service_per_call():
    calls = {"count": 0}
    service = StubService(result=[])

    def factory():
        calls["count"] += 1
        return service

    message = FakeMessage("!rares US-CA")
    logger = NoopLogger()

    await handle_search(message, factory, logger)

    assert calls["count"] == 1


async def test_handler_strips_whitespace_from_region():
    service = StubService(result=[])
    message = FakeMessage("!rares   US-CA   ")
    logger = NoopLogger()

    await handle_search(message, _make_service_factory(service), logger)

    assert service.calls == ["US-CA"]
