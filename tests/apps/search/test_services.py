import json

import pytest

from apps.search.services import (
    _BETA,
    SearchError,
    SearchService,
    SearchTimeout,
)
from core.config import Config

# ---------- fakes ----------


class FakeEvent:
    def __init__(self, event_type: str, text: str | None = None) -> None:
        self.type = event_type
        if text is not None:
            self.content = [type("C", (), {"text": text})()]
        else:
            self.content = []


class FakeEventsList:
    def __init__(self, data: list) -> None:
        self.data = data


class FakeEventsApi:
    def __init__(self, sequence: list[list]) -> None:
        self._seq = iter(sequence)
        self.sent: list[tuple] = []
        self.list_calls: list[tuple] = []

    def send(self, session_id, events, betas):
        self.sent.append((session_id, events, betas))

    def list(self, session_id, betas):
        self.list_calls.append((session_id, betas))
        return FakeEventsList(next(self._seq))


class FakeSessions:
    def __init__(self, sequence: list[list]) -> None:
        self.events = FakeEventsApi(sequence)
        self.created: list[tuple] = []

    def create(self, agent, environment_id, betas):
        self.created.append((agent, environment_id, betas))
        return type("S", (), {"id": "sess_123"})()


class FakeAnthropic:
    def __init__(self, sequence: list[list]) -> None:
        self.beta = type("B", (), {"sessions": FakeSessions(sequence)})()


class CountingSleeper:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


class NoopLogger:
    def info(self, *args, **kwargs):
        pass

    def debug(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


# ---------- helpers ----------


def _config() -> Config:
    return Config(
        discord_token="tok",
        anthropic_api_key="akey",
        agent_id="agent-xyz",
        environment_id="env-xyz",
    )


def _agent_message(payload, *, raw_text: str | None = None) -> FakeEvent:
    if raw_text is not None:
        return FakeEvent("agent.message", text=raw_text)
    return FakeEvent("agent.message", text=json.dumps(payload))


def _service(
    sequence: list[list],
    *,
    sleeper: CountingSleeper | None = None,
    max_polls: int = 120,
) -> tuple[SearchService, FakeAnthropic, CountingSleeper]:
    sleeper = sleeper or CountingSleeper()
    client = FakeAnthropic(sequence)
    svc = SearchService(
        client=client,  # type: ignore[arg-type]
        config=_config(),
        sleeper=sleeper,
        logger=NoopLogger(),
        poll_interval_s=3.0,
        max_polls=max_polls,
    )
    return svc, client, sleeper


# ---------- tests ----------


def test_search_returns_species_list_on_first_poll():
    species = [{"commonName": "Robin"}, {"commonName": "Kestrel"}]
    svc, _, sleeper = _service([[_agent_message(species)]])
    result = svc.search("US-CA")
    assert result == species
    assert sleeper.calls == []


def test_search_polls_until_agent_message_appears():
    species = [{"commonName": "Robin"}]
    svc, _, sleeper = _service([[], [], [_agent_message(species)]])
    result = svc.search("US-CA")
    assert result == species
    assert sleeper.calls == [3.0, 3.0]


def test_search_sends_region_as_user_message_event():
    species: list = []
    svc, client, _ = _service([[_agent_message(species)]])
    svc.search("US-CA")
    assert len(client.beta.sessions.events.sent) == 1
    sent = client.beta.sessions.events.sent[0]
    session_id, events, _betas = sent
    assert session_id == "sess_123"
    assert events == [
        {
            "type": "user.message",
            "content": [{"type": "text", "text": "US-CA"}],
        }
    ]


def test_search_passes_beta_header_on_create_send_and_list():
    svc, client, _ = _service([[_agent_message([])]])
    svc.search("US-CA")

    # create
    assert client.beta.sessions.created[0][2] == _BETA
    # send
    assert client.beta.sessions.events.sent[0][2] == _BETA
    # list
    assert client.beta.sessions.events.list_calls[0][1] == _BETA


def test_search_raises_search_error_when_payload_has_error_key():
    svc, _, _ = _service([[_agent_message({"error": "quota exceeded"})]])
    with pytest.raises(SearchError) as excinfo:
        svc.search("US-CA")
    assert "quota exceeded" in str(excinfo.value)


def test_search_raises_search_timeout_after_max_polls():
    svc, _, sleeper = _service([[], [], []], max_polls=3)
    with pytest.raises(SearchTimeout):
        svc.search("US-CA")
    # 3 polls means the sleeper is called 3 times (once per poll after checking)
    assert sleeper.calls == [3.0, 3.0, 3.0]


def test_search_does_not_sleep_before_first_poll():
    species = [{"commonName": "Robin"}]
    svc, _, sleeper = _service([[_agent_message(species)]])
    svc.search("US-CA")
    assert sleeper.calls == []


def test_search_ignores_non_agent_message_events():
    species = [{"commonName": "Robin"}]
    noise = FakeEvent("session.started")
    also_noise = FakeEvent("tool.call")
    svc, _, sleeper = _service([[noise, also_noise], [_agent_message(species)]])
    result = svc.search("US-CA")
    assert result == species
    assert sleeper.calls == [3.0]


def test_search_uses_injected_sleeper():
    counter = CountingSleeper()
    svc, _, sleeper = _service([[], [], [_agent_message([])]], sleeper=counter)
    svc.search("US-CA")
    assert counter is sleeper
    assert len(counter.calls) == 2


def test_search_passes_agent_and_environment_ids_on_create():
    svc, client, _ = _service([[_agent_message([])]])
    svc.search("US-CA")
    created = client.beta.sessions.created[0]
    assert created[0] == "agent-xyz"
    assert created[1] == "env-xyz"


def test_search_returns_empty_list_when_agent_returns_empty():
    svc, _, _ = _service([[_agent_message([])]])
    result = svc.search("US-CA")
    assert result == []


def test_search_returns_species_list_when_agent_response_is_fenced_json():
    species = [
        {"commonName": "Golden-crowned Kinglet", "scientificName": "Regulus satrapa"}
    ]
    fenced = f"```json\n{json.dumps(species)}\n```"
    svc, _, _ = _service([[_agent_message(None, raw_text=fenced)]])
    result = svc.search("US-GA-121")
    assert result == species


def test_search_raises_search_error_on_unparseable_agent_response():
    svc, _, _ = _service(
        [[_agent_message(None, raw_text="this is just prose, no JSON")]]
    )
    with pytest.raises(SearchError) as excinfo:
        svc.search("US-CA")
    assert "could not parse" in str(excinfo.value).lower()


def test_search_raises_search_error_when_fenced_payload_has_error_key():
    fenced = '```json\n{"error": "quota exceeded"}\n```'
    svc, _, _ = _service([[_agent_message(None, raw_text=fenced)]])
    with pytest.raises(SearchError) as excinfo:
        svc.search("US-CA")
    assert "quota exceeded" in str(excinfo.value)
