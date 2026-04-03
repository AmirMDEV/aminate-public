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


def _matrix(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, matrix=True)


def _times(node_name, attribute):
    return cmds.keyframe(node_name, attribute=attribute, query=True, timeChange=True) or []


def _build_scene():
    root = cmds.createNode("transform", name="contactHold_root_ctrl")
    left_foot = cmds.createNode("transform", name="L_contactHold_foot_ctrl", parent=root)
    right_foot = cmds.createNode("transform", name="R_contactHold_foot_ctrl", parent=root)
    suggest_foot = cmds.createNode("transform", name="L_contactSuggest_foot_ctrl")
    cmds.xform(left_foot, objectSpace=True, translation=(2.0, 0.0, 0.0))
    cmds.xform(right_foot, objectSpace=True, translation=(-2.0, 0.0, 0.0))
    cmds.setKeyframe(root, attribute="translateX", time=1, value=0.0)
    cmds.setKeyframe(root, attribute="translateX", time=10, value=9.0)
    cmds.setKeyframe(root, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(root, attribute="rotateY", time=10, value=90.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=1, value=0.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=4, value=3.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=8, value=3.0)
    cmds.setKeyframe(suggest_foot, attribute="translateX", time=12, value=6.0)
    cmds.setKeyframe(suggest_foot, attribute="translateY", time=1, value=0.0)
    cmds.setKeyframe(suggest_foot, attribute="translateY", time=12, value=0.0)
    return root, left_foot, right_foot, suggest_foot


def run():
    cmds.file(new=True, force=True)
    _root, left_foot, right_foot, suggest_foot = _build_scene()
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
    controller.keep_rotation = True
    controller.key_before_after = True
    success, message = controller.analyze_setup()
    _assert(success, message)

    anchor_matrices = {
        left_foot: _matrix(left_foot),
        right_foot: _matrix(right_foot),
    }
    success, message = controller.apply_hold()
    _assert(success, "Contact Hold failed: {0}\n{1}".format(message, controller.report_text()))

    for frame_value in range(3, 7):
        cmds.currentTime(frame_value, edit=True)
        for node_name, anchor_matrix in anchor_matrices.items():
            held_matrix = _matrix(node_name)
            _assert(max(abs(float(anchor_matrix[index]) - float(held_matrix[index])) for index in range(16)) <= 0.001, "{0} should stay in the same world pose across the hold".format(node_name))

    for node_name in (left_foot, right_foot):
        translate_times = _times(node_name, "translateX")
        rotate_times = _times(node_name, "rotateY")
        _assert(2.0 in translate_times and 7.0 in translate_times, "{0} should add clean move keys before and after".format(node_name))
        _assert(2.0 in rotate_times and 7.0 in rotate_times, "{0} should add clean turn keys before and after".format(node_name))

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
