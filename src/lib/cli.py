import argparse
from dataclasses import dataclass
from pathlib import Path
from argparse import ArgumentParser, Namespace
from lib.constants import buckets, scripts


@dataclass(frozen=True)
class ScriptArgs:
    scripts: list[str]
    log_dir: Path
    archive_bucket: str | None
    recovery_bucket: str | None
    recovery_src: Path | None
    upload_hash: bool


_script_options = [
    scripts.ARCHIVE,
    scripts.RECOVERY,
    scripts.PROCESSOR,
]
_buckets = [
    buckets.TEST,
    buckets.DEV,
    buckets.PUBLIC,
    buckets.PROD,
]


def init() -> ScriptArgs:
    """Initializes CLI args

    Returns:
        ScriptArgs: Resolved configuration from CLI args
    """
    parser = argparse.ArgumentParser(
        prog="otr-scripts", description="Run one or more scripts"
    )

    args = add_args(parser)
    validate_args(args, parser)

    # For each script provided as an argument, get the enum

    # Return the type-safe args
    return ScriptArgs(
        args.script,
        Path(args.log_dir),
        args.archive_bucket,
        args.recovery_bucket,
        Path(args.recovery_src) if args.recovery_src else None,
        args.upload_hash,
    )


def add_args(parser: ArgumentParser):
    parser.add_argument(
        "-s",
        "--script",
        type=str,
        required=True,
        choices=_script_options,
        nargs="*",
    )

    parser.add_argument("--log-dir", type=str, required=False, default="./logs")

    archive_args = parser.add_argument_group(
        "archive", f"Args specific to the {scripts.ARCHIVE} script"
    )
    archive_args.add_argument(
        "--archive-bucket",
        help="GCS bucket used for publishing archives",
        choices=_buckets,
    )
    archive_args.add_argument(
        "--upload-hash",
        action="store_true",
        help="Whether to upload a SHA256 hash with the archive",
    )

    recovery_args = parser.add_argument_group(
        "recovery", f"Args specific to the {scripts.RECOVERY} script"
    )
    recovery_src_args = recovery_args.add_mutually_exclusive_group()
    recovery_src_args.add_argument(
        "--recovery-bucket",
        help="GCS bucket used for disaster recovery",
        choices=_buckets,
    )
    recovery_src_args.add_argument(
        "--recovery-src",
        type=str,
        help="Path to a local database archive to use in recovery instead of a GCS bucket",
    )

    args = parser.parse_args()
    return args


def validate_args(args: Namespace, parser: ArgumentParser):
    validate_archive(args, parser)
    validate_disaster_recovery(args, parser)


def validate_archive(args: Namespace, parser: ArgumentParser):
    if scripts.ARCHIVE not in args.script:
        return

    if not args.archive_bucket:
        parser.error("An archive bucket must be supplied to perform an archive")


def validate_disaster_recovery(args: Namespace, parser: ArgumentParser):
    if scripts.RECOVERY not in args.script:
        return

    if not args.recovery_bucket:
        parser.error(
            "A recovery bucket must be supplied to perform a disaster recovery"
        )
