import json
import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from urllib.parse import urljoin
from typing import List, Dict, Optional

# 設定
ENEMY_RELEASE_ORDER_URL = "https://battle-cats.fandom.com/wiki/Enemy_Release_Order"
BASE_URL = "https://battle-cats.fandom.com"
OUTPUT_DIR = "data/processed"
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "enemy_release_order.json")


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


def parse_enemy_table(html: str) -> List[Dict]:
    """解析 Enemies 列表表格"""
    soup = BeautifulSoup(html, "lxml")

    # 使用更寬容的選擇器，如果找不到 cro_table，嘗試找一般的 sortable 表格
    table = soup.select_one("table.cro_table") or soup.select_one("table.article-table")

    if not table:
        raise RuntimeError("❌ 找不到目標表格 (table.cro_table or table.article-table)")

    rows = table.select("tbody > tr")
    data = []

    # 略過表頭 (index 0)
    # 敵人表格前兩行是空值，需跳過
    for tr in rows[1 + 2 :]:
        tds = tr.find_all("td")

        # 解析邏輯
        enemy_id = int(tds[0].get_text(strip=True)) - 2
        enemy_elem = tds[1].find("a")

        if enemy_elem:
            enemy_name = enemy_elem.get_text(strip=True)
            enemy_href = enemy_elem.get("href") or None
            enemy_url = urljoin(BASE_URL, enemy_href) if enemy_href else None
        else:
            enemy_name = tds[1].get_text(strip=True)
            enemy_url = None

        # 這裡有時候會有多個 `<br>` 或 `<li>`，用 separator=" " 讓讀取更自然
        traits = tds[2].get_text(strip=True)
        traits_list = (
            [name.strip() for name in traits.split("/") if name.strip()]
            if traits.upper() != "N/A"
            else []
        )
        first_appearance = tds[3].get_text(" ", strip=True)

        data.append(
            {
                "id": enemy_id,
                "traits": traits_list,
                "enemy_name": enemy_name,
                "enemy_url": enemy_url,
                "first_appearance": first_appearance,
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
    print(f"🚀 Starting scrape: {ENEMY_RELEASE_ORDER_URL}")
    html = fetch_html(ENEMY_RELEASE_ORDER_URL)

    try:
        enemy_data = parse_enemy_table(html)
        print(f"✅ Parsed {len(enemy_data)} enemies.")

        if enemy_data:
            print(f"👀 Example: {enemy_data[0]}")
            save_json(enemy_data, OUTPUT_FILE)
        else:
            print("⚠️ No data found.")

    except RuntimeError as e:
        print(e)


if __name__ == "__main__":
    main()
