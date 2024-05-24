from __future__ import annotations

import argparse
import logging
import os
import sys
import subprocess
import contextlib
from pathlib import Path
from typing import Any

from makepyz import api, misc


log = logging.getLogger(__name__)

DRYRUN = None
BUILDDIR = Path.cwd() / "build"

def logme(method, message, *args, **kwargs):
    tag = "(dry-run) " if DRYRUN else ""
    getattr(log, method)(tag + message, *args, **kwargs)


@api.task()
def info(arguments: list[str]):
    """this is the hello world"""
    print(  # noqa: T201
        f"""
    Hi!
    python: {sys.executable}
    version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
    cwd: {Path.cwd()}
    arguments: {arguments}
    """
    )


def process_pyproject(
    pyproject: Path, gdata: dict[str, Any], release: bool
) -> tuple[Path, str, str]:
    lineno, current, quote = misc.get_variable_def(pyproject, "version")
    logme("debug", "found at LN:%i: version = '%s'", lineno, current)
    version = current if release else f"{current}b{gdata['run_number']}"

    logme("info", "creating for version %s [%s]", version, gdata["sha"])
    misc.set_variable_def(pyproject, "version", lineno, version, quote)
    return pyproject, version, current


def process_init(
    initfile: Path, gdata: dict[str, Any], version: str, current: str
) -> Path:
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


@api.task()
def build(arguments: list[str]):
    """create beta and release packages for makepyz (only works in github)"""
    global DRYRUN

    def parse_arguments(arguments: list[str]):
        parser = argparse.ArgumentParser()
        parser.add_argument("mode", choices=["beta", "release"])
        parser.add_argument("-n", "--dry-run", dest="dryrun", action="store_true")
        return parser.parse_args(arguments)

    options = parse_arguments(arguments)

    DRYRUN = options.dryrun

    release = options.mode == "release"

    gdata = api.github.get_gdata(os.environ["GITHUB_DUMP"])

    with contextlib.ExitStack() as stack:
        save = stack.enter_context(api.backups())

        # pyproject.toml
        _, version, current = process_pyproject(save("pyproject.toml"), gdata, release)

        # __init__.py
        _ = process_init(save("src/makepyz/__init__.py"), gdata, version, current)

        if not options.dryrun:
            subprocess.check_call([sys.executable, "-m", "build"])  # noqa: S603


@api.task()
def pack(arguments: list[str]):
    """create a one .pyz single file package"""
    from configparser import ConfigParser, ParsingError

    def parse_arguments2(arguments: list[str]):
        parser = argparse.ArgumentParser()
        parser.add_argument("-o", "--output-dir", default=Path.cwd(), type=Path)
        return parser.parse_args(arguments)

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

    options = parse_arguments2(arguments)

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


@api.task()
def checks():
    """run code checks (ruff/mypy)"""
    api.check_call(
        [
            "pre-commit",
            "run",
            "-a",
            "ruff-format",
        ]
    )
    api.check_call(
        [
            "pre-commit",
            "run",
            "-a",
            "ruff",
        ]
    )
    api.check_call(["pre-commit", "run", "-a", "mypy"])


@api.task()
def tests():
    """run code checks (ruff/mypy)"""
    workdir = Path.cwd()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    # api.check_call(
    #     [
    #         "pytest",
    #         "-vvs",
    #         "--cov",
    #         "makepyz",
    #         "--cov-report",
    #         f"html:{BUILDDIR / 'coverage'}",
    #         "--cov-report",
    #         f"json:{BUILDDIR / 'coverage.json'}",
    #         str(workdir / "tests"),
    #     ],
    #     env=env,
    # )
    import json
    data = json.loads((BUILDDIR / "coverage.json").read_text())

    covered = round(data["totals"]["percent_covered"], 2)
    if covered < 40:
        print(f"🔴 Bad coverage ({covered}%)")
    elif covered < 80:
        print(f"🟡 Not good coverage ({covered}%)")
    else:
        print(f"🟢 Good coverage ({covered}%)")

    failures = [
        (
            str(path).replace("\\", "/"),
            round(pdata["summary"]["percent_covered"], 2),
            pdata["summary"]["num_statements"]
        )
        for path, pdata in data["files"].items()
        if pdata["summary"]["num_statements"] > 10
    ]
    for path, covered, lines in sorted(failures, key=lambda f: -f[1]):
        if covered < 40:
            print(f" 🔴 ({covered}% of {lines}) {path}")
        elif covered < 60:
            print(f" 🟡 ({covered}% of {lines}) {path}")
    print(f"👉 Coverage report under {BUILDDIR / 'coverage'}")


@api.task()
def fmt():
    """run code checks (ruff/mypy)"""
    api.check_call(["ruff", "format", "src", "tests"])
