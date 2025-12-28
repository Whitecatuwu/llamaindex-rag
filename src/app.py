from src.query.engine import build_query_engine
import src.config.settings  # noqa: F401


def main():
    qe = build_query_engine()

    while True:
        q = input("❓ 問題：")
        if q in ("exit", "quit"):
            break
        print("模型正在思考...")
        res = qe.query(q)
        print("\n🧠 回答：\n", res, "\n")


if __name__ == "__main__":
    main()
