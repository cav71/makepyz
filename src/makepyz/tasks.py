from __future__ import annotations

import functools
import inspect
import os
from pathlib import Path

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
