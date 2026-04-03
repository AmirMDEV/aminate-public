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
    import maya_tutorial_authoring
    import maya.cmds as cmds

    importlib.reload(maya_tutorial_authoring)

    window = maya_tutorial_authoring.launch_maya_tutorial_authoring(mode=maya_tutorial_authoring.PLAYBACK_MODE_AUTHOR)
    initial_workspace_exists = bool(cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, exists=True))
    initial_floating = bool(cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, query=True, floating=True)) if initial_workspace_exists else None
    lesson = window.controller.create_lesson("UI Smoke Lesson")
    window.current_lesson_id = lesson["id"]
    window._refresh_lessons()
    window._use_timeline_target()
    timeline_highlight = window._highlight_step_target(
        {
            "student_text": "Timeline target",
            "target": {"type": "timeline_slider", "label": "Timeline Slider"},
        }
    )

    button_name = maya_tutorial_authoring.install_maya_tutorial_authoring_shelf_button()
    shelf_highlight = window._highlight_step_target(
        {
            "student_text": "Shelf button target",
            "target": {
                "type": "shelf_button",
                "label": "Tutorials",
                "doc_tag": maya_tutorial_authoring.SHELF_BUTTON_DOC_TAG,
            },
        }
    )

    preferred = ["Windows", "Display", "Edit", "File", "Mesh", "Select", "Create", "Modify", "Animation"]
    chosen_menu_name = ""
    chosen_menu_label = ""
    for menu_name in cmds.lsUI(menus=True) or []:
        try:
            label = maya_tutorial_authoring._normalize_text(cmds.menu(menu_name, query=True, label=True) or "")
        except Exception:
            label = ""
        if label not in preferred:
            continue
        chosen_menu_name = menu_name
        chosen_menu_label = label
        break
    menu_highlight = window._highlight_step_target(
        {
            "student_text": "Menu target",
            "target": {
                "type": "control_name",
                "label": chosen_menu_label,
                "control_name": chosen_menu_name,
            },
        }
    )
    missing_highlight = window._highlight_step_target(
        {
            "student_text": "Missing target",
            "target": {
                "type": "control_name",
                "label": "Definitely Missing Maya Widget",
                "control_name": "missingMayaTutorialControl",
            },
        }
    )

    auto_ball = cmds.createNode("transform", name="uiSmokeRecorderBall_CTRL")
    cmds.autoKeyframe(state=False)
    cmds.select(clear=True)
    cmds.currentTime(1, edit=True)
    window._start_auto_recording()
    window.auto_recorder.note_target({"type": "timeline_slider", "label": "Timeline Slider", "control_name": maya_tutorial_authoring._playback_slider_name()})
    cmds.currentTime(6, edit=True)
    frame_recorded = window.auto_recorder.poll_once(force=True)
    window.auto_recorder.note_target({"type": "control_name", "label": "Auto Key", "control_name": "autoKeyButton"})
    cmds.autoKeyframe(state=True)
    auto_key_recorded = window.auto_recorder.poll_once(force=True)
    cmds.select([auto_ball], replace=True)
    selection_recorded = window.auto_recorder.poll_once(force=True)
    cmds.setAttr(auto_ball + ".translateY", 2.5)
    cmds.setKeyframe(auto_ball, attribute="translateY", time=6, value=2.5)
    keyframe_recorded = window.auto_recorder.poll_once(force=True)
    auto_record_lesson = window._current_lesson() or {}
    auto_record_steps = auto_record_lesson.get("steps") or []
    auto_record_step_kinds = [step.get("kind") for step in auto_record_steps]
    window._stop_auto_recording()

    screenshot_path = os.path.join(repo_path, "maya_tutorial_authoring_ui.png")
    window.grab().save(screenshot_path)

    result = {
        "ok": True,
        "window_title": window.windowTitle(),
        "initial_launch_result": {
            "workspace_exists": initial_workspace_exists,
            "floating": initial_floating,
        },
        "mode_items": [window.mode_combo.itemText(index) for index in range(window.mode_combo.count())],
        "author_tabs": [window.author_tools_tabs.tabText(index) for index in range(window.author_tools_tabs.count())],
        "new_lesson_text": window.new_lesson_button.text(),
        "save_lesson_text": window.save_lesson_button.text(),
        "more_actions_text": window.more_actions_button.text(),
        "more_action_items": [action.text() for action in window.more_actions_menu.actions() if action.text()],
        "auto_record_text": window.start_auto_record_button.text(),
        "stop_record_text": window.stop_auto_record_button.text(),
        "start_record_text": window.start_record_button.text(),
        "finish_record_text": window.finish_record_button.text(),
        "pick_target_text": window.pick_target_button.text(),
        "add_ui_callout_text": window.add_ui_callout_button.text(),
        "guided_prepare_text": window.guided_prepare_button.text(),
        "guided_check_text": window.guided_check_button.text(),
        "guided_do_it_text": window.guided_do_it_button.text(),
        "show_me_text": window.player_show_me_button.text(),
        "check_step_text": window.player_check_button.text(),
        "pose_compare_snapshot_text": window.pose_compare_snapshot_button.text(),
        "pose_compare_begin_text": window.pose_compare_begin_button.text(),
        "pose_compare_finish_text": window.pose_compare_finish_button.text(),
        "pose_compare_cancel_text": window.pose_compare_cancel_button.text(),
        "target_summary": window.target_summary_label.text(),
        "timeline_highlight": timeline_highlight,
        "shelf_button_name": button_name,
        "shelf_highlight": shelf_highlight,
        "chosen_menu_name": chosen_menu_name,
        "chosen_menu_label": chosen_menu_label,
        "menu_highlight": menu_highlight,
        "missing_highlight": missing_highlight,
        "brand_text": window.brand_label.text(),
        "donate_tooltip": window.donate_button.toolTip(),
        "donate_style": window.donate_button.styleSheet(),
        "recording_summary_text": window.recording_summary_label.text(),
        "auto_record_step_kinds": auto_record_step_kinds,
        "auto_record_results": [frame_recorded, auto_key_recorded, selection_recorded, keyframe_recorded],
        "screenshot_path": screenshot_path,
    }
    window._float_window()
    result["float_result"] = {
        "workspace_exists": bool(cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, exists=True)),
        "floating": bool(cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, query=True, floating=True)),
        "mode_text": window.mode_combo.currentText(),
    }
    window._dock_window_right()
    result["dock_result"] = {
        "workspace_exists": bool(cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, exists=True)),
        "floating": bool(cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, query=True, floating=True)),
        "mode_text": window.mode_combo.currentText(),
    }
    try:
        window.close()
    except Exception:
        pass
    try:
        if cmds.workspaceControl(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, exists=True):
            cmds.deleteUI(maya_tutorial_authoring.WORKSPACE_CONTROL_NAME, control=True)
    except Exception:
        pass
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
    if result.get("window_title") != "Maya Tutorial Authoring":
        raise AssertionError(json.dumps(result, indent=2))
    initial_launch = result.get("initial_launch_result") or {}
    if not initial_launch.get("workspace_exists"):
        raise AssertionError(json.dumps(result, indent=2))
    if initial_launch.get("floating") not in (True, False):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("mode_items") != ["Author", "Practice", "Watch", "Compare"]:
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("author_tabs") != ["Record", "Advanced", "Edit"]:
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("new_lesson_text") != "New":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("save_lesson_text") != "Save":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("more_actions_text") != "More":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("more_action_items") != ["Delete Lesson", "Dock Right", "Float Window"]:
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_record_text") != "Auto Record":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("stop_record_text") != "Stop Recorder":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("start_record_text") != "Start Capture":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("finish_record_text") != "Finish Step":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pick_target_text") != "Pick Under Mouse":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("add_ui_callout_text") != "Save Callout":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("guided_prepare_text") != "Prepare":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("guided_check_text") != "Check":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("guided_do_it_text") != "Do It":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("show_me_text") != "Show Me":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("check_step_text") != "Check":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pose_compare_snapshot_text") != "Snapshot":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pose_compare_begin_text") != "Start Capture":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pose_compare_finish_text") != "Finish Capture":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("pose_compare_cancel_text") != "Cancel":
        raise AssertionError(json.dumps(result, indent=2))
    if "Timeline Slider" not in (result.get("target_summary") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("timeline_highlight") or ())[:1] != (True,):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("shelf_highlight") or ())[:1] != (True,):
        raise AssertionError(json.dumps(result, indent=2))
    if not result.get("chosen_menu_name"):
        raise AssertionError(json.dumps(result, indent=2))
    if not result.get("chosen_menu_label"):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("menu_highlight") or ())[:1] != (True,):
        raise AssertionError(json.dumps(result, indent=2))
    if tuple(result.get("missing_highlight") or ())[:1] != (False,):
        raise AssertionError(json.dumps(result, indent=2))
    if "followamir.com" not in (result.get("brand_text") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "AMIR_PAYPAL_DONATE_URL" not in (result.get("donate_tooltip") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if "#FFC439" not in (result.get("donate_style") or ""):
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("recording_summary_text") != "Recorder: idle. Captured 4 steps.":
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_record_step_kinds") != ["frame_change", "auto_key_toggle", "selection_change", "keyframe_change"]:
        raise AssertionError(json.dumps(result, indent=2))
    if result.get("auto_record_results") != [True, True, True, True]:
        raise AssertionError(json.dumps(result, indent=2))
    float_result = result.get("float_result") or {}
    if not float_result.get("workspace_exists"):
        raise AssertionError(json.dumps(result, indent=2))
    if not float_result.get("floating"):
        raise AssertionError(json.dumps(result, indent=2))
    if float_result.get("mode_text") != "Author":
        raise AssertionError(json.dumps(result, indent=2))
    dock_result = result.get("dock_result") or {}
    if not dock_result.get("workspace_exists"):
        raise AssertionError(json.dumps(result, indent=2))
    if dock_result.get("floating"):
        raise AssertionError(json.dumps(result, indent=2))
    if dock_result.get("mode_text") != "Author":
        raise AssertionError(json.dumps(result, indent=2))

    print("MAYA_TUTORIAL_AUTHORING_LIVE_UI_SMOKE: PASS")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
