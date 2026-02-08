from loguru import logger
from pathlib import Path

log_dir = Path("logs")
log_file = log_dir / "{time}.log"

logger.remove()
logger.add(
    log_file,
    rotation="256 MB",  # 每個檔案滿 256MB 就切分
    retention="10 days",  # 只保留最近 10 天的日誌 (自動刪除舊的)
    compression="zip",  # 切分後的舊檔案自動壓縮成 zip (節省空間)
    encoding="utf-8",  # 防止中文亂碼
    level="DEBUG",  # 檔案中只存 INFO 以上 (過濾掉 DEBUG/TRACE)
)

if __name__ == "__main__":
    logger.info("這是一條資訊")
    logger.error("這是一條錯誤")
    logger.debug("這是一條除錯訊息")
    logger.warning("這是一條警告訊息")
    logger.success("這是一條成功訊息")
    logger.trace("這是一條追蹤訊息")
    logger.critical("這是一條嚴重錯誤訊息")
    logger.exception("這是一條例外訊息")
