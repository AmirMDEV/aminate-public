from __future__ import absolute_import, division, print_function

import importlib.util
import os
import sys
import traceback

import maya.standalone


maya.standalone.initialize(name="python")

import maya.cmds as cmds  # noqa: E402

try:
    from PySide6 import QtWidgets  # noqa: E402
except Exception:
    from PySide2 import QtWidgets  # noqa: E402


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


def _build_scene():
    cmds.file(new=True, force=True)
    root = cmds.group(empty=True, name="qt_char_root")
    body = cmds.polyCube(name="qt_body_geo", width=2.0, height=3.0, depth=1.0)[0]
    head = cmds.polySphere(name="qt_head_geo", radius=0.8)[0]
    cmds.parent(body, root)
    cmds.parent(head, root)
    cmds.move(0, 2.5, 0, head, absolute=True)
    cmds.setKeyframe(root, attribute="translateX", time=1, value=-1.0)
    cmds.setKeyframe(root, attribute="translateX", time=12, value=0.0)
    cmds.setKeyframe(root, attribute="translateX", time=24, value=2.0)
    cmds.currentTime(12, edit=True, update=True)
    cmds.select(root, replace=True)
    return root


def run():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    if not hasattr(app, "topLevelWidgets"):
        print("MAYA_ONION_SKIN_QT_SMOKE_TEST: SKIP (QWidget-capable QApplication unavailable in Maya standalone)")
        return

    module = _load_module()
    _build_scene()

    window = module.launch_maya_onion_skin(dock=False)
    QtWidgets.QApplication.processEvents()

    _assert(window is not None, "Window was not created")
    _assert(window.objectName() == module.WINDOW_OBJECT_NAME, "Unexpected window objectName")
    _assert(window.isVisible(), "Window should be visible")

    success, message = window.controller.attach_selection()
    _assert(success, "Attach failed: {0}".format(message))
    success, message = window.controller.refresh()
    _assert(success, "Refresh failed: {0}".format(message))
    _assert(sorted(window.controller.ghost_cache.keys()) == [-3, -2, -1, 1, 2, 3], "Unexpected ghost offsets")

    window.close()
    QtWidgets.QApplication.processEvents()

    print("MAYA_ONION_SKIN_QT_SMOKE_TEST: PASS")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        print("MAYA_ONION_SKIN_QT_SMOKE_TEST: FAIL")
        sys.exit(1)
