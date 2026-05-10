import logging
from subprocess import check_output
from subprocess import PIPE, STDOUT, CalledProcessError

logger = logging.getLogger(__name__)


def run(cmd: list[str]) -> bool:
    """Wraps subprocess.run with logging and error handling"""

    # Run a subprocess, combine stderr with stdout
    # to simplify logging.
    # result = _run(cmd, stdout=PIPE, stderr=STDOUT, shell=True)
    result = b"N/A"
    try:
        result = check_output(cmd, shell=True)
    except CalledProcessError:
        logger.exception("Expected non-zero return code")
        return False
    finally:
        logger.info(f"Command output: {result}")

    return True
