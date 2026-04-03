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

repo_path = r"__REPO_PATH__"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya.cmds as cmds
    import maya_anim_workflow_tools
    import maya_dynamic_parent_pivot

    importlib.reload(maya_anim_workflow_tools)
    importlib.reload(maya_dynamic_parent_pivot)

    window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(initial_tab="parenting")
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    if cmds.objExists("|dynamicParentingReloadVerify_GRP"):
        cmds.delete("|dynamicParentingReloadVerify_GRP")

    verify_group = cmds.createNode("transform", name="dynamicParentingReloadVerify_GRP")

    def make_marker(name, parent, translation, color_index):
        node = cmds.createNode("transform", name=name, parent=parent)
        cmds.xform(node, worldSpace=True, translation=translation)
        marker = cmds.polyCube(name=name.replace("_CTRL", "_GEO"), width=0.8, height=0.8, depth=0.8, constructionHistory=False)[0]
        marker = cmds.parent(marker, node)[0]
        cmds.setAttr(marker + ".translateY", 0.4)
        shapes = cmds.listRelatives(marker, shapes=True, fullPath=True) or []
        for shape in shapes:
            cmds.setAttr(shape + ".overrideEnabled", 1)
            cmds.setAttr(shape + ".overrideColor", color_index)
        return node

    mag = make_marker("reloadMag_CTRL", verify_group, (0.0, 0.0, 0.0), 17)
    hand = make_marker("reloadHand_CTRL", verify_group, (4.0, 1.5, 0.0), 6)
    gun = make_marker("reloadGun_CTRL", verify_group, (8.0, 2.0, -1.0), 13)

    cmds.currentTime(1, edit=True)
    cmds.select([mag], replace=True)
    window._create_temp_controls()

    cmds.select([mag, hand], replace=True)
    window._pickup_here()
    first_summary = window.parenting_summary.toPlainText()
    first_status = window.status_label.text()
    first_driver_line = window.driver_line.text()
    first_setup = window.controller.parenting_setups(from_selection=False)[0]

    cmds.currentTime(6, edit=True)
    before_switch = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    cmds.select([mag, gun], replace=True)
    window._pass_here()
    after_switch = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    second_summary = window.parenting_summary.toPlainText()
    second_status = window.status_label.text()
    second_driver_line = window.driver_line.text()
    second_setup = window.controller.parenting_setups(from_selection=False)[0]

    cmds.currentTime(9, edit=True)
    cmds.select([mag], replace=True)
    window.release_combo.setCurrentText("World")
    window._drop_here()
    release_summary = window.parenting_summary.toPlainText()
    release_status = window.status_label.text()
    event_items = [window.parenting_event_list.item(index).text() for index in range(window.parenting_event_list.count())]
    window.parenting_event_list.setCurrentRow(1)
    window._jump_to_selected_parenting_event()
    jumped_frame = float(cmds.currentTime(query=True))

    window.tab_widget.setCurrentWidget(window.parenting_tab)
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    screenshot_path = os.path.join(repo_path, "dynamic_parenting_reload_ui.png")
    window.grab().save(screenshot_path)

    result = {
        "ok": True,
        "create_text": window.create_temp_button.text(),
        "target_text": window.use_driver_button.text(),
        "grab_text": window.add_grab_button.text(),
        "fix_text": window.normalize_button.text(),
        "pickup_text": window.pickup_button.text(),
        "pass_text": window.pass_button.text(),
        "drop_text": window.drop_button.text(),
        "first_driver": first_setup.get("current_driver", ""),
        "first_driver_line": first_driver_line,
        "first_status": first_status,
        "first_summary": first_summary,
        "second_driver": second_setup.get("current_driver", ""),
        "second_driver_line": second_driver_line,
        "second_status": second_status,
        "second_summary": second_summary,
        "release_status": release_status,
        "release_summary": release_summary,
        "event_items": event_items,
        "jumped_frame": jumped_frame,
        "before_switch": before_switch,
        "after_switch": after_switch,
        "screenshot_path": screenshot_path,
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

    if result.get("create_text") != "Make Helpers":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("target_text") != "Use Picked Hand / Object":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("grab_text") != "Swap Here":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("fix_text") != "Fix Jump Here":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pickup_text") != "Pickup":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pass_text") != "Pass":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("drop_text") != "Drop":
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadHand_CTRL" not in (result.get("first_driver") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("first_driver_line") != "reloadHand_CTRL":
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadHand_CTRL" not in (result.get("first_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadGun_CTRL" not in (result.get("second_driver") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("second_driver_line") != "reloadGun_CTRL":
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadGun_CTRL" not in (result.get("second_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "free in world space" not in (result.get("release_summary") or "").lower():
        raise AssertionError(json.dumps(result, indent=2))
    event_items = result.get("event_items") or []
    if len(event_items) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if "Pickup reloadMag_CTRL -> reloadHand_CTRL" not in event_items[0]:
        raise AssertionError(json.dumps(result, indent=2))
    if "Pass reloadMag_CTRL -> reloadGun_CTRL" not in event_items[1]:
        raise AssertionError(json.dumps(result, indent=2))
    if "Drop reloadMag_CTRL -> world" not in event_items[2]:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(result.get("jumped_frame", 0.0)) - 6.0) > 0.01:
        raise AssertionError(json.dumps(result, indent=2))

    before_switch = result.get("before_switch") or []
    after_switch = result.get("after_switch") or []
    if len(before_switch) != 3 or len(after_switch) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(before_switch[index]) - float(after_switch[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))

    print("MAYA_DYNAMIC_PARENTING_LIVE_VERIFY: PASS")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
