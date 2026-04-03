"""
maya_tutorial_authoring.py

Scene-bound tutorial authoring and playback for Maya 2022-2026.
"""

from __future__ import absolute_import, division, print_function

import copy
import datetime
import json
import math
import os
import time
import uuid

import maya_shelf_utils
import maya_skinning_cleanup as skin_cleanup

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.OpenMayaUI as omui
    import maya.mel as mel

    MAYA_AVAILABLE = True
except Exception:
    cmds = None
    om = None
    omui = None
    mel = None
    MAYA_AVAILABLE = False

try:
    from PySide6 import QtCore, QtGui, QtWidgets
    import shiboken6 as shiboken

    QT_BINDING = "PySide6"
except Exception:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        import shiboken2 as shiboken

        QT_BINDING = "PySide2"
    except Exception:
        QtCore = None
        QtGui = None
        QtWidgets = None
        shiboken = None
        QT_BINDING = None


WINDOW_OBJECT_NAME = "mayaTutorialAuthoringWindow"
WORKSPACE_CONTROL_NAME = WINDOW_OBJECT_NAME + "WorkspaceControl"
FOLLOW_AMIR_URL = "https://followamir.com"
DEFAULT_DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=2U2GXSKFJKJCA"
DONATE_URL = os.environ.get("AMIR_PAYPAL_DONATE_URL") or os.environ.get("AMIR_DONATE_URL") or DEFAULT_DONATE_URL
DEFAULT_SHELF_NAME = maya_shelf_utils.DEFAULT_SHELF_NAME
DEFAULT_SHELF_BUTTON_LABEL = "Tutorials"
SHELF_BUTTON_DOC_TAG = "mayaTutorialAuthoringShelfButton"
LESSON_ROOT_NODE = "amirTutorialLessons_META"
LESSON_JSON_ATTR = "amirTutorialLessonsJson"
LESSON_VERSION = 1
TARGET_PICK_DELAY_MS = 1800
HIGHLIGHT_DURATION_MS = 2200
VALUE_EPSILON = 1.0e-4
SCROLL_MIN_HEIGHT = 520
AUTO_RECORD_POLL_MS = 250
AUTO_RECORD_DEBOUNCE_MS = 420
AUTO_RECORD_TARGET_TTL_MS = 1400
PLAYBACK_MODE_AUTHOR = "author"
PLAYBACK_MODE_GUIDED = "guided_practice"
PLAYBACK_MODE_PLAYER = "player"
PLAYBACK_MODE_POSE_COMPARE = "pose_compare"
POSE_COMPARE_ROOT_NODE = "amirPoseCompare_META"
POSE_COMPARE_JSON_ATTR = "amirPoseCompareJson"
POSE_COMPARE_GROUP_NAME = "amirPoseCompare_GRP"
POSE_COMPARE_DEFAULT_OFFSET = 18.0
POSE_COMPARE_BEFORE = "before"
POSE_COMPARE_AFTER = "after"
POSE_COMPARE_STYLES = {
    POSE_COMPARE_BEFORE: {
        "label": "Before Ghost (Left)",
        "offset_sign": -1.0,
        "material_name": "amirPoseCompareBefore_MAT",
        "shading_group": "amirPoseCompareBefore_SG",
        "color": (1.0, 0.56, 0.24),
        "transparency": (0.45, 0.45, 0.45),
    },
    POSE_COMPARE_AFTER: {
        "label": "Fix Ghost (Right)",
        "offset_sign": 1.0,
        "material_name": "amirPoseCompareAfter_MAT",
        "shading_group": "amirPoseCompareAfter_SG",
        "color": (0.24, 0.84, 1.0),
        "transparency": (0.34, 0.34, 0.34),
    },
}

GLOBAL_CONTROLLER = None
GLOBAL_WINDOW = None

_qt_flag = skin_cleanup._qt_flag
_style_donate_button = skin_cleanup._style_donate_button
_open_external_url = skin_cleanup._open_external_url
_maya_main_window = skin_cleanup._maya_main_window
_short_name = skin_cleanup._short_name


def _debug(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayInfo("[Maya Tutorial Authoring] {0}".format(message))


def _warning(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayWarning("[Maya Tutorial Authoring] {0}".format(message))


def _error(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayError("[Maya Tutorial Authoring] {0}".format(message))


def _now_iso():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _copy_json(data):
    return json.loads(json.dumps(data))


def _normalize_text(text):
    value = (text or "").replace("&", "").strip()
    return " ".join(value.split())


def _stable_id(prefix):
    return "{0}_{1}".format(prefix, uuid.uuid4().hex[:12])


def _safe_scene_name():
    if not MAYA_AVAILABLE:
        return ""
    try:
        return cmds.file(query=True, sceneName=True) or ""
    except Exception:
        return ""


def _set_string_attr(node_name, attr_name, value):
    if not cmds.attributeQuery(attr_name, node=node_name, exists=True):
        cmds.addAttr(node_name, longName=attr_name, dataType="string")
    cmds.setAttr("{0}.{1}".format(node_name, attr_name), value or "", type="string")


def _get_string_attr(node_name, attr_name, default=""):
    if not cmds.objExists(node_name) or not cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return default
    try:
        value = cmds.getAttr("{0}.{1}".format(node_name, attr_name))
    except Exception:
        return default
    return value if value is not None else default


def _empty_manifest():
    return {
        "version": LESSON_VERSION,
        "scene_name": _safe_scene_name(),
        "lessons": [],
    }


def _ensure_lessons_root():
    if cmds.objExists(LESSON_ROOT_NODE):
        return LESSON_ROOT_NODE
    root = cmds.createNode("network", name=LESSON_ROOT_NODE)
    _set_string_attr(root, LESSON_JSON_ATTR, json.dumps(_empty_manifest(), sort_keys=True))
    return root


def _load_manifest():
    if not MAYA_AVAILABLE:
        return _empty_manifest()
    root = _ensure_lessons_root()
    raw = _get_string_attr(root, LESSON_JSON_ATTR, "")
    if not raw:
        payload = _empty_manifest()
        _save_manifest(payload)
        return payload
    try:
        payload = json.loads(raw)
    except Exception:
        payload = _empty_manifest()
    if payload.get("version") != LESSON_VERSION:
        payload["version"] = LESSON_VERSION
    if not isinstance(payload.get("lessons"), list):
        payload["lessons"] = []
    payload["scene_name"] = _safe_scene_name()
    return payload


def _save_manifest(payload):
    if not MAYA_AVAILABLE:
        return
    root = _ensure_lessons_root()
    payload = copy.deepcopy(payload or _empty_manifest())
    payload["version"] = LESSON_VERSION
    payload["scene_name"] = _safe_scene_name()
    _set_string_attr(root, LESSON_JSON_ATTR, json.dumps(payload, sort_keys=True))


def _empty_pose_compare_manifest():
    return {
        "version": LESSON_VERSION,
        "scene_name": _safe_scene_name(),
        "snapshots": [],
    }


def _ensure_pose_compare_root():
    if cmds.objExists(POSE_COMPARE_ROOT_NODE):
        return POSE_COMPARE_ROOT_NODE
    root = cmds.createNode("network", name=POSE_COMPARE_ROOT_NODE)
    _set_string_attr(root, POSE_COMPARE_JSON_ATTR, json.dumps(_empty_pose_compare_manifest(), sort_keys=True))
    return root


def _load_pose_compare_manifest():
    if not MAYA_AVAILABLE:
        return _empty_pose_compare_manifest()
    root = _ensure_pose_compare_root()
    raw = _get_string_attr(root, POSE_COMPARE_JSON_ATTR, "")
    if not raw:
        payload = _empty_pose_compare_manifest()
        _save_pose_compare_manifest(payload)
        return payload
    try:
        payload = json.loads(raw)
    except Exception:
        payload = _empty_pose_compare_manifest()
    if payload.get("version") != LESSON_VERSION:
        payload["version"] = LESSON_VERSION
    if not isinstance(payload.get("snapshots"), list):
        payload["snapshots"] = []
    payload["scene_name"] = _safe_scene_name()
    return payload


def _save_pose_compare_manifest(payload):
    if not MAYA_AVAILABLE:
        return
    root = _ensure_pose_compare_root()
    payload = copy.deepcopy(payload or _empty_pose_compare_manifest())
    payload["version"] = LESSON_VERSION
    payload["scene_name"] = _safe_scene_name()
    _set_string_attr(root, POSE_COMPARE_JSON_ATTR, json.dumps(payload, sort_keys=True))


def _node_long_name(node_name):
    if not MAYA_AVAILABLE or not node_name:
        return node_name
    values = cmds.ls(node_name, long=True) or []
    return values[0] if values else node_name


def _node_uuid(node_name):
    if not MAYA_AVAILABLE or not node_name or not cmds.objExists(node_name):
        return ""
    values = cmds.ls(node_name, uuid=True) or []
    return values[0] if values else ""


def _node_by_uuid(node_uuid, fallback_name=""):
    if not MAYA_AVAILABLE:
        return ""
    if node_uuid:
        matches = cmds.ls(node_uuid, long=True) or []
        if matches:
            return matches[0]
    if fallback_name and cmds.objExists(fallback_name):
        return _node_long_name(fallback_name)
    short_name = _short_name(fallback_name) if fallback_name else ""
    if short_name and cmds.objExists(short_name):
        return _node_long_name(short_name)
    return ""


def _safe_selected_nodes():
    if not MAYA_AVAILABLE:
        return []
    return cmds.ls(selection=True, long=True) or []


def _selection_payload():
    payload = []
    for node_name in _safe_selected_nodes():
        payload.append(
            {
                "uuid": _node_uuid(node_name),
                "name": _node_long_name(node_name),
                "short_name": _short_name(node_name),
            }
        )
    return payload


def _apply_selection_payload(payload):
    node_names = []
    for entry in payload or []:
        resolved = _node_by_uuid(entry.get("uuid", ""), entry.get("name", ""))
        if resolved:
            node_names.append(resolved)
    if node_names:
        cmds.select(node_names, replace=True)
    else:
        cmds.select(clear=True)


def _auto_key_enabled():
    if not MAYA_AVAILABLE:
        return False
    try:
        return bool(cmds.autoKeyframe(query=True, state=True))
    except Exception:
        return False


def _general_checkpoint():
    current_time = 1.0
    if MAYA_AVAILABLE:
        try:
            current_time = float(cmds.currentTime(query=True))
        except Exception:
            current_time = 1.0
    return {
        "current_time": current_time,
        "selection": _selection_payload(),
        "auto_key": _auto_key_enabled(),
    }


def _restore_general_checkpoint(payload):
    state = payload or {}
    if "current_time" in state:
        try:
            cmds.currentTime(float(state.get("current_time", 1.0)), edit=True)
        except Exception:
            pass
    if "auto_key" in state:
        try:
            cmds.autoKeyframe(state=bool(state.get("auto_key")))
        except Exception:
            pass
    _apply_selection_payload(state.get("selection") or [])


def _selected_roots_payload(node_names):
    payload = []
    for node_name in node_names or []:
        resolved = _node_long_name(node_name)
        if not resolved or not cmds.objExists(resolved):
            continue
        payload.append(
            {
                "uuid": _node_uuid(resolved),
                "name": resolved,
                "short_name": _short_name(resolved),
            }
        )
    return payload


def _resolve_root_payload_entries(payload):
    node_names = []
    for entry in payload or []:
        resolved = _node_by_uuid(entry.get("uuid", ""), entry.get("name", ""))
        if resolved and resolved not in node_names:
            node_names.append(resolved)
    return node_names


def _transform_nodes_under_roots(root_nodes):
    ordered = []
    seen = set()
    for root_name in root_nodes or []:
        resolved = _node_long_name(root_name)
        if not resolved or not cmds.objExists(resolved):
            continue
        candidates = [resolved]
        candidates.extend(cmds.listRelatives(resolved, allDescendents=True, fullPath=True, type="transform") or [])
        for node_name in candidates:
            long_name = _node_long_name(node_name)
            if not long_name or long_name in seen:
                continue
            seen.add(long_name)
            ordered.append(long_name)
    return ordered


def _mesh_snapshot_transforms(root_nodes):
    ordered = []
    seen = set()
    for node_name in _transform_nodes_under_roots(root_nodes):
        mesh_shapes = cmds.listRelatives(node_name, shapes=True, fullPath=True, type="mesh") or []
        has_visible_shape = False
        for shape_name in mesh_shapes:
            try:
                if cmds.getAttr(shape_name + ".intermediateObject"):
                    continue
            except Exception:
                pass
            has_visible_shape = True
            break
        if not has_visible_shape or node_name in seen:
            continue
        seen.add(node_name)
        ordered.append(node_name)
    return ordered


def _current_time_float():
    if not MAYA_AVAILABLE:
        return 1.0
    try:
        return float(cmds.currentTime(query=True))
    except Exception:
        return 1.0


def _pose_attr_state(node_name, attr_name, frame_value):
    plug_name = "{0}.{1}".format(node_name, attr_name)
    if not cmds.objExists(plug_name):
        return None
    value = _get_attr_value(node_name, attr_name)
    if value is None:
        return None
    anim_curves = cmds.listConnections(plug_name, source=True, destination=False, type="animCurve") or []
    keys_here = cmds.keyframe(node_name, attribute=attr_name, query=True, time=(frame_value, frame_value), valueChange=True) or []
    return {
        "value": _copy_json(value),
        "animated": bool(anim_curves),
        "had_key_on_frame": bool(keys_here),
    }


def _capture_pose_restore_state(root_nodes, frame_value):
    payload = {
        "frame": float(frame_value),
        "roots": _selected_roots_payload(root_nodes),
        "transforms": [],
    }
    for node_name in _transform_nodes_under_roots(root_nodes):
        attrs = {}
        for attr_name in (
            "translateX",
            "translateY",
            "translateZ",
            "rotateX",
            "rotateY",
            "rotateZ",
            "scaleX",
            "scaleY",
            "scaleZ",
            "visibility",
        ):
            state = _pose_attr_state(node_name, attr_name, frame_value)
            if state is not None:
                attrs[attr_name] = state
        if attrs:
            payload["transforms"].append(
                {
                    "uuid": _node_uuid(node_name),
                    "name": _node_long_name(node_name),
                    "short_name": _short_name(node_name),
                    "attrs": attrs,
                }
            )
    return payload


def _restore_pose_restore_state(payload):
    frame_value = float((payload or {}).get("frame", _current_time_float()))
    try:
        cmds.currentTime(frame_value, edit=True)
    except Exception:
        pass
    for transform_state in (payload or {}).get("transforms") or []:
        node_name = _node_by_uuid(transform_state.get("uuid", ""), transform_state.get("name", ""))
        if not node_name:
            continue
        for attr_name, attr_state in (transform_state.get("attrs") or {}).items():
            plug_name = "{0}.{1}".format(node_name, attr_name)
            if not cmds.objExists(plug_name):
                continue
            if attr_state.get("animated"):
                try:
                    if attr_state.get("had_key_on_frame"):
                        cmds.setKeyframe(node_name, attribute=attr_name, time=frame_value, value=attr_state.get("value"))
                    else:
                        cmds.cutKey(node_name, attribute=attr_name, time=(frame_value, frame_value), clear=True)
                except Exception:
                    pass
            if not attr_state.get("animated") or attr_state.get("had_key_on_frame"):
                _set_attr_value(node_name, attr_name, attr_state.get("value"))
    try:
        cmds.currentTime(frame_value, edit=True)
    except Exception:
        pass


def _ensure_pose_compare_group():
    if cmds.objExists(POSE_COMPARE_GROUP_NAME):
        return _node_long_name(POSE_COMPARE_GROUP_NAME)
    return _node_long_name(cmds.createNode("transform", name=POSE_COMPARE_GROUP_NAME))


def _ensure_pose_compare_material(style_key):
    style = POSE_COMPARE_STYLES.get(style_key, POSE_COMPARE_STYLES[POSE_COMPARE_AFTER])
    material_name = style.get("material_name")
    shading_group = style.get("shading_group")
    if not cmds.objExists(material_name):
        material_name = cmds.shadingNode("lambert", asShader=True, name=material_name)
    if not cmds.objExists(shading_group):
        shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shading_group)
    try:
        cmds.connectAttr(material_name + ".outColor", shading_group + ".surfaceShader", force=True)
    except Exception:
        pass
    try:
        cmds.setAttr(material_name + ".color", *style.get("color", (0.24, 0.84, 1.0)), type="double3")
        cmds.setAttr(material_name + ".transparency", *style.get("transparency", (0.34, 0.34, 0.34)), type="double3")
        cmds.setAttr(material_name + ".ambientColor", 0.08, 0.08, 0.08, type="double3")
        cmds.setAttr(material_name + ".diffuse", 0.9)
    except Exception:
        pass
    return material_name, shading_group


def _apply_pose_compare_material(snapshot_group, style_key):
    _material_name, shading_group = _ensure_pose_compare_material(style_key)
    mesh_shapes = cmds.listRelatives(snapshot_group, allDescendents=True, fullPath=True, type="mesh") or []
    for shape_name in mesh_shapes:
        try:
            cmds.sets(shape_name, edit=True, forceElement=shading_group)
        except Exception:
            pass


def _snapshot_visibility_window(group_name, frame_value):
    start_frame = float(frame_value) - 1.0
    end_frame = float(frame_value) + 1.0
    for key_time, value in ((start_frame, 0), (float(frame_value), 1), (end_frame, 0)):
        try:
            cmds.setKeyframe(group_name, attribute="visibility", time=key_time, value=value)
        except Exception:
            pass
    try:
        cmds.keyTangent(group_name, attribute="visibility", time=(start_frame, end_frame), inTangentType="stepnext", outTangentType="step")
    except Exception:
        pass
    return {"start_frame": start_frame, "frame": float(frame_value), "end_frame": end_frame}


def _group_bbox_width(node_name):
    try:
        bbox = cmds.exactWorldBoundingBox(node_name)
    except Exception:
        return 0.0
    if not bbox or len(bbox) != 6:
        return 0.0
    return abs(float(bbox[3]) - float(bbox[0]))


def _recommended_pose_compare_offset(root_nodes, base_distance):
    width_total = 0.0
    for node_name in _mesh_snapshot_transforms(root_nodes):
        width_total = max(width_total, _group_bbox_width(node_name))
    if width_total <= VALUE_EPSILON:
        return float(base_distance or POSE_COMPARE_DEFAULT_OFFSET)
    return max(float(base_distance or POSE_COMPARE_DEFAULT_OFFSET), width_total * 1.25)


def _pose_snapshot_group_name(style_key, frame_value):
    return "{0}_{1}_f{2:04d}_GRP".format(
        POSE_COMPARE_GROUP_NAME,
        style_key,
        int(round(float(frame_value))),
    )


def _delete_pose_snapshot_group(group_name):
    if not group_name:
        return True
    if not cmds.objExists(group_name):
        resolved = _node_by_uuid("", group_name)
        if not resolved or not cmds.objExists(resolved):
            return True
        group_name = resolved
    try:
        cmds.delete(group_name)
        return True
    except Exception:
        return False


def _create_pose_compare_snapshot_nodes(root_nodes, frame_value, label_text, style_key, offset_distance):
    mesh_transforms = _mesh_snapshot_transforms(root_nodes)
    if not mesh_transforms:
        return False, "Pick at least one root that contains visible mesh geometry.", {}
    parent_group = _ensure_pose_compare_group()
    offset_distance = _recommended_pose_compare_offset(root_nodes, offset_distance)
    style = POSE_COMPARE_STYLES.get(style_key, POSE_COMPARE_STYLES[POSE_COMPARE_AFTER])
    signed_offset = float(offset_distance) * float(style.get("offset_sign", 1.0))
    group_name = cmds.createNode("transform", name=_pose_snapshot_group_name(style_key, frame_value), parent=parent_group)
    duplicated_roots = []
    for node_name in mesh_transforms:
        duplicate = cmds.duplicate(node_name, renameChildren=True, upstreamNodes=False, inputConnections=False)[0]
        duplicate = cmds.parent(duplicate, group_name)[0]
        try:
            cmds.delete(duplicate, constructionHistory=True)
        except Exception:
            pass
        duplicated_roots.append(_node_long_name(duplicate))
    try:
        cmds.xform(group_name, relative=True, worldSpace=True, translation=(signed_offset, 0.0, 0.0))
    except Exception:
        pass
    _apply_pose_compare_material(group_name, style_key)
    visibility_window = _snapshot_visibility_window(group_name, frame_value)
    _set_string_attr(group_name, "amirPoseCompareLabel", label_text or "")
    _set_string_attr(group_name, "amirPoseCompareStyle", style_key)
    return True, "Created the pose ghost snapshot.", {
        "group_name": _node_long_name(group_name),
        "group_uuid": _node_uuid(group_name),
        "style": style_key,
        "frame": float(frame_value),
        "offset": [signed_offset, 0.0, 0.0],
        "visibility": visibility_window,
        "duplicated_roots": _selected_roots_payload(duplicated_roots),
    }


def _current_frame_int():
    try:
        return int(round(float(cmds.currentTime(query=True))))
    except Exception:
        return 1


def _serializable_attr_value(value):
    if isinstance(value, (int, float, bool, str)):
        return value
    if isinstance(value, (list, tuple)):
        if len(value) == 1 and isinstance(value[0], (list, tuple)):
            return _serializable_attr_value(value[0])
        return [_serializable_attr_value(item) for item in value]
    return None


def _values_close(left, right):
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        if len(left) != len(right):
            return False
        return all(_values_close(left[index], right[index]) for index in range(len(left)))
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        try:
            return abs(float(left) - float(right)) <= VALUE_EPSILON
        except Exception:
            return False
    return left == right


def _get_attr_value(node_name, attr_name):
    plug = "{0}.{1}".format(node_name, attr_name)
    if not cmds.objExists(plug):
        return None
    try:
        value = cmds.getAttr(plug)
    except Exception:
        return None
    return _serializable_attr_value(value)


def _set_attr_value(node_name, attr_name, value):
    plug = "{0}.{1}".format(node_name, attr_name)
    if not cmds.objExists(plug):
        return False
    try:
        attr_type = cmds.getAttr(plug, type=True)
    except Exception:
        attr_type = ""
    try:
        if attr_type == "string":
            cmds.setAttr(plug, value or "", type="string")
            return True
        if isinstance(value, (list, tuple)):
            cmds.setAttr(plug, *value)
        else:
            cmds.setAttr(plug, value)
        return True
    except Exception:
        return False


def _playback_slider_name():
    if not MAYA_AVAILABLE or not mel:
        return ""
    try:
        if cmds.about(batch=True):
            return ""
    except Exception:
        pass
    try:
        slider = mel.eval("$tmpVar=$gPlayBackSlider")
    except Exception:
        return ""
    try:
        if slider and cmds.control(slider, exists=True):
            return slider
    except Exception:
        return ""
    return ""


def _find_qt_control(control_name):
    if not (MAYA_AVAILABLE and QtWidgets and omui and shiboken and control_name):
        return None
    pointer = None
    for resolver in (omui.MQtUtil.findControl, omui.MQtUtil.findLayout, omui.MQtUtil.findMenuItem):
        try:
            pointer = resolver(control_name)
        except Exception:
            pointer = None
        if pointer:
            break
    if not pointer:
        return None
    try:
        return shiboken.wrapInstance(int(pointer), QtWidgets.QWidget)
    except Exception:
        return None


def _find_widgets_by_text(text):
    normalized = _normalize_text(text)
    if not normalized or not QtWidgets:
        return []
    main_window = _maya_main_window()
    widgets = []
    if not main_window:
        return widgets
    for widget in main_window.findChildren(QtWidgets.QWidget):
        for attribute in ("text", "windowTitle", "title", "placeholderText"):
            getter = getattr(widget, attribute, None)
            if not callable(getter):
                continue
            try:
                value = getter()
            except Exception:
                continue
            if _normalize_text(value) == normalized:
                widgets.append(widget)
                break
    return widgets


def _menu_bar_widget():
    main_window = _maya_main_window()
    if not main_window or not QtWidgets:
        return None
    for menu_bar in main_window.findChildren(QtWidgets.QMenuBar):
        try:
            menu_bar.actions()
        except Exception:
            continue
        return menu_bar
    return None


def _find_menu_action_rect(menu_label):
    menu_bar = _menu_bar_widget()
    normalized = _normalize_text(menu_label)
    if menu_bar:
        try:
            actions = menu_bar.actions()
        except Exception:
            actions = []
        for action in actions:
            if _normalize_text(action.text()) != normalized:
                continue
            rect = menu_bar.actionGeometry(action)
            if rect.isNull():
                continue
            top_left = menu_bar.mapToGlobal(rect.topLeft())
            return QtCore.QRect(top_left, rect.size())
    if MAYA_AVAILABLE:
        for menu_name in cmds.lsUI(menus=True) or []:
            try:
                label = cmds.menu(menu_name, query=True, label=True) or ""
            except Exception:
                continue
            if _normalize_text(label) != normalized:
                continue
            widget = _find_qt_control(menu_name)
            if not widget:
                continue
            try:
                menu_action = widget.menuAction()
                parent_widget = menu_action.parentWidget() or widget.parentWidget()
                if not parent_widget:
                    continue
                rect = parent_widget.actionGeometry(menu_action)
                if rect.isNull():
                    continue
                top_left = parent_widget.mapToGlobal(rect.topLeft())
                return QtCore.QRect(top_left, rect.size())
            except Exception:
                continue
    return None


def _shelf_button_target_by_doc_tag(doc_tag):
    if not MAYA_AVAILABLE or not doc_tag:
        return ""
    try:
        shelf_top = maya_shelf_utils.shelf_top_level()
    except Exception:
        return ""
    child_names = cmds.shelfTabLayout(shelf_top, query=True, childArray=True) or []
    for shelf_layout in child_names:
        buttons = cmds.shelfLayout(shelf_layout, query=True, childArray=True) or []
        for child in buttons:
            if not cmds.control(child, exists=True):
                continue
            try:
                current_doc_tag = cmds.shelfButton(child, query=True, docTag=True)
            except Exception:
                current_doc_tag = ""
            if current_doc_tag == doc_tag:
                return child
    return ""


def _resolve_target_widget(target):
    if not QtWidgets:
        return None
    target = target or {}
    target_type = target.get("type", "")
    if target_type == "shelf_button":
        control_name = target.get("control_name", "") or _shelf_button_target_by_doc_tag(target.get("doc_tag", ""))
        if control_name:
            widget = _find_qt_control(control_name)
            if widget:
                return widget
        label = target.get("label", "")
        widgets = _find_widgets_by_text(label)
        return widgets[0] if widgets else None
    if target_type == "control_name":
        control_name = target.get("control_name", "")
        widget = _find_qt_control(control_name)
        if widget:
            return widget
        object_name = target.get("object_name", "")
        if object_name:
            main_window = _maya_main_window()
            if main_window:
                widget = main_window.findChild(QtWidgets.QWidget, object_name)
                if widget:
                    return widget
        label = target.get("label", "")
        widgets = _find_widgets_by_text(label)
        return widgets[0] if widgets else None
    if target_type == "timeline_slider":
        return _find_qt_control(_playback_slider_name())
    label = target.get("label", "")
    widgets = _find_widgets_by_text(label)
    return widgets[0] if widgets else None


def _target_summary(target):
    target = target or {}
    target_type = target.get("type", "")
    label = target.get("label", "") or target.get("control_name", "") or target.get("object_name", "")
    if target_type == "menu_action":
        menu_title = target.get("menu_title", "")
        if menu_title:
            return "Menu: {0} > {1}".format(menu_title, label)
        return "Menu Action: {0}".format(label)
    if target_type == "shelf_button":
        return "Shelf Button: {0}".format(label or target.get("doc_tag", ""))
    if target_type == "timeline_slider":
        return "Timeline Slider"
    if target_type == "control_name":
        return "Control: {0}".format(label)
    if target_type == "widget":
        return "Widget: {0}".format(label)
    return "No target picked yet."


def _capture_target_for_widget(widget, menu_action=None):
    if not (QtWidgets and widget):
        return {}
    if isinstance(widget, QtWidgets.QMenu):
        action = menu_action or widget.activeAction()
        if action:
            return {
                "type": "menu_action",
                "label": _normalize_text(action.text()),
                "menu_title": _normalize_text(widget.title()),
                "object_name": action.objectName() or "",
            }
    label = ""
    for attribute in ("text", "windowTitle", "title", "placeholderText"):
        getter = getattr(widget, attribute, None)
        if callable(getter):
            try:
                label = _normalize_text(getter())
            except Exception:
                label = ""
            if label:
                break
    object_name = widget.objectName() or ""
    control_name = object_name
    doc_tag = ""
    target_type = "widget"
    if control_name and MAYA_AVAILABLE:
        try:
            if control_name == _playback_slider_name():
                target_type = "timeline_slider"
                label = label or "Timeline Slider"
            elif cmds.shelfButton(control_name, query=True, exists=True):
                target_type = "shelf_button"
                doc_tag = cmds.shelfButton(control_name, query=True, docTag=True) or ""
                if not label:
                    label = cmds.shelfButton(control_name, query=True, label=True) or ""
            elif cmds.control(control_name, exists=True):
                target_type = "control_name"
        except Exception:
            pass
    return {
        "type": target_type,
        "label": label,
        "object_name": object_name,
        "control_name": control_name,
        "doc_tag": doc_tag,
        "class_name": widget.metaObject().className() if hasattr(widget, "metaObject") else "",
    }


def _capture_target_under_cursor():
    if not (QtWidgets and QtGui):
        return {}
    cursor_pos = QtGui.QCursor.pos()
    widget = QtWidgets.QApplication.widgetAt(cursor_pos)
    if not widget:
        return {}
    if isinstance(widget, QtWidgets.QMenu):
        local_pos = widget.mapFromGlobal(cursor_pos)
        action = widget.actionAt(local_pos)
        return _capture_target_for_widget(widget, menu_action=action)
    return _capture_target_for_widget(widget)


def _serializable_scene_nodes():
    result = {}
    if not MAYA_AVAILABLE:
        return result
    node_names = cmds.ls(long=True, dependencyNodes=True) or []
    for node_name in node_names:
        if not cmds.objExists(node_name):
            continue
        resolved_name = _node_long_name(node_name)
        node_type = cmds.nodeType(resolved_name)
        node_uuid = _node_uuid(resolved_name)
        if not node_uuid:
            continue
        parent_uuid = ""
        parent_nodes = cmds.listRelatives(resolved_name, parent=True, fullPath=True) or []
        if parent_nodes:
            parent_uuid = _node_uuid(parent_nodes[0])
        result[node_uuid] = {
            "uuid": node_uuid,
            "name": resolved_name,
            "short_name": _short_name(resolved_name),
            "type": node_type,
            "parent_uuid": parent_uuid,
        }
    return result


def _transform_serialization(node_name):
    node_name = _node_long_name(node_name)
    payload = {
        "serializer": "transform",
        "node_type": cmds.nodeType(node_name),
        "uuid": _node_uuid(node_name),
        "name": node_name,
        "short_name": _short_name(node_name),
        "parent_uuid": "",
        "world_matrix": [],
        "attrs": {},
        "keyed_attrs": {},
        "locator_shape": {},
    }
    parents = cmds.listRelatives(node_name, parent=True, fullPath=True) or []
    if parents:
        payload["parent_uuid"] = _node_uuid(parents[0])
    try:
        payload["world_matrix"] = [float(value) for value in cmds.xform(node_name, query=True, worldSpace=True, matrix=True) or []]
    except Exception:
        payload["world_matrix"] = []
    for attr_name in ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ", "scaleX", "scaleY", "scaleZ", "visibility"):
        value = _get_attr_value(node_name, attr_name)
        if value is not None:
            payload["attrs"][attr_name] = value
        key_times = cmds.keyframe(node_name, attribute=attr_name, query=True, timeChange=True) or []
        key_values = cmds.keyframe(node_name, attribute=attr_name, query=True, valueChange=True) or []
        if key_times and len(key_times) == len(key_values):
            payload["keyed_attrs"][attr_name] = [
                {"time": float(key_times[index]), "value": float(key_values[index])}
                for index in range(len(key_times))
            ]
    locator_shapes = cmds.listRelatives(node_name, shapes=True, fullPath=True, type="locator") or []
    if locator_shapes:
        locator_shape = locator_shapes[0]
        payload["locator_shape"] = {
            "name": locator_shape,
            "local_scale": [
                float(cmds.getAttr(locator_shape + ".localScaleX")),
                float(cmds.getAttr(locator_shape + ".localScaleY")),
                float(cmds.getAttr(locator_shape + ".localScaleZ")),
            ],
        }
    return payload


def _constraint_targets(constraint_name):
    targets = cmds.parentConstraint(constraint_name, query=True, targetList=True) or []
    aliases = cmds.parentConstraint(constraint_name, query=True, weightAliasList=True) or []
    mapping = []
    for index, target_name in enumerate(targets):
        alias_name = aliases[index] if index < len(aliases) else ""
        mapping.append(
            {
                "name": _node_long_name(target_name),
                "uuid": _node_uuid(target_name),
                "alias": alias_name,
            }
        )
    return mapping


def _parent_constraint_driven(constraint_name):
    for plug_name in ("constraintTranslateX", "constraintRotateX"):
        connections = cmds.listConnections("{0}.{1}".format(constraint_name, plug_name), source=False, destination=True, plugs=False) or []
        for node_name in connections:
            if cmds.nodeType(node_name) == "transform":
                return _node_long_name(node_name)
    return ""


def _parent_constraint_serialization(node_name):
    node_name = _node_long_name(node_name)
    settable_attrs = cmds.listAttr(node_name, scalar=True, settable=True) or []
    attrs = {}
    keyed_attrs = {}
    for attr_name in settable_attrs:
        value = _get_attr_value(node_name, attr_name)
        if value is None:
            continue
        attrs[attr_name] = value
        key_times = cmds.keyframe(node_name, attribute=attr_name, query=True, timeChange=True) or []
        key_values = cmds.keyframe(node_name, attribute=attr_name, query=True, valueChange=True) or []
        if key_times and len(key_times) == len(key_values):
            keyed_attrs[attr_name] = [
                {"time": float(key_times[index]), "value": float(key_values[index])}
                for index in range(len(key_times))
            ]
    driven_name = _parent_constraint_driven(node_name)
    return {
        "serializer": "parentConstraint",
        "node_type": "parentConstraint",
        "uuid": _node_uuid(node_name),
        "name": node_name,
        "short_name": _short_name(node_name),
        "driven": {
            "name": driven_name,
            "uuid": _node_uuid(driven_name),
        },
        "targets": _constraint_targets(node_name),
        "attrs": attrs,
        "keyed_attrs": keyed_attrs,
    }


def _network_serialization(node_name):
    node_name = _node_long_name(node_name)
    attrs = {}
    for attr_name in cmds.listAttr(node_name, scalar=True, settable=True) or []:
        value = _get_attr_value(node_name, attr_name)
        if value is not None:
            attrs[attr_name] = value
    for attr_name in cmds.listAttr(node_name, string=True, settable=True) or []:
        value = _get_attr_value(node_name, attr_name)
        if value is not None:
            attrs[attr_name] = value
    return {
        "serializer": "network",
        "node_type": "network",
        "uuid": _node_uuid(node_name),
        "name": node_name,
        "short_name": _short_name(node_name),
        "attrs": attrs,
    }


def _serialize_supported_node(node_name):
    if not MAYA_AVAILABLE or not node_name or not cmds.objExists(node_name):
        return None
    node_name = _node_long_name(node_name)
    node_type = cmds.nodeType(node_name)
    if node_type == "parentConstraint":
        return _parent_constraint_serialization(node_name)
    if node_type == "network":
        return _network_serialization(node_name)
    if node_type == "transform":
        return _transform_serialization(node_name)
    return None


def _supported_snapshot():
    snapshot = {}
    for node_name in cmds.ls(long=True, dependencyNodes=True) or []:
        payload = _serialize_supported_node(node_name)
        if not payload:
            continue
        payload_uuid = payload.get("uuid", "")
        if payload_uuid:
            snapshot[payload_uuid] = payload
    return snapshot


def _supported_snapshot_for_nodes(node_names):
    snapshot = {}
    seen = set()
    candidates = []
    for node_name in node_names or []:
        resolved = _node_long_name(node_name)
        if not resolved or resolved in seen or not cmds.objExists(resolved):
            continue
        seen.add(resolved)
        candidates.append(resolved)
        if cmds.nodeType(resolved) == "transform":
            constraints = cmds.listConnections(resolved, source=True, destination=False, type="parentConstraint") or []
            for constraint_name in constraints:
                constraint_name = _node_long_name(constraint_name)
                if constraint_name and constraint_name not in seen and cmds.objExists(constraint_name):
                    seen.add(constraint_name)
                    candidates.append(constraint_name)
    for node_name in candidates:
        payload = _serialize_supported_node(node_name)
        if not payload:
            continue
        payload_uuid = payload.get("uuid", "")
        if payload_uuid:
            snapshot[payload_uuid] = payload
    return snapshot


def _recording_scene_snapshot(focused_nodes=None, include_full_supported=False):
    focus_nodes = list(focused_nodes or [])
    if not focus_nodes:
        focus_nodes = _safe_selected_nodes()
    snapshot = {
        "captured_at": _now_iso(),
        "general": _general_checkpoint(),
        "scene_index": _serializable_scene_nodes(),
    }
    if include_full_supported:
        snapshot["supported_snapshot"] = _supported_snapshot()
    else:
        snapshot["supported_snapshot"] = _supported_snapshot_for_nodes(focus_nodes)
    return snapshot


def _json_signature(value):
    try:
        return json.dumps(_copy_json(value), sort_keys=True, separators=(",", ":"))
    except Exception:
        return repr(value)


def _payloads_equal(left_payload, right_payload):
    return _json_signature(left_payload) == _json_signature(right_payload)


def _recording_target_summary(target):
    summary = _target_summary(target or {})
    if summary == "No target picked yet.":
        return ""
    return summary


def _is_recordable_target(target):
    target = target or {}
    target_type = target.get("type", "")
    if target_type in ("menu_action", "shelf_button", "timeline_slider"):
        return True
    if target_type == "control_name":
        return bool(target.get("label") or target.get("control_name"))
    if target_type == "widget":
        return bool(target.get("label"))
    return False


def _node_payload_title(payloads):
    payloads = payloads or []
    if not payloads:
        return "Node"
    return payloads[0].get("short_name") or payloads[0].get("name") or "Node"


def _payload_has_key_changes(pre_payload, post_payload):
    pre_payload = pre_payload or {}
    post_payload = post_payload or {}
    pre_keys = pre_payload.get("keyed_attrs") or {}
    post_keys = post_payload.get("keyed_attrs") or {}
    return _json_signature(pre_keys) != _json_signature(post_keys)


def _resolve_payload_node(payload):
    payload = payload or {}
    return _node_by_uuid(payload.get("uuid", ""), payload.get("name", ""))


def _delete_node_if_exists(payload):
    node_name = _resolve_payload_node(payload)
    if not node_name:
        return True
    try:
        cmds.delete(node_name)
        return True
    except Exception:
        return False


def _restore_transform_payload(payload):
    payload = payload or {}
    node_name = _resolve_payload_node(payload)
    if not node_name:
        parent_name = _node_by_uuid(payload.get("parent_uuid", ""), "")
        short_name = payload.get("short_name", "") or "tutorialNode"
        locator_shape = payload.get("locator_shape") or {}
        if locator_shape:
            node_name = cmds.spaceLocator(name=short_name)[0]
            if parent_name:
                node_name = cmds.parent(node_name, parent_name)[0]
        else:
            node_name = cmds.createNode("transform", name=short_name, parent=parent_name) if parent_name else cmds.createNode("transform", name=short_name)
    managed_attrs = set((payload.get("attrs") or {}).keys()) | set((payload.get("keyed_attrs") or {}).keys())
    for attr_name in managed_attrs:
        try:
            cmds.cutKey(node_name, attribute=attr_name, clear=True)
        except Exception:
            pass
    for attr_name, value in (payload.get("attrs") or {}).items():
        _set_attr_value(node_name, attr_name, value)
    for attr_name, keyframes in (payload.get("keyed_attrs") or {}).items():
        for keyframe in keyframes:
            try:
                cmds.setKeyframe(
                    node_name,
                    attribute=attr_name,
                    time=float(keyframe.get("time", 0.0)),
                    value=float(keyframe.get("value", 0.0)),
                )
            except Exception:
                pass
    matrix_values = payload.get("world_matrix") or []
    if len(matrix_values) == 16:
        try:
            cmds.xform(node_name, worldSpace=True, matrix=matrix_values)
        except Exception:
            pass
    locator_shape = payload.get("locator_shape") or {}
    local_scale = locator_shape.get("local_scale") or []
    if local_scale:
        shapes = cmds.listRelatives(node_name, shapes=True, fullPath=True, type="locator") or []
        if shapes:
            try:
                cmds.setAttr(shapes[0] + ".localScaleX", float(local_scale[0]))
                cmds.setAttr(shapes[0] + ".localScaleY", float(local_scale[1]))
                cmds.setAttr(shapes[0] + ".localScaleZ", float(local_scale[2]))
            except Exception:
                pass
    return True


def _restore_network_payload(payload):
    payload = payload or {}
    node_name = _resolve_payload_node(payload)
    if not node_name:
        node_name = cmds.createNode("network", name=payload.get("short_name", "") or "tutorialNetwork")
    for attr_name, value in (payload.get("attrs") or {}).items():
        if isinstance(value, str):
            _set_string_attr(node_name, attr_name, value)
        else:
            _set_attr_value(node_name, attr_name, value)
    return True


def _restore_parent_constraint_payload(payload):
    payload = payload or {}
    constraint_name = _resolve_payload_node(payload)
    if not constraint_name:
        driven_node = _node_by_uuid((payload.get("driven") or {}).get("uuid", ""), (payload.get("driven") or {}).get("name", ""))
        target_nodes = []
        for target in payload.get("targets") or []:
            resolved = _node_by_uuid(target.get("uuid", ""), target.get("name", ""))
            if resolved:
                target_nodes.append(resolved)
        if not driven_node or not target_nodes:
            return False
        try:
            constraint_name = cmds.parentConstraint(target_nodes, driven_node, maintainOffset=False, name=payload.get("short_name", "") or "tutorialParentConstraint")[0]
        except Exception:
            return False
    managed_attrs = set((payload.get("attrs") or {}).keys()) | set((payload.get("keyed_attrs") or {}).keys())
    for attr_name in managed_attrs:
        try:
            cmds.cutKey(constraint_name, attribute=attr_name, clear=True)
        except Exception:
            pass
    for attr_name, value in (payload.get("attrs") or {}).items():
        _set_attr_value(constraint_name, attr_name, value)
    for attr_name, keyframes in (payload.get("keyed_attrs") or {}).items():
        for keyframe in keyframes:
            try:
                cmds.setKeyframe(
                    constraint_name,
                    attribute=attr_name,
                    time=float(keyframe.get("time", 0.0)),
                    value=float(keyframe.get("value", 0.0)),
                )
            except Exception:
                pass
    return True


def _restore_payload(payload):
    serializer = (payload or {}).get("serializer", "")
    if serializer == "transform":
        return _restore_transform_payload(payload)
    if serializer == "network":
        return _restore_network_payload(payload)
    if serializer == "parentConstraint":
        return _restore_parent_constraint_payload(payload)
    return False


def _filter_created_payloads(created_ids, scene_index):
    payloads = []
    seen = set()
    for node_uuid in created_ids:
        node_info = scene_index.get(node_uuid) or {}
        node_name = node_info.get("name", "")
        payload = _serialize_supported_node(node_name)
        if not payload:
            continue
        payload_uuid = payload.get("uuid", "")
        if payload_uuid in seen:
            continue
        seen.add(payload_uuid)
        payloads.append(payload)
    return payloads


def _validate_payload_state(expected_payloads):
    expected_payloads = expected_payloads or []
    for payload in expected_payloads:
        node_name = _resolve_payload_node(payload)
        if not node_name:
            return False
        current_payload = _serialize_supported_node(node_name)
        if not _payloads_equal(current_payload, payload):
            return False
    return True


class _BaseStepHandler(object):
    step_type = "manual"
    label = "Manual Step"

    def validate(self, step):
        return True, "This is a manual instruction step."

    def restore(self, step, side):
        _restore_general_checkpoint((step.get("checkpoint_{0}".format(side), {}) or {}).get("general") or {})
        return True, "Restored the {0} checkpoint.".format(side)


class _FrameChangeStepHandler(_BaseStepHandler):
    step_type = "frame_change"
    label = "Frame Change"

    def validate(self, step):
        expected = int(round(float((step.get("validation") or {}).get("frame", 0))))
        current = _current_frame_int()
        if current == expected:
            return True, "You are on frame {0}.".format(current)
        return False, "This step expects frame {0}, but the scene is on frame {1}.".format(expected, current)


class _SelectionStepHandler(_BaseStepHandler):
    step_type = "selection_change"
    label = "Selection Change"

    def validate(self, step):
        expected = []
        for entry in (step.get("validation") or {}).get("selection", []):
            expected.append(_node_by_uuid(entry.get("uuid", ""), entry.get("name", "")))
        current = _safe_selected_nodes()
        if expected == current:
            return True, "The picked objects match this step."
        return False, "This step expects a different selection."


class _UICalloutStepHandler(_BaseStepHandler):
    step_type = "ui_callout"
    label = "UI Callout"

    def validate(self, step):
        target = step.get("target") or {}
        if not target:
            return True, "This callout step has no bound target."
        if target.get("type") == "menu_action":
            if _find_menu_action_rect(target.get("label", "")):
                return True, "The menu target can be highlighted."
            return False, "The menu target could not be found in the current Maya layout."
        if _resolve_target_widget(target):
            return True, "The UI target can be highlighted."
        return False, "The UI target could not be resolved right now."


class _AttributeChangeStepHandler(_BaseStepHandler):
    step_type = "attribute_change"
    label = "Attribute Change"

    def validate(self, step):
        validation = step.get("validation") or {}
        node_name = _node_by_uuid(validation.get("node_uuid", ""), validation.get("node_name", ""))
        attr_name = validation.get("attr_name", "")
        if not node_name or not attr_name:
            return False, "This attribute step is missing its node or attribute."
        current_value = _get_attr_value(node_name, attr_name)
        if _values_close(current_value, validation.get("expected_value")):
            return True, "The attribute matches the recorded value."
        return False, "The attribute does not match the recorded value yet."

    def restore(self, step, side):
        checkpoint = step.get("checkpoint_{0}".format(side), {}) or {}
        state = checkpoint.get("state") or {}
        node_name = _node_by_uuid(state.get("node_uuid", ""), state.get("node_name", ""))
        attr_name = state.get("attr_name", "")
        if node_name and attr_name:
            _set_attr_value(node_name, attr_name, state.get("value"))
        return super(_AttributeChangeStepHandler, self).restore(step, side)


class _AutoKeyToggleStepHandler(_BaseStepHandler):
    step_type = "auto_key_toggle"
    label = "Auto Key Toggle"

    def validate(self, step):
        expected = bool((step.get("validation") or {}).get("enabled"))
        current = _auto_key_enabled()
        if current == expected:
            return True, "Auto Key matches the recorded state."
        return False, "Auto Key does not match the recorded state yet."


class _StateChangeStepHandler(_BaseStepHandler):
    step_type = "state_change"
    label = "State Change"

    def validate(self, step):
        expected_nodes = (step.get("validation") or {}).get("nodes", [])
        if _validate_payload_state(expected_nodes):
            return True, "The recorded node state matches this step."
        return False, "The node values do not match the recorded step yet."

    def restore(self, step, side):
        checkpoint = step.get("checkpoint_{0}".format(side), {}) or {}
        state = checkpoint.get("state") or {}
        for payload in state.get("nodes", []):
            _restore_payload(payload)
        return super(_StateChangeStepHandler, self).restore(step, side)


class _KeyframeChangeStepHandler(_StateChangeStepHandler):
    step_type = "keyframe_change"
    label = "Keyframe Change"

    def validate(self, step):
        success, message = super(_KeyframeChangeStepHandler, self).validate(step)
        if success:
            return True, "The recorded keys match this step."
        return False, "The keys for this step do not match yet."


class _NodeCreateStepHandler(_BaseStepHandler):
    step_type = "node_create"
    label = "Node Creation"

    def validate(self, step):
        for payload in (step.get("validation") or {}).get("nodes", []):
            if not _resolve_payload_node(payload):
                return False, "A created node for this step is missing."
        return True, "The created nodes are in the scene."

    def restore(self, step, side):
        checkpoint = step.get("checkpoint_{0}".format(side), {}) or {}
        state = checkpoint.get("state") or {}
        target_nodes = state.get("nodes", [])
        if side == "pre":
            for payload in reversed(target_nodes):
                _delete_node_if_exists(payload)
        else:
            for payload in target_nodes:
                _restore_payload(payload)
        return super(_NodeCreateStepHandler, self).restore(step, side)


class _NodeDeleteStepHandler(_BaseStepHandler):
    step_type = "node_delete"
    label = "Node Deletion"

    def validate(self, step):
        for payload in (step.get("validation") or {}).get("nodes", []):
            if _resolve_payload_node(payload):
                return False, "A deleted node from this step is still present."
        return True, "The deleted nodes are gone."

    def restore(self, step, side):
        checkpoint = step.get("checkpoint_{0}".format(side), {}) or {}
        state = checkpoint.get("state") or {}
        target_nodes = state.get("nodes", [])
        if side == "pre":
            for payload in target_nodes:
                _restore_payload(payload)
        else:
            for payload in reversed(target_nodes):
                _delete_node_if_exists(payload)
        return super(_NodeDeleteStepHandler, self).restore(step, side)


class _ConstraintCreateStepHandler(_NodeCreateStepHandler):
    step_type = "constraint_create"
    label = "Constraint Creation"

    def validate(self, step):
        for payload in (step.get("validation") or {}).get("nodes", []):
            node_name = _resolve_payload_node(payload)
            if not node_name or cmds.nodeType(node_name) != "parentConstraint":
                return False, "The recorded parent constraint is not present."
        return True, "The parent constraint is present."


STEP_HANDLER_REGISTRY = {
    "manual": _BaseStepHandler(),
    "frame_change": _FrameChangeStepHandler(),
    "selection_change": _SelectionStepHandler(),
    "ui_callout": _UICalloutStepHandler(),
    "attribute_change": _AttributeChangeStepHandler(),
    "auto_key_toggle": _AutoKeyToggleStepHandler(),
    "state_change": _StateChangeStepHandler(),
    "keyframe_change": _KeyframeChangeStepHandler(),
    "node_create": _NodeCreateStepHandler(),
    "node_delete": _NodeDeleteStepHandler(),
    "constraint_create": _ConstraintCreateStepHandler(),
}


def _handler_for_step(step):
    step_type = (step or {}).get("kind", "manual")
    return STEP_HANDLER_REGISTRY.get(step_type, STEP_HANDLER_REGISTRY["manual"])


def _build_recorded_step_from_snapshots(baseline, current, title, student_text, author_note, target=None):
    baseline = baseline or {}
    current = current or {}
    baseline_general = baseline.get("general") or _general_checkpoint()
    current_general = current.get("general") or _general_checkpoint()
    baseline_scene_index = baseline.get("scene_index") or {}
    current_scene_index = current.get("scene_index") or {}
    baseline_supported = baseline.get("supported_snapshot") or {}
    current_supported = current.get("supported_snapshot") or {}
    target_payload = copy.deepcopy(target or {})
    target_summary = _recording_target_summary(target_payload)

    created_ids = sorted(set(current_scene_index.keys()) - set(baseline_scene_index.keys()))
    deleted_ids = sorted(set(baseline_scene_index.keys()) - set(current_scene_index.keys()))
    changed_ids = []
    for node_uuid in sorted(set(current_supported.keys()) & set(baseline_supported.keys())):
        if not _payloads_equal(baseline_supported.get(node_uuid), current_supported.get(node_uuid)):
            changed_ids.append(node_uuid)

    created_payloads = _filter_created_payloads(created_ids, current_scene_index)
    deleted_payloads = []
    for node_uuid in deleted_ids:
        payload = baseline_supported.get(node_uuid)
        if payload:
            deleted_payloads.append(payload)
    changed_pre_payloads = [copy.deepcopy(baseline_supported.get(node_uuid)) for node_uuid in changed_ids if baseline_supported.get(node_uuid)]
    changed_post_payloads = [copy.deepcopy(current_supported.get(node_uuid)) for node_uuid in changed_ids if current_supported.get(node_uuid)]

    created_at = _now_iso()
    start_time = int(round(float(baseline_general.get("current_time", 0.0))))
    end_time = int(round(float(current_general.get("current_time", 0.0))))
    baseline_selection = baseline_general.get("selection") or []
    current_selection = current_general.get("selection") or []
    baseline_auto_key = bool(baseline_general.get("auto_key"))
    current_auto_key = bool(current_general.get("auto_key"))

    if created_payloads and all(payload.get("node_type") == "parentConstraint" for payload in created_payloads):
        return {
            "id": _stable_id("step"),
            "title": title or "Create Parent Constraint",
            "student_text": student_text or "Create the parent constraint for this step.",
            "author_note": author_note or "",
            "kind": "constraint_create",
            "target": target_payload,
            "validation": {"type": "constraint_exists", "nodes": _copy_json(created_payloads)},
            "checkpoint_pre": {"general": baseline_general, "state": {"nodes": _copy_json(created_payloads)}},
            "checkpoint_post": {"general": current_general, "state": {"nodes": _copy_json(created_payloads)}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if created_payloads:
        return {
            "id": _stable_id("step"),
            "title": title or "Create Nodes",
            "student_text": student_text or "Create the node or helper for this step.",
            "author_note": author_note or "",
            "kind": "node_create",
            "target": target_payload,
            "validation": {"type": "node_exists", "nodes": _copy_json(created_payloads)},
            "checkpoint_pre": {"general": baseline_general, "state": {"nodes": _copy_json(created_payloads)}},
            "checkpoint_post": {"general": current_general, "state": {"nodes": _copy_json(created_payloads)}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if deleted_payloads:
        return {
            "id": _stable_id("step"),
            "title": title or "Delete Nodes",
            "student_text": student_text or "Delete the node or helper for this step.",
            "author_note": author_note or "",
            "kind": "node_delete",
            "target": target_payload,
            "validation": {"type": "node_missing", "nodes": _copy_json(deleted_payloads)},
            "checkpoint_pre": {"general": baseline_general, "state": {"nodes": _copy_json(deleted_payloads)}},
            "checkpoint_post": {"general": current_general, "state": {"nodes": _copy_json(deleted_payloads)}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if baseline_auto_key != current_auto_key:
        state_label = "On" if current_auto_key else "Off"
        return {
            "id": _stable_id("step"),
            "title": title or "Turn Auto Key {0}".format(state_label),
            "student_text": student_text or "Turn Auto Key {0}.".format(state_label.lower()),
            "author_note": author_note or "",
            "kind": "auto_key_toggle",
            "target": target_payload,
            "validation": {"type": "auto_key_state", "enabled": current_auto_key},
            "checkpoint_pre": {"general": baseline_general, "state": {"auto_key": baseline_auto_key}},
            "checkpoint_post": {"general": current_general, "state": {"auto_key": current_auto_key}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if changed_pre_payloads and changed_post_payloads:
        has_key_change = False
        for index in range(min(len(changed_pre_payloads), len(changed_post_payloads))):
            if _payload_has_key_changes(changed_pre_payloads[index], changed_post_payloads[index]):
                has_key_change = True
                break
        if has_key_change:
            default_title = "Set Keyframe"
            default_student_text = "Set the keyframe for this step."
            kind = "keyframe_change"
        else:
            node_title = _node_payload_title(changed_post_payloads)
            default_title = "Change {0}".format(node_title)
            default_student_text = "Change the values for {0}.".format(node_title)
            kind = "state_change"
        return {
            "id": _stable_id("step"),
            "title": title or default_title,
            "student_text": student_text or default_student_text,
            "author_note": author_note or "",
            "kind": kind,
            "target": target_payload,
            "validation": {"type": "state_equals", "nodes": _copy_json(changed_post_payloads)},
            "checkpoint_pre": {"general": baseline_general, "state": {"nodes": _copy_json(changed_pre_payloads)}},
            "checkpoint_post": {"general": current_general, "state": {"nodes": _copy_json(changed_post_payloads)}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if start_time != end_time:
        return {
            "id": _stable_id("step"),
            "title": title or "Go To Frame {0}".format(end_time),
            "student_text": student_text or "Go to frame {0}.".format(end_time),
            "author_note": author_note or "",
            "kind": "frame_change",
            "target": target_payload,
            "validation": {"type": "frame_equals", "frame": end_time},
            "checkpoint_pre": {"general": baseline_general, "state": {"frame": start_time}},
            "checkpoint_post": {"general": current_general, "state": {"frame": end_time}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if baseline_selection != current_selection:
        return {
            "id": _stable_id("step"),
            "title": title or "Pick The Right Objects",
            "student_text": student_text or "Pick the same objects shown in this step.",
            "author_note": author_note or "",
            "kind": "selection_change",
            "target": target_payload,
            "validation": {"type": "selection_equals", "selection": _copy_json(current_selection)},
            "checkpoint_pre": {"general": baseline_general, "state": {"selection": _copy_json(baseline_selection)}},
            "checkpoint_post": {"general": current_general, "state": {"selection": _copy_json(current_selection)}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    if target_payload:
        click_title = "Click {0}".format(target_summary or "This Control")
        click_text = "Click {0}.".format(target_summary.lower() if target_summary else "this control")
        return {
            "id": _stable_id("step"),
            "title": title or click_title,
            "student_text": student_text or click_text,
            "author_note": author_note or "",
            "kind": "ui_callout",
            "target": target_payload,
            "validation": {"type": "ui_callout", "target": copy.deepcopy(target_payload)},
            "checkpoint_pre": {"general": baseline_general, "state": {}},
            "checkpoint_post": {"general": current_general, "state": {}},
            "supported": True,
            "created_at": created_at,
            "updated_at": created_at,
        }

    return None


def _manual_step(title, student_text, author_note, target=None):
    return {
        "id": _stable_id("step"),
        "title": title or "Manual Step",
        "student_text": student_text or "Read the note, then do this step by hand.",
        "author_note": author_note or "",
        "kind": "manual",
        "target": target or {},
        "validation": {"type": "manual"},
        "checkpoint_pre": {"general": _general_checkpoint(), "state": {}},
        "checkpoint_post": {"general": _general_checkpoint(), "state": {}},
        "supported": False,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }


def _empty_lesson(title="New Lesson"):
    lesson_id = _stable_id("lesson")
    return {
        "id": lesson_id,
        "title": title or "New Lesson",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "steps": [],
    }


class MayaTutorialAuthoringController(object):
    def __init__(self):
        self.status_callback = None
        self.recording_state = None
        self.attribute_recording_state = None
        self.pose_compare_state = None

    def set_status_callback(self, callback):
        self.status_callback = callback

    def _set_status(self, message, success=True):
        if self.status_callback:
            self.status_callback(message, success)
        if success:
            _debug(message)
        else:
            _warning(message)

    def manifest(self):
        return _load_manifest()

    def lessons(self):
        return copy.deepcopy(self.manifest().get("lessons") or [])

    def lesson(self, lesson_id):
        for lesson in self.lessons():
            if lesson.get("id") == lesson_id:
                return lesson
        return None

    def pose_compare_manifest(self):
        return _load_pose_compare_manifest()

    def pose_compare_snapshots(self):
        snapshots = self.pose_compare_manifest().get("snapshots") or []
        return sorted(copy.deepcopy(snapshots), key=lambda item: (float(item.get("frame", 0.0)), item.get("label", ""), item.get("id", "")))

    def create_lesson(self, title="New Lesson"):
        manifest = self.manifest()
        lesson = _empty_lesson(title=title)
        manifest["lessons"].append(lesson)
        _save_manifest(manifest)
        self._set_status("Created lesson '{0}'.".format(lesson["title"]))
        return lesson

    def update_lesson(self, lesson_payload):
        manifest = self.manifest()
        lessons = manifest.get("lessons") or []
        updated = False
        for index, lesson in enumerate(lessons):
            if lesson.get("id") != lesson_payload.get("id"):
                continue
            payload = copy.deepcopy(lesson_payload)
            payload["updated_at"] = _now_iso()
            lessons[index] = payload
            updated = True
            break
        if not updated:
            payload = copy.deepcopy(lesson_payload)
            payload["created_at"] = payload.get("created_at") or _now_iso()
            payload["updated_at"] = _now_iso()
            lessons.append(payload)
        manifest["lessons"] = lessons
        _save_manifest(manifest)
        self._set_status("Saved lesson '{0}'.".format((lesson_payload or {}).get("title", "Lesson")))
        return copy.deepcopy(lesson_payload)

    def delete_lesson(self, lesson_id):
        manifest = self.manifest()
        lessons = manifest.get("lessons") or []
        manifest["lessons"] = [lesson for lesson in lessons if lesson.get("id") != lesson_id]
        _save_manifest(manifest)
        self._set_status("Deleted the lesson.", success=True)
        return True

    def move_step(self, lesson_id, step_id, direction):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first."
        steps = lesson.get("steps") or []
        current_index = -1
        for index, step in enumerate(steps):
            if step.get("id") == step_id:
                current_index = index
                break
        if current_index < 0:
            return False, "Pick a step first."
        swap_index = current_index + int(direction)
        if swap_index < 0 or swap_index >= len(steps):
            return False, "That step cannot move any further."
        steps[current_index], steps[swap_index] = steps[swap_index], steps[current_index]
        lesson["steps"] = steps
        self.update_lesson(lesson)
        return True, "Moved the step."

    def delete_step(self, lesson_id, step_id):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first."
        lesson["steps"] = [step for step in (lesson.get("steps") or []) if step.get("id") != step_id]
        self.update_lesson(lesson)
        return True, "Deleted the step."

    def update_step_text(self, lesson_id, step_id, title, student_text, author_note):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first."
        for step in lesson.get("steps") or []:
            if step.get("id") != step_id:
                continue
            step["title"] = title or step.get("title") or "Step"
            step["student_text"] = student_text or ""
            step["author_note"] = author_note or ""
            step["updated_at"] = _now_iso()
            self.update_lesson(lesson)
            return True, "Updated the step text."
        return False, "Pick a step first."

    def add_manual_step(self, lesson_id, title, student_text, author_note, target=None):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first.", None
        step = _manual_step(title, student_text, author_note, target=target)
        lesson.setdefault("steps", []).append(step)
        self.update_lesson(lesson)
        return True, "Added a manual step.", step

    def add_ui_callout_step(self, lesson_id, title, student_text, author_note, target):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first.", None
        step = _manual_step(title, student_text, author_note, target=target)
        step["kind"] = "ui_callout"
        step["supported"] = True
        step["validation"] = {
            "type": "ui_callout",
            "target": copy.deepcopy(target or {}),
        }
        lesson.setdefault("steps", []).append(step)
        self.update_lesson(lesson)
        return True, "Added a UI callout step.", step

    def begin_recording_step(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        self.recording_state = {
            "started_at": _now_iso(),
            "snapshot": _recording_scene_snapshot(include_full_supported=True),
        }
        self._set_status("Started step recording. Do the Maya action, then click Finish Recorded Step.")
        return True, "Started step recording."

    def cancel_recording_step(self):
        self.recording_state = None
        self._set_status("Cancelled the current recording.")
        return True, "Cancelled the current recording."

    def finish_recorded_step(self, lesson_id, title, student_text, author_note, target=None):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first.", None
        if not self.recording_state:
            return False, "Start recording first.", None

        baseline = self.recording_state
        current_snapshot = _recording_scene_snapshot(include_full_supported=True)
        step = _build_recorded_step_from_snapshots(
            baseline.get("snapshot") or {},
            current_snapshot,
            title,
            student_text,
            author_note,
            target=target,
        )
        if not step:
            step = _manual_step(title or "Manual Step", student_text, author_note, target=target)

        lesson.setdefault("steps", []).append(step)
        self.update_lesson(lesson)
        self.recording_state = None
        return True, "Captured a {0} step.".format(_handler_for_step(step).label.lower()), step

    def record_snapshot_step(self, lesson_id, baseline_snapshot, current_snapshot, title="", student_text="", author_note="", target=None):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first.", None
        step = _build_recorded_step_from_snapshots(
            baseline_snapshot,
            current_snapshot,
            title,
            student_text,
            author_note,
            target=target,
        )
        if not step:
            return False, "No supported Maya change was detected for a new step.", None
        lesson.setdefault("steps", []).append(step)
        self.update_lesson(lesson)
        return True, "Recorded {0}.".format(_handler_for_step(step).label.lower()), step

    def begin_attribute_recording(self, node_name, attr_name):
        node_name = _node_long_name(node_name)
        if not node_name or not cmds.objExists(node_name):
            return False, "Pick a valid node first."
        if not attr_name:
            return False, "Type the attribute name first."
        value = _get_attr_value(node_name, attr_name)
        if value is None:
            return False, "Could not read that attribute from the picked node."
        self.attribute_recording_state = {
            "general": _general_checkpoint(),
            "node_uuid": _node_uuid(node_name),
            "node_name": node_name,
            "attr_name": attr_name,
            "pre_value": _copy_json(value),
        }
        self._set_status("Captured the attribute's starting value. Change it in Maya, then click Finish Attribute Step.")
        return True, "Captured the attribute's starting value."

    def finish_attribute_recording(self, lesson_id, title, student_text, author_note, target=None):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first.", None
        state = self.attribute_recording_state
        if not state:
            return False, "Start the attribute capture first.", None
        node_name = _node_by_uuid(state.get("node_uuid", ""), state.get("node_name", ""))
        attr_name = state.get("attr_name", "")
        post_value = _get_attr_value(node_name, attr_name) if node_name and attr_name else None
        if post_value is None:
            return False, "Could not read the attribute's new value.", None
        step = {
            "id": _stable_id("step"),
            "title": title or "Change {0}".format(attr_name),
            "student_text": student_text or "Change {0} on {1}.".format(attr_name, _short_name(node_name)),
            "author_note": author_note or "",
            "kind": "attribute_change",
            "target": target or {},
            "validation": {
                "type": "attribute_equals",
                "node_uuid": state.get("node_uuid", ""),
                "node_name": state.get("node_name", ""),
                "attr_name": attr_name,
                "expected_value": _copy_json(post_value),
            },
            "checkpoint_pre": {
                "general": state.get("general"),
                "state": {
                    "node_uuid": state.get("node_uuid", ""),
                    "node_name": state.get("node_name", ""),
                    "attr_name": attr_name,
                    "value": _copy_json(state.get("pre_value")),
                },
            },
            "checkpoint_post": {
                "general": _general_checkpoint(),
                "state": {
                    "node_uuid": state.get("node_uuid", ""),
                    "node_name": state.get("node_name", ""),
                    "attr_name": attr_name,
                    "value": _copy_json(post_value),
                },
            },
            "supported": True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        lesson.setdefault("steps", []).append(step)
        self.update_lesson(lesson)
        self.attribute_recording_state = None
        return True, "Captured the attribute step.", step

    def create_pose_compare_snapshot(self, root_nodes, label_text, frame_value=None, offset_distance=POSE_COMPARE_DEFAULT_OFFSET, style_key=POSE_COMPARE_AFTER):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya.", None
        resolved_roots = _resolve_root_payload_entries(_selected_roots_payload(root_nodes))
        if not resolved_roots:
            return False, "Pick one or more roots first.", None
        frame_value = float(frame_value if frame_value is not None else _current_time_float())
        success, message, snapshot_data = _create_pose_compare_snapshot_nodes(
            resolved_roots,
            frame_value,
            label_text,
            style_key,
            offset_distance,
        )
        if not success:
            return False, message, None
        manifest = self.pose_compare_manifest()
        snapshot_entry = {
            "id": _stable_id("poseCompare"),
            "label": label_text or "Pose Fix",
            "frame": float(frame_value),
            "style": style_key,
            "source_roots": _selected_roots_payload(resolved_roots),
            "group_uuid": snapshot_data.get("group_uuid", ""),
            "group_name": snapshot_data.get("group_name", ""),
            "ghost_roots": snapshot_data.get("duplicated_roots", []),
            "offset": snapshot_data.get("offset", [0.0, 0.0, 0.0]),
            "visibility": snapshot_data.get("visibility", {}),
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        manifest.setdefault("snapshots", []).append(snapshot_entry)
        _save_pose_compare_manifest(manifest)
        self._set_status("Saved a pose compare snapshot on frame {0}.".format(int(round(float(frame_value)))))
        return True, "Created the pose compare snapshot.", snapshot_entry

    def begin_pose_compare_capture(self, root_nodes, label_text, frame_value=None, offset_distance=POSE_COMPARE_DEFAULT_OFFSET, style_key=POSE_COMPARE_AFTER):
        resolved_roots = _resolve_root_payload_entries(_selected_roots_payload(root_nodes))
        if not resolved_roots:
            return False, "Pick the rig or geometry roots you want to compare."
        frame_value = float(frame_value if frame_value is not None else _current_time_float())
        self.pose_compare_state = {
            "roots": _selected_roots_payload(resolved_roots),
            "label": label_text or "Pose Fix",
            "frame": float(frame_value),
            "offset_distance": float(offset_distance or POSE_COMPARE_DEFAULT_OFFSET),
            "style": style_key or POSE_COMPARE_AFTER,
            "restore_state": _capture_pose_restore_state(resolved_roots, frame_value),
        }
        self._set_status(
            "Captured the starting pose. Repose the rig, then click Finish Corrected Snapshot.",
            success=True,
        )
        return True, "Captured the starting pose."

    def finish_pose_compare_capture(self, label_text=None, frame_value=None, offset_distance=None, style_key=None):
        state = self.pose_compare_state
        if not state:
            return False, "Start the corrected-pose capture first.", None
        roots = _resolve_root_payload_entries(state.get("roots") or [])
        if not roots:
            return False, "The saved pose roots could not be found anymore.", None
        frame_value = float(frame_value if frame_value is not None else state.get("frame", _current_time_float()))
        label_text = label_text or state.get("label") or "Pose Fix"
        offset_distance = float(offset_distance if offset_distance is not None else state.get("offset_distance", POSE_COMPARE_DEFAULT_OFFSET))
        style_key = style_key or state.get("style") or POSE_COMPARE_AFTER
        success, message, snapshot_entry = self.create_pose_compare_snapshot(
            roots,
            label_text,
            frame_value=frame_value,
            offset_distance=offset_distance,
            style_key=style_key,
        )
        _restore_pose_restore_state(state.get("restore_state") or {})
        self.pose_compare_state = None
        if not success:
            return False, message, None
        self._set_status(
            "Created the corrected pose snapshot and restored the live rig pose.",
            success=True,
        )
        return True, "Created the corrected pose snapshot and restored the live rig.", snapshot_entry

    def cancel_pose_compare_capture(self):
        self.pose_compare_state = None
        self._set_status("Cancelled the corrected-pose capture.")
        return True, "Cancelled the corrected-pose capture."

    def delete_pose_compare_snapshot(self, snapshot_id):
        manifest = self.pose_compare_manifest()
        snapshots = manifest.get("snapshots") or []
        kept = []
        deleted = False
        for snapshot in snapshots:
            if snapshot.get("id") != snapshot_id:
                kept.append(snapshot)
                continue
            deleted = True
            _delete_pose_snapshot_group(snapshot.get("group_name", ""))
        manifest["snapshots"] = kept
        _save_pose_compare_manifest(manifest)
        if deleted:
            self._set_status("Deleted the pose compare snapshot.")
            return True, "Deleted the pose compare snapshot."
        return False, "Pick a pose compare snapshot first."

    def delete_pose_compare_frame(self, frame_value):
        manifest = self.pose_compare_manifest()
        snapshots = manifest.get("snapshots") or []
        kept = []
        deleted_count = 0
        target_frame = int(round(float(frame_value)))
        for snapshot in snapshots:
            snapshot_frame = int(round(float(snapshot.get("frame", 0.0))))
            if snapshot_frame != target_frame:
                kept.append(snapshot)
                continue
            deleted_count += 1
            _delete_pose_snapshot_group(snapshot.get("group_name", ""))
        manifest["snapshots"] = kept
        _save_pose_compare_manifest(manifest)
        if deleted_count:
            self._set_status("Deleted {0} pose compare snapshot(s) on frame {1}.".format(deleted_count, target_frame))
            return True, "Deleted the pose compare snapshots on this frame."
        return False, "There were no pose compare snapshots on that frame."

    def clear_pose_compare_snapshots(self):
        manifest = self.pose_compare_manifest()
        for snapshot in manifest.get("snapshots") or []:
            _delete_pose_snapshot_group(snapshot.get("group_name", ""))
        manifest["snapshots"] = []
        _save_pose_compare_manifest(manifest)
        self._set_status("Cleared all pose compare snapshots.")
        return True, "Cleared all pose compare snapshots."

    def lesson_start_checkpoint(self, lesson):
        steps = (lesson or {}).get("steps") or []
        if not steps:
            return {"general": _general_checkpoint(), "state": {}}
        return copy.deepcopy((steps[0].get("checkpoint_pre") or {}))

    def reset_lesson(self, lesson_id):
        lesson = self.lesson(lesson_id)
        if not lesson:
            return False, "Pick a lesson first."
        checkpoint = self.lesson_start_checkpoint(lesson)
        _restore_general_checkpoint(checkpoint.get("general") or {})
        return True, "Reset the lesson to the first step."

    def restore_step(self, step, side):
        try:
            cmds.undoInfo(openChunk=True, chunkName="MayaTutorialPlayback")
        except Exception:
            pass
        try:
            success, message = _handler_for_step(step).restore(step, side)
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        return success, message

    def validate_step(self, step):
        return _handler_for_step(step).validate(step)


class _HighlightOverlay(QtWidgets.QWidget if QtWidgets else object):
    def __init__(self):
        if not QtWidgets:
            return
        super(_HighlightOverlay, self).__init__(None)
        flags = _qt_flag("WindowType", "ToolTip", QtCore.Qt.ToolTip) | _qt_flag("WindowType", "FramelessWindowHint", QtCore.Qt.FramelessWindowHint)
        self.setWindowFlags(flags)
        self.setAttribute(_qt_flag("WidgetAttribute", "WA_TransparentForMouseEvents", QtCore.Qt.WA_TransparentForMouseEvents), True)
        self.setAttribute(_qt_flag("WidgetAttribute", "WA_ShowWithoutActivating", QtCore.Qt.WA_ShowWithoutActivating), True)
        self.setStyleSheet("background: rgba(255, 196, 57, 36); border: 3px solid #FFC439; border-radius: 8px;")
        self.message_label = QtWidgets.QLabel(None)
        self.message_label.setWindowFlags(flags)
        self.message_label.setAttribute(_qt_flag("WidgetAttribute", "WA_TransparentForMouseEvents", QtCore.Qt.WA_TransparentForMouseEvents), True)
        self.message_label.setAttribute(_qt_flag("WidgetAttribute", "WA_ShowWithoutActivating", QtCore.Qt.WA_ShowWithoutActivating), True)
        self.message_label.setStyleSheet(
            "QLabel { background-color: #111111; color: white; border: 1px solid #FFC439; border-radius: 6px; padding: 6px 10px; }"
        )
        self.timer = QtCore.QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.clear)

    def highlight_rect(self, rect, message):
        if not QtWidgets or rect is None or rect.isNull():
            return False
        grown = rect.adjusted(-4, -4, 4, 4)
        self.setGeometry(grown)
        self.show()
        self.raise_()
        if message:
            self.message_label.setText(message)
            self.message_label.adjustSize()
            message_pos = QtCore.QPoint(rect.left(), rect.bottom() + 8)
            self.message_label.move(message_pos)
            self.message_label.show()
            self.message_label.raise_()
        self.timer.start(HIGHLIGHT_DURATION_MS)
        return True

    def clear(self):
        if not QtWidgets:
            return
        self.hide()
        self.message_label.hide()


class _AutoStepRecorder(QtCore.QObject if QtCore else object):
    def __init__(self, controller, lesson_id, owner_window=None):
        if not QtCore:
            return
        super(_AutoStepRecorder, self).__init__(owner_window)
        self.controller = controller
        self.lesson_id = lesson_id
        self.owner_window = owner_window
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(AUTO_RECORD_POLL_MS)
        self.timer.timeout.connect(self.poll_once)
        self.active = False
        self.baseline_snapshot = None
        self.pending_snapshot = None
        self.pending_signature = ""
        self.pending_started_ms = 0
        self.recent_target = {}
        self.recent_target_ms = 0
        self.step_count = 0

    def start(self):
        if not QtWidgets:
            return False, "Qt is not available."
        self.baseline_snapshot = _recording_scene_snapshot()
        self.pending_snapshot = None
        self.pending_signature = ""
        self.pending_started_ms = 0
        self.recent_target = {}
        self.recent_target_ms = 0
        self.step_count = 0
        self.active = True
        app = QtWidgets.QApplication.instance()
        if app:
            app.installEventFilter(self)
        self.timer.start()
        return True, "Recorder is watching Maya actions."

    def stop(self, commit_pending=True):
        if not QtWidgets:
            return False, "Qt is not available."
        if commit_pending:
            self.poll_once(force=True)
        self.active = False
        self.timer.stop()
        app = QtWidgets.QApplication.instance()
        if app:
            try:
                app.removeEventFilter(self)
            except Exception:
                pass
        return True, "Stopped the automatic recorder."

    def cancel(self):
        self.pending_snapshot = None
        self.pending_signature = ""
        self.pending_started_ms = 0
        self.recent_target = {}
        self.recent_target_ms = 0
        return self.stop(commit_pending=False)

    def note_target(self, target):
        target = copy.deepcopy(target or {})
        if not target:
            return
        self.recent_target = target
        self.recent_target_ms = int(time.time() * 1000.0)

    def _current_target(self):
        if not self.recent_target:
            return {}
        age = int(time.time() * 1000.0) - int(self.recent_target_ms or 0)
        if age > AUTO_RECORD_TARGET_TTL_MS:
            return {}
        return copy.deepcopy(self.recent_target)

    def _clear_target(self):
        self.recent_target = {}
        self.recent_target_ms = 0

    def _is_owner_widget(self, widget):
        owner = self.owner_window
        current = widget
        while current is not None:
            if current is owner:
                return True
            current = current.parentWidget() if hasattr(current, "parentWidget") else None
        return False

    def _capture_target_from_event(self, watched, event):
        if not QtWidgets:
            return {}
        if isinstance(watched, QtWidgets.QMenu):
            action = None
            try:
                action = watched.actionAt(event.pos()) or watched.activeAction()
            except Exception:
                action = watched.activeAction()
            target = _capture_target_for_widget(watched, menu_action=action)
            if _is_recordable_target(target):
                return target
            return {}
        if isinstance(watched, QtWidgets.QWidget):
            target = _capture_target_for_widget(watched)
            if _is_recordable_target(target):
                return target
            return {}
        return {}

    def eventFilter(self, watched, event):
        if not self.active or not QtCore:
            return False
        try:
            event_type = event.type()
        except Exception:
            return False
        mouse_release = _qt_flag("QEvent", "MouseButtonRelease", QtCore.QEvent.MouseButtonRelease)
        mouse_double = _qt_flag("QEvent", "MouseButtonDblClick", QtCore.QEvent.MouseButtonDblClick)
        if event_type not in (mouse_release, mouse_double):
            return False
        if isinstance(watched, QtWidgets.QWidget) and self._is_owner_widget(watched):
            return False
        target = self._capture_target_from_event(watched, event)
        if target:
            self.note_target(target)
        return False

    def _snapshot_signature(self, snapshot):
        signature_payload = {
            "general": (snapshot or {}).get("general") or {},
            "scene_index": (snapshot or {}).get("scene_index") or {},
            "supported_snapshot": (snapshot or {}).get("supported_snapshot") or {},
        }
        return _json_signature(signature_payload)

    def _emit_step(self, snapshot, force=False):
        if not self.baseline_snapshot:
            self.baseline_snapshot = snapshot
            return False
        success, message, step = self.controller.record_snapshot_step(
            self.lesson_id,
            self.baseline_snapshot,
            snapshot,
            target=self._current_target(),
        )
        if not success and force and self._current_target():
            success, message, step = self.controller.record_snapshot_step(
                self.lesson_id,
                self.baseline_snapshot,
                snapshot,
                title="",
                student_text="",
                author_note="",
                target=self._current_target(),
            )
        if success and step:
            self.step_count += 1
            self.baseline_snapshot = snapshot
            self.pending_snapshot = None
            self.pending_signature = ""
            self.pending_started_ms = 0
            self._clear_target()
            if self.owner_window and hasattr(self.owner_window, "_handle_auto_recorded_step"):
                self.owner_window._handle_auto_recorded_step(step, message)
            return True
        return False

    def poll_once(self, force=False):
        if not self.active and not force:
            return False
        snapshot = _recording_scene_snapshot()
        if not self.baseline_snapshot:
            self.baseline_snapshot = snapshot
            return False
        if self._snapshot_signature(snapshot) == self._snapshot_signature(self.baseline_snapshot):
            current_target = self._current_target()
            target_age = int(time.time() * 1000.0) - int(self.recent_target_ms or 0)
            if current_target and (force or target_age >= AUTO_RECORD_DEBOUNCE_MS):
                emitted = self._emit_step(snapshot, force=True)
                if emitted:
                    return True
            if force and self._current_target():
                emitted = self._emit_step(snapshot, force=True)
                if emitted:
                    return True
            self.pending_snapshot = None
            self.pending_signature = ""
            self.pending_started_ms = 0
            return False
        signature = self._snapshot_signature(snapshot)
        now_ms = int(time.time() * 1000.0)
        if force:
            self.pending_snapshot = snapshot
            self.pending_signature = signature
            self.pending_started_ms = now_ms
            return self._emit_step(snapshot, force=True)
        if signature != self.pending_signature:
            self.pending_snapshot = snapshot
            self.pending_signature = signature
            self.pending_started_ms = now_ms
            return False
        if (now_ms - int(self.pending_started_ms or now_ms)) < AUTO_RECORD_DEBOUNCE_MS:
            return False
        return self._emit_step(snapshot)


if QtWidgets:
    try:
        from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

        _WindowBase = type("MayaTutorialAuthoringBase", (MayaQWidgetDockableMixin, QtWidgets.QDialog), {})
    except Exception:
        _WindowBase = type("MayaTutorialAuthoringBase", (QtWidgets.QDialog,), {})


if QtWidgets:
    class MayaTutorialAuthoringWindow(_WindowBase):
        def __init__(self, controller, parent=None, mode=PLAYBACK_MODE_AUTHOR, lesson_id=None):
            super(MayaTutorialAuthoringWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller
            self.controller.set_status_callback(self._set_status)
            self.setObjectName(WINDOW_OBJECT_NAME)
            self.setWindowTitle("Maya Tutorial Authoring")
            self.setMinimumSize(860, 640)
            self.resize(1220, 900)
            if hasattr(self, "setSizePolicy"):
                self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self.current_target = {}
            self.current_lesson_id = lesson_id or ""
            self.pose_compare_roots = []
            self.player_step_index = 0
            self.guided_step_index = 0
            self._syncing_ui = False
            self.target_pick_timer = None
            self.auto_recorder = None
            self.highlight_overlay = _HighlightOverlay()
            self._build_ui()
            self._refresh_lessons()
            self._set_mode(mode)

        def closeEvent(self, event):
            try:
                if self.target_pick_timer:
                    self.target_pick_timer.stop()
            except Exception:
                pass
            try:
                if self.auto_recorder:
                    self.auto_recorder.cancel()
            except Exception:
                pass
            try:
                self.highlight_overlay.clear()
            except Exception:
                pass
            super(MayaTutorialAuthoringWindow, self).closeEvent(event)

        def _make_scroll_page(self, widget):
            if hasattr(widget, "setSizePolicy"):
                widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            scroll = QtWidgets.QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(_qt_flag("ScrollBarPolicy", "ScrollBarAsNeeded", QtCore.Qt.ScrollBarAsNeeded))
            scroll.setVerticalScrollBarPolicy(_qt_flag("ScrollBarPolicy", "ScrollBarAsNeeded", QtCore.Qt.ScrollBarAsNeeded))
            scroll.setWidget(widget)
            if hasattr(scroll, "setSizePolicy"):
                scroll.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            return scroll

        def _make_mode_tab(self):
            page = QtWidgets.QWidget()
            if hasattr(page, "setSizePolicy"):
                page.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
            return page, self._make_scroll_page(page)

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(10, 10, 10, 10)
            main_layout.setSpacing(8)

            header = QtWidgets.QGridLayout()
            header.setHorizontalSpacing(10)
            header.setVerticalSpacing(8)
            self.mode_combo = QtWidgets.QComboBox()
            self.mode_combo.addItem("Author", PLAYBACK_MODE_AUTHOR)
            self.mode_combo.addItem("Practice", PLAYBACK_MODE_GUIDED)
            self.mode_combo.addItem("Watch", PLAYBACK_MODE_PLAYER)
            self.mode_combo.addItem("Compare", PLAYBACK_MODE_POSE_COMPARE)
            self.lesson_combo = QtWidgets.QComboBox()
            self.new_lesson_button = QtWidgets.QPushButton("New")
            self.save_lesson_button = QtWidgets.QPushButton("Save")
            self.more_actions_button = QtWidgets.QToolButton()
            self.more_actions_button.setText("More")
            self.more_actions_button.setPopupMode(QtWidgets.QToolButton.InstantPopup)
            self.more_actions_menu = QtWidgets.QMenu(self.more_actions_button)
            self.delete_lesson_action = self.more_actions_menu.addAction("Delete Lesson")
            self.more_actions_menu.addSeparator()
            self.dock_right_action = self.more_actions_menu.addAction("Dock Right")
            self.float_window_action = self.more_actions_menu.addAction("Float Window")
            self.more_actions_button.setMenu(self.more_actions_menu)
            self.lesson_title_line = QtWidgets.QLineEdit()
            self.lesson_title_line.setPlaceholderText("Lesson title")
            header.addWidget(QtWidgets.QLabel("Mode"), 0, 0)
            header.addWidget(self.mode_combo, 0, 1)
            header.addWidget(QtWidgets.QLabel("Lesson"), 0, 2)
            header.addWidget(self.lesson_combo, 0, 3, 1, 4)
            header.addWidget(self.new_lesson_button, 0, 7)
            header.addWidget(self.more_actions_button, 0, 8)
            header.addWidget(QtWidgets.QLabel("Title"), 1, 0)
            header.addWidget(self.lesson_title_line, 1, 1, 1, 7)
            header.addWidget(self.save_lesson_button, 1, 8)
            main_layout.addLayout(header)

            self.mode_stack = QtWidgets.QStackedWidget()
            main_layout.addWidget(self.mode_stack, 1)

            self.author_root, self.author_scroll = self._make_mode_tab()
            self.guided_root, self.guided_scroll = self._make_mode_tab()
            self.player_root, self.player_scroll = self._make_mode_tab()
            self.pose_compare_root, self.pose_compare_scroll = self._make_mode_tab()
            self.mode_stack.addWidget(self.author_scroll)
            self.mode_stack.addWidget(self.guided_scroll)
            self.mode_stack.addWidget(self.player_scroll)
            self.mode_stack.addWidget(self.pose_compare_scroll)

            self._build_author_mode()
            self._build_guided_mode()
            self._build_player_mode()
            self._build_pose_compare_mode()

            self.status_label = QtWidgets.QLabel("Ready.")
            self.status_label.setWordWrap(True)
            main_layout.addWidget(self.status_label)

            footer_layout = QtWidgets.QHBoxLayout()
            self.brand_label = QtWidgets.QLabel('Built by Amir. Follow Amir at <a href="{0}">followamir.com</a>.'.format(FOLLOW_AMIR_URL))
            self.brand_label.setOpenExternalLinks(False)
            self.brand_label.linkActivated.connect(self._open_follow_url)
            self.brand_label.setWordWrap(True)
            footer_layout.addWidget(self.brand_label, 1)
            self.donate_button = QtWidgets.QPushButton("Donate")
            self.donate_button.setToolTip("Uses AMIR_PAYPAL_DONATE_URL, then AMIR_DONATE_URL, then the shared PayPal fallback.")
            _style_donate_button(self.donate_button)
            self.donate_button.clicked.connect(self._open_donate_url)
            footer_layout.addWidget(self.donate_button)
            main_layout.addLayout(footer_layout)

            self.mode_combo.currentIndexChanged.connect(self._handle_mode_change)
            self.lesson_combo.currentIndexChanged.connect(self._handle_lesson_change)
            self.new_lesson_button.clicked.connect(self._new_lesson)
            self.save_lesson_button.clicked.connect(self._save_current_lesson_header)
            self.delete_lesson_action.triggered.connect(self._delete_current_lesson)
            self.dock_right_action.triggered.connect(self._dock_window_right)
            self.float_window_action.triggered.connect(self._float_window)

        def _build_author_mode(self):
            layout = QtWidgets.QHBoxLayout(self.author_root)
            layout.setContentsMargins(0, 0, 0, 0)
            splitter = QtWidgets.QSplitter()
            splitter.setChildrenCollapsible(False)
            layout.addWidget(splitter, 1)

            left_panel = QtWidgets.QWidget()
            if hasattr(left_panel, "setSizePolicy"):
                left_panel.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)
            left_panel.setMinimumWidth(170)
            left_panel.setMaximumWidth(220)
            left_layout = QtWidgets.QVBoxLayout(left_panel)
            left_layout.addWidget(QtWidgets.QLabel("Steps"))
            self.author_steps_list = QtWidgets.QListWidget()
            self.author_steps_list.setAlternatingRowColors(True)
            left_layout.addWidget(self.author_steps_list, 1)
            reorder_row = QtWidgets.QHBoxLayout()
            self.step_up_button = QtWidgets.QPushButton("Up")
            self.step_down_button = QtWidgets.QPushButton("Down")
            self.delete_step_button = QtWidgets.QPushButton("Delete")
            reorder_row.addWidget(self.step_up_button)
            reorder_row.addWidget(self.step_down_button)
            reorder_row.addWidget(self.delete_step_button)
            left_layout.addLayout(reorder_row)
            splitter.addWidget(left_panel)

            right_panel = QtWidgets.QWidget()
            if hasattr(right_panel, "setSizePolicy"):
                right_panel.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            right_layout = QtWidgets.QVBoxLayout(right_panel)
            self.author_tools_tabs = QtWidgets.QTabWidget()
            self.author_tools_tabs.setUsesScrollButtons(True)
            right_layout.addWidget(self.author_tools_tabs, 1)

            capture_page = QtWidgets.QWidget()
            capture_page_layout = QtWidgets.QVBoxLayout(capture_page)
            capture_group = QtWidgets.QGroupBox("Step")
            capture_layout = QtWidgets.QVBoxLayout(capture_group)
            self.capture_title_line = QtWidgets.QLineEdit()
            self.capture_title_line.setPlaceholderText("What is this step called?")
            self.capture_student_text = QtWidgets.QPlainTextEdit()
            self.capture_student_text.setPlaceholderText("Explain the step in simple words.")
            self.capture_student_text.setMaximumHeight(110)
            self.capture_author_note = QtWidgets.QPlainTextEdit()
            self.capture_author_note.setPlaceholderText("Teacher note (optional).")
            self.capture_author_note.setMaximumHeight(72)
            capture_form = QtWidgets.QGridLayout()
            capture_form.addWidget(QtWidgets.QLabel("Title"), 0, 0)
            capture_form.addWidget(self.capture_title_line, 0, 1)
            capture_form.addWidget(QtWidgets.QLabel("Student"), 1, 0)
            capture_form.addWidget(self.capture_student_text, 1, 1)
            capture_form.addWidget(QtWidgets.QLabel("Teacher"), 2, 0)
            capture_form.addWidget(self.capture_author_note, 2, 1)
            capture_layout.addLayout(capture_form)

            recorder_row = QtWidgets.QGridLayout()
            self.start_auto_record_button = QtWidgets.QPushButton("Auto Record")
            self.stop_auto_record_button = QtWidgets.QPushButton("Stop Recorder")
            recorder_row.addWidget(self.start_auto_record_button, 0, 0)
            recorder_row.addWidget(self.stop_auto_record_button, 0, 1)
            capture_layout.addLayout(recorder_row)
            self.recording_summary_label = QtWidgets.QLabel("Recorder: idle.")
            self.recording_summary_label.setWordWrap(True)
            capture_layout.addWidget(self.recording_summary_label)

            record_row = QtWidgets.QGridLayout()
            self.start_record_button = QtWidgets.QPushButton("Start Capture")
            self.finish_record_button = QtWidgets.QPushButton("Finish Step")
            self.cancel_record_button = QtWidgets.QPushButton("Cancel")
            self.add_manual_step_button = QtWidgets.QPushButton("Manual Note")
            record_row.addWidget(self.start_record_button, 0, 0)
            record_row.addWidget(self.finish_record_button, 0, 1)
            record_row.addWidget(self.cancel_record_button, 1, 0)
            record_row.addWidget(self.add_manual_step_button, 1, 1)
            capture_layout.addLayout(record_row)
            capture_hint = QtWidgets.QLabel(
                "Auto Record turns supported Maya actions into steps as you work. Use Start Capture when you want to bracket one manual before-and-after step instead."
            )
            capture_hint.setWordWrap(True)
            capture_layout.addWidget(capture_hint)
            capture_page_layout.addWidget(capture_group)
            capture_page_layout.addStretch(1)

            advanced_page = QtWidgets.QWidget()
            advanced_page_layout = QtWidgets.QVBoxLayout(advanced_page)
            target_group = QtWidgets.QGroupBox("Target")
            target_layout = QtWidgets.QVBoxLayout(target_group)
            self.target_summary_label = QtWidgets.QLabel("No target picked yet.")
            self.target_summary_label.setWordWrap(True)
            target_layout.addWidget(self.target_summary_label)
            target_button_row = QtWidgets.QGridLayout()
            self.pick_target_button = QtWidgets.QPushButton("Pick Under Mouse")
            self.use_timeline_target_button = QtWidgets.QPushButton("Use Timeline")
            self.add_ui_callout_button = QtWidgets.QPushButton("Save Callout")
            self.clear_target_button = QtWidgets.QPushButton("Clear Target")
            target_button_row.addWidget(self.pick_target_button, 0, 0)
            target_button_row.addWidget(self.use_timeline_target_button, 0, 1)
            target_button_row.addWidget(self.add_ui_callout_button, 1, 0)
            target_button_row.addWidget(self.clear_target_button, 1, 1)
            target_layout.addLayout(target_button_row)
            advanced_page_layout.addWidget(target_group)

            attr_group = QtWidgets.QGroupBox("Attribute")
            attr_layout = QtWidgets.QGridLayout(attr_group)
            self.attr_node_line = QtWidgets.QLineEdit()
            self.attr_node_line.setReadOnly(True)
            self.attr_attr_line = QtWidgets.QLineEdit()
            self.attr_attr_line.setPlaceholderText("translateX")
            self.use_selected_node_button = QtWidgets.QPushButton("Use Selected")
            self.begin_attr_capture_button = QtWidgets.QPushButton("Begin Capture")
            self.finish_attr_capture_button = QtWidgets.QPushButton("Finish Attribute")
            attr_layout.addWidget(QtWidgets.QLabel("Node"), 0, 0)
            attr_layout.addWidget(self.attr_node_line, 0, 1)
            attr_layout.addWidget(self.use_selected_node_button, 0, 2)
            attr_layout.addWidget(QtWidgets.QLabel("Attribute"), 1, 0)
            attr_layout.addWidget(self.attr_attr_line, 1, 1, 1, 2)
            attr_layout.addWidget(self.begin_attr_capture_button, 2, 1)
            attr_layout.addWidget(self.finish_attr_capture_button, 2, 2)
            advanced_page_layout.addWidget(attr_group)
            advanced_page_layout.addStretch(1)

            edit_page = QtWidgets.QWidget()
            edit_layout = QtWidgets.QVBoxLayout(edit_page)
            selected_group = QtWidgets.QGroupBox("Picked Step")
            selected_layout = QtWidgets.QGridLayout(selected_group)
            self.selected_step_title_line = QtWidgets.QLineEdit()
            self.selected_step_student_text = QtWidgets.QPlainTextEdit()
            self.selected_step_student_text.setMaximumHeight(170)
            self.selected_step_author_note = QtWidgets.QPlainTextEdit()
            self.selected_step_author_note.setMaximumHeight(140)
            self.selected_step_kind_label = QtWidgets.QLabel("No step picked yet.")
            self.selected_step_target_label = QtWidgets.QLabel("No target")
            self.selected_step_target_label.setWordWrap(True)
            self.apply_step_text_button = QtWidgets.QPushButton("Apply Step Text")
            self.preview_step_button = QtWidgets.QPushButton("Preview Step")
            self.validate_step_button = QtWidgets.QPushButton("Validate Step")
            selected_layout.addWidget(QtWidgets.QLabel("Type"), 0, 0)
            selected_layout.addWidget(self.selected_step_kind_label, 0, 1, 1, 2)
            selected_layout.addWidget(QtWidgets.QLabel("Target"), 1, 0)
            selected_layout.addWidget(self.selected_step_target_label, 1, 1, 1, 2)
            selected_layout.addWidget(QtWidgets.QLabel("Title"), 2, 0)
            selected_layout.addWidget(self.selected_step_title_line, 2, 1, 1, 2)
            selected_layout.addWidget(QtWidgets.QLabel("Student"), 3, 0)
            selected_layout.addWidget(self.selected_step_student_text, 3, 1, 1, 2)
            selected_layout.addWidget(QtWidgets.QLabel("Teacher"), 4, 0)
            selected_layout.addWidget(self.selected_step_author_note, 4, 1, 1, 2)
            selected_layout.addWidget(self.apply_step_text_button, 5, 0)
            selected_layout.addWidget(self.preview_step_button, 5, 1)
            selected_layout.addWidget(self.validate_step_button, 5, 2)
            edit_layout.addWidget(selected_group)
            edit_layout.addStretch(1)

            self.author_tools_tabs.addTab(self._make_scroll_page(capture_page), "Record")
            self.author_tools_tabs.addTab(self._make_scroll_page(advanced_page), "Advanced")
            self.author_tools_tabs.addTab(self._make_scroll_page(edit_page), "Edit")
            splitter.addWidget(right_panel)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            splitter.setSizes([190, 890])

            self.author_steps_list.itemSelectionChanged.connect(self._load_selected_author_step)
            self.step_up_button.clicked.connect(lambda: self._move_selected_step(-1))
            self.step_down_button.clicked.connect(lambda: self._move_selected_step(1))
            self.delete_step_button.clicked.connect(self._delete_selected_step)
            self.start_auto_record_button.clicked.connect(self._start_auto_recording)
            self.stop_auto_record_button.clicked.connect(self._stop_auto_recording)
            self.start_record_button.clicked.connect(self._begin_recording)
            self.finish_record_button.clicked.connect(self._finish_recording)
            self.cancel_record_button.clicked.connect(self._cancel_recording)
            self.add_manual_step_button.clicked.connect(self._add_manual_step)
            self.pick_target_button.clicked.connect(self._begin_target_pick)
            self.use_timeline_target_button.clicked.connect(self._use_timeline_target)
            self.clear_target_button.clicked.connect(self._clear_target)
            self.add_ui_callout_button.clicked.connect(self._add_ui_callout_step)
            self.use_selected_node_button.clicked.connect(self._use_selected_attr_node)
            self.begin_attr_capture_button.clicked.connect(self._begin_attribute_capture)
            self.finish_attr_capture_button.clicked.connect(self._finish_attribute_capture)
            self.apply_step_text_button.clicked.connect(self._apply_selected_step_text)
            self.preview_step_button.clicked.connect(self._preview_selected_step)
            self.validate_step_button.clicked.connect(self._validate_selected_step)

        def _build_guided_mode(self):
            layout = QtWidgets.QVBoxLayout(self.guided_root)
            layout.setContentsMargins(0, 0, 0, 0)
            splitter = QtWidgets.QSplitter()
            splitter.setChildrenCollapsible(False)
            layout.addWidget(splitter, 1)

            left_panel = QtWidgets.QWidget()
            left_panel.setMinimumWidth(170)
            left_panel.setMaximumWidth(220)
            left_layout = QtWidgets.QVBoxLayout(left_panel)
            left_layout.addWidget(QtWidgets.QLabel("Steps"))
            self.guided_steps_list = QtWidgets.QListWidget()
            self.guided_steps_list.setAlternatingRowColors(True)
            left_layout.addWidget(self.guided_steps_list, 1)
            splitter.addWidget(left_panel)

            right_panel = QtWidgets.QWidget()
            right_layout = QtWidgets.QVBoxLayout(right_panel)
            self.guided_step_header = QtWidgets.QLabel("No lesson picked yet.")
            self.guided_step_header.setStyleSheet("font-weight: 600; font-size: 15px;")
            self.guided_instruction_box = QtWidgets.QPlainTextEdit()
            self.guided_instruction_box.setReadOnly(True)
            self.guided_instruction_box.setMaximumHeight(170)
            self.guided_target_label = QtWidgets.QLabel("Target: None")
            self.guided_target_label.setWordWrap(True)
            self.guided_status_label = QtWidgets.QLabel("Status: Ready.")
            self.guided_status_label.setWordWrap(True)
            right_layout.addWidget(self.guided_step_header)
            right_layout.addWidget(self.guided_instruction_box)
            right_layout.addWidget(self.guided_target_label)
            right_layout.addWidget(self.guided_status_label)
            prep_row = QtWidgets.QGridLayout()
            self.guided_prepare_button = QtWidgets.QPushButton("Prepare")
            self.guided_show_me_button = QtWidgets.QPushButton("Show Me")
            self.guided_check_button = QtWidgets.QPushButton("Check")
            self.guided_do_it_button = QtWidgets.QPushButton("Do It")
            prep_row.addWidget(self.guided_prepare_button, 0, 0)
            prep_row.addWidget(self.guided_show_me_button, 0, 1)
            prep_row.addWidget(self.guided_check_button, 1, 0)
            prep_row.addWidget(self.guided_do_it_button, 1, 1)
            right_layout.addLayout(prep_row)

            nav_row = QtWidgets.QHBoxLayout()
            self.guided_back_button = QtWidgets.QPushButton("Back")
            self.guided_next_button = QtWidgets.QPushButton("Next")
            self.guided_reset_button = QtWidgets.QPushButton("Reset")
            nav_row.addStretch(1)
            nav_row.addWidget(self.guided_back_button)
            nav_row.addWidget(self.guided_next_button)
            nav_row.addWidget(self.guided_reset_button)
            right_layout.addLayout(nav_row)
            right_layout.addStretch(1)
            splitter.addWidget(right_panel)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            splitter.setSizes([190, 890])

            self.guided_steps_list.itemSelectionChanged.connect(self._load_selected_guided_step)
            self.guided_prepare_button.clicked.connect(self._guided_prepare_step)
            self.guided_show_me_button.clicked.connect(self._guided_show_me)
            self.guided_check_button.clicked.connect(self._guided_check_step)
            self.guided_do_it_button.clicked.connect(self._guided_do_it_for_me)
            self.guided_back_button.clicked.connect(self._guided_back)
            self.guided_next_button.clicked.connect(self._guided_next)
            self.guided_reset_button.clicked.connect(self._guided_reset)

        def _build_player_mode(self):
            layout = QtWidgets.QVBoxLayout(self.player_root)
            layout.setContentsMargins(0, 0, 0, 0)
            splitter = QtWidgets.QSplitter()
            splitter.setChildrenCollapsible(False)
            layout.addWidget(splitter, 1)

            left_panel = QtWidgets.QWidget()
            left_panel.setMinimumWidth(170)
            left_panel.setMaximumWidth(220)
            left_layout = QtWidgets.QVBoxLayout(left_panel)
            left_layout.addWidget(QtWidgets.QLabel("Steps"))
            self.player_steps_list = QtWidgets.QListWidget()
            self.player_steps_list.setAlternatingRowColors(True)
            left_layout.addWidget(self.player_steps_list, 1)
            splitter.addWidget(left_panel)

            right_panel = QtWidgets.QWidget()
            right_layout = QtWidgets.QVBoxLayout(right_panel)
            self.player_step_header = QtWidgets.QLabel("No lesson picked yet.")
            self.player_step_header.setStyleSheet("font-weight: 600; font-size: 15px;")
            self.player_instruction_box = QtWidgets.QPlainTextEdit()
            self.player_instruction_box.setReadOnly(True)
            self.player_instruction_box.setMaximumHeight(200)
            self.player_target_label = QtWidgets.QLabel("Target: None")
            self.player_target_label.setWordWrap(True)
            self.player_validation_label = QtWidgets.QLabel("Status: Ready.")
            self.player_validation_label.setWordWrap(True)
            button_row = QtWidgets.QHBoxLayout()
            self.player_show_me_button = QtWidgets.QPushButton("Show Me")
            self.player_check_button = QtWidgets.QPushButton("Check")
            self.player_back_button = QtWidgets.QPushButton("Back")
            self.player_next_button = QtWidgets.QPushButton("Next")
            self.player_reset_button = QtWidgets.QPushButton("Reset")
            button_row.addWidget(self.player_show_me_button)
            button_row.addWidget(self.player_check_button)
            button_row.addStretch(1)
            button_row.addWidget(self.player_back_button)
            button_row.addWidget(self.player_next_button)
            button_row.addWidget(self.player_reset_button)
            right_layout.addWidget(self.player_step_header)
            right_layout.addWidget(self.player_instruction_box, 1)
            right_layout.addWidget(self.player_target_label)
            right_layout.addWidget(self.player_validation_label)
            right_layout.addLayout(button_row)
            splitter.addWidget(right_panel)
            splitter.setStretchFactor(0, 1)
            splitter.setStretchFactor(1, 2)
            splitter.setSizes([190, 890])

            self.player_steps_list.itemSelectionChanged.connect(self._load_selected_player_step)
            self.player_show_me_button.clicked.connect(self._player_show_me)
            self.player_check_button.clicked.connect(self._player_check_step)
            self.player_back_button.clicked.connect(self._player_back)
            self.player_next_button.clicked.connect(self._player_next)
            self.player_reset_button.clicked.connect(self._player_reset)

        def _build_pose_compare_mode(self):
            layout = QtWidgets.QVBoxLayout(self.pose_compare_root)
            layout.setContentsMargins(0, 0, 0, 0)
            form_group = QtWidgets.QGroupBox("Pose Compare")
            form_layout = QtWidgets.QGridLayout(form_group)
            self.pose_compare_roots_line = QtWidgets.QLineEdit()
            self.pose_compare_roots_line.setReadOnly(True)
            self.pose_compare_roots_line.setPlaceholderText("Pick the rig or geometry roots you want to duplicate.")
            self.pose_compare_use_selected_button = QtWidgets.QPushButton("Use Selected")
            self.pose_compare_label_line = QtWidgets.QLineEdit()
            self.pose_compare_label_line.setPlaceholderText("Forearm fix")
            self.pose_compare_style_combo = QtWidgets.QComboBox()
            self.pose_compare_style_combo.addItem(POSE_COMPARE_STYLES[POSE_COMPARE_BEFORE]["label"], POSE_COMPARE_BEFORE)
            self.pose_compare_style_combo.addItem(POSE_COMPARE_STYLES[POSE_COMPARE_AFTER]["label"], POSE_COMPARE_AFTER)
            self.pose_compare_frame_spin = QtWidgets.QSpinBox()
            self.pose_compare_frame_spin.setRange(-100000, 100000)
            self.pose_compare_frame_spin.setValue(_current_frame_int())
            self.pose_compare_offset_spin = QtWidgets.QDoubleSpinBox()
            self.pose_compare_offset_spin.setRange(1.0, 100000.0)
            self.pose_compare_offset_spin.setDecimals(2)
            self.pose_compare_offset_spin.setSingleStep(1.0)
            self.pose_compare_offset_spin.setValue(POSE_COMPARE_DEFAULT_OFFSET)
            self.pose_compare_use_current_frame_button = QtWidgets.QPushButton("Use Current")
            form_layout.addWidget(QtWidgets.QLabel("Roots"), 0, 0)
            form_layout.addWidget(self.pose_compare_roots_line, 0, 1, 1, 3)
            form_layout.addWidget(self.pose_compare_use_selected_button, 0, 4)
            form_layout.addWidget(QtWidgets.QLabel("Label"), 1, 0)
            form_layout.addWidget(self.pose_compare_label_line, 1, 1, 1, 2)
            form_layout.addWidget(QtWidgets.QLabel("Ghost"), 1, 3)
            form_layout.addWidget(self.pose_compare_style_combo, 1, 4)
            form_layout.addWidget(QtWidgets.QLabel("Frame"), 2, 0)
            form_layout.addWidget(self.pose_compare_frame_spin, 2, 1)
            form_layout.addWidget(self.pose_compare_use_current_frame_button, 2, 2)
            form_layout.addWidget(QtWidgets.QLabel("Offset"), 2, 3)
            form_layout.addWidget(self.pose_compare_offset_spin, 2, 4)
            layout.addWidget(form_group)

            buttons_row = QtWidgets.QHBoxLayout()
            self.pose_compare_snapshot_button = QtWidgets.QPushButton("Snapshot")
            self.pose_compare_begin_button = QtWidgets.QPushButton("Start Capture")
            self.pose_compare_finish_button = QtWidgets.QPushButton("Finish Capture")
            self.pose_compare_cancel_button = QtWidgets.QPushButton("Cancel")
            buttons_row.addWidget(self.pose_compare_snapshot_button)
            buttons_row.addWidget(self.pose_compare_begin_button)
            buttons_row.addWidget(self.pose_compare_finish_button)
            buttons_row.addWidget(self.pose_compare_cancel_button)
            layout.addLayout(buttons_row)

            cleanup_row = QtWidgets.QHBoxLayout()
            self.pose_compare_delete_frame_button = QtWidgets.QPushButton("Delete Frame")
            self.pose_compare_delete_selected_button = QtWidgets.QPushButton("Delete Selected")
            self.pose_compare_clear_all_button = QtWidgets.QPushButton("Clear All")
            cleanup_row.addWidget(self.pose_compare_delete_frame_button)
            cleanup_row.addWidget(self.pose_compare_delete_selected_button)
            cleanup_row.addWidget(self.pose_compare_clear_all_button)
            layout.addLayout(cleanup_row)

            self.pose_compare_status_label = QtWidgets.QLabel("Status: Ready.")
            self.pose_compare_status_label.setWordWrap(True)
            layout.addWidget(self.pose_compare_status_label)

            self.pose_compare_list = QtWidgets.QListWidget()
            self.pose_compare_list.setAlternatingRowColors(True)
            layout.addWidget(self.pose_compare_list, 1)

            self.pose_compare_use_selected_button.clicked.connect(self._pose_compare_use_selected_roots)
            self.pose_compare_use_current_frame_button.clicked.connect(self._pose_compare_use_current_frame)
            self.pose_compare_snapshot_button.clicked.connect(self._pose_compare_create_snapshot)
            self.pose_compare_begin_button.clicked.connect(self._pose_compare_begin_capture)
            self.pose_compare_finish_button.clicked.connect(self._pose_compare_finish_capture)
            self.pose_compare_cancel_button.clicked.connect(self._pose_compare_cancel_capture)
            self.pose_compare_delete_frame_button.clicked.connect(self._pose_compare_delete_frame)
            self.pose_compare_delete_selected_button.clicked.connect(self._pose_compare_delete_selected)
            self.pose_compare_clear_all_button.clicked.connect(self._pose_compare_clear_all)

        def _handle_mode_change(self):
            self._set_mode(self.mode_combo.currentData())

        def _set_mode(self, mode):
            if mode == PLAYBACK_MODE_GUIDED:
                self.mode_stack.setCurrentIndex(1)
                self.mode_combo.setCurrentIndex(1)
                self._refresh_guided_steps()
            elif mode == PLAYBACK_MODE_PLAYER:
                self.mode_stack.setCurrentIndex(2)
                self.mode_combo.setCurrentIndex(2)
                self._refresh_player_steps()
            elif mode == PLAYBACK_MODE_POSE_COMPARE:
                self.mode_stack.setCurrentIndex(3)
                self.mode_combo.setCurrentIndex(3)
                self._refresh_pose_compare_list()
            else:
                self.mode_stack.setCurrentIndex(0)
                self.mode_combo.setCurrentIndex(0)

        def _refresh_lessons(self):
            lessons = self.controller.lessons()
            self.lesson_combo.blockSignals(True)
            self.lesson_combo.clear()
            for lesson in lessons:
                self.lesson_combo.addItem(lesson.get("title", "Lesson"), lesson.get("id"))
            self.lesson_combo.blockSignals(False)
            if lessons:
                target_id = self.current_lesson_id or lessons[0].get("id")
                index = self.lesson_combo.findData(target_id)
                if index < 0:
                    index = 0
                self.lesson_combo.setCurrentIndex(index)
                self._load_current_lesson()
            else:
                self.current_lesson_id = ""
                self.lesson_title_line.setText("")
                self.author_steps_list.clear()
                self.guided_steps_list.clear()
                self.player_steps_list.clear()
                self._load_selected_author_step()
                self._load_selected_guided_step()
                self._load_selected_player_step()
            self._refresh_pose_compare_list()

        def _handle_lesson_change(self):
            self.current_lesson_id = self.lesson_combo.currentData() or ""
            self._load_current_lesson()

        def _current_lesson(self):
            if not self.current_lesson_id:
                return None
            return self.controller.lesson(self.current_lesson_id)

        def _load_current_lesson(self):
            lesson = self._current_lesson()
            if not lesson:
                self.lesson_title_line.setText("")
                self.author_steps_list.clear()
                self.guided_steps_list.clear()
                self.player_steps_list.clear()
                self._load_selected_author_step()
                self._load_selected_guided_step()
                self._load_selected_player_step()
                return
            self.lesson_title_line.setText(lesson.get("title", ""))
            self._refresh_author_steps()
            self._refresh_guided_steps(reset_index=True)
            self._refresh_player_steps(reset_index=True)

        def _save_current_lesson_header(self):
            lesson = self._current_lesson()
            if not lesson:
                lesson = self.controller.create_lesson(self.lesson_title_line.text() or "New Lesson")
                self.current_lesson_id = lesson.get("id")
            lesson["title"] = self.lesson_title_line.text() or lesson.get("title") or "Lesson"
            self.controller.update_lesson(lesson)
            self._refresh_lessons()

        def _new_lesson(self):
            lesson = self.controller.create_lesson(self.lesson_title_line.text() or "New Lesson")
            self.current_lesson_id = lesson.get("id")
            self._refresh_lessons()

        def _delete_current_lesson(self):
            if not self.current_lesson_id:
                self._set_status("Pick a lesson first.", success=False)
                return
            self.controller.delete_lesson(self.current_lesson_id)
            self.current_lesson_id = ""
            self._refresh_lessons()

        def _refresh_author_steps(self):
            lesson = self._current_lesson()
            current_step_id = self._selected_author_step_id()
            self.author_steps_list.clear()
            if not lesson:
                return
            selected_row = 0
            for index, step in enumerate(lesson.get("steps") or []):
                label = "{0}. {1}".format(index + 1, step.get("title", "Step"))
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, step.get("id"))
                self.author_steps_list.addItem(item)
                if step.get("id") == current_step_id:
                    selected_row = index
            if self.author_steps_list.count():
                self.author_steps_list.setCurrentRow(min(selected_row, self.author_steps_list.count() - 1))

        def _refresh_guided_steps(self, reset_index=False):
            lesson = self._current_lesson()
            self.guided_steps_list.clear()
            if reset_index:
                self.guided_step_index = 0
            if not lesson:
                self._load_selected_guided_step()
                return
            for index, step in enumerate(lesson.get("steps") or []):
                item = QtWidgets.QListWidgetItem("{0}. {1}".format(index + 1, step.get("title", "Step")))
                item.setData(QtCore.Qt.UserRole, step.get("id"))
                self.guided_steps_list.addItem(item)
            if self.guided_steps_list.count():
                self.guided_steps_list.setCurrentRow(min(self.guided_step_index, self.guided_steps_list.count() - 1))
            else:
                self._load_selected_guided_step()

        def _refresh_player_steps(self, reset_index=False):
            lesson = self._current_lesson()
            self.player_steps_list.clear()
            if reset_index:
                self.player_step_index = 0
            if not lesson:
                self._load_selected_player_step()
                return
            for index, step in enumerate(lesson.get("steps") or []):
                item = QtWidgets.QListWidgetItem("{0}. {1}".format(index + 1, step.get("title", "Step")))
                item.setData(QtCore.Qt.UserRole, step.get("id"))
                self.player_steps_list.addItem(item)
            if self.player_steps_list.count():
                self.player_steps_list.setCurrentRow(min(self.player_step_index, self.player_steps_list.count() - 1))
            else:
                self._load_selected_player_step()

        def _selected_author_step_id(self):
            item = self.author_steps_list.currentItem()
            if not item:
                return ""
            return item.data(QtCore.Qt.UserRole) or ""

        def _selected_player_step_id(self):
            item = self.player_steps_list.currentItem()
            if not item:
                return ""
            return item.data(QtCore.Qt.UserRole) or ""

        def _selected_guided_step_id(self):
            item = self.guided_steps_list.currentItem()
            if not item:
                return ""
            return item.data(QtCore.Qt.UserRole) or ""

        def _step_by_id(self, lesson, step_id):
            for step in (lesson or {}).get("steps") or []:
                if step.get("id") == step_id:
                    return step
            return None

        def _selected_author_step(self):
            lesson = self._current_lesson()
            return self._step_by_id(lesson, self._selected_author_step_id())

        def _selected_guided_step(self):
            lesson = self._current_lesson()
            return self._step_by_id(lesson, self._selected_guided_step_id())

        def _selected_player_step(self):
            lesson = self._current_lesson()
            return self._step_by_id(lesson, self._selected_player_step_id())

        def _load_selected_author_step(self):
            step = self._selected_author_step()
            if not step:
                self.selected_step_kind_label.setText("No step picked yet.")
                self.selected_step_target_label.setText("No target")
                self.selected_step_title_line.setText("")
                self.selected_step_student_text.setPlainText("")
                self.selected_step_author_note.setPlainText("")
                return
            handler = _handler_for_step(step)
            self.selected_step_kind_label.setText("{0} ({1})".format(handler.label, step.get("kind", "")))
            self.selected_step_target_label.setText(_target_summary(step.get("target") or {}))
            self.selected_step_title_line.setText(step.get("title", ""))
            self.selected_step_student_text.setPlainText(step.get("student_text", ""))
            self.selected_step_author_note.setPlainText(step.get("author_note", ""))

        def _load_selected_guided_step(self):
            step = self._selected_guided_step()
            if not step:
                self.guided_step_header.setText("No lesson picked yet.")
                self.guided_instruction_box.setPlainText("")
                self.guided_target_label.setText("Target: None")
                self.guided_status_label.setText("Status: Ready to practise.")
                return
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            self.guided_step_index = max(0, self.guided_steps_list.currentRow())
            self.guided_step_header.setText("Practice Step {0} of {1}: {2}".format(self.guided_step_index + 1, len(steps), step.get("title", "Step")))
            self.guided_instruction_box.setPlainText(step.get("student_text", ""))
            self.guided_target_label.setText("Target: {0}".format(_target_summary(step.get("target") or {})))
            self.guided_status_label.setText("Status: Prepare the scene, then let the student try the step.")

        def _load_selected_player_step(self):
            step = self._selected_player_step()
            if not step:
                self.player_step_header.setText("No lesson picked yet.")
                self.player_instruction_box.setPlainText("")
                self.player_target_label.setText("Target: None")
                self.player_validation_label.setText("Status: Ready.")
                return
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            self.player_step_index = max(0, self.player_steps_list.currentRow())
            self.player_step_header.setText("Step {0} of {1}: {2}".format(self.player_step_index + 1, len(steps), step.get("title", "Step")))
            self.player_instruction_box.setPlainText(step.get("student_text", ""))
            self.player_target_label.setText("Target: {0}".format(_target_summary(step.get("target") or {})))
            self.player_validation_label.setText("Status: Ready to guide the step.")

        def _move_selected_step(self, direction):
            step_id = self._selected_author_step_id()
            if not step_id:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.move_step(self.current_lesson_id, step_id, direction)
            self._set_status(message, success)
            self._refresh_author_steps()
            self._refresh_guided_steps()
            self._refresh_player_steps()

        def _delete_selected_step(self):
            step_id = self._selected_author_step_id()
            if not step_id:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.delete_step(self.current_lesson_id, step_id)
            self._set_status(message, success)
            self._refresh_author_steps()
            self._refresh_guided_steps()
            self._refresh_player_steps()

        def _begin_recording(self):
            if self.auto_recorder:
                self._set_status("Stop the automatic recorder before starting a manual capture.", success=False)
                return
            success, message = self.controller.begin_recording_step()
            self._set_status(message, success)

        def _ensure_current_lesson(self):
            lesson = self._current_lesson()
            if lesson:
                return lesson
            title = self.lesson_title_line.text() or "New Lesson"
            lesson = self.controller.create_lesson(title)
            self.current_lesson_id = lesson.get("id", "")
            self._refresh_lessons()
            return lesson

        def _set_recording_summary(self, message):
            self.recording_summary_label.setText(message)

        def _start_auto_recording(self):
            lesson = self._ensure_current_lesson()
            if not lesson:
                self._set_status("Pick or create a lesson first.", success=False)
                return
            if self.auto_recorder:
                self._set_status("The automatic recorder is already running.", success=False)
                return
            self.auto_recorder = _AutoStepRecorder(self.controller, lesson.get("id"), owner_window=self)
            success, message = self.auto_recorder.start()
            if not success:
                self.auto_recorder = None
                self._set_status(message, success)
                return
            self._set_recording_summary("Recorder: running. Supported Maya actions will appear as steps automatically.")
            self._set_status(message, success)

        def _stop_auto_recording(self):
            if not self.auto_recorder:
                self._set_status("The automatic recorder is not running.", success=False)
                return
            success, message = self.auto_recorder.stop(commit_pending=True)
            count = int(getattr(self.auto_recorder, "step_count", 0))
            self.auto_recorder = None
            self._set_recording_summary("Recorder: idle. Captured {0} step{1}.".format(count, "" if count == 1 else "s"))
            self._set_status(message, success)

        def _handle_auto_recorded_step(self, step, message):
            self._refresh_author_steps()
            self._refresh_guided_steps()
            self._refresh_player_steps()
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            if steps:
                self.author_steps_list.setCurrentRow(len(steps) - 1)
            count = int(getattr(self.auto_recorder, "step_count", 0))
            self._set_recording_summary("Recorder: running. Captured {0} step{1}.".format(count, "" if count == 1 else "s"))
            self._set_status(message, True)

        def _finish_recording(self):
            if self.auto_recorder:
                self._set_status("Use Stop Recorder to finish the automatic recorder.", success=False)
                return
            success, message, step = self.controller.finish_recorded_step(
                self.current_lesson_id,
                self.capture_title_line.text(),
                self.capture_student_text.toPlainText(),
                self.capture_author_note.toPlainText(),
                target=copy.deepcopy(self.current_target),
            )
            self._set_status(message, success)
            if success and step:
                self.capture_title_line.clear()
                self.capture_student_text.setPlainText("")
                self.capture_author_note.setPlainText("")
                self._refresh_author_steps()
                self._refresh_guided_steps()
                self._refresh_player_steps()

        def _cancel_recording(self):
            if self.auto_recorder:
                success, message = self.auto_recorder.cancel()
                self.auto_recorder = None
                self._set_recording_summary("Recorder: idle. Cancelled the automatic recorder.")
                self._set_status(message, success)
                return
            success, message = self.controller.cancel_recording_step()
            self._set_status(message, success)

        def _add_manual_step(self):
            success, message, step = self.controller.add_manual_step(
                self.current_lesson_id,
                self.capture_title_line.text(),
                self.capture_student_text.toPlainText(),
                self.capture_author_note.toPlainText(),
                target=copy.deepcopy(self.current_target),
            )
            self._set_status(message, success)
            if success and step:
                self._refresh_author_steps()
                self._refresh_guided_steps()
                self._refresh_player_steps()

        def _add_ui_callout_step(self):
            success, message, step = self.controller.add_ui_callout_step(
                self.current_lesson_id,
                self.capture_title_line.text() or "Show A Maya Button",
                self.capture_student_text.toPlainText(),
                self.capture_author_note.toPlainText(),
                target=copy.deepcopy(self.current_target),
            )
            self._set_status(message, success)
            if success and step:
                self._refresh_author_steps()
                self._refresh_guided_steps()
                self._refresh_player_steps()

        def _use_selected_attr_node(self):
            selection = _safe_selected_nodes()
            if not selection:
                self._set_status("Pick one node first.", success=False)
                return
            self.attr_node_line.setText(selection[0])
            self._set_status("Using {0} for the attribute step.".format(_short_name(selection[0])))

        def _begin_attribute_capture(self):
            success, message = self.controller.begin_attribute_recording(self.attr_node_line.text(), self.attr_attr_line.text())
            self._set_status(message, success)

        def _finish_attribute_capture(self):
            success, message, step = self.controller.finish_attribute_recording(
                self.current_lesson_id,
                self.capture_title_line.text(),
                self.capture_student_text.toPlainText(),
                self.capture_author_note.toPlainText(),
                target=copy.deepcopy(self.current_target),
            )
            self._set_status(message, success)
            if success and step:
                self._refresh_author_steps()
                self._refresh_guided_steps()
                self._refresh_player_steps()

        def _apply_selected_step_text(self):
            step = self._selected_author_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.update_step_text(
                self.current_lesson_id,
                step.get("id"),
                self.selected_step_title_line.text(),
                self.selected_step_student_text.toPlainText(),
                self.selected_step_author_note.toPlainText(),
            )
            self._set_status(message, success)
            self._refresh_author_steps()
            self._refresh_guided_steps()
            self._refresh_player_steps()

        def _preview_selected_step(self):
            step = self._selected_author_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.restore_step(step, "post")
            self._set_status(message, success)
            self._highlight_step_target(step)

        def _validate_selected_step(self):
            step = self._selected_author_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.validate_step(step)
            self._set_status(message, success)

        def _begin_target_pick(self):
            if self.target_pick_timer:
                try:
                    self.target_pick_timer.stop()
                except Exception:
                    pass
            self.target_pick_timer = QtCore.QTimer(self)
            self.target_pick_timer.setSingleShot(True)
            self.target_pick_timer.timeout.connect(self._finish_target_pick)
            self.target_pick_timer.start(TARGET_PICK_DELAY_MS)
            self._set_status("Move the mouse over the Maya button or menu item you want, then wait a moment.")

        def _finish_target_pick(self):
            self.current_target = _capture_target_under_cursor()
            if not self.current_target:
                self._set_status("Could not capture a target under the mouse.", success=False)
                return
            self.target_summary_label.setText(_target_summary(self.current_target))
            self._set_status("Captured a highlight target.")

        def _use_timeline_target(self):
            slider_name = _playback_slider_name()
            self.current_target = {
                "type": "timeline_slider",
                "label": "Timeline Slider",
                "control_name": slider_name,
            }
            self.target_summary_label.setText(_target_summary(self.current_target))
            self._set_status("Using the Maya time slider as the highlight target.")

        def _clear_target(self):
            self.current_target = {}
            self.target_summary_label.setText("No target picked yet.")
            self._set_status("Cleared the current highlight target.")

        def _highlight_step_target(self, step):
            target = (step or {}).get("target") or {}
            if not target:
                return False, "This step does not have a saved target."
            if target.get("type") == "menu_action":
                rect = _find_menu_action_rect(target.get("label", ""))
                if rect and self.highlight_overlay.highlight_rect(rect, step.get("student_text", "") or _target_summary(target)):
                    return True, "Highlighted the menu target."
                return False, "Could not find that Maya menu in the current layout."
            widget = _resolve_target_widget(target)
            if not widget:
                return False, "Could not find that Maya control right now."
            global_top_left = widget.mapToGlobal(widget.rect().topLeft())
            rect = QtCore.QRect(global_top_left, widget.rect().size())
            if self.highlight_overlay.highlight_rect(rect, step.get("student_text", "") or _target_summary(target)):
                return True, "Highlighted the Maya control."
            return False, "Could not highlight that Maya control."

        def _player_show_me(self):
            step = self._selected_player_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self._highlight_step_target(step)
            if not success:
                message = "{0} {1}".format(message, step.get("student_text", "")).strip()
            self.player_validation_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _player_check_step(self):
            step = self._selected_player_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.validate_step(step)
            self.player_validation_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _player_reset(self):
            success, message = self.controller.reset_lesson(self.current_lesson_id)
            if success:
                self.player_step_index = 0
                self._refresh_player_steps(reset_index=True)
            self.player_validation_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _player_back(self):
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            if not steps:
                self._set_status("This lesson does not have any steps yet.", success=False)
                return
            row = self.player_steps_list.currentRow()
            target_row = max(0, row - 1)
            if row <= 0:
                success, message = self.controller.reset_lesson(self.current_lesson_id)
            else:
                prior_step = steps[target_row]
                success, message = self.controller.restore_step(prior_step, "pre")
            self.player_steps_list.setCurrentRow(target_row)
            self.player_validation_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _player_next(self):
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            step = self._selected_player_step()
            if not step or not steps:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.restore_step(step, "post")
            self._highlight_step_target(step)
            current_row = self.player_steps_list.currentRow()
            if current_row < len(steps) - 1:
                self.player_steps_list.setCurrentRow(current_row + 1)
            self.player_validation_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_prepare_step(self):
            step = self._selected_guided_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.restore_step(step, "pre")
            self.guided_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_show_me(self):
            step = self._selected_guided_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self._highlight_step_target(step)
            if not success:
                message = "{0} {1}".format(message, step.get("student_text", "")).strip()
            self.guided_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_check_step(self):
            step = self._selected_guided_step()
            if not step:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.validate_step(step)
            self.guided_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_do_it_for_me(self):
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            step = self._selected_guided_step()
            if not step or not steps:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.restore_step(step, "post")
            self._highlight_step_target(step)
            current_row = self.guided_steps_list.currentRow()
            if current_row < len(steps) - 1:
                self.guided_steps_list.setCurrentRow(current_row + 1)
            self.guided_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_reset(self):
            success, message = self.controller.reset_lesson(self.current_lesson_id)
            if success:
                self.guided_step_index = 0
                self._refresh_guided_steps(reset_index=True)
            self.guided_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_back(self):
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            if not steps:
                self._set_status("This lesson does not have any steps yet.", success=False)
                return
            row = self.guided_steps_list.currentRow()
            target_row = max(0, row - 1)
            if row <= 0:
                success, message = self.controller.reset_lesson(self.current_lesson_id)
            else:
                prior_step = steps[target_row]
                success, message = self.controller.restore_step(prior_step, "pre")
            self.guided_steps_list.setCurrentRow(target_row)
            self.guided_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _guided_next(self):
            lesson = self._current_lesson()
            steps = (lesson or {}).get("steps") or []
            step = self._selected_guided_step()
            if not step or not steps:
                self._set_status("Pick a step first.", success=False)
                return
            success, message = self.controller.validate_step(step)
            if not success:
                message = "{0} Use Check My Work or Do It For Me first.".format(message)
                self.guided_status_label.setText("Status: {0}".format(message))
                self._set_status(message, success=False)
                return
            current_row = self.guided_steps_list.currentRow()
            if current_row < len(steps) - 1:
                self.guided_steps_list.setCurrentRow(current_row + 1)
                self.guided_status_label.setText("Status: Great. Move on to the next practice step.")
                self._set_status("Moved to the next guided-practice step.", success=True)
                return
            self.guided_status_label.setText("Status: Lesson complete. The student matched the final step.")
            self._set_status("Guided practice complete.", success=True)

        def _pose_compare_root_names(self):
            return list(self.pose_compare_roots or [])

        def _pose_compare_style(self):
            return self.pose_compare_style_combo.currentData() or POSE_COMPARE_AFTER

        def _pose_compare_use_selected_roots(self):
            selection = _safe_selected_nodes()
            if not selection:
                self._set_status("Pick one or more roots first.", success=False)
                return
            self.pose_compare_roots = list(selection)
            display_names = [_short_name(node_name) for node_name in selection]
            self.pose_compare_roots_line.setText(", ".join(display_names))
            self.pose_compare_status_label.setText("Status: Using the current Maya selection as the compare roots.")
            self._set_status("Using the current Maya selection for pose compare.", success=True)

        def _pose_compare_use_current_frame(self):
            self.pose_compare_frame_spin.setValue(_current_frame_int())
            self.pose_compare_status_label.setText("Status: Using the current Maya frame.")
            self._set_status("Loaded the current Maya frame into Pose Compare.", success=True)

        def _refresh_pose_compare_list(self):
            if not hasattr(self, "pose_compare_list"):
                return
            current_item = self.pose_compare_list.currentItem()
            current_snapshot_id = current_item.data(QtCore.Qt.UserRole) if current_item else ""
            self.pose_compare_list.clear()
            snapshots = self.controller.pose_compare_snapshots()
            selected_row = 0
            for index, snapshot in enumerate(snapshots):
                frame_value = int(round(float(snapshot.get("frame", 0.0))))
                style_key = snapshot.get("style", POSE_COMPARE_AFTER)
                style_label = POSE_COMPARE_STYLES.get(style_key, POSE_COMPARE_STYLES[POSE_COMPARE_AFTER]).get("label", style_key)
                label = "F{0}: {1} [{2}]".format(frame_value, snapshot.get("label", "Pose Compare"), style_label)
                item = QtWidgets.QListWidgetItem(label)
                item.setData(QtCore.Qt.UserRole, snapshot.get("id"))
                self.pose_compare_list.addItem(item)
                if snapshot.get("id") == current_snapshot_id:
                    selected_row = index
            if self.pose_compare_list.count():
                self.pose_compare_list.setCurrentRow(min(selected_row, self.pose_compare_list.count() - 1))

        def _selected_pose_compare_snapshot_id(self):
            item = self.pose_compare_list.currentItem()
            if not item:
                return ""
            return item.data(QtCore.Qt.UserRole) or ""

        def _pose_compare_create_snapshot(self):
            success, message, _snapshot = self.controller.create_pose_compare_snapshot(
                self._pose_compare_root_names(),
                self.pose_compare_label_line.text() or "Pose Compare",
                frame_value=self.pose_compare_frame_spin.value(),
                offset_distance=self.pose_compare_offset_spin.value(),
                style_key=self._pose_compare_style(),
            )
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)
            self._refresh_pose_compare_list()

        def _pose_compare_begin_capture(self):
            success, message = self.controller.begin_pose_compare_capture(
                self._pose_compare_root_names(),
                self.pose_compare_label_line.text() or "Pose Fix",
                frame_value=self.pose_compare_frame_spin.value(),
                offset_distance=self.pose_compare_offset_spin.value(),
                style_key=self._pose_compare_style(),
            )
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _pose_compare_finish_capture(self):
            success, message, _snapshot = self.controller.finish_pose_compare_capture(
                label_text=self.pose_compare_label_line.text() or "Pose Fix",
                frame_value=self.pose_compare_frame_spin.value(),
                offset_distance=self.pose_compare_offset_spin.value(),
                style_key=self._pose_compare_style(),
            )
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)
            self._refresh_pose_compare_list()

        def _pose_compare_cancel_capture(self):
            success, message = self.controller.cancel_pose_compare_capture()
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)

        def _pose_compare_delete_frame(self):
            success, message = self.controller.delete_pose_compare_frame(self.pose_compare_frame_spin.value())
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)
            self._refresh_pose_compare_list()

        def _pose_compare_delete_selected(self):
            snapshot_id = self._selected_pose_compare_snapshot_id()
            if not snapshot_id:
                self._set_status("Pick a pose compare snapshot first.", success=False)
                return
            success, message = self.controller.delete_pose_compare_snapshot(snapshot_id)
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)
            self._refresh_pose_compare_list()

        def _pose_compare_clear_all(self):
            success, message = self.controller.clear_pose_compare_snapshots()
            self.pose_compare_status_label.setText("Status: {0}".format(message))
            self._set_status(message, success)
            self._refresh_pose_compare_list()

        def _dock_window_right(self):
            if not _workspace_control_exists(WORKSPACE_CONTROL_NAME):
                success, message = _show_window_dockable(self, floating=True, area="right")
                if not success:
                    self._set_status(message, success)
                    return
            success, message = _dock_workspace_control(WORKSPACE_CONTROL_NAME, area="right", tab=False)
            self._set_status(message, success)

        def _float_window(self):
            if not _workspace_control_exists(WORKSPACE_CONTROL_NAME):
                success, message = _show_window_dockable(self, floating=True, area="right")
                self._set_status(message, success)
                return
            success, message = _float_workspace_control(WORKSPACE_CONTROL_NAME)
            self._set_status(message, success)

        def _set_status(self, message, success=True):
            self.status_label.setText(message)
            palette = self.status_label.palette()
            palette.setColor(self.status_label.foregroundRole(), QtGui.QColor("#24A148" if success else "#DA1E28"))
            self.status_label.setPalette(palette)

        def _open_follow_url(self, *_args):
            _open_external_url(FOLLOW_AMIR_URL)

        def _open_donate_url(self):
            _open_external_url(DONATE_URL)


def _close_existing_window():
    global GLOBAL_WINDOW
    if GLOBAL_WINDOW is not None:
        try:
            GLOBAL_WINDOW.close()
            GLOBAL_WINDOW.deleteLater()
        except Exception:
            pass
    GLOBAL_WINDOW = None
    if not QtWidgets:
        return
    app = QtWidgets.QApplication.instance()
    if not app:
        return
    for widget in app.topLevelWidgets():
        try:
            if widget.objectName() == WINDOW_OBJECT_NAME:
                widget.close()
                widget.deleteLater()
        except Exception:
            pass
    if QtWidgets and MAYA_AVAILABLE:
        try:
            _delete_workspace_control(WORKSPACE_CONTROL_NAME)
        except Exception:
            pass


def _process_qt_events(cycles=12):
    if not QtWidgets:
        return
    app = QtWidgets.QApplication.instance()
    if not app:
        return
    for _index in range(max(1, int(cycles or 1))):
        try:
            app.processEvents()
        except Exception:
            break


def _workspace_control_exists(name=WORKSPACE_CONTROL_NAME):
    return bool(MAYA_AVAILABLE and cmds and cmds.workspaceControl(name, exists=True))


def _show_window_dockable(window, floating=True, area="right"):
    if not window:
        return False, "No tutorial window is available to show."
    try:
        window.show(dockable=True, floating=bool(floating), area=area)
        _process_qt_events()
    except Exception as exc:
        try:
            window.show()
        except Exception:
            pass
        return False, "Could not show the tutorial as a dockable Maya panel: {0}".format(exc)
    if not _workspace_control_exists(WORKSPACE_CONTROL_NAME):
        return False, "Maya did not create the dockable workspace control."
    if floating:
        return True, "Opened the tutorial as a floating dockable Maya panel."
    return True, "Opened the tutorial as a docked Maya panel."


def _dock_workspace_control(name=WORKSPACE_CONTROL_NAME, area="right", tab=False):
    if not _workspace_control_exists(name):
        return False, "The dockable Maya workspace control is not open yet."
    try:
        cmds.workspaceControl(name, edit=True, dockToMainWindow=(area, bool(tab)))
        cmds.workspaceControl(name, edit=True, restore=True)
        _process_qt_events()
        floating = bool(cmds.workspaceControl(name, query=True, floating=True))
    except Exception as exc:
        return False, "Could not dock the Maya workspace control: {0}".format(exc)
    if floating:
        return False, "Maya kept the tutorial panel floating instead of docking it."
    return True, "Docked the tutorial panel into Maya's {0} layout.".format(area)


def _float_workspace_control(name=WORKSPACE_CONTROL_NAME):
    if not _workspace_control_exists(name):
        return False, "The dockable Maya workspace control is not open yet."
    try:
        cmds.workspaceControl(name, edit=True, floating=True)
        cmds.workspaceControl(name, edit=True, restore=True)
        _process_qt_events()
        floating = bool(cmds.workspaceControl(name, query=True, floating=True))
    except Exception as exc:
        return False, "Could not float the Maya workspace control: {0}".format(exc)
    if not floating:
        return False, "Maya kept the tutorial panel docked instead of floating it."
    return True, "Floated the tutorial panel so it can be moved freely."


if QtWidgets:
    def _delete_workspace_control(name):
        if MAYA_AVAILABLE and cmds and cmds.workspaceControl(name, exists=True):
            try:
                cmds.deleteUI(name, control=True)
            except Exception:
                cmds.deleteUI(name)


def _shelf_button_command(repo_path, mode):
    return (
        "import importlib\n"
        "import sys\n"
        "repo_path = r\"{0}\"\n"
        "if repo_path not in sys.path:\n"
        "    sys.path.insert(0, repo_path)\n"
        "import maya_tutorial_authoring\n"
        "importlib.reload(maya_tutorial_authoring)\n"
        "maya_tutorial_authoring.launch_maya_tutorial_authoring(dock=True, mode=\"{1}\")\n"
    ).format(repo_path, mode)


def install_maya_tutorial_authoring_shelf_button(shelf_name=DEFAULT_SHELF_NAME, button_label=DEFAULT_SHELF_BUTTON_LABEL, repo_path=None):
    if not MAYA_AVAILABLE:
        raise RuntimeError("install_maya_tutorial_authoring_shelf_button() must run inside Autodesk Maya.")
    repo_path = repo_path or os.path.dirname(os.path.abspath(__file__))
    metadata = maya_shelf_utils.install_shelf_button(
        command_text=_shelf_button_command(repo_path, PLAYBACK_MODE_AUTHOR),
        doc_tag=SHELF_BUTTON_DOC_TAG,
        annotation="Launch Maya Tutorial Authoring",
        button_label=button_label,
        image_overlay_label="TT",
        shelf_name=shelf_name,
    )
    return metadata["button"]


def launch_maya_tutorial_authoring(dock=False, mode=PLAYBACK_MODE_AUTHOR, lesson_id=None):
    global GLOBAL_CONTROLLER, GLOBAL_WINDOW
    if not (MAYA_AVAILABLE and QtWidgets):
        raise RuntimeError("Maya Tutorial Authoring must be launched inside Maya with PySide available.")

    _close_existing_window()
    if dock:
        _delete_workspace_control(WORKSPACE_CONTROL_NAME)

    GLOBAL_CONTROLLER = MayaTutorialAuthoringController()
    GLOBAL_WINDOW = MayaTutorialAuthoringWindow(GLOBAL_CONTROLLER, parent=_maya_main_window(), mode=mode, lesson_id=lesson_id)
    success, _message = _show_window_dockable(GLOBAL_WINDOW, floating=True, area="right")
    if dock and success:
        _dock_workspace_control(WORKSPACE_CONTROL_NAME, area="right", tab=False)
    elif not success:
        GLOBAL_WINDOW.show()
    return GLOBAL_WINDOW


def launch_maya_tutorial_player(dock=False, lesson_id=None):
    return launch_maya_tutorial_authoring(dock=dock, mode=PLAYBACK_MODE_PLAYER, lesson_id=lesson_id)


def launch_maya_tutorial_guided_practice(dock=False, lesson_id=None):
    return launch_maya_tutorial_authoring(dock=dock, mode=PLAYBACK_MODE_GUIDED, lesson_id=lesson_id)


def launch_maya_pose_compare(dock=False):
    return launch_maya_tutorial_authoring(dock=dock, mode=PLAYBACK_MODE_POSE_COMPARE, lesson_id=None)


def dock_maya_tutorial_authoring_window(area="right", tab=False):
    return _dock_workspace_control(WORKSPACE_CONTROL_NAME, area=area, tab=tab)


def float_maya_tutorial_authoring_window():
    return _float_workspace_control(WORKSPACE_CONTROL_NAME)


__all__ = [
    "DEFAULT_SHELF_BUTTON_LABEL",
    "DEFAULT_SHELF_NAME",
    "DONATE_URL",
    "FOLLOW_AMIR_URL",
    "LESSON_JSON_ATTR",
    "LESSON_ROOT_NODE",
    "MayaTutorialAuthoringController",
    "MayaTutorialAuthoringWindow",
    "PLAYBACK_MODE_AUTHOR",
    "PLAYBACK_MODE_GUIDED",
    "PLAYBACK_MODE_PLAYER",
    "PLAYBACK_MODE_POSE_COMPARE",
    "POSE_COMPARE_AFTER",
    "POSE_COMPARE_BEFORE",
    "POSE_COMPARE_GROUP_NAME",
    "POSE_COMPARE_JSON_ATTR",
    "POSE_COMPARE_ROOT_NODE",
    "SHELF_BUTTON_DOC_TAG",
    "WINDOW_OBJECT_NAME",
    "WORKSPACE_CONTROL_NAME",
    "install_maya_tutorial_authoring_shelf_button",
    "dock_maya_tutorial_authoring_window",
    "float_maya_tutorial_authoring_window",
    "launch_maya_tutorial_authoring",
    "launch_maya_tutorial_guided_practice",
    "launch_maya_pose_compare",
    "launch_maya_tutorial_player",
]
