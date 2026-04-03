from __future__ import absolute_import, division, print_function

import importlib.util
import json
import os
import traceback

import maya.cmds as cmds
import maya.utils


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(THIS_DIR, "maya_onion_skin.py")
RESULT_PATH = os.path.join(THIS_DIR, "maya_onion_skin_gui_smoke_result.json")


def _load_module():
    spec = importlib.util.spec_from_file_location("maya_onion_skin", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_result(payload):
    with open(RESULT_PATH, "w") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)


def _build_scene():
    cmds.file(new=True, force=True)
    root = cmds.group(empty=True, name="gui_char_root")
    body = cmds.polyCube(name="gui_body_geo", width=2.0, height=3.0, depth=1.0)[0]
    head = cmds.polySphere(name="gui_head_geo", radius=0.8)[0]
    cmds.parent(body, root)
    cmds.parent(head, root)
    cmds.move(0, 2.5, 0, head, absolute=True)
    cmds.setKeyframe(root, attribute="translateX", time=1, value=-1.0)
    cmds.setKeyframe(root, attribute="translateX", time=12, value=0.0)
    cmds.setKeyframe(root, attribute="translateX", time=24, value=2.0)
    cmds.currentTime(12, edit=True, update=True)
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

        if window is None:
            raise RuntimeError("launch_maya_onion_skin() returned None")

        window.controller.set_settings(
            past_frames=1,
            future_frames=1,
            opacity=0.6,
            falloff=1.0,
            auto_update=True,
            full_fidelity_scrub=False,
            past_color=(0.2, 0.7, 1.0),
            future_color=(1.0, 0.5, 0.2),
        )

        success, message = window.controller.attach_selection()
        if not success:
            raise RuntimeError(message)

        success, message = window.controller.refresh()
        if not success:
            raise RuntimeError(message)

        ghost_offsets = sorted(window.controller.ghost_cache.keys())
        result["status"] = "pass"
        result["details"] = {
            "attached_root": window.controller.attached_root,
            "qt_binding": module.QT_BINDING,
            "ghost_offsets": ghost_offsets,
            "source_mesh_count": len(window.controller.source_meshes),
            "window_visible": bool(window.isVisible()),
            "window_object_name": window.objectName(),
            "scene_root": root,
        }
    except Exception:
        result["error"] = traceback.format_exc()
    finally:
        _write_result(result)
        maya.utils.executeDeferred(_quit_maya)


maya.utils.executeDeferred(_run)
