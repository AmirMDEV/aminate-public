from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request


REPO_ROOT = pathlib.Path(__file__).resolve().parent
BROKER = REPO_ROOT.parent / "codex-desktop-broker" / "broker.py"
BOOTSTRAP = REPO_ROOT / "maya_live_bridge_bootstrap.py"
BRIDGE_URL = "http://127.0.0.1:62225"


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


def ensure_bridge() -> None:
    try:
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
        return
    except Exception:
        completed = subprocess.run(
            [sys.executable, str(BOOTSTRAP)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "Maya bridge bootstrap failed.")
        run_broker(
            "app-command",
            "run",
            "--app",
            "maya",
            "--command",
            "capture_status",
            "--ensure-bridge",
        )


def run_bridge_exec_python(code: str, timeout: int = 120) -> dict:
    payload = json.dumps({"action": "exec_python", "args": {"code": code}}).encode("utf-8")
    request = urllib.request.Request(
        BRIDGE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(raw)

    payload = json.loads(raw)
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def main() -> int:
    ensure_bridge()

    code = """
import importlib
import sys
import traceback

repo_path = r"{repo_path}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya.cmds as cmds
    import maya_anim_workflow_tools
    import maya_universal_ikfk_switcher
    import maya_dynamic_parent_pivot
    importlib.reload(maya_anim_workflow_tools)
    importlib.reload(maya_universal_ikfk_switcher)
    importlib.reload(maya_dynamic_parent_pivot)

    main_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(initial_tab="pivot")
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    def panel_snapshot(tab_widget, target_tab, panel):
        tab_widget.setCurrentWidget(target_tab)
        if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
            maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()
        return {{
            "is_window": bool(panel.isWindow()),
            "visible_to_main": bool(panel.isVisibleTo(main_window)),
            "size": [panel.width(), panel.height()],
        }}

    contact_hold_panel_state = panel_snapshot(main_window.tab_widget, main_window.contact_hold_tab, main_window.contact_hold_panel)
    onion_panel_state = panel_snapshot(main_window.tab_widget, main_window.onion_tab, main_window.onion_panel)
    rotation_panel_state = panel_snapshot(main_window.tab_widget, main_window.rotation_tab, main_window.rotation_panel)
    skin_panel_state = panel_snapshot(main_window.tab_widget, main_window.skin_tab, main_window.skin_panel)
    rig_scale_panel_state = panel_snapshot(main_window.tab_widget, main_window.rig_scale_tab, main_window.rig_scale_panel)
    video_panel_state = panel_snapshot(main_window.tab_widget, main_window.video_tab, main_window.video_panel)
    timeline_panel_state = panel_snapshot(main_window.tab_widget, main_window.timeline_tab, main_window.timeline_panel)

    main_result = {{
        "window_title": main_window.windowTitle(),
        "minimum_size": [main_window.minimumWidth(), main_window.minimumHeight()],
        "tab_count": main_window.tab_widget.count(),
        "tabs": [main_window.tab_widget.tabText(index) for index in range(main_window.tab_widget.count())],
        "tabs_movable": main_window.tab_widget.isMovable(),
        "current_tab": main_window.tab_widget.tabText(main_window.tab_widget.currentIndex()),
        "tab_intro_count": len(main_window.tab_intro_labels),
        "parenting_intro_text": main_window.tab_intro_labels[maya_dynamic_parent_pivot.TAB_PARENTING].text(),
        "guide_intro_text": main_window.tab_intro_labels[maya_dynamic_parent_pivot.TAB_GUIDE].text(),
        "timeline_intro_text": main_window.tab_intro_labels[maya_dynamic_parent_pivot.TAB_TIMELINE].text(),
        "tabs_use_scroll_areas": all(isinstance(tab, maya_dynamic_parent_pivot.QtWidgets.QScrollArea) for tab in [
            main_window.parenting_tab,
            main_window.contact_hold_tab,
            main_window.pivot_tab,
            main_window.ikfk_tab,
            main_window.onion_tab,
            main_window.rotation_tab,
            main_window.skin_tab,
            main_window.rig_scale_tab,
            main_window.video_tab,
            main_window.timeline_tab,
            main_window.guide_tab,
        ]),
        "timeline_scroll_widget_resizable": bool(main_window.timeline_tab.widgetResizable()),
        "parenting_simple_steps_text": main_window.parenting_simple_steps_label.text(),
        "create_temp_text": main_window.create_temp_button.text(),
        "use_object_text": main_window.use_driver_button.text(),
        "grab_here_text": main_window.add_grab_button.text(),
        "release_here_text": main_window.add_release_button.text(),
        "fix_jumps_text": main_window.normalize_button.text(),
        "pickup_text": main_window.pickup_button.text(),
        "pass_text": main_window.pass_button.text(),
        "drop_text": main_window.drop_button.text(),
        "has_parenting_event_list": hasattr(main_window, "parenting_event_list"),
        "parenting_jump_text": main_window.parenting_jump_button.text(),
        "switch_fk_to_ik_text": main_window.switch_fk_to_ik_button.text(),
        "has_ik_controls_field": hasattr(main_window, "ik_controls_line"),
        "ik_controls_placeholder": main_window.ik_controls_line.placeholderText(),
        "has_contact_hold_panel": hasattr(main_window, "contact_hold_panel"),
        "contact_hold_panel_state": contact_hold_panel_state,
        "contact_hold_apply_text": main_window.contact_hold_panel.apply_button.text(),
        "contact_hold_other_side_text": main_window.contact_hold_panel.add_other_side_button.text(),
        "has_onion_panel": hasattr(main_window, "onion_panel"),
        "has_rotation_panel": hasattr(main_window, "rotation_panel"),
        "has_skin_panel": hasattr(main_window, "skin_panel"),
        "has_rig_scale_panel": hasattr(main_window, "rig_scale_panel"),
        "has_video_panel": hasattr(main_window, "video_panel"),
        "has_timeline_panel": hasattr(main_window, "timeline_panel"),
        "onion_panel_state": onion_panel_state,
        "rotation_panel_state": rotation_panel_state,
        "skin_panel_state": skin_panel_state,
        "rig_scale_panel_state": rig_scale_panel_state,
        "video_panel_state": video_panel_state,
        "timeline_panel_state": timeline_panel_state,
        "onion_attach_text": main_window.onion_panel.attach_button.text(),
        "onion_scrub_label": main_window.onion_panel.full_fidelity_scrub_check.text(),
        "rotation_analyze_text": main_window.rotation_panel.analyze_button.text(),
        "rotation_best_fix_text": main_window.rotation_panel.apply_recommended_button.text(),
        "skin_analyze_text": main_window.skin_panel.analyze_button.text(),
        "skin_create_text": main_window.skin_panel.create_button.text(),
        "rig_scale_analyze_text": main_window.rig_scale_panel.analyze_button.text(),
        "rig_scale_create_text": main_window.rig_scale_panel.create_button.text(),
        "video_import_text": main_window.video_panel.import_button.text(),
        "video_target_text": main_window.video_panel.use_target_button.text(),
        "video_mode_text": main_window.video_panel.placement_combo.currentText(),
        "video_draw_text": main_window.video_panel.draw_button.text(),
        "timeline_auto_range_text": main_window.timeline_panel.auto_highlight_range_check.text(),
        "timeline_auto_range_checked": main_window.timeline_panel.auto_highlight_range_check.isChecked(),
        "timeline_auto_update_text": main_window.timeline_panel.auto_update_note_check.text(),
        "timeline_auto_update_checked": main_window.timeline_panel.auto_update_note_check.isChecked(),
        "timeline_marking_menu_text": main_window.timeline_panel.marking_menu_button.text(),
        "timeline_marking_menu_actions": [
            action.text()
            for action in main_window.timeline_panel.marking_menu.actions()
            if not action.isSeparator()
        ],
        "timeline_current_frame_label": main_window.timeline_panel.current_frame_notes_label.text(),
        "timeline_current_frame_readonly": main_window.timeline_panel.current_frame_notes_box.isReadOnly(),
        "timeline_add_text": main_window.timeline_panel.add_button.text(),
        "timeline_export_text": main_window.timeline_panel.export_button.text(),
        "brand_text": main_window.brand_label.text(),
        "donate_tooltip": main_window.donate_button.toolTip(),
        "donate_style": main_window.donate_button.styleSheet(),
    }}
    main_window.close()

    default_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools()
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()
    default_result = {{
        "current_tab": default_window.tab_widget.tabText(default_window.tab_widget.currentIndex()),
    }}
    default_window.close()

    docked_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True, initial_tab="timeline")
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()
    dock_result = {{
        "workspace_exists": bool(cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, exists=True)),
        "current_tab": docked_window.tab_widget.tabText(docked_window.tab_widget.currentIndex()),
    }}
    try:
        docked_window.close()
    except Exception:
        pass
    try:
        if cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, exists=True):
            cmds.deleteUI(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, control=True)
    except Exception:
        pass

    ikfk_window = maya_universal_ikfk_switcher.launch_maya_universal_ikfk_switcher()
    ikfk_result = {{
        "current_tab": ikfk_window.tab_widget.tabText(ikfk_window.tab_widget.currentIndex()),
    }}
    ikfk_window.close()

    result = {{
        "ok": True,
        "main": main_result,
        "default": default_result,
        "dock": dock_result,
        "ikfk": ikfk_result,
    }}
except Exception:
    result = {{
        "ok": False,
        "traceback": traceback.format_exc(),
    }}
""".format(repo_path=str(REPO_ROOT).replace("\\", "\\\\"))

    payload = run_bridge_exec_python(code, timeout=120)
    result = payload.get("result") or {}
    if not result.get("ok"):
        raise AssertionError(json.dumps(payload, indent=2))

    main = result.get("main") or {}
    if main.get("window_title") != "Maya Anim Workflow Tools":
        raise AssertionError(json.dumps(payload, indent=2))
    if tuple(main.get("minimum_size") or ()) != (760, 520):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("tab_count") != 11:
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("tabs") != ["Quick Start", "Dynamic Parenting", "Hand / Foot Hold", "Dynamic Pivot", "Universal IK/FK", "Onion Skin", "Rotation Doctor", "Skinning Cleanup", "Rig Scale", "Video Reference", "Timeline Notes"]:
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("tabs_movable"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("current_tab") != "Timeline Notes":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("tab_intro_count") != 11:
        raise AssertionError(json.dumps(payload, indent=2))
    if "different hands, props, or objects without popping" not in (main.get("parenting_intro_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if "plain-English version of what each tab does" not in (main.get("guide_intro_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if "timeline so you can scrub and review shot notes" not in (main.get("timeline_intro_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("tabs_use_scroll_areas"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("timeline_scroll_widget_resizable"):
        raise AssertionError(json.dumps(payload, indent=2))
    if "Pick the thing that moves and click Make Helpers once" not in (main.get("parenting_simple_steps_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("create_temp_text") != "Make Helpers":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("use_object_text") != "Use Picked Hand / Object":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("grab_here_text") != "Swap Here":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("release_here_text") != "Let Go Here":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("fix_jumps_text") != "Fix Jump Here":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("pickup_text") != "Pickup":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("pass_text") != "Pass":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("drop_text") != "Drop":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_parenting_event_list"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_jump_text") != "Jump To Picked Event":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("switch_fk_to_ik_text") != "Switch FK -> IK":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_ik_controls_field"):
        raise AssertionError(json.dumps(payload, indent=2))
    if "pole_vector_ctrl" not in (main.get("ik_controls_placeholder") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_contact_hold_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    contact_hold_panel_state = main.get("contact_hold_panel_state") or {}
    if contact_hold_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not contact_hold_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (contact_hold_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_apply_text") != "Hold Still":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_other_side_text") != "Add Matching Other Side":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_onion_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_rotation_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_skin_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_rig_scale_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_video_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_timeline_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    onion_panel_state = main.get("onion_panel_state") or {}
    if onion_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not onion_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (onion_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    rotation_panel_state = main.get("rotation_panel_state") or {}
    if rotation_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not rotation_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (rotation_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    skin_panel_state = main.get("skin_panel_state") or {}
    if skin_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not skin_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (skin_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    rig_scale_panel_state = main.get("rig_scale_panel_state") or {}
    if rig_scale_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not rig_scale_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (rig_scale_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    video_panel_state = main.get("video_panel_state") or {}
    if video_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not video_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (video_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    timeline_panel_state = main.get("timeline_panel_state") or {}
    if timeline_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not timeline_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (timeline_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("onion_attach_text") != "Attach Selected":
        raise AssertionError(json.dumps(payload, indent=2))
    if "Show Every Ghost" not in (main.get("onion_scrub_label") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("rotation_analyze_text") != "Analyze Selected":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("rotation_best_fix_text") != "Use Best Fix":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("skin_analyze_text") != "Check Selected Mesh":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("skin_create_text") != "Make Clean Copy":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("rig_scale_analyze_text") != "Check Setup":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("rig_scale_create_text") != "Make Export Copy":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("video_import_text") != "Make Tracing Card":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("video_target_text") != "Use Selected Object":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("video_mode_text") != "Behind Picked Object":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("video_draw_text") != "Start Drawing":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("timeline_auto_range_text") != "Auto Use Highlighted Range":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("timeline_auto_range_checked"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("timeline_auto_update_text") != "Auto Update Picked Note":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("timeline_auto_update_checked"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("timeline_marking_menu_text") != "Marking Menu":
        raise AssertionError(json.dumps(payload, indent=2))
    required_marking_actions = [
        "Add Note",
        "Update Picked Note",
        "Delete Picked Note",
        "Use Playback Range",
        "Pick Color",
        "Auto Use Highlighted Range",
        "Auto Update Picked Note",
        "Export Notes",
        "Import Notes",
    ]
    if main.get("timeline_marking_menu_actions") != required_marking_actions:
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("timeline_current_frame_label") != "Notes At Current Frame":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("timeline_current_frame_readonly"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("timeline_add_text") != "Add Note":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("timeline_export_text") != "Export Notes":
        raise AssertionError(json.dumps(payload, indent=2))
    if "followamir.com" not in (main.get("brand_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if "AMIR_PAYPAL_DONATE_URL" not in (main.get("donate_tooltip") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if "#FFC439" not in (main.get("donate_style") or ""):
        raise AssertionError(json.dumps(payload, indent=2))

    dock = result.get("dock") or {}
    default = result.get("default") or {}
    if default.get("current_tab") != "Quick Start":
        raise AssertionError(json.dumps(payload, indent=2))
    if not dock.get("workspace_exists"):
        raise AssertionError(json.dumps(payload, indent=2))
    if dock.get("current_tab") != "Timeline Notes":
        raise AssertionError(json.dumps(payload, indent=2))

    ikfk = result.get("ikfk") or {}
    if ikfk.get("current_tab") != "Universal IK/FK":
        raise AssertionError(json.dumps(payload, indent=2))

    print("MAYA_ANIM_WORKFLOW_TOOLS_LIVE_UI_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
