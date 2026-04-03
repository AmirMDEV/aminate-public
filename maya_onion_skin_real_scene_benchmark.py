from __future__ import absolute_import, division, print_function

import importlib.util
import json
import os
import sys
import time

import maya.standalone


try:
    maya.standalone.initialize(name="python")
except RuntimeError as exc:
    if "inside of Maya" not in str(exc):
        raise

import maya.cmds as cmds  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(THIS_DIR, "maya_onion_skin.py")
DEFAULT_RESULTS_PATH = os.path.join(THIS_DIR, "maya_onion_skin_real_scene_benchmark.json")
DEFAULT_PAST_FRAMES = 12
DEFAULT_FUTURE_FRAMES = 12


def _load_module():
    spec = importlib.util.spec_from_file_location("maya_onion_skin", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scene_candidates():
    skip_roots = set(["|persp", "|top", "|front", "|side"])
    candidates = []

    for root in cmds.ls(assemblies=True, long=True) or []:
        if root in skip_roots:
            continue

        shapes = cmds.listRelatives(root, allDescendents=True, fullPath=True, type="mesh") or []
        visible_shapes = []
        for shape in shapes:
            if not cmds.objExists(shape):
                continue
            try:
                if cmds.getAttr(shape + ".intermediateObject"):
                    continue
            except Exception:
                continue
            visible_shapes.append(shape)

        if not visible_shapes:
            continue

        transforms = set()
        for shape in visible_shapes:
            parent = cmds.listRelatives(shape, parent=True, fullPath=True) or []
            if parent:
                transforms.add(parent[0])

        candidates.append(
            {
                "root": root,
                "mesh_shape_count": len(visible_shapes),
                "mesh_transform_count": len(transforms),
            }
        )

    candidates.sort(
        key=lambda item: (item["mesh_shape_count"], item["mesh_transform_count"], len(item["root"])),
        reverse=True,
    )
    return candidates


def _benchmark_scene(module, scene_path):
    scene_result = {
        "scene_path": scene_path,
        "status": "fail",
    }

    print("BENCHMARK_OPEN:", scene_path)
    sys.stdout.flush()
    open_start = time.perf_counter()
    cmds.file(
        scene_path,
        open=True,
        force=True,
        prompt=False,
        ignoreVersion=True,
        executeScriptNodes=False,
    )
    scene_result["open_ms"] = round((time.perf_counter() - open_start) * 1000.0, 3)
    scene_result["scene_name"] = cmds.file(query=True, sceneName=True)
    print("BENCHMARK_OPENED:", scene_path, scene_result["open_ms"])
    sys.stdout.flush()

    candidates = _scene_candidates()
    scene_result["candidate_count"] = len(candidates)
    scene_result["top_candidates"] = candidates[:5]
    if not candidates:
        raise RuntimeError("No mesh-bearing root candidates found.")

    target_root = candidates[0]["root"]
    scene_result["selected_root"] = target_root

    cmds.select(target_root, replace=True)
    controller = module.MayaOnionSkinController()
    controller.set_settings(
        DEFAULT_PAST_FRAMES,
        DEFAULT_FUTURE_FRAMES,
        0.55,
        1.35,
        True,
        False,
        (0.25, 0.7, 1.0),
        (1.0, 0.55, 0.2),
    )

    attach_start = time.perf_counter()
    success, message = controller.attach_selection()
    scene_result["attach_ms"] = round((time.perf_counter() - attach_start) * 1000.0, 3)
    scene_result["attach_message"] = message
    if not success:
        raise RuntimeError(message)
    print("BENCHMARK_ATTACHED:", scene_path, target_root, scene_result["attach_ms"])
    sys.stdout.flush()

    full_refresh_times = []
    for _ in range(3):
        start = time.perf_counter()
        success, message = controller.refresh(rebuild=False, reason="manual")
        duration_ms = (time.perf_counter() - start) * 1000.0
        if not success:
            raise RuntimeError(message)
        full_refresh_times.append(duration_ms)

    desired_offsets = controller._desired_offsets()
    controller._last_callback_request_at = time.perf_counter()
    preview_offsets = controller._active_offsets_for_reason("callback", desired_offsets)
    preview_start = time.perf_counter()
    success, message = controller.refresh(rebuild=False, reason="callback")
    preview_refresh_ms = (time.perf_counter() - preview_start) * 1000.0
    if not success:
        raise RuntimeError(message)

    scene_result["status"] = "pass"
    scene_result["mesh_shape_count"] = len(controller.source_meshes)
    scene_result["desired_offset_count"] = len(desired_offsets)
    scene_result["preview_offset_count"] = len(preview_offsets)
    scene_result["full_refresh_ms"] = [round(value, 3) for value in full_refresh_times]
    scene_result["full_refresh_avg_ms"] = round(sum(full_refresh_times) / float(len(full_refresh_times)), 3)
    scene_result["preview_refresh_ms"] = round(preview_refresh_ms, 3)
    scene_result["controller_last_refresh_ms"] = round(controller._last_refresh_duration_ms, 3)
    scene_result["refresh_count"] = controller._completed_refresh_count
    controller.detach(clear_attachment=True)
    return scene_result


def main(argv):
    scene_paths = []
    output_path = DEFAULT_RESULTS_PATH

    arguments = list(argv[1:])
    while arguments:
        token = arguments.pop(0)
        if token == "--output" and arguments:
            output_path = arguments.pop(0)
            continue
        scene_paths.append(token)

    if not scene_paths:
        raise SystemExit("Usage: mayapy maya_onion_skin_real_scene_benchmark.py [--output path] <scene.ma|scene.mb> [...]")

    module = _load_module()
    results = {
        "tool": "maya_onion_skin",
        "scene_count": len(scene_paths),
        "results": [],
    }

    for scene_path in scene_paths:
        scene_payload = {
            "scene_path": scene_path,
            "status": "fail",
        }
        try:
            if not os.path.exists(scene_path):
                raise RuntimeError("Scene file does not exist.")
            scene_payload = _benchmark_scene(module, scene_path)
        except Exception as exc:
            scene_payload["error"] = str(exc)
        results["results"].append(scene_payload)

    with open(output_path, "w") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)

    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main(sys.argv)
