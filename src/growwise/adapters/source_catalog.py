from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SourceIntegrationMode(StrEnum):
    LIVE_API = "live_api"
    KEYED_API = "keyed_api"
    CURATED_LINK = "curated_link"
    OFFLINE_DATASET = "offline_dataset"
    LOCAL_ENGINE = "local_engine"
    RENDERER = "renderer"


@dataclass(frozen=True, slots=True)
class EducationSourceSpec:
    source_id: str
    label: str
    domain: str
    mode: SourceIntegrationMode
    homepage: str
    license_note: str
    requires_setting: str | None = None


EDUCATION_SOURCE_CATALOG: tuple[EducationSourceSpec, ...] = (
    # Books / literacy
    EducationSourceSpec("data4library", "도서관 정보나루", "books", SourceIntegrationMode.KEYED_API, "https://data4library.kr", "Open API terms", "data4library_api_key"),
    EducationSourceSpec("national_library_isbn", "국립중앙도서관 ISBN 서지", "books", SourceIntegrationMode.KEYED_API, "https://www.nl.go.kr", "bibliographic metadata", "national_library_api_key"),
    EducationSourceSpec("google_books", "Google Books", "books", SourceIntegrationMode.LIVE_API, "https://books.google.com", "Google Books API terms"),
    EducationSourceSpec("open_library", "Open Library", "books", SourceIntegrationMode.OFFLINE_DATASET, "https://openlibrary.org", "use CC0 data dump rather than live API for commercial-safe ingestion"),
    EducationSourceSpec("gutendex", "Project Gutenberg / Gutendex", "books", SourceIntegrationMode.LIVE_API, "https://gutendex.com", "public-domain works; jurisdiction check"),
    EducationSourceSpec("storyweaver", "Pratham StoryWeaver", "books", SourceIntegrationMode.CURATED_LINK, "https://storyweaver.org.in", "CC BY 4.0 content; no stable public search API assumed"),
    EducationSourceSpec("global_digital_library", "Global Digital Library", "books", SourceIntegrationMode.LIVE_API, "https://digitallibrary.io", "item-level Creative Commons license"),
    EducationSourceSpec("standard_ebooks", "Standard Ebooks", "books", SourceIntegrationMode.CURATED_LINK, "https://standardebooks.org", "public-domain editions; searchable OPDS catalog may require membership"),
    # Language / vocabulary
    EducationSourceSpec("krdict", "한국어기초사전", "language", SourceIntegrationMode.KEYED_API, "https://krdict.korean.go.kr", "CC BY-SA 2.0 KR; media excluded", "krdict_api_key"),
    EducationSourceSpec("opendict", "우리말샘", "language", SourceIntegrationMode.KEYED_API, "https://opendict.korean.go.kr", "CC BY-SA 2.0 KR", "opendict_api_key"),
    EducationSourceSpec("wordnet", "Princeton WordNet", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://wordnet.princeton.edu", "WordNet license"),
    EducationSourceSpec("cmudict", "CMU Pronouncing Dictionary", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://github.com/cmusphinx/cmudict", "permissive"),
    EducationSourceSpec("wordfreq", "wordfreq", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://github.com/rspeer/wordfreq", "code Apache-2.0 / data CC BY-SA"),
    EducationSourceSpec("kiwi", "kiwipiepy / Kiwi", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://github.com/bab2min/kiwipiepy", "verify installed version license"),
    EducationSourceSpec("spacy", "spaCy", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://spacy.io", "MIT"),
    EducationSourceSpec("soynlp", "soynlp / KR-WordRank", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://github.com/lovit/soynlp", "LGPL-3.0"),
    EducationSourceSpec("languagetool", "LanguageTool", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://languagetool.org", "LGPL; self-hosted use"),
    EducationSourceSpec("hunspell_ko", "hunspell-dict-ko", "language", SourceIntegrationMode.LOCAL_ENGINE, "https://github.com/spellcheck-ko/hunspell-dict-ko", "verify dictionary license"),
    EducationSourceSpec("tatoeba", "Tatoeba", "language", SourceIntegrationMode.LIVE_API, "https://tatoeba.org", "CC BY"),
    # Field trip / geography / history
    EducationSourceSpec("openstreetmap_nominatim", "OpenStreetMap Nominatim", "places", SourceIntegrationMode.LIVE_API, "https://nominatim.openstreetmap.org", "ODbL 1.0"),
    EducationSourceSpec("openstreetmap_overpass", "OpenStreetMap Overpass", "places", SourceIntegrationMode.LIVE_API, "https://overpass-api.de", "ODbL 1.0"),
    EducationSourceSpec("opentopodata", "OpenTopoData", "places", SourceIntegrationMode.LIVE_API, "https://www.opentopodata.org", "dataset-specific license"),
    EducationSourceSpec("leaflet", "Leaflet", "places", SourceIntegrationMode.RENDERER, "https://leafletjs.com", "BSD-2-Clause"),
    EducationSourceSpec("threejs", "Three.js", "places", SourceIntegrationMode.RENDERER, "https://threejs.org", "MIT"),
    EducationSourceSpec("wikidata", "Wikidata", "reference", SourceIntegrationMode.LIVE_API, "https://www.wikidata.org", "CC0"),
    EducationSourceSpec("wikipedia_ko", "Wikipedia", "reference", SourceIntegrationMode.LIVE_API, "https://ko.wikipedia.org", "CC BY-SA"),
    EducationSourceSpec("wikimedia_commons", "Wikimedia Commons", "media", SourceIntegrationMode.LIVE_API, "https://commons.wikimedia.org", "item-level license filter required"),
    EducationSourceSpec("korean_heritage", "국가유산청 국가유산정보", "history", SourceIntegrationMode.LIVE_API, "https://www.khs.go.kr", "official public XML; attribution"),
    EducationSourceSpec("emuseum", "국립중앙박물관 e뮤지엄", "history", SourceIntegrationMode.KEYED_API, "https://www.emuseum.go.kr", "CC0/public-data item terms", "public_data_api_key"),
    # Science / nature
    EducationSourceSpec("nasa_images", "NASA Image and Video Library", "science", SourceIntegrationMode.LIVE_API, "https://images.nasa.gov", "NASA media usage guidelines"),
    EducationSourceSpec("phet", "PhET Simulations", "science", SourceIntegrationMode.CURATED_LINK, "https://phet.colorado.edu", "CC BY 4.0 simulations"),
    EducationSourceSpec("bioclip", "BioCLIP", "science", SourceIntegrationMode.LOCAL_ENGINE, "https://huggingface.co/imageomics/bioclip", "model MIT; dataset licenses separate"),
    EducationSourceSpec("gbif_species", "GBIF Species", "science", SourceIntegrationMode.LIVE_API, "https://www.gbif.org", "taxonomy metadata; media licenses separate"),
    EducationSourceSpec("kma_forecast", "기상청 단기예보", "science", SourceIntegrationMode.KEYED_API, "https://www.data.go.kr/data/15084084/openapi.do", "KOGL Type 1 attribution", "public_data_api_key"),
    EducationSourceSpec("kbr", "국립생물자원관 KBR", "science", SourceIntegrationMode.KEYED_API, "https://kbr.go.kr", "text metadata preferred; media reuse requires separate verification", "public_data_api_key"),
    # Math
    EducationSourceSpec("sympy", "SymPy", "math", SourceIntegrationMode.LOCAL_ENGINE, "https://www.sympy.org", "BSD"),
    EducationSourceSpec("manim", "Manim Community", "math", SourceIntegrationMode.LOCAL_ENGINE, "https://www.manim.community", "MIT"),
    EducationSourceSpec("jsxgraph", "JSXGraph", "math", SourceIntegrationMode.RENDERER, "https://jsxgraph.org", "MIT branch"),
    EducationSourceSpec("mathjs", "mathjs", "math", SourceIntegrationMode.RENDERER, "https://mathjs.org", "Apache-2.0"),
    EducationSourceSpec("illustrative_math_v1", "Illustrative Mathematics 1st edition", "math", SourceIntegrationMode.CURATED_LINK, "https://illustrativemathematics.org", "use only CC BY 4.0 first-edition content"),
    # Additional curriculum-source candidates from the original planning docs.
    EducationSourceSpec("khan_academy_kids", "Khan Academy Kids", "curriculum", SourceIntegrationMode.CURATED_LINK, "https://learn.khanacademy.org/khan-academy-kids", "provider terms; do not ingest NC/restricted material"),
    EducationSourceSpec("openstax", "OpenStax", "curriculum", SourceIntegrationMode.CURATED_LINK, "https://openstax.org", "item-level Creative Commons license"),
)


SOURCE_BY_ID = {source.source_id: source for source in EDUCATION_SOURCE_CATALOG}


def source_spec(source_id: str) -> EducationSourceSpec:
    try:
        return SOURCE_BY_ID[source_id]
    except KeyError as exc:
        raise KeyError(f"unknown education source: {source_id}") from exc
