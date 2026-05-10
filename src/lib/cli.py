import argparse
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


@dataclass(frozen=True)
class ScriptArgs:
    scripts: list[Scripts]
    log_dir: Path


class Scripts(Enum):
    DISASTER_RECOVERY = "disaster-recovery"
    PUBLIC_ARCHIVE = "public-archive"
    DEV_ARCHIVE = "dev-archive"
    PROD_ARCHIVE = "prod-archive"
    EXEC_PROCESSOR = "run-processor"


_options = [
    "disaster-recovery",
    "public-archive",
    "dev-archive",
    "prod-archive",
    "run-processor",
]


def init() -> ScriptArgs:
    """Initializes CLI args

    Returns:
        ScriptArgs: Resolved configuration from CLI args
    """
    parser = argparse.ArgumentParser(
        prog="otr-scripts", description="Run one or more scripts"
    )

    parser.add_argument("script", choices=_options, nargs="*")
    parser.add_argument("--log-dir", type=str, required=False, default="./logs")

    args = parser.parse_args()

    if not args.script:
        parser.error("Missing required positional argument")

    # For each script provided as an argument, get the enum
    scripts: list[Scripts] = [Scripts(k) for k in args.script]
    log_dir = Path(args.log_dir)

    # Return the type-safe args
    return ScriptArgs(scripts, log_dir)
