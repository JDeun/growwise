"""Docs/code consistency audit.

Guards that the roadmap does not keep referencing code that no longer exists. When someone
renames a class (e.g. ``ScaffoldGuard`` -> ``ScaffoldChecker``) or removes a test file but
forgets to update ``docs/roadmap.md``, this audit fails.

Scope is deliberately limited to ``docs/roadmap.md`` and to tokens that *clearly* look like
code — a backtick token is only checked when it is a ``*.py`` filename, or a Python/TypeScript
identifier that carries an underscore or CamelCase (or such a dotted path). Plain English words,
shell commands, config/lock filenames, colour codes, HTTP headers, version strings and the like
are skipped, so the guard flags real drift without producing false alarms on prose.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_ROADMAP = _REPO / "docs" / "roadmap.md"
_SELF = Path(__file__).resolve()

_BACKTICK = re.compile(r"`([^`]+)`")
_FENCE = re.compile(r"```.*?```", re.S)
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_DOTTED = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+$")
# Mixed case (CamelCase) marks a token as code-like rather than an English word.
_CAMEL = re.compile(r"[a-z][A-Z]|[A-Z][a-z]")

# Suffixes that mark a token as a config/data/asset file, not a code symbol.
_SKIP_SUFFIXES = {
    ".toml", ".lock", ".json", ".yaml", ".yml", ".cfg", ".ini",
    ".txt", ".md", ".db", ".png", ".exe", ".dmg", ".env", ".conf",
}
# Leading characters that mark a token as non-code (flags, paths, css, checklist, template).
_SKIP_LEADING = "-.#[{*/"

# Roots under which referenced files and symbols must be found.
_FILE_ROOTS = ("tests", "src", "scripts", "desktop/scripts")
_SYMBOL_ROOTS = ("src/growwise", "tests", "desktop/src")
_SYMBOL_PATTERNS = ("*.py", "*.ts", "*.tsx")


def _classify(token: str) -> tuple[str, str] | None:
    """Return ``(kind, name)`` for a checkable token, or ``None`` to skip it.

    ``kind`` is ``"pyfile"`` (a ``*.py`` filename) or ``"symbol"`` (a code identifier).
    """
    tok = token.strip()
    if not tok or any(c.isspace() for c in tok):
        return None
    if tok.endswith(".py"):
        return ("pyfile", tok)
    if tok[0] in _SKIP_LEADING or "/" in tok:
        return None
    if Path(tok).suffix.lower() in _SKIP_SUFFIXES:
        return None
    if _IDENT.match(tok):
        if "_" in tok or _CAMEL.search(tok):
            return ("symbol", tok)
        return None
    if _DOTTED.match(tok):
        last = tok.rsplit(".", 1)[1]
        if "_" in last or _CAMEL.search(last):
            return ("symbol", last)
    return None


def _roadmap_tokens() -> list[tuple[str, str]]:
    text = _FENCE.sub("", _ROADMAP.read_text(encoding="utf-8"))
    out: dict[tuple[str, str], None] = {}
    for match in _BACKTICK.finditer(text):
        classified = _classify(match.group(1))
        if classified is not None:
            out[classified] = None
    return list(out)


def _source_text() -> str:
    parts: list[str] = []
    seen: set[Path] = set()
    for base in _SYMBOL_ROOTS:
        root = _REPO / base
        if not root.is_dir():
            continue
        for pattern in _SYMBOL_PATTERNS:
            for path in sorted(root.rglob(pattern)):
                resolved = path.resolve()
                if resolved == _SELF or resolved in seen:
                    continue
                seen.add(resolved)
                parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(parts)


def _file_exists(name: str) -> bool:
    # Path-qualified tokens (e.g. ``scripts/benchmark_model.py`` or the abbreviated
    # ``model/registry.py`` for ``src/growwise/model/registry.py``) resolve either literally
    # from the repo root or by path-suffix under the source roots (never scanning .venv).
    # Bare filenames are searched under the known roots.
    if "/" in name:
        if (_REPO / name).is_file():
            return True
        needle = "/" + name
        for base in ("src", "tests", "scripts", "desktop/scripts"):
            root = _REPO / base
            if root.is_dir() and any(
                str(path).replace("\\", "/").endswith(needle) for path in root.rglob("*.py")
            ):
                return True
        return False
    return any(
        any((_REPO / base).rglob(name)) for base in _FILE_ROOTS if (_REPO / base).is_dir()
    )


_TOKENS = _roadmap_tokens()
_PYFILES = [name for kind, name in _TOKENS if kind == "pyfile"]
_SYMBOLS = [name for kind, name in _TOKENS if kind == "symbol"]


def test_audit_covers_code_tokens() -> None:
    # Guards the extractor itself: if it silently stops finding tokens, this fails loudly.
    assert _PYFILES, "로드맵에서 코드 파일 참조를 하나도 추출하지 못함 — 추출기 회귀 의심"
    assert _SYMBOLS, "로드맵에서 코드 심볼 참조를 하나도 추출하지 못함 — 추출기 회귀 의심"


@pytest.mark.parametrize("name", sorted(set(_PYFILES)))
def test_roadmap_referenced_file_exists(name: str) -> None:
    assert _file_exists(name), f"roadmap.md가 참조하는 파일이 저장소에 없음: {name}"


def test_roadmap_referenced_symbols_defined() -> None:
    corpus = _source_text()
    missing = [
        name
        for name in sorted(set(_SYMBOLS))
        if re.search(rf"(?<![\w.]){re.escape(name)}\b", corpus) is None
    ]
    assert not missing, f"roadmap.md가 참조하는 심볼이 코드에 정의되지 않음: {missing}"
