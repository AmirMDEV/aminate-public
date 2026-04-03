from __future__ import annotations

import json
import pathlib
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent
BROKER = REPO_ROOT.parent / "codex-desktop-broker" / "broker.py"


def run_broker(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(BROKER), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if not completed.stdout.strip():
        raise RuntimeError("Broker did not produce JSON output: {0}".format(completed.stderr))
    payload = json.loads(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    run_broker(
        "app-command",
        "run",
        "--app",
        "maya",
        "--command",
        "capture_status",
        "--ensure-bridge",
        "--allow-foreground-bootstrap",
    )

    code = """
import importlib
import os
import sys
import traceback

from maya import cmds, mel

repo_path = r"{repo_path}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya_rotation_doctor
    importlib.reload(maya_rotation_doctor)
    button_name = maya_rotation_doctor.install_maya_rotation_doctor_shelf_button()

    shelf_top_level = mel.eval("$tmpVar=$gShelfTopLevel")
    child_names = cmds.shelfTabLayout(shelf_top_level, query=True, childArray=True) or []
    tab_labels = cmds.shelfTabLayout(shelf_top_level, query=True, tabLabel=True) or []
    shelf_layout = ""
    shelf_label = ""
    internal_name = "Amir_s_Scripts"
    for index, child_name in enumerate(child_names):
        visible_label = tab_labels[index] if index < len(tab_labels) else child_name
        if (
            visible_label == maya_rotation_doctor.DEFAULT_SHELF_NAME
            or child_name == maya_rotation_doctor.DEFAULT_SHELF_NAME
            or visible_label == internal_name
            or child_name == internal_name
        ):
            shelf_layout = child_name
            shelf_label = visible_label
            break

    selected_tab = cmds.shelfTabLayout(shelf_top_level, query=True, selectTab=True)
    buttons = cmds.shelfLayout(shelf_layout, query=True, childArray=True) or []
    matching_button = ""
    matching_label = ""
    for child in buttons:
        if not cmds.control(child, exists=True):
            continue
        try:
            doc_tag = cmds.shelfButton(child, query=True, docTag=True)
        except Exception:
            doc_tag = ""
        if doc_tag != maya_rotation_doctor.SHELF_BUTTON_DOC_TAG:
            continue
        matching_button = child
        matching_label = cmds.shelfButton(child, query=True, label=True) or ""
        break

    shelf_dir = cmds.internalVar(userShelfDir=True)
    shelf_file_path = os.path.join("{{0}}".format(shelf_dir), "shelf_{{0}}.mel".format(shelf_layout))

    result = {{
        "ok": True,
        "button_name": button_name,
        "shelf_layout": shelf_layout,
        "selected_tab": selected_tab,
        "shelf_label": shelf_label,
        "matching_button": matching_button,
        "matching_label": matching_label,
        "shelf_file_path": shelf_file_path,
        "shelf_file_exists": os.path.exists(shelf_file_path),
    }}
except Exception:
    result = {{
        "ok": False,
        "traceback": traceback.format_exc(),
    }}
""".format(repo_path=str(REPO_ROOT).replace("\\", "\\\\"))

    payload = run_broker(
        "app-command",
        "run",
        "--app",
        "maya",
        "--command",
        "exec_python",
        "--ensure-bridge",
        "--allow-foreground-bootstrap",
        "--args-json",
        json.dumps({"code": code}),
    )
    if not payload.get("ok"):
        raise AssertionError(json.dumps(payload, indent=2))

    result = (payload.get("data") or {}).get("result") or {}
    if not result.get("ok"):
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("shelf_layout") != "Amir_s_Scripts":
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("shelf_label") != "Amir's Scripts":
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("selected_tab") != "Amir_s_Scripts":
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("matching_label") != "Rotation Doctor":
        raise AssertionError(json.dumps(payload, indent=2))
    if not result.get("matching_button"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not result.get("shelf_file_exists"):
        raise AssertionError(json.dumps(payload, indent=2))

    print("MAYA_ROTATION_DOCTOR_SHELF_INSTALL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
