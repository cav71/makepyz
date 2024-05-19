from __future__ import annotations

import argparse
import functools
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING
import logging

if TYPE_CHECKING:
    from jinja2 import Environment


log = logging.getLogger(__name__)


def get_variable_def(
    path: Path, key: str, abort: bool = True
) -> tuple[int | None, str, str]:
    # version = "1.2.3"

    expr = re.compile(key + r"\s*[=]\s*(?P<quote>['\"])(?P<version>(\d+([.]\d)*)?)\1")
    found = []
    lines = path.read_text().split("\n")
    for lineno, line in enumerate(lines):
        if match := expr.search(line):
            found.append((lineno, match.group("version"), match.group("quote")))
    if not abort and len(found) == 0:
        return None, "", ""
    if len(found) != 1:
        raise RuntimeError(f"found {len(found)} candidates for {key} in {path}")
    return found[0]


def set_variable_def(
    path: Path, key: str, lineno: int | None, version: str, quote: str
) -> None:
    lines = path.read_text().split("\n")
    line = f"{key} = {quote}{version}{quote}"
    if lineno is None:
        lines.append(line)
    else:
        lines[lineno] = line
    path.write_text("\n".join(lines))


def get_environment(data: dict[str, str]) -> Environment:
    """returns a context object"""
    from jinja2 import Environment
    from urllib.parse import quote

    class Context(argparse.Namespace):
        def items(self):
            for name, value in self.__dict__.items():
                if name.startswith("_"):
                    continue
                yield (name, value)

    env = Environment(autoescape=True)
    env.filters["urlquote"] = functools.partial(quote, safe="")
    env.globals = {
        "dir": dir,
        "len": len,
        "sorted": sorted,
        "reversed": reversed,
    }
    env.globals["ctx"] = Context(**data)
    return env


def zdata(path: Path):
    from makepyz.fileos import zextract
    from hashlib import sha256

    result = {}
    for key, data in zextract(path).items():
        result[key] = sha256(data.encode("utf-8")).hexdigest()
    return result


def makezapp(dst: Path, srcdir: Path, *args, **kwargs) -> Path | None:
    from zipapp import create_archive

    # cleanup cache dirs
    for cachedir in srcdir.rglob("__pycache__"):
        shutil.rmtree(cachedir, ignore_errors=True)
    for cachedir in srcdir.rglob("*.egg-info"):
        shutil.rmtree(cachedir, ignore_errors=True)

    generate = True
    if dst.exists():
        dst1 = dst.parent / f"{dst.name}.bak"
        create_archive(srcdir, dst1, *args, **kwargs)
        generate = zdata(dst) != zdata(dst1)
        dst1.unlink()

    if generate:
        # cleanup cache dirs
        for xx in srcdir.rglob("__pycache__"):
            shutil.rmtree(xx, ignore_errors=True)

        create_archive(srcdir, dst, *args, **kwargs)
        return dst
