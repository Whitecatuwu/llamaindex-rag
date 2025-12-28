import json
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from typing import List, Dict, Optional

# 設定常數
CAT_RELEASE_ORDER_URL = "https://battle-cats.fandom.com/wiki/Cat_Release_Order"
BASE_URL = "https://battle-cats.fandom.com"
OUTPUT_DIR = "data/processed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "cat_release_order.json")


def fetch_html(url: str) -> str:
    """抓取 HTML 並處理基本的網路錯誤"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": BASE_URL,  # 增加 Referer 增加擬真度
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        raise


def parse_cat_table(html: str) -> List[Dict]:
    """解析 Battle Cats 列表表格"""
    soup = BeautifulSoup(html, "lxml")

    # 使用更寬容的選擇器，如果找不到 cro_table，嘗試找一般的 sortable 表格
    table = soup.select_one("table.cro_table") or soup.select_one("table.article-table")

    if not table:
        raise RuntimeError("❌ 找不到目標表格 (table.cro_table or table.article-table)")

    rows = table.select("tbody > tr")
    data = []

    # 略過表頭 (index 0)
    for tr in rows[1:]:
        tds = tr.find_all("td")

        # 解析邏輯
        cat_id = tds[0].get_text(strip=True) or None
        cat_id = int(cat_id) if cat_id else None
        rarity = tds[1].get_text(strip=True)

        cat_elem = tds[2].find("a")
        if cat_elem:
            cat_name = cat_elem.get_text(strip=True)
            cat_href = cat_elem.get("href") or None
            cat_url = urljoin(BASE_URL, cat_href) if cat_href else None
        else:
            cat_name = tds[2].get_text(strip=True)
            cat_url = None

        # 這裡有時候會有多個 `<br>` 或 `<li>`，用 separator=" " 讓讀取更自然
        evolved = tds[3].get_text(strip=True)
        evolved_list = (
            [name.strip() for name in evolved.split("/") if name.strip()]
            if evolved.upper() != "N/A"
            else []
        )
        obtaining = tds[4].get_text(" ", strip=True)

        data.append(
            {
                "id": cat_id,
                "rarity": rarity,
                "cat_name": cat_name,
                "cat_url": cat_url,
                "evolved_true_ultra": evolved_list,
                "obtaining_method": obtaining,
            }
        )

    return data


def save_json(data: List[Dict], filepath: str):
    """儲存 JSON，並自動建立路徑"""
    # 自動建立父目錄
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ Data saved to: {filepath}")


def main():
    print(f"🚀 Starting scrape: {CAT_RELEASE_ORDER_URL}")
    html = fetch_html(CAT_RELEASE_ORDER_URL)

    try:
        cat_data = parse_cat_table(html)
        print(f"✅ Parsed {len(cat_data)} cats.")

        if cat_data:
            print(f"👀 Example: {cat_data[0]}")
            save_json(cat_data, OUTPUT_FILE)
        else:
            print("⚠️ No data found.")

    except RuntimeError as e:
        print(e)


if __name__ == "__main__":
    main()
