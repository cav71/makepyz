import argparse
import contextlib
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

DRYRUN = False


def logme(method, message, *args, **kwargs):
    tag = "(dry-run) " if DRYRUN else ""
    getattr(log, method)(tag + message, *args, **kwargs)


def process_pyproject(
    pyproject: Path, gdata: dict[str, Any], release: bool
) -> tuple[Path, str, str]:
    from . import misc

    lineno, current, quote = misc.get_variable_def(pyproject, "version")
    logme("debug", "found at LN:%i: version = '%s'", lineno, current)
    version = current if release else f"{current}b{gdata['run_number']}"

    logme("info", "creating for version %s [%s]", version, gdata["sha"])
    misc.set_variable_def(pyproject, "version", lineno, version, quote)
    return pyproject, version, current


def process_init(
    initfile: Path, gdata: dict[str, Any], version: str, current: str
) -> Path:
    from . import misc

    lineno, old, quote = misc.get_variable_def(initfile, "__version__")
    logme("debug", "found at LN:%i: __version__ = '%s'", lineno, old)
    if old != "" and old != current:
        raise RuntimeError(f"found in {initfile} __version__ {old} != {current}")
    misc.set_variable_def(initfile, "__version__", lineno, version, quote)

    lineno, old, quote = misc.get_variable_def(initfile, "__hash__")
    log.debug("found at LN:%i: __hash__ = '%s'", lineno, old)
    if old != "" and old != gdata["sha"]:
        raise RuntimeError(f"found in {initfile} __hash__ {old} != {gdata['sha']}")
    misc.set_variable_def(initfile, "__hash__", lineno, gdata["sha"], quote)

    return initfile


def build(arguments: list[str]):
    """create beta and release packages for makepyz (only in github)"""
    from . import cli, fileops, github

    global DRYRUN

    def parse_arguments(arguments: list[str]):
        parser = argparse.ArgumentParser()
        parser.add_argument("mode", choices=["beta", "release"])
        parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true")
        return parser.parse_args(arguments)

    options = parse_arguments(arguments)

    if not os.getenv("GITHUB_DUMP"):
        raise cli.AbortWrongArgumentError("no GITHUB_DUMP env defined")

    DRYRUN = options.dryrun
    release = options.mode == "release"
    gdata = github.get_gdata(os.environ["GITHUB_DUMP"])

    with contextlib.ExitStack() as stack:
        save = stack.enter_context(fileops.backups())

        # pyproject.toml
        _, version, current = process_pyproject(save("pyproject.toml"), gdata, release)

        # __init__.py
        _ = process_init(save("src/makepyz/__init__.py"), gdata, version, current)

        if not options.dryrun:
            subprocess.check_call([sys.executable, "-m", "build"])  # noqa: S603
