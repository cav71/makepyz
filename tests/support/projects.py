from __future__ import annotations

import pytest

from makepyz import scm  # F401,E402


@pytest.fixture(scope="function")
def git_project_factory(request, tmp_path):
    """fixture to generate git working repositories

    def test(git_project_factory):
        # simple git repo (only 1 .keep file)
        repo = git_project_factory().create()

        # git repo with a "version" src/__init__.py file
        repo1 = git_project_factory().create("0.0.0")

        # or with version under src/foobar/__init__.py)
        repo1 = git_project_factory("foobar").create("0.0.0")


        # clone from repo
        repo2 = git_project_factory().create(clone=repo)

        assert repo.workdir != repo1.workdir
        assert repo.workdir != repo1.workdir

    """

    class GitRepoBase(scm.GitRepo):
        def init(self, force: bool = False, nobranch: bool = False) -> GitRepoBase:
            from shutil import rmtree

            if force:
                rmtree(self.workdir, ignore_errors=True)
            self.workdir.mkdir(parents=True, exist_ok=True if force else False)

            if not nobranch:
                self(["init", "-b", "master"])
            else:
                self(
                    [
                        "init",
                    ]
                )

            self(["config", "user.name", "First Last"])
            self(["config", "user.email", "user@email"])

            if not nobranch:
                self(["commit", "-m", "initial", "--allow-empty"])
            return self

    class Project(GitRepoBase):
        def __init__(self, name="", *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.name = name

        @property
        def initfile(self):
            return self.workdir / "src" / (self.name or "") / "__init__.py"

        def version(self, value=None):
            if value is not None:
                initial = not self.initfile.exists()
                self.initfile.parent.mkdir(parents=True, exist_ok=True)
                self.initfile.write_text(f'__version__ = "{value}"\n')
                self.commit(
                    [self.initfile], "initial commit" if initial else "update version"
                )

            if not self.initfile.exists():
                return None

            lines = [
                line.partition("=")[2].strip().strip("'").strip('"')
                for line in self.initfile.read_text().split("\n")
                if line.strip().startswith("__version__")
            ]
            return lines[0] if lines else None

        def create(
            self, version=None, clone=None, subdir=None, force=False, nobranch=False
        ):
            if clone:
                clone.clone(self.workdir, force=force)
            else:
                self.init(force=force, nobranch=nobranch)
            self.version(version)
            return self

    def id_generator(size=6):
        from random import choice
        from string import ascii_uppercase, digits

        return "".join(
            choice(ascii_uppercase + digits)  # noqa: S311
            for _ in range(size)
        )

    return lambda subdir="", name="": Project(
        name, tmp_path / (subdir or id_generator())
    )
    # or request.node.name
