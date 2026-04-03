from __future__ import absolute_import, division, print_function

import importlib.util
import os
import traceback

import maya.standalone


try:
    maya.standalone.initialize(name="python")
except RuntimeError as exc:
    if "inside of Maya" not in str(exc):
        raise

import maya.cmds as cmds  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(THIS_DIR, "maya_rotation_doctor.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("maya_rotation_doctor", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _values(node, attr):
    return cmds.keyframe(node, attribute=attr, query=True, valueChange=True) or []


def _times(node, attr):
    return cmds.keyframe(node, attribute=attr, query=True, timeChange=True) or []


def build_scene():
    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    cmds.playbackOptions(minTime=1, maxTime=24)

    jump_ctrl = cmds.createNode("transform", name="jump_ctrl")
    cmds.setKeyframe(jump_ctrl, attribute="rotateX", time=1, value=179.0)
    cmds.setKeyframe(jump_ctrl, attribute="rotateX", time=12, value=-181.0)

    spin_ctrl = cmds.createNode("transform", name="spin_ctrl")
    cmds.setKeyframe(spin_ctrl, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(spin_ctrl, attribute="rotateY", time=12, value=450.0)
    cmds.setKeyframe(spin_ctrl, attribute="rotateY", time=24, value=810.0)

    gimbal_ctrl = cmds.createNode("transform", name="gimbal_ctrl")
    cmds.setKeyframe(gimbal_ctrl, attribute="rotateX", time=1, value=0.0)
    cmds.setKeyframe(gimbal_ctrl, attribute="rotateX", time=24, value=45.0)
    cmds.setKeyframe(gimbal_ctrl, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(gimbal_ctrl, attribute="rotateY", time=24, value=90.0)
    cmds.setKeyframe(gimbal_ctrl, attribute="rotateZ", time=1, value=0.0)
    cmds.setKeyframe(gimbal_ctrl, attribute="rotateZ", time=24, value=30.0)

    sync_ctrl = cmds.createNode("transform", name="sync_ctrl")
    cmds.setKeyframe(sync_ctrl, attribute="rotateX", time=1, value=0.0)
    cmds.setKeyframe(sync_ctrl, attribute="rotateX", time=24, value=25.0)
    cmds.setKeyframe(sync_ctrl, attribute="rotateY", time=1, value=0.0)
    cmds.setKeyframe(sync_ctrl, attribute="rotateY", time=24, value=20.0)
    cmds.setKeyframe(sync_ctrl, attribute="rotateZ", time=1, value=0.0)
    cmds.setKeyframe(sync_ctrl, attribute="rotateZ", time=24, value=10.0)

    untouched_ctrl = cmds.createNode("transform", name="untouched_ctrl")
    cmds.setKeyframe(untouched_ctrl, attribute="rotateX", time=1, value=5.0)
    cmds.setKeyframe(untouched_ctrl, attribute="rotateX", time=24, value=45.0)

    return jump_ctrl, spin_ctrl, gimbal_ctrl, sync_ctrl, untouched_ctrl


def run():
    module = _load_module()
    jump_ctrl, spin_ctrl, gimbal_ctrl, sync_ctrl, untouched_ctrl = build_scene()

    controller = module.MayaRotationDoctorController()
    success, message = controller.analyze_targets([jump_ctrl, spin_ctrl, gimbal_ctrl, sync_ctrl])
    _assert(success, "Analyze failed: {0}".format(message))
    _assert(len(controller.reports) == 4, "Expected 4 reports, found {0}".format(len(controller.reports)))

    reports_by_name = {report["display_name"]: report for report in controller.reports}

    jump_report = reports_by_name["jump_ctrl"]
    _assert(jump_report["has_discontinuity"], "jump_ctrl should be flagged for Euler discontinuity")
    _assert(
        jump_report["recommended_recipe"] == "clean_euler_discontinuity",
        "jump_ctrl should recommend Euler cleanup",
    )

    spin_report = reports_by_name["spin_ctrl"]
    _assert(spin_report["has_long_spin"], "spin_ctrl should be flagged for an intentional long spin")
    _assert(
        spin_report["recommended_recipe"] == "preserve_spin_and_unroll",
        "spin_ctrl should recommend preserving the spin",
    )

    gimbal_report = reports_by_name["gimbal_ctrl"]
    _assert(gimbal_report["has_gimbal_risk"], "gimbal_ctrl should show a gimbal-risk warning")
    _assert(
        gimbal_report["recommended_recipe"] == "switch_interp_to_quaternion",
        "gimbal_ctrl should recommend quaternion interpolation",
    )

    sync_report = reports_by_name["sync_ctrl"]
    _assert(sync_report["has_multi_axis_rotation"], "sync_ctrl should be treated as multi-axis rotation")
    _assert(
        sync_report["recommended_recipe"] == "switch_interp_to_synchronized_euler",
        "sync_ctrl should recommend synchronized Euler interpolation",
    )

    untouched_before = _values(untouched_ctrl, "rotateX")
    success, message = controller.apply_recipe("clean_euler_discontinuity", [jump_report])
    _assert(success, "Euler cleanup failed: {0}".format(message))
    jump_values = _values(jump_ctrl, "rotateX")
    _assert(len(jump_values) == 2, "jump_ctrl should still have 2 keys")
    _assert(abs(jump_values[1] - jump_values[0]) < 0.01, "Euler cleanup should remove the 360-degree flip")
    _assert(_values(untouched_ctrl, "rotateX") == untouched_before, "Untouched control should remain unchanged")

    success, message = controller.apply_recipe("preserve_spin_and_unroll", [spin_report])
    _assert(success, "Preserve spins failed: {0}".format(message))
    spin_values = _values(spin_ctrl, "rotateY")
    _assert(spin_values[1] > 360.0 and spin_values[2] > 720.0, "Long spin should stay unrolled and preserved")

    gimbal_times_before = {attr: list(_times(gimbal_ctrl, attr)) for attr in ("rotateX", "rotateY", "rotateZ")}
    success, message = controller.apply_recipe("switch_interp_to_quaternion", [gimbal_report])
    _assert(success, "Quaternion conversion failed: {0}".format(message))
    for attr_name, expected_times in gimbal_times_before.items():
        _assert(_times(gimbal_ctrl, attr_name) == expected_times, "Quaternion conversion must not change key timing")

    sync_times_before = {attr: list(_times(sync_ctrl, attr)) for attr in ("rotateX", "rotateY")}
    success, message = controller.apply_recipe("switch_interp_to_synchronized_euler", [sync_report])
    _assert(success, "Sync Euler conversion failed: {0}".format(message))
    for attr_name, expected_times in sync_times_before.items():
        _assert(_times(sync_ctrl, attr_name) == expected_times, "Sync Euler conversion must not change key timing")

    cmds.setKeyframe(spin_ctrl, attribute="rotateZ", time=1, value=0.0)
    cmds.setKeyframe(spin_ctrl, attribute="rotateZ", time=12, value=360.0)
    cmds.setKeyframe(spin_ctrl, attribute="rotateZ", time=24, value=720.0)
    custom_report = module._build_report(spin_ctrl)
    success, message = controller.apply_recipe("custom_continuity_pass", [custom_report])
    _assert(success, "Custom continuity pass failed: {0}".format(message))
    custom_values = _values(spin_ctrl, "rotateZ")
    _assert(abs(custom_values[1]) < 0.01 and abs(custom_values[2]) < 0.01, "Custom continuity should collapse equivalent wraps")

    print("MAYA_ROTATION_DOCTOR_SMOKE_TEST: PASS")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        print("MAYA_ROTATION_DOCTOR_SMOKE_TEST: FAIL")
