from __future__ import absolute_import, division, print_function

import importlib
import os
import sys


try:
    import maya.cmds as cmds
except Exception:
    cmds = None


THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _ensure_repo_on_path():
    if THIS_DIR not in sys.path:
        sys.path.insert(0, THIS_DIR)


def _focus_persp_view():
    model_panels = cmds.getPanel(type="modelPanel") or []
    if not model_panels:
        return
    panel = model_panels[0]
    try:
        cmds.setFocus(panel)
        cmds.lookThru(panel, "persp")
    except Exception:
        pass


def _key_translate(node, axis, keys):
    attribute = "translate{0}".format(axis.upper())
    for frame, value in keys:
        cmds.setKeyframe(node, attribute=attribute, time=frame, value=value)


def build_demo_scene():
    if not cmds:
        raise RuntimeError("This demo must run inside Maya.")

    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    cmds.playbackOptions(minTime=1, maxTime=48, animationStartTime=1, animationEndTime=48)

    hero_root = cmds.group(empty=True, name="hero_root")
    prop_root = cmds.group(empty=True, name="prop_root")

    body_transform = cmds.polyCube(name="hero_body_geo", width=2.4, height=4.2, depth=1.2)[0]
    head_transform = cmds.polySphere(name="hero_head_geo", radius=0.95)[0]
    prop_transform = cmds.polyCylinder(name="hero_prop_geo", radius=0.4, height=2.0, subdivisionsAxis=16)[0]

    cmds.parent(body_transform, hero_root)
    cmds.parent(head_transform, hero_root)
    cmds.parent(prop_transform, prop_root)

    cmds.move(0.0, 3.35, 0.0, head_transform, absolute=True)
    cmds.move(-2.8, 1.25, 1.7, prop_transform, absolute=True)

    bend_deformer, bend_handle = cmds.nonLinear(body_transform, type="bend", lowBound=-1, highBound=1)
    twist_deformer, twist_handle = cmds.nonLinear(prop_transform, type="twist", lowBound=-1, highBound=1)
    cmds.parent(bend_handle, hero_root)
    cmds.parent(twist_handle, prop_root)
    cmds.setAttr("{0}.rotateZ".format(bend_handle), 90)
    cmds.setAttr("{0}.rotateX".format(twist_handle), 90)

    _key_translate(hero_root, "x", [(1, -5.0), (16, -1.25), (32, 2.25), (48, 5.5)])
    _key_translate(hero_root, "z", [(1, -1.5), (24, 0.75), (48, -0.25)])
    _key_translate(prop_root, "x", [(1, -4.0), (24, -1.0), (48, 2.0)])
    _key_translate(prop_root, "z", [(1, 2.5), (24, 0.5), (48, -2.25)])

    cmds.setKeyframe(bend_deformer, attribute="curvature", time=1, value=-35.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=16, value=-10.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=32, value=18.0)
    cmds.setKeyframe(bend_deformer, attribute="curvature", time=48, value=40.0)

    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=1, value=-120.0)
    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=16, value=-40.0)
    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=32, value=65.0)
    cmds.setKeyframe(twist_deformer, attribute="endAngle", time=48, value=135.0)

    cmds.select([hero_root, prop_root], replace=True)
    _focus_persp_view()
    try:
        cmds.viewFit()
    except Exception:
        pass
    try:
        cmds.window("scriptEditorPanel1Window", edit=True, visible=False)
        cmds.deleteUI("scriptEditorPanel1Window", window=True)
    except Exception:
        pass
    cmds.currentTime(24, edit=True, update=True)
    return {"hero_root": hero_root, "prop_root": prop_root}


def prepare_demo(open_tool=True, dock=False):
    if not cmds:
        raise RuntimeError("This demo must run inside Maya.")

    _ensure_repo_on_path()
    import maya_onion_skin

    maya_onion_skin = importlib.reload(maya_onion_skin)
    roots = build_demo_scene()
    window = None

    if open_tool:
        window = maya_onion_skin.launch_maya_onion_skin(dock=dock)
        try:
            window.resize(460, 560)
            window.move(760, 150)
            window.raise_()
            window.activateWindow()
            if maya_onion_skin.QtWidgets:
                maya_onion_skin.QtWidgets.QApplication.processEvents()
        except Exception:
            pass
        window.past_spin.setValue(8)
        window.future_spin.setValue(8)
        window.frame_step_spin.setValue(2)
        window.opacity_spin.setValue(0.62)
        window.falloff_spin.setValue(1.25)
        window.auto_update_check.setChecked(True)
        window.full_fidelity_scrub_check.setChecked(False)

        cmds.select(roots["hero_root"], replace=True)
        window._attach_selected()
        cmds.select(roots["prop_root"], replace=True)
        window._add_selected()
        cmds.currentTime(24, edit=True, update=True)
        window._refresh()

    return {
        "roots": roots,
        "window_visible": bool(window and window.isVisible()),
        "window_title": None if window is None else window.windowTitle(),
    }


if __name__ == "__main__":
    prepare_demo(open_tool=True, dock=False)
