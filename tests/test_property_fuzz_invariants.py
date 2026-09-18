from __future__ import annotations

import random
import string
import unicodedata

import pytest

from growwise.backup import BackupService, InvalidBackup
from growwise.idempotency import request_fingerprint
from growwise.rag.index import _normalize_query_terms, cosine_similarity

_SEED = 0x47524F57


def _random_component(rng: random.Random, *, min_length: int = 2, max_length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "-_"
    length = rng.randint(min_length, max_length)
    return "".join(rng.choice(alphabet) for _ in range(length))


def test_portable_member_key_randomized_case_and_unicode_equivalence() -> None:
    rng = random.Random(_SEED)
    for _ in range(1_000):
        component = _random_component(rng)
        base = f"assets/{component}/Caf\u00e9-{_random_component(rng)}.jpg"
        case_variant = "/".join(
            "".join(char.swapcase() if char.isalpha() else char for char in part)
            for part in base.split("/")
        )
        nfd_variant = unicodedata.normalize("NFD", case_variant)

        expected = BackupService._portable_member_key(base)
        assert BackupService._portable_member_key(case_variant) == expected
        assert BackupService._portable_member_key(nfd_variant) == expected


def test_portable_member_validation_randomized_collision_rejection() -> None:
    rng = random.Random(_SEED + 1)
    for _ in range(300):
        component = f"Case{_random_component(rng)}"
        left = f"assets/{component}.jpg"
        right = f"assets/{component.swapcase()}.jpg"
        with pytest.raises(InvalidBackup, match="collide on a portable filesystem"):
            BackupService._validate_portable_member_names(["manifest.json", left, right])


@pytest.mark.parametrize("reserved", ["CON", "PRN", "AUX", "NUL", "COM1", "COM9", "LPT1", "LPT9"])
def test_portable_member_validation_rejects_windows_device_names_under_random_extensions(
    reserved: str,
) -> None:
    rng = random.Random(_SEED + len(reserved))
    for _ in range(40):
        extension = _random_component(rng, min_length=2, max_length=8)
        with pytest.raises(InvalidBackup, match="non-portable archive member"):
            BackupService._portable_member_key(f"assets/{reserved}.{extension}")


def test_rag_query_normalization_randomized_invariants() -> None:
    rng = random.Random(_SEED + 2)
    raw_terms: list[str] = []
    for _ in range(1_000):
        token = _random_component(rng, min_length=1, max_length=220)
        raw_terms.extend((token, token.upper(), token.casefold()))

    normalized = _normalize_query_terms(" ".join(raw_terms))

    assert len(normalized) <= 32
    assert len(normalized) == len(set(normalized))
    assert all(2 <= len(term) <= 128 for term in normalized)
    assert all(term == term.casefold() for term in normalized)


def test_rag_query_normalization_is_deterministic_for_randomized_input() -> None:
    rng = random.Random(_SEED + 3)
    for _ in range(250):
        query = " ".join(
            _random_component(rng, min_length=1, max_length=160)
            for _ in range(rng.randint(0, 90))
        )
        assert _normalize_query_terms(query) == _normalize_query_terms(query)


def test_request_fingerprint_ignores_mapping_insertion_order() -> None:
    rng = random.Random(_SEED + 4)
    for _ in range(500):
        keys = [_random_component(rng) for _ in range(rng.randint(1, 20))]
        payload = {key: rng.randint(-1_000_000, 1_000_000) for key in keys}
        items = list(payload.items())
        rng.shuffle(items)
        reordered = dict(items)

        assert request_fingerprint(payload) == request_fingerprint(reordered)


def test_cosine_similarity_randomized_symmetry_identity_and_bounds() -> None:
    rng = random.Random(_SEED + 5)
    for _ in range(500):
        dimension = rng.randint(1, 64)
        left = [rng.uniform(-100.0, 100.0) for _ in range(dimension)]
        right = [rng.uniform(-100.0, 100.0) for _ in range(dimension)]

        forward = cosine_similarity(left, right)
        reverse = cosine_similarity(right, left)
        identity = cosine_similarity(left, left)

        assert forward == pytest.approx(reverse, abs=1e-12)
        assert -1.000000000001 <= forward <= 1.000000000001
        assert identity == pytest.approx(1.0, abs=1e-12)


def test_cosine_similarity_degenerate_vectors_are_safe() -> None:
    assert cosine_similarity([], []) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0
    assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0
