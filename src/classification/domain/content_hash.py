import hashlib


def compute_content_hash(content: str) -> str:
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()

