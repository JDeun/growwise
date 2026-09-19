from __future__ import annotations

import json
import re
from ipaddress import ip_address
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from .provider import ModelProvider, T
from .resilience import FailureCircuit

_MAX_RESPONSE_BYTES = 2_000_000
_JSON_FENCE = re.compile(r"^\s*\`\`\`(?:json)?\s*(.*?)\s*\`\`\`\s*$", re.DOTALL | re.IGNORECASE)
_FORMAT_RETRY_CODES = {400, 404, 415, 422}


class OpenAICompatibleError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    normalized = host.strip().strip("[]").casefold()
    if normalized == "localhost" or normalized.endswith(".localhost"):
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


def _chat_completions_url(base_url: str) -> str:
    raw = base_url.strip()
    if not raw:
        raise ValueError("model_base_url cannot be empty")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("OpenAI-compatible model_base_url must be an http(s) URL")

    path = parsed.path.rstrip("/")
    if path.endswith("/chat/completions"):
        final_path = path
    elif path.endswith("/v1"):
        final_path = f"{path}/chat/completions"
    else:
        final_path = f"{path}/v1/chat/completions"
    return urlunparse(parsed._replace(path=final_path, params="", query="", fragment=""))


def _strip_json_fence(value: str) -> str:
    match = _JSON_FENCE.match(value)
    return match.group(1).strip() if match else value.strip()


class OpenAICompatibleProvider(ModelProvider):
    """Minimal Chat Completions provider for local or remote OpenAI-compatible endpoints.

    No vendor SDK is required. Remote endpoints are opt-in because material generation may include
    child stage/interests and generalized learning context. An API key is never embedded in errors.
    """

    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        api_key: str | None = None,
        allow_remote: bool = False,
        temperature: float = 0.1,
        timeout_seconds: float = 12.0,
        max_output_tokens: int = 4096,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_output_tokens < 64:
            raise ValueError("max_output_tokens must be at least 64")

        self.model = model.strip()
        self.base_url = base_url.strip()
        self.endpoint = _chat_completions_url(self.base_url)
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.temperature = temperature
        self.timeout_seconds = timeout_seconds
        self.max_output_tokens = max_output_tokens

        parsed = urlparse(self.endpoint)
        loopback = _is_loopback(parsed.hostname)
        if not loopback and not allow_remote:
            raise ValueError(
                "remote OpenAI-compatible endpoint requires GROWWISE_MODEL_REMOTE_ALLOWED=true"
            )
        if self.api_key and parsed.scheme != "https" and not loopback:
            raise ValueError("API-key authenticated remote model endpoints must use HTTPS")

        self._circuit = FailureCircuit(
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
        )

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "GrowWise/0.1",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(
            self.endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # noqa: S310
                raw = response.read(_MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise OpenAICompatibleError(
                f"OpenAI-compatible endpoint returned HTTP {exc.code}",
                status_code=exc.code,
            ) from exc
        except URLError as exc:
            raise OpenAICompatibleError("OpenAI-compatible endpoint is unreachable") from exc

        if len(raw) > _MAX_RESPONSE_BYTES:
            raise OpenAICompatibleError("OpenAI-compatible response exceeded size limit")
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise OpenAICompatibleError("OpenAI-compatible endpoint returned invalid JSON") from exc
        if not isinstance(parsed, dict):
            raise OpenAICompatibleError("OpenAI-compatible endpoint returned an invalid payload")
        return cast(dict[str, Any], parsed)

    def _chat(
        self,
        *,
        system: str,
        user: str,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        result = self._post(payload)
        choices = result.get("choices")
        if not isinstance(choices, list) or not choices:
            raise OpenAICompatibleError("OpenAI-compatible response contained no choices")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise OpenAICompatibleError("OpenAI-compatible response choice was invalid")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise OpenAICompatibleError("OpenAI-compatible response message was invalid")
        content = message.get("content")
        if isinstance(content, str):
            text = content
        elif isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
            text = "\n".join(parts)
        else:
            raise OpenAICompatibleError("OpenAI-compatible response content was invalid")
        if not text.strip():
            raise OpenAICompatibleError("OpenAI-compatible response content was empty")
        return text

    def generate_text(self, *, system: str, user: str) -> str:
        permit = self._circuit.before_call()
        try:
            content = self._chat(system=system, user=user)
        except Exception:
            self._circuit.record_failure(permit)
            raise
        self._circuit.record_success(permit)
        return content

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        permit = self._circuit.before_call()
        schema_payload = schema.model_json_schema()
        response_format = {
            "type": "json_schema",
            "json_schema": {
                "name": schema.__name__[:64] or "GrowWiseStructuredOutput",
                "strict": True,
                "schema": schema_payload,
            },
        }
        try:
            try:
                content = self._chat(
                    system=system,
                    user=user,
                    response_format=response_format,
                )
            except OpenAICompatibleError as exc:
                if exc.status_code not in _FORMAT_RETRY_CODES:
                    raise
                # llama.cpp and other compatible servers may implement Chat Completions without
                # json_schema response_format. Fall back to a strict JSON-only instruction while
                # preserving the same Pydantic validation boundary.
                content = self._chat(
                    system=system,
                    user=(
                        f"{user}\n\nReturn ONLY one JSON object matching this JSON Schema:\n"
                        f"{json.dumps(schema_payload, ensure_ascii=False)}"
                    ),
                )
            parsed = schema.model_validate_json(_strip_json_fence(content))
        except Exception:
            self._circuit.record_failure(permit)
            raise
        self._circuit.record_success(permit)
        return parsed
