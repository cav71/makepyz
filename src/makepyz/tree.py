# # tree -aF layouts/my-project
from __future__ import annotations

import argparse
import collections
import dataclasses as dc
import enum
import io
import sys
from pathlib import Path
from typing import TextIO


class NodeError(Exception):
    pass


class InvalidNodeType(NodeError):
    pass


class InvalidNodeName(NodeError):
    pass


class LocationError(NodeError):
    pass


class Kind(enum.IntEnum):
    UNKNOWN = 1
    DIR = 1
    FILE = 2


@dc.dataclass
class Node:
    name: str
    kind: Kind = Kind.UNKNOWN
    children: list[Node] = dc.field(default_factory=list)
    parent: Node | None = None

    def __post_init__(self):
        if self.name.endswith("/"):
            if self.kind is None:
                self.kind = Kind.DIR
            if self.kind != Kind.DIR:
                raise InvalidNodeName(f"cannot use {self.name=} for a non dir")
        assert self.kind
        self.name = self.name.rstrip("/")

    def append(self, node: Node) -> None:
        node.parent = self
        self.children.append(node)

    def __repr__(self):
        return (
            f"<{self.__class__.__name__} "
            f"name='{self.name}' "
            f"kind={self.kind.name if self.kind else self.kind} "
            f"parent={self.parent.name if self.parent else None} "
            f"children={len(self.children)} "
            f"at {hex(id(self))}>"
        )

    @property
    def xpath(self) -> list[str]:
        result = []
        cur: Node | None = self
        while cur is not None:
            result.append(cur.name)
            cur = cur.parent
        return list(reversed(result))

    @property
    def path(self) -> Path:
        return Path(*self.xpath)


def create(path: Path) -> Node:
    """
    Generates a tree out of path directory.

    Args:
        path: A Path object representing the directory to start the walk from.

    Returns:
        A Node object representing the root of the directory tree.

    Raises:
        InvalidNodeType: If the specified path is not a directory.

    """
    if not path.is_dir():
        raise InvalidNodeType("path is not a directory", path)

    root = Node("", Kind.DIR)
    queue = collections.deque([root])
    while queue:
        n = len(queue)
        for i in range(n):
            cur = queue.popleft()
            if not (sub := (path / cur.path)).is_dir():
                continue
            for child in sorted(sub.glob("*")):
                node = Node(
                    child.name, Kind.DIR if child.is_dir() else Kind.FILE, parent=cur
                )
                cur.children.append(node)
                if child.is_dir():
                    queue.appendleft(node)
    return root


def find(root: Node, loc: str | list[str], create: bool = False) -> Node | None:
    """find a node starting from root tree"""
    if isinstance(loc, str):
        lloc = collections.deque(loc.rstrip("/").split("/"))
        if loc.endswith("/"):
            lloc[-1] = f"{lloc[-1]}/"
    else:
        lloc = collections.deque(loc[:])
    kind = Kind.FILE
    if lloc[-1].endswith("/"):
        kind = Kind.DIR
        lloc[-1] = lloc[-1].rstrip("/")
    for i in range(len(lloc)):
        lloc[i] = lloc[i].rstrip("/")

    def lookup(node: Node, key: str) -> list[Node]:
        return [child for child in node.children if child.name == key]

    cur = root
    while lloc:
        path = lloc.popleft()
        found = lookup(cur, path)
        if not found:
            if create:
                if cur.kind == Kind.FILE:
                    raise InvalidNodeType(
                        f"cannot insert {path=} under {cur=}", cur, path
                    )
                cur.append(Node(path.rstrip("/"), Kind.DIR if lloc else kind))
            else:
                return None
        cur = lookup(cur, path)[0]

    return cur


def write(path: Path, root: Node) -> None:
    # TODO implement this
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)

    queue = collections.deque([root])
    while queue:
        node = queue.popleft()
        dst = path / node.path
        dst.relative_to(path)
        if node.kind == Kind.FILE:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text("")
        else:
            dst.mkdir(parents=True, exist_ok=True)
            for child in node.children:
                queue.appendleft(child)


def dumps(root: Node, nbs: str = " ") -> str:
    # use nbs="\u00A0" when comparing tree -aF

    buffer = io.StringIO()
    queue = collections.deque([(root, "", True)])
    counter = 0
    head = True
    while queue:
        counter += 1
        node, indent, is_last = queue.pop()
        if node.kind == Kind.DIR:
            pre = "" if head else "└── " if is_last else "├── "
            print(f"{indent}{pre}{node.name}/", file=buffer)
            for i, child in enumerate(reversed(node.children)):
                is_last2 = i == 0
                mid = indent + ("    " if is_last else f"│{nbs}{nbs} ")
                if head:
                    mid = "" if is_last else f"│{nbs}{nbs} "
                queue.append(
                    (
                        child,
                        mid,
                        is_last2,
                    )
                )
            if head:
                head = False
        else:
            print(f"{indent}{'└──' if is_last else '├──'} {node.name}", file=buffer)
    return buffer.getvalue()


def parse(txt: str) -> Node:
    plevel = 0
    sep = "─ "
    result = []
    context: collections.deque[str] = collections.deque()
    for line in txt.split("\n"):
        if sep not in line:
            continue
        index = line.find(sep) + len(sep)
        level = index // 4
        key = line[index:].rstrip()
        if level > plevel:
            context.append(key)
            plevel = level
        elif level == plevel:
            result.append(list(context))
            context[-1] = key
        else:
            result.append(list(context))
            for _ in range(plevel - level + 1):
                context.pop()
            context.append(key)
            plevel = level
    if context:
        result.append(list(context))

    root = Node("/")
    for path in result:
        find(root, path, create=True)
    return root


def plot(root: Node, buffer: TextIO = sys.stdout) -> TextIO:
    print("digraph {", file=buffer)

    mapper = {}
    counter = 0
    queue = collections.deque([root])
    while queue:
        node = queue.popleft()
        key, val = f"n-{counter:05}", node.name
        mapper[hex(id(node))] = (key, val)
        print(f'  "{key}" [label="{val}"]', file=buffer)

        for n in reversed(node.children or []):
            queue.appendleft(n)
        counter += 1

    queue = collections.deque([root])
    while queue:
        node = queue.popleft()
        start = mapper[hex(id(node))]

        for n in reversed(node.children or []):
            end = mapper[hex(id(n))]
            print(f'  "{start[0]}" -> "{end[0]}"', file=buffer)
            queue.appendleft(n)

    print("}", file=buffer)
    return buffer


def showtree(root: Node) -> None:  # pragma: no cover
    from contextlib import ExitStack
    from subprocess import call, check_call
    from tempfile import NamedTemporaryFile
    from time import sleep

    if sys.platform != "darwin":
        raise NotImplementedError(f"cannot use this on {sys.platform}")

    buffer = plot(root, io.StringIO())
    if not hasattr(buffer, "getvalue"):
        return
    txt = buffer.getvalue()

    with ExitStack() as stack:
        dotout = stack.enter_context(NamedTemporaryFile())
        pngout = stack.enter_context(NamedTemporaryFile(suffix=".png"))
        dotout.write(txt.encode("utf-8"))
        dotout.flush()
        cmd = [
            Path(sys.executable).parent / "dot",
            "-Tpng",
            f"-o{pngout.name}",
            dotout.name,
        ]
        check_call([str(c) for c in cmd])
        pngout.file.flush()
        call(["open", pngout.name])
        sleep(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--copy", type=Path, help="destination directory")
    parser.add_argument("srcdir", type=Path, help="source directory")
    args = parser.parse_args()

    if not args.srcdir.exists():
        parser.error(f"dir not found, {args.srcdir}")
    if not args.srcdir.is_dir():
        parser.error(f"path is not a dir, {args.srcdir}")

    root = create(args.srcdir)
    if args.copy:
        write(args.copy, root)

    root.name = args.srcdir
    print(dumps(root))


if __name__ == "__main__":
    main()
