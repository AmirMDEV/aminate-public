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
import time
import traceback

repo_path = r"__REPO_PATH__"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya.cmds as cmds
    import maya_anim_workflow_tools
    import maya_timeline_notes

    importlib.reload(maya_timeline_notes)
    importlib.reload(maya_anim_workflow_tools)

    cmds.playbackOptions(minTime=1, maxTime=24, animationStartTime=1, animationEndTime=24)
    window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(initial_tab="timeline")
    panel = window.timeline_panel
    for existing_note in panel.controller.notes():
        panel.controller.delete_note(existing_note["node"])
    panel._refresh_notes()
    marking_menu_actions = [action.text() for action in panel.marking_menu.actions() if not action.isSeparator()]
    fake_range = {"value": (7, 14)}
    original_selected_time_range = maya_timeline_notes._selected_time_range

    def fake_selected_time_range():
        return fake_range["value"]

    maya_timeline_notes._selected_time_range = fake_selected_time_range
    panel.auto_highlight_range_check.setChecked(True)
    panel._sync_highlighted_range_if_needed(force=True, announce=True)
    first_range = (panel.start_spin.value(), panel.end_spin.value())

    fake_range["value"] = (10, 18)
    panel._sync_highlighted_range_if_needed()
    second_range = (panel.start_spin.value(), panel.end_spin.value())

    panel._use_playback_range()
    playback_range = (panel.start_spin.value(), panel.end_spin.value())
    auto_checked_after_playback = panel.auto_highlight_range_check.isChecked()

    fake_range["value"] = (3, 6)
    panel.auto_highlight_range_check.setChecked(True)
    panel._sync_highlighted_range_if_needed(force=True, announce=True)
    third_range = (panel.start_spin.value(), panel.end_spin.value())

    panel.title_line.setText("Auto Update Test")
    panel.note_text.setPlainText("Before auto update")
    panel._add_note()
    if panel.notes_list.topLevelItemCount() < 1:
        raise RuntimeError("No timeline note was added for the auto-update test.")
    created_item = panel.notes_list.topLevelItem(panel.notes_list.topLevelItemCount() - 1)
    panel.notes_list.setCurrentItem(created_item)
    panel.auto_update_note_check.setChecked(True)
    panel.title_line.setText("Auto Update Changed")
    panel.note_text.setPlainText("Saved from auto update")
    fake_range["value"] = (12, 17)
    panel._sync_highlighted_range_if_needed(force=True, announce=False)
    if maya_timeline_notes.QtWidgets and maya_timeline_notes.QtWidgets.QApplication.instance():
        maya_timeline_notes.QtWidgets.QApplication.processEvents()
    time.sleep(0.4)
    if maya_timeline_notes.QtWidgets and maya_timeline_notes.QtWidgets.QApplication.instance():
        maya_timeline_notes.QtWidgets.QApplication.processEvents()
    note_after_auto = next((item for item in panel.controller.notes() if item["node"] == panel._selected_node()), None)
    if not note_after_auto:
        raise RuntimeError("Could not read back the picked note after auto update.")

    cmds.currentTime(13, edit=True)
    panel._refresh_current_frame_notes(force=True)
    note_reader_inside = panel.current_frame_notes_box.toPlainText()
    tooltip_html = panel.controller.tooltip_html(note_after_auto)

    cmds.currentTime(2, edit=True)
    panel._refresh_current_frame_notes(force=True)
    note_reader_outside = panel.current_frame_notes_box.toPlainText()

    screenshot_path = os.path.join(repo_path, "timeline_notes_auto_range_ui.png")
    window.tab_widget.setCurrentWidget(window.timeline_tab)
    if maya_timeline_notes.QtWidgets and maya_timeline_notes.QtWidgets.QApplication.instance():
        maya_timeline_notes.QtWidgets.QApplication.processEvents()
    window.grab().save(screenshot_path)

    maya_timeline_notes._selected_time_range = original_selected_time_range
    result = {
        "ok": True,
        "checkbox_text": panel.auto_highlight_range_check.text(),
        "first_range": first_range,
        "second_range": second_range,
        "playback_range": playback_range,
        "auto_checked_after_playback": auto_checked_after_playback,
        "third_range": third_range,
        "auto_update_checkbox_text": panel.auto_update_note_check.text(),
        "auto_update_checkbox_checked": panel.auto_update_note_check.isChecked(),
        "marking_menu_text": panel.marking_menu_button.text(),
        "marking_menu_actions": marking_menu_actions,
        "auto_updated_title": note_after_auto["title"],
        "auto_updated_range": (note_after_auto["start_frame"], note_after_auto["end_frame"]),
        "auto_updated_text": note_after_auto["text"],
        "tooltip_html": tooltip_html,
        "current_frame_label": panel.current_frame_notes_label.text(),
        "note_reader_inside": note_reader_inside,
        "note_reader_outside": note_reader_outside,
        "status_text": panel.status_label.text(),
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
    if result.get("checkbox_text") != "Auto Use Highlighted Range":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_update_checkbox_text") != "Auto Update Picked Note":
        raise AssertionError(json.dumps(result, indent=2))
    if not result.get("auto_update_checkbox_checked"):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("marking_menu_text") != "Marking Menu":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("marking_menu_actions") != [
        "Add Note",
        "Update Picked Note",
        "Delete Picked Note",
        "Use Playback Range",
        "Pick Color",
        "Auto Use Highlighted Range",
        "Auto Update Picked Note",
        "Export Notes",
        "Import Notes",
    ]:
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("current_frame_label") != "Notes At Current Frame":
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("first_range") or ()) != (7, 14):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("second_range") or ()) != (10, 18):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("playback_range") or ()) != (1, 24):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_checked_after_playback"):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("third_range") or ()) != (3, 6):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_updated_title") != "Auto Update Changed":
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("auto_updated_range") or ()) != (12, 17):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_updated_text") != "Saved from auto update":
        raise AssertionError(json.dumps(result, indent=2))
    if "Saved from auto update" not in (result.get("tooltip_html") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "Title: Auto Update Changed" not in (result.get("tooltip_html") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if (result.get("tooltip_html") or "").index("Saved from auto update") > (result.get("tooltip_html") or "").index("Title: Auto Update Changed"):
        raise AssertionError(json.dumps(result, indent=2))
    if "Frame 13" not in (result.get("note_reader_inside") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "Auto Update Changed (12-17)" not in (result.get("note_reader_inside") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "Saved from auto update" not in (result.get("note_reader_inside") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "Frame 2" not in (result.get("note_reader_outside") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "No note at this frame yet." not in (result.get("note_reader_outside") or ""):
        raise AssertionError(json.dumps(result, indent=2))

    print("MAYA_TIMELINE_NOTES_LIVE_VERIFY: PASS")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
