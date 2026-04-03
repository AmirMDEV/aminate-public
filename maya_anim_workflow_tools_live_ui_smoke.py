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

    def force_cleanup():
        try:
            maya_dynamic_parent_pivot._close_existing_window()
        except Exception:
            pass
        if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
            maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

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
    parenting_panel_state = panel_snapshot(main_window.tab_widget, main_window.parenting_tab, main_window.parenting_panel)
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
        "has_parenting_panel": hasattr(main_window, "parenting_panel"),
        "parenting_panel_state": parenting_panel_state,
        "parenting_add_object_text": main_window.parenting_panel.add_object_button.text(),
        "parenting_remove_object_text": main_window.parenting_panel.remove_object_button.text(),
        "parenting_pick_parent_text": main_window.parenting_panel.use_target_button.text(),
        "parenting_parent_to_picked_text": main_window.parenting_panel.parent_to_picked_button.text(),
        "parenting_add_parent_text": main_window.parenting_panel.add_target_button.text(),
        "parenting_parent_to_row_text": main_window.parenting_panel.parent_to_row_button.text(),
        "parenting_parent_to_world_text": main_window.parenting_panel.parent_to_world_button.text(),
        "parenting_apply_weights_text": main_window.parenting_panel.apply_weights_button.text(),
        "parenting_fix_blend_text": main_window.parenting_panel.fix_pop_button.text(),
        "has_parenting_event_list": hasattr(main_window.parenting_panel, "event_list"),
        "parenting_jump_text": main_window.parenting_panel.jump_button.text(),
        "parenting_delete_switch_text": main_window.parenting_panel.delete_switch_button.text(),
        "parenting_clear_switches_text": main_window.parenting_panel.clear_switches_button.text(),
        "parenting_maintain_offset_checked": main_window.parenting_panel.maintain_offset_check.isChecked(),
        "parenting_advanced_visible": main_window.parenting_panel.advanced_widget.isVisible(),
        "parenting_advanced_toggle_text": main_window.parenting_panel.advanced_toggle.text(),
        "switch_fk_to_ik_text": main_window.switch_fk_to_ik_button.text(),
        "has_ik_controls_field": hasattr(main_window, "ik_controls_line"),
        "ik_controls_placeholder": main_window.ik_controls_line.placeholderText(),
        "has_contact_hold_panel": hasattr(main_window, "contact_hold_panel"),
        "contact_hold_panel_state": contact_hold_panel_state,
        "contact_hold_has_table": hasattr(main_window.contact_hold_panel, "holds_table"),
        "contact_hold_apply_text": main_window.contact_hold_panel.apply_button.text(),
        "contact_hold_update_text": main_window.contact_hold_panel.update_button.text(),
        "contact_hold_enable_text": main_window.contact_hold_panel.enable_button.text(),
        "contact_hold_disable_text": main_window.contact_hold_panel.disable_button.text(),
        "contact_hold_delete_all_text": main_window.contact_hold_panel.delete_all_button.text(),
        "contact_hold_other_side_text": main_window.contact_hold_panel.add_other_side_button.text(),
        "contact_hold_x_checked": main_window.contact_hold_panel.hold_x_check.isChecked(),
        "contact_hold_y_checked": main_window.contact_hold_panel.hold_y_check.isChecked(),
        "contact_hold_z_checked": main_window.contact_hold_panel.hold_z_check.isChecked(),
        "contact_hold_keep_rotation_checked": main_window.contact_hold_panel.keep_rotation_check.isChecked(),
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
    force_cleanup()

    default_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools()
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()
    default_result = {{
        "current_tab": default_window.tab_widget.tabText(default_window.tab_widget.currentIndex()),
    }}
    default_window.close()
    force_cleanup()

    result = {{
        "ok": True,
        "main": main_result,
        "default": default_result,
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
    if "switch between hand, gun, world, or mixed parents without popping" not in (main.get("parenting_intro_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if "plain-English version of what each tab does" not in (main.get("guide_intro_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if "timeline so you can scrub and review shot notes" not in (main.get("timeline_intro_text") or ""):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("tabs_use_scroll_areas"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("timeline_scroll_widget_resizable"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_parenting_panel"):
        raise AssertionError(json.dumps(payload, indent=2))
    parenting_panel_state = main.get("parenting_panel_state") or {}
    if parenting_panel_state.get("is_window"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not parenting_panel_state.get("visible_to_main"):
        raise AssertionError(json.dumps(payload, indent=2))
    if (parenting_panel_state.get("size") or [0, 0])[1] < 200:
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_add_object_text") != "Add Object":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_remove_object_text") != "Remove Object":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_pick_parent_text") != "Pick Parent":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_parent_to_picked_text") != "Switch":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_add_parent_text") != "Add Parent":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_parent_to_row_text") != "Switch Chosen":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_parent_to_world_text") != "World":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_apply_weights_text") != "Blend Parents":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_fix_blend_text") != "Fix Jump Here":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("has_parenting_event_list"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_jump_text") != "Jump To Frame":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_delete_switch_text") != "Delete Chosen":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_clear_switches_text") != "Delete All":
        raise AssertionError(json.dumps(payload, indent=2))
    if not main.get("parenting_maintain_offset_checked"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_advanced_visible"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("parenting_advanced_toggle_text") != "More":
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
    if not main.get("contact_hold_has_table"):
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_apply_text") != "Save New Hold":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_update_text") != "Update Picked Hold":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_enable_text") != "Use Hold On Picked":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_disable_text") != "Use Original Motion On Picked":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_delete_all_text") != "Delete All Holds":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_other_side_text") != "Add Matching Other Side":
        raise AssertionError(json.dumps(payload, indent=2))
    if main.get("contact_hold_keep_rotation_checked"):
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

    default = result.get("default") or {}
    if default.get("current_tab") != "Quick Start":
        raise AssertionError(json.dumps(payload, indent=2))
    dock_code = """
import importlib
import sys
import traceback

repo_path = r"{repo_path}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya.cmds as cmds
    import maya_anim_workflow_tools
    import maya_dynamic_parent_pivot
    importlib.reload(maya_anim_workflow_tools)
    importlib.reload(maya_dynamic_parent_pivot)

    maya_dynamic_parent_pivot._close_existing_window()
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    docked_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True, initial_tab="timeline")
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    dock_parent_chain = []
    walker = docked_window
    while walker is not None:
        try:
            dock_parent_chain.append(walker.objectName() or walker.__class__.__name__)
        except Exception:
            dock_parent_chain.append(str(type(walker)))
        try:
            walker = walker.parentWidget()
        except Exception:
            break

    result = {{
        "ok": True,
        "workspace_exists": bool(cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, exists=True)),
        "workspace_floating": bool(cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, query=True, floating=True)) if cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, exists=True) else None,
        "current_tab": docked_window.tab_widget.tabText(docked_window.tab_widget.currentIndex()),
        "docked_is_window": bool(docked_window.isWindow()),
        "dock_host_exists": bool(maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST),
        "dock_host_is_window": bool(maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST.isWindow()) if maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST else None,
        "dock_host_object_name": maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST.objectName() if maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST else "",
        "host_owns_content": bool(maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST and getattr(maya_dynamic_parent_pivot.GLOBAL_DOCK_HOST, "content_widget", None) is docked_window),
        "expected_workspace_name": maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME,
        "expected_dock_host_name": maya_dynamic_parent_pivot.DOCK_HOST_OBJECT_NAME,
        "dock_parent_chain": dock_parent_chain,
    }}
except Exception:
    result = {{
        "ok": False,
        "traceback": traceback.format_exc(),
    }}
""".format(repo_path=str(REPO_ROOT).replace("\\", "\\\\"))
    dock_payload = run_bridge_exec_python(dock_code, timeout=120)
    dock = dock_payload.get("result") or {}
    if not dock.get("ok"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if not dock.get("workspace_exists"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("workspace_floating"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("current_tab") not in ["Quick Start", "Dynamic Parenting", "Hand / Foot Hold", "Dynamic Pivot", "Universal IK/FK", "Onion Skin", "Rotation Doctor", "Skinning Cleanup", "Rig Scale", "Video Reference", "Timeline Notes"]:
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("docked_is_window"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if not dock.get("dock_host_exists"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("dock_host_is_window"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("dock_host_object_name") != dock.get("expected_dock_host_name"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if not dock.get("host_owns_content"):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("expected_dock_host_name") not in (dock.get("dock_parent_chain") or []):
        raise AssertionError(json.dumps(dock_payload, indent=2))
    if dock.get("expected_workspace_name") not in (dock.get("dock_parent_chain") or []):
        raise AssertionError(json.dumps(dock_payload, indent=2))

    ikfk_code = """
import importlib
import sys
import traceback

repo_path = r"{repo_path}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya_universal_ikfk_switcher
    import maya_dynamic_parent_pivot
    importlib.reload(maya_universal_ikfk_switcher)
    importlib.reload(maya_dynamic_parent_pivot)

    maya_dynamic_parent_pivot._close_existing_window()
    if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
        maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()

    ikfk_window = maya_universal_ikfk_switcher.launch_maya_universal_ikfk_switcher()
    result = {{
        "ok": True,
        "current_tab": ikfk_window.tab_widget.tabText(ikfk_window.tab_widget.currentIndex()),
    }}
except Exception:
    result = {{
        "ok": False,
        "traceback": traceback.format_exc(),
    }}
""".format(repo_path=str(REPO_ROOT).replace("\\", "\\\\"))
    ikfk_payload = run_bridge_exec_python(ikfk_code, timeout=120)
    ikfk = ikfk_payload.get("result") or {}
    if not ikfk.get("ok"):
        raise AssertionError(json.dumps(ikfk_payload, indent=2))
    if ikfk.get("current_tab") != "Universal IK/FK":
        raise AssertionError(json.dumps(ikfk_payload, indent=2))

    print("MAYA_ANIM_WORKFLOW_TOOLS_LIVE_UI_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
