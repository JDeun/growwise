from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .book_sources import (
    GlobalDigitalLibraryAdapter,
    GoogleBooksAdapter,
    GutendexAdapter,
    NationalLibraryIsbnAdapter,
    OpenLibraryAdapter,
)
from .cache import CachedPayload, SQLiteExternalCache
from .curriculum import CurriculumRecord, PublicCurriculumAdapter
from .curriculum_resources import (
    curriculum_records_to_resources,
    curriculum_refs,
    curriculum_resource_ref,
)
from .data4library import Data4LibraryAdapter
from .http import JsonHttpClient
from .knowledge_sources import (
    GbifSpeciesAdapter,
    NasaMediaAdapter,
    NominatimAdapter,
    OpenTopoDataAdapter,
    TatoebaAdapter,
    WikidataAdapter,
    WikimediaCommonsAdapter,
    WikipediaAdapter,
)
from .korean_sources import (
    ConfiguredPublicDataAdapter,
    KbrAdapter,
    KmaForecastAdapter,
    KoreanHeritageAdapter,
    KrdictAdapter,
    OpenDictAdapter,
)
from .license_filter import filter_licensed, is_commercial_safe, normalize_license
from .official_curriculum_catalog import OfficialKoreanCurriculumCatalogAdapter
from .overpass import OverpassAdapter
from .search_base import CachedSearchAdapter
from .source_catalog import (
    EDUCATION_SOURCE_CATALOG,
    SOURCE_BY_ID,
    EducationSourceSpec,
    SourceIntegrationMode,
    source_spec,
)

__all__ = [
    "AdapterResult",
    "CachedPayload",
    "CachedSearchAdapter",
    "ConfiguredPublicDataAdapter",
    "CurriculumRecord",
    "Data4LibraryAdapter",
    "EDUCATION_SOURCE_CATALOG",
    "EducationSourceSpec",
    "ExternalAdapterError",
    "ExternalUnavailable",
    "GbifSpeciesAdapter",
    "GlobalDigitalLibraryAdapter",
    "GoogleBooksAdapter",
    "GutendexAdapter",
    "JsonHttpClient",
    "OpenLibraryAdapter",
    "KbrAdapter",
    "KmaForecastAdapter",
    "KoreanHeritageAdapter",
    "KrdictAdapter",
    "NasaMediaAdapter",
    "NationalLibraryIsbnAdapter",
    "NominatimAdapter",
    "OfficialKoreanCurriculumCatalogAdapter",
    "OpenDictAdapter",
    "OpenTopoDataAdapter",
    "OverpassAdapter",
    "PublicCurriculumAdapter",
    "SOURCE_BY_ID",
    "SQLiteExternalCache",
    "SourceIntegrationMode",
    "TatoebaAdapter",
    "WikidataAdapter",
    "WikimediaCommonsAdapter",
    "WikipediaAdapter",
    "curriculum_records_to_resources",
    "curriculum_refs",
    "curriculum_resource_ref",
    "filter_licensed",
    "is_commercial_safe",
    "normalize_license",
    "source_spec",
]
