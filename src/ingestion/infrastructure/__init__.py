"""Infrastructure adapters for ingestion."""

from src.ingestion.infrastructure.fs_sink import JsonFileSink
from src.ingestion.infrastructure.mw_client import MediaWikiClient
from src.ingestion.infrastructure.raw_sink import RawApiJsonlSink
from src.ingestion.infrastructure.registry_sqlite import SQLiteRegistryRepository

__all__ = ["JsonFileSink", "MediaWikiClient", "RawApiJsonlSink", "SQLiteRegistryRepository"]
