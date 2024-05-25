from makepyz import packaging


def test_zhash(resolver):
    path = resolver.lookup("support.zip")
    assert packaging.zhash(path) == {
        "support/__init__.py": "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855",
        "support/projects.py": "5251be0d3003c87a3e713c0f54f1d6e8"
        "55a8a8b009afe1f542df18225638532e",
        "support/resolver.py": "92bb0412309795ddb34837ff0d25fd36"
        "47d0b9dd3ae935633033d0a24772b47d",
        "support/scripter.py": "e763f376c92dfa5aad69154146bf506d"
        "11cc08da9fc3e24b5d7e1e9e6d755987",
    }
