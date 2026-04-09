import json

import pytest

from core.json_extract import JsonExtractError, extract_json


def test_extract_json_returns_value_from_fenced_json_array():
    text = "```json\n[1, 2, 3]\n```"
    assert extract_json(text) == [1, 2, 3]


def test_extract_json_returns_value_from_fenced_json_object():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_extract_json_strips_prose_around_fenced_block():
    text = "Here you go:\n```json\n[1]\n```\nDone!"
    assert extract_json(text) == [1]


def test_extract_json_falls_back_to_balanced_brackets_when_unfenced():
    text = "prose [1, 2, 3] more prose"
    assert extract_json(text) == [1, 2, 3]


def test_extract_json_falls_back_to_balanced_object_when_unfenced():
    text = 'prose {"a": 1} more'
    assert extract_json(text) == {"a": 1}


def test_extract_json_raises_on_empty_text():
    with pytest.raises(JsonExtractError) as excinfo:
        extract_json("")
    assert "no text" in str(excinfo.value)


def test_extract_json_raises_when_no_json_present():
    with pytest.raises(JsonExtractError) as excinfo:
        extract_json("just prose, no JSON here")
    assert "no JSON found" in str(excinfo.value)


def test_extract_json_propagates_jsondecodeerror_for_malformed_fence():
    with pytest.raises(json.JSONDecodeError):
        extract_json("```json\n[not valid\n```")


def test_extract_json_handles_realistic_managed_agent_response():
    text = (
        "```json\n"
        "[\n"
        '  {\n    "commonName": "Golden-crowned Kinglet",\n'
        '    "scientificName": "Regulus satrapa",\n'
        '    "speciesCode": "gockin",\n'
        '    "sightings": []\n  }\n'
        "]\n"
        "```"
    )
    result = extract_json(text)
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["commonName"] == "Golden-crowned Kinglet"
