from typing import Any

import discord

from apps.locate.views import RegionButtonsView
from apps.search.services import SearchError, SearchTimeout


class FakeResponse:
    def __init__(self) -> None:
        self.deferred = False
        self.deferred_kwargs: dict = {}

    async def defer(self, **kwargs: Any) -> None:
        self.deferred = True
        self.deferred_kwargs = kwargs


class FakeFollowup:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send(self, content: Any = None, embed: Any = None) -> None:
        self.sent.append({"content": content, "embed": embed})


class FakeInteraction:
    def __init__(self) -> None:
        self.response = FakeResponse()
        self.followup = FakeFollowup()


class StubSearchService:
    def __init__(
        self,
        *,
        result: list | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._result = result
        self._exc = exc
        self.calls: list[str] = []

    def search(self, region: str):
        self.calls.append(region)
        if self._exc is not None:
            raise self._exc
        return self._result if self._result is not None else []


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


def _three_results() -> list[dict]:
    return [
        {"regionCode": "US-TX-453", "displayName": "Travis County, Texas, US"},
        {"regionCode": "US-TX-491", "displayName": "Williamson County, Texas, US"},
        {"regionCode": "US-TX", "displayName": "Texas, US"},
    ]


def _species() -> list[dict]:
    return [
        {"commonName": "Robin", "sightings": []},
        {"commonName": "Kestrel", "sightings": []},
    ]


def test_three_results_yields_three_buttons_with_numbered_labels():
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    buttons = [c for c in view.children]
    assert len(buttons) == 3
    labels = [b.label for b in buttons]  # type: ignore[attr-defined]
    assert labels[0].startswith("1. ")
    assert labels[1].startswith("2. ")
    assert labels[2].startswith("3. ")


def test_one_result_yields_one_button():
    view = RegionButtonsView(
        results=[{"regionCode": "AQ", "displayName": "Antarctica"}],  # type: ignore[list-item]
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    assert len(view.children) == 1


def test_button_custom_id_contains_region_code():
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    ids = [c.custom_id for c in view.children]  # type: ignore[attr-defined]
    assert ids[0] == "locate:US-TX-453:1"
    assert ids[1] == "locate:US-TX-491:2"
    assert ids[2] == "locate:US-TX:3"


async def test_callback_defers_then_sends_species_embeds_via_followup():
    stub = StubSearchService(result=_species())
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: stub,  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    button = view.children[0]
    interaction = FakeInteraction()
    await button.callback(interaction)  # type: ignore[attr-defined]
    assert interaction.response.deferred
    assert interaction.response.deferred_kwargs == {"thinking": True}
    # Two species embeds sent via followup
    assert len(interaction.followup.sent) == 2
    assert interaction.followup.sent[0]["embed"] is not None
    assert interaction.followup.sent[0]["embed"].title == "Robin"
    assert interaction.followup.sent[1]["embed"].title == "Kestrel"


async def test_callback_uses_clicked_buttons_region_code():
    stub = StubSearchService(result=[])
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: stub,  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    # Click the third button
    button = view.children[2]
    interaction = FakeInteraction()
    await button.callback(interaction)  # type: ignore[attr-defined]
    assert stub.calls == ["US-TX"]


async def test_callback_handles_search_error_with_friendly_followup():
    stub = StubSearchService(exc=SearchError("agent failed"))
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: stub,  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    button = view.children[0]
    interaction = FakeInteraction()
    await button.callback(interaction)  # type: ignore[attr-defined]
    assert len(interaction.followup.sent) == 1
    assert "Agent error" in interaction.followup.sent[0]["content"]


async def test_callback_handles_search_timeout_with_friendly_followup():
    stub = StubSearchService(exc=SearchTimeout("boom"))
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: stub,  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    button = view.children[0]
    interaction = FakeInteraction()
    await button.callback(interaction)  # type: ignore[attr-defined]
    assert len(interaction.followup.sent) == 1
    assert "timed out" in interaction.followup.sent[0]["content"]


async def test_callback_handles_generic_exception_with_logger_and_followup():
    stub = StubSearchService(exc=RuntimeError("kaboom"))
    logger = NoopLogger()
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: stub,  # type: ignore[return-value]
        logger=logger,
    )
    button = view.children[0]
    interaction = FakeInteraction()
    await button.callback(interaction)  # type: ignore[attr-defined]
    assert len(interaction.followup.sent) == 1
    assert "Something went wrong" in interaction.followup.sent[0]["content"]
    assert len(logger.exceptions) == 1


async def test_callback_empty_species_list_sends_no_sightings_message():
    stub = StubSearchService(result=[])
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: stub,  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    button = view.children[0]
    interaction = FakeInteraction()
    await button.callback(interaction)  # type: ignore[attr-defined]
    assert len(interaction.followup.sent) == 1
    assert "No rare bird sightings" in interaction.followup.sent[0]["content"]
    assert "US-TX-453" in interaction.followup.sent[0]["content"]


def test_long_display_name_is_truncated_to_80_chars():
    long_name = "X" * 200
    view = RegionButtonsView(
        results=[{"regionCode": "US-TX-453", "displayName": long_name}],  # type: ignore[list-item]
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    button = view.children[0]
    assert len(button.label) <= 80  # type: ignore[attr-defined]


def test_buttons_do_not_shadow_discord_internal_parent_attr():
    """Regression: discord.py's `Item._parent` is typed `Optional[Item]` and is
    walked by `Item._run_checks` to validate clicks. Storing a View there
    breaks dispatch with `AttributeError: '...View' object has no attribute
    '_run_checks'` and the user sees "This interaction failed".
    """
    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    for child in view.children:
        assert child._parent is None or isinstance(child._parent, discord.ui.Item), (
            f"button._parent shadowed by {type(child._parent).__name__}; "
            "this breaks discord.py's _run_checks chain"
        )


async def test_each_click_constructs_fresh_search_service():
    factory_calls = {"count": 0}

    def factory():
        factory_calls["count"] += 1
        return StubSearchService(result=[])

    view = RegionButtonsView(
        results=_three_results(),  # type: ignore[arg-type]
        make_search_service=factory,  # type: ignore[arg-type]
        logger=NoopLogger(),
    )
    button = view.children[0]

    await button.callback(FakeInteraction())  # type: ignore[attr-defined]
    await button.callback(FakeInteraction())  # type: ignore[attr-defined]
    assert factory_calls["count"] == 2
