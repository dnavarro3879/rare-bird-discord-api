import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anthropic

from apps.search.schemas import Species
from core.config import Config
from core.json_extract import JsonExtractError, extract_json

_BETA = ["managed-agents-2026-04-01"]


class SearchError(RuntimeError): ...


class SearchTimeout(RuntimeError): ...


@dataclass(frozen=True)
class SearchService:
    client: anthropic.Anthropic
    config: Config
    sleeper: Callable[[float], None]
    logger: Any
    poll_interval_s: float = 3.0
    max_polls: int = 120  # 6-minute ceiling

    def search(self, region: str) -> list[Species]:
        session = self.client.beta.sessions.create(
            agent=self.config.agent_id,
            environment_id=self.config.environment_id,
            betas=_BETA,
        )
        self.logger.info("session created", session_id=session.id, region=region)

        self.client.beta.sessions.events.send(
            session.id,
            events=[
                {
                    "type": "user.message",
                    "content": [{"type": "text", "text": region}],
                }
            ],
            betas=_BETA,
        )

        for _ in range(self.max_polls):
            events = self.client.beta.sessions.events.list(session.id, betas=_BETA)
            for event in events.data:
                if event.type == "agent.message":
                    text = event.content[0].text
                    try:
                        payload = extract_json(text)
                    except (JsonExtractError, json.JSONDecodeError) as exc:
                        raise SearchError(
                            f"could not parse agent response: {exc}"
                        ) from exc
                    self.logger.info(
                        "agent response parsed",
                        session_id=session.id,
                        region=region,
                    )
                    if isinstance(payload, dict) and "error" in payload:
                        raise SearchError(payload["error"])
                    return payload
            self.sleeper(self.poll_interval_s)

        raise SearchTimeout(f"no agent.message after {self.max_polls} polls")
