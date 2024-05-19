# see https://pypi.org/project/setuptools-github
# copy of setuptools_github.scm
from __future__ import annotations

import dataclasses as dc
import io
import re
import subprocess
from pathlib import Path
from typing import Any, List, Union

from typing_extensions import TypeAlias

ListOfArgs: TypeAlias = Union[str, Path, List[Union[str, Path]]]


def to_list_of_paths(paths: ListOfArgs) -> list[Path]:
    return [Path(s) for s in ([paths] if isinstance(paths, (str, Path)) else paths)]


def indent(txt: str, pre: str = " " * 2) -> str:
    "simple text indentation"

    from textwrap import dedent

    txt = dedent(txt)
    if txt.endswith("\n"):
        last_eol = "\n"
        txt = txt[:-1]
    else:
        last_eol = ""

    result = pre + txt.replace("\n", "\n" + pre) + last_eol
    return result if result.strip() else result.strip()


def shorthand(txt: str) -> str:
    tag = "refs/heads/"
    return txt[len(tag) :] if txt.startswith(tag) else txt


class NA:
    pass


class GitError(Exception):
    pass


class InvalidGitRepoError(GitError):
    pass


@dc.dataclass
class GitRepoBranches:
    local: list[str]
    remote: list[str]


@dc.dataclass
class GitRepoHead:
    @dc.dataclass
    class GitRepoHeadHex:
        hex: str

    name: str
    target: GitRepoHeadHex

    @property
    def shorthand(self):
        return shorthand(self.name)


class GitRepoBase:
    def __init__(self, workdir: Path | str, exe: str = "git", gitdir: Path | str = ""):
        self.workdir = Path(workdir).absolute()
        self.exe = exe
        self.gitdir = Path(gitdir or (self.workdir / ".git")).absolute()

    def __call__(self, cmd: ListOfArgs) -> str:
        cmds = cmd if isinstance(cmd, list) else [cmd]

        arguments = [self.exe]
        if cmds[0] != "clone":
            arguments.extend(
                [
                    "--work-tree",
                    str(self.workdir),
                    "--git-dir",
                    str(self.gitdir),
                ]
            )
        arguments.extend(str(c) for c in cmds)
        return subprocess.check_output(arguments, encoding="utf-8")  # noqa: S603

    def __truediv__(self, other):
        return (self.workdir / other).absolute()

    def dumps(self, mask: bool = False) -> str:
        lines = f"REPO: {self.workdir}"
        lines += "\n [status]\n" + indent(self(["status"]))
        branches = self(["branch", "-avv"])
        if mask:
            branches = re.sub(r"(..\w\s+)\w{7}(\s+.*)", r"\1ABCDEFG\2", branches)
        lines += "\n [branch]\n" + indent(branches)
        lines += "\n [tags]\n" + indent(self(["tag", "-l"]))
        lines += "\n [remote]\n" + indent(self(["remote", "-v"]))

        buf = io.StringIO()
        print("\n".join([line.rstrip() for line in lines.split("\n")]), file=buf)
        return buf.getvalue()


class GitRepo(GitRepoBase):
    @property
    def config(self):
        @dc.dataclass
        class X:
            repo: GitRepo

            def __getitem__(self, item: str):
                return self.repo(["config", item]).strip()

            def __setitem__(self, item: str, value: Any):
                self.repo(["config", item, str(value)])

            def __contains__(self, item: str):
                return item in self.repo(
                    [
                        "config",
                        "--list",
                        "--name-only",
                    ]
                ).split("\n")

        return X(self)

    def revert(self, paths: ListOfArgs | None = None):
        sources = to_list_of_paths(paths or self.workdir)
        self(["checkout", *sources])

    @property
    def detached(self):
        try:
            self(["symbolic-ref", "HEAD"]).strip()
        except subprocess.CalledProcessError:
            ref = (self.gitdir / "HEAD").read_text().strip()
            if re.search("^[a-fA-F0-9]+$", ref):
                return GitRepoHead(
                    name="refs/heads/master", target=GitRepoHead.GitRepoHeadHex(ref)
                )

    @property
    def head(self):
        # handles the detached git mode (used by pip)
        if head := self.detached:
            return head

        name = self(["symbolic-ref", "HEAD"]).strip()
        try:
            txt = self(["rev-parse", name]).strip()
        except subprocess.CalledProcessError as exc:
            raise GitError(f"no branch '{name}'") from exc
        return GitRepoHead(name=name, target=GitRepoHead.GitRepoHeadHex(txt))

    def status(
        self,
        untracked_files: str = "all",
        ignored: bool = False,
    ) -> dict[str, int]:
        # to update the mapping:
        # pygit2.Repository(self.workdir).status()
        mapper = {
            "??": 128 if untracked_files == "all" else None,
            " D": 512,
            "D ": 4,
            " M": 256,
            "MM": 258,
            "A ": 1,
            "R ": 4 | 1,
            "RM": 4 | 1 | 256,
            "RD": 4 | 1 | 256,
        }
        result: dict[str, int] = {}
        try:
            txt = self(["status", "--porcelain"])
        except subprocess.CalledProcessError as exc:
            raise GitError("invalid repo") from exc
        for line in txt.split("\n"):
            if not line.strip():
                continue
            tag, filename = line[:2], line[3:]
            if tag not in mapper:
                raise GitError(f"cannot map git status for '{tag}' on {filename}")
            value = mapper[tag]
            if value:
                result[filename] = (
                    (result[filename] | value) if filename in result else value
                )
        return result

    def dirty(self) -> bool:
        return bool(self.status(untracked_files="no"))

    def commit(
        self,
        paths: ListOfArgs,
        message: str,
    ) -> None:
        all_paths = to_list_of_paths(paths)
        self(["add", *all_paths])
        self(["commit", "-m", message, *all_paths])

    def branch(self, name: str | None = None, origin: str = "master") -> str:
        if not name:
            name = self.head.name or ""
            return name[11:] if name.startswith("refs/heads/") else name
        if not (origin or origin is None):
            raise RuntimeError(f"invalid {origin=}")
        old = self.branch()
        self(["checkout", "-b", name, "--track", origin])
        return old[11:] if old.startswith("refs/heads/") else old

    @property
    def branches(self) -> GitRepoBranches:
        result = GitRepoBranches([], [])
        for line in self(["branch", "-a", "--format", "%(refname)"]).split("\n"):
            if not line.strip():
                continue
            if line.startswith("refs/heads/"):
                result.local.append(line[11:])
            elif line.startswith("refs/remotes/"):
                result.remote.append(line[13:])
            else:
                raise RuntimeError(f"invalid branch {line}")
        return result

    @property
    def references(self) -> list[str]:
        return [
            f"refs/tags/{line.strip()}"
            for line in self(["tag", "-l"]).split("\n")
            if line.strip()
        ]

    def clone(
        self,
        dest: str | Path,
        force: bool = False,
        branch: str | None = None,
    ) -> GitRepo:
        from shutil import rmtree

        workdir = Path(dest).absolute()
        if force:
            rmtree(workdir, ignore_errors=True)
        if workdir.exists():
            raise ValueError(f"target directory present {workdir}")

        self(
            [
                "clone",
                *(["--branch", branch] if branch else []),
                self.workdir.absolute(),
                workdir.absolute(),
            ],
        )

        repo = self.__class__(workdir=workdir)
        repo(["config", "user.name", self(["config", "user.name"])])
        repo(["config", "user.email", self(["config", "user.email"])])

        return repo


def lookup(path: Path | str) -> GitRepo | None:
    cur = Path(path).absolute()
    found = False
    while not found and cur != cur.parent:
        if (cur / ".git").exists():
            return GitRepo(cur)
        if str(cur) == cur.root:
            break
        cur = cur.parent

    return None
