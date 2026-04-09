import json
import re
from dataclasses import dataclass
from typing import Any

import anthropic

from apps.locate.schemas import RegionResult
from core.config import Config

_DEFAULT_MODEL = "claude-sonnet-4-5"
_WEB_SEARCH_MAX_USES = 3
_REQUEST_TIMEOUT_S = 120.0
_MAX_TOKENS = 2048

_SYSTEM_PROMPT = (
    "You are a geographic lookup assistant for an eBird-based Discord bot."
    " Given a\n"
    "city name, return up to three eBird region codes most useful for birders\n"
    "searching for rare bird sightings near that city.\n"
    "\n"
    "eBird region code rules:\n"
    '- Country codes are ISO 3166-1 alpha-2 (e.g. "US", "CA", "MX").\n'
    '- State/subnational1 codes are "<COUNTRY>-<STATE>" (e.g. "US-TX",'
    ' "CA-ON").\n'
    '- County/subnational2 codes are "<COUNTRY>-<STATE>-<COUNTYNUM>" (e.g.\n'
    '  "US-TX-453" for Travis County, Texas). COUNTYNUM is the numeric FIPS\n'
    "  subdivision code and is NOT memorizable from parametric knowledge"
    " alone.\n"
    "\n"
    "Choose granularity based on the query:\n"
    "- If the city is in a clearly identifiable county (most US/CA cities),"
    " the\n"
    "  first result MUST be the county containing that city, and you MUST"
    " verify\n"
    "  the county-level region code using the web_search tool before"
    " returning it.\n"
    '- Country and state-level codes (e.g. "US", "US-TX") can come from your\n'
    "  knowledge without a web search — do not waste a web search on them.\n"
    '- If the city is ambiguous (e.g. "Springfield"), pick the largest or\n'
    "  most-known match and explain the disambiguation in `description`.\n"
    "\n"
    "Return between 1 and 3 results. The first result is the region"
    " containing\n"
    "the city itself. Optional 2nd/3rd results are adjacent or nearby regions"
    " a\n"
    "birder might also want to check. If you cannot find a usable region,"
    " return\n"
    "a JSON object with an `error` key instead of a list.\n"
    "\n"
    "Output format: reply with ONLY a single fenced ```json code block"
    " containing\n"
    "either a JSON array (success) or a JSON object with an `error` key"
    " (failure).\n"
    "No commentary before or after. Each array item MUST have exactly these"
    " keys:\n"
    "`regionCode`, `displayName`, `description`.\n"
    "\n"
    "Success example:\n"
    "```json\n"
    "[\n"
    '  {"regionCode": "US-TX-453", "displayName": "Travis County, Texas, US",'
    ' "description": "Contains Austin, TX"},\n'
    '  {"regionCode": "US-TX-491",'
    ' "displayName": "Williamson County, Texas, US",'
    ' "description": "Directly north of Austin;'
    ' Balcones Canyonlands hotspots"},\n'
    '  {"regionCode": "US-TX", "displayName": "Texas, US",'
    ' "description": "State-wide fallback if county searches are too narrow"}\n'
    "]\n"
    "```\n"
    "\n"
    "Failure example:\n"
    "```json\n"
    '{"error": "Could not identify a city matching \'Xyzzy\'"}\n'
    "```\n"
)

_REGION_CODE_RE = re.compile(r"^[A-Z]{2}(-[A-Z0-9]+){0,2}$")

_FENCED_JSON_RE = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
_BALANCED_JSON_RE = re.compile(r"(\[.*\]|\{.*\})", re.DOTALL)


class LocateError(RuntimeError): ...


class LocateTimeout(RuntimeError): ...


@dataclass(frozen=True)
class LocateService:
    client: anthropic.Anthropic
    config: Config
    logger: Any

    def locate(self, city: str) -> list[RegionResult]:
        model = self.config.claude_model or _DEFAULT_MODEL
        try:
            response = self.client.messages.create(
                model=model,
                system=_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"City: {city}"}],
                tools=[
                    {
                        "type": "web_search_20250305",
                        "name": "web_search",
                        "max_uses": _WEB_SEARCH_MAX_USES,
                    }
                ],
                max_tokens=_MAX_TOKENS,
                timeout=_REQUEST_TIMEOUT_S,
            )
        except anthropic.APITimeoutError as exc:
            raise LocateTimeout(f"messages.create timed out for city={city!r}") from exc
        except anthropic.APIError as exc:
            raise LocateError(f"messages.create failed: {exc}") from exc

        payload = self._extract_json_payload(response)

        if isinstance(payload, dict) and "error" in payload:
            raise LocateError(str(payload["error"]))

        if not isinstance(payload, list) or not (1 <= len(payload) <= 3):
            raise LocateError(f"unexpected payload shape: {payload!r}")

        for item in payload:
            if not isinstance(item, dict):
                raise LocateError(f"unexpected payload shape: {payload!r}")
            region_code = item.get("regionCode")
            if not isinstance(region_code, str) or not _REGION_CODE_RE.match(
                region_code
            ):
                raise LocateError(f"malformed region code: {region_code!r}")

        self.logger.info("locate success", city=city, count=len(payload))
        return payload

    def _extract_json_payload(self, response: Any) -> Any:
        text_parts: list[str] = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text_parts.append(getattr(block, "text", ""))
        text = "".join(text_parts)
        if not text:
            raise LocateError("no text block in response")

        fenced = _FENCED_JSON_RE.search(text)
        candidate = fenced.group(1) if fenced else None
        if candidate is None:
            fallback = _BALANCED_JSON_RE.search(text)
            candidate = fallback.group(1) if fallback else None
        if candidate is None:
            raise LocateError("could not parse JSON from response")

        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise LocateError("could not parse JSON from response") from exc
