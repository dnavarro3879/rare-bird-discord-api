import discord

from apps.search.embeds import build_species_embed


def _sighting(i: int) -> dict:
    return {
        "locationName": f"Loc {i}",
        "dateTime": f"2026-04-0{i}",
        "checklistUrl": f"https://ebird.example/{i}",
        "googleMapsUrl": f"https://maps.example/{i}",
    }


def test_build_embed_sets_title_and_scientific_name():
    species = {
        "commonName": "Kestrel",
        "scientificName": "Falco tinnunculus",
        "allAboutBirdsUrl": "https://allaboutbirds.example/kestrel",
        "sightings": [],
    }
    embed = build_species_embed(species)
    assert embed.title == "Kestrel"
    assert embed.description == "*Falco tinnunculus*"
    assert embed.url == "https://allaboutbirds.example/kestrel"
    assert embed.color == discord.Color.green()


def test_build_embed_handles_missing_fields():
    embed = build_species_embed({"commonName": "Mystery Bird"})
    assert embed.title == "Mystery Bird"
    assert embed.description is None
    assert embed.url is None
    assert len(embed.fields) == 0
    assert embed.footer.text is None


def test_build_embed_caps_sightings_at_five_and_sets_footer():
    sightings = [_sighting(i) for i in range(1, 8)]  # 7 sightings
    species = {"commonName": "Robin", "sightings": sightings}
    embed = build_species_embed(species)
    assert len(embed.fields) == 5
    assert embed.footer.text == "+2 more sighting(s)"


def test_build_embed_omits_footer_when_five_or_fewer():
    sightings = [_sighting(i) for i in range(1, 6)]  # exactly 5
    species = {"commonName": "Robin", "sightings": sightings}
    embed = build_species_embed(species)
    assert len(embed.fields) == 5
    assert embed.footer.text is None


def test_build_embed_joins_checklist_and_map_links_with_pipe():
    species = {
        "commonName": "Robin",
        "sightings": [_sighting(1)],
    }
    embed = build_species_embed(species)
    field = embed.fields[0]
    assert "[Checklist](https://ebird.example/1)" in field.value
    assert "[Map](https://maps.example/1)" in field.value
    assert " | " in field.value


def test_build_embed_omits_link_section_when_no_urls():
    species = {
        "commonName": "Robin",
        "sightings": [{"locationName": "Park", "dateTime": "2026-04-01"}],
    }
    embed = build_species_embed(species)
    field = embed.fields[0]
    assert field.value == "2026-04-01"


def test_build_embed_uses_checklist_only_when_map_missing():
    species = {
        "commonName": "Robin",
        "sightings": [
            {
                "locationName": "Park",
                "dateTime": "2026-04-01",
                "checklistUrl": "https://ebird.example/only",
            }
        ],
    }
    embed = build_species_embed(species)
    value = embed.fields[0].value
    assert "[Checklist](https://ebird.example/only)" in value
    assert "Map" not in value


def test_build_embed_uses_map_only_when_checklist_missing():
    species = {
        "commonName": "Robin",
        "sightings": [
            {
                "locationName": "Park",
                "dateTime": "2026-04-01",
                "googleMapsUrl": "https://maps.example/only",
            }
        ],
    }
    embed = build_species_embed(species)
    value = embed.fields[0].value
    assert "[Map](https://maps.example/only)" in value
    assert "Checklist" not in value


def test_build_embed_color_is_green():
    embed = build_species_embed({"commonName": "X"})
    assert embed.color == discord.Color.green()


def test_build_embed_defaults_unknown_species_and_unknown_location():
    species = {"sightings": [{"dateTime": "2026-04-01"}]}
    embed = build_species_embed(species)
    assert embed.title == "Unknown Species"
    assert embed.fields[0].name == "Unknown location"


def test_build_embed_honors_max_sightings_override():
    sightings = [_sighting(i) for i in range(1, 11)]  # exactly 10
    species = {"commonName": "Robin", "sightings": sightings}
    embed = build_species_embed(species, max_sightings=10)
    assert len(embed.fields) == 10
    assert embed.footer.text is None
