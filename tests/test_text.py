from makepyz import text

try:
    import rich
except ModuleNotFoundError:
    rich = None


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
