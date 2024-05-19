from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

# this fixtures allows loading data from data subdir
# Eg.
#     resolver.lookup("foobar") ->
#       looks un under data/foobar or data/test_name/foobar
from support.resolver import datadir, resolver, mktree  # noqa: F401


# this ficture generate a new brand python/git project
# Eg.
#     repo = git_project_factory().create()
from support.projects import git_project_factory  # noqa: F401


def loadmod(path: Path) -> types.ModuleType:
    from importlib import util

    spec = util.spec_from_file_location(Path(path).name, Path(path))
    module = util.module_from_spec(spec)  # type: ignore
    spec.loader.exec_module(module)  # type: ignore
    return module


#####################
# Main flags/config #
#####################


def pytest_configure(config):
    config.addinivalue_line("markers", "manual: test intented to run manually")


def pytest_collection_modifyitems(config, items):
    if config.option.keyword or config.option.markexpr:
        return  # let pytest handle this

    for item in items:
        if "manual" not in item.keywords:
            continue
        item.add_marker(pytest.mark.skip(reason="manual not selected"))
