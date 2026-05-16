import logging
from pathlib import Path
from subprocess import run

logger = logging.getLogger(__name__)


def hash(p: Path) -> Path:
    """
    Hashes a file and saves the hash as a .sha256 file.
    Returns a path to the hash
    """
    logger.info(f"Hashing {p}")
    run(f"sha256 {p.name} > {p.name}.sha256", cwd=p.parent, shell=True)

    output_loc = p.parent / f"{p.name}.sha256"
    logger.info(f"Hash saved to {output_loc}")

    return output_loc
