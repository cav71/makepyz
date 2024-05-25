"""various file/dir related functions"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Iterator, overload


class FileOSError(Exception):
    pass


class FileOSModuleNotFoundError(FileOSError):
    pass


class FileOSMInvalidModuleError(FileOSError):
    pass


def rmtree(path: Path):
    """universal (win|*nix) rmtree"""

    from os import name
    from shutil import rmtree
    from stat import S_IWUSR

    if name == "nt":
        for p in path.rglob("*"):
            p.chmod(S_IWUSR)
    rmtree(path, ignore_errors=True)
    if path.exists():
        raise RuntimeError(f"cannot remove {path=}")


def mkdir(path: Path) -> Path:
    """make a path directory and returns if it has been created"""
    path.mkdir(exist_ok=True, parents=True)
    return path


def touch(path: Path) -> Path:
    """touch a new empty file"""
    mkdir(path.parent)
    path.write_text("")
    return path


@overload
def which(exe: Path | str) -> list[Path]: ...


@overload
def which(exe: Path | str, kind: type[list]) -> list[Path]: ...


@overload
def which(exe: Path | str, kind: None) -> Path | None: ...


def which(exe: Path | str, kind: type[list] | None = None) -> list[Path] | Path | None:
    candidates: list[Path] = []
    for srcdir in os.environ.get("PATH", "").split(os.pathsep):
        for ext in os.environ.get("PATHEXT", "").split(os.pathsep):
            path = srcdir / Path(exe).with_suffix(ext)
            if not path.exists():
                continue
            if kind is None:
                return path
            candidates.append(path)
    return candidates


def loadmod(path: Path | str, suffix: str | None = "") -> types.ModuleType:
    import inspect
    from importlib import machinery, util

    if isinstance(path, str):
        if not Path(path).is_absolute():
            path = Path(inspect.stack()[1].filename).parent / path
        path = Path(path)

    if suffix is not None:
        machinery.SOURCE_SUFFIXES.append(suffix)
    try:
        spec = util.spec_from_file_location(Path(path).name, Path(path))
        if not spec:
            raise FileOSModuleNotFoundError(f"cannot find module for {path=}")
        module = util.module_from_spec(spec)
        if not spec.loader:
            raise FileOSMInvalidModuleError(f"invalid module in {path=}")
        spec.loader.exec_module(module)
    finally:
        if suffix is not None:
            machinery.SOURCE_SUFFIXES.pop()
    return module


### FILE UTILITIES


def zextract(
    path: Path | str, items: list[str] | None = None, encoding: str | None = "utf-8"
) -> dict[str, str | bytes]:
    """extracts from path (a zipfile/tarball) all data in a dictionary"""
    from tarfile import TarFile, is_tarfile
    from zipfile import ZipFile, is_zipfile

    path = Path(path)
    result: dict[str, str | bytes] = {}
    if is_tarfile(path):
        with TarFile.open(path) as tfp:
            for member in tfp.getmembers():
                fp = tfp.extractfile(member)
                if not fp:
                    continue
                result[member.name] = str(fp.read(), encoding="utf-8")
    elif is_zipfile(path):
        with ZipFile(path) as tfp:
            for zinfo in tfp.infolist():
                if items and zinfo.filename not in items:
                    continue
                with tfp.open(zinfo.filename) as fp:
                    data = fp.read()
                    try:
                        if encoding:
                            out = str(data, encoding=encoding).replace("\r", "")
                            result[zinfo.filename] = out
                        else:
                            result[zinfo.filename] = data
                    except UnicodeDecodeError:
                        pass

    return result


def backup(path: Path, ext: str, overwrite: bool = False, abort: bool = True) -> Path:
    """creates a backup of path"""
    from shutil import copyfile, copymode

    path2 = path.parent / f"{path.name}{ext}"
    if path2.exists() and not overwrite:
        if abort:
            raise FileOSError(f"backup file present {path2}")
        return path2

    copyfile(path, path2)
    copymode(path, path2)
    return path2


def unbackup(path: Path, ext: str, abort: bool = True) -> Path:
    """restores from a backup of path"""
    from shutil import move

    path2 = path.parent / f"{path.name}{ext}"
    if abort and not path2.exists():
        raise FileOSError(f"cannot find backup file {path2} for {path=}")
    if path2.exists():
        move(str(path2), str(path))
    return path2


@contextlib.contextmanager
def mkstemp(**kwargs) -> Iterator[Path]:
    fid, name = tempfile.mkstemp(**kwargs)
    os.close(fid)
    path = Path(name)
    try:
        yield path
    finally:
        path.unlink()


@contextlib.contextmanager
def backups():
    pathlist: list[Path | str] = []

    def save(path: Path | str):
        nonlocal pathlist
        original = Path(path).expanduser().absolute()
        backup = original.parent / f"{original.name}.bak"
        if backup.exists():
            raise RuntimeError("backup file present", backup)
        shutil.copy(original, backup)
        pathlist.append(backup)
        return original

    try:
        yield save
    finally:
        for backup in pathlist:
            original = Path(backup).with_suffix("")
            original.unlink()
            shutil.move(Path(backup), original)


def check_call(*args, **kwargs):
    """multiplatform check_call"""

    # this takes care of win/*nix fdifferences
    shell = False
    env = kwargs.get("env", os.environ).copy()
    if sys.platform == "win32":
        epath = os.environ.get("PATH", "").split(os.pathsep)
        exedir = Path(sys.executable).parent / "Scripts"
        if str(exedir) not in epath:
            epath.insert(0, str(exedir))
        env["PATH"] = os.pathsep.join(str(e) for e in epath)

        eext = os.environ.get("PATHEXT", "").split(os.pathsep)
        exeext = ".EXE"
        if exeext not in eext:
            eext.insert(0, str(exeext))
        env["PATHEXT"] = os.pathsep.join(str(e) for e in eext)
        shell = True
    kwargs["shell"] = shell
    kwargs["env"] = env
    return subprocess.check_call(*args, **kwargs)
