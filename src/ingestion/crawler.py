import asyncio
import aiohttp
import sqlite3
import json
from loguru import logger
from pathlib import Path
from typing import Any, Coroutine, Dict, Optional
from urllib.parse import quote
from pathvalidate import sanitize_filename as lib_sanitize
from datetime import datetime, timezone
from aiohttp import (
    ClientConnectorError,
    ClientResponseError,
    ServerDisconnectedError,
    ClientPayloadError,
    ContentTypeError,
)


# 配置
BASE_URL = "https://battlecats.miraheze.org/w/api.php"
DATA_DIR = Path("data/raw/wiki")
HTML_DIR = DATA_DIR / "html"
DB_PATH = DATA_DIR / "wiki_registry.db"

# 建立目錄
HTML_DIR.mkdir(parents=True, exist_ok=True)


class WikiCrawler:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()
        # 遵守 Miraheze API 友善規範
        self.semaphore = asyncio.Semaphore(5)

    def _init_db(self):
        """初始化 SQLite 用於追蹤頁面狀態"""
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pages (
                page_id INTEGER PRIMARY KEY,
                title TEXT UNIQUE,
                last_revid INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT,
                categories TEXT
            )
        """)
        self.conn.commit()

    async def fetch_categories(self, session) -> Optional[list]:
        """抓取頁面分類"""
        params = {
            "action": "query",
            "prop": "info|recisions",
            "cllimit": "max",
            "gapnamespace":"14",
            "generator":"allpages",
            "gaplimit": "50",
            "format": "json",
            "formatversion": "2"
            ""
        }
        continue_token = {}
        req_params = {**params, **continue_token}

        result = []
        while True:
            fetch_result = await self._fetch(session, req_params)
            if not fetch_result:
                logger.error("Failed to fetch categories list.")
                break

            data, _ = fetch_result
            pages: list = data.get("query", {}).get("pages", [])
            if not pages or "missing" in pages[0]:
                break
            for page in pages:
                result.append(page["title"])
            # ??????
            if "continue" in data:
                continue_token = data["continue"]
                req_params = {**params, **continue_token}
            else:
                break

        return result
    
    async def fetch_all_pages_metadata(self, session) -> Dict[str, int]:
        """
        第一步：快速獲取全站所有頁面的 (Title, Revision ID)
        這不會下載 HTML, 只抓清單, 速度很快。
        """
        logger.info("📡 Fetching global page list and revision IDs...")
        pages_metadata = {}

        # --- 優化版：使用 Generator 直接獲取 RevID ---
        gen_params = {
            "action": "query",
            "format": "json",
            "generator": "allpages",
            "gaplimit": "50",  # Generator 限制較嚴，一次 50
            "gapnamespace": "0",
            "gapfilterredir": "nonredirects",
            "prop": "info|revisions",  # 同時抓取 info 和 revision
            "rvprop": "ids",  # 只要 revid
        }

        continue_token = {}
        total_fetched = 0

        while True:
            req_params = {**gen_params, **continue_token}
            fetch_result = await self._fetch(session, req_params)
            if not fetch_result:
                logger.error("Failed to fetch pages metadata.")
                break

            data, _ = fetch_result

            if "query" in data and "pages" in data["query"]:
                batch = data["query"]["pages"]
                for pid, info in batch.items():
                    title = info["title"]
                    # 取得最新 revid
                    revid = 0
                    if "revisions" in info:
                        revid = info["revisions"][0]["revid"]
                    elif "lastrevid" in info:
                        revid = info["lastrevid"]

                    pages_metadata[title] = revid

                total_fetched += len(batch)
                print(f"\r??Discovered {total_fetched} pages...", end="")

            # 處理分頁
            if "continue" in data:
                continue_token = data["continue"]
            else:
                break
        print(f"\n✨ Discovery complete. Total pages: {len(pages_metadata)}")
        return pages_metadata

    def get_local_state(self) -> Dict[str, int]:
        """從 SQLite 讀取本地已有的頁面狀態"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT title, last_revid FROM pages")
        return {row[0]: row[1] for row in cursor.fetchall()}

    def sanitize_filename(self, title: str) -> str:
        """處理檔名中的非法字元"""
        safe_name = lib_sanitize(title, replacement_text="_")

        # 確保不會因為替換後變成空字串
        if not safe_name:
            safe_name = "untitled"

        return f"{safe_name}.html"

    async def fetch_page_data(self, session: aiohttp.ClientSession, title: str, retries: int = 3) -> Optional[Dict]:
        """
        ?????? HTML (????????
        :param retries: ??????????
        """
        params = {
            "action": "query",
            "titles": title,
            "prop": "categories|info|revisions",
            "rvprop": "content|ids|timestamp", # ?????? revid
            "rvslots": "*",
            "format": "json",
            "formatversion": "2" # ??? version 2 ?????? list ????????
        }

        fetch_result = await self._fetch(session, params, retries=retries)
        if not fetch_result:
            return None

        data, http_meta = fetch_result

        try:
            # ??? API ???
            if "error" in data:
                logger.error(f"??API Error for {title}: {data['error']}")
                return None
            
            # formatversion=2 ???pages ?????list
            pages = data.get("query", {}).get("pages", [])
            if not pages or "missing" in pages[0]:
                logger.warning(f"??? Page '{title}' not found.")
                return None
            
            page = pages[0]
            revisions = page.get("revisions", [])
            
            # ??? revisions (?????????????????
            if not revisions:
                logger.warning(f"??? No content found for '{title}'")
                return None
            
            revision = revisions[0]
            content = revision.get("slots", {}).get("main", {}).get("content", "")

            # ?????? Canonical URL (?????????)
            # Wiki ?????????????????? URL Encode
            safe_url_title = quote(page.get("title", "").replace(" ", "_"))
            canonical_url = f"https://battlecats.miraheze.org/wiki/{safe_url_title}"

            # ???????JSON
            result = {
                "source": "battlecats.miraheze.org",
                "pageid": page.get("pageid"),
                "title": page.get("title"),
                "canonical_url": canonical_url,  # ??????
                "revid": revision.get("revid"),
                "timestamp": revision.get("timestamp"),
                "content_model": "wikitext",
                "wikitext": content,
                "is_redirect": page.get("redirect", False),
                "redirect_target": None, 
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "http": http_meta,
            }
            return result
        except Exception as e:
            # ????????? (??JSON ??????)?????????
            logger.error(f"??Unexpected error for '{title}': {e}")
            return None

    async def process_page(self, session, title: str, remote_revid: int):
        """Worker: 下載 -> 存檔 -> 更新 DB"""
        async with self.semaphore:  # 限制並發
            try:
                page_data = await self.fetch_page_data(session, title)
                if not page_data:
                    return

                # 存檔邏輯 (確保副檔名是 .json)
                # 使用 rsplit 確保只替換最後一個副檔名，避免檔名中點號誤判
                safe_name = self.sanitize_filename(title)
                if "." in safe_name:
                    filename = safe_name.rsplit('.', 1)[0] + ".json"
                else:
                    filename = safe_name + ".json"
                
                file_path = HTML_DIR / filename
                
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(page_data, f, ensure_ascii=False, indent=2)

                # 更新 DB
                cursor = self.conn.cursor()
                cursor.execute("""
                    INSERT INTO pages (page_id, title, last_revid, file_path, last_updated)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(page_id) DO UPDATE SET
                        title = excluded.title, 
                        last_revid = excluded.last_revid,
                        file_path = excluded.file_path,
                        last_updated = CURRENT_TIMESTAMP
                """, (page_data["pageid"], title, remote_revid, str(file_path)))
                self.conn.commit()

                logger.info(f"💾 Saved JSON: {title}")

            except sqlite3.IntegrityError as e:
                # 捕捉極端情況：如果新標題跟「另一筆」舊資料的標題衝突 (Swap Case)
                logger.error(f"❌ Database Integrity Error for {title}: {e}")
                self.conn.rollback()

            except Exception as e:
                logger.error(f"Failed to process {title}: {e}")

    async def run(self):
        # limit=0 表示無總限制 (由 semaphore 控制)，limit_per_host=10 限制對 Fandom 的連線
        # ttl_dns_cache 可以減少 DNS 查詢次數
        connector = aiohttp.TCPConnector(limit=0, limit_per_host=10, ttl_dns_cache=300)
        async with aiohttp.ClientSession(connector=connector) as session:
            # 1. 獲取遠端所有頁面狀態
            remote_pages = await self.fetch_all_pages_metadata(session)

            # 2. 獲取本地狀態
            local_pages = self.get_local_state()

            # 3. 比較差異 (Diff)
            tasks: list[Coroutine[Any, Any, None]] = []
            for title, remote_revid in remote_pages.items():
                local_revid = local_pages.get(title)

                # 判定邏輯：如果本地沒有，或者遠端版本較新
                if local_revid is None or remote_revid > local_revid:
                    # 加入下載排程
                    tasks.append(self.process_page(session, title, remote_revid))

            if not tasks:
                logger.info("🎉 All pages are up to date!")
                return

            logger.info(f"🚀 Starting download for {len(tasks)} pages...")

            # 4. 執行下載 (使用 gather 並發)
            # 為了避免一次塞爆記憶體，可以分批處理 (Chunking)
            chunk_size = 50
            for i in range(0, len(tasks), chunk_size):
                chunk: list[Coroutine[Any, Any, None]] = tasks[i : i + chunk_size]
                await asyncio.gather(*chunk)
                logger.info(f"Processing chunk {i}/{len(tasks)}...")
                await asyncio.sleep(1)  # 禮貌性暫停

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        params: Dict[str, Any],
        retries: int = 3,
    ) -> Optional[tuple[Dict[str, Any], Dict[str, Any]]]:
        # 設定較寬鬆的超時 (連線 10秒，讀取 30秒)
        timeout = aiohttp.ClientTimeout(total=45, connect=10)

        for attempt in range(1, retries + 1):
            try:
                async with session.get(
                    BASE_URL, params=params, timeout=timeout
                ) as resp:
                    # 如果遇到 5xx / 429 伺服器錯誤，也應該重試
                    if resp.status >= 500 or resp.status == 429:
                        logger.warning(
                            f"⚠️ Server error {resp.status}. Attempt {attempt}/{retries}"
                        )
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message="Server Error",
                        )

                     # 404 或其他錯誤則直接回報，不重試
                    if resp.status != 200:
                        logger.error(f"??HTTP {resp.status}: {await resp.text()}")
                        return None

                    data = await resp.json()
                    http_meta = {
                        "status": resp.status,
                        "etag": resp.headers.get("ETag", ""),
                        "last_modified": resp.headers.get("Last-Modified", ""),
                    }
                    return data, http_meta

            except (
                ClientResponseError,
                ClientConnectorError,
                ServerDisconnectedError,
                asyncio.TimeoutError,
                ClientPayloadError,
                ContentTypeError,
                json.JSONDecodeError,
                ValueError,
            ) as e:
                # 這是預期的網路錯誤
                wait_time = 2**attempt  # 指數退避: 2s, 4s, 8s...

                if attempt == retries:
                    logger.error(
                        f"Failed to connect after {retries} attempts. Error: {e}"
                    )
                    return None

                logger.warning(
                    f"🔄 Connection unstable ({e}). Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                # 未預期的錯誤 (如 JSON 解析失敗)，記錄後跳過
                logger.error(f"Unexpected error while fetching: {e}")
                return None

if __name__ == "__main__":
    # 設定日誌
    log_dir = Path("logs")
    log_file = log_dir / "crawler_{time}.log"

    logger.remove()
    logger.add(
        log_file,
        rotation="256 MB",  # 每個檔案滿 256MB 就切分
        retention="10 days",  # 只保留最近 10 天的日誌 (自動刪除舊的)
        compression="zip",  # 切分後的舊檔案自動壓縮成 zip (節省空間)
        encoding="utf-8",  # 防止中文亂碼
        level="INFO",  # 檔案中只存 INFO 以上 (過濾掉 DEBUG/TRACE)
        enqueue=True,
    )
    crawler = WikiCrawler()
    async def abc():
        connector = aiohttp.TCPConnector(limit=0, limit_per_host=10, ttl_dns_cache=300)
        session = aiohttp.ClientSession(connector=connector)
        result = await crawler.fetch_categories(session)
        print(result)


    asyncio.run(crawler.run())
