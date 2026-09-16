from __future__ import annotations

import threading
import time
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from .provider import ModelProvider, T


class ModelCircuitOpen(RuntimeError):
    """Raised when repeated model failures have temporarily opened the local circuit."""


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
        if failure_threshold <= 0:
            raise ValueError("failure_threshold must be positive")
        if recovery_seconds <= 0:
            raise ValueError("recovery_seconds must be positive")

        self.model = model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failure_count = 0
        self._open_until = 0.0
        self._circuit_lock = threading.Lock()
        self._chat = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
            client_kwargs={"timeout": timeout_seconds},
        )

    def _before_call(self) -> None:
        now = time.monotonic()
        with self._circuit_lock:
            if self._open_until > now:
                remaining = self._open_until - now
                raise ModelCircuitOpen(
                    f"model circuit is open for another {remaining:.1f}s"
                )
            if self._open_until:
                # Half-open: allow one new request after the cooldown. A successful call fully
                # resets the circuit; a failure opens it again below.
                self._open_until = 0.0

    def _record_success(self) -> None:
        with self._circuit_lock:
            self._failure_count = 0
            self._open_until = 0.0

    def _record_failure(self) -> None:
        with self._circuit_lock:
            self._failure_count += 1
            if self._failure_count >= self.failure_threshold:
                self._open_until = time.monotonic() + self.recovery_seconds

    def generate_text(self, *, system: str, user: str) -> str:
        self._before_call()
        try:
            response = self._chat.invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
            content = str(response.content)
        except Exception:
            self._record_failure()
            raise
        self._record_success()
        return content

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        self._before_call()
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
            self._record_failure()
            raise
        self._record_success()
        return parsed
