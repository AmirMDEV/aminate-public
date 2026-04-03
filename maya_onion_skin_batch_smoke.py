from __future__ import absolute_import, division, print_function

import json
import os
import sys
import traceback

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_PATH = os.path.join(THIS_DIR, "maya_onion_skin_batch_result.json")

if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)


def _write_result(payload):
    with open(RESULT_PATH, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def main():
    import maya_onion_skin_smoke_test as smoke_test

    payload = {"status": "fail"}
    try:
        smoke_test.run()
        payload["status"] = "pass"
    except Exception:
        payload["error"] = traceback.format_exc()
        _write_result(payload)
        raise

    _write_result(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(1)
