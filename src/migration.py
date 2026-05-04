from db import init_db


def main() -> None:
    init_db()
    print("Schema migrations applied.")


if __name__ == "__main__":
    main()
