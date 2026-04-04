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
    import maya_dynamic_parenting_tool
    import maya_dynamic_parent_pivot

    importlib.reload(maya_anim_workflow_tools)
    importlib.reload(maya_dynamic_parenting_tool)
    importlib.reload(maya_dynamic_parent_pivot)

    window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(initial_tab="parenting")
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()
    panel = window.parenting_panel

    if cmds.objExists("|dynamicParentingReloadVerify_GRP"):
        cmds.delete("|dynamicParentingReloadVerify_GRP")
    if cmds.objExists("|" + maya_dynamic_parenting_tool.ROOT_GROUP_NAME):
        cmds.delete("|" + maya_dynamic_parenting_tool.ROOT_GROUP_NAME)

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
    before_add = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    panel._add_object()
    after_add = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    start_in_place_text = panel.start_in_place_check.text()
    start_in_place_checked = panel.start_in_place_check.isChecked()
    initial_scale = cmds.xform(mag, query=True, relative=True, scale=True)

    cmds.select([hand], replace=True)
    panel._use_target()
    parent_only_pick_status = panel.status_label.text()

    cmds.select([mag, hand], replace=True)
    panel._use_target()
    first_pick_status = panel.status_label.text()
    before_first_switch = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    panel._parent_to_picked_target()
    after_first_switch = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    first_summary = panel.summary_box.toPlainText()
    first_status = panel.status_label.text()
    first_driver_line = panel.target_line.text()
    first_setup = panel.controller.current_setup()
    first_blend_values = maya_dynamic_parenting_tool._get_blend_attr_values(mag)

    cmds.currentTime(6, edit=True)
    cmds.select([mag, gun], replace=True)
    panel._use_target()
    second_pick_status = panel.status_label.text()
    panel._snap_to_picked_target()
    snap_status = panel.status_label.text()
    snapped_position = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    snapped_scale = cmds.xform(mag, query=True, relative=True, scale=True)
    cmds.xform(mag, worldSpace=True, translation=(8.75, 2.4, -0.35))
    placed_position_before_switch = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    panel._parent_to_picked_target()
    after_switch = cmds.xform(mag, query=True, worldSpace=True, translation=True)
    after_switch_scale = cmds.xform(mag, query=True, relative=True, scale=True)
    second_summary = panel.summary_box.toPlainText()
    second_status = panel.status_label.text()
    second_driver_line = panel.target_line.text()
    second_setup = panel.controller.current_setup()
    second_blend_values = maya_dynamic_parenting_tool._get_blend_attr_values(mag)

    cmds.currentTime(8, edit=True)
    setup_after_switch = panel.controller.current_setup()
    target_lookup = {target["label"]: target["id"] for target in setup_after_switch.get("targets") or []}
    for target_id, spin_box in panel._weight_widgets.items():
        if target_id == target_lookup.get("World"):
            spin_box.setValue(0.5)
        elif target_id == target_lookup.get("reloadGun_CTRL"):
            spin_box.setValue(0.5)
        else:
            spin_box.setValue(0.0)
    panel._apply_weights()
    blend_summary = panel.summary_box.toPlainText()
    blend_status = panel.status_label.text()

    cmds.currentTime(10, edit=True)
    panel._parent_to_world()
    release_summary = panel.summary_box.toPlainText()
    release_status = panel.status_label.text()
    event_items = [panel.event_list.item(index).text() for index in range(panel.event_list.count())]
    panel.event_list.setCurrentRow(1)
    panel._jump_to_event()
    jumped_frame = float(cmds.currentTime(query=True))
    panel.event_list.setCurrentRow(1)
    panel._delete_event()
    delete_status = panel.status_label.text()
    event_items_after_delete = [panel.event_list.item(index).text() for index in range(panel.event_list.count())]
    panel._clear_events()
    clear_status = panel.status_label.text()
    event_count_after_clear = panel.event_list.count()

    remove_warning_called = {"value": False}
    original_question = maya_dynamic_parenting_tool.QtWidgets.QMessageBox.question

    def fake_question(*_args, **_kwargs):
        remove_warning_called["value"] = True
        return maya_dynamic_parenting_tool.QtWidgets.QMessageBox.Yes

    maya_dynamic_parenting_tool.QtWidgets.QMessageBox.question = fake_question
    try:
        panel._remove_object()
    finally:
        maya_dynamic_parenting_tool.QtWidgets.QMessageBox.question = original_question
    remove_status = panel.status_label.text()
    object_count_after_remove = panel.object_list.count()

    cmds.select([mag], replace=True)
    panel._add_object()
    readd_status = panel.status_label.text()
    object_count_after_readd = panel.object_list.count()

    window.tab_widget.setCurrentWidget(window.parenting_tab)
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    screenshot_path = os.path.join(repo_path, "dynamic_parenting_reload_ui.png")
    window.grab().save(screenshot_path)

    result = {
        "ok": True,
        "add_object_text": panel.add_object_button.text(),
        "before_add": before_add,
        "after_add": after_add,
        "start_in_place_text": start_in_place_text,
        "start_in_place_checked": start_in_place_checked,
        "parent_only_pick_status": parent_only_pick_status,
        "pick_parent_text": panel.use_target_button.text(),
        "snap_text": panel.snap_to_picked_button.text(),
        "parent_to_picked_text": panel.parent_to_picked_button.text(),
        "save_parent_text": panel.add_target_button.text(),
        "row_switch_text": panel.parent_to_row_button.text(),
        "world_text": panel.parent_to_world_button.text(),
        "blend_text": panel.apply_weights_button.text(),
        "fix_text": panel.fix_pop_button.text(),
        "jump_text": panel.jump_button.text(),
        "delete_text": panel.delete_switch_button.text(),
        "clear_text": panel.clear_switches_button.text(),
        "first_pick_status": first_pick_status,
        "second_pick_status": second_pick_status,
        "snap_status": snap_status,
        "snapped_position": snapped_position,
        "initial_scale": initial_scale,
        "snapped_scale": snapped_scale,
        "after_switch_scale": after_switch_scale,
        "first_driver": first_driver_line,
        "first_driver_line": first_driver_line,
        "first_status": first_status,
        "first_summary": first_summary,
        "first_blend_values": first_blend_values,
        "second_driver": second_driver_line,
        "second_driver_line": second_driver_line,
        "second_status": second_status,
        "second_summary": second_summary,
        "second_blend_values": second_blend_values,
        "blend_status": blend_status,
        "blend_summary": blend_summary,
        "release_status": release_status,
        "release_summary": release_summary,
        "event_items": event_items,
        "jumped_frame": jumped_frame,
        "delete_status": delete_status,
        "event_items_after_delete": event_items_after_delete,
        "clear_status": clear_status,
        "event_count_after_clear": event_count_after_clear,
        "remove_warning_called": remove_warning_called["value"],
        "remove_status": remove_status,
        "object_count_after_remove": object_count_after_remove,
        "readd_status": readd_status,
        "object_count_after_readd": object_count_after_readd,
        "before_first_switch": before_first_switch,
        "after_first_switch": after_first_switch,
        "placed_position_before_switch": placed_position_before_switch,
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

    if result.get("add_object_text") != "Add Object":
        raise AssertionError(json.dumps(result, indent=2))
    before_add = result.get("before_add") or []
    after_add = result.get("after_add") or []
    if len(before_add) != 3 or len(after_add) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(before_add[index]) - float(after_add[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("start_in_place_text") != "Stay In Current Position At Start?":
        raise AssertionError(json.dumps(result, indent=2))
    if not result.get("start_in_place_checked"):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pick_parent_text") != "Pick Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("snap_text") != "Snap To Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("parent_to_picked_text") != "Switch to this Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadHand_CTRL" not in (result.get("parent_only_pick_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("save_parent_text") != "Add Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("row_switch_text") != "Reparent to Selected Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("world_text") != "World":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("blend_text") != "Blend Parents":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("fix_text") != "Fix Jump Here":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("jump_text") != "Jump To Frame":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("delete_text") != "Delete Picked Switch":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("clear_text") != "Delete All Switches":
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadHand_CTRL" not in (result.get("first_pick_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadHand_CTRL" not in (result.get("first_driver") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadHand_CTRL" not in (result.get("first_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    first_blend_values = result.get("first_blend_values") or {}
    if not first_blend_values or any(abs(float(value) - 1.0) > 0.001 for value in first_blend_values.values()):
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadGun_CTRL" not in (result.get("second_pick_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "Snapped reloadMag_CTRL onto reloadGun_CTRL" not in (result.get("snap_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadGun_CTRL" not in (result.get("second_driver") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "reloadGun_CTRL" not in (result.get("second_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    second_blend_values = result.get("second_blend_values") or {}
    if not second_blend_values or any(abs(float(value) - 1.0) > 0.001 for value in second_blend_values.values()):
        raise AssertionError(json.dumps(result, indent=2))
    if "World: 0.50" not in (result.get("blend_summary") or "") or "reloadGun_CTRL: 0.50" not in (result.get("blend_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "World: 1.00" not in (result.get("release_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    event_items = result.get("event_items") or []
    if len(event_items) != 4:
        raise AssertionError(json.dumps(result, indent=2))
    if "F2: Switch -> reloadHand_CTRL 1.00" not in event_items[0]:
        raise AssertionError(json.dumps(result, indent=2))
    if "F7: Switch -> reloadGun_CTRL 1.00" not in event_items[1]:
        raise AssertionError(json.dumps(result, indent=2))
    if "F8: Blend -> World 0.50, reloadGun_CTRL 0.50" not in event_items[2]:
        raise AssertionError(json.dumps(result, indent=2))
    if "F11: World -> World 1.00" not in event_items[3]:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(result.get("jumped_frame", 0.0)) - 7.0) > 0.01:
        raise AssertionError(json.dumps(result, indent=2))
    if "Deleted the saved switch on frame 7" not in (result.get("delete_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    event_items_after_delete = result.get("event_items_after_delete") or []
    if len(event_items_after_delete) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if any("F7:" in item for item in event_items_after_delete):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("event_count_after_clear") != 0:
        raise AssertionError(json.dumps(result, indent=2))
    if "Deleted all saved switches" not in (result.get("clear_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))

    before_first_switch = result.get("before_first_switch") or []
    after_first_switch = result.get("after_first_switch") or []
    if len(before_first_switch) != 3 or len(after_first_switch) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(before_first_switch[index]) - float(after_first_switch[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))

    before_switch = result.get("placed_position_before_switch") or []
    after_switch = result.get("after_switch") or []
    if len(before_switch) != 3 or len(after_switch) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(before_switch[index]) - float(after_switch[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    snapped_position = result.get("snapped_position") or []
    if len(snapped_position) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    expected_snap = [8.0, 2.0, -1.0]
    if any(abs(float(snapped_position[index]) - expected_snap[index]) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    initial_scale = result.get("initial_scale") or []
    snapped_scale = result.get("snapped_scale") or []
    after_switch_scale = result.get("after_switch_scale") or []
    if len(initial_scale) != 3 or len(snapped_scale) != 3 or len(after_switch_scale) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(initial_scale[index]) - float(snapped_scale[index])) > 0.001 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(initial_scale[index]) - float(after_switch_scale[index])) > 0.001 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    if not result.get("remove_warning_called"):
        raise AssertionError(json.dumps(result, indent=2))
    if "Removed reloadMag_CTRL" not in (result.get("remove_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("object_count_after_remove") != 0:
        raise AssertionError(json.dumps(result, indent=2))
    if "Added reloadMag_CTRL" not in (result.get("readd_status") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("object_count_after_readd") != 1:
        raise AssertionError(json.dumps(result, indent=2))

    print("MAYA_DYNAMIC_PARENTING_LIVE_VERIFY: PASS")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
