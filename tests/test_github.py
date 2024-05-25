import json

import pytest

from makepyz import github


def test_validate_gdata(resolver):
    data = json.loads(resolver.lookup("github.master.branch.json").read_text())

    github.validate_gdata(data)
    del data["sha"]

    pytest.raises(RuntimeError, github.validate_gdata, data)


def test_get_gdata(resolver):
    path = resolver.lookup("github.master.branch.json")
    data = json.loads(path.read_text())

    assert github.get_gdata(json.dumps(data)) == {
        "ref_name": "main",
        "ref_type": "branch",
        "run_number": "5",
        "sha": "18cc30248e1023c50f26b0d5c38c11e71e5af99a",
        "workflow_ref": "LuxorLabs/luxos-tooling/.github/workflows/"
        "push-main.yml@refs/heads/main",
    }

    assert github.get_gdata(f"@{path}") == {
        "ref_name": "main",
        "ref_type": "branch",
        "run_number": "5",
        "sha": "18cc30248e1023c50f26b0d5c38c11e71e5af99a",
        "workflow_ref": "LuxorLabs/luxos-tooling/.github/workflows/"
        "push-main.yml@refs/heads/main",
    }
