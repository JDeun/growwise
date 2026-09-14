from __future__ import annotations

from typing import cast

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from pydantic import BaseModel

from .provider import ModelProvider, T


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
        self._chat = ChatOllama(
            model=model,
            base_url=base_url,
            temperature=temperature,
        )

    def generate_text(self, *, system: str, user: str) -> str:
        response = self._chat.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        return str(response.content)

    def generate_structured(self, *, system: str, user: str, schema: type[T]) -> T:
        structured = self._chat.with_structured_output(schema)
        result = structured.invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        if isinstance(result, BaseModel):
            return cast(T, result)
        return schema.model_validate(result)
