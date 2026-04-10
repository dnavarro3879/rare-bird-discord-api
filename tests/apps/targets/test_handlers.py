from apps.targets.handlers import handle_targets
from apps.targets.services import TargetsError, TargetsTimeout


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
    """Plain sync service matching TargetsService's interface."""

    def __init__(self, *, result=None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc
        self.calls: list[str] = []

    def targets(self, region: str):
        self.calls.append(region)
        if self._exc is not None:
            raise self._exc
        return self._result


def _make_service_factory(service):
    return lambda: service


async def test_handler_rejects_empty_region():
    message = FakeMessage("!targets")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_targets(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "county-level" in message.channel.sent[0]["content"]
    assert called["count"] == 0  # no service constructed


async def test_handler_rejects_whitespace_only_region():
    message = FakeMessage("!targets   ")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_targets(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "county-level" in message.channel.sent[0]["content"]
    assert called["count"] == 0


async def test_handler_rejects_state_level_region():
    message = FakeMessage("!targets US-CO")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_targets(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "county level" in message.channel.sent[0]["content"]
    assert "US-CO" in message.channel.sent[0]["content"]
    assert called["count"] == 0  # no service constructed


async def test_handler_rejects_country_level_region():
    message = FakeMessage("!targets US")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_targets(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "county level" in message.channel.sent[0]["content"]
    assert called["count"] == 0


async def test_handler_rejects_lowercase_region():
    message = FakeMessage("!targets us-co-013")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_targets(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "county level" in message.channel.sent[0]["content"]
    assert called["count"] == 0


async def test_handler_rejects_garbage_region():
    message = FakeMessage("!targets foo")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubService(result=[])

    await handle_targets(message, factory, logger)

    assert len(message.channel.sent) == 1
    assert "county level" in message.channel.sent[0]["content"]
    assert called["count"] == 0


async def test_handler_sends_finding_message_and_embeds_on_success():
    species = [
        {"commonName": "Robin", "sightings": []},
        {"commonName": "Kestrel", "sightings": []},
    ]
    service = StubService(result=species)
    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, _make_service_factory(service), logger)

    sent = message.channel.sent
    assert len(sent) == 3  # finding message + 2 embeds
    assert "Finding life-list targets" in sent[0]["content"]
    assert "US-CO-013" in sent[0]["content"]
    assert sent[1]["embed"].title == "Robin"
    assert sent[2]["embed"].title == "Kestrel"
    assert service.calls == ["US-CO-013"]


async def test_handler_sends_no_results_message_on_empty_list():
    service = StubService(result=[])
    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "Finding" in message.channel.sent[0]["content"]
    assert "No life-list targets" in message.channel.sent[1]["content"]


async def test_handler_reports_targets_error_as_friendly_message():
    service = StubService(exc=TargetsError("agent blew up"))
    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "Agent error" in message.channel.sent[1]["content"]
    assert "agent blew up" in message.channel.sent[1]["content"]


async def test_handler_reports_targets_timeout_as_friendly_message():
    service = StubService(exc=TargetsTimeout("no message"))
    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "timed out" in message.channel.sent[1]["content"]


async def test_handler_catches_unknown_exception_and_replies_generically():
    service = StubService(exc=RuntimeError("kaboom"))
    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, _make_service_factory(service), logger)

    assert len(message.channel.sent) == 2
    assert "Something went wrong" in message.channel.sent[1]["content"]
    assert len(logger.exceptions) == 1


async def test_handler_constructs_fresh_service_per_call():
    calls = {"count": 0}
    service = StubService(result=[])

    def factory():
        calls["count"] += 1
        return service

    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, factory, logger)

    assert calls["count"] == 1


async def test_handler_uses_max_sightings_ten_for_embeds():
    sightings = [{"locationName": f"L{i}", "dateTime": "x"} for i in range(12)]
    species = [{"commonName": "Robin", "sightings": sightings}]
    service = StubService(result=species)
    message = FakeMessage("!targets US-CO-013")
    logger = NoopLogger()

    await handle_targets(message, _make_service_factory(service), logger)

    # Finding message + 1 species embed
    assert len(message.channel.sent) == 2
    embed = message.channel.sent[1]["embed"]
    assert len(embed.fields) == 10
    assert embed.footer.text == "+2 more sighting(s)"
