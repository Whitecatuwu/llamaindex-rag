import asyncio
import json
from datetime import datetime, timezone
from typing import Any

import aiohttp
from aiohttp import (
    ClientConnectorError,
    ClientPayloadError,
    ClientResponseError,
    ContentTypeError,
    ServerDisconnectedError,
)
from loguru import logger

from src.ingestion.domain.models import WikiPageDoc
from src.ingestion.domain.rules import build_canonical_url
from src.ingestion.infrastructure.raw_sink import RawApiJsonlSink


class MediaWikiClient:
    def __init__(
        self,
        base_url: str = "https://battlecats.miraheze.org/w/api.php",
        raw_sink: RawApiJsonlSink | None = None,
        run_id: str | None = None,
    ) -> None:
        self.base_url = base_url
        self.raw_sink = raw_sink
        self.run_id = run_id

    async def fetch_categories(self, session: aiohttp.ClientSession) -> list[str]:
        params: dict[str, Any] = {
            "action": "query",
            "list": "allcategories",
            "aclimit": "500",
            "format": "json",
            "formatversion": "2",
        }
        continue_token: dict[str, Any] = {}
        seen: set[str] = set()
        result: list[str] = []

        while True:
            req_params = {**params, **continue_token}
            fetch_result = await self._fetch(
                session,
                req_params,
                operation="fetch_categories",
            )
            if not fetch_result:
                logger.error("Failed to fetch categories list.")
                return []

            data, _ = fetch_result
            categories = data.get("query", {}).get("allcategories", [])
            for category in categories:
                name = str(
                    category.get("*")
                    or category.get("category")
                    or category.get("title")
                    or ""
                ).strip()
                if not name:
                    continue
                if name not in seen:
                    seen.add(name)
                    result.append(name)

            if "continue" not in data:
                break
            continue_token = data["continue"]

        return result

    async def fetch_all_pages_metadata(self, session: aiohttp.ClientSession) -> dict[int, int]:
        logger.info("Fetching global page list and revision IDs...")
        pages_metadata: dict[int, int] = {}
        gen_params: dict[str, Any] = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "generator": "allpages",
            "gaplimit": "500",
            "gapnamespace": "0",
            "gapfilterredir": "nonredirects",
            "prop": "info|revisions",
            "rvprop": "ids",
        }
        continue_token: dict[str, Any] = {}
        total_fetched = 0

        while True:
            req_params = {**gen_params, **continue_token}
            fetch_result = await self._fetch(
                session,
                req_params,
                operation="fetch_all_pages_metadata",
            )
            if not fetch_result:
                logger.error("Failed to fetch pages metadata.")
                break

            data, _ = fetch_result
            pages = data.get("query", {}).get("pages", [])
            for page in pages:
                pageid = page.get("pageid")
                if pageid is None:
                    continue
                revid: int | None = None
                revisions = page.get("revisions", [])
                if revisions:
                    revid = revisions[0].get("revid")
                if revid is None:
                    revid = page.get("lastrevid")
                if revid is None:
                    continue
                pages_metadata[int(pageid)] = int(revid)

            total_fetched += len(pages)
            logger.info("Discovered {} pages so far", total_fetched)

            if "continue" not in data:
                break
            continue_token = data["continue"]

        logger.info("Discovery complete. Total pages: {}", len(pages_metadata))
        return pages_metadata

    async def fetch_page_doc(
        self, session: aiohttp.ClientSession, page_id: int, retries: int = 3
    ) -> WikiPageDoc | None:
        params = {
            "action": "query",
            "pageids": page_id,
            "explaintext": "1",
            "prop": "categories|info|revisions|extracts",
            "rvprop": "content|ids|timestamp",
            "redirects": "1",
            "rvslots": "*",
            "format": "json",
            "formatversion": "2",
        }
        fetch_result = await self._fetch(
            session,
            params,
            retries=retries,
            operation="fetch_page_doc",
            pageid=page_id,
        )
        if not fetch_result:
            return None

        data, http_meta = fetch_result
        try:
            if "error" in data:
                logger.error("API error for pageid {}: {}", page_id, data["error"])
                return None

            pages = data.get("query", {}).get("pages", [])
            if not pages:
                logger.warning("Pageid '{}' not found.", page_id)
                return None

            page = pages[0]
            if page.get("missing"):
                logger.warning("Pageid '{}' not found.", page_id)
                return None

            revisions = page.get("revisions", [])
            if not revisions:
                logger.warning("No content found for pageid '{}'", page_id)
                return None

            revision = revisions[0]
            revid = revision.get("revid")
            timestamp = revision.get("timestamp")
            current_pageid = page.get("pageid")
            title = str(page.get("title") or "")

            if current_pageid is None or revid is None or not timestamp or not title:
                logger.warning("Incomplete page payload for pageid '{}'", page_id)
                return None

            categories = tuple(
                str(x.get("title")).strip()
                for x in page.get("categories", [])
                if str(x.get("title", "")).strip()
            )

            return WikiPageDoc(
                source="battlecats.miraheze.org",
                pageid=int(current_pageid),
                title=title,
                canonical_url=build_canonical_url(title),
                revid=int(revid),
                timestamp=timestamp,
                content_model=page.get("contentmodel"),
                categories=categories,
                content=str(page.get("extract", "")),
                is_redirect=bool(page.get("redirect", False)),
                redirect_target=None,
                fetched_at=datetime.now(timezone.utc).isoformat(),
                http=http_meta,
            )
        except Exception as exc:
            logger.error("Unexpected error for pageid {}: {}", page_id, exc)
            return None

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        params: dict[str, Any],
        retries: int = 3,
        *,
        operation: str,
        pageid: int | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        timeout = aiohttp.ClientTimeout(total=45, connect=10)
        for attempt in range(1, retries + 1):
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                async with session.get(self.base_url, params=params, timeout=timeout) as resp:
                    if resp.status >= 500 or resp.status == 429:
                        logger.warning(
                            "Server error {}. Attempt {}/{}",
                            resp.status,
                            attempt,
                            retries,
                        )
                        raise ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message="Server Error",
                        )

                    if resp.status != 200:
                        body = await resp.text()
                        await self._write_raw_event(
                            {
                                "run_id": self.run_id,
                                "operation": operation,
                                "pageid": pageid,
                                "attempt": attempt,
                                "request": {"base_url": self.base_url, "params": params},
                                "http": self._build_http_meta(resp),
                                "response_json": None,
                                "response_text": body,
                                "warnings": None,
                                "continue_token": None,
                                "error": {"type": "HTTPError", "message": f"HTTP {resp.status}"},
                                "timing": {
                                    "started_at": started_at,
                                    "finished_at": datetime.now(timezone.utc).isoformat(),
                                },
                                "outcome": "http_error",
                            }
                        )
                        logger.error("HTTP {}: {}", resp.status, body)
                        return None

                    try:
                        data = await resp.json()
                    except (ContentTypeError, json.JSONDecodeError, ValueError) as exc:
                        body = await resp.text()
                        await self._write_raw_event(
                            {
                                "run_id": self.run_id,
                                "operation": operation,
                                "pageid": pageid,
                                "attempt": attempt,
                                "request": {"base_url": self.base_url, "params": params},
                                "http": self._build_http_meta(resp),
                                "response_json": None,
                                "response_text": body,
                                "warnings": None,
                                "continue_token": None,
                                "error": {"type": type(exc).__name__, "message": str(exc)},
                                "timing": {
                                    "started_at": started_at,
                                    "finished_at": datetime.now(timezone.utc).isoformat(),
                                },
                                "outcome": "retryable_error",
                            }
                        )
                        wait_time = 2**attempt
                        if attempt == retries:
                            logger.error("Failed after {} attempts. Error: {}", retries, exc)
                            return None
                        logger.warning("Connection unstable ({}). Retrying in {}s...", exc, wait_time)
                        await asyncio.sleep(wait_time)
                        continue

                    http_meta = {
                        "status": resp.status,
                        "etag": resp.headers.get("ETag", ""),
                        "last_modified": resp.headers.get("Last-Modified", ""),
                    }
                    await self._write_raw_event(
                        {
                            "run_id": self.run_id,
                            "operation": operation,
                            "pageid": pageid,
                            "attempt": attempt,
                            "request": {"base_url": self.base_url, "params": params},
                            "http": self._build_http_meta(resp),
                            "response_json": data,
                            "response_text": None,
                            "warnings": data.get("warnings"),
                            "continue_token": data.get("continue"),
                            "error": None,
                            "timing": {
                                "started_at": started_at,
                                "finished_at": datetime.now(timezone.utc).isoformat(),
                            },
                            "outcome": "success",
                        }
                    )
                    return data, http_meta

            except (
                ClientResponseError,
                ClientConnectorError,
                ServerDisconnectedError,
                asyncio.TimeoutError,
                ClientPayloadError,
            ) as exc:
                await self._write_raw_event(
                    {
                        "run_id": self.run_id,
                        "operation": operation,
                        "pageid": pageid,
                        "attempt": attempt,
                        "request": {"base_url": self.base_url, "params": params},
                        "http": {"status": getattr(exc, "status", None)},
                        "response_json": None,
                        "response_text": None,
                        "warnings": None,
                        "continue_token": None,
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                        "timing": {
                            "started_at": started_at,
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        },
                        "outcome": "retryable_error",
                    }
                )
                wait_time = 2**attempt
                if attempt == retries:
                    logger.error("Failed after {} attempts. Error: {}", retries, exc)
                    return None
                logger.warning("Connection unstable ({}). Retrying in {}s...", exc, wait_time)
                await asyncio.sleep(wait_time)
            except Exception as exc:
                await self._write_raw_event(
                    {
                        "run_id": self.run_id,
                        "operation": operation,
                        "pageid": pageid,
                        "attempt": attempt,
                        "request": {"base_url": self.base_url, "params": params},
                        "http": None,
                        "response_json": None,
                        "response_text": None,
                        "warnings": None,
                        "continue_token": None,
                        "error": {"type": type(exc).__name__, "message": str(exc)},
                        "timing": {
                            "started_at": started_at,
                            "finished_at": datetime.now(timezone.utc).isoformat(),
                        },
                        "outcome": "fatal_error",
                    }
                )
                logger.error("Unexpected error while fetching: {}", exc)
                return None

        return None

    @staticmethod
    def _build_http_meta(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        return {
            "status": resp.status,
            "etag": resp.headers.get("ETag", ""),
            "last_modified": resp.headers.get("Last-Modified", ""),
            "headers": dict(resp.headers),
        }

    async def _write_raw_event(self, event: dict[str, Any]) -> None:
        if self.raw_sink is None:
            return
        try:
            await self.raw_sink.write_event(event)
        except Exception as exc:
            logger.warning("Failed to persist raw API event: {}", exc)
