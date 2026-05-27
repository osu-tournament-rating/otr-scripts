import subprocess
import logging
from lib.config import config

logger = logging.getLogger(__name__)


def run():
    tag = config.tag
    image = f"stagecodes/otr-processor:{tag}"

    pull_cmd = f"docker pull {image}".split()

    logger.info(f"Pulling {pull_cmd}")
    pull = subprocess.run(pull_cmd, capture_output=True)

    for line in pull.stdout.splitlines():
        logger.info(line.decode())

    conn_str = f"postgresql://{config.db_user}:{config.db_password}@{config.db_container}:{config.db_port}/{config.db_name}"
    rust_log = "info"
    rabbit = config.rabbitmq_url

    run_cmd = f"docker run -e CONNECTION_STRING={conn_str} -e RUST_LOG={rust_log} -e RABBITMQ_URL={rabbit} {image}".split()

    logger.info("Running processor")
    exc = subprocess.run(run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    for line in exc.stdout.splitlines():
        logger.info(line.decode())
