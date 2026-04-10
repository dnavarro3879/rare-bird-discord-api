from typing import Any

from apps.locate.handlers import handle_locate
from apps.locate.services import LocateError, LocateTimeout


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
    def __init__(self, content: str) -> None:
        self.content = content
        self.channel = FakeChannel()


class NoopLogger:
    def __init__(self) -> None:
        self.exceptions: list = []

    def info(self, *args: Any, **kwargs: Any) -> None:
        pass

    def debug(self, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, *args: Any, **kwargs: Any) -> None:
        pass

    def exception(self, *args: Any, **kwargs: Any) -> None:
        self.exceptions.append((args, kwargs))


class StubLocateService:
    def __init__(
        self,
        *,
        result: list | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._result = result
        self._exc = exc
        self.calls: list[str] = []

    def locate(self, city: str):
        self.calls.append(city)
        if self._exc is not None:
            raise self._exc
        return self._result if self._result is not None else []


class StubSearchService:
    def search(self, region: str):
        return []


class StubTargetsService:
    def targets(self, region: str):
        return []


def _make_search_service_factory():
    return lambda: StubSearchService()


def _make_targets_service_factory():
    return lambda: StubTargetsService()


async def test_handler_rejects_empty_city():
    message = FakeMessage("!locate")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubLocateService(result=[])

    await handle_locate(
        message,
        factory,
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )  # type: ignore[arg-type]

    assert len(message.channel.sent) == 1
    assert "Please provide a city" in message.channel.sent[0]["content"]
    assert called["count"] == 0


async def test_handler_rejects_whitespace_only_city():
    message = FakeMessage("!locate   ")
    logger = NoopLogger()

    called = {"count": 0}

    def factory():
        called["count"] += 1
        return StubLocateService(result=[])

    await handle_locate(
        message,
        factory,
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )  # type: ignore[arg-type]

    assert len(message.channel.sent) == 1
    assert "Please provide a city" in message.channel.sent[0]["content"]
    assert called["count"] == 0


async def test_handler_passes_multi_word_city_intact_to_service():
    service = StubLocateService(
        result=[{"regionCode": "MX-CMX", "displayName": "Mexico City"}]
    )
    message = FakeMessage("!locate Mexico City")
    logger = NoopLogger()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )

    assert service.calls == ["Mexico City"]


async def test_handler_success_sends_looking_up_then_embed_with_view():
    results = [
        {
            "regionCode": "US-TX-453",
            "displayName": "Travis County",
            "description": "Austin",
        },
    ]
    service = StubLocateService(result=results)
    message = FakeMessage("!locate Austin")
    logger = NoopLogger()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )

    sent = message.channel.sent
    assert len(sent) == 2
    assert "Looking up" in sent[0]["content"]
    assert "Austin" in sent[0]["content"]
    assert sent[1]["embed"] is not None
    assert "Austin" in sent[1]["embed"].title
    assert sent[1]["view"] is not None


async def test_handler_reports_locate_error_as_friendly_message():
    service = StubLocateService(exc=LocateError("agent blew up"))
    message = FakeMessage("!locate Austin")
    logger = NoopLogger()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )

    sent = message.channel.sent
    assert len(sent) == 2
    assert "Locate error" in sent[1]["content"]
    assert "agent blew up" in sent[1]["content"]
    assert sent[1]["embed"] is None


async def test_handler_reports_locate_timeout_as_friendly_message():
    service = StubLocateService(exc=LocateTimeout("slow"))
    message = FakeMessage("!locate Austin")
    logger = NoopLogger()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )

    sent = message.channel.sent
    assert len(sent) == 2
    assert "timed out" in sent[1]["content"]
    assert sent[1]["embed"] is None


async def test_handler_catches_generic_exception_and_logs():
    service = StubLocateService(exc=RuntimeError("kaboom"))
    message = FakeMessage("!locate Austin")
    logger = NoopLogger()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )

    sent = message.channel.sent
    assert len(sent) == 2
    assert "Something went wrong" in sent[1]["content"]
    assert len(logger.exceptions) == 1


async def test_handler_empty_results_sends_no_regions_found_message():
    service = StubLocateService(result=[])
    message = FakeMessage("!locate Nowhere")
    logger = NoopLogger()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )

    sent = message.channel.sent
    assert len(sent) == 2
    assert "No regions found" in sent[1]["content"]
    assert sent[1]["embed"] is None


async def test_handler_constructs_fresh_locate_service_per_call():
    calls = {"count": 0}

    def factory():
        calls["count"] += 1
        return StubLocateService(result=[])

    message = FakeMessage("!locate Austin")
    logger = NoopLogger()

    await handle_locate(
        message,
        factory,
        _make_search_service_factory(),
        _make_targets_service_factory(),
        logger,
    )  # type: ignore[arg-type]

    assert calls["count"] == 1


async def test_handler_constructs_view_with_make_targets_service():
    results = [
        {
            "regionCode": "US-TX-453",
            "displayName": "Travis County",
            "description": "Austin",
        },
    ]
    service = StubLocateService(result=results)
    message = FakeMessage("!locate Austin")
    logger = NoopLogger()

    targets_factory_calls = {"count": 0}

    def make_targets_service():
        targets_factory_calls["count"] += 1
        return StubTargetsService()

    await handle_locate(
        message,
        lambda: service,  # type: ignore[arg-type,return-value]
        _make_search_service_factory(),
        make_targets_service,  # type: ignore[arg-type]
        logger,
    )

    sent = message.channel.sent
    assert sent[1]["view"] is not None
    view = sent[1]["view"]
    # The view holds the make_targets_service factory via its buttons; each
    # button gets a reference to _make_targets_service.
    for child in view.children:
        assert child._make_targets_service is make_targets_service  # type: ignore[attr-defined]
