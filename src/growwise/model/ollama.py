from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from .provider import ModelProvider, T
from .resilience import FailureCircuit


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        temperature: float = 0.1,
        timeout_seconds: float = 12.0,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self._circuit = FailureCircuit(
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
        )
        self._chat = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
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
            structured = self._chat.with_structured_output(schema)
            result = structured.invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
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
