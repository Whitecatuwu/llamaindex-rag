from urllib.parse import quote

from pathvalidate import sanitize_filename as lib_sanitize


def sanitize_filename(title: str) -> str:
    safe_name = lib_sanitize(title, replacement_text="_")
    if not safe_name:
        return "untitled"
    return safe_name


def build_canonical_url(title: str, wiki_root_url: str = "https://battlecats.miraheze.org/wiki") -> str:
    safe_url_title = quote((title or "").replace(" ", "_"))
    return f"{wiki_root_url.rstrip('/')}/{safe_url_title}"


def make_filename(title: str, pageid: int) -> str:
    return f"{sanitize_filename(title)}_{pageid}.json"
