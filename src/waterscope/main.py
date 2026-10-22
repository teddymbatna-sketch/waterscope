import logging
from pathlib import Path

from waterscope import __version__

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_DIR / "waterscope.log", encoding="utf-8"),
        ],
    )


def bienvenue() -> str:
    return f"WaterScope v{__version__}"


def main():
    setup_logging()
    logging.info(bienvenue())


if __name__ == "__main__":
    main()
