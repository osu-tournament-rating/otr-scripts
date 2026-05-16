from functools import partial
import logging
from typing import Callable

from lib import cli, logs, processor, public_html
from lib.scripts import db
from lib.constants import scripts

args = cli.init()

logs.init(args.log_dir)
logger = logging.getLogger(__name__)


def main():
    logger.info(f"Resolved args: {args}")

    script_map: dict[str, Callable] = {
        scripts.ARCHIVE: partial(db.archive, args),
        scripts.PROCESSOR: processor.run,
        scripts.RECOVERY: partial(db.recovery, args),
        scripts.REFRESH_INDEX: public_html.generate_index,
    }

    for script in args.scripts:
        script_map[script]()


if __name__ == "__main__":
    main()
