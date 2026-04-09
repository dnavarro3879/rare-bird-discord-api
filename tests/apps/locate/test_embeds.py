import discord

from apps.locate.embeds import build_locate_embed


def _three_results() -> list[dict]:
    return [
        {
            "regionCode": "US-TX-453",
            "displayName": "Travis County, Texas, US",
            "description": "Contains Austin, TX",
        },
        {
            "regionCode": "US-TX-491",
            "displayName": "Williamson County, Texas, US",
            "description": "North of Austin",
        },
        {
            "regionCode": "US-TX",
            "displayName": "Texas, US",
            "description": "Statewide fallback",
        },
    ]


def test_title_includes_city_name():
    embed = build_locate_embed("Austin", _three_results())  # type: ignore[arg-type]
    assert "Austin" in embed.title  # type: ignore[operator]


def test_color_is_blurple():
    embed = build_locate_embed("Austin", _three_results())  # type: ignore[arg-type]
    assert embed.color == discord.Color.blurple()


def test_three_results_yields_three_numbered_fields():
    embed = build_locate_embed("Austin", _three_results())  # type: ignore[arg-type]
    assert len(embed.fields) == 3
    assert embed.fields[0].name.startswith("1. ")  # type: ignore[union-attr]
    assert embed.fields[1].name.startswith("2. ")  # type: ignore[union-attr]
    assert embed.fields[2].name.startswith("3. ")  # type: ignore[union-attr]


def test_region_code_rendered_in_backticks():
    embed = build_locate_embed("Austin", _three_results())  # type: ignore[arg-type]
    assert "`US-TX-453`" in embed.fields[0].value  # type: ignore[operator]


def test_missing_description_renders_only_backticked_region_code():
    results = [{"regionCode": "US-TX-453", "displayName": "Travis County"}]
    embed = build_locate_embed("Austin", results)  # type: ignore[arg-type]
    value = embed.fields[0].value
    assert value == "`US-TX-453`"
    assert "\n" not in value  # type: ignore[operator]


def test_missing_display_name_falls_back_to_region_code():
    results = [{"regionCode": "US-TX-453", "description": "Austin"}]
    embed = build_locate_embed("Austin", results)  # type: ignore[arg-type]
    assert embed.fields[0].name == "1. US-TX-453"


def test_single_result_input_renders_one_field():
    results = [{"regionCode": "AQ", "displayName": "Antarctica"}]
    embed = build_locate_embed("McMurdo", results)  # type: ignore[arg-type]
    assert len(embed.fields) == 1


def test_empty_results_list_yields_zero_fields():
    embed = build_locate_embed("Nowhere", [])
    assert len(embed.fields) == 0
