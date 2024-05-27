from __future__ import annotations

import argparse
import contextlib
import logging
import sys
from pathlib import Path

from makepyz import api, tasks_gh

log = logging.getLogger(__name__)

DRYRUN = None
BUILDDIR = Path("build")


tests = api.task()(api.tasks.tests)
checks = api.task()(api.tasks.checks)
fmt = api.task()(api.tasks.fmt)
build = api.task()(tasks_gh.build)


@api.task()
def pack(arguments: list[str]):
    """create a one .pyz single file package"""
    from configparser import ConfigParser, ParsingError

    def parse_arguments(arguments: list[str]):
        parser = argparse.ArgumentParser()
        parser.add_argument("-o", "--output-dir", default=Path.cwd(), type=Path)
        return parser.parse_args(arguments)

    options = parse_arguments(arguments)

    workdir = Path.cwd()

    config = ConfigParser(strict=False)
    with contextlib.suppress(ParsingError):
        config.read(workdir / "pyproject.toml")

    targets = []
    section = "project.scripts"
    for target in config.options(section):
        entrypoint = config.get(section, target).strip("'").strip('"')
        if target == "makepyz":
            targets.append((f"{target}", entrypoint))
        else:
            targets.append((f"{target}.pyz", entrypoint))

    changed = False
    for target, entrypoint in targets:
        dst = options.output_dir / target
        out = api.makezapp(dst, workdir / "src", main=entrypoint, compressed=True)

        relpath = dst.relative_to(Path.cwd()) if dst.is_relative_to(Path.cwd()) else dst
        if out:
            print(f"Written: {relpath}", file=sys.stderr)
            changed = True
        else:
            print(f"Skipping generation: {relpath}", file=sys.stderr)
    sys.exit(int(changed))
