from src.query.engine import build_query_engine
import src.config.settings  # noqa: F401
from src.config.logger_config import logger  # noqa: F401


def main():
    qe = build_query_engine()

    while True:
        q = input("❓ 問題：")
        if q in ("exit", "quit"):
            break
        print("模型正在思考...")

        try:
            res = qe.query(q)
            print("\n🧠 回答：\n", res, "\n")
        except Exception as e:
            if "'NoneType' object is not subscriptable" in str(e):
                logger.error(
                    "錯誤：LLM 回傳了空值。這可能是因為觸發了安全過濾機制，或是模型後端發生錯誤。"
                )
            else:
                logger.exception(str(e))


if __name__ == "__main__":
    main()
