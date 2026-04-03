from __future__ import annotations

import json
import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from maya_anim_workflow_tools_live_ui_smoke import ensure_bridge, run_bridge_exec_python  # noqa: E402


def main() -> int:
    ensure_bridge()

    code = """
import importlib
import os
import sys
import traceback

from maya import cmds, mel

repo_path = r"__REPO_PATH__"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya_tutorial_authoring
    importlib.reload(maya_tutorial_authoring)

    button_name = maya_tutorial_authoring.install_maya_tutorial_authoring_shelf_button()

    shelf_top_level = mel.eval("$tmpVar=$gShelfTopLevel")
    child_names = cmds.shelfTabLayout(shelf_top_level, query=True, childArray=True) or []
    tab_labels = cmds.shelfTabLayout(shelf_top_level, query=True, tabLabel=True) or []
    shelf_layout = ""
    shelf_label = ""
    for index, child_name in enumerate(child_names):
        visible_label = tab_labels[index] if index < len(tab_labels) else child_name
        if visible_label == "Amir's Scripts" or child_name == "Amir_s_Scripts":
            shelf_layout = child_name
            shelf_label = visible_label
            break

    selected_tab = cmds.shelfTabLayout(shelf_top_level, query=True, selectTab=True)
    buttons = cmds.shelfLayout(shelf_layout, query=True, childArray=True) or []
    matching_button = ""
    matching_label = ""
    matching_doc_tag = ""
    for child in buttons:
        if not cmds.control(child, exists=True):
            continue
        try:
            doc_tag = cmds.shelfButton(child, query=True, docTag=True)
        except Exception:
            doc_tag = ""
        if doc_tag != maya_tutorial_authoring.SHELF_BUTTON_DOC_TAG:
            continue
        matching_button = child
        matching_label = cmds.shelfButton(child, query=True, label=True) or ""
        matching_doc_tag = doc_tag
        break

    shelf_dir = cmds.internalVar(userShelfDir=True)
    shelf_file_path = os.path.join(shelf_dir, "shelf_" + shelf_layout + ".mel")

    result = {
        "ok": True,
        "button_name": button_name,
        "shelf_layout": shelf_layout,
        "shelf_label": shelf_label,
        "selected_tab": selected_tab,
        "matching_button": matching_button,
        "matching_label": matching_label,
        "matching_doc_tag": matching_doc_tag,
        "shelf_file_path": shelf_file_path,
    }
except Exception:
    result = {
        "ok": False,
        "traceback": traceback.format_exc(),
    }
""".replace("__REPO_PATH__", str(REPO_ROOT).replace("\\", "\\\\"))

    payload = run_bridge_exec_python(code, timeout=120)
    result = payload.get("result") or {}
    if not result.get("ok"):
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("shelf_layout") != "Amir_s_Scripts":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("shelf_label") != "Amir's Scripts":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("selected_tab") != "Amir_s_Scripts":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("matching_label") != "Tutorials":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("matching_doc_tag") != "mayaTutorialAuthoringShelfButton":
        raise AssertionError(json.dumps(result, indent=2))
    if not result.get("matching_button"):
        raise AssertionError(json.dumps(result, indent=2))
    shelf_file_path = pathlib.Path(result.get("shelf_file_path") or "")
    if not shelf_file_path.exists():
        raise AssertionError(json.dumps(result, indent=2))

    print("MAYA_TUTORIAL_AUTHORING_SHELF_INSTALL_VERIFY: PASS")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
