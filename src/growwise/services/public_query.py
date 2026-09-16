from __future__ import annotations

import re
from collections.abc import Iterable

# Values in this catalog are intentionally generic educational topics. The external-query boundary
# emits only canonical values from this table, never the parent/child text that happened to match.
_PUBLIC_TOPIC_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("동물", ("동물", "animals", "animal")),
    ("고양이", ("고양이", "cats", "cat")),
    ("강아지", ("강아지", "dogs", "dog")),
    ("공룡", ("공룡", "dinosaurs", "dinosaur")),
    ("화석", ("화석", "fossils", "fossil")),
    ("곤충", ("곤충", "insects", "insect")),
    ("식물", ("식물", "plants", "plant")),
    ("자연", ("자연", "nature")),
    ("환경", ("환경", "environment")),
    ("생태", ("생태", "ecology")),
    ("바다", ("바다", "ocean", "sea")),
    ("물고기", ("물고기", "fish")),
    ("나무", ("나무", "trees", "tree")),
    ("꽃", ("꽃", "flowers", "flower")),
    ("우주", ("우주", "space")),
    ("별", ("별", "stars", "star")),
    ("달", ("달", "moon")),
    ("지구", ("지구", "earth")),
    ("날씨", ("날씨", "weather")),
    ("계절", ("계절", "seasons", "season")),
    ("물", ("물", "water")),
    ("빛", ("빛", "light")),
    ("소리", ("소리", "sound")),
    ("자석", ("자석", "magnet", "magnets")),
    ("힘", ("힘", "force", "forces")),
    ("에너지", ("에너지", "energy")),
    ("과학", ("과학", "science")),
    ("실험", ("실험", "experiment", "experiments")),
    ("관찰", ("관찰", "observation")),
    ("수학", ("수학", "math", "mathematics")),
    ("숫자", ("숫자", "numbers", "number")),
    ("분수", ("분수", "fractions", "fraction")),
    ("덧셈", ("덧셈", "addition")),
    ("뺄셈", ("뺄셈", "subtraction")),
    ("곱셈", ("곱셈", "multiplication")),
    ("나눗셈", ("나눗셈", "division")),
    ("도형", ("도형", "geometry", "shapes", "shape")),
    ("패턴", ("패턴", "patterns", "pattern")),
    ("측정", ("측정", "measurement")),
    ("통계", ("통계", "statistics")),
    ("읽기", ("읽기", "reading")),
    ("쓰기", ("쓰기", "writing")),
    ("독서", ("독서", "books", "book")),
    ("문학", ("문학", "literature")),
    ("영어", ("영어", "english")),
    ("언어", ("언어", "language")),
    ("역사", ("역사", "history")),
    ("한국사", ("한국사",)),
    ("세계사", ("세계사",)),
    ("사회", ("사회", "social studies")),
    ("지리", ("지리", "geography")),
    ("지도", ("지도", "maps", "map")),
    ("문화", ("문화", "culture")),
    ("경제", ("경제", "economics")),
    ("음악", ("음악", "music")),
    ("미술", ("미술", "art")),
    ("체육", ("체육", "physical education")),
    ("코딩", ("코딩", "coding", "programming")),
    ("로봇", ("로봇", "robot", "robotics")),
    ("자동차", ("자동차", "cars", "car")),
    ("기차", ("기차", "trains", "train")),
    ("탈것", ("탈것", "vehicles", "vehicle")),
    ("색깔", ("색깔", "colors", "colour", "color")),
    ("모양", ("모양",)),
    ("음식", ("음식", "food")),
    ("과일", ("과일", "fruit")),
    ("가족", ("가족", "family")),
    ("친구", ("친구", "friends", "friend")),
    ("감정", ("감정", "emotions", "emotion")),
    ("몸", ("몸", "body")),
    ("박물관", ("박물관", "museum", "museums")),
    ("도서관", ("도서관", "library", "libraries")),
)


def _alias_position(text: str, alias: str) -> int | None:
    folded_alias = alias.casefold()
    if folded_alias.isascii():
        match = re.search(rf"(?<![a-z0-9]){re.escape(folded_alias)}(?![a-z0-9])", text)
        return match.start() if match else None
    position = text.find(folded_alias)
    return position if position >= 0 else None


def generalize_public_terms(values: Iterable[str], *, limit: int = 12) -> list[str]:
    """Project arbitrary local text onto an allow-listed set of public education topics.

    The returned list is safe to send to external discovery adapters because every output token is
    a canonical constant from ``_PUBLIC_TOPIC_ALIASES``. Unknown names, notes, IDs, and free-form
    phrases are dropped rather than sanitized heuristically.
    """
    if limit <= 0:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value).casefold()
        matches: list[tuple[int, int, str]] = []
        for catalog_index, (canonical, aliases) in enumerate(_PUBLIC_TOPIC_ALIASES):
            positions = [
                position
                for alias in aliases
                if (position := _alias_position(text, alias)) is not None
            ]
            if positions:
                matches.append((min(positions), catalog_index, canonical))
        matches.sort()
        for _position, _catalog_index, canonical in matches:
            folded = canonical.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            result.append(canonical)
            if len(result) >= limit:
                return result
    return result
