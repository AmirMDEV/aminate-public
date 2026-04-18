"""
maya_animators_pencil.py

Scene-native drawing layer tool for Maya animators.
"""

from __future__ import absolute_import, division, print_function

import json
import math
import os
import time

try:
    import maya.cmds as cmds
    import maya.mel as mel
    MAYA_AVAILABLE = True
except Exception:
    cmds = None
    mel = None
    MAYA_AVAILABLE = False

try:
    from PySide6 import QtCore, QtGui, QtWidgets
except Exception:
    from PySide2 import QtCore, QtGui, QtWidgets


WINDOW_OBJECT_NAME = "mayaAnimatorsPencilWindow"
ROOT_GROUP_NAME = "amirAnimatorsPencil_GRP"
ROOT_MARKER_ATTR = "amirAnimatorsPencilRoot"
ROOT_STATE_ATTR = "animatorsPencilState"
LAYER_MARKER_ATTR = "amirAnimatorsPencilLayer"
MARK_MARKER_ATTR = "amirAnimatorsPencilMark"
LAYER_VERSION = 1

FOLLOW_AMIR_URL = "https://followamir.com"
DEFAULT_DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=2U2GXSKFJKJCA"
DONATE_URL = os.environ.get("AMIR_PAYPAL_DONATE_URL") or os.environ.get("AMIR_DONATE_URL") or DEFAULT_DONATE_URL

DEFAULT_COLORS = {
    "Red": (1.0, 0.05, 0.05),
    "Blue": (0.15, 0.38, 1.0),
    "Green": (0.1, 0.8, 0.25),
    "Yellow": (1.0, 0.9, 0.05),
    "White": (1.0, 1.0, 1.0),
    "Black": (0.0, 0.0, 0.0),
}

LAYER_STATES = ("Animation", "Static", "Locked")
TOOL_NAMES = ("Pencil", "Brush", "Eraser", "Text", "Line", "Arrow", "Rectangle", "Ellipse")


def _qt_flag(scope_name, member_name, fallback=None):
    if hasattr(QtCore.Qt, member_name):
        return getattr(QtCore.Qt, member_name)
    scoped_enum = getattr(QtCore.Qt, scope_name, None)
    if scoped_enum and hasattr(scoped_enum, member_name):
        return getattr(scoped_enum, member_name)
    return fallback


def _short_name(node_name):
    return (node_name or "").split("|")[-1].split(":")[-1]


def _long_name(node_name):
    if not MAYA_AVAILABLE or not node_name:
        return node_name
    try:
        matches = cmds.ls(node_name, long=True) or []
    except Exception:
        return node_name
    return matches[0] if matches else node_name


def _safe_name(value):
    clean = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in (value or "Layer"))
    clean = clean.strip("_") or "Layer"
    return clean[:48]


def _ensure_attr(node_name, attr_name, attr_type="string", default=None):
    if not MAYA_AVAILABLE or not cmds.objExists(node_name):
        return
    if cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return
    if attr_type == "string":
        cmds.addAttr(node_name, longName=attr_name, dataType="string")
        if default is not None:
            cmds.setAttr("{0}.{1}".format(node_name, attr_name), default, type="string")
    elif attr_type == "bool":
        cmds.addAttr(node_name, longName=attr_name, attributeType="bool", defaultValue=bool(default))
    elif attr_type == "double":
        cmds.addAttr(node_name, longName=attr_name, attributeType="double", defaultValue=float(default or 0.0))
    elif attr_type == "long":
        cmds.addAttr(node_name, longName=attr_name, attributeType="long", defaultValue=int(default or 0))


def _set_string_attr(node_name, attr_name, value):
    _ensure_attr(node_name, attr_name, "string")
    cmds.setAttr("{0}.{1}".format(node_name, attr_name), value or "", type="string")


def _get_string_attr(node_name, attr_name, default=""):
    if not MAYA_AVAILABLE or not cmds.objExists(node_name):
        return default
    if not cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return default
    value = cmds.getAttr("{0}.{1}".format(node_name, attr_name))
    return value if value is not None else default


def _set_json_attr(node_name, attr_name, value):
    _set_string_attr(node_name, attr_name, json.dumps(value, sort_keys=True))


def _get_json_attr(node_name, attr_name, default=None):
    raw = _get_string_attr(node_name, attr_name, "")
    if not raw:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _current_frame():
    if not MAYA_AVAILABLE:
        return 0
    return int(round(float(cmds.currentTime(query=True))))


def _current_camera():
    if not MAYA_AVAILABLE:
        return "persp"
    try:
        panel = cmds.getPanel(withFocus=True)
        if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
            camera = cmds.modelPanel(panel, query=True, camera=True)
            if camera:
                parents = cmds.listRelatives(camera, parent=True, fullPath=False) or []
                return parents[0] if cmds.nodeType(camera) == "camera" and parents else camera
    except Exception:
        pass
    for fallback in ("persp", "camera1"):
        if cmds.objExists(fallback):
            return fallback
    cameras = cmds.ls(type="camera") or []
    if cameras:
        parents = cmds.listRelatives(cameras[0], parent=True, fullPath=False) or []
        return parents[0] if parents else cameras[0]
    return ""


def _run_mel(command):
    if not MAYA_AVAILABLE or not mel:
        return None
    try:
        return mel.eval(command)
    except Exception:
        return None


def _open_undo_chunk(name):
    if MAYA_AVAILABLE:
        try:
            cmds.undoInfo(openChunk=True, chunkName=name)
        except Exception:
            pass


def _close_undo_chunk():
    if MAYA_AVAILABLE:
        try:
            cmds.undoInfo(closeChunk=True)
        except Exception:
            pass


def _set_display_color(node_name, color, opacity=1.0, line_width=2.0):
    shapes = cmds.listRelatives(node_name, shapes=True, noIntermediate=True, fullPath=True) or []
    children = cmds.listRelatives(node_name, allDescendents=True, fullPath=True) or []
    for child in children:
        if cmds.nodeType(child) in ("nurbsCurve", "nurbsSurface", "mesh"):
            shapes.append(child)
    seen = set()
    for shape in shapes:
        if shape in seen or not cmds.objExists(shape):
            continue
        seen.add(shape)
        for attr, value in (
            ("overrideEnabled", True),
            ("overrideRGBColors", True),
        ):
            if cmds.objExists("{0}.{1}".format(shape, attr)):
                cmds.setAttr("{0}.{1}".format(shape, attr), value)
        if cmds.objExists(shape + ".overrideColorRGB"):
            cmds.setAttr(shape + ".overrideColorRGB", color[0], color[1], color[2])
        if cmds.objExists(shape + ".lineWidth"):
            cmds.setAttr(shape + ".lineWidth", max(1.0, float(line_width)))
        if cmds.objExists(shape + ".overrideDisplayType"):
            cmds.setAttr(shape + ".overrideDisplayType", 0)
    if cmds.objExists(node_name + ".visibility"):
        cmds.setAttr(node_name + ".visibility", True)
    _ensure_attr(node_name, "animatorsPencilOpacity", "double", opacity)
    cmds.setAttr(node_name + ".animatorsPencilOpacity", float(opacity))


def _curve_node(name, points, parent, color, opacity, size, degree=1):
    curve = cmds.curve(name=name, degree=degree, point=points)
    if parent:
        curve = cmds.parent(curve, parent)[0]
    curve = _long_name(curve)
    _set_display_color(curve, color, opacity=opacity, line_width=size)
    return curve


def _parent_if_needed(node_name, parent_name):
    if not parent_name or not cmds.objExists(node_name) or not cmds.objExists(parent_name):
        return node_name
    node_name = _long_name(node_name)
    parent_name = _long_name(parent_name)
    current_parent = (cmds.listRelatives(node_name, parent=True, fullPath=True) or [""])[0]
    if current_parent == parent_name or _short_name(current_parent) == _short_name(parent_name):
        return node_name
    result = cmds.parent(node_name, parent_name)
    return _long_name(result[0]) if result else node_name


class AnimatorsPencilController(object):
    def __init__(self):
        self.clipboard = []
        self.status_callback = None

    def set_status_callback(self, callback):
        self.status_callback = callback

    def _status(self, message):
        if self.status_callback:
            self.status_callback(message)
        elif MAYA_AVAILABLE:
            try:
                import maya.api.OpenMaya as om
                om.MGlobal.displayInfo("[Animators Pencil] {0}".format(message))
            except Exception:
                pass

    def root(self):
        if not MAYA_AVAILABLE:
            return ""
        if cmds.objExists(ROOT_GROUP_NAME):
            return ROOT_GROUP_NAME
        root = cmds.createNode("transform", name=ROOT_GROUP_NAME)
        _set_string_attr(root, ROOT_MARKER_ATTR, "animators_pencil")
        _set_json_attr(root, ROOT_STATE_ATTR, {"version": LAYER_VERSION, "created": time.time()})
        return root

    def open_native_blue_pencil(self):
        if not MAYA_AVAILABLE:
            return False
        try:
            if not cmds.pluginInfo("bluePencil", query=True, loaded=True):
                cmds.loadPlugin("bluePencil", quiet=True)
        except Exception:
            pass
        result = _run_mel("OpenBluePencil;")
        _run_mel("ToggleBluePencilToolBar;")
        self._status("Native Blue Pencil opened.")
        return result is not None

    def set_native_tool(self, tool):
        command_map = {
            "Pencil": "bluePencilUtil -pencilTool;",
            "Brush": "bluePencilUtil -brushTool;",
            "Eraser": "bluePencilUtil -eraserTool;",
            "Text": "bluePencilUtil -textTool;",
            "Line": "bluePencilUtil -lineTool;",
            "Arrow": "bluePencilUtil -arrowTool;",
            "Rectangle": "bluePencilUtil -rectangleTool;",
            "Ellipse": "bluePencilUtil -ellipseTool;",
        }
        self.open_native_blue_pencil()
        _run_mel(command_map.get(tool, "bluePencilUtil -pencilTool;"))
        self._status("Native Blue Pencil tool: {0}".format(tool))

    def apply_native_options(self, tool, color, size, opacity):
        self.open_native_blue_pencil()
        r, g, b = color
        _run_mel("bluePencilUtil -e -drawColor {0} {1} {2};".format(r, g, b))
        int_size = max(1, int(round(size)))
        int_opacity = max(1, min(100, int(round(opacity * 100.0))))
        if tool == "Brush":
            _run_mel("bluePencilUtil -brushOptions {0} {1} 50 false false;".format(int_size, int_opacity))
        elif tool == "Eraser":
            _run_mel("bluePencilUtil -eraserOptions {0} {1} 50 false false;".format(int_size, int_opacity))
        elif tool == "Text":
            _run_mel('bluePencilUtil -textOptions {0} {1} "Arial";'.format(int_size, int_opacity))
        elif tool == "Line":
            _run_mel("bluePencilUtil -lineOptions {0} {1};".format(int_size, int_opacity))
        elif tool == "Arrow":
            _run_mel("bluePencilUtil -arrowOptions {0} {1};".format(int_size, int_opacity))
        elif tool == "Ellipse":
            _run_mel("bluePencilUtil -ellipseOptions {0} {1};".format(int_size, int_opacity))
        elif tool == "Rectangle":
            _run_mel("bluePencilUtil -rectangleOptions {0} {1};".format(int_size, int_opacity))
        else:
            _run_mel("bluePencilUtil -pencilOptions {0} {1} false false;".format(int_size, int_opacity))
        self.set_native_tool(tool)

    def native_frame_command(self, action):
        command_map = {
            "insert": "bluePencilFrame -insert;",
            "delete": "bluePencilFrame -delete;",
            "duplicate": "bluePencilFrame -duplicate;",
            "cut": "bluePencilFrame -cut;",
            "copy": "bluePencilFrame -copy;",
            "paste": "bluePencilFrame -paste;",
            "clear": "bluePencilFrame -clear;",
            "step_back": "bluePencilFrame -stepBack;",
            "step_forward": "bluePencilFrame -stepForward;",
        }
        self.open_native_blue_pencil()
        _run_mel(command_map.get(action, "bluePencilFrame -duplicate;"))
        self._status("Native Blue Pencil frame: {0}".format(action.replace("_", " ")))

    def configure_native_ghosting(self, previous_count=2, next_count=2, previous_color=(0.1, 0.6, 1.0), next_color=(1.0, 0.4, 0.1)):
        self.open_native_blue_pencil()
        _run_mel("bluePencilUtil -e -ghostPrevious true;")
        _run_mel("bluePencilUtil -e -ghostNext true;")
        _run_mel("bluePencilUtil -e -ghostPreviousCount {0};".format(int(previous_count)))
        _run_mel("bluePencilUtil -e -ghostNextCount {0};".format(int(next_count)))
        _run_mel("bluePencilUtil -e -ghostColorOverride true;")
        _run_mel("bluePencilUtil -e -ghostColorPrevious {0} {1} {2};".format(previous_color[0], previous_color[1], previous_color[2]))
        _run_mel("bluePencilUtil -e -ghostColorNext {0} {1} {2};".format(next_color[0], next_color[1], next_color[2]))
        self._status("Native Blue Pencil ghosting configured.")

    def layers(self):
        if not MAYA_AVAILABLE:
            return []
        root = self.root()
        result = []
        for node in cmds.ls(type="transform", long=True) or []:
            if _get_string_attr(node, LAYER_MARKER_ATTR, "") != "layer":
                continue
            data = self.layer_data(node)
            result.append(data)
        result.sort(key=lambda item: (item.get("order", 0), item.get("name", "")))
        return result

    def layer_data(self, layer_node):
        layer_node = _long_name(layer_node)
        data = _get_json_attr(layer_node, "animatorsPencilLayerData", {}) or {}
        data["node"] = layer_node
        data.setdefault("name", _short_name(layer_node))
        data.setdefault("camera", _get_string_attr(layer_node, "animatorsPencilCamera", ""))
        data.setdefault("state", _get_string_attr(layer_node, "animatorsPencilLayerState", "Animation"))
        data.setdefault("order", int(cmds.getAttr(layer_node + ".animatorsPencilLayerOrder")) if cmds.objExists(layer_node + ".animatorsPencilLayerOrder") else 0)
        data.setdefault("locked", bool(cmds.getAttr(layer_node + ".animatorsPencilLayerLocked")) if cmds.objExists(layer_node + ".animatorsPencilLayerLocked") else False)
        data["count"] = len(self.marks(layer_node))
        return data

    def active_layer(self):
        state = _get_json_attr(self.root(), ROOT_STATE_ATTR, {}) or {}
        layer = state.get("active_layer")
        if layer and cmds.objExists(layer):
            return _long_name(layer)
        layers = self.layers()
        if layers:
            return layers[0]["node"]
        return self.create_layer("Pencil Layer")

    def set_active_layer(self, layer_node):
        root = self.root()
        state = _get_json_attr(root, ROOT_STATE_ATTR, {}) or {}
        state["active_layer"] = _long_name(layer_node)
        _set_json_attr(root, ROOT_STATE_ATTR, state)

    def create_layer(self, name="Pencil Layer", camera=None, state="Animation"):
        if not MAYA_AVAILABLE:
            return ""
        camera = camera or _current_camera()
        order = len(self.layers())
        layer_name = "amirPencil_{0}_{1}_LYR".format(_safe_name(camera), _safe_name(name))
        layer = cmds.createNode("transform", name=layer_name)
        if camera and cmds.objExists(camera):
            try:
                layer = cmds.parent(layer, camera)[0]
            except Exception:
                pass
        layer = _long_name(layer)
        cmds.setAttr(layer + ".translate", 0, 0, -10.0 - (order * 0.03), type="double3")
        _set_string_attr(layer, LAYER_MARKER_ATTR, "layer")
        _set_string_attr(layer, "animatorsPencilCamera", camera or "")
        _set_string_attr(layer, "animatorsPencilLayerState", state)
        _ensure_attr(layer, "animatorsPencilLayerOrder", "long", order)
        _ensure_attr(layer, "animatorsPencilLayerLocked", "bool", False)
        data = {"version": LAYER_VERSION, "name": name, "camera": camera, "state": state, "order": order, "locked": False}
        _set_json_attr(layer, "animatorsPencilLayerData", data)
        self.set_active_layer(layer)
        self._status("Layer created: {0}".format(name))
        return layer

    def delete_layer(self, layer_node):
        if layer_node and cmds.objExists(layer_node):
            cmds.delete(layer_node)
            self._status("Layer deleted.")

    def set_layer_state(self, layer_node, state):
        if not layer_node or not cmds.objExists(layer_node):
            return
        locked = state == "Locked"
        _set_string_attr(layer_node, "animatorsPencilLayerState", state)
        if cmds.objExists(layer_node + ".animatorsPencilLayerLocked"):
            cmds.setAttr(layer_node + ".animatorsPencilLayerLocked", locked)
        data = self.layer_data(layer_node)
        data["state"] = state
        data["locked"] = locked
        _set_json_attr(layer_node, "animatorsPencilLayerData", data)
        for attr in ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz"):
            try:
                cmds.setAttr("{0}.{1}".format(layer_node, attr), lock=locked)
            except Exception:
                pass

    def move_layer_order(self, layer_node, delta):
        layers = self.layers()
        nodes = [item["node"] for item in layers]
        if layer_node not in nodes:
            return
        index = nodes.index(layer_node)
        new_index = max(0, min(len(nodes) - 1, index + delta))
        nodes.insert(new_index, nodes.pop(index))
        for order, node in enumerate(nodes):
            if cmds.objExists(node + ".animatorsPencilLayerOrder"):
                cmds.setAttr(node + ".animatorsPencilLayerOrder", order)
            data = self.layer_data(node)
            data["order"] = order
            _set_json_attr(node, "animatorsPencilLayerData", data)
            cmds.setAttr(node + ".translateZ", -10.0 - (order * 0.03))

    def move_layer_to_camera(self, layer_node, camera=None):
        camera = camera or _current_camera()
        if not layer_node or not camera or not cmds.objExists(layer_node) or not cmds.objExists(camera):
            return
        world_matrix = cmds.xform(layer_node, query=True, matrix=True, worldSpace=True)
        layer_node = cmds.parent(layer_node, camera)[0]
        layer_node = _long_name(layer_node)
        cmds.xform(layer_node, matrix=world_matrix, worldSpace=True)
        _set_string_attr(layer_node, "animatorsPencilCamera", camera)
        data = self.layer_data(layer_node)
        data["camera"] = camera
        _set_json_attr(layer_node, "animatorsPencilLayerData", data)
        self._status("Layer moved to camera: {0}".format(camera))

    def marks(self, layer_node=None):
        if not MAYA_AVAILABLE:
            return []
        layer_node = layer_node or self.active_layer()
        if not layer_node or not cmds.objExists(layer_node):
            return []
        layer_node = _long_name(layer_node)
        children = cmds.listRelatives(layer_node, children=True, fullPath=True) or []
        return [child for child in children if _get_string_attr(child, MARK_MARKER_ATTR, "") == "mark"]

    def selected_marks(self):
        if not MAYA_AVAILABLE:
            return []
        selected = cmds.ls(selection=True, type="transform", long=True) or []
        return [node for node in selected if _get_string_attr(node, MARK_MARKER_ATTR, "") == "mark"]

    def _mark_node(self, node, layer_node, tool, color, opacity, size, frame=None):
        node = _long_name(node)
        layer_node = _long_name(layer_node)
        frame = _current_frame() if frame is None else int(frame)
        _set_string_attr(node, MARK_MARKER_ATTR, "mark")
        data = {
            "version": LAYER_VERSION,
            "tool": tool,
            "layer": layer_node,
            "frame": frame,
            "color": list(color),
            "opacity": float(opacity),
            "size": float(size),
        }
        _set_json_attr(node, "animatorsPencilMarkData", data)
        _ensure_attr(node, "animatorsPencilFrame", "long", frame)
        cmds.setAttr(node + ".animatorsPencilFrame", frame)
        self._key_mark_visibility(node, layer_node, frame)
        return node

    def _key_mark_visibility(self, node, layer_node, frame):
        layer_state = _get_string_attr(layer_node, "animatorsPencilLayerState", "Animation")
        if layer_state == "Static":
            cmds.setAttr(node + ".visibility", True)
            return
        cmds.setAttr(node + ".visibility", False)
        cmds.setKeyframe(node, attribute="visibility", time=max(frame - 1, 0), value=0)
        cmds.setAttr(node + ".visibility", True)
        cmds.setKeyframe(node, attribute="visibility", time=frame, value=1)

    def _tool_points(self, tool):
        if tool == "Brush":
            return [(-1.0, -0.15, 0.0), (-0.45, 0.25, 0.0), (0.1, -0.05, 0.0), (0.75, 0.28, 0.0)]
        if tool == "Line":
            return [(-0.8, 0.0, 0.0), (0.8, 0.0, 0.0)]
        if tool == "Arrow":
            return [(-0.9, 0.0, 0.0), (0.75, 0.0, 0.0), (0.45, 0.22, 0.0), (0.75, 0.0, 0.0), (0.45, -0.22, 0.0)]
        if tool == "Rectangle":
            return [(-0.7, -0.45, 0.0), (0.7, -0.45, 0.0), (0.7, 0.45, 0.0), (-0.7, 0.45, 0.0), (-0.7, -0.45, 0.0)]
        if tool == "Ellipse":
            points = []
            for i in range(33):
                angle = (math.pi * 2.0) * (float(i) / 32.0)
                points.append((math.cos(angle) * 0.72, math.sin(angle) * 0.45, 0.0))
            return points
        return [(-0.9, 0.0, 0.0), (-0.55, 0.18, 0.0), (-0.1, -0.1, 0.0), (0.35, 0.24, 0.0), (0.9, 0.0, 0.0)]

    def create_mark(self, tool="Pencil", layer_node=None, color=(1.0, 0.05, 0.05), size=2.0, opacity=1.0, text="Note"):
        if not MAYA_AVAILABLE:
            return ""
        layer_node = layer_node or self.active_layer()
        if not layer_node or not cmds.objExists(layer_node):
            layer_node = self.create_layer()
        if _get_string_attr(layer_node, "animatorsPencilLayerState", "Animation") == "Locked":
            self._status("Layer locked.")
            return ""
        _open_undo_chunk("Animators Pencil Create {0}".format(tool))
        try:
            if tool == "Eraser":
                self.delete_selected_marks()
                return ""
            if tool == "Text":
                group = cmds.textCurves(name="amirPencilText_MARK", text=text or "Note", font="Arial", constructionHistory=False)[0]
                group = cmds.parent(group, layer_node)[0]
                group = _long_name(group)
                cmds.setAttr(group + ".translate", -0.55, 0.0, 0.0, type="double3")
                cmds.setAttr(group + ".scale", 0.025, 0.025, 0.025, type="double3")
                mark = group
                _set_display_color(mark, color, opacity=opacity, line_width=size)
            else:
                mark = _curve_node("amirPencil{0}_MARK".format(tool), self._tool_points(tool), layer_node, color, opacity, size)
            self._mark_node(mark, layer_node, tool, color, opacity, size)
            cmds.select(mark, replace=True)
            self._status("{0} mark created.".format(tool))
            return mark
        finally:
            _close_undo_chunk()

    def delete_selected_marks(self):
        marks = self.selected_marks()
        if marks:
            cmds.delete(marks)
            self._status("Selected pencil marks deleted.")

    def copy_selected_marks(self, cut=False):
        self.clipboard = []
        for mark in self.selected_marks():
            data = _get_json_attr(mark, "animatorsPencilMarkData", {}) or {}
            data["source"] = mark
            data["matrix"] = cmds.xform(mark, query=True, matrix=True, objectSpace=True)
            self.clipboard.append(data)
        if cut and self.selected_marks():
            cmds.delete(self.selected_marks())
        self._status("{0} mark(s) copied.".format(len(self.clipboard)))

    def paste_marks(self, layer_node=None):
        layer_node = layer_node or self.active_layer()
        pasted = []
        for item in self.clipboard:
            source = item.get("source")
            if source and cmds.objExists(source):
                dup = cmds.duplicate(source, name="amirPencilPasted_MARK")[0]
                dup = _parent_if_needed(dup, layer_node)
                cmds.xform(dup, matrix=item.get("matrix"), objectSpace=True)
                cmds.move(0.2, -0.2, 0.0, dup, relative=True, objectSpace=True)
                self._mark_node(dup, layer_node, item.get("tool", "Pencil"), item.get("color", (1, 0, 0)), item.get("opacity", 1.0), item.get("size", 2.0))
                pasted.append(dup)
        if pasted:
            cmds.select(pasted, replace=True)
        self._status("{0} mark(s) pasted.".format(len(pasted)))
        return pasted

    def transform_selected(self, tx=0.0, ty=0.0, rotate=0.0, scale=1.0):
        marks = self.selected_marks()
        for mark in marks:
            cmds.move(tx, ty, 0.0, mark, relative=True, objectSpace=True)
            if rotate:
                cmds.rotate(0.0, 0.0, rotate, mark, relative=True, objectSpace=True)
            if abs(scale - 1.0) > 0.001:
                cmds.scale(scale, scale, scale, mark, relative=True, objectSpace=True)
        self._status("Transformed {0} mark(s).".format(len(marks)))

    def transform_layer(self, layer_node=None, tx=0.0, ty=0.0, rotate=0.0, scale=1.0):
        layer_node = layer_node or self.active_layer()
        if not layer_node or not cmds.objExists(layer_node):
            return
        cmds.move(tx, ty, 0.0, layer_node, relative=True, objectSpace=True)
        if rotate:
            cmds.rotate(0.0, 0.0, rotate, layer_node, relative=True, objectSpace=True)
        if abs(scale - 1.0) > 0.001:
            cmds.scale(scale, scale, scale, layer_node, relative=True, objectSpace=True)
        self._status("Layer transformed.")

    def add_key(self):
        marks = self.selected_marks() or self.marks()
        for mark in marks:
            cmds.setKeyframe(mark, attribute=("translate", "rotate", "scale", "visibility"), time=_current_frame())
        self._status("Keyed {0} mark(s).".format(len(marks)))

    def remove_key(self):
        marks = self.selected_marks() or self.marks()
        frame = _current_frame()
        for mark in marks:
            cmds.cutKey(mark, time=(frame, frame), clear=True)
        self._status("Removed keys on frame {0}.".format(frame))

    def duplicate_previous_key(self, layer_node=None):
        layer_node = layer_node or self.active_layer()
        frame = _current_frame()
        created = []
        candidates = []
        for mark in self.marks(layer_node):
            data = _get_json_attr(mark, "animatorsPencilMarkData", {}) or {}
            mark_frame = int(data.get("frame", cmds.getAttr(mark + ".animatorsPencilFrame") if cmds.objExists(mark + ".animatorsPencilFrame") else 0))
            if mark_frame < frame:
                candidates.append((mark_frame, mark))
        if not candidates:
            self._status("No previous drawing key found.")
            return []
        previous_frame = max(item[0] for item in candidates)
        for _, mark in [item for item in candidates if item[0] == previous_frame]:
            dup = cmds.duplicate(mark, name="amirPencilDupKey_MARK")[0]
            dup = _parent_if_needed(dup, layer_node)
            data = _get_json_attr(mark, "animatorsPencilMarkData", {}) or {}
            self._mark_node(dup, layer_node, data.get("tool", "Pencil"), data.get("color", (1, 0, 0)), data.get("opacity", 1.0), data.get("size", 2.0), frame=frame)
            created.append(dup)
        if created:
            cmds.select(created, replace=True)
        self._status("Duplicated frame {0} drawing to frame {1}.".format(previous_frame, frame))
        return created

    def retime_selected(self, offset=1):
        marks = self.selected_marks()
        for mark in marks:
            if not cmds.objExists(mark + ".animatorsPencilFrame"):
                continue
            old_frame = int(cmds.getAttr(mark + ".animatorsPencilFrame"))
            new_frame = old_frame + int(offset)
            cmds.setAttr(mark + ".animatorsPencilFrame", new_frame)
            data = _get_json_attr(mark, "animatorsPencilMarkData", {}) or {}
            data["frame"] = new_frame
            _set_json_attr(mark, "animatorsPencilMarkData", data)
            self._key_mark_visibility(mark, data.get("layer") or self.active_layer(), new_frame)
        self._status("Retimed {0} mark(s).".format(len(marks)))

    def create_frame_marker(self, color=(1.0, 0.9, 0.05), label="Marker"):
        layer = self.active_layer()
        mark = self.create_mark("Text", layer, color=color, size=2.0, opacity=1.0, text="{0} F{1}".format(label, _current_frame()))
        if mark:
            _set_string_attr(mark, "animatorsPencilFrameMarker", "marker")
        return mark

    def make_ghosts(self, layer_node=None, before=1, after=1, before_color=(0.1, 0.6, 1.0), after_color=(1.0, 0.4, 0.1)):
        layer_node = layer_node or self.active_layer()
        ghost_root = "amirAnimatorsPencilGhosts_GRP"
        if cmds.objExists(ghost_root):
            cmds.delete(ghost_root)
        ghost_root = cmds.createNode("transform", name=ghost_root)
        frame = _current_frame()
        count = 0
        for mark in self.marks(layer_node):
            data = _get_json_attr(mark, "animatorsPencilMarkData", {}) or {}
            mark_frame = int(data.get("frame", 0))
            if frame - before <= mark_frame < frame:
                color = before_color
            elif frame < mark_frame <= frame + after:
                color = after_color
            else:
                continue
            dup = cmds.duplicate(mark, name="amirPencilGhost_MARK")[0]
            dup = _parent_if_needed(dup, ghost_root)
            _set_display_color(dup, color, opacity=0.35, line_width=max(1.0, float(data.get("size", 2.0)) * 0.75))
            count += 1
        self._status("Ghosts rebuilt: {0}".format(count))
        return ghost_root

    def clear_ghosts(self):
        if cmds.objExists("amirAnimatorsPencilGhosts_GRP"):
            cmds.delete("amirAnimatorsPencilGhosts_GRP")

    def undo(self):
        if MAYA_AVAILABLE:
            cmds.undo()

    def redo(self):
        if MAYA_AVAILABLE:
            cmds.redo()


class AnimatorsPencilPanel(QtWidgets.QWidget):
    def __init__(self, controller=None, parent=None):
        super(AnimatorsPencilPanel, self).__init__(parent)
        self.controller = controller or AnimatorsPencilController()
        self.controller.set_status_callback(self._set_status)
        self.current_layer = ""
        self._build_ui()
        self.refresh_layers()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        intro = QtWidgets.QLabel(
            "Draws real Maya curves/text in front of chosen camera, so marks stay visible even without this tool installed. "
            "Use Maya viewport 2D Pan/Zoom, tablet input, Move/Rotate/Scale tools, plus this panel for layers, keys, ghosts, retime."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        native = QtWidgets.QGroupBox("Native Maya Blue Pencil")
        native_layout = QtWidgets.QGridLayout(native)
        self.open_native_button = QtWidgets.QPushButton("Open Blue Pencil")
        self.native_tool_button = QtWidgets.QPushButton("Use Tool In Viewport")
        self.native_options_button = QtWidgets.QPushButton("Apply Color / Size / Opacity")
        self.native_insert_button = QtWidgets.QPushButton("Insert BP Frame")
        self.native_duplicate_button = QtWidgets.QPushButton("Duplicate BP Frame")
        self.native_delete_button = QtWidgets.QPushButton("Delete BP Frame")
        self.native_ghost_button = QtWidgets.QPushButton("Native Ghosting")
        native_buttons = (
            self.open_native_button,
            self.native_tool_button,
            self.native_options_button,
            self.native_insert_button,
            self.native_duplicate_button,
            self.native_delete_button,
            self.native_ghost_button,
        )
        for index, button in enumerate(native_buttons):
            native_layout.addWidget(button, index // 3, index % 3)
        layout.addWidget(native)

        top = QtWidgets.QHBoxLayout()
        self.layer_name = QtWidgets.QLineEdit("Pencil Layer")
        top.addWidget(QtWidgets.QLabel("Layer"))
        top.addWidget(self.layer_name, 1)
        self.add_layer_button = QtWidgets.QPushButton("Add Layer")
        self.delete_layer_button = QtWidgets.QPushButton("Delete Layer")
        top.addWidget(self.add_layer_button)
        top.addWidget(self.delete_layer_button)
        layout.addLayout(top)

        self.layer_table = QtWidgets.QTableWidget(0, 5)
        self.layer_table.setHorizontalHeaderLabels(["Layer", "Camera", "State", "Locked", "Marks"])
        self.layer_table.horizontalHeader().setStretchLastSection(True)
        self.layer_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.layer_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.layer_table.setContextMenuPolicy(_qt_flag("ContextMenuPolicy", "CustomContextMenu", QtCore.Qt.CustomContextMenu))
        layout.addWidget(self.layer_table, 1)

        layer_buttons = QtWidgets.QHBoxLayout()
        self.state_combo = QtWidgets.QComboBox()
        self.state_combo.addItems(LAYER_STATES)
        self.layer_up_button = QtWidgets.QPushButton("Layer Up")
        self.layer_down_button = QtWidgets.QPushButton("Layer Down")
        self.move_camera_button = QtWidgets.QPushButton("Move Layer To Current Camera")
        layer_buttons.addWidget(QtWidgets.QLabel("State"))
        layer_buttons.addWidget(self.state_combo)
        layer_buttons.addWidget(self.layer_up_button)
        layer_buttons.addWidget(self.layer_down_button)
        layer_buttons.addWidget(self.move_camera_button, 1)
        layout.addLayout(layer_buttons)

        toolbox = QtWidgets.QGroupBox("Toolbox")
        tool_layout = QtWidgets.QGridLayout(toolbox)
        self.tool_combo = QtWidgets.QComboBox()
        self.tool_combo.addItems(TOOL_NAMES)
        self.color_combo = QtWidgets.QComboBox()
        self.color_combo.addItems(list(DEFAULT_COLORS.keys()))
        self.size_spin = QtWidgets.QDoubleSpinBox()
        self.size_spin.setRange(1.0, 24.0)
        self.size_spin.setValue(3.0)
        self.opacity_spin = QtWidgets.QDoubleSpinBox()
        self.opacity_spin.setRange(0.05, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(1.0)
        self.text_field = QtWidgets.QLineEdit("Note")
        self.draw_button = QtWidgets.QPushButton("Create Mark")
        tool_layout.addWidget(QtWidgets.QLabel("Tool"), 0, 0)
        tool_layout.addWidget(self.tool_combo, 0, 1)
        tool_layout.addWidget(QtWidgets.QLabel("Color"), 0, 2)
        tool_layout.addWidget(self.color_combo, 0, 3)
        tool_layout.addWidget(QtWidgets.QLabel("Size"), 1, 0)
        tool_layout.addWidget(self.size_spin, 1, 1)
        tool_layout.addWidget(QtWidgets.QLabel("Opacity"), 1, 2)
        tool_layout.addWidget(self.opacity_spin, 1, 3)
        tool_layout.addWidget(QtWidgets.QLabel("Text"), 2, 0)
        tool_layout.addWidget(self.text_field, 2, 1, 1, 2)
        tool_layout.addWidget(self.draw_button, 2, 3)
        layout.addWidget(toolbox)

        edit_buttons = QtWidgets.QHBoxLayout()
        self.undo_button = QtWidgets.QPushButton("Undo")
        self.redo_button = QtWidgets.QPushButton("Redo")
        self.copy_button = QtWidgets.QPushButton("Copy Selected")
        self.cut_button = QtWidgets.QPushButton("Cut Selected")
        self.paste_button = QtWidgets.QPushButton("Paste")
        self.delete_marks_button = QtWidgets.QPushButton("Erase Selected")
        for button in (self.undo_button, self.redo_button, self.copy_button, self.cut_button, self.paste_button, self.delete_marks_button):
            edit_buttons.addWidget(button)
        layout.addLayout(edit_buttons)

        transform = QtWidgets.QGroupBox("Transform")
        transform_layout = QtWidgets.QGridLayout(transform)
        self.move_left_button = QtWidgets.QPushButton("Left")
        self.move_right_button = QtWidgets.QPushButton("Right")
        self.move_up_button = QtWidgets.QPushButton("Up")
        self.move_down_button = QtWidgets.QPushButton("Down")
        self.rotate_left_button = QtWidgets.QPushButton("Rotate -5")
        self.rotate_right_button = QtWidgets.QPushButton("Rotate +5")
        self.scale_down_button = QtWidgets.QPushButton("Scale 90%")
        self.scale_up_button = QtWidgets.QPushButton("Scale 110%")
        self.transform_layer_button = QtWidgets.QPushButton("Apply To Full Layer")
        for i, button in enumerate((self.move_left_button, self.move_right_button, self.move_up_button, self.move_down_button, self.rotate_left_button, self.rotate_right_button, self.scale_down_button, self.scale_up_button)):
            transform_layout.addWidget(button, i // 4, i % 4)
        transform_layout.addWidget(self.transform_layer_button, 2, 0, 1, 4)
        layout.addWidget(transform)

        anim = QtWidgets.QGroupBox("Animation")
        anim_layout = QtWidgets.QGridLayout(anim)
        self.add_key_button = QtWidgets.QPushButton("Add Key")
        self.remove_key_button = QtWidgets.QPushButton("Remove Key")
        self.duplicate_key_button = QtWidgets.QPushButton("Duplicate Previous Key")
        self.marker_button = QtWidgets.QPushButton("Add Frame Marker")
        self.retime_back_button = QtWidgets.QPushButton("Retime -1")
        self.retime_forward_button = QtWidgets.QPushButton("Retime +1")
        self.ghost_button = QtWidgets.QPushButton("Build Ghosts")
        self.clear_ghosts_button = QtWidgets.QPushButton("Clear Ghosts")
        for i, button in enumerate((self.add_key_button, self.remove_key_button, self.duplicate_key_button, self.marker_button, self.retime_back_button, self.retime_forward_button, self.ghost_button, self.clear_ghosts_button)):
            anim_layout.addWidget(button, i // 4, i % 4)
        layout.addWidget(anim)

        self.status_label = QtWidgets.QLabel("Ready.")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.add_layer_button.clicked.connect(self._add_layer)
        self.open_native_button.clicked.connect(self.controller.open_native_blue_pencil)
        self.native_tool_button.clicked.connect(lambda: self.controller.set_native_tool(self.tool_combo.currentText()))
        self.native_options_button.clicked.connect(lambda: self.controller.apply_native_options(self.tool_combo.currentText(), self._current_color(), self.size_spin.value(), self.opacity_spin.value()))
        self.native_insert_button.clicked.connect(lambda: self.controller.native_frame_command("insert"))
        self.native_duplicate_button.clicked.connect(lambda: self.controller.native_frame_command("duplicate"))
        self.native_delete_button.clicked.connect(lambda: self.controller.native_frame_command("delete"))
        self.native_ghost_button.clicked.connect(self.controller.configure_native_ghosting)
        self.delete_layer_button.clicked.connect(self._delete_layer)
        self.layer_table.itemSelectionChanged.connect(self._layer_selection_changed)
        self.layer_table.customContextMenuRequested.connect(self._show_layer_menu)
        self.state_combo.currentTextChanged.connect(self._set_layer_state)
        self.layer_up_button.clicked.connect(lambda: self._move_layer(-1))
        self.layer_down_button.clicked.connect(lambda: self._move_layer(1))
        self.move_camera_button.clicked.connect(self._move_layer_to_camera)
        self.draw_button.clicked.connect(self._create_mark)
        self.undo_button.clicked.connect(self.controller.undo)
        self.redo_button.clicked.connect(self.controller.redo)
        self.copy_button.clicked.connect(lambda: self.controller.copy_selected_marks(False))
        self.cut_button.clicked.connect(lambda: self.controller.copy_selected_marks(True))
        self.paste_button.clicked.connect(lambda: self._after_action(self.controller.paste_marks(self.current_layer)))
        self.delete_marks_button.clicked.connect(lambda: self._after_action(self.controller.delete_selected_marks()))
        self.move_left_button.clicked.connect(lambda: self.controller.transform_selected(tx=-0.1))
        self.move_right_button.clicked.connect(lambda: self.controller.transform_selected(tx=0.1))
        self.move_up_button.clicked.connect(lambda: self.controller.transform_selected(ty=0.1))
        self.move_down_button.clicked.connect(lambda: self.controller.transform_selected(ty=-0.1))
        self.rotate_left_button.clicked.connect(lambda: self.controller.transform_selected(rotate=-5.0))
        self.rotate_right_button.clicked.connect(lambda: self.controller.transform_selected(rotate=5.0))
        self.scale_down_button.clicked.connect(lambda: self.controller.transform_selected(scale=0.9))
        self.scale_up_button.clicked.connect(lambda: self.controller.transform_selected(scale=1.1))
        self.transform_layer_button.clicked.connect(lambda: self.controller.transform_layer(self.current_layer, scale=1.05))
        self.add_key_button.clicked.connect(self.controller.add_key)
        self.remove_key_button.clicked.connect(self.controller.remove_key)
        self.duplicate_key_button.clicked.connect(lambda: self._after_action(self.controller.duplicate_previous_key(self.current_layer)))
        self.marker_button.clicked.connect(lambda: self._after_action(self.controller.create_frame_marker(self._current_color())))
        self.retime_back_button.clicked.connect(lambda: self.controller.retime_selected(-1))
        self.retime_forward_button.clicked.connect(lambda: self.controller.retime_selected(1))
        self.ghost_button.clicked.connect(lambda: self.controller.make_ghosts(self.current_layer))
        self.clear_ghosts_button.clicked.connect(self.controller.clear_ghosts)

    def _set_status(self, message):
        self.status_label.setText(message)

    def _after_action(self, _result=None):
        self.refresh_layers()

    def _current_color(self):
        return DEFAULT_COLORS.get(self.color_combo.currentText(), DEFAULT_COLORS["Red"])

    def refresh_layers(self):
        layers = self.controller.layers() if MAYA_AVAILABLE else []
        self.layer_table.blockSignals(True)
        self.layer_table.setRowCount(len(layers))
        for row, layer in enumerate(layers):
            for col, value in enumerate((layer.get("name"), layer.get("camera"), layer.get("state"), "Yes" if layer.get("locked") else "No", str(layer.get("count", 0)))):
                item = QtWidgets.QTableWidgetItem(value or "")
                item.setData(_qt_flag("ItemDataRole", "UserRole", QtCore.Qt.UserRole), layer.get("node"))
                self.layer_table.setItem(row, col, item)
        self.layer_table.blockSignals(False)
        if layers:
            active = self.controller.active_layer()
            row = next((i for i, layer in enumerate(layers) if layer["node"] == active), 0)
            self.layer_table.selectRow(row)
            self.current_layer = layers[row]["node"]
            self.state_combo.blockSignals(True)
            self.state_combo.setCurrentText(layers[row].get("state", "Animation"))
            self.state_combo.blockSignals(False)
        else:
            self.current_layer = ""

    def _selected_layer_from_table(self):
        rows = self.layer_table.selectionModel().selectedRows() if self.layer_table.selectionModel() else []
        if not rows:
            return self.current_layer
        item = self.layer_table.item(rows[0].row(), 0)
        return item.data(_qt_flag("ItemDataRole", "UserRole", QtCore.Qt.UserRole)) if item else self.current_layer

    def _layer_selection_changed(self):
        layer = self._selected_layer_from_table()
        if layer:
            self.current_layer = layer
            self.controller.set_active_layer(layer)
            data = self.controller.layer_data(layer)
            self.state_combo.blockSignals(True)
            self.state_combo.setCurrentText(data.get("state", "Animation"))
            self.state_combo.blockSignals(False)

    def _add_layer(self):
        self.current_layer = self.controller.create_layer(self.layer_name.text() or "Pencil Layer")
        self.refresh_layers()

    def _delete_layer(self):
        layer = self._selected_layer_from_table()
        if not layer:
            return
        result = QtWidgets.QMessageBox.question(self, "Delete Layer", "Delete this pencil layer and all marks inside it?")
        if result == QtWidgets.QMessageBox.Yes:
            self.controller.delete_layer(layer)
            self.refresh_layers()

    def _set_layer_state(self, state):
        layer = self._selected_layer_from_table()
        if layer:
            self.controller.set_layer_state(layer, state)
            self.refresh_layers()

    def _move_layer(self, delta):
        layer = self._selected_layer_from_table()
        if layer:
            self.controller.move_layer_order(layer, delta)
            self.refresh_layers()

    def _move_layer_to_camera(self):
        layer = self._selected_layer_from_table()
        if layer:
            self.controller.move_layer_to_camera(layer)
            self.refresh_layers()

    def _create_mark(self):
        mark = self.controller.create_mark(
            tool=self.tool_combo.currentText(),
            layer_node=self.current_layer,
            color=self._current_color(),
            size=self.size_spin.value(),
            opacity=self.opacity_spin.value(),
            text=self.text_field.text(),
        )
        self._after_action(mark)

    def _show_layer_menu(self, position):
        menu = QtWidgets.QMenu(self)
        menu.addAction("Set Active Layer", self._layer_selection_changed)
        menu.addAction("Add Layer", self._add_layer)
        menu.addAction("Delete Layer", self._delete_layer)
        menu.addSeparator()
        menu.addAction("Layer Up", lambda: self._move_layer(-1))
        menu.addAction("Layer Down", lambda: self._move_layer(1))
        menu.addAction("Move Layer To Current Camera", self._move_layer_to_camera)
        menu.exec_(self.layer_table.mapToGlobal(position))


class AnimatorsPencilWindow(QtWidgets.QDialog):
    def __init__(self, controller=None, parent=None):
        super(AnimatorsPencilWindow, self).__init__(parent)
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle("Animators Pencil")
        self.controller = controller or AnimatorsPencilController()
        layout = QtWidgets.QVBoxLayout(self)
        self.panel = AnimatorsPencilPanel(self.controller, self)
        layout.addWidget(self.panel)
        self.resize(760, 760)


GLOBAL_CONTROLLER = None
GLOBAL_WINDOW = None


def launch_animators_pencil():
    global GLOBAL_CONTROLLER, GLOBAL_WINDOW
    if GLOBAL_WINDOW:
        try:
            GLOBAL_WINDOW.close()
        except Exception:
            pass
    GLOBAL_CONTROLLER = AnimatorsPencilController()
    GLOBAL_WINDOW = AnimatorsPencilWindow(GLOBAL_CONTROLLER)
    GLOBAL_WINDOW.show()
    return GLOBAL_WINDOW


def run_smoke_scene():
    if not MAYA_AVAILABLE:
        return {"available": False}
    for layer_info in AnimatorsPencilController().layers():
        if layer_info.get("name") == "Smoke Layer" and cmds.objExists(layer_info.get("node")):
            cmds.delete(layer_info.get("node"))
    if cmds.objExists("amirAnimatorsPencilGhosts_GRP"):
        cmds.delete("amirAnimatorsPencilGhosts_GRP")
    controller = AnimatorsPencilController()
    layer = controller.create_layer("Smoke Layer", camera=_current_camera(), state="Animation")
    cmds.currentTime(10)
    line = controller.create_mark("Line", layer, DEFAULT_COLORS["Blue"], 4.0, 0.9)
    rect = controller.create_mark("Rectangle", layer, DEFAULT_COLORS["Yellow"], 3.0, 1.0)
    text = controller.create_mark("Text", layer, DEFAULT_COLORS["White"], 2.0, 1.0, text="Animators Pencil")
    controller.add_key()
    cmds.currentTime(12)
    dupes = controller.duplicate_previous_key(layer)
    ghosts = controller.make_ghosts(layer, before=3, after=3)
    data = {
        "root_exists": cmds.objExists(ROOT_GROUP_NAME),
        "layer": layer,
        "line": line,
        "rect": rect,
        "text": text,
        "dupe_count": len(dupes),
        "ghost_exists": cmds.objExists(ghosts),
        "mark_count": len(controller.marks(layer)),
        "scene_native_mark_shapes": len(cmds.listRelatives(layer, allDescendents=True, type="nurbsCurve") or []),
        "layer_data": controller.layer_data(layer),
    }
    return data


if __name__ == "__main__":
    launch_animators_pencil()
