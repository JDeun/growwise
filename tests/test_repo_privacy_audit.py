"""Repository privacy audit.

Enforces GrowWise's core principle that no real personal data ever lands in the public repo.
Structural PII (Korean phone numbers, resident registration numbers) is rejected everywhere
except the guard's own fixture. A caller may additionally supply real identifiers (e.g. a
child's name) via the ``GROWWISE_PII_DENYLIST`` env var (comma-separated) so CI can enforce
their absence without ever committing them.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]

# Files that legitimately contain PII-shaped strings to exercise the guards.
_ALLOWLIST = {
    "tests/test_material_pii_guard.py",
    "tests/test_repo_privacy_audit.py",
}
# Lock/generated files: long hashes can coincidentally resemble numeric PII.
_SKIP_NAMES = {"uv.lock", "package-lock.json", "Cargo.lock", "yarn.lock"}
_TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ".cfg", ".ini",
    ".rs", ".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".sh",
}

_PHONE = re.compile(r"01[016789][ -]?\d{3,4}[ -]?\d{4}")
# YYMMDD + gender digit(1-4) + 6 digits — plausible resident registration number.
_RRN = re.compile(r"\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])[ -]?[1-4]\d{6}")


def _tracked_text_files() -> Iterator[tuple[str, Path]]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=_REPO, capture_output=True, text=True, check=True
    ).stdout
    for rel in out.splitlines():
        if rel in _ALLOWLIST or Path(rel).name in _SKIP_NAMES:
            continue
        path = _REPO / rel
        if path.suffix.lower() in _TEXT_SUFFIXES and path.is_file():
            yield rel, path


def test_no_structural_pii_in_tracked_files() -> None:
    hits: list[str] = []
    for rel, path in _tracked_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        if _PHONE.search(text) or _RRN.search(text):
            hits.append(rel)
    assert not hits, f"전화번호/주민등록번호 형태의 PII가 발견됨: {sorted(hits)}"


def test_denylist_terms_absent_from_tracked_files() -> None:
    terms = [t.strip() for t in os.environ.get("GROWWISE_PII_DENYLIST", "").split(",") if t.strip()]
    if not terms:
        pytest.skip("GROWWISE_PII_DENYLIST 미설정 — 구조적 감사만 수행")
    hits: list[tuple[str, str]] = []
    for rel, path in _tracked_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        hits.extend((rel, term) for term in terms if term in text)
    assert not hits, f"금지 식별자가 저장소에 존재함: {sorted(hits)}"
