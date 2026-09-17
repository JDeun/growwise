from __future__ import annotations

from typing import Protocol

from langchain_ollama import OllamaEmbeddings

from growwise.config import Settings
from growwise.model.resilience import FailureCircuit


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        model: str,
        base_url: str,
        timeout_seconds: float | None = None,
        failure_threshold: int | None = None,
        recovery_seconds: float | None = None,
    ) -> None:
        settings = Settings()
        effective_timeout = (
            settings.embedding_timeout_seconds if timeout_seconds is None else timeout_seconds
        )
        effective_threshold = (
            settings.model_circuit_failure_threshold
            if failure_threshold is None
            else failure_threshold
        )
        effective_recovery = (
            settings.model_circuit_recovery_seconds
            if recovery_seconds is None
            else recovery_seconds
        )
        if effective_timeout <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._circuit = FailureCircuit(
            failure_threshold=effective_threshold,
            recovery_seconds=effective_recovery,
        )
        self._embedding = OllamaEmbeddings(
            model=model,
            base_url=base_url,
            client_kwargs={"timeout": effective_timeout},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        permit = self._circuit.before_call()
        try:
            result = self._embedding.embed_documents(texts)
        except Exception:
            self._circuit.record_failure(permit)
            raise
        self._circuit.record_success(permit)
        return result

    def embed_query(self, text: str) -> list[float]:
        permit = self._circuit.before_call()
        try:
            result = self._embedding.embed_query(text)
        except Exception:
            self._circuit.record_failure(permit)
            raise
        self._circuit.record_success(permit)
        return result
