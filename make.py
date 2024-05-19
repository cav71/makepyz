from __future__ import annotations

import logging
import os
import argparse
import json
import contextlib
from pathlib import Path
from makepyz import api


log = logging.getLogger(__name__)


@api.task()
def info(arguments: list[str]):
    print("arguments.")
    for argument in arguments:
        print(f"  {argument}")


@api.task()
def build(arguments: list[str]):
    """create beta packages for luxos (only works in github)"""

    if not arguments or arguments[0] not in {"release", "beta"}:
        raise api.AbortWrongArgumentError(f"first argument must be release|test, found {arguments}")


    github_dump = os.getenv("GITHUB_DUMP")
    if not github_dump:
        raise RuntimeError("missing GITHUB_DUMP variable")

    gdata = (
        json.loads(Path(github_dump[1:]).read_text())
        if github_dump.startswith("@")
        else json.loads(github_dump)
    )
    api.github.validate_gdata(
        gdata, ["run_number", "sha", "ref_name", "ref_type", "workflow_ref"]
    )

    # with contextlib.ExitStack() as stack:
    #     save = stack.enter_context(fileos.backups())
    #
    #     # pyproject.toml
    #     pyproject = save("pyproject.toml")
    #     lineno, current, quote = misc.get_variable_def(pyproject, "version")
    #     log.debug("found at LN:%i: version = '%s'", lineno, current)
    #     version = current if options.release else f"{current}b{gdata['run_number']}"
    #
    #     log.info("creating for version %s [%s]", version, gdata["sha"])
    #     misc.set_variable_def(pyproject, "version", lineno, version, quote)
    #
    #     # __init__.py
    #     initfile = save("src/luxos/__init__.py")
    #     lineno, old, quote = misc.get_variable_def(initfile, "__version__")
    #     log.debug("found at LN:%i: __version__ = '%s'", lineno, old)
    #     if old != "" and old != current:
    #         raise RuntimeError(f"found in {initfile} __version__ {old} != {current}")
    #     misc.set_variable_def(initfile, "__version__", lineno, version, quote)
    #
    #     lineno, old, quote = misc.get_variable_def(initfile, "__hash__")
    #     log.debug("found at LN:%i: __hash__ = '%s'", lineno, old)
    #     if old != "" and old != gdata["sha"]:
    #         raise RuntimeError(f"found in {initfile} __hash__ {old} != {gdata['sha']}")
    #     misc.set_variable_def(initfile, "__hash__", lineno, gdata["sha"], quote)
    #
    #     if not options.dryrun:
    #         subprocess.check_call([sys.executable, "-m", "build"])  # noqa: S603
