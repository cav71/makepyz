from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def validate_gdata(gdata: dict[str, Any], keys: list[str] | None = None):
    """validate the GITHUB json dioctionary

    Eg.
        validate_gdata(json.loads(os.getenv("GITHUB_DUMP")))

        In github workflow:
        env:
            GITHUB_DUMP: ${{ toJson(github) }}
    """
    missing = []
    keys = keys or ["run_number", "sha", "ref_name", "ref_type", "workflow_ref"]
    for key in keys:
        if key not in gdata:
            missing.append(key)
            continue
        log.debug("found key %s: %s", key, gdata[key])
    if missing:
        raise RuntimeError(f"missing keys: {', '.join(missing)}")


def get_gdata(github_dump: str) -> dict[str, Any]:
    """process the github_dump into a valid dictionary

    Eg.
        gdata = get_gdata(os.environ["GITHUB_DUMP"])

    """
    gdata = (
        json.loads(Path(github_dump[1:]).read_text())
        if github_dump.startswith("@")
        else json.loads(github_dump)
    )
    validate_gdata(gdata, ["run_number", "sha", "ref_name", "ref_type", "workflow_ref"])
    return gdata
