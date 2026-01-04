import requests

API_URL = "https://battle-cats.fandom.com/api.php"


def fetch_via_api(page_title):
    """
    透過 MediaWiki API 取得頁面的 HTML 內容
    """
    params = {
        "action": "parse",  # 指令：解析頁面
        "page": page_title,  # 頁面標題
        "format": "json",  # 回傳格式
        "prop": "text",  # 我們只要解析後的 HTML 文字
        "disablepp": 1,  # 關閉一些不必要的預處理
        "redirects": 1,  # 如果有重定向，自動跟隨
    }

    # 雖然是 API，還是建議帶上 User-Agent，這是良好的爬蟲禮儀
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Bot/1.0"}

    print(f"📡 Calling API for page: {page_title}...")
    resp = requests.get(API_URL, params=params, headers=headers, timeout=30)
    resp.raise_for_status()

    data = resp.json()

    # 檢查是否有錯誤
    if "error" in data:
        raise RuntimeError(f"API Error: {data['error']}")

    # 取出解析後的 HTML (在 ['parse']['text']['*'] 裡面)
    raw_html = data["parse"]["text"]["*"]
    return raw_html


if __name__ == "__main__":
    # 測試用例
    page = "Cat_(Normal_Cat)"
    html_content = fetch_via_api(page)
    # with open("sample_api_output.html", "w", encoding="utf-8") as f:
    # f.write(html_content)
    print(html_content[:500])  # 只印前 500 字元看看
