from __future__ import annotations

import importlib.util
import types

from makepyz import text

rich: types.ModuleType | None = None
if _spec := importlib.util.find_spec("rich"):
    rich = importlib.util.module_from_spec(_spec)


def test_indent():
    txt = """

            Lorem Ipsum is simply dummy text of the printing and
          typesetting industry. Lorem Ipsum has been the industry's standard
         dummy text ever since the 1500s, when an unknown printer
           took a galley of type and scrambled it to make a type specimen book.
"""

    assert (
        text.indent(txt, "." * 2)
        == """\
..
..
..   Lorem Ipsum is simply dummy text of the printing and
.. typesetting industry. Lorem Ipsum has been the industry's standard
..dummy text ever since the 1500s, when an unknown printer
..  took a galley of type and scrambled it to make a type specimen book.
"""
    )


def test_indent2():
    txt = """\
     An unusually complicated text
    with un-even indented lines
   that make life harder
"""
    assert (
        text.indent(txt, pre="..")
        == """\
..  An unusually complicated text
.. with un-even indented lines
..that make life harder
"""
    )


def test_indent_another():
    txt = """
    This is a simply
       indented text
      with some special
         formatting
"""
    expected = """
..This is a simply
..   indented text
..  with some special
..     formatting
"""

    found = text.indent(txt[1:], "..")
    assert f"\n{found}" == expected


def test_lstrip():
    assert text.lstrip("/a/b/c/d/e", "/a/b") == "/c/d/e"


def test_md(resolver):
    txt = """
## Intro

This is a test!
> **NOTE** Wow
"""

    path = resolver.lookup("test.md.txt")
    assert text.md(txt, width=80).replace("\r", "") == str(
        path.read_bytes(), encoding="utf-8"
    ).replace("\r", "")
