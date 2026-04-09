import json
import re
from typing import Any

_FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
_BALANCED_JSON_RE = re.compile(r"(\[.*\]|\{.*\})", re.DOTALL)


class JsonExtractError(ValueError):
    """Raised when no JSON candidate can be located in the input text."""


def extract_json(text: str) -> Any:
    """Extract a JSON value from text, tolerating ```json fences and prose.

    Strategy:
    1. Prefer the contents of a fenced ```json ... ``` block.
    2. Fall back to the longest top-level [...] or {...} substring.
    3. json.loads the candidate.

    Raises:
        JsonExtractError: when input is empty or contains no recognizable JSON.
        json.JSONDecodeError: when the candidate isn't valid JSON.
    """
    if not text:
        raise JsonExtractError("no text to extract from")

    fenced = _FENCED_JSON_RE.search(text)
    candidate = fenced.group(1) if fenced else None
    if candidate is None:
        fallback = _BALANCED_JSON_RE.search(text)
        candidate = fallback.group(1) if fallback else None
    if candidate is None:
        raise JsonExtractError("no JSON found in text")

    return json.loads(candidate)
