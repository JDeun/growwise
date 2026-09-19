from __future__ import annotations

from dataclasses import dataclass

from growwise.domain import ChildProfile, MaterialKind
from growwise.generators import MaterialSourceEvidence

from .discovery import (
    DiscoveryCategory,
    DiscoverySuggestion,
    EducationDiscoveryService,
)


_KIND_CATEGORIES: dict[MaterialKind, frozenset[DiscoveryCategory]] = {
    MaterialKind.ACTIVITY_GUIDE: frozenset(
        {
            DiscoveryCategory.BOOK,
            DiscoveryCategory.CURRICULUM,
            DiscoveryCategory.PLACE,
            DiscoveryCategory.REFERENCE,
            DiscoveryCategory.SCIENCE,
            DiscoveryCategory.LANGUAGE,
            DiscoveryCategory.MEDIA,
        }
    ),
    MaterialKind.READING_ACTIVITY: frozenset(
        {
            DiscoveryCategory.BOOK,
            DiscoveryCategory.CURRICULUM,
            DiscoveryCategory.REFERENCE,
            DiscoveryCategory.LANGUAGE,
        }
    ),
    MaterialKind.ENGLISH_CARD: frozenset(
        {
            DiscoveryCategory.LANGUAGE,
            DiscoveryCategory.BOOK,
            DiscoveryCategory.CURRICULUM,
            DiscoveryCategory.REFERENCE,
        }
    ),
    MaterialKind.MATH_ACTIVITY: frozenset(
        {
            DiscoveryCategory.CURRICULUM,
            DiscoveryCategory.REFERENCE,
        }
    ),
    MaterialKind.SCIENCE_INQUIRY: frozenset(
        {
            DiscoveryCategory.SCIENCE,
            DiscoveryCategory.REFERENCE,
            DiscoveryCategory.MEDIA,
            DiscoveryCategory.CURRICULUM,
        }
    ),
    MaterialKind.WRITING_PROMPT: frozenset(
        {
            DiscoveryCategory.BOOK,
            DiscoveryCategory.LANGUAGE,
            DiscoveryCategory.REFERENCE,
            DiscoveryCategory.CURRICULUM,
        }
    ),
    MaterialKind.FIELD_TRIP: frozenset(
        {
            DiscoveryCategory.PLACE,
            DiscoveryCategory.REFERENCE,
            DiscoveryCategory.MEDIA,
            DiscoveryCategory.SCIENCE,
            DiscoveryCategory.CURRICULUM,
        }
    ),
}


_KIND_SOURCE_PRIORITY: dict[MaterialKind, tuple[str, ...]] = {
    MaterialKind.ACTIVITY_GUIDE: (
        "official_korean_curriculum",
        "data4library",
        "google_books",
        "wikidata",
        "wikipedia_ko",
        "nasa_images",
        "gbif_species",
        "korean_heritage",
        "krdict",
        "tatoeba",
    ),
    MaterialKind.READING_ACTIVITY: (
        "data4library",
        "national_library_isbn",
        "google_books",
        "open_library",
        "global_digital_library",
        "gutendex",
        "official_korean_curriculum",
        "krdict",
        "opendict",
    ),
    MaterialKind.ENGLISH_CARD: (
        "tatoeba",
        "google_books",
        "open_library",
        "official_korean_curriculum",
        "wikidata",
        "wikipedia_ko",
    ),
    MaterialKind.MATH_ACTIVITY: (
        "official_korean_curriculum",
        "public_curriculum",
        "wikidata",
        "wikipedia_ko",
    ),
    MaterialKind.SCIENCE_INQUIRY: (
        "official_korean_curriculum",
        "public_curriculum",
        "nasa_images",
        "wikidata",
        "wikipedia_ko",
        "wikimedia_commons",
        "gbif_species",
        "kbr",
    ),
    MaterialKind.WRITING_PROMPT: (
        "official_korean_curriculum",
        "data4library",
        "google_books",
        "open_library",
        "krdict",
        "opendict",
        "tatoeba",
        "wikidata",
    ),
    MaterialKind.FIELD_TRIP: (
        "korean_heritage",
        "openstreetmap_nominatim",
        "wikidata",
        "wikipedia_ko",
        "wikimedia_commons",
        "emuseum",
        "official_korean_curriculum",
        "nasa_images",
    ),
}


@dataclass(frozen=True, slots=True)
class MaterialGroundingResult:
    source_refs: tuple[str, ...]
    evidence: tuple[MaterialSourceEvidence, ...]
    queried_sources: tuple[str, ...]


class MaterialGroundingService:
    """Select diverse, public grounding evidence for one material request.

    Discovery owns all outbound API/privacy/cache/license behavior. This layer only chooses
    material-relevant suggestions and converts them into transient material evidence; it never
    persists external results into the parent's long-term Resource library.
    """

    def __init__(
        self,
        *,
        discovery: EducationDiscoveryService,
        max_sources: int = 8,
    ) -> None:
        if not 1 <= max_sources <= 12:
            raise ValueError("max_sources must be between 1 and 12")
        self.discovery = discovery
        self.max_sources = max_sources

    def ground(
        self,
        *,
        child: ChildProfile,
        kind: MaterialKind,
        topic: str,
        offline: bool = False,
    ) -> MaterialGroundingResult:
        response = self.discovery.discover(
            child=child,
            query=topic,
            limit=30,
            offline=offline,
        )
        eligible = [
            item
            for item in response.suggestions
            if item.category in _KIND_CATEGORIES[kind]
        ]
        selected = self._select_diverse(kind=kind, suggestions=eligible)

        evidence = tuple(self._evidence(item) for item in selected)
        return MaterialGroundingResult(
            source_refs=tuple(item.source_ref for item in evidence),
            evidence=evidence,
            queried_sources=tuple(
                state.source
                for state in response.sources
                if state.enabled and state.status not in {"disabled", "not_configured"}
            ),
        )

    def _select_diverse(
        self,
        *,
        kind: MaterialKind,
        suggestions: list[DiscoverySuggestion],
    ) -> list[DiscoverySuggestion]:
        if not suggestions:
            return []

        by_source: dict[str, list[DiscoverySuggestion]] = {}
        for suggestion in suggestions:
            by_source.setdefault(suggestion.source_name, []).append(suggestion)

        selected: list[DiscoverySuggestion] = []
        used_candidates: set[str] = set()

        # First pass: one result per preferred source. This prevents a single provider with many
        # hits from crowding out curriculum/reference/science diversity.
        for source in _KIND_SOURCE_PRIORITY[kind]:
            candidates = by_source.get(source, [])
            if not candidates:
                continue
            candidate = candidates[0]
            selected.append(candidate)
            used_candidates.add(candidate.candidate_id)
            if len(selected) >= self.max_sources:
                return selected

        # Second pass: include one result from any other relevant source.
        for suggestion in suggestions:
            if suggestion.candidate_id in used_candidates:
                continue
            if suggestion.source_name in {item.source_name for item in selected}:
                continue
            selected.append(suggestion)
            used_candidates.add(suggestion.candidate_id)
            if len(selected) >= self.max_sources:
                return selected

        # Final pass: fill any remaining slots by discovery rank.
        for suggestion in suggestions:
            if suggestion.candidate_id in used_candidates:
                continue
            selected.append(suggestion)
            used_candidates.add(suggestion.candidate_id)
            if len(selected) >= self.max_sources:
                break
        return selected

    @staticmethod
    def _evidence(suggestion: DiscoverySuggestion) -> MaterialSourceEvidence:
        metadata_text = " · ".join(
            f"{key}: {value}"
            for key, value in list(suggestion.metadata.items())[:8]
            if value
        )
        excerpt_parts = [
            value
            for value in (suggestion.summary, metadata_text or None)
            if value
        ]
        return MaterialSourceEvidence(
            source_ref=f"external:{suggestion.candidate_id}",
            title=suggestion.title,
            excerpt="\n".join(excerpt_parts)[:4_000],
            source_name=suggestion.source_name,
            source_url=suggestion.source_url,
            attribution=suggestion.attribution,
            license_note=suggestion.license_note,
        )
