from dataclasses import dataclass
from typing import Any

import anthropic
import httpx
import pytest

from apps.locate.services import (
    _DEFAULT_MODEL,
    LocateError,
    LocateService,
    LocateTimeout,
)
from core.config import Config

# ---------- fakes ----------


@dataclass
class FakeTextBlock:
    text: str
    type: str = "text"


@dataclass
class FakeServerToolUseBlock:
    type: str = "server_tool_use"


@dataclass
class FakeWebSearchResultBlock:
    type: str = "web_search_tool_result"


@dataclass
class FakeResponse:
    content: list[Any]


class FakeMessagesApi:
    def __init__(self, response_or_exc: Any) -> None:
        self._response_or_exc = response_or_exc
        self.calls: list[dict] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if isinstance(self._response_or_exc, BaseException):
            raise self._response_or_exc
        return self._response_or_exc


class FakeAnthropic:
    def __init__(self, messages_api: FakeMessagesApi) -> None:
        self.messages = messages_api


class NoopLogger:
    def info(self, *args: Any, **kwargs: Any) -> None:
        pass

    def debug(self, *args: Any, **kwargs: Any) -> None:
        pass

    def warning(self, *args: Any, **kwargs: Any) -> None:
        pass

    def error(self, *args: Any, **kwargs: Any) -> None:
        pass

    def exception(self, *args: Any, **kwargs: Any) -> None:
        pass


# ---------- helpers ----------


def _config(claude_model: str = "") -> Config:
    return Config(
        discord_token="tok",
        anthropic_api_key="akey",
        agent_id="agent",
        environment_id="env",
        claude_model=claude_model,
    )


def _service(
    response_or_exc: Any,
    *,
    claude_model: str = "",
) -> tuple[LocateService, FakeAnthropic]:
    messages_api = FakeMessagesApi(response_or_exc)
    client = FakeAnthropic(messages_api)
    svc = LocateService(
        client=client,  # type: ignore[arg-type]
        config=_config(claude_model=claude_model),
        logger=NoopLogger(),
    )
    return svc, client


def _text_response(text: str) -> FakeResponse:
    return FakeResponse(content=[FakeTextBlock(text=text)])


def _fenced(payload: str) -> str:
    return f"```json\n{payload}\n```"


_THREE_RESULTS_JSON = (
    '[{"regionCode": "US-TX-453", "displayName": "Travis County, Texas, US",'
    ' "description": "Contains Austin, TX"},'
    ' {"regionCode": "US-TX-491", "displayName": "Williamson County, Texas, US",'
    ' "description": "North of Austin"},'
    ' {"regionCode": "US-TX", "displayName": "Texas, US",'
    ' "description": "Statewide fallback"}]'
)

_ONE_RESULT_JSON = (
    '[{"regionCode": "AQ", "displayName": "Antarctica", "description": "Very remote"}]'
)


def _httpx_request() -> httpx.Request:
    return httpx.Request("POST", "https://api.anthropic.com/v1/messages")


# ---------- tests ----------


def test_fenced_json_list_of_three_returns_three_results():
    svc, _ = _service(_text_response(_fenced(_THREE_RESULTS_JSON)))
    result = svc.locate("Austin")
    assert len(result) == 3
    assert result[0]["regionCode"] == "US-TX-453"
    assert result[2]["displayName"] == "Texas, US"


def test_fenced_json_list_of_one_returns_one_result():
    svc, _ = _service(_text_response(_fenced(_ONE_RESULT_JSON)))
    result = svc.locate("McMurdo")
    assert len(result) == 1
    assert result[0]["regionCode"] == "AQ"


def test_fenced_error_dict_raises_locate_error():
    payload = '{"error": "Could not identify a city matching \'Xyzzy\'"}'
    svc, _ = _service(_text_response(_fenced(payload)))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Xyzzy")
    assert "Xyzzy" in str(excinfo.value)


def test_malformed_json_raises_locate_error():
    svc, _ = _service(_text_response("```json\n[not valid json\n```"))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "could not parse" in str(excinfo.value).lower()


def test_wrong_shape_dict_without_error_key_raises_locate_error():
    svc, _ = _service(_text_response(_fenced('{"foo": "bar"}')))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "unexpected payload shape" in str(excinfo.value)


def test_length_four_list_raises_locate_error():
    payload = (
        "["
        '{"regionCode": "US-TX-453"},'
        '{"regionCode": "US-TX-491"},'
        '{"regionCode": "US-TX"},'
        '{"regionCode": "US"}'
        "]"
    )
    svc, _ = _service(_text_response(_fenced(payload)))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "unexpected payload shape" in str(excinfo.value)


def test_empty_list_raises_locate_error():
    svc, _ = _service(_text_response(_fenced("[]")))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "unexpected payload shape" in str(excinfo.value)


def test_interleaved_content_blocks_parses_text_only():
    response = FakeResponse(
        content=[
            FakeServerToolUseBlock(),
            FakeWebSearchResultBlock(),
            FakeTextBlock(text=_fenced(_ONE_RESULT_JSON)),
        ]
    )
    svc, _ = _service(response)
    result = svc.locate("McMurdo")
    assert len(result) == 1
    assert result[0]["regionCode"] == "AQ"


def test_unfenced_json_after_prose_falls_back_to_regex_parse():
    text = (
        "Here are the regions you asked about:\n\n"
        '[{"regionCode": "AQ", "displayName": "Antarctica",'
        ' "description": "Very remote"}]'
    )
    svc, _ = _service(_text_response(text))
    result = svc.locate("McMurdo")
    assert len(result) == 1
    assert result[0]["regionCode"] == "AQ"


def test_messages_create_call_args_contain_city_in_user_message():
    svc, client = _service(_text_response(_fenced(_ONE_RESULT_JSON)))
    svc.locate("Mexico City")
    call = client.messages.calls[0]
    messages = call["messages"]
    assert messages == [{"role": "user", "content": "City: Mexico City"}]


def test_tools_arg_contains_web_search_tool_with_max_uses_three():
    svc, client = _service(_text_response(_fenced(_ONE_RESULT_JSON)))
    svc.locate("Austin")
    tools = client.messages.calls[0]["tools"]
    assert len(tools) == 1
    tool = tools[0]
    assert tool["type"] == "web_search_20250305"
    assert tool["name"] == "web_search"
    assert tool["max_uses"] == 3


def test_system_prompt_contains_ebird():
    svc, client = _service(_text_response(_fenced(_ONE_RESULT_JSON)))
    svc.locate("Austin")
    system = client.messages.calls[0]["system"]
    assert "eBird" in system


def test_timeout_arg_is_120_seconds():
    svc, client = _service(_text_response(_fenced(_ONE_RESULT_JSON)))
    svc.locate("Austin")
    assert client.messages.calls[0]["timeout"] == 120.0


def test_config_claude_model_override_is_honored():
    svc, client = _service(
        _text_response(_fenced(_ONE_RESULT_JSON)),
        claude_model="claude-sonnet-test",
    )
    svc.locate("Austin")
    assert client.messages.calls[0]["model"] == "claude-sonnet-test"


def test_empty_config_claude_model_falls_back_to_default():
    svc, client = _service(_text_response(_fenced(_ONE_RESULT_JSON)))
    svc.locate("Austin")
    assert client.messages.calls[0]["model"] == _DEFAULT_MODEL


def test_api_timeout_error_raises_locate_timeout():
    svc, _ = _service(anthropic.APITimeoutError(request=_httpx_request()))
    with pytest.raises(LocateTimeout):
        svc.locate("Austin")


def test_api_error_raises_locate_error():
    svc, _ = _service(
        anthropic.APIError(message="boom", request=_httpx_request(), body=None)
    )
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "boom" in str(excinfo.value)


def test_response_with_zero_text_blocks_raises_locate_error():
    response = FakeResponse(
        content=[FakeServerToolUseBlock(), FakeWebSearchResultBlock()]
    )
    svc, _ = _service(response)
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "no text block" in str(excinfo.value)


def test_malformed_region_code_raises_locate_error():
    payload = (
        '[{"regionCode": "us-tx-453", "displayName": "bad", "description": "bad"}]'
    )
    svc, _ = _service(_text_response(_fenced(payload)))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "malformed region code" in str(excinfo.value)


def test_list_of_non_dict_items_raises_locate_error():
    svc, _ = _service(_text_response(_fenced("[1, 2, 3]")))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "unexpected payload shape" in str(excinfo.value)


def test_text_without_any_json_raises_locate_error():
    svc, _ = _service(_text_response("just prose, no JSON here"))
    with pytest.raises(LocateError) as excinfo:
        svc.locate("Austin")
    assert "could not parse JSON from response" in str(excinfo.value)
