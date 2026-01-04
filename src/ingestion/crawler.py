import asyncio
import aiohttp
import sqlite3
from loguru import logger
from pathlib import Path
from typing import List, Dict, Set, Tuple
from urllib.parse import quote
from pathvalidate import sanitize_filename as lib_sanitize
from aiohttp import ClientConnectorError, ServerDisconnectedError, ClientPayloadError

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

# 配置
BASE_URL = "https://battle-cats.fandom.com/api.php"
DATA_DIR = Path("data/raw/wiki")
HTML_DIR = DATA_DIR / "html"
DB_PATH = DATA_DIR / "wiki_registry.db"

# 建立目錄
HTML_DIR.mkdir(parents=True, exist_ok=True)


class WikiCrawler:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH)
        self._init_db()
        # 限制並發數，避免對 Fandom 造成 DoS
        self.semaphore = asyncio.Semaphore(5)

    def _init_db(self):
        """初始化 SQLite 用於追蹤頁面狀態"""
        cursor = self.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pages (
                page_id INTEGER PRIMARY KEY,
                title TEXT UNIQUE,
                last_revid INTEGER,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                file_path TEXT
            )
        """
        )
        self.conn.commit()

    async def fetch_all_pages_metadata(self, session) -> Dict[str, int]:
        """
        第一步：快速獲取全站所有頁面的 (Title, Revision ID)
        這不會下載 HTML，只抓清單，速度很快。
        """
        logger.info("📡 Fetching global page list and revision IDs...")
        pages_metadata = {}

        params = {
            "action": "query",
            "format": "json",
            "list": "allpages",
            "aplimit": "500",  # 一次拿 500 筆
            "apnamespace": "0",  # 0 = Main Content (排除 Talk, User 等)
            "apfilterredir": "nonredirects",  # 排除重定向頁面
        }

        while True:
            async with session.get(BASE_URL, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Error fetching list: {resp.status}")
                    break

                data = await resp.json()

                # 這裡 API 只給了 title 和 pageid，為了拿到 revid，我們通常需要
                # 在這裡先收集 pageids，然後再發送一次 query 查 revid，
                # 或者改用 generator=allpages & prop=info|revisions (如下優化)
                pass
                # 備註：標準 allpages 不直接給 revid，為求精確與效率，
                # 我們改用下面的邏輯 (Generator approach)
                break

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
            async with session.get(BASE_URL, params=req_params) as resp:
                data = await resp.json()

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
                    print(f"\r✅ Discovered {total_fetched} pages...", end="")

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

    async def fetch_page_html(self, session, title: str, retries: int = 3) -> str:
        """
        下載單頁 HTML (含重試機制)
        :param retries: 最大重試次數
        """
        params = {
            "action": "parse",
            "page": title,
            "format": "json",
            "prop": "text",
            "disablepp": 1,
            "redirects": 1,
        }

        # 設定較寬鬆的超時 (連線 10秒，讀取 30秒)
        timeout = aiohttp.ClientTimeout(total=45, connect=10)

        for attempt in range(1, retries + 1):
            try:
                async with session.get(
                    BASE_URL, params=params, timeout=timeout
                ) as resp:
                    # 如果遇到 5xx 伺服器錯誤，也應該重試
                    if resp.status >= 500:
                        logger.warning(
                            f"⚠️ Server error {resp.status} for {title}. Attempt {attempt}/{retries}"
                        )
                        raise aiohttp.ClientResponseError(
                            resp.request_info,
                            resp.history,
                            status=resp.status,
                            message="Server Error",
                        )

                    # 404 或其他錯誤則直接回報，不重試
                    if resp.status != 200:
                        logger.error(
                            f"❌ HTTP {resp.status} for {title}: {await resp.text()}"
                        )
                        return None

                    data = await resp.json()
                    if "error" in data:
                        logger.error(f"❌ API Error for {title}: {data['error']}")
                        return None

                    return data["parse"]["text"]["*"]

            except (
                ClientConnectorError,
                ServerDisconnectedError,
                asyncio.TimeoutError,
                ClientPayloadError,
            ) as e:
                # 這是預期的網路錯誤
                wait_time = 2**attempt  # 指數退避: 2s, 4s, 8s...

                if attempt == retries:
                    logger.error(
                        f"💀 Failed to connect for '{title}' after {retries} attempts. Error: {e}"
                    )
                    return None

                logger.warning(
                    f"🔄 Connection unstable for '{title}' ({e}). Retrying in {wait_time}s..."
                )
                await asyncio.sleep(wait_time)

            except Exception as e:
                # 未預期的錯誤 (如 JSON 解析失敗)，記錄後跳過
                logger.error(f"❌ Unexpected error for '{title}': {e}")
                return None

    async def process_page(self, session, title: str, remote_revid: int):
        """Worker: 下載 -> 存檔 -> 更新 DB"""
        async with self.semaphore:  # 限制並發
            try:
                html = await self.fetch_page_html(session, title)
                if not html:
                    return

                # 存檔
                filename = self.sanitize_filename(title)
                file_path = HTML_DIR / filename
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html)

                # 更新 DB
                cursor = self.conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO pages (title, last_revid, file_path, last_updated)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(title) DO UPDATE SET
                        last_revid = excluded.last_revid,
                        file_path = excluded.file_path,
                        last_updated = CURRENT_TIMESTAMP
                """,
                    (title, remote_revid, str(file_path)),
                )
                self.conn.commit()

                logger.info(f"📥 Updated: {title} (Rev: {remote_revid})")

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
            tasks = []
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
                chunk = tasks[i : i + chunk_size]
                await asyncio.gather(*chunk)
                logger.info(f"Processing chunk {i}/{len(tasks)}...")
                await asyncio.sleep(1)  # 禮貌性暫停


if __name__ == "__main__":
    crawler = WikiCrawler()
    asyncio.run(crawler.run())
