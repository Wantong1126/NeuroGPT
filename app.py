# entrypoint (CLI demo runner)

from core.config_loader import load_config


def main() -> None:
    config = load_config()
    print(config)


if __name__ == "__main__":
    main()
