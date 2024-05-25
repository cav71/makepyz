import sys
from pathlib import Path

import pytest

from makepyz import fileops


def test_rmtree(tmp_path):
    target = tmp_path / "abc" / "def"
    target.mkdir(parents=True, exist_ok=True)
    assert target.exists()

    fileops.rmtree(target)
    assert not target.exists()
    assert target.parent.exists()


def test_mkdir(tmp_path):
    target = tmp_path / "abc"
    assert not target.exists()
    assert fileops.mkdir(target)
    assert target.exists()
    assert target.is_dir()


def test_touch(tmp_path):
    target = tmp_path / "abc"
    assert not target.exists()
    assert fileops.touch(target)
    assert target.exists()
    assert target.is_file()


def test_which():
    exe = "cmd" if sys.platform == "win32" else "sh"

    path = fileops.which(exe)
    assert path
    assert isinstance(path, Path)

    path = fileops.which(exe, kind=list)
    assert path
    assert isinstance(path, list)
    assert path[0] == fileops.which(exe)


def test_loadmod(tmp_path):
    path = fileops.touch(tmp_path / "blah")
    path.write_text("MYVAR = 99")

    mod = fileops.loadmod(path)
    assert mod.MYVAR == 99

    pytest.raises(FileNotFoundError, fileops.loadmod, tmp_path / "xyz")


def test_zextract(resolver):
    ball = resolver.lookup("foobar-0.0.0-py3-none-any.whl")
    data = fileops.zextract(ball)
    assert data["foobar/__init__.py"].strip() == '__version__ = "0.0.0"'

    ball = resolver.lookup("foobar-0.0.0.tar.gz")
    data = fileops.zextract(ball)
    assert (
        data["foobar-0.0.0/src/foobar/__init__.py"].strip() == '__version__ = "0.0.0"'
    )


def test_backup_unbackup(tmp_path):
    path = tmp_path / "anoter.test.txt"
    path.write_text("A brand new message")
    bak = path.parent / f"{path.name}.original"

    assert not bak.exists()

    assert fileops.backup(path, ".original") == bak
    assert bak.exists()
    pytest.raises(fileops.FileOSError, fileops.backup, path, ".original")
    path.write_text("New message")

    assert fileops.unbackup(path, ".original") == bak
    assert not bak.exists()
    pytest.raises(fileops.FileOSError, fileops.unbackup, path, ".original")
    assert path.read_text() == "A brand new message"
