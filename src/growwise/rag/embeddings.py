from __future__ import annotations

from typing import Protocol

from langchain_ollama import OllamaEmbeddings

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
        timeout_seconds: float = 8.0,
        failure_threshold: int = 3,
        recovery_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self._circuit = FailureCircuit(
            failure_threshold=failure_threshold,
            recovery_seconds=recovery_seconds,
        )
        self._embedding = OllamaEmbeddings(
            model=model,
            base_url=base_url,
            client_kwargs={"timeout": timeout_seconds},
        )

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self._circuit.before_call()
        try:
            result = self._embedding.embed_documents(texts)
        except Exception:
            self._circuit.record_failure()
            raise
        self._circuit.record_success()
        return result

    def embed_query(self, text: str) -> list[float]:
        self._circuit.before_call()
        try:
            result = self._embedding.embed_query(text)
        except Exception:
            self._circuit.record_failure()
            raise
        self._circuit.record_success()
        return result
