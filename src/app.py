from query.engine import build_query_engine


def main():
    qe = build_query_engine()

    while True:
        q = input("❓ 問題：")
        if q in ("exit", "quit"):
            break
        res = qe.query(q)
        print("\n🧠 回答：\n", res, "\n")


if __name__ == "__main__":
    main()
