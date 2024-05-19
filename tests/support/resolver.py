"""adds a datadir and resolver fixtures"""

from __future__ import annotations

import dataclasses as dc
import os
from pathlib import Path

import pytest


@pytest.fixture()
def datadir(request):
    """return the Path object to the tests datadir

    Examples:
        # This will print the tests/data directory
        # (unless overridden using DATADIR env)
        >>> def test_me(datadir):
        >>>    print(datadir)
    """
    basedir = Path(__file__).parent.parent / "data"
    if os.getenv("DATADIR"):
        basedir = Path(os.environ["DATADIR"])
    basedir = basedir / getattr(request.module, "DATADIR", "")
    return basedir


@pytest.fixture(scope="function")
def resolver(request, datadir):
    """return a resolver object to lookup for test data

    Examples:
        >>> def test_me(resolver):
        >>>     print(resolver.lookup("a/b/c"))
    """

    @dc.dataclass
    class Resolver:
        root: Path
        name: str

        def lookup(self, path: Path | str) -> Path:
            candidates = [
                self.root / self.name / path,
                self.root / path,
            ]
            for candidate in candidates:
                if candidate.exists():
                    return candidate
            raise FileNotFoundError(f"cannot find {path}", candidates)

    yield Resolver(datadir, request.module.__name__)


@pytest.fixture(scope="function")
def mktree(tmp_path):
    """
    Args:
        tmp_path (str): The temporary path where the tree structure will be created.

    Returns:
        function: A nested function that creates a directory tree or
        files within the given temporary path.

    """

    def create(txt, mode=None, subpath=""):
        mode = mode or ("tree" if "─ " in txt else "txt")
        if mode == "tree":
            from makepyz import tree

            tree.write(Path(tmp_path) / subpath, tree.parse(txt))
        else:
            for path in [f for f in txt.split("\n") if f.strip()]:
                dst = Path(tmp_path) / subpath / path.strip()
                if path.strip().startswith("#"):
                    continue
                elif path.strip().endswith("/"):
                    dst.mkdir(exist_ok=True, parents=True)
                else:
                    dst.parent.mkdir(exist_ok=True, parents=True)
                    dst.write_text("")
        return Path(tmp_path) / subpath

    return create
