from __future__ import absolute_import, division, print_function

import importlib.util
import json
import os
import time
import traceback

import maya.cmds as cmds
import maya.utils

try:
    from PySide6 import QtWidgets
except Exception:
    try:
        from PySide2 import QtWidgets
    except Exception:
        QtWidgets = None


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(THIS_DIR, "maya_onion_skin.py")
RESULT_PATH = os.path.join(THIS_DIR, "maya_onion_skin_gui_perf_result.json")


def _load_module():
    spec = importlib.util.spec_from_file_location("maya_onion_skin", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_result(payload):
    with open(RESULT_PATH, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _pump_events(seconds):
    app = QtWidgets.QApplication.instance() if QtWidgets else None
    end_time = time.time() + seconds
    while time.time() < end_time:
        if app:
            app.processEvents()
        time.sleep(0.01)


def _wait_for(predicate, timeout_seconds):
    app = QtWidgets.QApplication.instance() if QtWidgets else None
    end_time = time.time() + timeout_seconds
    while time.time() < end_time:
        if predicate():
            return True
        if app:
            app.processEvents()
        time.sleep(0.02)
    return bool(predicate())


def _build_scene():
    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    cmds.playbackOptions(minTime=1, maxTime=36)

    root = cmds.group(empty=True, name="perf_char_root")
    body = cmds.polyCube(name="perf_body_geo", width=2.2, height=3.2, depth=1.2)[0]
    head = cmds.polySphere(name="perf_head_geo", radius=0.9)[0]
    shoulder = cmds.polyCube(name="perf_shoulder_geo", width=3.4, height=0.7, depth=0.8)[0]

    cmds.parent(body, root)
    cmds.parent(head, root)
    cmds.parent(shoulder, root)
    cmds.move(0, 2.8, 0, head, absolute=True)
    cmds.move(0, 1.8, 0, shoulder, absolute=True)

    bend_deformer, bend_handle = cmds.nonLinear(body, type="bend", lowBound=-1, highBound=1)
    cmds.parent(bend_handle, root)
    cmds.setAttr(bend_handle + ".rotateZ", 90)

    twist_deformer, twist_handle = cmds.nonLinear(shoulder, type="twist", lowBound=-1, highBound=1)
    cmds.parent(twist_handle, root)
    cmds.setAttr(twist_handle + ".rotateX", 90)

    cmds.setKeyframe(root, attribute="translateX", time=1, value=-4.0)
    cmds.setKeyframe(root, attribute="translateX", time=18, value=0.0)
    cmds.setKeyframe(root, attribute="translateX", time=36, value=4.0)

    cmds.setKeyframe(bend_deformer, attribute="curvature", time=1, value=-45.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=18, value=0.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=36, value=45.0)

    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=1, value=-25.0)
    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=18, value=0.0)
    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=36, value=25.0)

    cmds.currentTime(18, edit=True, update=True)
    cmds.select(root, replace=True)
    return root


def _quit_maya():
    try:
        cmds.quit(force=True)
    except Exception:
        pass


def _run():
    result = {"status": "fail", "details": {}}

    try:
        module = _load_module()
        root = _build_scene()
        window = module.launch_maya_onion_skin(dock=False)
        controller = window.controller
        controller.set_settings(
            past_frames=12,
            future_frames=12,
            opacity=0.55,
            falloff=1.35,
            auto_update=True,
            full_fidelity_scrub=False,
            past_color=(0.25, 0.7, 1.0),
            future_color=(1.0, 0.55, 0.2),
        )

        success, message = controller.attach_selection()
        if not success:
            raise RuntimeError(message)

        _pump_events(0.2)
        baseline_count = controller._completed_refresh_count
        baseline_duration = controller._last_refresh_duration_ms

        for frame in range(1, 37):
            cmds.currentTime(frame, edit=True, update=True)

        burst_count = controller._completed_refresh_count
        queued_after_burst = controller._refresh_pending

        drained = _wait_for(
            lambda: not controller._refresh_pending and not controller._updating,
            timeout_seconds=5.0,
        )
        final_count = controller._completed_refresh_count
        callback_refresh_delta = final_count - burst_count

        expected_offsets = controller.past_frames + controller.future_frames
        if not drained:
            raise RuntimeError("Queued GUI refresh did not drain in time.")
        if len(controller.ghost_cache) != expected_offsets:
            raise RuntimeError(
                "Expected {0} ghost offsets, found {1}.".format(
                    expected_offsets,
                    len(controller.ghost_cache),
                )
            )
        if callback_refresh_delta > 4:
            raise RuntimeError(
                "Expected scrub burst to coalesce into a handful of refreshes, observed {0}.".format(
                    callback_refresh_delta
                )
            )

        result["status"] = "pass"
        result["details"] = {
            "scene_root": root,
            "qt_binding": module.QT_BINDING,
            "ghost_offset_count": len(controller.ghost_cache),
            "baseline_refresh_count": baseline_count,
            "baseline_refresh_duration_ms": round(baseline_duration, 3),
            "burst_count_before_drain": burst_count,
            "callback_refresh_delta": callback_refresh_delta,
            "last_refresh_duration_ms": round(controller._last_refresh_duration_ms, 3),
            "queued_after_burst": bool(queued_after_burst),
            "drained": bool(drained),
        }
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        _write_result(result)
        maya.utils.executeDeferred(_quit_maya)


maya.utils.executeDeferred(_run)
