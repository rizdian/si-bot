import logging
import sys


def setup_logger():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)  # penting untuk Docker
        ],
    )

    # DEBUG level khusus untuk bot & music, biar bisa trace yt-dlp detail
    logging.getLogger("bot").setLevel(logging.DEBUG)