from __future__ import absolute_import, division, print_function

import os
import sys
import traceback

import maya.standalone


try:
    maya.standalone.initialize(name="python")
except RuntimeError as exc:
    if "inside of Maya" not in str(exc):
        raise

import maya.cmds as cmds  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import maya_anim_workflow_tools  # noqa: E402
import maya_contact_hold  # noqa: E402
import maya_rig_scale_export  # noqa: E402
import maya_timeline_notes  # noqa: E402
import maya_universal_ikfk_switcher  # noqa: E402
import maya_video_reference_tool  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _translation(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, translation=True)


def _matrix(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, matrix=True)


def _times(node_name, attribute):
    return cmds.keyframe(node_name, attribute=attribute, query=True, timeChange=True) or []


def _enabled_times(locator_node):
    payload = maya_contact_hold._hold_payload(locator_node)
    _assert(payload and payload.get("enabled_attr"), "Contact Hold should create a live enabled payload")
    return cmds.keyframe(payload["enabled_attr"], query=True, timeChange=True) or []


def _shader_group(shader_name):
    shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader_name + "SG")
    cmds.connectAttr(shader_name + ".outColor", shading_group + ".surfaceShader", force=True)
    return shading_group


def _long_name(node_name):
    return (cmds.ls(node_name, long=True) or [node_name])[0]


def _build_parenting_scene():
    hand_target = cmds.createNode("transform", name="hand_ctrl")
    gun_target = cmds.createNode("transform", name="gun_ctrl")
    driven_a = cmds.createNode("transform", name="drivenA_ctrl")
    driven_b = cmds.createNode("transform", name="drivenB_ctrl")
    cmds.xform(hand_target, worldSpace=True, translation=(8.0, 0.0, 0.0))
    cmds.xform(gun_target, worldSpace=True, translation=(14.0, 2.0, 0.0))
    cmds.xform(driven_a, worldSpace=True, translation=(0.0, 1.0, 0.0))
    cmds.xform(driven_b, worldSpace=True, translation=(0.0, 3.0, 0.0))
    return hand_target, gun_target, driven_a, driven_b


def _build_ikfk_scene():
    shoulder_fk = cmds.createNode("transform", name="L_arm_shoulder_fk_ctrl")
    elbow_fk = cmds.createNode("transform", name="L_arm_elbow_fk_ctrl")
    wrist_fk = cmds.createNode("transform", name="L_arm_wrist_fk_ctrl")
    cmds.parent(elbow_fk, shoulder_fk)
    cmds.parent(wrist_fk, elbow_fk)
    cmds.xform(shoulder_fk, worldSpace=True, translation=(0.0, 10.0, 0.0))
    cmds.xform(elbow_fk, worldSpace=True, translation=(5.0, 12.0, 0.0))
    cmds.xform(wrist_fk, worldSpace=True, translation=(9.0, 14.0, 0.0))

    shoulder_drv = cmds.createNode("transform", name="L_arm_shoulder_drv")
    elbow_drv = cmds.createNode("transform", name="L_arm_elbow_drv")
    wrist_drv = cmds.createNode("transform", name="L_arm_wrist_drv")
    cmds.parent(elbow_drv, shoulder_drv)
    cmds.parent(wrist_drv, elbow_drv)
    cmds.xform(shoulder_drv, worldSpace=True, translation=(0.0, 10.0, 0.0))
    cmds.xform(elbow_drv, worldSpace=True, translation=(4.0, 12.0, 0.0))
    cmds.xform(wrist_drv, worldSpace=True, translation=(8.0, 14.0, 0.0))

    ik_ctrl = cmds.createNode("transform", name="L_arm_ik_ctrl")
    pv_ctrl = cmds.createNode("transform", name="L_arm_pv_ctrl")
    settings = cmds.createNode("transform", name="L_arm_settings_ctrl")
    cmds.addAttr(settings, longName="leftArm_ikfk", attributeType="double")

    return {
        "fk_controls": [shoulder_fk, elbow_fk, wrist_fk],
        "match_nodes": [shoulder_drv, elbow_drv, wrist_drv],
        "ik_control": ik_ctrl,
        "pole_vector_control": pv_ctrl,
        "switch_attr": settings + ".leftArm_ikfk",
    }


def _build_skin_cleanup_scene():
    root_joint = cmds.createNode("joint", name="skinCleanup_root_jnt")
    mid_joint = cmds.createNode("joint", name="skinCleanup_mid_jnt", parent=root_joint)
    cmds.xform(root_joint, worldSpace=True, translation=(14.0, 0.0, 0.0))
    cmds.xform(mid_joint, worldSpace=True, translation=(14.0, 4.0, 0.0))

    mesh = cmds.polyCube(
        name="skinCleanup_badScale_geo",
        width=2.0,
        height=3.0,
        depth=1.5,
        subdivisionsY=2,
    )[0]
    cmds.xform(mesh, worldSpace=True, translation=(16.0, 1.0, -2.0), rotation=(10.0, 25.0, 5.0), scale=(1.8, 0.7, 1.3))
    cmds.polySoftEdge(mesh, angle=180, constructionHistory=False)
    cmds.polySoftEdge(mesh + ".e[0:3]", angle=0, constructionHistory=False)

    shader_a = cmds.shadingNode("lambert", asShader=True, name="skinCleanup_red")
    shader_b = cmds.shadingNode("lambert", asShader=True, name="skinCleanup_blue")
    sg_a = _shader_group(shader_a)
    sg_b = _shader_group(shader_b)
    cmds.sets(mesh + ".f[0:2]", edit=True, forceElement=sg_a)
    cmds.sets(mesh + ".f[3:5]", edit=True, forceElement=sg_b)

    skin_cluster = cmds.skinCluster([root_joint, mid_joint], mesh, toSelectedBones=True, name="skinCleanup_skinCluster")[0]
    cmds.skinPercent(skin_cluster, mesh + ".vtx[0:3]", transformValue=[(root_joint, 1.0), (mid_joint, 0.0)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[4:7]", transformValue=[(root_joint, 0.5), (mid_joint, 0.5)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[8:11]", transformValue=[(root_joint, 0.1), (mid_joint, 0.9)])
    return mesh


def _build_rig_scale_scene():
    rig_group = cmds.createNode("transform", name="combinedRigScale_source_GRP")
    cmds.setAttr(rig_group + ".scaleX", 1.5)
    cmds.setAttr(rig_group + ".scaleY", 1.5)
    cmds.setAttr(rig_group + ".scaleZ", 1.5)

    root_joint = cmds.createNode("joint", name="combinedRigScale_root_jnt", parent=rig_group)
    mid_joint = cmds.createNode("joint", name="combinedRigScale_mid_jnt", parent=root_joint)
    cmds.setAttr(root_joint + ".translateX", 20.0)
    cmds.setAttr(root_joint + ".translateY", 4.0)
    cmds.setAttr(mid_joint + ".translateY", 4.0)

    mesh = cmds.polyCube(name="combinedRigScale_geo", width=2.0, height=4.0, depth=1.5, subdivisionsY=2)[0]
    mesh = cmds.parent(mesh, rig_group)[0]
    cmds.xform(mesh, objectSpace=True, translation=(20.0, 2.0, 0.0))
    skin_cluster = cmds.skinCluster([root_joint, mid_joint], mesh, toSelectedBones=True, name="combinedRigScale_skinCluster")[0]
    cmds.skinPercent(skin_cluster, mesh + ".vtx[0:3]", transformValue=[(root_joint, 1.0), (mid_joint, 0.0)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[4:7]", transformValue=[(root_joint, 0.5), (mid_joint, 0.5)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[8:11]", transformValue=[(root_joint, 0.1), (mid_joint, 0.9)])
    return rig_group, root_joint, mid_joint


def _build_contact_hold_scene():
    root = cmds.createNode("transform", name="contactHold_root_ctrl")
    left_foot = cmds.createNode("transform", name="L_contactHold_foot_ctrl", parent=root)
    right_foot = cmds.createNode("transform", name="R_contactHold_foot_ctrl", parent=root)
    cmds.xform(left_foot, objectSpace=True, translation=(2.0, 0.0, 0.0))
    cmds.xform(right_foot, objectSpace=True, translation=(-2.0, 0.0, 0.0))
    cmds.setKeyframe(root, attribute="translateX", time=1, value=0.0)
    cmds.setKeyframe(root, attribute="translateX", time=10, value=9.0)
    cmds.setKeyframe(root, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(root, attribute="rotateY", time=10, value=90.0)
    cmds.setKeyframe(left_foot, attribute="rotateX", time=3, value=0.0)
    cmds.setKeyframe(left_foot, attribute="rotateX", time=6, value=-35.0)
    cmds.setKeyframe(right_foot, attribute="rotateX", time=3, value=0.0)
    cmds.setKeyframe(right_foot, attribute="rotateX", time=6, value=-30.0)
    return root, left_foot, right_foot


def run():
    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    cmds.playbackOptions(minTime=1, maxTime=24, animationStartTime=1, animationEndTime=24)

    controller = maya_anim_workflow_tools.MayaAnimWorkflowController()

    hand_target, gun_target, driven_a, driven_b = _build_parenting_scene()
    parenting_controller = controller.dynamic_parenting_controller
    _assert(parenting_controller is not None, "Dynamic Parenting controller should exist in the combined tool")
    cmds.currentTime(8, edit=True)
    cmds.select([driven_a, driven_b], replace=True)
    success, message = parenting_controller.add_driven_from_selection()
    _assert(success, message)
    payloads = parenting_controller.setup_payloads(from_selection=False)
    _assert(len(payloads) == 2, "Expected two scene-backed parenting setups")
    setup_lookup = {item["driven"]: item for item in payloads}
    success, message = parenting_controller.set_active_setup(setup_lookup[_long_name(driven_a)]["setup_group"])
    _assert(success, message)

    before_first_switch = _translation(driven_a)
    cmds.select([driven_a, hand_target], replace=True)
    success, message = parenting_controller.set_pending_target_from_selection()
    _assert(success, message)
    success, message = parenting_controller.apply_pending_target()
    _assert(success, message)
    after_first_switch = _translation(driven_a)
    _assert(all(abs(before_first_switch[index] - after_first_switch[index]) < 0.01 for index in range(3)), "Switching to the hand target should preserve the driven control position")
    first_blend_values = maya_dynamic_parenting_tool._get_blend_attr_values(driven_a)
    _assert(first_blend_values and all(abs(float(value) - 1.0) < 0.001 for value in first_blend_values.values()), "Driven blendParent attrs should turn on after the first switch")
    driven_a_setup = parenting_controller.current_setup()
    current_weights = parenting_controller.current_weights(driven_a_setup)
    hand_target_entry = next(target for target in driven_a_setup["targets"] if target["driver"] == _long_name(hand_target))
    _assert(abs(current_weights.get(hand_target_entry["id"], 0.0) - 1.0) < 0.001, "Driven A should fully follow the hand target after the first switch")

    cmds.currentTime(10, edit=True)
    before_switch = _translation(driven_a)
    cmds.select([driven_a, gun_target], replace=True)
    success, message = parenting_controller.set_pending_target_from_selection()
    _assert(success, message)
    success, message = parenting_controller.apply_pending_target()
    _assert(success, message)
    after_switch = _translation(driven_a)
    _assert(all(abs(before_switch[index] - after_switch[index]) < 0.01 for index in range(3)), "Switching targets should preserve the driven control position")
    second_blend_values = maya_dynamic_parenting_tool._get_blend_attr_values(driven_a)
    _assert(second_blend_values and all(abs(float(value) - 1.0) < 0.001 for value in second_blend_values.values()), "Driven blendParent attrs should stay on after later switches")
    driven_a_setup = parenting_controller.current_setup()
    current_weights = parenting_controller.current_weights(driven_a_setup)
    gun_target_entry = next(target for target in driven_a_setup["targets"] if target["driver"] == _long_name(gun_target))
    _assert(abs(current_weights.get(gun_target_entry["id"], 0.0) - 1.0) < 0.001, "Driven A should fully follow the gun target after the second switch")

    cmds.currentTime(12, edit=True)
    success, message = parenting_controller.apply_weight_map(
        {
            "world": 0.5,
            gun_target_entry["id"]: 0.5,
            hand_target_entry["id"]: 0.0,
        },
        action_label="blend",
    )
    _assert(success, message)
    current_weights = parenting_controller.current_weights(parenting_controller.current_setup())
    _assert(abs(current_weights.get("world", 0.0) - 0.5) < 0.001, "World should be half-on in the blend step")
    _assert(abs(current_weights.get(gun_target_entry["id"], 0.0) - 0.5) < 0.001, "Gun should be half-on in the blend step")

    cmds.currentTime(13, edit=True)
    success, message = parenting_controller.parent_to_world()
    _assert(success, message)
    current_weights = parenting_controller.current_weights(parenting_controller.current_setup())
    _assert(abs(current_weights.get("world", 0.0) - 1.0) < 0.001, "World should be fully on after the world switch")
    driven_a_events = parenting_controller.event_items(parenting_controller.current_setup())
    _assert(len(driven_a_events) == 4, "Driven A should have hand, gun, blend, and world events saved")
    _assert(driven_a_events[0]["display"] == "F9: Switch -> hand_ctrl 1.00", "First dynamic-parenting event should switch to the hand on the next frame")
    _assert(driven_a_events[1]["display"] == "F11: Switch -> gun_ctrl 1.00", "Second dynamic-parenting event should switch to the gun on the next frame")
    _assert(driven_a_events[2]["display"] == "F12: Blend -> World 0.50, gun_ctrl 0.50", "Third dynamic-parenting event should save the weight blend")
    _assert(driven_a_events[3]["display"] == "F14: World -> World 1.00", "Fourth dynamic-parenting event should return to world on the next frame")

    pivot_a = cmds.createNode("transform", name="pivotA_ctrl")
    pivot_b = cmds.createNode("transform", name="pivotB_ctrl")
    cmds.xform(pivot_b, worldSpace=True, translation=(4.0, 0.0, 0.0))
    cmds.select([pivot_a, pivot_b], replace=True)
    success, message = controller.create_pivot("centered")
    _assert(success, message)
    cmds.xform(controller.active_pivot, worldSpace=True, translation=(0.0, 2.0, 0.0))
    cmds.setAttr(controller.active_pivot + ".rotateY", 90.0)
    success, message = controller.apply_pivot_rotation()
    _assert(success, message)
    moved = _translation(pivot_b)
    _assert(abs(moved[0] - 0.0) < 0.01 and abs(moved[2] + 4.0) < 0.01, "Pivot rotation should respect a repositioned pivot")
    active_pivot = controller.active_pivot
    success, message = controller.clear_pivot()
    _assert(success, message)
    _assert(not active_pivot or not cmds.objExists(active_pivot), "Pivot control should be removed on clear")

    ikfk_nodes = _build_ikfk_scene()
    cmds.select(ikfk_nodes["fk_controls"], replace=True)
    detected_profile, issues = controller.detect_profile()
    _assert(detected_profile["ik_control"].endswith("L_arm_ik_ctrl"), "IK control should be auto-detected")
    _assert(detected_profile["switch_attr"].endswith(".leftArm_ikfk"), "Switch attribute should be auto-detected")
    _assert(len(detected_profile["fk_controls"]) == 3, "All FK controls should be auto-detected")
    _assert(any(item.endswith("L_arm_ik_ctrl") for item in detected_profile.get("ik_controls", [])), "IK controllers should include the IK end control")
    _assert(any(item.endswith("L_arm_pv_ctrl") for item in detected_profile.get("ik_controls", [])), "IK controllers should include the pole vector control")
    _assert(not issues, "Expected a clean profile detection, got: {0}".format(issues))

    detected_profile["profile_name"] = "left_arm_profile"
    success, message = controller.save_profile(detected_profile)
    _assert(success, message)
    success, loaded_profile = controller.load_profile("left_arm_profile")
    _assert(success, loaded_profile)
    _assert(any(item.endswith("L_arm_ik_ctrl") for item in loaded_profile.get("ik_controls", [])), "Saved profiles should persist IK controller lists")
    _assert(any(item.endswith("L_arm_pv_ctrl") for item in loaded_profile.get("ik_controls", [])), "Saved profiles should persist pole-vector membership")

    cmds.currentTime(12, edit=True)
    success, message = controller.switch_fk_to_ik(loaded_profile)
    _assert(success, message)
    ik_position = _translation(ikfk_nodes["ik_control"])
    _assert(abs(ik_position[0] - 8.0) < 0.01 and abs(ik_position[1] - 14.0) < 0.01, "IK control should match end effector")
    switch_times = _times(ikfk_nodes["switch_attr"].split(".", 1)[0], "leftArm_ikfk")
    _assert(11.0 in switch_times and 12.0 in switch_times, "Switch attribute should be keyed on frame-1 and frame")

    success, message = controller.switch_ik_to_fk(loaded_profile)
    _assert(success, message)
    switch_times = _times(ikfk_nodes["switch_attr"].split(".", 1)[0], "leftArm_ikfk")
    _assert(11.0 in switch_times and 12.0 in switch_times, "IK -> FK should keep frame-1 and frame keys")

    cleanup_mesh = _build_skin_cleanup_scene()
    skin_controller = controller.skinning_controller
    _assert(skin_controller is not None, "Skinning Cleanup controller should exist in the combined tool")
    cmds.select(cleanup_mesh, replace=True)
    success, message = skin_controller.analyze_selection()
    _assert(success, message)
    _assert(not skin_controller.report["errors"], skin_controller.report_text())
    source_scale = cmds.getAttr(cleanup_mesh + ".scale")[0]
    success, message = skin_controller.create_clean_copy()
    _assert(success, "Skinning Cleanup create failed: {0}\n{1}".format(message, skin_controller.report_text()))
    _assert(skin_controller.result["verified"], skin_controller.report_text())
    clean_scale = cmds.getAttr(skin_controller.result["clean_transform"] + ".scale")[0]
    _assert(all(abs(value - 1.0) <= 0.00001 for value in clean_scale), "Skinning Cleanup copy should freeze scale to 1,1,1")
    _assert(any(abs(source_scale[index] - 1.0) > 0.001 for index in range(3)), "Skinning Cleanup should keep the original bad scale until replace")
    success, message = skin_controller.delete_clean_copy()
    _assert(success, message)

    rig_group, rig_root, rig_mid = _build_rig_scale_scene()
    rig_scale_controller = controller.rig_scale_controller
    _assert(rig_scale_controller is not None, "Rig Scale controller should exist in the combined tool")
    rig_scale_controller.character_root = rig_group
    rig_scale_controller.skeleton_root = rig_root
    rig_scale_controller.scale_factor = 2.0
    source_rig_root_long = maya_rig_scale_export._node_long_name(rig_root)
    source_rig_mid_long = maya_rig_scale_export._node_long_name(rig_mid)
    success, message = rig_scale_controller.analyze_setup()
    _assert(success, message)
    _assert(not rig_scale_controller.report["errors"], rig_scale_controller.report_text())
    source_root = _translation(rig_root)
    source_mid = _translation(rig_mid)
    source_distance = ((source_root[0] - source_mid[0]) ** 2 + (source_root[1] - source_mid[1]) ** 2 + (source_root[2] - source_mid[2]) ** 2) ** 0.5
    success, message = rig_scale_controller.create_export_copy()
    _assert(success, "Rig Scale create failed: {0}\n{1}".format(message, rig_scale_controller.report_text()))
    _assert(rig_scale_controller.result["verified"], rig_scale_controller.report_text())
    duplicate_root = rig_scale_controller.result["joint_map"][source_rig_root_long]
    duplicate_mid = rig_scale_controller.result["joint_map"][source_rig_mid_long]
    duplicate_scale = cmds.getAttr(duplicate_root + ".scale")[0]
    _assert(all(abs(value - 1.0) <= 0.00001 for value in duplicate_scale), "Rig Scale joints should stay at 1,1,1 scale")
    duplicate_root_position = _translation(duplicate_root)
    duplicate_mid_position = _translation(duplicate_mid)
    duplicate_distance = ((duplicate_root_position[0] - duplicate_mid_position[0]) ** 2 + (duplicate_root_position[1] - duplicate_mid_position[1]) ** 2 + (duplicate_root_position[2] - duplicate_mid_position[2]) ** 2) ** 0.5
    _assert(abs(duplicate_distance - (source_distance * 2.0)) <= 0.001, "Rig Scale should scale bone lengths from the current visible size")
    success, message = rig_scale_controller.delete_export_copy()
    _assert(success, message)

    hold_root, hold_left_foot, hold_right_foot = _build_contact_hold_scene()
    contact_hold_controller = controller.contact_hold_controller
    _assert(contact_hold_controller is not None, "Contact Hold controller should exist in the combined tool")
    cmds.currentTime(3, edit=True)
    cmds.select(hold_left_foot, replace=True)
    success, message = contact_hold_controller.set_controls_from_selection()
    _assert(success, message)
    success, message = contact_hold_controller.add_matching_other_side()
    _assert(success, message)
    expected_hold_controls = [
        maya_contact_hold._node_long_name(hold_left_foot),
        maya_contact_hold._node_long_name(hold_right_foot),
    ]
    _assert(contact_hold_controller.control_nodes == expected_hold_controls, "Contact Hold should add the matching other-side foot")
    contact_hold_controller.start_frame = 3
    contact_hold_controller.end_frame = 6
    contact_hold_controller.keep_rotation = False
    contact_hold_controller.hold_axes = ("x",)
    success, message = contact_hold_controller.analyze_setup()
    _assert(success, message)
    anchor_x = {
        hold_left_foot: float(_translation(hold_left_foot)[0]),
        hold_right_foot: float(_translation(hold_right_foot)[0]),
    }
    cmds.currentTime(3, edit=True)
    start_rotate_x = float(cmds.getAttr(hold_left_foot + ".rotateX"))
    cmds.currentTime(6, edit=True)
    end_rotate_x = float(cmds.getAttr(hold_left_foot + ".rotateX"))
    _assert(abs(end_rotate_x - start_rotate_x) > 0.01, "Contact Hold smoke scene should keep visible foot rotation animation")
    success, message = contact_hold_controller.apply_hold()
    _assert(success, "Contact Hold failed: {0}\n{1}".format(message, contact_hold_controller.report_text()))
    for node_name in (hold_left_foot, hold_right_foot):
        locator_node = maya_contact_hold._find_hold_locator(node_name)
        payload = maya_contact_hold._hold_payload(locator_node)
        _assert(payload is not None, "Contact Hold should save a live hold payload")
        _assert(payload["axes"] == ("x",), "Contact Hold should store the chosen world axis")
        _assert(not payload["keep_rotation"], "Contact Hold should leave rotation free in this test")
        enabled_times = _enabled_times(locator_node)
        _assert(2.0 in enabled_times and 3.0 in enabled_times and 6.0 in enabled_times and 7.0 in enabled_times, "Contact Hold should key only the live hold boundary frames")

    cmds.setKeyframe(hold_root, attribute="translateX", time=10, value=18.0)
    for frame_value in range(3, 7):
        cmds.currentTime(frame_value, edit=True)
        for node_name, anchor_value in anchor_x.items():
            held_x = float(_translation(node_name)[0])
            _assert(abs(held_x - anchor_value) <= 0.001, "Held control should stay on the same chosen world axis while the live hold is enabled")
    cmds.currentTime(6, edit=True)
    _assert(abs(float(cmds.getAttr(hold_left_foot + ".rotateX")) - end_rotate_x) <= 0.001, "Contact Hold should not freeze the original foot rotation when Keep Turn Too is off")

    success, message = contact_hold_controller.disable_hold()
    _assert(success, message)
    cmds.currentTime(6, edit=True)
    _assert(abs(float(_translation(hold_left_foot)[0]) - anchor_x[hold_left_foot]) > 0.01, "Disabling Contact Hold should restore the original moving axis motion")

    success, message = contact_hold_controller.enable_hold()
    _assert(success, message)
    cmds.currentTime(6, edit=True)
    _assert(abs(float(_translation(hold_left_foot)[0]) - anchor_x[hold_left_foot]) <= 0.001, "Re-enabling Contact Hold should restore the saved held axis motion")

    contact_hold_controller.set_selected_hold_locators(
        [
            maya_contact_hold._find_hold_locator(hold_left_foot),
            maya_contact_hold._find_hold_locator(hold_right_foot),
        ]
    )
    contact_hold_controller.end_frame = 5
    success, message = contact_hold_controller.update_selected_hold()
    _assert(success, message)
    cmds.currentTime(5, edit=True)
    _assert(abs(float(_translation(hold_left_foot)[0]) - anchor_x[hold_left_foot]) <= 0.001, "Updated Contact Hold should still keep the chosen axis locked inside the new range")
    cmds.currentTime(6, edit=True)
    _assert(abs(float(_translation(hold_left_foot)[0]) - anchor_x[hold_left_foot]) > 0.01, "Updated Contact Hold should stop affecting frames after the new end frame")

    _assert(hasattr(maya_rig_scale_export, "launch_maya_rig_scale_export"), "Rig Scale wrapper entrypoint missing")
    _assert(hasattr(maya_universal_ikfk_switcher, "launch_maya_universal_ikfk_switcher"), "IK/FK wrapper entrypoint missing")
    _assert(hasattr(maya_video_reference_tool, "launch_maya_video_reference"), "Video Reference entrypoint missing")
    _assert(hasattr(maya_timeline_notes, "launch_maya_timeline_notes"), "Timeline Notes entrypoint missing")

    print("MAYA_ANIM_WORKFLOW_TOOLS_SMOKE_TEST: PASS")


if __name__ == "__main__":
    exit_code = 0
    try:
        run()
    except Exception:
        exit_code = 1
        traceback.print_exc()
        print("MAYA_ANIM_WORKFLOW_TOOLS_SMOKE_TEST: FAIL")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        os._exit(exit_code)
