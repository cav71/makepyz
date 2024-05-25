# All related to packaging
from __future__ import annotations

import hashlib
import zipapp
from pathlib import Path

from . import fileops


def zhash(path: Path, encoding: str | None = "utf-8") -> dict[str, str]:
    """extract a zip file in path"""
    result = {}
    for key, data in fileops.zextract(path, encoding=encoding).items():
        if isinstance(data, str):
            binary = data.encode(encoding or "utf-8")
        else:
            binary = data

        result[key] = hashlib.sha256(binary).hexdigest()
    return result


def makezapp(dst: Path, srcdir: Path, *args, **kwargs) -> Path | None:
    def filter(path: Path) -> bool:
        if "__pycache__" in str(path):
            return False
        if ".egg-info" in str(path):
            return False
        return True

    kwargs = kwargs.copy()
    if "filter" not in kwargs:
        kwargs["filter"] = filter

    generate = True
    if dst.exists():
        dst1 = dst.parent / f"{dst.name}.bak"
        zipapp.create_archive(srcdir, dst1, *args, **kwargs)
        generate = zhash(dst) != zhash(dst1)
        dst1.unlink()

    if generate:
        zipapp.create_archive(srcdir, dst, *args, **kwargs)
        return dst
