from __future__ import annotations

import functools
import inspect
import json
import os
import sys
import types
from pathlib import Path

from . import fileops

BASEDIR: Path | None = None


def task(name: str | None = None):
    def _fn(function):
        @functools.wraps(function)
        def _fn1(*args, **kwargs):
            oldcd = Path.cwd()
            try:
                if not BASEDIR:
                    raise RuntimeError("BASEDIR not defined")
                os.chdir(BASEDIR)
                params = inspect.signature(function).parameters
                if "workdir" in params:
                    kwargs["workdir"] = oldcd
                return function(*args, **kwargs)
            finally:
                os.chdir(oldcd)

        _fn1.task = name or function.__name__  # type: ignore
        return _fn1

    return _fn


def info(arguments: list[str], mod: types.ModuleType | None = None):
    """this is the hello world"""
    from makepyz import api

    print(  # noqa: T201
        f"""
Hi!
  python: {sys.executable}
  version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}
  cwd: {Path.cwd()}
  mod: {mod}
  arguments: {arguments}
"""
    )
    print("** SPECIAL MODULE LEVEL VARIABLE **")
    for name, value in sorted(api.MODULE_VARIABLES.items(), key=lambda x: x[0].upper()):
        print(f"{name}")
        print(f"  actual: {getattr(mod, name, 'N/A')}")
        print(f"  api:    {value}")
    print()
    print("** ARGUMENTS **")
    names = [f"[{i}]" for i in range(len(arguments))]
    width = max(len(n) for n in names)
    head = f"  {{name:{width + 1}}}{{sep}} '{{value}}'"
    for name, argument in zip(names, arguments) or []:  # type: ignore
        print(head.format(name=name, value=argument, sep=":"))


def tests(arguments: list[str], mod: types.ModuleType):
    """run all tests"""

    # def parse_arguments(arguments: list[str]):
    #     parser = argparse.ArgumentParser()
    #     parser.add_argument("--json", action="store_true")
    #     return parser.parse_args(arguments)
    #
    # options = parse_arguments(arguments)

    builddir = mod.BUILDDIR

    workdir = Path.cwd()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd() / "src")
    fileops.check_call(
        [
            "pytest",
            "-vvs",
            "--cov",
            "makepyz",
            "--cov-report",
            f"html:{builddir / 'coverage'}",
            "--cov-report",
            f"json:{builddir / 'coverage.json'}",
            str(workdir / "tests"),
        ],
        env=env,
    )

    data = json.loads((builddir / "coverage.json").read_text())

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
            pdata["summary"]["num_statements"],
        )
        for path, pdata in data["files"].items()
        if pdata["summary"]["num_statements"] > 10
    ]
    for path, covered, lines in sorted(failures, key=lambda f: -f[1]):
        if covered < 40:
            print(f" 🔴 ({covered}% of {lines}) {path}")
        elif covered < 60:
            print(f" 🟡 ({covered}% of {lines}) {path}")
    print(f"👉 Coverage report under {builddir / 'coverage'}")


def checks():
    """run code checks (ruff/mypy)"""
    fileops.check_call(
        [
            "pre-commit",
            "run",
            "-a",
            "ruff-format",
        ]
    )
    fileops.check_call(
        [
            "pre-commit",
            "run",
            "-a",
            "ruff",
        ]
    )
    fileops.check_call(["pre-commit", "run", "-a", "mypy"])


def fmt():
    """apply 'ruff check --fix'"""
    fileops.check_call(["ruff", "check", "--fix", "src", "tests"])
