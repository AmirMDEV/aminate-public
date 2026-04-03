from __future__ import absolute_import, division, print_function

import os
import sys
import time

from PIL import ImageGrab
from pywinauto import Desktop
from pywinauto.keyboard import send_keys
from pywinauto.mouse import click


OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_TITLE_RE = ".*Autodesk MAYA 2026.*"
TOOL_TITLE = "Maya Onion Skin"

SETUP_SCRIPT = r"""import sys
sys.path.insert(0, r"C:\Users\Amir Mansaray\Documents\Github\maya-animation-tools")
import maya.cmds as cmds
cmds.file(new=True, force=True)
root = cmds.group(empty=True, name="OS_TestRig_GRP")
body = cmds.polyCube(name="OS_Body_GEO", width=2.0, height=3.0, depth=1.0)[0]
head = cmds.polySphere(name="OS_Head_GEO", radius=0.8)[0]
hidden = cmds.polyCube(name="OS_HiddenHelper_GEO", width=0.5, height=0.5, depth=0.5)[0]
cmds.parent(body, root)
cmds.parent(head, root)
cmds.parent(hidden, root)
cmds.move(0, 2.5, 0, head, absolute=True)
cmds.move(3, 0, 0, hidden, absolute=True)
cmds.setAttr(hidden + ".visibility", 0)
bend, handle = cmds.nonLinear(body, type="bend", lowBound=-1, highBound=1)
cmds.parent(handle, root)
cmds.setAttr(handle + ".rotateZ", 90)
cmds.setKeyframe(root, attribute="translateX", time=1, value=-2.0)
cmds.setKeyframe(root, attribute="translateX", time=12, value=0.0)
cmds.setKeyframe(root, attribute="translateX", time=24, value=3.0)
cmds.setKeyframe(bend, attribute="curvature", time=1, value=-35.0)
cmds.setKeyframe(bend, attribute="curvature", time=12, value=0.0)
cmds.setKeyframe(bend, attribute="curvature", time=24, value=35.0)
cmds.currentTime(12, edit=True, update=True)
cmds.select(root, replace=True)
import maya_onion_skin
_MAYA_ONION_SKIN_WINDOW = maya_onion_skin.launch_maya_onion_skin(dock=False)
_MAYA_ONION_SKIN_WINDOW.past_spin.setValue(2)
_MAYA_ONION_SKIN_WINDOW.future_spin.setValue(2)
_MAYA_ONION_SKIN_WINDOW.auto_update_check.setChecked(True)
print("GUI_READY")
"""

FRAME_9_SCRIPT = 'import maya.cmds as cmds\ncmds.currentTime(9, edit=True, update=True)\nprint("FRAME_9_READY")\n'
FRAME_11_SCRIPT = 'import maya.cmds as cmds\ncmds.currentTime(11, edit=True, update=True)\nprint("FRAME_11_READY")\n'


def _capture(name):
    path = os.path.join(OUTPUT_DIR, name)
    ImageGrab.grab().save(path)
    print("CAPTURED", path)
    return path


def _wait_for(predicate, timeout=60.0, step=0.5, message="timeout"):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(step)
    raise RuntimeError(message)


def _maya_window():
    return Desktop(backend="uia").window(title_re=MAIN_TITLE_RE)


def _script_editor_controls():
    win = _maya_window()
    edit = None
    python_tab = None
    for control in win.descendants():
        rect = control.rectangle()
        title = control.window_text()
        ctrl_type = control.element_info.control_type
        if title == "Python" and ctrl_type in ("Tab", "TabItem"):
            python_tab = control
        if ctrl_type == "Edit" and 240 <= rect.left <= 740 and 390 <= rect.top <= 530:
            edit = control
    if not edit:
        raise RuntimeError("Could not find Script Editor Python edit control")
    return python_tab, edit


def _set_script_editor_text(script_text):
    python_tab, edit = _script_editor_controls()
    if python_tab:
        try:
            python_tab.click_input()
            time.sleep(0.2)
        except Exception:
            pass
    edit.set_focus()
    edit.set_edit_text(script_text)
    time.sleep(0.3)


def _execute_editor_selection():
    send_keys("^a")
    time.sleep(0.1)
    send_keys("^{ENTER}")
    time.sleep(2.0)


def _wait_for_tool_window():
    def finder():
        try:
            main = _maya_window()
            buttons = [c for c in main.descendants(control_type="Button") if c.window_text() == "Attach Selected"]
            if buttons:
                return main
        except Exception:
            return None
        return None

    return _wait_for(finder, timeout=30.0, step=0.5, message="Maya Onion Skin controls did not appear")


def _click_button(window, title):
    button = window.child_window(title=title, control_type="Button")
    button.wait("exists enabled visible", timeout=10)
    button.click_input()
    time.sleep(1.5)


def _timeline_click_for_frame(frame_value):
    main = _maya_window()
    rect = main.rectangle()
    left = rect.left + 5
    timeline_left = rect.left + 12
    timeline_right = rect.right - 330
    timeline_y = rect.bottom - 59
    min_frame = 1.0
    max_frame = 250.0
    ratio = (float(frame_value) - min_frame) / (max_frame - min_frame)
    ratio = max(0.0, min(1.0, ratio))
    x = int(timeline_left + ((timeline_right - timeline_left) * ratio))
    click(coords=(x, timeline_y))
    time.sleep(1.5)


def run():
    main = _wait_for(lambda: _maya_window() if _maya_window().exists(timeout=0.2) else None, timeout=30.0)
    main.set_focus()
    _capture("maya_gui_driver_01_before_setup.png")

    _set_script_editor_text(SETUP_SCRIPT)
    _execute_editor_selection()

    tool = _wait_for_tool_window()
    _capture("maya_gui_driver_02_tool_open.png")

    _click_button(tool, "Attach Selected")
    _capture("maya_gui_driver_03_attached.png")

    _timeline_click_for_frame(9)
    _capture("maya_gui_driver_04_frame09.png")

    _timeline_click_for_frame(11)
    _capture("maya_gui_driver_05_frame11.png")

    _click_button(tool, "Clear")
    _capture("maya_gui_driver_06_cleared.png")

    try:
        tool.close()
    except Exception:
        pass

    print("MAYA_ONION_SKIN_GUI_DRIVER: PASS")


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        print("MAYA_ONION_SKIN_GUI_DRIVER: FAIL")
        print(type(exc).__name__, exc)
        sys.exit(1)
