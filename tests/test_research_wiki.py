from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("research_wiki", ROOT / "scripts/research_wiki.py")
assert SPEC and SPEC.loader
wiki = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(wiki)


@pytest.fixture
def wiki_root(tmp_path: Path) -> Path:
    # Copy only public references, excluding private app state and dependencies.
    for name in ("docs", "src", "scripts", "tests"):
        shutil.copytree(ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__"))
    return tmp_path


def _append(path: Path, record: dict) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def test_repository_wiki_has_all_workstreams_and_only_real_links() -> None:
    assert wiki.check(ROOT) >= 5
    assert {
        row["workstream"] for row in wiki.read_registry(ROOT / "docs/knowledge/sources.jsonl")
    } == wiki.WORKSTREAMS


def test_offline_search_is_case_insensitive_and_conjunctive() -> None:
    matches = wiki.search(ROOT, "SCAFFOLD")
    assert matches
    assert all("scaffold" in match["text"].casefold() for match in matches)
    assert wiki.search(ROOT, "unlikely-missing-token-7f28") == []
    with pytest.raises(ValueError, match="at least one"):
        wiki.search(ROOT, "   ")


@pytest.mark.parametrize(
    "text, expected",
    [
        ("[broken](missing.md)", "missing local reference"),
        ("[escape](../../../../outside)", "escapes repository"),
        ("[bad](http://example.invalid/reference)", "HTTPS"),
        ("unknown source:GW-NOT-REGISTERED", "unknown source"),
    ],
)
def test_checker_rejects_broken_or_unattributed_references(
    wiki_root: Path,
    text: str,
    expected: str,
) -> None:
    (wiki_root / "docs/knowledge/broken.md").write_text(text)
    with pytest.raises(ValueError, match=expected):
        wiki.check(wiki_root)


def test_checker_rejects_duplicate_sources_and_fabricated_run_status(wiki_root: Path) -> None:
    ledger = wiki_root / "docs/knowledge/sources.jsonl"
    first = wiki.read_registry(ledger)[0]
    _append(ledger, first)
    with pytest.raises(ValueError, match="duplicate source"):
        wiki.check(wiki_root)


def test_observed_experiment_requires_artifact_and_known_environment(wiki_root: Path) -> None:
    ledger = wiki_root / "docs/knowledge/experiments.jsonl"
    row = wiki.read_registry(ledger)[0]
    row.update(id="EXP-UNPROVEN", status="observed")
    _append(ledger, row)
    with pytest.raises(ValueError, match="missing observed_on"):
        wiki.check(wiki_root)
    row.update(observed_on="2026-11-03", artifact="docs/README.md", revision="unknown")
    ledger.write_text(json.dumps(row) + "\n")
    with pytest.raises(ValueError, match="cannot be unknown"):
        wiki.check(wiki_root)
    row.update(
        revision="synthetic-fixture-revision",
        environment="Python test synthetic fixture",
        outcome="Synthetic metadata accepted in unit test; no real study performed",
    )
    ledger.write_text(json.dumps(row) + "\n")
    assert wiki.check(wiki_root) >= 5


def test_registry_history_allows_append_but_rejects_rewrite(wiki_root: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=wiki_root, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-q")
    git("add", "docs/knowledge")
    git(
        "-c",
        "user.name=Fixture",
        "-c",
        "user.email=fixture@example.invalid",
        "commit",
        "-qm",
        "synthetic baseline",
    )
    baseline = git("rev-parse", "HEAD")
    ledger = wiki_root / "docs/knowledge/sources.jsonl"
    row = wiki.read_registry(ledger)[0]
    row["id"] = "GW-APPENDED"
    _append(ledger, row)
    assert wiki.check(wiki_root, base_ref=baseline) >= 6
    ledger.write_text(
        ledger.read_text().replace('"id": "GW-CURRICULUM-DESIGN"', '"id": "GW-REWRITTEN"', 1)
    )
    # Avoid stale source refs so the specific history invariant is exercised.
    row = wiki.read_registry(ledger)[0]
    row["id"] = "GW-CURRICULUM-DESIGN"
    _append(ledger, row)
    with pytest.raises(ValueError, match="historical entries"):
        wiki.check(wiki_root, base_ref=baseline)


def _watcher_payload(url: str = "https://www.ncic.re.kr/bbs/ncicnotice/view.do?id=example") -> dict:
    return {
        "status": "update_candidate",
        "count": 1,
        "candidates": [
            {
                "source": "ncic",
                "marker": "synthetic future notice",
                "title": "교육과정 검토 후보",
                "url": url,
            }
        ],
    }


def test_curriculum_import_remains_review_only_and_writes_no_runtime_state() -> None:
    original = _watcher_payload()
    before = json.dumps(original)
    result = wiki.curriculum_candidates(original)
    assert json.dumps(original) == before
    assert result[0]["status"] == "candidate"
    assert result[0]["revision"] == "unknown"
    assert result[0]["effective_dates"] == []
    assert "required" in result[0]["review"]
    assert wiki.curriculum_candidates({"status": "current", "count": 0, "candidates": []}) == []


@pytest.mark.parametrize(
    "url",
    [
        "http://www.ncic.re.kr/notice",
        "https://www.ncic.re.kr.evil.invalid/notice",
        "https://www.moe.go.kr/notice",
        "https://private.invalid/notice",
        "https://user:password@www.ncic.re.kr/notice",
        "https://www.ncic.re.kr:8443/notice",
    ],
)
def test_curriculum_import_rejects_nonmatching_official_origin(url: str) -> None:
    with pytest.raises(ValueError, match="official watcher source"):
        wiki.curriculum_candidates(_watcher_payload(url))


@pytest.mark.parametrize("payload", [[], {}, {"status": "current", "count": 0, "candidates": [1]}])
def test_curriculum_import_rejects_malformed_watcher_data(payload: Any) -> None:
    with pytest.raises(ValueError):
        wiki.curriculum_candidates(payload)


def test_cli_reads_watcher_file_and_reports_invalid_inputs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / "watcher.json"
    path.write_text(json.dumps(_watcher_payload()))
    assert wiki.main(["curriculum-candidates", str(path)]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "candidate"
    path.write_text("bad JSON")
    assert wiki.main(["curriculum-candidates", str(path)]) == 1
    assert "Research wiki error" in capsys.readouterr().out
