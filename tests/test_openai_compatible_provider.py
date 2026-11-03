from __future__ import annotations

import json
from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import HTTPHandler, HTTPSHandler, build_opener
from urllib.response import addinfourl

import pytest
from pydantic import BaseModel, SecretStr

from growwise.config import Settings
from growwise.model import OpenAICompatibleProvider, create_model_provider
from growwise.model import openai_compatible as openai_module
from growwise.model.health import probe_model_runtime


class _Answer(BaseModel):
    answer: str


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self._raw if limit < 0 else self._raw[:limit]


def _chat_response(content: str) -> _FakeResponse:
    return _FakeResponse({"choices": [{"message": {"content": content}}]})


def test_openai_compatible_text_request_uses_chat_completions(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["headers"] = dict(request.header_items())
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _chat_response("안녕하세요")

    monkeypatch.setattr(
        openai_module, "build_opener", lambda *_args: SimpleNamespace(open=fake_urlopen)
    )
    provider = OpenAICompatibleProvider(
        model="local-model",
        base_url="http://127.0.0.1:8080",
        timeout_seconds=3.0,
    )

    assert provider.generate_text(system="system", user="user") == "안녕하세요"
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert captured["timeout"] == 3.0
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == "local-model"
    assert payload["messages"][0]["role"] == "system"
    assert "Authorization" not in captured["headers"]


def test_openai_compatible_structured_output_uses_json_schema(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(request, timeout):
        del timeout
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _chat_response('{"answer":"구조화 성공"}')

    monkeypatch.setattr(
        openai_module, "build_opener", lambda *_args: SimpleNamespace(open=fake_urlopen)
    )
    provider = OpenAICompatibleProvider(
        model="local-model",
        base_url="http://localhost:9000/v1",
    )

    result = provider.generate_structured(system="system", user="user", schema=_Answer)

    assert result.answer == "구조화 성공"
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["response_format"]["type"] == "json_schema"
    assert payload["response_format"]["json_schema"]["strict"] is True


def test_openai_compatible_retries_without_json_schema_for_basic_servers(monkeypatch) -> None:
    payloads: list[dict] = []

    def fake_urlopen(request, timeout):
        del timeout
        payload = json.loads(request.data.decode("utf-8"))
        payloads.append(payload)
        if len(payloads) == 1:
            raise HTTPError(
                request.full_url,
                400,
                "response_format unsupported",
                hdrs=None,
                fp=BytesIO(b"unsupported"),
            )
        return _chat_response('{"answer":"fallback"}')

    monkeypatch.setattr(
        openai_module, "build_opener", lambda *_args: SimpleNamespace(open=fake_urlopen)
    )
    provider = OpenAICompatibleProvider(
        model="llama.cpp-model",
        base_url="http://127.0.0.1:8080/v1",
    )

    result = provider.generate_structured(system="system", user="user", schema=_Answer)

    assert result.answer == "fallback"
    assert "response_format" in payloads[0]
    assert "response_format" not in payloads[1]
    assert "Return ONLY one JSON object" in payloads[1]["messages"][1]["content"]


def test_remote_openai_compatible_requires_explicit_privacy_opt_in() -> None:
    with pytest.raises(ValueError, match="MODEL_REMOTE_ALLOWED"):
        OpenAICompatibleProvider(
            model="remote-model",
            base_url="https://models.example.com/v1",
        )

    with pytest.raises(ValueError, match="must use HTTPS"):
        OpenAICompatibleProvider(
            model="remote-model",
            base_url="http://models.example.com/v1",
            api_key="secret",
            allow_remote=True,
        )


def test_factory_supports_openai_compatible_without_redirecting_embeddings(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        model_provider="openai-compatible",
        model_id="local-model",
        model_base_url="http://127.0.0.1:8080/v1",
        model_api_key=SecretStr("local-secret"),
        embedding_provider="ollama",
        embedding_base_url="http://127.0.0.1:11434",
    )

    provider = create_model_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.endpoint == "http://127.0.0.1:8080/v1/chat/completions"
    assert provider.api_key == "local-secret"
    assert settings.embedding_base_url == "http://127.0.0.1:11434"


def test_health_reports_remote_provider_unconfigured_without_opt_in(tmp_path) -> None:
    settings = Settings(
        data_dir=tmp_path,
        model_provider="openai_compatible",
        model_base_url="https://models.example.com/v1",
        model_remote_allowed=False,
    )

    runtime = probe_model_runtime(settings)

    assert runtime.configured is False
    assert runtime.reachable is False


@pytest.mark.parametrize(
    "base_url, allow_remote",
    [
        ("http://127.0.0.1:8080/v1", False),
        ("https://models.example.invalid/v1", True),
    ],
)
def test_redirect_never_forwards_key_or_escapes_local_origin(
    monkeypatch,
    base_url,
    allow_remote,
) -> None:
    endpoint = base_url + "/chat/completions"
    requests = []
    token = "synthetic-redirect-test-token"

    def respond(request):
        requests.append(request)
        assert request.full_url == endpoint, "redirect exposed the credential to another origin"
        headers = Message()
        headers["Location"] = "https://untrusted.example.invalid/collect"
        response = addinfourl(BytesIO(b""), headers, request.full_url, 302)
        response.msg = "Found"
        return response

    class HttpServer(HTTPHandler):
        def http_open(self, request):
            return respond(request)

    class HttpsServer(HTTPSHandler):
        def https_open(self, request):
            return respond(request)

    # Exercise urllib's actual redirect/proxy machinery with an in-memory HTTP transport.
    monkeypatch.setenv("http_proxy", "http://proxy.example.invalid:9999")
    monkeypatch.setenv("no_proxy", "")
    monkeypatch.setenv("NO_PROXY", "")
    monkeypatch.setattr(
        openai_module,
        "build_opener",
        lambda *handlers: build_opener(*handlers, HttpServer(), HttpsServer()),
    )
    provider = OpenAICompatibleProvider(
        model="synthetic-model",
        base_url=base_url,
        api_key=token,
        allow_remote=allow_remote,
    )
    with pytest.raises(openai_module.OpenAICompatibleError, match="HTTP 302") as caught:
        provider.generate_text(system="synthetic connection test", user="synthetic prompt")
    assert caught.value.status_code == 302
    assert token not in str(caught.value)
    assert len(requests) == 1
    assert requests[0].get_header("Authorization") == f"Bearer {token}"
    if not allow_remote:
        assert requests[0].host == "127.0.0.1:8080", "loopback traffic entered a proxy"


def test_model_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="must not embed credentials"):
        OpenAICompatibleProvider(
            model="synthetic-model", base_url="http://user:secret@localhost:8080"
        )
