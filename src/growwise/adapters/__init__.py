from .base import AdapterResult, ExternalAdapterError, ExternalUnavailable
from .cache import CachedPayload, SQLiteExternalCache
from .curated_catalog import CuratedEducationCatalogAdapter
from .curriculum import CurriculumRecord, PublicCurriculumAdapter
from .curriculum_resources import (
    curriculum_records_to_resources,
    curriculum_refs,
    curriculum_resource_ref,
)
from .data4library import Data4LibraryAdapter
from .gbif import GbifSpeciesAdapter
from .google_books import GoogleBooksAdapter
from .heritage_palace import HeritagePalaceAdapter
from .http import JsonHttpClient
from .kma_weather import KmaWeatherAdapter, kma_grid_for, kma_observation_base
from .krdict import KrDictAdapter
from .license_filter import filter_licensed, is_commercial_safe, normalize_license
from .museum import MuseumArtGalleryAdapter
from .nasa_images import NasaImagesAdapter
from .national_library import NationalLibraryIsbnAdapter
from .official_curriculum_catalog import OfficialKoreanCurriculumCatalogAdapter
from .openlibrary import OpenLibraryAdapter
from .overpass import OverpassAdapter
from .wikidata import WikidataAdapter
from .wikimedia_commons import WikimediaCommonsAdapter
from .wikipedia import WikipediaAdapter

__all__ = [
    "AdapterResult",
    "CachedPayload",
    "CurriculumRecord",
    "Data4LibraryAdapter",
    "ExternalAdapterError",
    "ExternalUnavailable",
    "GbifSpeciesAdapter",
    "GoogleBooksAdapter",
    "JsonHttpClient",
    "NasaImagesAdapter",
    "OfficialKoreanCurriculumCatalogAdapter",
    "OpenLibraryAdapter",
    "OverpassAdapter",
    "PublicCurriculumAdapter",
    "SQLiteExternalCache",
    "WikidataAdapter",
    "WikimediaCommonsAdapter",
    "WikipediaAdapter",
    "CuratedEducationCatalogAdapter",
    "HeritagePalaceAdapter",
    "KmaWeatherAdapter",
    "KrDictAdapter",
    "MuseumArtGalleryAdapter",
    "NationalLibraryIsbnAdapter",
    "kma_grid_for",
    "kma_observation_base",
    "curriculum_records_to_resources",
    "curriculum_refs",
    "curriculum_resource_ref",
    "filter_licensed",
    "is_commercial_safe",
    "normalize_license",
]
