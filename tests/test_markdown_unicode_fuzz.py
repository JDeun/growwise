from __future__ import annotations

import random
from pathlib import Path

from growwise.domain import ChildProfile, Stage
from growwise.storage.markdown import MarkdownRepository

_SEED = 0x47524F57
_ALPHABET = [
    "가", "나", "다", "A", "z", "0", "9", " ", "-", "_", ":", "#", "[", "]", "{", "}",
    "é", "e\u0301", "中", "🙂", "🌱", "→", "·", "'", '"', "\n", "\t", "\u200b", "\u2060",
]


def _text(rng: random.Random, *, minimum: int = 1, maximum: int = 60) -> str:
    length = rng.randint(minimum, maximum)
    value = "".join(rng.choice(_ALPHABET) for _ in range(length))
    if not value.strip():
        value = "synthetic"
    return value


def test_markdown_roundtrip_survives_deterministic_unicode_fuzz_corpus(tmp_path: Path) -> None:
    rng = random.Random(_SEED)
    repository = MarkdownRepository(tmp_path / "records")

    for index in range(300):
        nickname = _text(rng, maximum=40)
        notes = _text(rng, maximum=120)
        interests = [_text(rng, maximum=30) for _ in range(rng.randint(0, 5))]
        profile = ChildProfile(
            nickname=nickname,
            stage=rng.choice(list(Stage)),
            age_months=rng.choice([None, 0, 1, 12, 60, 120, 180, 240]),
            interests=interests,
            notes=notes,
        )
        path = repository.save(profile)
        loaded = repository.load(path, ChildProfile)

        assert loaded == profile, f"unicode roundtrip drift at deterministic case {index}"


def test_roundtrip_fuzz_seed_is_stable_and_large_enough() -> None:
    rng = random.Random(_SEED)
    samples = {_text(rng, maximum=30) for _ in range(100)}
    assert len(samples) >= 95
