import pytest

from growwise.config import Settings
from growwise.model import create_model_provider
from growwise.model.ollama import OllamaProvider


def test_ollama_factory_applies_generation_budget_without_unbounded_thinking(tmp_path):
    provider = create_model_provider(Settings(data_dir=tmp_path, model_max_output_tokens=512))
    assert isinstance(provider, OllamaProvider)
    assert provider._chat.num_predict == 512
    assert provider._chat.reasoning is False


def test_background_generation_has_independent_quality_budget(tmp_path):
    settings = Settings(data_dir=tmp_path, model_timeout_seconds=2, model_max_output_tokens=128)
    provider = create_model_provider(settings, background=True)
    assert isinstance(provider, OllamaProvider)
    assert provider.timeout_seconds == 600
    assert provider._chat.num_predict == 8192
    assert provider._chat.reasoning is False
    assert provider._chat.num_ctx == 8192


def test_background_reasoning_and_context_are_explicit_opt_in(tmp_path):
    provider = create_model_provider(Settings(
        data_dir=tmp_path, background_ai_reasoning_enabled=True,
        background_ai_model_context_tokens=16384,
    ), background=True)
    assert isinstance(provider, OllamaProvider)
    assert provider._chat.reasoning is True
    assert provider._chat.num_ctx == 16384


@pytest.mark.parametrize("limit", [0, 1023, 131_073])
def test_ollama_rejects_invalid_context_budget(limit):
    with pytest.raises(ValueError, match="context_tokens"):
        OllamaProvider(model="test:latest", context_tokens=limit)


@pytest.mark.parametrize("limit", [0, 63, 65_537])
def test_ollama_rejects_invalid_generation_budget(limit):
    with pytest.raises(ValueError, match="max_output_tokens"):
        OllamaProvider(model="test:latest", max_output_tokens=limit)
