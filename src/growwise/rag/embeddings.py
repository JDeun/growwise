from __future__ import annotations

from typing import Protocol

from langchain_ollama import OllamaEmbeddings


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    def __init__(self, *, model: str, base_url: str) -> None:
        self._embedding = OllamaEmbeddings(model=model, base_url=base_url)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embedding.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embedding.embed_query(text)
