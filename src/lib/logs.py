from datetime import datetime
import logging
from pathlib import Path

time_snapshot = datetime.now()
file_timestamp = time_snapshot.strftime(format="%Y%m%d_%H%M%S")


def init(log_dir: Path):
    log_file = f"otr-scripts_{file_timestamp}.log"
    log_dir.mkdir(exist_ok=True)

    log_path = log_dir / log_file

    logging.basicConfig(
        level=logging.INFO,
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
        format="%(asctime)s [%(levelname)s]: %(message)s",
    )
