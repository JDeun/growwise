from __future__ import annotations

import logging
from typing import Protocol

from langchain_ollama import OllamaEmbeddings

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class OllamaEmbeddingProvider:
    def __init__(self, *, model: str, base_url: str) -> None:
        self.model = model
        try:
            self._embedding = OllamaEmbeddings(model=model, base_url=base_url)
        except Exception:
            logger.exception("failed to initialize Ollama embedding provider for model %s", model)
            raise

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        try:
            return self._embedding.embed_documents(texts)
        except Exception:
            logger.exception("Ollama document embedding failed for model %s", self.model)
            raise

    def embed_query(self, text: str) -> list[float]:
        try:
            return self._embedding.embed_query(text)
        except Exception:
            logger.exception("Ollama query embedding failed for model %s", self.model)
            raise
