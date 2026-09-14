from growwise.config import Settings
from growwise.model.health import probe_model_runtime


def test_disabled_llm_is_core_only_without_probe() -> None:
    health = probe_model_runtime(Settings(llm_features_enabled=False))
    assert health.configured is False
    assert health.reachable is False


def test_unreachable_ollama_is_degraded_not_core_failure() -> None:
    settings = Settings(
        llm_features_enabled=True,
        model_provider="ollama",
        model_base_url="http://127.0.0.1:1",
    )
    health = probe_model_runtime(settings, timeout_seconds=0.01)
    assert health.configured is True
    assert health.reachable is False
