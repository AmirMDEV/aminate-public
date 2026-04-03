from __future__ import absolute_import, division, print_function

import importlib.util
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
import maya.api.OpenMaya as om  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(THIS_DIR, "maya_onion_skin.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("maya_onion_skin", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _world_translation(node):
    return cmds.xform(node, query=True, translation=True, worldSpace=True)


def _mesh_points(shape):
    selection = om.MSelectionList()
    selection.add(shape)
    dag = selection.getDagPath(0)
    return om.MFnMesh(dag).getPoints(om.MSpace.kWorld)


def build_scene():
    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    cmds.playbackOptions(minTime=1, maxTime=24)

    primary_root = cmds.group(empty=True, name="char_root")

    body_transform = cmds.polyCube(name="body_geo", width=2.0, height=3.0, depth=1.0)[0]
    head_transform = cmds.polySphere(name="head_geo", radius=0.8)[0]
    hidden_transform = cmds.polyCube(name="hidden_geo", width=0.5, height=0.5, depth=0.5)[0]

    cmds.parent(body_transform, primary_root)
    cmds.parent(head_transform, primary_root)
    cmds.parent(hidden_transform, primary_root)

    cmds.move(0, 2.5, 0, head_transform, absolute=True)
    cmds.move(3, 0, 0, hidden_transform, absolute=True)
    cmds.setAttr(hidden_transform + ".visibility", 0)

    bend_deformer, bend_handle = cmds.nonLinear(body_transform, type="bend", lowBound=-1, highBound=1)
    cmds.parent(bend_handle, primary_root)
    cmds.setAttr(bend_handle + ".rotateZ", 90)

    cmds.setKeyframe(primary_root, attribute="translateX", time=1, value=-2.0)
    cmds.setKeyframe(primary_root, attribute="translateX", time=12, value=0.0)
    cmds.setKeyframe(primary_root, attribute="translateX", time=24, value=3.0)

    cmds.setKeyframe(bend_deformer, attribute="curvature", time=1, value=-35.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=12, value=0.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=24, value=35.0)

    secondary_root = cmds.group(empty=True, name="prop_root")
    prop_transform = cmds.polyCylinder(name="prop_geo", radius=0.45, height=1.6)[0]
    cmds.parent(prop_transform, secondary_root)
    cmds.move(-2.5, 1.2, 1.5, prop_transform, absolute=True)
    cmds.setKeyframe(secondary_root, attribute="translateZ", time=1, value=-1.0)
    cmds.setKeyframe(secondary_root, attribute="translateZ", time=12, value=0.0)
    cmds.setKeyframe(secondary_root, attribute="translateZ", time=24, value=2.0)

    cmds.select(primary_root, replace=True)
    cmds.currentTime(12, edit=True, update=True)
    return primary_root, secondary_root


def run():
    module = _load_module()
    controller = module.MayaOnionSkinController()
    controller.set_settings(
        past_frames=2,
        future_frames=2,
        frame_step=2,
        opacity=0.6,
        falloff=1.2,
        auto_update=True,
        full_fidelity_scrub=False,
        past_color=(0.2, 0.7, 1.0),
        future_color=(1.0, 0.5, 0.2),
    )

    preview_offsets = list(range(-24, 0, 2)) + list(range(2, 25, 2))
    controller.full_fidelity_scrub = True
    _assert(
        controller._active_offsets_for_reason("callback", preview_offsets) == preview_offsets,
        "Full fidelity scrub should preserve the full callback offset set",
    )
    controller.full_fidelity_scrub = False
    controller._last_callback_request_at = module.time.perf_counter()
    reduced_offsets = controller._active_offsets_for_reason("callback", preview_offsets)
    _assert(len(reduced_offsets) < len(preview_offsets), "Adaptive preview should reduce callback offsets on dense offset sets")

    primary_root, secondary_root = build_scene()
    success, message = controller.attach_selection()
    _assert(success, "Attach failed: {0}".format(message))
    _assert(
        controller.attached_root == "|" + primary_root or controller.attached_root.endswith(primary_root),
        "Unexpected primary attachment root",
    )
    _assert(len(controller.attached_roots) == 1, "Expected 1 attached root after the first attach")
    _assert(len(controller.source_meshes) == 2, "Expected 2 visible mesh shapes, found {0}".format(len(controller.source_meshes)))

    cmds.select(secondary_root, replace=True)
    success, message = controller.attach_selection(add=True)
    _assert(success, "Add Selected failed: {0}".format(message))
    _assert(len(controller.attached_roots) == 2, "Expected 2 attached roots after Add Selected")
    _assert(len(controller.source_meshes) == 3, "Expected 3 visible mesh shapes after multi-root attach")

    success, message = controller.refresh()
    _assert(success, "Refresh failed: {0}".format(message))

    expected_offsets = set([-4, -2, 2, 4])
    _assert(set(controller.ghost_cache.keys()) == expected_offsets, "Unexpected ghost offsets: {0}".format(sorted(controller.ghost_cache.keys())))

    for offset in sorted(expected_offsets):
        slot = controller.ghost_cache[offset]
        _assert(cmds.objExists(slot["group"]), "Missing ghost group for offset {0}".format(offset))
        _assert(len(slot["entries"]) == 3, "Offset {0} should have 3 ghost entries".format(offset))
        shader_info = controller.material_cache.get(offset)
        _assert(shader_info, "Missing material cache for offset {0}".format(offset))
        _assert(cmds.objExists(shader_info["shader"]), "Missing shader for offset {0}".format(offset))

    deformed_entry = next(entry for entry in controller.source_meshes if entry["is_deformed"])
    prop_entry = next(entry for entry in controller.source_meshes if entry["root"].endswith(secondary_root))

    past_body = controller.ghost_cache[-4]["entries"][deformed_entry["shape"]]["transform"]
    future_body = controller.ghost_cache[4]["entries"][deformed_entry["shape"]]["transform"]
    past_translate = _world_translation(past_body)
    future_translate = _world_translation(future_body)
    _assert(abs(past_translate[0] - future_translate[0]) > 0.001, "Past and future ghosts should not overlap in world space")

    prop_future = controller.ghost_cache[4]["entries"][prop_entry["shape"]]["transform"]
    _assert(cmds.objExists(prop_future), "Multi-root prop ghost should exist at the future offset")

    source_shape = deformed_entry["shape"]
    past_shape = controller.ghost_cache[-4]["entries"][source_shape]["shape"]
    future_shape = controller.ghost_cache[4]["entries"][source_shape]["shape"]
    source_points = _mesh_points(source_shape)
    past_points = _mesh_points(past_shape)
    future_points = _mesh_points(future_shape)
    _assert(len(source_points) == len(past_points) == len(future_points), "Mesh point counts should match")
    _assert(
        any(abs(past_points[index].y - future_points[index].y) > 0.001 for index in range(len(past_points))),
        "Bent mesh points should differ between past and future samples",
    )
    _assert(
        any(abs(source_points[index].y - past_points[index].y) > 0.001 for index in range(len(source_points))),
        "Ghost points should differ from the current frame on a deformed mesh",
    )

    controller.detach(clear_attachment=True)
    _assert(not cmds.objExists(module.ROOT_GROUP_NAME), "Ghost root group should be deleted on detach")
    _assert(not controller.callback_ids and not controller.script_job_id, "Callbacks should be cleared on detach")

    print("MAYA_ONION_SKIN_SMOKE_TEST: PASS")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        print("MAYA_ONION_SKIN_SMOKE_TEST: FAIL")
        sys.exit(1)
