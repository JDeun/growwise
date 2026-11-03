from __future__ import annotations

import json
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from .privacy import is_loopback_endpoint
from .provider import ModelProvider, T
from .resilience import FailureCircuit


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        allow_remote: bool = False,
        temperature: float = 0.1,
        timeout_seconds: float = 12.0,
        max_output_tokens: int = 4096,
        reasoning: bool | None = None,
        context_tokens: int | None = None,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
    ) -> None:
        if not model.strip():
            raise ValueError("model must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 64 <= max_output_tokens <= 65_536:
            raise ValueError("max_output_tokens must be between 64 and 65536")
        if context_tokens is not None and not 1024 <= context_tokens <= 131_072:
            raise ValueError("context_tokens must be between 1024 and 131072")

        self.model = model.strip()
        self.base_url = base_url.strip()
        if not is_loopback_endpoint(self.base_url) and not allow_remote:
            raise ValueError(
                "remote Ollama endpoint requires GROWWISE_MODEL_REMOTE_ALLOWED=true"
            )
        self.timeout_seconds = timeout_seconds
        self._circuit = FailureCircuit(
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
        )
        self._chat = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=temperature,
            num_predict=max_output_tokens,
            reasoning=reasoning,
            num_ctx=context_tokens,
            client_kwargs={"timeout": timeout_seconds},
        )

    def generate_text(self, *, system: str, user: str) -> str:
        permit = self._circuit.before_call()
        try:
            response = self._chat.invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            content = str(response.content)
        except Exception:
            self._circuit.record_failure(permit)
            raise
        self._circuit.record_success(permit)
        return content

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        permit = self._circuit.before_call()
        try:
            structured = self._chat.with_structured_output(schema, method="json_schema")
            # Ollama constrains JSON decoding but does not put the schema in the model's prompt.
            # Ground the field meanings as well, as recommended by its structured-output API.
            grounded_system = (
                f"{system}\n\nReturn the fully populated JSON object matching this schema, "
                "not the schema itself:\n"
                f"{json.dumps(schema.model_json_schema(), ensure_ascii=False)}"
            )
            result = structured.invoke(
                [SystemMessage(content=grounded_system), HumanMessage(content=user)]
            )
            if isinstance(result, BaseModel):
                parsed = cast(T, result)
            else:
                parsed = schema.model_validate(result)
        except Exception:
            self._circuit.record_failure(permit)
            raise
        self._circuit.record_success(permit)
        return parsed
