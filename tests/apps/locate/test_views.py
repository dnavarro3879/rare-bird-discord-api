from typing import Any

import discord

from apps.locate.views import RegionButtonsView
from apps.search.services import SearchError, SearchTimeout
from apps.targets.services import TargetsError, TargetsTimeout


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


class StubTargetsService:
    def __init__(
        self,
        *,
        result: list | None = None,
        exc: Exception | None = None,
    ) -> None:
        self._result = result
        self._exc = exc
        self.calls: list[str] = []

    def targets(self, region: str):
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


def _default_view(
    *,
    results: list[dict] | None = None,
    search_stub: StubSearchService | None = None,
    targets_stub: StubTargetsService | None = None,
    logger: NoopLogger | None = None,
) -> RegionButtonsView:
    return RegionButtonsView(
        results=results if results is not None else _three_results(),  # type: ignore[arg-type]
        make_search_service=lambda: search_stub or StubSearchService(),  # type: ignore[return-value]
        make_targets_service=lambda: targets_stub or StubTargetsService(),  # type: ignore[return-value]
        logger=logger or NoopLogger(),
    )


def _rares_buttons(view: RegionButtonsView) -> list:
    return [c for c in view.children if c.custom_id.startswith("locate:rares:")]  # type: ignore[attr-defined]


def _targets_buttons(view: RegionButtonsView) -> list:
    return [c for c in view.children if c.custom_id.startswith("locate:targets:")]  # type: ignore[attr-defined]


def test_three_results_yields_rares_buttons_with_labeled_prefixes():
    # All three results are county-level (2) plus a state, so we expect
    # 2 rares + 2 targets + 1 rares = 5 buttons total.
    results = _three_results()
    view = _default_view(results=results)
    rares = _rares_buttons(view)
    targets = _targets_buttons(view)
    assert len(rares) == 3
    # Only the first two are county-level (US-TX-453, US-TX-491).
    assert len(targets) == 2
    for b in rares:
        assert b.label.startswith("Rares: ")
    for b in targets:
        assert b.label.startswith("Targets: ")


def test_one_result_yields_one_rares_button_when_not_county():
    view = _default_view(
        results=[{"regionCode": "AQ", "displayName": "Antarctica"}],
    )
    assert len(view.children) == 1
    assert view.children[0].custom_id == "locate:rares:AQ:1"  # type: ignore[attr-defined]


def test_one_result_yields_rares_and_targets_when_county():
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
    )
    assert len(view.children) == 2
    ids = [c.custom_id for c in view.children]  # type: ignore[attr-defined]
    assert "locate:rares:US-CO-013:1" in ids
    assert "locate:targets:US-CO-013:1" in ids


def test_mixed_results_only_county_regions_get_targets_buttons():
    # Second result is county-level; others are not.
    results = [
        {"regionCode": "US", "displayName": "United States"},
        {"regionCode": "US-CO-013", "displayName": "Boulder County"},
        {"regionCode": "US-CO", "displayName": "Colorado"},
    ]
    view = _default_view(results=results)
    assert len(view.children) == 4  # 3 rares + 1 targets
    assert len(_rares_buttons(view)) == 3
    assert len(_targets_buttons(view)) == 1
    targets = _targets_buttons(view)
    assert targets[0].custom_id == "locate:targets:US-CO-013:2"


def test_targets_button_never_created_for_non_county_regions():
    results = [
        {"regionCode": "US", "displayName": "USA"},
        {"regionCode": "US-CO", "displayName": "Colorado"},
        {"regionCode": "us-co-013", "displayName": "lowercase"},
    ]
    view = _default_view(results=results)
    assert _targets_buttons(view) == []
    assert len(_rares_buttons(view)) == 3


def test_button_custom_id_contains_kind_and_region_code():
    view = _default_view(results=_three_results())
    ids = [c.custom_id for c in view.children]  # type: ignore[attr-defined]
    # Exactly 5: rares for all 3 + targets for the first two county-level
    assert "locate:rares:US-TX-453:1" in ids
    assert "locate:targets:US-TX-453:1" in ids
    assert "locate:rares:US-TX-491:2" in ids
    assert "locate:targets:US-TX-491:2" in ids
    assert "locate:rares:US-TX:3" in ids


def test_buttons_for_same_region_share_a_row():
    view = _default_view(results=_three_results())
    by_region: dict[str, list] = {}
    for child in view.children:
        cid = child.custom_id  # type: ignore[attr-defined]
        region = cid.split(":")[2]
        by_region.setdefault(region, []).append(child)
    for region, buttons in by_region.items():
        rows = {b.row for b in buttons}  # type: ignore[attr-defined]
        assert len(rows) == 1, f"region {region} buttons not on same row"


def test_rares_button_uses_primary_style_targets_uses_success_style():
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
    )
    for child in view.children:
        cid = child.custom_id  # type: ignore[attr-defined]
        if "rares" in cid:
            assert child.style == discord.ButtonStyle.primary  # type: ignore[attr-defined]
        else:
            assert child.style == discord.ButtonStyle.success  # type: ignore[attr-defined]


async def test_rares_callback_defers_then_sends_species_embeds():
    stub = StubSearchService(result=_species())
    view = _default_view(search_stub=stub)
    button = _rares_buttons(view)[0]
    interaction = FakeInteraction()
    await button.callback(interaction)
    assert interaction.response.deferred
    assert interaction.response.deferred_kwargs == {"thinking": True}
    assert len(interaction.followup.sent) == 2
    assert interaction.followup.sent[0]["embed"].title == "Robin"
    assert interaction.followup.sent[1]["embed"].title == "Kestrel"


async def test_rares_callback_uses_clicked_button_region_code():
    stub = StubSearchService(result=[])
    view = _default_view(search_stub=stub)
    # The last child is the state-level rares button ("US-TX").
    button = _rares_buttons(view)[-1]
    interaction = FakeInteraction()
    await button.callback(interaction)
    assert stub.calls == ["US-TX"]


async def test_rares_callback_handles_search_error():
    stub = StubSearchService(exc=SearchError("agent failed"))
    view = _default_view(search_stub=stub)
    button = _rares_buttons(view)[0]
    interaction = FakeInteraction()
    await button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "Agent error" in interaction.followup.sent[0]["content"]


async def test_rares_callback_handles_search_timeout():
    stub = StubSearchService(exc=SearchTimeout("boom"))
    view = _default_view(search_stub=stub)
    button = _rares_buttons(view)[0]
    interaction = FakeInteraction()
    await button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "timed out" in interaction.followup.sent[0]["content"]


async def test_rares_callback_handles_generic_exception_logs_and_replies():
    stub = StubSearchService(exc=RuntimeError("kaboom"))
    logger = NoopLogger()
    view = _default_view(search_stub=stub, logger=logger)
    button = _rares_buttons(view)[0]
    interaction = FakeInteraction()
    await button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "Something went wrong" in interaction.followup.sent[0]["content"]
    assert len(logger.exceptions) == 1


async def test_rares_callback_empty_species_list_sends_no_sightings_message():
    stub = StubSearchService(result=[])
    view = _default_view(search_stub=stub)
    button = _rares_buttons(view)[0]
    interaction = FakeInteraction()
    await button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "No rare bird sightings" in interaction.followup.sent[0]["content"]
    assert "US-TX-453" in interaction.followup.sent[0]["content"]


async def test_rares_callback_still_fires_on_county_region():
    # Regression: county-level regions must keep serving rares clicks as well
    # as targets clicks. The rares path must not cross-wire to targets.
    search_stub = StubSearchService(result=_species())
    targets_stub = StubTargetsService(result=[{"commonName": "X", "sightings": []}])
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        search_stub=search_stub,
        targets_stub=targets_stub,
    )
    # Rares button is the one whose custom_id contains `:rares:`
    rares_button = [
        c
        for c in view.children
        if "rares" in c.custom_id  # type: ignore[attr-defined]
    ][0]
    interaction = FakeInteraction()
    await rares_button.callback(interaction)
    assert search_stub.calls == ["US-CO-013"]
    assert targets_stub.calls == []  # did not accidentally hit targets


async def test_targets_callback_runs_targets_service_and_renders_embeds():
    species = [
        {"commonName": "Dickcissel", "sightings": [{"locationName": "X"}]},
    ]
    targets_stub = StubTargetsService(result=species)
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        targets_stub=targets_stub,
    )
    targets_button = _targets_buttons(view)[0]
    interaction = FakeInteraction()
    await targets_button.callback(interaction)
    assert targets_stub.calls == ["US-CO-013"]
    assert interaction.response.deferred
    assert len(interaction.followup.sent) == 1
    assert interaction.followup.sent[0]["embed"].title == "Dickcissel"


async def test_targets_callback_renders_with_max_sightings_ten():
    sightings = [{"locationName": f"Loc {i}", "dateTime": "x"} for i in range(12)]
    targets_stub = StubTargetsService(
        result=[{"commonName": "Robin", "sightings": sightings}]
    )
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        targets_stub=targets_stub,
    )
    targets_button = _targets_buttons(view)[0]
    interaction = FakeInteraction()
    await targets_button.callback(interaction)
    embed = interaction.followup.sent[0]["embed"]
    assert len(embed.fields) == 10
    assert embed.footer.text == "+2 more sighting(s)"


async def test_targets_callback_handles_targets_error():
    targets_stub = StubTargetsService(exc=TargetsError("quota"))
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        targets_stub=targets_stub,
    )
    targets_button = _targets_buttons(view)[0]
    interaction = FakeInteraction()
    await targets_button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "Agent error" in interaction.followup.sent[0]["content"]
    assert "quota" in interaction.followup.sent[0]["content"]


async def test_targets_callback_handles_targets_timeout():
    targets_stub = StubTargetsService(exc=TargetsTimeout("slow"))
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        targets_stub=targets_stub,
    )
    targets_button = _targets_buttons(view)[0]
    interaction = FakeInteraction()
    await targets_button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "timed out" in interaction.followup.sent[0]["content"]


async def test_targets_callback_handles_generic_exception():
    targets_stub = StubTargetsService(exc=RuntimeError("kaboom"))
    logger = NoopLogger()
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        targets_stub=targets_stub,
        logger=logger,
    )
    targets_button = _targets_buttons(view)[0]
    interaction = FakeInteraction()
    await targets_button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "Something went wrong" in interaction.followup.sent[0]["content"]
    assert len(logger.exceptions) == 1


async def test_targets_callback_empty_species_list_sends_no_targets_message():
    targets_stub = StubTargetsService(result=[])
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder County"}],
        targets_stub=targets_stub,
    )
    targets_button = _targets_buttons(view)[0]
    interaction = FakeInteraction()
    await targets_button.callback(interaction)
    assert len(interaction.followup.sent) == 1
    assert "No life-list targets found" in interaction.followup.sent[0]["content"]
    assert "US-CO-013" in interaction.followup.sent[0]["content"]


def test_long_display_name_is_truncated_to_80_chars_with_kind_prefix():
    long_name = "X" * 200
    view = _default_view(
        results=[{"regionCode": "US-CO-013", "displayName": long_name}],
    )
    for button in view.children:
        assert len(button.label) <= 80  # type: ignore[attr-defined]


def test_buttons_do_not_shadow_discord_internal_parent_attr():
    """Regression: discord.py's `Item._parent` is typed `Optional[Item]` and is
    walked by `Item._run_checks` to validate clicks. Storing a View there
    breaks dispatch with `AttributeError: '...View' object has no attribute
    '_run_checks'` and the user sees "This interaction failed".
    """
    view = _default_view(results=_three_results())
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
        make_targets_service=lambda: StubTargetsService(),  # type: ignore[return-value]
        logger=NoopLogger(),
    )
    button = _rares_buttons(view)[0]

    await button.callback(FakeInteraction())
    await button.callback(FakeInteraction())
    assert factory_calls["count"] == 2


async def test_each_click_constructs_fresh_targets_service():
    factory_calls = {"count": 0}

    def factory():
        factory_calls["count"] += 1
        return StubTargetsService(result=[])

    view = RegionButtonsView(
        results=[{"regionCode": "US-CO-013", "displayName": "Boulder"}],  # type: ignore[list-item]
        make_search_service=lambda: StubSearchService(),  # type: ignore[return-value]
        make_targets_service=factory,  # type: ignore[arg-type]
        logger=NoopLogger(),
    )
    button = _targets_buttons(view)[0]

    await button.callback(FakeInteraction())
    await button.callback(FakeInteraction())
    assert factory_calls["count"] == 2
