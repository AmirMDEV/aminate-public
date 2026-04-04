from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile
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


def run_bridge_exec_python(code: str, timeout: int = 240) -> dict:
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

    runner_code = r"""
import importlib
import json
import math
import sys
import traceback

import maya.cmds as cmds

repo_path = r"__REPO_PATH__"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

import maya_anim_workflow_tools
import maya_contact_hold
import maya_dynamic_parenting_tool
import maya_dynamic_parent_pivot
import maya_onion_skin
import maya_rotation_doctor
import maya_rig_scale_export

importlib.reload(maya_contact_hold)
importlib.reload(maya_dynamic_parenting_tool)
importlib.reload(maya_onion_skin)
importlib.reload(maya_rotation_doctor)
importlib.reload(maya_rig_scale_export)
importlib.reload(maya_dynamic_parent_pivot)
importlib.reload(maya_anim_workflow_tools)


def _short_name(node_name):
    return (node_name or "").split("|")[-1]


def _world_translation(node_name):
    return [float(value) for value in (cmds.xform(node_name, query=True, worldSpace=True, translation=True) or [0.0, 0.0, 0.0])]


def _world_rotation(node_name):
    return [float(value) for value in (cmds.xform(node_name, query=True, worldSpace=True, rotation=True) or [0.0, 0.0, 0.0])]


def _distance(a, b):
    return math.sqrt(sum((float(a[index]) - float(b[index])) ** 2 for index in range(3)))


def _key_times(node_name, attribute):
    return cmds.keyframe(node_name, attribute=attribute, query=True, timeChange=True) or []


def _create_transform(name, parent=None, translation=None, rotation=None):
    node_name = cmds.createNode("transform", name=name, parent=parent) if parent else cmds.createNode("transform", name=name)
    if translation:
        cmds.xform(node_name, worldSpace=True, translation=list(translation))
    if rotation:
        cmds.xform(node_name, worldSpace=True, rotation=list(rotation))
    return node_name


def _select(node_names):
    if node_names:
        cmds.select(node_names, replace=True)
    else:
        cmds.select(clear=True)


def _mesh_root_from_scene():
    selection = cmds.ls(selection=True, long=True) or []

    def _ancestors(node_name):
        parts = [part for part in node_name.split("|") if part]
        results = []
        for index in range(1, len(parts) + 1):
            results.append("|" + "|".join(parts[:index]))
        return results

    def _mesh_count(node_name):
        return len(cmds.listRelatives(node_name, allDescendents=True, type="mesh", fullPath=True) or [])

    for node_name in selection:
        if not cmds.objExists(node_name):
            continue
        best_candidate = ""
        best_count = 0
        for candidate in _ancestors(node_name):
            if not cmds.objExists(candidate):
                continue
            count = _mesh_count(candidate)
            if count >= best_count:
                best_candidate = candidate
                best_count = count
        if best_candidate:
            return best_candidate, best_count

    mesh_shapes = cmds.ls(type="mesh", long=True) or []
    if not mesh_shapes:
        return "", 0
    mesh_transform = cmds.listRelatives(mesh_shapes[0], parent=True, fullPath=True) or []
    if not mesh_transform:
        return "", 0
    node_name = mesh_transform[0]
    best = node_name
    best_count = _mesh_count(node_name)
    for candidate in reversed(_ancestors(node_name)):
        count = _mesh_count(candidate)
        if count >= best_count:
            best = candidate
            best_count = count
    return best, best_count


scene_before = {{
    "scene_name": cmds.file(query=True, sceneName=True) or "",
    "modified": bool(cmds.file(query=True, modified=True)),
    "current_time": float(cmds.currentTime(query=True)),
    "selection": cmds.ls(selection=True, long=True) or [],
}}

result = {{
    "ok": False,
    "scene": dict(scene_before),
}}

test_group = ""
onion_window = None
rotation_window = None
anim_window = None

try:
    root_candidate, mesh_count = _mesh_root_from_scene()
    if not root_candidate:
        raise RuntimeError("Could not find a mesh-bearing root in the open scene.")
    onion_target = root_candidate
    if cmds.objExists("Amanda_v_3:body_geo"):
        onion_target = (cmds.ls("Amanda_v_3:body_geo", long=True) or [onion_target])[0]
    result["scene"]["root_candidate"] = root_candidate
    result["scene"]["root_mesh_count"] = mesh_count
    result["scene"]["onion_target"] = onion_target

    test_group_name = "codexLiveFunctionalVerify_GRP"
    if cmds.objExists(test_group_name):
        cmds.delete(test_group_name)
    test_group = cmds.createNode("transform", name=test_group_name)

    onion_window = maya_onion_skin.launch_maya_onion_skin()
    onion_window.past_spin.setValue(4)
    onion_window.future_spin.setValue(4)
    onion_window.frame_step_spin.setValue(2)
    onion_window.auto_update_check.setChecked(True)
    onion_window.full_fidelity_scrub_check.setChecked(False)
    onion_window.display_mode_combo.setCurrentIndex(onion_window.display_mode_combo.findData(maya_onion_skin.MODE_FAST_SILHOUETTE))
    _select([onion_target])
    success, message = onion_window.controller.attach_selection(add=False)
    if not success:
        raise RuntimeError("Onion Skin attach failed: {0}".format(message))
    refresh_success, refresh_message = onion_window.controller.manual_refresh()
    if not refresh_success:
        raise RuntimeError("Onion Skin refresh failed: {0}".format(refresh_message))
    onion_offsets = sorted(onion_window.controller.silhouette_image_planes.keys())
    if not onion_offsets:
        raise RuntimeError("Onion Skin created no fast silhouette offsets.")
    result["onion_skin"] = {{
        "attached_roots": list(onion_window.controller.attached_roots),
        "mesh_count": len(onion_window.controller.source_meshes),
        "offsets": onion_offsets,
        "display_mode": onion_window.controller.display_mode,
        "silhouette_plane_count": len(onion_window.controller.silhouette_image_planes),
        "ghost_cache_count": len(onion_window.controller.ghost_cache),
        "summary": onion_window.controller.attachment_summary(),
    }}
    onion_window.controller.shutdown()
    onion_window.close()
    onion_window = None

    rotation_test = _create_transform("rotationDoctorVerify_CTRL", parent=test_group, translation=(0.0, 0.0, 0.0))
    cmds.setKeyframe(rotation_test, attribute="rotateX", time=1, value=0.0)
    cmds.setKeyframe(rotation_test, attribute="rotateY", time=1, value=10.0)
    cmds.setKeyframe(rotation_test, attribute="rotateZ", time=1, value=0.0)
    cmds.setKeyframe(rotation_test, attribute="rotateX", time=10, value=179.0)
    cmds.setKeyframe(rotation_test, attribute="rotateY", time=10, value=10.0)
    cmds.setKeyframe(rotation_test, attribute="rotateZ", time=10, value=0.0)
    cmds.setKeyframe(rotation_test, attribute="rotateX", time=20, value=-181.0)
    cmds.setKeyframe(rotation_test, attribute="rotateY", time=20, value=10.0)
    cmds.setKeyframe(rotation_test, attribute="rotateZ", time=20, value=0.0)

    long_spin_test = _create_transform("rotationDoctorSpinVerify_CTRL", parent=test_group, translation=(2.0, 0.0, 0.0))
    cmds.setKeyframe(long_spin_test, attribute="rotateX", time=1, value=0.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateZ", time=1, value=0.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateX", time=10, value=360.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateY", time=10, value=0.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateZ", time=10, value=0.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateX", time=20, value=720.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateY", time=20, value=0.0)
    cmds.setKeyframe(long_spin_test, attribute="rotateZ", time=20, value=0.0)

    rotation_window = maya_rotation_doctor.launch_maya_rotation_doctor()
    analyze_success, analyze_message = rotation_window.controller.analyze_targets([rotation_test, long_spin_test])
    if not analyze_success:
        raise RuntimeError("Rotation Doctor analyze failed: {0}".format(analyze_message))
    reports_by_name = {{report["display_name"]: report for report in rotation_window.controller.reports}}
    rotation_report = reports_by_name.get(_short_name(rotation_test))
    spin_report = reports_by_name.get(_short_name(long_spin_test))
    if not rotation_report:
        raise RuntimeError("Rotation Doctor did not report on the discontinuity test control.")
    if not spin_report:
        raise RuntimeError("Rotation Doctor did not report on the long spin test control.")
    apply_success, apply_message = rotation_window.controller.apply_recipe("clean_euler_discontinuity", [rotation_report])
    if not apply_success:
        raise RuntimeError("Rotation Doctor Euler cleanup failed: {0}".format(apply_message))
    spin_apply_success, spin_apply_message = rotation_window.controller.apply_recipe("preserve_spin_and_unroll", [spin_report])
    if not spin_apply_success:
        raise RuntimeError("Rotation Doctor preserve-spins failed: {0}".format(spin_apply_message))
    cmds.currentTime(20, edit=True)
    result["rotation_doctor"] = {{
        "analyzed_controls": [report["display_name"] for report in rotation_window.controller.reports],
        "discontinuity_recipe_before": rotation_report.get("recommended_recipe"),
        "spin_recipe_before": spin_report.get("recommended_recipe"),
        "discontinuity_rotate_x_end": float(cmds.getAttr(rotation_test + ".rotateX")),
        "spin_rotate_x_end": float(cmds.getAttr(long_spin_test + ".rotateX")),
    }}
    rotation_window.controller.shutdown()
    rotation_window.close()
    rotation_window = None

    anim_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools()
    controller = anim_window.controller
    parenting_controller = controller.dynamic_parenting_controller

    driven = _create_transform("dynamicDriven_CTRL", parent=test_group, translation=(2.0, 1.0, -1.5))
    hand_driver = _create_transform("dynamicHand_CTRL", parent=test_group, translation=(6.0, 0.0, 0.0))
    gun_driver = _create_transform("dynamicGun_CTRL", parent=test_group, translation=(10.0, 2.0, 0.0))
    starting_setup_count = len(parenting_controller.setup_payloads(from_selection=False))
    cmds.currentTime(1, edit=True)
    _select([driven])
    before_add = _world_translation(driven)
    add_success, add_message = parenting_controller.add_driven_from_selection()
    if not add_success:
        raise RuntimeError("Dynamic Parenting add failed: {0}".format(add_message))
    after_add = _world_translation(driven)
    if any(abs(float(before_add[index]) - float(after_add[index])) > 0.01 for index in range(3)):
        raise RuntimeError("Dynamic Parenting add should keep the driven object in place when the start-position option is on.")
    hand_before = _world_translation(driven)
    _select([driven, hand_driver])
    hand_pick_success, hand_pick_message = parenting_controller.set_pending_target_from_selection()
    if not hand_pick_success:
        raise RuntimeError("Dynamic Parenting hand pick failed: {0}".format(hand_pick_message))
    hand_snap_success, hand_snap_message = parenting_controller.snap_pending_target()
    if not hand_snap_success:
        raise RuntimeError("Dynamic Parenting hand snap failed: {0}".format(hand_snap_message))
    hand_snapped = _world_translation(driven)
    hand_switch_success, hand_switch_message = parenting_controller.apply_pending_target()
    if not hand_switch_success:
        raise RuntimeError("Dynamic Parenting hand switch failed: {0}".format(hand_switch_message))
    hand_after = _world_translation(driven)
    if any(abs(float(hand_snapped[index]) - float(hand_after[index])) > 0.01 for index in range(3)):
        raise RuntimeError("Dynamic Parenting snap pose was not preserved after switching.")
    hand_blend_values = maya_dynamic_parenting_tool._get_blend_attr_values(driven)
    if not hand_blend_values or any(abs(float(value) - 1.0) > 0.001 for value in hand_blend_values.values()):
        raise RuntimeError("Dynamic Parenting did not turn on the driven blendParent attribute.")
    cmds.currentTime(6, edit=True)
    cmds.xform(driven, worldSpace=True, translation=(15.0, 3.25, -0.5))
    hand_manual = _world_translation(driven)
    before_switch = _world_translation(driven)
    _select([driven, gun_driver])
    gun_pick_success, gun_pick_message = parenting_controller.set_pending_target_from_selection()
    if not gun_pick_success:
        raise RuntimeError("Dynamic Parenting gun pick failed: {0}".format(gun_pick_message))
    result["scene"]["manual_switch_before_apply"] = _world_translation(driven)
    current_setup_before_apply = parenting_controller.current_setup()
    result["scene"]["manual_switch_target_positions_before_apply"] = {
        target["label"]: _world_translation(target["locator"])
        for target in current_setup_before_apply.get("targets") or []
    }
    add_success = parenting_controller.add_targets_from_nodes([gun_driver])
    if not add_success[0] if isinstance(add_success, tuple) else not add_success:
        raise RuntimeError("Dynamic Parenting gun add failed: {0}".format(add_success[1] if isinstance(add_success, tuple) else add_success))
    result["scene"]["manual_switch_after_add"] = _world_translation(driven)
    current_setup_after_add = parenting_controller.current_setup()
    result["scene"]["manual_switch_target_positions_after_add"] = {
        target["label"]: _world_translation(target["locator"])
        for target in current_setup_after_add.get("targets") or []
    }
    gun_target_entry = parenting_controller._target_entry_by_driver(current_setup_after_add, gun_driver)
    if not gun_target_entry:
        gun_target_entry = next(
            (
                target
                for target in current_setup_after_add.get("targets") or []
                if target.get("label") == "dynamicGun_CTRL"
            ),
            None,
        )
    if not gun_target_entry:
        raise RuntimeError("Dynamic Parenting gun target was not added.")
    if any(abs(float(hand_manual[index]) - float(result["scene"]["manual_switch_after_add"][index])) > 0.01 for index in range(3)):
        raise RuntimeError("Dynamic Parenting add-target step should preserve the hand-adjusted pose when Maintain Current Offset is on.")
    gun_switch_success, gun_switch_message = parenting_controller.parent_fully_to_target(gun_target_entry["id"])
    if not gun_switch_success:
        raise RuntimeError("Dynamic Parenting gun switch failed: {0}".format(gun_switch_message))
    after_switch = _world_translation(driven)
    gun_weights_after = parenting_controller.current_weights(parenting_controller.current_setup())
    current_setup_after = parenting_controller.current_setup()
    locator_positions_after = {}
    target_offsets_after = {}
    driven_constraint_after = current_setup_after.get("driven_constraint")
    for target in current_setup_after.get("targets") or []:
        locator_positions_after[target["label"]] = _world_translation(target["locator"])
        if driven_constraint_after and target["locator"]:
            try:
                target_list = cmds.parentConstraint(driven_constraint_after, query=True, targetList=True) or []
                target_index = target_list.index(target["locator"])
                plug_base = "{0}.target[{1}]".format(driven_constraint_after, target_index)
                target_offsets_after[target["label"]] = {
                    "translate": list(cmds.getAttr(plug_base + ".targetOffsetTranslate")[0]),
                    "rotate": list(cmds.getAttr(plug_base + ".targetOffsetRotate")[0]),
                }
            except Exception:
                target_offsets_after[target["label"]] = None
    gun_blend_values = maya_dynamic_parenting_tool._get_blend_attr_values(driven)
    if not gun_blend_values or any(abs(float(value) - 1.0) > 0.001 for value in gun_blend_values.values()):
        raise RuntimeError("Dynamic Parenting did not keep the driven blendParent attribute on after the second switch.")
    result["scene"]["manual_switch_before"] = hand_manual
    result["scene"]["manual_switch_after"] = after_switch
    result["scene"]["manual_switch_message"] = gun_switch_message
    result["scene"]["manual_switch_weights"] = gun_weights_after
    result["scene"]["manual_switch_target_positions"] = locator_positions_after
    result["scene"]["manual_switch_target_offsets"] = target_offsets_after
    if any(abs(float(hand_manual[index]) - float(after_switch[index])) > 0.01 for index in range(3)):
        raise RuntimeError("Dynamic Parenting switch should preserve the hand-adjusted pose when Maintain Current Offset is on.")
    current_setup = current_setup_after
    target_lookup = {target["label"]: target["id"] for target in current_setup.get("targets") or []}
    cmds.currentTime(8, edit=True)
    blend_success, blend_message = parenting_controller.apply_weight_map(
        {
            "world": 0.5,
            target_lookup.get("dynamicGun_CTRL", ""): 0.5,
            target_lookup.get("dynamicHand_CTRL", ""): 0.0,
        },
        action_label="blend",
    )
    if not blend_success:
        raise RuntimeError("Dynamic Parenting blend failed: {0}".format(blend_message))
    blend_weights = parenting_controller.current_weights(parenting_controller.current_setup())
    cmds.currentTime(10, edit=True)
    world_success, world_message = parenting_controller.parent_to_world()
    if not world_success:
        raise RuntimeError("Dynamic Parenting world switch failed: {0}".format(world_message))
    world_weights = parenting_controller.current_weights(parenting_controller.current_setup())
    remaining_setups = parenting_controller.setup_payloads(from_selection=False)
    event_items = parenting_controller.event_items(parenting_controller.current_setup())

    hold_root = _create_transform("contactHoldRoot_CTRL", parent=test_group, translation=(0.0, 1.0, 0.0))
    hold_left_foot = _create_transform("L_contactHoldFoot_CTRL", parent=hold_root, translation=(2.0, 0.0, 0.0))
    hold_right_foot = _create_transform("R_contactHoldFoot_CTRL", parent=hold_root, translation=(-2.0, 0.0, 0.0))
    cmds.setKeyframe(hold_root, attribute="translateX", time=1, value=0.0)
    cmds.setKeyframe(hold_root, attribute="translateX", time=10, value=9.0)
    cmds.setKeyframe(hold_root, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(hold_root, attribute="rotateY", time=10, value=90.0)
    cmds.setKeyframe(hold_left_foot, attribute="rotateX", time=3, value=0.0)
    cmds.setKeyframe(hold_left_foot, attribute="rotateX", time=6, value=-35.0)
    cmds.setKeyframe(hold_right_foot, attribute="rotateX", time=3, value=0.0)
    cmds.setKeyframe(hold_right_foot, attribute="rotateX", time=6, value=-30.0)
    cmds.currentTime(3, edit=True)
    _select([hold_left_foot])
    hold_pick_success, hold_pick_message = controller.contact_hold_controller.set_controls_from_selection()
    if not hold_pick_success:
        raise RuntimeError("Contact Hold pick failed: {0}".format(hold_pick_message))
    hold_mirror_success, hold_mirror_message = controller.contact_hold_controller.add_matching_other_side()
    if not hold_mirror_success:
        raise RuntimeError("Contact Hold other-side pick failed: {0}".format(hold_mirror_message))
    controller.contact_hold_controller.start_frame = 3
    controller.contact_hold_controller.end_frame = 6
    controller.contact_hold_controller.keep_rotation = False
    controller.contact_hold_controller.hold_axes = ("x",)
    hold_analyze_success, hold_analyze_message = controller.contact_hold_controller.analyze_setup()
    if not hold_analyze_success:
        raise RuntimeError("Contact Hold analyze failed: {0}".format(hold_analyze_message))
    hold_anchor_x = {
        hold_left_foot: float(cmds.xform(hold_left_foot, query=True, worldSpace=True, translation=True)[0]),
        hold_right_foot: float(cmds.xform(hold_right_foot, query=True, worldSpace=True, translation=True)[0]),
    }
    hold_start_rotate_x = float(cmds.getAttr(hold_left_foot + ".rotateX"))
    cmds.currentTime(6, edit=True)
    hold_end_rotate_x = float(cmds.getAttr(hold_left_foot + ".rotateX"))
    cmds.currentTime(3, edit=True)
    hold_apply_success, hold_apply_message = controller.contact_hold_controller.apply_hold()
    if not hold_apply_success:
        raise RuntimeError("Contact Hold apply failed: {0}".format(hold_apply_message))
    hold_locator = maya_contact_hold._find_hold_locator(hold_left_foot)
    mirrored_hold_locator = maya_contact_hold._find_hold_locator(hold_right_foot)
    if not hold_locator or not mirrored_hold_locator:
        raise RuntimeError("Contact Hold did not save both live hold locators.")
    hold_payload = maya_contact_hold._hold_payload(hold_locator)
    mirrored_hold_payload = maya_contact_hold._hold_payload(mirrored_hold_locator)
    hold_weight_attr = hold_payload.get("enabled_attr")
    mirrored_hold_weight_attr = mirrored_hold_payload.get("enabled_attr")
    hold_weight_keys = cmds.keyframe(hold_weight_attr, query=True, timeChange=True) or []
    mirrored_hold_weight_keys = cmds.keyframe(mirrored_hold_weight_attr, query=True, timeChange=True) or []
    cmds.setKeyframe(hold_root, attribute="translateX", time=10, value=18.0)
    hold_frames = {}
    for frame_value in range(3, 7):
        cmds.currentTime(frame_value, edit=True)
        frame_axis = {}
        for hold_node, anchor_value in hold_anchor_x.items():
            held_x = float(cmds.xform(hold_node, query=True, worldSpace=True, translation=True)[0])
            frame_axis[hold_node] = held_x
            if abs(anchor_value - held_x) > 0.001:
                raise RuntimeError("Contact Hold did not keep the chosen world axis locked.")
        hold_frames[frame_value] = frame_axis
    cmds.currentTime(6, edit=True)
    hold_rotation_after = float(cmds.getAttr(hold_left_foot + ".rotateX"))
    if abs(hold_rotation_after - hold_end_rotate_x) > 0.001 or abs(hold_end_rotate_x - hold_start_rotate_x) <= 0.01:
        raise RuntimeError("Contact Hold broke the original foot rotation while Keep Turn Too was off.")
    hold_disable_success, hold_disable_message = controller.contact_hold_controller.disable_hold()
    if not hold_disable_success:
        raise RuntimeError("Contact Hold disable failed: {0}".format(hold_disable_message))
    cmds.currentTime(6, edit=True)
    hold_disabled_x = float(cmds.xform(hold_left_foot, query=True, worldSpace=True, translation=True)[0])
    if abs(hold_disabled_x - hold_anchor_x[hold_left_foot]) <= 0.01:
        raise RuntimeError("Contact Hold disable did not restore the original moving axis motion.")
    hold_enable_success, hold_enable_message = controller.contact_hold_controller.enable_hold()
    if not hold_enable_success:
        raise RuntimeError("Contact Hold enable failed: {0}".format(hold_enable_message))
    cmds.currentTime(6, edit=True)
    hold_reenabled_x = float(cmds.xform(hold_left_foot, query=True, worldSpace=True, translation=True)[0])
    if abs(hold_reenabled_x - hold_anchor_x[hold_left_foot]) > 0.001:
        raise RuntimeError("Contact Hold enable did not restore the saved held axis motion.")
    controller.contact_hold_controller.set_selected_hold_locators(
        [
            maya_contact_hold._find_hold_locator(hold_left_foot),
            maya_contact_hold._find_hold_locator(hold_right_foot),
        ]
    )
    controller.contact_hold_controller.end_frame = 5
    hold_update_success, hold_update_message = controller.contact_hold_controller.update_selected_hold()
    if not hold_update_success:
        raise RuntimeError("Contact Hold update failed: {0}".format(hold_update_message))
    cmds.currentTime(5, edit=True)
    updated_hold_x = float(cmds.xform(hold_left_foot, query=True, worldSpace=True, translation=True)[0])
    cmds.currentTime(6, edit=True)
    updated_release_x = float(cmds.xform(hold_left_foot, query=True, worldSpace=True, translation=True)[0])
    if abs(updated_hold_x - hold_anchor_x[hold_left_foot]) > 0.001:
        raise RuntimeError("Contact Hold update no longer held inside the new range.")
    if abs(updated_release_x - hold_anchor_x[hold_left_foot]) <= 0.01:
        raise RuntimeError("Contact Hold update did not release after the new end frame.")

    pivot_a = _create_transform("pivotVerifyA_CTRL", parent=test_group, translation=(1.0, 0.0, 0.0))
    pivot_b = _create_transform("pivotVerifyB_CTRL", parent=test_group, translation=(3.0, 0.0, 0.0))
    pivot_before = {{
        pivot_a: _world_translation(pivot_a),
        pivot_b: _world_translation(pivot_b),
    }}
    _select([pivot_a, pivot_b])
    pivot_success, pivot_message = controller.create_pivot("centered")
    if not pivot_success:
        raise RuntimeError("Dynamic Pivot create failed: {0}".format(pivot_message))
    cmds.xform(controller.active_pivot, worldSpace=True, translation=[0.0, 2.0, 0.0])
    cmds.xform(controller.active_pivot, worldSpace=True, rotation=[0.0, 45.0, 0.0])
    apply_pivot_success, apply_pivot_message = controller.apply_pivot_rotation()
    if not apply_pivot_success:
        raise RuntimeError("Dynamic Pivot apply failed: {0}".format(apply_pivot_message))
    pivot_after = {{
        pivot_a: _world_translation(pivot_a),
        pivot_b: _world_translation(pivot_b),
    }}
    if _distance(pivot_before[pivot_a], pivot_after[pivot_a]) < 0.001 and _distance(pivot_before[pivot_b], pivot_after[pivot_b]) < 0.001:
        raise RuntimeError("Dynamic Pivot did not change either target transform.")
    clear_pivot_success, clear_pivot_message = controller.clear_pivot()
    if not clear_pivot_success:
        raise RuntimeError("Dynamic Pivot clear failed: {0}".format(clear_pivot_message))

    switch_host = _create_transform("ikfkSwitchHost_CTRL", parent=test_group, translation=(0.0, 3.0, 0.0))
    if not cmds.attributeQuery("ikFkBlend", node=switch_host, exists=True):
        cmds.addAttr(switch_host, longName="ikFkBlend", attributeType="double", keyable=True, min=0.0, max=1.0, defaultValue=0.0)
    fk_shoulder = _create_transform("fkShoulder_CTRL", parent=test_group, translation=(0.0, 5.0, 0.0), rotation=(10.0, 15.0, 0.0))
    fk_elbow = _create_transform("fkElbow_CTRL", parent=test_group, translation=(3.0, 5.0, 0.0), rotation=(20.0, 25.0, 0.0))
    fk_wrist = _create_transform("fkWrist_CTRL", parent=test_group, translation=(6.0, 5.0, 0.0), rotation=(30.0, 35.0, 5.0))
    ik_hand = _create_transform("ikHand_CTRL", parent=test_group, translation=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0))
    pole_vector = _create_transform("poleVector_CTRL", parent=test_group, translation=(1.0, 2.0, 5.0), rotation=(0.0, 0.0, 0.0))
    match_shoulder = _create_transform("matchShoulder_JNT", parent=test_group, translation=(0.0, 5.0, 0.0), rotation=(10.0, 15.0, 0.0))
    match_elbow = _create_transform("matchElbow_JNT", parent=test_group, translation=(3.0, 5.0, 1.0), rotation=(20.0, 25.0, 0.0))
    match_wrist = _create_transform("matchWrist_JNT", parent=test_group, translation=(7.0, 5.5, 2.0), rotation=(35.0, 40.0, 10.0))

    profile = {{
        "profile_name": "verify_left_arm",
        "rig_root": test_group,
        "namespace_hint": "",
        "limb_type": "arm",
        "side": "left",
        "fk_controls": [fk_shoulder, fk_elbow, fk_wrist],
        "ik_control": ik_hand,
        "pole_vector_control": pole_vector,
        "switch_attr": switch_host + ".ikFkBlend",
        "fk_value": 0.0,
        "ik_value": 1.0,
        "extra_controls": [],
        "match_nodes": [match_shoulder, match_elbow, match_wrist],
    }}

    detection = {{}}
    if scene_before["selection"]:
        _select(scene_before["selection"])
        detected_profile, detected_issues = controller.detect_profile()
        detection = {{
            "profile_name": detected_profile.get("profile_name", ""),
            "ik_control": detected_profile.get("ik_control", ""),
            "ik_controls": list(detected_profile.get("ik_controls", [])),
            "pole_vector_control": detected_profile.get("pole_vector_control", ""),
            "switch_attr": detected_profile.get("switch_attr", ""),
            "fk_controls": list(detected_profile.get("fk_controls", [])),
            "issues": list(detected_issues),
        }}

    cmds.currentTime(10, edit=True)
    cmds.setAttr(profile["switch_attr"], profile["fk_value"])
    fk_to_ik_success, fk_to_ik_message = controller.switch_fk_to_ik(profile)
    if not fk_to_ik_success:
        raise RuntimeError("Universal IK/FK FK -> IK failed: {0}".format(fk_to_ik_message))
    fk_to_ik_attr = float(cmds.getAttr(profile["switch_attr"]))
    fk_to_ik_ik_position = _world_translation(profile["ik_control"])
    expected_ik_position = _world_translation(match_wrist)
    fk_switch_keys = _key_times(switch_host, "ikFkBlend")
    if fk_to_ik_attr != profile["ik_value"]:
        raise RuntimeError("Universal IK/FK did not set the switch attribute to IK.")
    if _distance(fk_to_ik_ik_position, expected_ik_position) > 0.001:
        raise RuntimeError("Universal IK/FK did not move the IK control to the match wrist.")

    cmds.currentTime(14, edit=True)
    cmds.xform(match_shoulder, worldSpace=True, rotation=[45.0, 5.0, 0.0])
    cmds.xform(match_elbow, worldSpace=True, rotation=[65.0, 15.0, 0.0])
    cmds.xform(match_wrist, worldSpace=True, rotation=[80.0, 30.0, 10.0])
    cmds.setAttr(profile["switch_attr"], profile["ik_value"])
    ik_to_fk_success, ik_to_fk_message = controller.switch_ik_to_fk(profile)
    if not ik_to_fk_success:
        raise RuntimeError("Universal IK/FK IK -> FK failed: {0}".format(ik_to_fk_message))
    ik_to_fk_attr = float(cmds.getAttr(profile["switch_attr"]))
    fk_rotations_after = [_world_rotation(node_name) for node_name in profile["fk_controls"]]
    expected_fk_rotations = [_world_rotation(node_name) for node_name in profile["match_nodes"]]
    ik_switch_keys = _key_times(switch_host, "ikFkBlend")
    if ik_to_fk_attr != profile["fk_value"]:
        raise RuntimeError("Universal IK/FK did not set the switch attribute to FK.")

    skin_root = cmds.createNode("joint", name="skinCleanupVerify_root_jnt", parent=test_group)
    skin_mid = cmds.createNode("joint", name="skinCleanupVerify_mid_jnt", parent=skin_root)
    cmds.xform(skin_root, worldSpace=True, translation=[12.0, 0.0, 0.0])
    cmds.xform(skin_mid, worldSpace=True, translation=[12.0, 4.0, 0.0])
    skin_mesh = cmds.polyCube(name="skinCleanupVerify_geo", width=2.0, height=3.0, depth=1.5, subdivisionsY=2)[0]
    cmds.parent(skin_mesh, test_group)
    cmds.xform(skin_mesh, worldSpace=True, translation=[14.0, 1.0, -2.0], rotation=[10.0, 25.0, 5.0], scale=[1.8, 0.7, 1.3])
    skin_cluster = cmds.skinCluster([skin_root, skin_mid], skin_mesh, toSelectedBones=True, name="skinCleanupVerify_skinCluster")[0]
    cmds.skinPercent(skin_cluster, skin_mesh + ".vtx[0:3]", transformValue=[(skin_root, 1.0), (skin_mid, 0.0)])
    cmds.skinPercent(skin_cluster, skin_mesh + ".vtx[4:7]", transformValue=[(skin_root, 0.5), (skin_mid, 0.5)])
    cmds.skinPercent(skin_cluster, skin_mesh + ".vtx[8:11]", transformValue=[(skin_root, 0.1), (skin_mid, 0.9)])
    original_skin_scale = [float(value) for value in cmds.getAttr(skin_mesh + ".scale")[0]]
    _select([skin_mesh])
    skin_analyze_success, skin_analyze_message = controller.skinning_controller.analyze_selection()
    if not skin_analyze_success:
        raise RuntimeError("Skinning Cleanup analyze failed: {0}".format(skin_analyze_message))
    skin_create_success, skin_create_message = controller.skinning_controller.create_clean_copy()
    if not skin_create_success:
        raise RuntimeError("Skinning Cleanup create failed: {0}".format(skin_create_message))
    if not controller.skinning_controller.result or not controller.skinning_controller.result.get("verified"):
        raise RuntimeError("Skinning Cleanup preview did not pass verification.")
    skin_replace_success, skin_replace_message = controller.skinning_controller.replace_original()
    if not skin_replace_success:
        raise RuntimeError("Skinning Cleanup replace failed: {0}".format(skin_replace_message))
    cleaned_skin_scale = [float(value) for value in cmds.getAttr("skinCleanupVerify_geo.scale")[0]]
    skin_backup = controller.skinning_controller.result.get("backup_transform", "")
    if not skin_backup or not cmds.objExists(skin_backup):
        raise RuntimeError("Skinning Cleanup did not leave the original mesh as a hidden backup.")

    rig_scale_group = cmds.createNode("transform", name="rigScaleVerify_source_GRP", parent=test_group)
    cmds.setAttr(rig_scale_group + ".scaleX", 1.5)
    cmds.setAttr(rig_scale_group + ".scaleY", 1.5)
    cmds.setAttr(rig_scale_group + ".scaleZ", 1.5)
    rig_scale_root = cmds.createNode("joint", name="rigScaleVerify_root_jnt", parent=rig_scale_group)
    rig_scale_mid = cmds.createNode("joint", name="rigScaleVerify_mid_jnt", parent=rig_scale_root)
    cmds.setAttr(rig_scale_root + ".translateX", 18.0)
    cmds.setAttr(rig_scale_root + ".translateY", 2.0)
    cmds.setAttr(rig_scale_mid + ".translateY", 4.0)
    rig_scale_mesh = cmds.polyCube(name="rigScaleVerify_geo", width=2.0, height=4.0, depth=1.5, subdivisionsY=2)[0]
    rig_scale_mesh = cmds.parent(rig_scale_mesh, rig_scale_group)[0]
    cmds.xform(rig_scale_mesh, objectSpace=True, translation=(18.0, 2.0, 0.0))
    rig_scale_skin = cmds.skinCluster([rig_scale_root, rig_scale_mid], rig_scale_mesh, toSelectedBones=True, name="rigScaleVerify_skinCluster")[0]
    cmds.skinPercent(rig_scale_skin, rig_scale_mesh + ".vtx[0:3]", transformValue=[(rig_scale_root, 1.0), (rig_scale_mid, 0.0)])
    cmds.skinPercent(rig_scale_skin, rig_scale_mesh + ".vtx[4:7]", transformValue=[(rig_scale_root, 0.5), (rig_scale_mid, 0.5)])
    cmds.skinPercent(rig_scale_skin, rig_scale_mesh + ".vtx[8:11]", transformValue=[(rig_scale_root, 0.1), (rig_scale_mid, 0.9)])
    source_rig_distance = _distance(_world_translation(rig_scale_root), _world_translation(rig_scale_mid))
    controller.rig_scale_controller.character_root = rig_scale_group
    controller.rig_scale_controller.skeleton_root = rig_scale_root
    controller.rig_scale_controller.scale_factor = 2.0
    rig_scale_analyze_success, rig_scale_analyze_message = controller.rig_scale_controller.analyze_setup()
    if not rig_scale_analyze_success:
        raise RuntimeError("Rig Scale analyze failed: {0}".format(rig_scale_analyze_message))
    rig_scale_create_success, rig_scale_create_message = controller.rig_scale_controller.create_export_copy()
    if not rig_scale_create_success:
        raise RuntimeError("Rig Scale create failed: {0}".format(rig_scale_create_message))
    if not controller.rig_scale_controller.result or not controller.rig_scale_controller.result.get("verified"):
        raise RuntimeError("Rig Scale export copy did not pass verification.")
    joint_map = controller.rig_scale_controller.result.get("joint_map") or {}

    def _mapped_joint(source_joint):
        if source_joint in joint_map:
            return joint_map[source_joint]
        source_long = cmds.ls(source_joint, long=True) or []
        if source_long and source_long[0] in joint_map:
            return joint_map[source_long[0]]
        source_short = source_joint.rsplit("|", 1)[-1]
        for key_name, mapped_name in joint_map.items():
            key_short = key_name.rsplit("|", 1)[-1]
            if key_short == source_short:
                return mapped_name
        raise RuntimeError("Rig Scale joint map is missing '{0}'.".format(source_joint))

    rig_scale_duplicate_root = _mapped_joint(rig_scale_root)
    rig_scale_duplicate_mid = _mapped_joint(rig_scale_mid)
    rig_scale_duplicate_distance = _distance(_world_translation(rig_scale_duplicate_root), _world_translation(rig_scale_duplicate_mid))

    def _panel_snapshot(target_tab, panel):
        anim_window.tab_widget.setCurrentWidget(target_tab)
        if maya_dynamic_parent_pivot.QtWidgets and maya_dynamic_parent_pivot.QtWidgets.QApplication.instance():
            maya_dynamic_parent_pivot.QtWidgets.QApplication.processEvents()
        return {{
            "is_window": bool(panel.isWindow()),
            "visible_to_main": bool(panel.isVisibleTo(anim_window)),
            "size": [int(panel.width()), int(panel.height())],
        }}

    result["anim_workflow"] = {{
        "tabs": [anim_window.tab_widget.tabText(index) for index in range(anim_window.tab_widget.count())],
        "embedded_tools": {{
            "parenting_add_object_text": anim_window.parenting_panel.add_object_button.text(),
            "parenting_pick_parent_text": anim_window.parenting_panel.use_target_button.text(),
            "parenting_snap_text": anim_window.parenting_panel.snap_to_picked_button.text(),
            "parenting_parent_to_picked_text": anim_window.parenting_panel.parent_to_picked_button.text(),
            "parenting_world_text": anim_window.parenting_panel.parent_to_world_button.text(),
            "parenting_blend_text": anim_window.parenting_panel.apply_weights_button.text(),
            "parenting_panel_state": _panel_snapshot(anim_window.parenting_tab, anim_window.parenting_panel),
            "contact_hold_apply_text": anim_window.contact_hold_panel.apply_button.text(),
            "contact_hold_enable_text": anim_window.contact_hold_panel.enable_button.text(),
            "contact_hold_disable_text": anim_window.contact_hold_panel.disable_button.text(),
            "contact_hold_other_side_text": anim_window.contact_hold_panel.add_other_side_button.text(),
            "onion_attach_text": anim_window.onion_panel.attach_button.text(),
            "rotation_analyze_text": anim_window.rotation_panel.analyze_button.text(),
            "skin_analyze_text": anim_window.skin_panel.analyze_button.text(),
            "rig_scale_analyze_text": anim_window.rig_scale_panel.analyze_button.text(),
            "contact_hold_panel_state": _panel_snapshot(anim_window.contact_hold_tab, anim_window.contact_hold_panel),
            "onion_panel_state": _panel_snapshot(anim_window.onion_tab, anim_window.onion_panel),
            "rotation_panel_state": _panel_snapshot(anim_window.rotation_tab, anim_window.rotation_panel),
            "skin_panel_state": _panel_snapshot(anim_window.skin_tab, anim_window.skin_panel),
            "rig_scale_panel_state": _panel_snapshot(anim_window.rig_scale_tab, anim_window.rig_scale_panel),
        }},
        "dynamic_parenting": {{
        "add_message": add_message,
        "before_add": before_add,
        "after_add": after_add,
        "hand_pick_message": hand_pick_message,
            "hand_switch_message": hand_switch_message,
            "hand_blend_values": hand_blend_values,
            "gun_pick_message": gun_pick_message,
            "gun_switch_message": gun_switch_message,
            "gun_blend_values": gun_blend_values,
            "blend_message": blend_message,
            "world_message": world_message,
            "starting_setups": starting_setup_count,
            "remaining_setups": len(remaining_setups),
            "hand_before": hand_before,
            "hand_snapped": hand_snapped,
            "hand_after": hand_after,
            "switch_before": before_switch,
            "switch_after": after_switch,
            "blend_world_weight": blend_weights.get("world", 0.0),
            "blend_gun_weight": blend_weights.get(target_lookup.get("dynamicGun_CTRL", ""), 0.0),
            "world_weight": world_weights.get("world", 0.0),
            "event_items": [item["display"] for item in event_items],
        }},
        "contact_hold": {{
            "frames": hold_frames,
            "controls": list(controller.contact_hold_controller.control_nodes),
            "axes": list(hold_payload.get("axes") or []),
            "keep_rotation": bool(hold_payload.get("keep_rotation")),
            "weight_keys": hold_weight_keys,
            "mirrored_weight_keys": mirrored_hold_weight_keys,
            "disabled_x": hold_disabled_x,
            "reenabled_x": hold_reenabled_x,
            "anchor_x": hold_anchor_x[hold_left_foot],
            "rotation_after": hold_rotation_after,
            "rotation_expected": hold_end_rotate_x,
            "updated_hold_x": updated_hold_x,
            "updated_release_x": updated_release_x,
        }},
        "dynamic_pivot": {{
            "pivot_before": pivot_before,
            "pivot_after": pivot_after,
        }},
        "ikfk": {{
            "detect_profile": detection,
            "fk_to_ik_keys": fk_switch_keys,
            "fk_to_ik_ik_position": fk_to_ik_ik_position,
            "expected_ik_position": expected_ik_position,
            "ik_to_fk_keys": ik_switch_keys,
            "fk_rotations_after": fk_rotations_after,
            "expected_fk_rotations": expected_fk_rotations,
        }},
        "skinning_cleanup": {{
            "original_scale_before": original_skin_scale,
            "cleaned_scale_after": cleaned_skin_scale,
            "backup_transform": skin_backup,
            "report": controller.skinning_controller.report_text(),
        }},
        "rig_scale": {{
            "source_distance": source_rig_distance,
            "duplicate_distance": rig_scale_duplicate_distance,
            "export_group": controller.rig_scale_controller.result.get("export_group", ""),
            "report": controller.rig_scale_controller.report_text(),
        }},
    }}

    result["ok"] = True
except Exception:
    result["ok"] = False
    result["traceback"] = traceback.format_exc()
finally:
    try:
        if onion_window is not None:
            try:
                onion_window.controller.shutdown()
            except Exception:
                pass
            try:
                onion_window.close()
            except Exception:
                pass
        if rotation_window is not None:
            try:
                rotation_window.controller.shutdown()
            except Exception:
                pass
            try:
                rotation_window.close()
            except Exception:
                pass
        if anim_window is not None:
            try:
                anim_window.controller.clear_pivot(silent=True)
            except Exception:
                pass
            try:
                anim_window.close()
            except Exception:
                pass
        for root_name in (
            getattr(maya_onion_skin, "ROOT_GROUP_NAME", ""),
            getattr(maya_dynamic_parenting_tool, "ROOT_GROUP_NAME", ""),
            getattr(maya_dynamic_parent_pivot, "ROOT_GROUP_NAME", ""),
        ):
            if root_name and cmds.objExists(root_name):
                try:
                    cmds.delete(root_name)
                except Exception:
                    pass
        if test_group and cmds.objExists(test_group):
            try:
                cmds.delete(test_group)
            except Exception:
                pass
        cmds.currentTime(scene_before["current_time"], edit=True)
        _select(scene_before["selection"])
        cmds.file(modified=scene_before["modified"])
    except Exception:
        pass
""".replace("__REPO_PATH__", str(REPO_ROOT).replace("\\", "\\\\")).replace("{{", "{").replace("}}", "}")

    runner_path = pathlib.Path(tempfile.gettempdir()) / "codex_maya_live_scene_functional_verify_runner.py"
    runner_path.write_text(runner_code, encoding="utf-8")

    code = """
namespace = {{
    "__name__": "__codex_live_scene_functional_verify__",
}}
exec(compile(open(r"{runner_path}", "r").read(), r"{runner_path}", "exec"), namespace, namespace)
result = namespace.get("result")
""".format(runner_path=str(runner_path).replace("\\", "/"))

    payload = run_bridge_exec_python(code, timeout=240)
    result = payload.get("result") or {}
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result.get("ok"):
        raise AssertionError(json.dumps(result, indent=2))

    onion = result.get("onion_skin") or {}
    if not onion.get("attached_roots") or not onion.get("offsets"):
        raise AssertionError(json.dumps(result, indent=2))
    if onion.get("display_mode") != "fast_silhouette":
        raise AssertionError(json.dumps(result, indent=2))
    if int(onion.get("silhouette_plane_count", 0)) != len(onion.get("offsets") or []):
        raise AssertionError(json.dumps(result, indent=2))
    if int(onion.get("ghost_cache_count", 0)) != 0:
        raise AssertionError(json.dumps(result, indent=2))

    rotation = result.get("rotation_doctor") or {}
    if not rotation.get("analyzed_controls"):
        raise AssertionError(json.dumps(result, indent=2))

    workflow = result.get("anim_workflow") or {}
    if workflow.get("tabs") != ["Quick Start", "Dynamic Parenting", "Hand / Foot Hold", "Dynamic Pivot", "Universal IK/FK", "Onion Skin", "Rotation Doctor", "Skinning Cleanup", "Rig Scale", "Video Reference", "Timeline Notes"]:
        raise AssertionError(json.dumps(result, indent=2))
    embedded_tools = workflow.get("embedded_tools") or {}
    if embedded_tools.get("parenting_add_object_text") != "Add Object":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("parenting_pick_parent_text") != "Pick Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("parenting_snap_text") != "Snap To Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("parenting_parent_to_picked_text") != "Switch to this Parent":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("parenting_world_text") != "World":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("parenting_blend_text") != "Blend Parents":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("contact_hold_apply_text") != "Save New Hold":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("contact_hold_enable_text") != "Use Hold On Picked":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("contact_hold_disable_text") != "Use Original Motion On Picked":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("contact_hold_other_side_text") != "Add Matching Other Side":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("onion_attach_text") != "Attach Selected":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("rotation_analyze_text") != "Analyze Selected":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("skin_analyze_text") != "Check Selected Mesh":
        raise AssertionError(json.dumps(result, indent=2))
    if embedded_tools.get("rig_scale_analyze_text") != "Check Setup":
        raise AssertionError(json.dumps(result, indent=2))
    for key in ("parenting_panel_state", "contact_hold_panel_state", "onion_panel_state", "rotation_panel_state", "skin_panel_state", "rig_scale_panel_state"):
        state = embedded_tools.get(key) or {}
        if state.get("is_window"):
            raise AssertionError(json.dumps(result, indent=2))
        if not state.get("visible_to_main"):
            raise AssertionError(json.dumps(result, indent=2))
        if (state.get("size") or [0, 0])[1] < 200:
            raise AssertionError(json.dumps(result, indent=2))
    dynamic_parenting = workflow.get("dynamic_parenting") or {}
    if int(dynamic_parenting.get("remaining_setups", 0)) != int(dynamic_parenting.get("starting_setups", 0)) + 1:
        raise AssertionError(json.dumps(result, indent=2))
    if len(dynamic_parenting.get("event_items") or []) != 4:
        raise AssertionError(json.dumps(result, indent=2))
    if not (dynamic_parenting.get("hand_blend_values") or {}):
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(value) - 1.0) > 0.001 for value in (dynamic_parenting.get("hand_blend_values") or {}).values()):
        raise AssertionError(json.dumps(result, indent=2))
    if any(abs(float(value) - 1.0) > 0.001 for value in (dynamic_parenting.get("gun_blend_values") or {}).values()):
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(dynamic_parenting.get("blend_world_weight", 0.0)) - 0.5) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(dynamic_parenting.get("blend_gun_weight", 0.0)) - 0.5) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(dynamic_parenting.get("world_weight", 0.0)) - 1.0) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))
    hand_before = dynamic_parenting.get("hand_before") or []
    hand_snapped = dynamic_parenting.get("hand_snapped") or []
    hand_after = dynamic_parenting.get("hand_after") or []
    if len(hand_before) != 3 or len(hand_snapped) != 3:
        raise AssertionError(json.dumps(result, indent=2))
    if not any(abs(float(hand_before[index]) - float(hand_snapped[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    if len(hand_snapped) != 3 or len(hand_after) != 3 or any(abs(float(hand_snapped[index]) - float(hand_after[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    switch_before = dynamic_parenting.get("switch_before") or []
    switch_after = dynamic_parenting.get("switch_after") or []
    if len(switch_before) != 3 or len(switch_after) != 3 or any(abs(float(switch_before[index]) - float(switch_after[index])) > 0.01 for index in range(3)):
        raise AssertionError(json.dumps(result, indent=2))
    if dynamic_parenting.get("event_items", [None])[0] != "F2: Switch -> dynamicHand_CTRL 1.00":
        raise AssertionError(json.dumps(result, indent=2))
    if dynamic_parenting.get("event_items", [None, None])[1] != "F7: Switch -> dynamicGun_CTRL 1.00":
        raise AssertionError(json.dumps(result, indent=2))
    if dynamic_parenting.get("event_items", [None, None, None])[2] != "F8: Blend -> World 0.50, dynamicGun_CTRL 0.50":
        raise AssertionError(json.dumps(result, indent=2))
    if dynamic_parenting.get("event_items", [None, None, None, None])[3] != "F11: World -> World 1.00":
        raise AssertionError(json.dumps(result, indent=2))
    contact_hold = workflow.get("contact_hold") or {}
    if len(contact_hold.get("controls") or []) != 2:
        raise AssertionError(json.dumps(result, indent=2))
    if contact_hold.get("axes") != ["x"]:
        raise AssertionError(json.dumps(result, indent=2))
    if contact_hold.get("keep_rotation"):
        raise AssertionError(json.dumps(result, indent=2))
    for frame_value in ("3", "4", "5", "6"):
        if frame_value not in {str(key) for key in (contact_hold.get("frames") or {}).keys()}:
            raise AssertionError(json.dumps(result, indent=2))
    if 2.0 not in (contact_hold.get("weight_keys") or []) or 3.0 not in (contact_hold.get("weight_keys") or []) or 6.0 not in (contact_hold.get("weight_keys") or []) or 7.0 not in (contact_hold.get("weight_keys") or []):
        raise AssertionError(json.dumps(result, indent=2))
    if 2.0 not in (contact_hold.get("mirrored_weight_keys") or []) or 3.0 not in (contact_hold.get("mirrored_weight_keys") or []) or 6.0 not in (contact_hold.get("mirrored_weight_keys") or []) or 7.0 not in (contact_hold.get("mirrored_weight_keys") or []):
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(contact_hold.get("reenabled_x", 0.0)) - float(contact_hold.get("anchor_x", 0.0))) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(contact_hold.get("disabled_x", 0.0)) - float(contact_hold.get("anchor_x", 0.0))) <= 0.01:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(contact_hold.get("rotation_after", 0.0)) - float(contact_hold.get("rotation_expected", 0.0))) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(contact_hold.get("updated_hold_x", 0.0)) - float(contact_hold.get("anchor_x", 0.0))) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(contact_hold.get("updated_release_x", 0.0)) - float(contact_hold.get("anchor_x", 0.0))) <= 0.01:
        raise AssertionError(json.dumps(result, indent=2))
    skinning_cleanup = workflow.get("skinning_cleanup") or {}
    cleaned_scale_after = skinning_cleanup.get("cleaned_scale_after") or []
    if len(cleaned_scale_after) != 3 or any(abs(value - 1.0) > 0.00001 for value in cleaned_scale_after):
        raise AssertionError(json.dumps(result, indent=2))
    if not skinning_cleanup.get("backup_transform"):
        raise AssertionError(json.dumps(result, indent=2))
    rig_scale = workflow.get("rig_scale") or {}
    if not rig_scale.get("export_group"):
        raise AssertionError(json.dumps(result, indent=2))
    if abs(float(rig_scale.get("duplicate_distance", 0.0)) - (float(rig_scale.get("source_distance", 0.0)) * 2.0)) > 0.001:
        raise AssertionError(json.dumps(result, indent=2))

    print("MAYA_LIVE_SCENE_FUNCTIONAL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
