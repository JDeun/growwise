from __future__ import annotations

import logging
from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from .provider import ModelProvider, T

logger = logging.getLogger(__name__)


class OllamaProvider(ModelProvider):
    def __init__(
        self,
        *,
        model: str,
        base_url: str = "http://127.0.0.1:11434",
        temperature: float = 0.1,
    ) -> None:
        self.model = model
        self.base_url = base_url
        try:
            self._chat = ChatOllama(
                model=model,
                base_url=base_url,
                temperature=temperature,
            )
        except Exception:
            logger.exception("failed to initialize Ollama model provider for model %s", model)
            raise

    def generate_text(self, *, system: str, user: str) -> str:
        try:
            response = self._chat.invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
        except Exception:
            logger.exception("Ollama text generation failed for model %s", self.model)
            raise
        return str(response.content)

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        try:
            structured = self._chat.with_structured_output(schema)
            result = structured.invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            )
        except Exception:
            logger.exception(
                "Ollama structured generation failed for model %s and schema %s",
                self.model,
                schema.__name__,
            )
            raise
        if isinstance(result, BaseModel):
            return cast(T, result)
        return schema.model_validate(result)
