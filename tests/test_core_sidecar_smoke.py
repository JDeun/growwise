"""The packaging harness must consume real API envelopes, not invented response shapes."""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from fastapi.testclient import TestClient

from growwise.api import main, photo_routes
from growwise.config import Settings
from growwise.storage import EntityStore

SCRIPT = Path(__file__).resolve().parents[1] / "desktop/scripts/smoke_core_sidecar.py"
SPEC = importlib.util.spec_from_file_location("smoke_core_sidecar", SCRIPT)
assert SPEC and SPEC.loader
smoke = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(smoke)


def test_packaging_photo_probe_uses_real_create_envelope_and_thumbnail_codecs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = Settings(
        data_dir=tmp_path,
        llm_features_enabled=False,
        vision_features_enabled=False,
        embedding_features_enabled=False,
        public_enrichment_enabled=False,
    )
    store = EntityStore(settings.records_dir, settings.index_path)
    for dependency, value in (
        (main.get_settings, settings),
        (main.get_store, store),
        (photo_routes.get_photo_settings, settings),
        (photo_routes.get_photo_store, store),
    ):
        monkeypatch.setitem(main.app.dependency_overrides, dependency, lambda value=value: value)
    client = TestClient(main.app)
    paths = []

    def transport(request, *, timeout):
        assert timeout == 10
        assert request.get_header("Authorization") == "Bearer synthetic-smoke-session"
        path = urlsplit(request.full_url).path
        paths.append(path)
        response = client.request(
            request.method, path, content=request.data,
            headers={"Content-Type": "application/json"},
        )
        assert 200 <= response.status_code < 300, response.text
        return io.BytesIO(response.content)

    monkeypatch.setattr(smoke.urllib.request, "urlopen", transport)
    smoke.assert_packaged_photo_thumbnail("http://127.0.0.1:1234", "synthetic-smoke-session")
    assert len(paths) == 3
    assert paths[-1].endswith("/thumbnail")
    assert "synthetic PNG -> bounded JPEG" in capsys.readouterr().out
    assert len(store.index.list_entities(entity_type="photo_activity_record")) == 1


def test_sidecar_ci_has_clean_pinned_runtime_and_offline_attribution_inputs():
    workflow = (SCRIPT.parents[2] / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    job = workflow.split("  core-sidecar-smoke:", 1)[1]
    assert "--extra desktop-build --managed-python --python 3.12.13" in job
    assert "npm ci --prefix desktop --omit=dev" in job
    assert "cargo fetch --locked" in job
    assert "build_license_bundle.py --check" in job
    assert "uv run --no-sync python desktop/scripts/smoke_core_sidecar.py" in job
    assert "UV_PYTHON_INSTALL_DIR: ${{ runner.temp }}/growwise-packaging-python" in job
    assert "--python-downloads-json-url https://raw.githubusercontent.com/astral-sh/uv/" in job
