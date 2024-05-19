from __future__ import annotations
import logging
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
        log.debug("found key %s: %s", key, gdata[key])
    if missing:
        raise RuntimeError(f"missing keys: {', '.join(missing)}")
