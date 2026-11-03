#!/usr/bin/env python3
"""Check and search the public maintainer wiki without network or model access."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
WORKSTREAMS = {"curriculum", "pedagogy", "models", "rag-safety", "evaluation"}
STATUSES = {"design", "implemented", "reported", "observed", "candidate"}
REGISTRIES = ("sources.jsonl", "experiments.jsonl")
LINK = re.compile(r"(?<!!)\[[^\]\n]+\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)")
SOURCE_REF = re.compile(r"\bsource:(GW-[A-Z0-9-]+)\b")


def read_registry(path: Path) -> list[dict]:
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError(f"{path.name}:{number}: expected an object")
        records.append(item)
    return records


def local_target(root: Path, parent: Path, target: str) -> Path:
    path = (parent / unquote(target.split("#", 1)[0])).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"link escapes repository: {target}")
    return path


def validate_location(root: Path, parent: Path, target: str) -> None:
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError(f"expected a public HTTPS reference: {target}")
    elif not target.startswith("#") and not local_target(root, parent, target).exists():
        raise ValueError(f"missing local reference: {target}")


def required_text(record: dict, fields: tuple[str, ...]) -> None:
    if not isinstance(record, dict):
        raise ValueError("expected a metadata object")
    for field in fields:
        value = record.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{record.get('id', '?')}: missing {field}")


def check(root: Path, *, base_ref: str | None = None) -> int:
    wiki = root / "docs/knowledge"
    registries = {name: read_registry(wiki / name) for name in REGISTRIES}
    sources = registries["sources.jsonl"]
    source_ids = set()
    covered = set()
    for source in sources:
        required_text(
            source,
            (
                "id",
                "title",
                "workstream",
                "location",
                "recorded_on",
                "revision",
                "status",
                "license",
                "summary",
            ),
        )
        if not re.fullmatch(r"GW-[A-Z0-9-]+", source["id"]) or source["id"] in source_ids:
            raise ValueError(f"invalid or duplicate source ID: {source['id']}")
        source_ids.add(source["id"])
        if source["workstream"] not in WORKSTREAMS or source["status"] not in STATUSES:
            raise ValueError(f"{source['id']}: invalid workstream/status")
        date.fromisoformat(source["recorded_on"])
        validate_location(root, root, source["location"])
        covered.add(source["workstream"])
    if covered != WORKSTREAMS:
        raise ValueError(f"missing workstreams: {sorted(WORKSTREAMS - covered)}")

    experiment_ids = set()
    for experiment in registries["experiments.jsonl"]:
        required_text(
            experiment,
            (
                "id",
                "hypothesis",
                "workstream",
                "status",
                "recorded_on",
                "command",
                "fixture",
                "model_revision",
                "environment",
                "outcome",
                "privacy_review",
            ),
        )
        if experiment["id"] in experiment_ids:
            raise ValueError(f"duplicate experiment ID: {experiment['id']}")
        experiment_ids.add(experiment["id"])
        if experiment["workstream"] not in WORKSTREAMS:
            raise ValueError(f"{experiment['id']}: invalid workstream")
        date.fromisoformat(experiment["recorded_on"])
        if experiment["status"] not in {"planned", "observed", "failed", "superseded"}:
            raise ValueError(f"{experiment['id']}: invalid experiment status")
        refs = experiment.get("source_ids")
        if (
            not isinstance(refs, list)
            or not refs
            or any(not isinstance(ref, str) or ref not in source_ids for ref in refs)
        ):
            raise ValueError(f"{experiment['id']}: unknown or missing source_ids")
        if experiment["status"] in {"observed", "failed"}:
            required_text(experiment, ("observed_on", "artifact", "revision"))
            date.fromisoformat(experiment["observed_on"])
            if any(
                experiment[field].casefold().startswith("unknown")
                for field in ("environment", "revision", "model_revision", "outcome")
            ):
                raise ValueError(f"{experiment['id']}: run evidence cannot be unknown")
            validate_location(root, root, experiment["artifact"])

    for document in [*wiki.rglob("*.md"), root / "docs/adr/README.md"]:
        content = document.read_text(encoding="utf-8")
        for target in LINK.findall(content):
            validate_location(root, document.parent, target)
        for source_id in SOURCE_REF.findall(content):
            if source_id not in source_ids:
                raise ValueError(f"{document.name}: unknown source:{source_id}")

    if base_ref and set(base_ref) != {"0"}:
        subprocess.run(
            ["git", "cat-file", "-e", f"{base_ref}^{{commit}}"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        for name, current in registries.items():
            old = subprocess.run(
                ["git", "show", f"{base_ref}:docs/knowledge/{name}"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
            )
            if old.returncode == 0:
                previous = [json.loads(line) for line in old.stdout.splitlines() if line.strip()]
                if current[: len(previous)] != previous:
                    raise ValueError(
                        f"{name}: historical entries must remain unchanged; append a new ID"
                    )
    return len(sources)


def search(root: Path, query: str) -> list[dict[str, str | int]]:
    terms = query.casefold().split()
    if not terms:
        raise ValueError("search needs at least one word")
    matches = []
    for path in sorted((root / "docs/knowledge").rglob("*")):
        if path.suffix not in {".md", ".jsonl"}:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if all(term in line.casefold() for term in terms):
                matches.append({"path": str(path.relative_to(root)), "line": number, "text": line})
    return matches


def curriculum_candidates(payload: dict) -> list[dict]:
    """Project watcher output into review-only records; never write curriculum runtime state."""
    if not isinstance(payload, dict):
        raise ValueError("expected watcher metadata object")
    candidates = payload.get("candidates")
    if payload.get("status") not in {"current", "update_candidate"} or not isinstance(
        candidates, list
    ):
        raise ValueError("expected check_curriculum_updates.py JSON output")
    if payload.get("count") != len(candidates):
        raise ValueError("candidate count mismatch")
    records = []
    for candidate in candidates:
        required_text(candidate, ("source", "marker", "title", "url"))
        allowed = {"ncic": "www.ncic.re.kr", "moe_early_childhood": "www.moe.go.kr"}
        parsed = urlsplit(candidate["url"])
        if (
            parsed.scheme != "https"
            or parsed.hostname != allowed.get(candidate["source"])
            or parsed.username
            or parsed.password
            or parsed.port not in {None, 443}
        ):
            raise ValueError("candidate must point to its official watcher source")
        records.append(
            {
                "source": candidate["source"],
                "notice": candidate["marker"],
                "title": candidate["title"],
                "location": candidate["url"],
                "status": "candidate",
                "revision": "unknown",
                "effective_dates": [],
                "applicability": "unknown; verify grade, stage and effective dates before use",
                "license": "unknown; link only, no original text redistribution",
                "review": "required; this record cannot activate runtime curriculum",
            }
        )
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    checker = subparsers.add_parser("check", help="validate structure, provenance and local links")
    checker.add_argument("--base-ref", help="also enforce append-only history against a Git commit")
    finder = subparsers.add_parser("search", help="case-insensitive offline search (all words)")
    finder.add_argument("query")
    importer = subparsers.add_parser(
        "curriculum-candidates", help="print review-only watcher records"
    )
    importer.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.action == "check":
            print(f"Research wiki valid: {check(ROOT, base_ref=args.base_ref)} sources")
        elif args.action == "search":
            for match in search(ROOT, args.query):
                print(f"{match['path']}:{match['line']}: {match['text']}")
        else:
            for candidate in curriculum_candidates(
                json.loads(args.input.read_text(encoding="utf-8"))
            ):
                print(json.dumps(candidate, ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Research wiki error: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
