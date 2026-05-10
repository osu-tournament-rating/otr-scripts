import logging
from pathlib import Path

from lib import cli, logs
from lib.scripts import db
from lib.cli import Scripts

args = cli.init()

logs.init(args.log_dir)
logger = logging.getLogger(__name__)


def main():
    logger.info(f"Resolved args: {args}")

    db._upload(
        Path("/Users/stage/otr-db-dumps/otr-dev-replica_2026-05_09_19_07_35.gz"),
        replica="dev",
    )
    # script_fns = {
    #     Scripts.DEV_ARCHIVE: db.dev_archive,
    #     Scripts.PUBLIC_ARCHIVE: db.public_archive,
    #     Scripts.PROD_ARCHIVE: db.prod_archive,
    # }

    # for s in args.scripts:
    #     s_name = s.name

    #     if s not in script_fns:
    #         logger.error(f"Unsupported script: {s_name}")
    #         continue

    #     logger.info(f"Executing {s_name}")

    #     script_fns[s]()

    #     logger.info(f"Completed {s_name}")


if __name__ == "__main__":
    main()
