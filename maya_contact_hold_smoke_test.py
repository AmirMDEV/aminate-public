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

import maya_contact_hold  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _world_translation(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, translation=True) or [0.0, 0.0, 0.0]


def _enabled_times(locator_node):
    payload = maya_contact_hold._hold_payload(locator_node)
    _assert(payload and payload.get("enabled_attr"), "Hold payload should expose the live enabled attribute")
    return cmds.keyframe(payload["enabled_attr"], query=True, timeChange=True) or []


def _build_scene():
    root = cmds.createNode("transform", name="contactHold_root_ctrl")
    left_foot = cmds.createNode("transform", name="L_contactHold_foot_ctrl", parent=root)
    right_foot = cmds.createNode("transform", name="R_contactHold_foot_ctrl", parent=root)
    suggest_foot = cmds.createNode("transform", name="L_contactSuggest_foot_ctrl")
    cmds.xform(left_foot, objectSpace=True, translation=(2.0, 0.0, 0.0))
    cmds.xform(right_foot, objectSpace=True, translation=(-2.0, 0.0, 0.0))
    cmds.setKeyframe(root, attribute="translateZ", time=1, value=0.0)
    cmds.setKeyframe(root, attribute="translateZ", time=10, value=9.0)
    cmds.setKeyframe(root, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(root, attribute="rotateY", time=10, value=45.0)
    cmds.setKeyframe(left_foot, attribute="rotateX", time=3, value=0.0)
    cmds.setKeyframe(left_foot, attribute="rotateX", time=6, value=-35.0)
    cmds.setKeyframe(right_foot, attribute="rotateX", time=3, value=0.0)
    cmds.setKeyframe(right_foot, attribute="rotateX", time=6, value=-30.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=1, value=0.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=4, value=3.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=8, value=3.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=12, value=6.0)
    cmds.setKeyframe(suggest_foot, attribute="translateY", time=1, value=0.0)
    cmds.setKeyframe(suggest_foot, attribute="translateY", time=12, value=0.0)
    return root, left_foot, right_foot, suggest_foot


def run():
    cmds.file(new=True, force=True)
    root, left_foot, right_foot, suggest_foot = _build_scene()
    cmds.playbackOptions(minTime=1, maxTime=12)

    controller = maya_contact_hold.MayaContactHoldController()
    cmds.currentTime(3, edit=True)
    cmds.select(left_foot, replace=True)
    success, message = controller.set_controls_from_selection()
    _assert(success, message)
    success, message = controller.add_matching_other_side()
    _assert(success, message)
    expected_controls = [
        maya_contact_hold._node_long_name(left_foot),
        maya_contact_hold._node_long_name(right_foot),
    ]
    _assert(controller.control_nodes == expected_controls, "Mirror helper should add the matching other-side foot")

    controller.start_frame = 3
    controller.end_frame = 6
    controller.keep_rotation = False
    controller.hold_axes = ("z",)
    success, message = controller.analyze_setup()
    _assert(success, message)

    anchor_z = {}
    for node_name in (left_foot, right_foot):
        anchor_z[node_name] = float(_world_translation(node_name)[2])
    cmds.currentTime(3, edit=True)
    start_rotate_x = float(cmds.getAttr(left_foot + ".rotateX"))
    cmds.currentTime(6, edit=True)
    end_rotate_x = float(cmds.getAttr(left_foot + ".rotateX"))
    _assert(abs(end_rotate_x - start_rotate_x) > 0.01, "The test scene should have visible foot rotation across the planted range")

    success, message = controller.apply_hold()
    _assert(success, "Live hold create failed: {0}\n{1}".format(message, controller.report_text()))

    for node_name in (left_foot, right_foot):
        locator_node = maya_contact_hold._find_hold_locator(node_name)
        payload = maya_contact_hold._hold_payload(locator_node)
        _assert(payload is not None, "A live hold locator should be created for each picked control")
        _assert(payload["axes"] == ("z",), "The live hold should store the chosen world axis")
        _assert(not payload["keep_rotation"], "Keep rotation should stay off in this test")
        enabled_times = _enabled_times(locator_node)
        _assert(2.0 in enabled_times and 3.0 in enabled_times and 6.0 in enabled_times and 7.0 in enabled_times, "Live hold should key only the boundary on/off frames")

    cmds.setKeyframe(root, attribute="translateZ", time=10, value=20.0)
    for frame_value in range(3, 7):
        cmds.currentTime(frame_value, edit=True)
        for node_name in (left_foot, right_foot):
            held_z = float(_world_translation(node_name)[2])
            _assert(abs(held_z - anchor_z[node_name]) <= 0.001, "{0} should keep the same world Z while the live hold is on".format(node_name))
    cmds.currentTime(6, edit=True)
    _assert(abs(float(cmds.getAttr(left_foot + ".rotateX")) - end_rotate_x) <= 0.001, "Live hold should keep the original foot rotation animation when Keep Turn Too is off")

    success, message = controller.disable_hold()
    _assert(success, message)
    cmds.currentTime(6, edit=True)
    _assert(abs(float(_world_translation(left_foot)[2]) - anchor_z[left_foot]) > 0.01, "Disabling the hold should restore the original moving Z motion")

    success, message = controller.enable_hold()
    _assert(success, message)
    cmds.currentTime(6, edit=True)
    _assert(abs(float(_world_translation(left_foot)[2]) - anchor_z[left_foot]) <= 0.001, "Re-enabling the hold should restore the saved held Z motion")

    controller.set_selected_hold_locators(
        [
            maya_contact_hold._find_hold_locator(left_foot),
            maya_contact_hold._find_hold_locator(right_foot),
        ]
    )
    controller.end_frame = 5
    success, message = controller.update_selected_hold()
    _assert(success, message)
    cmds.currentTime(5, edit=True)
    _assert(abs(float(_world_translation(left_foot)[2]) - anchor_z[left_foot]) <= 0.001, "Updated hold should still keep the chosen axis locked inside the new range")
    cmds.currentTime(6, edit=True)
    _assert(abs(float(_world_translation(left_foot)[2]) - anchor_z[left_foot]) > 0.01, "Updated hold should stop affecting frames after the new end frame")

    cmds.select(left_foot, replace=True)
    success, message = controller.set_controls_from_selection()
    _assert(success, message)
    controller.start_frame = 8
    controller.end_frame = 9
    controller.keep_rotation = False
    controller.hold_axes = ("z",)
    success, message = controller.apply_hold()
    _assert(success, message)
    left_entries = maya_contact_hold._hold_entries_for_control(left_foot)
    _assert(len(left_entries) == 2, "Left foot should be able to store more than one saved hold row")

    controller.set_selected_hold_locators(left_entries)
    success, message = controller.load_selected_hold()
    _assert(success, message)
    success, message = controller.set_control_list_name("Left Foot Friendly")
    _assert(success, message)
    renamed_payloads = [maya_contact_hold._hold_payload(item) for item in maya_contact_hold._hold_entries_for_control(left_foot)]
    _assert(all(item["list_name"] == "Left Foot Friendly" for item in renamed_payloads), "Friendly list rename should update every saved row for the same control")

    controller.set_selected_hold_locators([left_entries[0]])
    success, message = controller.delete_hold()
    _assert(success, message)
    _assert(len(maya_contact_hold._hold_entries_for_control(left_foot)) == 1, "Deleting one saved row should leave the other hold rows alone")

    success, message = controller.delete_all_holds()
    _assert(success, message)
    _assert(not maya_contact_hold._find_hold_locator(left_foot), "Deleting all holds should remove saved left-foot locators")
    _assert(not maya_contact_hold._find_hold_locator(right_foot), "Deleting all holds should remove saved right-foot locators")

    suggest_controller = maya_contact_hold.MayaContactHoldController()
    cmds.currentTime(6, edit=True)
    cmds.select(suggest_foot, replace=True)
    success, message = suggest_controller.set_controls_from_selection()
    _assert(success, message)
    suggest_controller.keep_rotation = False
    success, message = suggest_controller.suggest_range()
    _assert(success, message)
    _assert(suggest_controller.start_frame == 4, "Suggest Range should find the planted start frame")
    _assert(suggest_controller.end_frame == 8, "Suggest Range should find the planted end frame")

    print("MAYA_CONTACT_HOLD_SMOKE_TEST: PASS")


if __name__ == "__main__":
    exit_code = 0
    try:
        run()
    except Exception:
        exit_code = 1
        traceback.print_exc()
        print("MAYA_CONTACT_HOLD_SMOKE_TEST: FAIL")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        os._exit(exit_code)
