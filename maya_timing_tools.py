from __future__ import absolute_import, division, print_function

import json
import math
import os

import maya_contact_hold as hold_utils

try:
    import maya.cmds as cmds
    MAYA_AVAILABLE = True
except Exception:
    cmds = None
    MAYA_AVAILABLE = False

try:
    import maya.mel as mel
except Exception:
    mel = None

try:
    from PySide2 import QtCore, QtGui, QtWidgets
except Exception:
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
    except Exception:
        QtCore = QtGui = QtWidgets = None

try:
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
except Exception:
    MayaQWidgetDockableMixin = None

try:
    import maya.api.OpenMaya as om2
except Exception:
    om2 = None

WINDOW_OBJECT_NAME = "mayaTimingToolsWindow"
AUTO_SNAP_OPTION = "AmirMayaAnimWorkflowAutoSnapToFrames"
DEFAULT_AUTO_SNAP = True
DEFAULT_TIME_UNIT = "ntsc"
DEFAULT_PLAYBACK_SPEED = 1.0
DEFAULT_MAX_BACKUPS = 5
DEFAULT_RENDER_ENV_LIGHT_EXPOSURE = 1.5
DEFAULT_RENDER_ENV_LIGHT_INTENSITY = 0.2
DEFAULT_RENDER_ENV_SCALE_MULTIPLIER = 3.5
DEFAULT_SCENE_HELPERS_CAMERA_BASE_HEIGHT = 5.0
DEFAULT_SCENE_HELPERS_CAMERA_HEIGHT_OFFSET = 0.0
DEFAULT_SCENE_HELPERS_CAMERA_DOLLY_OFFSET = 0.0
SCENE_HELPERS_ROOT_NAME = "amirSceneHelpers_GRP"
SCENE_HELPERS_RENDER_ROOT_NAME = "amirSceneRenderEnv_GRP"
SCENE_HELPERS_CAMERA_ROOT_NAME = "amirSceneRenderCameras_GRP"
SCENE_HELPERS_LIGHT_ROOT_NAME = "amirSceneRenderLights_GRP"
SCENE_HELPERS_FLOOR_NAME = "amirSceneRenderFloor_GEO"
SCENE_HELPERS_BACKDROP_NAME = "amirSceneRenderBackdrop_GEO"
SCENE_HELPERS_CYCLORAMA_NAME = "amirSceneCyclorama_GEO"
SCENE_HELPERS_CYCLORAMA_MAT_NAME = "sceneHelpersCyclorama_MAT"
SCENE_HELPERS_CYCLORAMA_SG_NAME = "sceneHelpersCyclorama_MATSG"
SCENE_HELPERS_CYCLORAMA_ATTR = "sceneHelpersCyclorama"
SCENE_HELPERS_INFINITY_WALL_NAME = SCENE_HELPERS_CYCLORAMA_NAME
SCENE_HELPERS_LEGACY_INFINITY_WALL_NAME = "amirSceneRenderInfinityWall_GEO"
SCENE_HELPERS_INFINITY_WALL_MAT_NAME = SCENE_HELPERS_CYCLORAMA_MAT_NAME
SCENE_HELPERS_INFINITY_WALL_SG_NAME = SCENE_HELPERS_CYCLORAMA_SG_NAME

_CYCLORAMA_POINTS = [
    (-336.44533901151135, 0.0, 173.6245593460942),
    (336.44533901151135, 0.0, 173.6245593460942),
    (-336.44533901151135, 415.02265454619277, -471.9410829452879),
    (336.44533901151135, 415.02265454619277, -471.9410829452879),
    (336.44533901151135, 415.02265454619277, -560.9881722280204),
    (-336.44533901151135, 415.02265454619277, -560.9881722280204),
    (-336.44533901151135, 0.0, -229.97837667726787),
    (-336.44533901151135, 3.195199236504672, -261.5608473856972),
    (-336.44533901151135, 12.72612560197932, -292.6029351690814),
    (-336.44533901151135, 28.429703910997215, -322.5734976907079),
    (-336.44533901151135, 50.03723998579082, -350.9597312510704),
    (-336.44533901151135, 77.17902629888164, -377.2759391242581),
    (-336.44533901151135, 109.39065100844118, -401.07184348011873),
    (-336.44533901151135, 146.12097833523038, -421.94029691294486),
    (-336.44533901151135, 186.74152334475124, -439.52422368116714),
    (-336.44533901151135, 230.55727299265646, -453.5227618622041),
    (-336.44533901151135, 276.8185212830406, -463.6963933331772),
    (-336.44533901151135, 324.73371853961305, -469.8710529387356),
    (-336.44533901151135, 373.4830466895025, -471.9410829452879),
    (336.44533901151135, 373.4830466895025, -471.9410829452879),
    (336.44533901151135, 324.73371853961305, -469.8710529387356),
    (336.44533901151135, 276.8185212830406, -463.6963933331772),
    (336.44533901151135, 230.55727299265646, -453.5227618622041),
    (336.44533901151135, 186.74152334475124, -439.52422368116714),
    (336.44533901151135, 146.12097833523038, -421.94029691294486),
    (336.44533901151135, 109.39065100844118, -401.07184348011873),
    (336.44533901151135, 77.17902629888164, -377.2759391242581),
    (336.44533901151135, 50.03723998579082, -350.9597312510704),
    (336.44533901151135, 28.429703910997215, -322.5734976907079),
    (336.44533901151135, 12.72612560197932, -292.6029351690814),
    (336.44533901151135, 3.195199236504672, -261.5608473856972),
    (336.44533901151135, 0.0, -229.97837667726787),
]
_CYCLORAMA_FACE_COUNTS = [4] * 15
_CYCLORAMA_FACE_CONNECTS = [
    2, 3, 4, 5,
    0, 1, 31, 6,
    18, 19, 3, 2,
    18, 17, 20, 19,
    17, 16, 21, 20,
    16, 15, 22, 21,
    15, 14, 23, 22,
    14, 13, 24, 23,
    13, 12, 25, 24,
    12, 11, 26, 25,
    11, 10, 27, 26,
    10, 9, 28, 27,
    9, 8, 29, 28,
    8, 7, 30, 29,
    7, 6, 31, 30,
]
SCENE_HELPERS_CAMERA_HEIGHT_OFFSET_OPTION = "AmirMayaAnimWorkflowSceneHelpersCameraHeightOffset"
SCENE_HELPERS_CAMERA_DOLLY_OFFSET_OPTION = "AmirMayaAnimWorkflowSceneHelpersCameraDollyOffset"
SCENE_HELPERS_CAMERA_NAMES = {
    "front": "amirSceneFront_cam",
    "side": "amirSceneSide_cam",
    "three_quarter": "amirSceneThreeQuarter_cam",
}
SCENE_HELPERS_CAMERA_PRESET_LABELS = {
    "perspective": "Perspective",
    "front": "Front",
    "side": "Side",
    "three_quarter": "Three Quarter",
}
SCENE_HELPERS_BOOKMARK_NAMES = {
    "front": "Scene Helpers - Front",
    "side": "Scene Helpers - Side",
    "three_quarter": "Scene Helpers - Three Quarter",
}
SCENE_HELPERS_CAMERA_MAP_ATTR = "sceneHelpersCameraMap"
SCENE_HELPERS_LIGHTS_ATTR = "sceneHelpersLights"
SCENE_HELPERS_LIGHT_MODE_ATTR = "sceneHelpersLightMode"
SCENE_HELPERS_CAMERA_HEIGHT_OFFSET_ATTR = "sceneHelpersCameraHeightOffset"
SCENE_HELPERS_CAMERA_DOLLY_OFFSET_ATTR = "sceneHelpersCameraDollyOffset"
SCENE_HELPERS_CAMERA_DISTANCE_ATTR = "sceneHelpersCameraDistance"
SCENE_HELPERS_HEIGHT_SPAN_ATTR = "sceneHelpersHeightSpan"
FOLLOW_AMIR_URL = hold_utils.FOLLOW_AMIR_URL
DEFAULT_DONATE_URL = hold_utils.DEFAULT_DONATE_URL
DONATE_URL = os.environ.get("AMIR_PAYPAL_DONATE_URL") or os.environ.get("AMIR_DONATE_URL") or DEFAULT_DONATE_URL

GLOBAL_CONTROLLER = None
GLOBAL_WINDOW = None

_qt_flag = hold_utils._qt_flag
_style_donate_button = hold_utils._style_donate_button
_open_external_url = hold_utils._open_external_url
_maya_main_window = hold_utils._maya_main_window


def _dedupe_preserve_order(values):
    seen = set()
    ordered = []
    for value in values:
        if value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def _short_name(node_name):
    return (node_name or "").split("|")[-1]


def _option_var_bool(option_name, default):
    if not cmds or not cmds.optionVar(exists=option_name):
        return bool(default)
    try:
        return bool(cmds.optionVar(query=option_name))
    except Exception:
        return bool(default)


def _save_option_var_bool(option_name, value):
    if not cmds:
        return
    try:
        cmds.optionVar(intValue=(option_name, int(bool(value))))
    except Exception:
        pass


def _option_var_float(option_name, default):
    if not cmds or not cmds.optionVar(exists=option_name):
        return float(default)
    try:
        return float(cmds.optionVar(query=option_name))
    except Exception:
        return float(default)


def _save_option_var_float(option_name, value):
    if not cmds:
        return
    try:
        cmds.optionVar(floatValue=(option_name, float(value)))
    except Exception:
        pass


def _current_time_unit():
    if not cmds:
        return DEFAULT_TIME_UNIT
    try:
        return cmds.currentUnit(query=True, time=True) or DEFAULT_TIME_UNIT
    except Exception:
        return DEFAULT_TIME_UNIT


def _current_auto_key_state():
    if not cmds:
        return False
    try:
        return bool(cmds.autoKeyframe(query=True, state=True))
    except Exception:
        return False


def _selected_transform_nodes():
    if not cmds:
        return []
    selected = cmds.ls(selection=True, long=True) or []
    transforms = []
    for node_name in selected:
        if not node_name or not cmds.objExists(node_name):
            continue
        try:
            if cmds.nodeType(node_name) == "transform":
                transforms.append(node_name)
                continue
        except Exception:
            pass
        try:
            parents = cmds.listRelatives(node_name, parent=True, fullPath=True) or []
        except Exception:
            parents = []
        for parent_name in parents:
            if parent_name and cmds.objExists(parent_name):
                try:
                    if cmds.nodeType(parent_name) == "transform":
                        transforms.append(parent_name)
                except Exception:
                    continue
    return _dedupe_preserve_order(transforms)


def _scene_keyed_transforms():
    if not cmds:
        return []
    nodes = []
    anim_curves = cmds.ls(type="animCurve") or []
    for curve_name in anim_curves:
        try:
            destinations = cmds.listConnections(curve_name, source=False, destination=True, plugs=True) or []
        except Exception:
            destinations = []
        for plug_name in destinations:
            node_name = plug_name.split(".", 1)[0]
            if not node_name or not cmds.objExists(node_name):
                continue
            try:
                if cmds.nodeType(node_name) == "transform":
                    nodes.append(node_name)
                    continue
            except Exception:
                pass
            try:
                parents = cmds.listRelatives(node_name, parent=True, fullPath=True) or []
            except Exception:
                parents = []
            for parent_name in parents:
                if parent_name and cmds.objExists(parent_name):
                    try:
                        if cmds.nodeType(parent_name) == "transform":
                            nodes.append(parent_name)
                    except Exception:
                        continue
    return _dedupe_preserve_order(nodes)


def _all_model_panels():
    if not cmds:
        return []
    try:
        return cmds.getPanel(type="modelPanel") or []
    except Exception:
        return []


def _scene_helpers_perspective_camera():
    if not cmds:
        return "persp"
    for camera_name in ("persp", "perspShape"):
        try:
            if cmds.objExists(camera_name):
                return camera_name
        except Exception:
            pass
    try:
        for panel_name in _all_model_panels():
            try:
                camera_name = cmds.modelEditor(panel_name, query=True, camera=True) or ""
            except Exception:
                camera_name = ""
            if _short_name(camera_name).lower().startswith("persp"):
                return camera_name
    except Exception:
        pass
    return "persp"


def _snap_curve_times(node_name, attr_name):
    times = cmds.keyframe(node_name, attribute=attr_name, query=True, timeChange=True) or []
    if not times:
        return 0
    unique_times = sorted({float(time_value) for time_value in times})
    if not unique_times:
        return 0

    if len(unique_times) == 1:
        snapped_times = [int(round(unique_times[0]))]
    else:
        start_time = unique_times[0]
        end_time = unique_times[-1]
        start_frame = int(round(start_time))
        total_span = float(end_time - start_time)
        target_span = max(1, int(round(end_time - start_time)), len(unique_times) - 1)
        snapped_times = []
        previous_time = None
        for time_value in unique_times:
            if total_span <= 1.0e-8:
                candidate_time = start_frame
            else:
                normalized = (time_value - start_time) / total_span
                candidate_time = int(round(start_frame + normalized * float(target_span)))
            if previous_time is not None and candidate_time <= previous_time:
                candidate_time = previous_time + 1
            snapped_times.append(candidate_time)
            previous_time = candidate_time

    changed = 0
    for old_time, new_time in zip(unique_times, snapped_times):
        delta = float(new_time) - float(old_time)
        if abs(delta) <= 1.0e-8:
            continue
        cmds.keyframe(
            node_name,
            attribute=attr_name,
            edit=True,
            time=(float(old_time), float(old_time)),
            relative=True,
            timeChange=delta,
        )
        changed += 1
    return changed


def _make_snap_icon():
    if not QtGui:
        return QtGui.QIcon() if QtGui else None
    pixmap = QtGui.QPixmap(24, 24)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        frame_pen = QtGui.QPen(QtGui.QColor("#2F80ED"))
        frame_pen.setWidth(2)
        painter.setPen(frame_pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawRoundedRect(4, 4, 16, 16, 2, 2)
        painter.drawLine(4, 12, 20, 12)
        painter.drawLine(12, 4, 12, 20)
        arrow_pen = QtGui.QPen(QtGui.QColor("#EAF2FF"))
        arrow_pen.setWidth(2)
        painter.setPen(arrow_pen)
        painter.drawLine(7, 7, 17, 17)
        painter.drawLine(17, 17, 14, 17)
        painter.drawLine(17, 17, 17, 14)
    finally:
        painter.end()
    return QtGui.QIcon(pixmap)


def _make_key_icon():
    if not QtGui:
        return QtGui.QIcon() if QtGui else None
    pixmap = QtGui.QPixmap(24, 24)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        outline_pen = QtGui.QPen(QtGui.QColor("#D4A017"))
        outline_pen.setWidth(2)
        painter.setPen(outline_pen)
        painter.setBrush(QtGui.QColor("#F5D76E"))
        painter.drawEllipse(4, 7, 7, 7)
        painter.drawRect(10, 9, 10, 3)
        painter.drawRect(16, 7, 2, 7)
        painter.drawRect(18, 7, 2, 5)
    finally:
        painter.end()
    return QtGui.QIcon(pixmap)


def _primary_transform(node_name):
    if not node_name:
        return ""
    try:
        if cmds.nodeType(node_name) == "transform":
            return node_name
    except Exception:
        pass
    try:
        parents = cmds.listRelatives(node_name, parent=True, fullPath=True) or []
    except Exception:
        parents = []
    return parents[0] if parents else node_name


def _delete_if_exists(node_name):
    if not cmds or not node_name:
        return
    try:
        if cmds.objExists(node_name):
            cmds.delete(node_name)
    except Exception:
        pass


def _selected_render_targets():
    if not cmds:
        return []
    selected = cmds.ls(selection=True, long=True) or []
    targets = []
    for node_name in selected:
        if not node_name or not cmds.objExists(node_name):
            continue
        if _is_scene_helpers_transform(node_name):
            continue
        try:
            if cmds.nodeType(node_name) == "transform":
                targets.append(node_name)
                continue
        except Exception:
            pass
        try:
            parents = cmds.listRelatives(node_name, parent=True, fullPath=True) or []
        except Exception:
            parents = []
        for parent_name in parents:
            if parent_name and cmds.objExists(parent_name):
                try:
                    if cmds.nodeType(parent_name) == "transform":
                        targets.append(parent_name)
                except Exception:
                    continue
    return _dedupe_preserve_order(targets)


def _mesh_transforms_in_scene():
    if not cmds:
        return []
    transforms = []
    for shape_name in cmds.ls(type="mesh", long=True) or []:
        try:
            if cmds.getAttr(shape_name + ".intermediateObject"):
                continue
        except Exception:
            pass
        try:
            parent_names = cmds.listRelatives(shape_name, parent=True, fullPath=True) or []
        except Exception:
            parent_names = []
        for parent_name in parent_names:
            if parent_name and cmds.objExists(parent_name):
                try:
                    if cmds.nodeType(parent_name) == "transform":
                        if _is_scene_helpers_transform(parent_name):
                            continue
                        transforms.append(parent_name)
                except Exception:
                    continue
    return _dedupe_preserve_order(transforms)


def _visible_mesh_transforms():
    if not cmds:
        return []
    transforms = []
    for transform_name in _mesh_transforms_in_scene():
        if _is_scene_helpers_transform(transform_name):
            continue
        try:
            if not cmds.getAttr(transform_name + ".visibility"):
                continue
        except Exception:
            pass
        transforms.append(transform_name)
    return transforms


def _transform_bbox(node_name):
    if not cmds or not node_name or not cmds.objExists(node_name):
        return None
    try:
        bounds = cmds.exactWorldBoundingBox(node_name)
    except Exception:
        return None
    if not bounds or len(bounds) != 6:
        return None
    return [float(value) for value in bounds]


def _union_bbox(bboxes):
    valid = [bbox for bbox in bboxes if bbox]
    if not valid:
        return None
    min_x = min(bbox[0] for bbox in valid)
    min_y = min(bbox[1] for bbox in valid)
    min_z = min(bbox[2] for bbox in valid)
    max_x = max(bbox[3] for bbox in valid)
    max_y = max(bbox[4] for bbox in valid)
    max_z = max(bbox[5] for bbox in valid)
    return [min_x, min_y, min_z, max_x, max_y, max_z]


def _scene_helpers_target_nodes():
    selected_targets = _selected_render_targets()
    if selected_targets:
        return selected_targets
    visible_meshes = _visible_mesh_transforms()
    if visible_meshes:
        largest = []
        largest_volume = -1.0
        for transform_name in visible_meshes:
            bbox = _transform_bbox(transform_name)
            if not bbox:
                continue
            span_x = max(bbox[3] - bbox[0], 0.0)
            span_y = max(bbox[4] - bbox[1], 0.0)
            span_z = max(bbox[5] - bbox[2], 0.0)
            volume = span_x * span_y * span_z
            if volume >= largest_volume:
                largest_volume = volume
                largest = [transform_name]
        if largest:
            return largest
    scene_meshes = _mesh_transforms_in_scene()
    return scene_meshes[:1]


def _is_scene_helpers_transform(node_name):
    if not node_name:
        return False
    short_name = _short_name(node_name)
    return short_name.startswith("amirSceneHelpers") or short_name.startswith("amirSceneRender") or short_name.startswith("sceneHelpers")


def _scene_helpers_focus_bbox():
    target_nodes = _scene_helpers_target_nodes()
    if not target_nodes:
        return None, []
    bbox = _union_bbox([_transform_bbox(node_name) for node_name in target_nodes])
    if not bbox:
        return None, target_nodes
    return bbox, target_nodes


def _center_from_bbox(bbox):
    return [
        (bbox[0] + bbox[3]) * 0.5,
        (bbox[1] + bbox[4]) * 0.5,
        (bbox[2] + bbox[5]) * 0.5,
    ]


def _span_from_bbox(bbox):
    return max(bbox[3] - bbox[0], bbox[4] - bbox[1], bbox[5] - bbox[2], 1.0)


def _ensure_scene_helpers_root():
    if cmds.objExists(SCENE_HELPERS_ROOT_NAME):
        return SCENE_HELPERS_ROOT_NAME
    return cmds.createNode("transform", name=SCENE_HELPERS_ROOT_NAME)


def _delete_existing_scene_helpers():
    for node_name in (
        SCENE_HELPERS_ROOT_NAME,
        SCENE_HELPERS_RENDER_ROOT_NAME,
        SCENE_HELPERS_CAMERA_ROOT_NAME,
        SCENE_HELPERS_LIGHT_ROOT_NAME,
        SCENE_HELPERS_INFINITY_WALL_NAME,
        SCENE_HELPERS_LEGACY_INFINITY_WALL_NAME,
    ):
        _delete_if_exists(node_name)
    for node_name in list(SCENE_HELPERS_CAMERA_NAMES.values()) + list(SCENE_HELPERS_BOOKMARK_NAMES.values()) + [SCENE_HELPERS_FLOOR_NAME, SCENE_HELPERS_BACKDROP_NAME, SCENE_HELPERS_INFINITY_WALL_MAT_NAME, SCENE_HELPERS_INFINITY_WALL_SG_NAME]:
        _delete_if_exists(node_name)


def _set_arnold_light_settings(light_shape, exposure):
    if not light_shape or not cmds.objExists(light_shape):
        return
    for attr_name, value in (("aiExposure", exposure), ("aiSamples", 2), ("intensity", DEFAULT_RENDER_ENV_LIGHT_INTENSITY)):
        try:
            if cmds.attributeQuery(attr_name, node=light_shape, exists=True):
                cmds.setAttr("{0}.{1}".format(light_shape, attr_name), value)
        except Exception:
            pass


def _make_camera(name, center, offset, focal_length=55.0):
    camera_result = cmds.camera(name=name) or []
    camera_transform = camera_result[0] if camera_result else name
    camera_shape = camera_result[1] if len(camera_result) > 1 else ""
    if camera_transform and cmds.objExists(camera_transform):
        cmds.xform(
            camera_transform,
            worldSpace=True,
            translation=(center[0] + offset[0], center[1] + offset[1], center[2] + offset[2]),
        )
        try:
            cmds.setAttr(camera_shape + ".focalLength", focal_length)
        except Exception:
            pass
    return camera_transform, camera_shape


def _scene_helpers_camera_specs(height_span, camera_distance):
    return {
        "front": ((0.0, DEFAULT_SCENE_HELPERS_CAMERA_BASE_HEIGHT, camera_distance), 55.0),
        "side": ((camera_distance, DEFAULT_SCENE_HELPERS_CAMERA_BASE_HEIGHT, 0.0), 55.0),
        "three_quarter": ((camera_distance * 0.72, DEFAULT_SCENE_HELPERS_CAMERA_BASE_HEIGHT, camera_distance * 0.72), 50.0),
    }


def _apply_scene_helpers_camera_offsets(render_root, center, height_span, camera_distance, height_offset, dolly_offset):
    if not cmds or not render_root or not cmds.objExists(render_root):
        return False, "Create the render environment first."
    camera_map_payload = ""
    try:
        camera_map_payload = cmds.getAttr(render_root + "." + SCENE_HELPERS_CAMERA_MAP_ATTR)
    except Exception:
        camera_map_payload = ""
    try:
        camera_map = json.loads(camera_map_payload or "{}")
    except Exception:
        camera_map = {}
    if not camera_map:
        return False, "Create the render environment first."

    specs = _scene_helpers_camera_specs(height_span, camera_distance)
    changed = 0
    for preset_key, (base_offset, _focal_length) in specs.items():
        camera_name = camera_map.get(preset_key) or SCENE_HELPERS_CAMERA_NAMES.get(preset_key, "")
        if not camera_name or not cmds.objExists(camera_name):
            continue
        final_offset = _scene_helpers_camera_offset_vector(base_offset, height_offset, dolly_offset)
        target_center = (center[0], center[1] + float(height_offset), center[2])
        try:
            cmds.xform(
                camera_name,
                worldSpace=True,
                translation=(center[0] + final_offset[0], center[1] + final_offset[1], center[2] + final_offset[2]),
            )
            _look_at(camera_name, target_center)
            changed += 1
        except Exception:
            continue
    for attr_name, value in (
        (SCENE_HELPERS_CAMERA_HEIGHT_OFFSET_ATTR, float(height_offset)),
        (SCENE_HELPERS_CAMERA_DOLLY_OFFSET_ATTR, float(dolly_offset)),
        (SCENE_HELPERS_CAMERA_DISTANCE_ATTR, float(camera_distance)),
        (SCENE_HELPERS_HEIGHT_SPAN_ATTR, float(height_span)),
    ):
        try:
            if cmds.attributeQuery(attr_name, node=render_root, exists=True):
                cmds.setAttr("{0}.{1}".format(render_root, attr_name), value)
            else:
                cmds.addAttr(render_root, longName=attr_name, attributeType="double")
                cmds.setAttr("{0}.{1}".format(render_root, attr_name), value)
        except Exception:
            pass
    return True, "Updated helper camera offsets for {0} camera(s).".format(changed)


def _look_at(camera_transform, center):
    aim_locator = cmds.spaceLocator(name=camera_transform + "_aim_LOC")[0]
    cmds.xform(aim_locator, worldSpace=True, translation=(center[0], center[1], center[2]))
    try:
        aim_constraint = cmds.aimConstraint(
            aim_locator,
            camera_transform,
            aimVector=(0, 0, -1),
            upVector=(0, 1, 0),
            worldUpType="scene",
            maintainOffset=False,
        ) or []
        if aim_constraint:
            cmds.delete(aim_constraint)
    finally:
        _delete_if_exists(aim_locator)


def _scene_helpers_camera_offset_vector(base_offset, height_offset=0.0, dolly_offset=0.0):
    x_value, y_value, z_value = base_offset
    y_value += float(height_offset)
    dolly_offset = float(dolly_offset)
    if abs(dolly_offset) <= 1.0e-8:
        return x_value, y_value, z_value
    horizontal_length = math.sqrt((x_value * x_value) + (z_value * z_value))
    if horizontal_length <= 1.0e-8:
        z_value += dolly_offset
        return x_value, y_value, z_value
    x_value += (x_value / horizontal_length) * dolly_offset
    z_value += (z_value / horizontal_length) * dolly_offset
    return x_value, y_value, z_value
def _create_scene_helpers_bookmark(camera_transform, bookmark_name):
    if not camera_transform or not cmds.objExists(camera_transform):
        return ""
    try:
        bookmark = cmds.cameraView(camera=camera_transform, name=bookmark_name, ab=True)
    except TypeError:
        try:
            bookmark = cmds.cameraView(camera=camera_transform, name=bookmark_name)
        except Exception:
            bookmark = ""
        except Exception:
            bookmark = ""
    return bookmark or bookmark_name


def _maya_arnold_available():
    if not cmds:
        return False
    plugin_names = ("mtoa", "mtoa.mll")
    for plugin_name in plugin_names:
        try:
            if cmds.pluginInfo(plugin_name, query=True, loaded=True):
                return True
        except Exception:
            pass
    return False


def _active_model_panel():
    if not cmds:
        return ""
    try:
        focused_panel = cmds.getPanel(withFocus=True) or ""
    except Exception:
        focused_panel = ""
    if focused_panel:
        try:
            if cmds.getPanel(typeOf=focused_panel) == "modelPanel":
                return focused_panel
        except Exception:
            pass
    return (_all_model_panels() or [""])[0]


def _set_model_panel_camera(camera_name, display_label=""):
    if not cmds or not camera_name or not cmds.objExists(camera_name):
        return False, "Camera preset is not available."
    panel = _active_model_panel()
    if not panel:
        label = display_label or _short_name(camera_name)
        return True, "Ready to use {0}. Click a viewport to apply it.".format(label)
    try:
        cmds.modelEditor(panel, edit=True, camera=camera_name)
    except Exception:
        try:
            cmds.lookThru(panel, camera_name)
        except Exception as exc:
            return False, "Could not switch the viewport camera: {0}".format(exc)
    label = ""
    short_name = _short_name(camera_name).lower()
    if short_name.startswith("persp"):
        label = SCENE_HELPERS_CAMERA_PRESET_LABELS.get("perspective", "Perspective")
    for preset_key, preset_label in SCENE_HELPERS_CAMERA_PRESET_LABELS.items():
        if camera_name == SCENE_HELPERS_CAMERA_NAMES.get(preset_key, ""):
            label = preset_label
            break
    return True, "Switched the viewport to {0}.".format(label or _short_name(camera_name))


def _apply_scene_helpers_camera_preset(preset_key):
    preset_key = (preset_key or "").strip().lower().replace(" ", "_").replace("-", "_")
    display_label = SCENE_HELPERS_CAMERA_PRESET_LABELS.get(preset_key, preset_key.replace("_", " ").title())
    if preset_key == "perspective":
        camera_name = _scene_helpers_perspective_camera()
        return _set_model_panel_camera(camera_name, display_label)
    if preset_key not in SCENE_HELPERS_CAMERA_NAMES:
        return False, "Choose Perspective, Front, Side, or Three-Quarter."
    if not cmds.objExists(SCENE_HELPERS_RENDER_ROOT_NAME):
        return False, "Create the render environment first."
    camera_map_payload = ""
    try:
        camera_map_payload = cmds.getAttr(SCENE_HELPERS_RENDER_ROOT_NAME + "." + SCENE_HELPERS_CAMERA_MAP_ATTR)
    except Exception:
        camera_map_payload = ""
    try:
        camera_map = json.loads(camera_map_payload or "{}")
    except Exception:
        camera_map = {}
    camera_name = camera_map.get(preset_key) or SCENE_HELPERS_CAMERA_NAMES.get(preset_key, "")
    if not camera_name or not cmds.objExists(camera_name):
        return False, "The {0} camera is missing. Rebuild the render environment.".format(display_label)
    return _set_model_panel_camera(camera_name, display_label)


def _ensure_cgab_blast_panel_opt_change_callback():
    if not mel:
        return
    try:
        exists = bool(mel.eval("exists CgAbBlastPanelOptChangeCallback"))
    except Exception:
        exists = False
    if exists:
        return
    for proc_definition in (
        "global proc CgAbBlastPanelOptChangeCallback(string $panel, string $state) {}",
        "global proc CgAbBlastPanelOptChangeCallback(string $panel) {}",
    ):
        try:
            mel.eval(proc_definition)
            return
        except Exception:
            pass


def _create_scene_helpers_sky_light(light_root, center, render_scale):
    light_mode = "fallback_directional"
    light_transform = ""
    light_shape = ""
    if _maya_arnold_available():
        try:
            light_node = cmds.shadingNode("aiSkyDomeLight", asLight=True, name="sceneHelpersSkyDomeLight")
        except Exception:
            light_node = ""
        light_transform = _primary_transform(light_node)
        if light_transform and cmds.objExists(light_transform):
            try:
                parent_result = cmds.parent(light_transform, light_root) or []
                if parent_result:
                    light_transform = _primary_transform(parent_result[0]) or light_transform
            except Exception:
                pass
            try:
                cmds.xform(light_transform, worldSpace=True, translation=center)
            except Exception:
                pass
            light_shape = (cmds.listRelatives(light_transform, shapes=True, fullPath=True) or [""])[0]
            if light_shape:
                _set_arnold_light_settings(light_shape, DEFAULT_RENDER_ENV_LIGHT_EXPOSURE * 1.1)
                try:
                    if cmds.attributeQuery("color", node=light_shape, exists=True):
                        cmds.setAttr(light_shape + ".color", 0.92, 0.96, 1.0, type="double3")
                except Exception:
                    pass
            light_mode = "arnold_skydome"
    if not light_transform or not cmds.objExists(light_transform):
        try:
            light_node = cmds.directionalLight(name="sceneHelpersSkyFallbackLight")
        except Exception:
            light_node = ""
        light_transform = _primary_transform(light_node)
        if light_transform and cmds.objExists(light_transform):
            try:
                parent_result = cmds.parent(light_transform, light_root) or []
                if parent_result:
                    light_transform = _primary_transform(parent_result[0]) or light_transform
            except Exception:
                pass
            try:
                cmds.xform(light_transform, worldSpace=True, translation=(center[0] + render_scale * 0.4, center[1] + render_scale * 0.9, center[2] + render_scale * 0.7))
            except Exception:
                pass
            try:
                _look_at(light_transform, center)
            except Exception:
                pass
            light_shape = (cmds.listRelatives(light_transform, shapes=True, fullPath=True) or [""])[0]
            if light_shape:
                try:
                    if cmds.attributeQuery("intensity", node=light_shape, exists=True):
                        cmds.setAttr(light_shape + ".intensity", 0.85)
                except Exception:
                    pass
            light_mode = "fallback_directional"
    return light_transform, light_shape, light_mode


def _create_scene_helpers_cyclorama(render_root, center, bbox, render_scale):
    wall = ""
    if om2 is not None and cmds:
        try:
            transform_name = cmds.createNode("transform", name=SCENE_HELPERS_CYCLORAMA_NAME)
            selection = om2.MSelectionList()
            selection.add(transform_name)
            transform_obj = selection.getDependNode(0)
            point_array = om2.MPointArray()
            for point in _CYCLORAMA_POINTS:
                point_array.append(om2.MPoint(*point))
            face_counts = om2.MIntArray()
            for face_count in _CYCLORAMA_FACE_COUNTS:
                face_counts.append(int(face_count))
            face_connects = om2.MIntArray()
            for face_index in _CYCLORAMA_FACE_CONNECTS:
                face_connects.append(int(face_index))
            mesh_fn = om2.MFnMesh()
            mesh_fn.create(point_array, face_counts, face_connects, parent=transform_obj)
            wall = transform_name
            try:
                base_width = abs(_CYCLORAMA_POINTS[1][0] - _CYCLORAMA_POINTS[0][0]) or 1.0
                target_width = max(render_scale * 4.2, 8.0)
                scale_factor = float(target_width) / float(base_width)
                cmds.xform(wall, scale=(scale_factor, scale_factor, scale_factor))
            except Exception:
                pass
        except Exception:
            wall = ""

    if not wall or not cmds.objExists(wall):
        return "", "Could not build the cyclorama helper."

    try:
        cmds.parent(wall, render_root)
    except Exception:
        pass

    wall_shape = (cmds.listRelatives(wall, shapes=True, fullPath=True) or [""])[0]
    if wall_shape:
        for attr_name, value in (("doubleSided", 1), ("castsShadows", 0), ("receiveShadows", 0)):
            try:
                if cmds.attributeQuery(attr_name, node=wall_shape, exists=True):
                    cmds.setAttr("{0}.{1}".format(wall_shape, attr_name), value)
            except Exception:
                pass
        try:
            if not cmds.objExists(SCENE_HELPERS_INFINITY_WALL_MAT_NAME):
                mat = cmds.shadingNode("lambert", asShader=True, name=SCENE_HELPERS_INFINITY_WALL_MAT_NAME)
                try:
                    cmds.setAttr(mat + ".color", 0.965, 0.965, 0.965, type="double3")
                    cmds.setAttr(mat + ".diffuse", 0.9)
                except Exception:
                    pass
                sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=SCENE_HELPERS_INFINITY_WALL_SG_NAME)
                cmds.connectAttr(mat + ".outColor", sg + ".surfaceShader", force=True)
            try:
                cmds.setAttr(wall_shape + ".doubleSided", 1)
            except Exception:
                pass
            cmds.sets(wall_shape, edit=True, forceElement=SCENE_HELPERS_INFINITY_WALL_SG_NAME)
        except Exception:
            pass
    try:
        cmds.xform(wall, worldSpace=True, translation=(center[0], bbox[1], center[2] - max(render_scale * 0.48, 1.0)))
    except Exception:
        pass

    return wall, "Built the cyclorama helper in Python."


def _apply_scene_helpers_render_environment(camera_height_offset=0.0, camera_dolly_offset=0.0):
    if not MAYA_AVAILABLE:
        return False, "This tool only works inside Maya."
    bbox, target_nodes = _scene_helpers_focus_bbox()
    if not bbox:
        return False, "Select a character or open a scene with visible geometry first."

    center = _center_from_bbox(bbox)
    span = _span_from_bbox(bbox)
    render_scale = max(span * DEFAULT_RENDER_ENV_SCALE_MULTIPLIER, 10.0)
    height_span = max(bbox[4] - bbox[1], 1.0)
    # Keep the default helper cameras tight around the character.
    # Students can dolly out manually if a specific shot needs more room.
    camera_distance = 20.0

    _delete_existing_scene_helpers()
    root_group = _ensure_scene_helpers_root()

    render_root = cmds.createNode("transform", name=SCENE_HELPERS_RENDER_ROOT_NAME, parent=root_group)
    camera_root = cmds.createNode("transform", name=SCENE_HELPERS_CAMERA_ROOT_NAME, parent=render_root)
    light_root = cmds.createNode("transform", name=SCENE_HELPERS_LIGHT_ROOT_NAME, parent=render_root)

    infinity_wall, infinity_wall_message = _create_scene_helpers_cyclorama(render_root, center, bbox, render_scale)

    camera_specs = _scene_helpers_camera_specs(height_span, camera_distance)
    created_cameras = {}
    created_bookmarks = []
    for key, (offset, focal_length) in camera_specs.items():
        camera_name = SCENE_HELPERS_CAMERA_NAMES[key]
        adjusted_offset = _scene_helpers_camera_offset_vector(offset, camera_height_offset, camera_dolly_offset)
        camera_transform, camera_shape = _make_camera(camera_name, center, adjusted_offset, focal_length=focal_length)
        if camera_transform:
            cmds.parent(camera_transform, camera_root)
            _look_at(camera_transform, center)
            try:
                cmds.setAttr(camera_shape + ".renderable", 1)
            except Exception:
                pass
            created_cameras[key] = camera_transform
            bookmark_name = _create_scene_helpers_bookmark(camera_transform, SCENE_HELPERS_BOOKMARK_NAMES[key])
            if bookmark_name:
                created_bookmarks.append(bookmark_name)

    light_transform, light_shape, light_mode = _create_scene_helpers_sky_light(light_root, center, render_scale)
    created_lights = [light_transform] if light_transform else []

    hold_utils._set_string_attr(render_root, "sceneHelpersTarget", "|".join(target_nodes))
    hold_utils._set_string_attr(render_root, "sceneHelpersCameras", json.dumps(list(created_cameras.values())))
    hold_utils._set_string_attr(render_root, "sceneHelpersCameraMap", json.dumps(created_cameras))
    hold_utils._set_string_attr(render_root, "sceneHelpersBookmarks", json.dumps(created_bookmarks))
    hold_utils._set_string_attr(render_root, "sceneHelpersLights", json.dumps(created_lights))
    hold_utils._set_string_attr(render_root, "sceneHelpersLightMode", light_mode)
    hold_utils._set_string_attr(render_root, SCENE_HELPERS_CYCLORAMA_ATTR, infinity_wall or "")
    hold_utils._set_string_attr(render_root, "sceneHelpersInfinityWall", infinity_wall or "")
    hold_utils._set_string_attr(render_root, "sceneHelpersScale", "{0:.3f}".format(render_scale))
    hold_utils._set_string_attr(render_root, "sceneHelpersCenter", json.dumps(center))
    for attr_name, value in (
        (SCENE_HELPERS_CAMERA_HEIGHT_OFFSET_ATTR, float(camera_height_offset)),
        (SCENE_HELPERS_CAMERA_DOLLY_OFFSET_ATTR, float(camera_dolly_offset)),
        (SCENE_HELPERS_CAMERA_DISTANCE_ATTR, float(camera_distance)),
        (SCENE_HELPERS_HEIGHT_SPAN_ATTR, float(height_span)),
    ):
        try:
            if cmds.attributeQuery(attr_name, node=render_root, exists=True):
                cmds.setAttr("{0}.{1}".format(render_root, attr_name), value)
            else:
                cmds.addAttr(render_root, longName=attr_name, attributeType="double")
                cmds.setAttr("{0}.{1}".format(render_root, attr_name), value)
        except Exception:
            pass

    try:
        cmds.select(clear=True)
    except Exception:
        pass

    light_message = "Arnold sky dome" if light_mode == "arnold_skydome" else "fallback directional light"
    message = "Set up render environment for {0} target object(s): cameras, the cyclorama helper, and {1}.".format(len(target_nodes), light_message)
    if infinity_wall_message:
        message = "{0} {1}".format(message, infinity_wall_message)
    return True, message


class MayaTimingToolsController(object):
    def __init__(self):
        self.auto_snap_enabled = _option_var_bool(AUTO_SNAP_OPTION, DEFAULT_AUTO_SNAP)
        self.auto_key_enabled = _current_auto_key_state()
        self._last_time_unit = _current_time_unit()
        self._idle_script_job_id = None
        self.status_callback = None
        self.last_render_camera_preset = "perspective"
        self.scene_helpers_camera_height_offset = 0.0
        self.scene_helpers_camera_dolly_offset = 0.0
        self._install_idle_watch()

    def reset_scene_helpers_camera_offsets(self):
        self.scene_helpers_camera_height_offset = 0.0
        self.scene_helpers_camera_dolly_offset = 0.0
        return True, "Reset render camera offsets to zero."

    def set_status_callback(self, callback):
        self.status_callback = callback

    def shutdown(self):
        self._remove_idle_watch()

    def _emit_status(self, message, success=True):
        if self.status_callback:
            try:
                self.status_callback(message, success)
            except Exception:
                pass

    def _remove_idle_watch(self):
        if not cmds:
            self._idle_script_job_id = None
            return
        if self._idle_script_job_id is not None:
            try:
                cmds.scriptJob(kill=self._idle_script_job_id, force=True)
            except Exception:
                pass
        self._idle_script_job_id = None

    def _install_idle_watch(self):
        if not cmds or not self.auto_snap_enabled:
            return
        self._remove_idle_watch()
        try:
            self._idle_script_job_id = cmds.scriptJob(event=["idle", self._on_idle], protected=True)
        except Exception:
            self._idle_script_job_id = None

    def _on_idle(self, *_args):
        if not self.auto_snap_enabled or not cmds:
            return
        current_unit = _current_time_unit()
        if current_unit == self._last_time_unit:
            return
        self._last_time_unit = current_unit
        success, message = self.snap_current_targets()
        self._emit_status(message, success)

    def set_auto_snap_enabled(self, enabled):
        enabled = bool(enabled)
        self.auto_snap_enabled = enabled
        _save_option_var_bool(AUTO_SNAP_OPTION, enabled)
        self._last_time_unit = _current_time_unit()
        if enabled:
            self._install_idle_watch()
            return True, "Auto Snap To Frames is on."
        self._remove_idle_watch()
        return True, "Auto Snap To Frames is off."

    def set_auto_key_enabled(self, enabled):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        enabled = bool(enabled)
        try:
            cmds.autoKeyframe(state=enabled)
        except Exception as exc:
            self.auto_key_enabled = _current_auto_key_state()
            return False, "Could not change Auto Key: {0}".format(exc)
        self.auto_key_enabled = enabled
        return True, "Auto Key is {0}.".format("on" if enabled else "off")

    def snap_current_targets(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes = _selected_transform_nodes()
        scope_label = "selected controls"
        if not nodes:
            nodes = _scene_keyed_transforms()
            scope_label = "all keyed controls"
        if not nodes:
            return False, "There are no keyed controls to snap."

        total_keys = 0
        changed_keys = 0
        changed_nodes = 0
        for node_name in nodes:
            node_changed = False
            keyable_attrs = cmds.listAttr(node_name, keyable=True) or []
            for attr_name in keyable_attrs:
                times = cmds.keyframe(node_name, attribute=attr_name, query=True, timeChange=True) or []
                if not times:
                    continue
                total_keys += len(times)
                changed = _snap_curve_times(node_name, attr_name)
                if changed:
                    node_changed = True
                    changed_keys += changed
            if node_changed:
                changed_nodes += 1

        if not changed_keys:
            return True, "All snapped keys were already on whole frames."
        return True, "Snapped {0} key group(s) across {1} {2}.".format(changed_keys, changed_nodes, scope_label)

    def apply_game_animation_mode(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        try:
            cmds.currentUnit(time=DEFAULT_TIME_UNIT)
        except Exception as exc:
            return False, "Could not set the scene to 30 fps: {0}".format(exc)

        try:
            cmds.playbackOptions(edit=True, playbackSpeed=DEFAULT_PLAYBACK_SPEED)
        except Exception as exc:
            return False, "Could not set playback to real-time: {0}".format(exc)

        try:
            cmds.autoSave(enable=True, limitBackups=True, maxBackups=DEFAULT_MAX_BACKUPS)
        except Exception as exc:
            return False, "Could not enable autosave backups: {0}".format(exc)

        active_panels = 0
        _ensure_cgab_blast_panel_opt_change_callback()
        for panel_name in _all_model_panels():
            try:
                cmds.modelEditor(panel_name, edit=True, activeView=True)
                active_panels += 1
            except Exception:
                pass

        self._last_time_unit = _current_time_unit()
        message = "Game Animation Mode is on. Scene set to 30 fps, real-time playback, autosave, and {0} active viewport(s).".format(active_panels)
        self._emit_status(message, True)
        return True, message

    def setup_render_environment(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        self.reset_scene_helpers_camera_offsets()
        success, message = _apply_scene_helpers_render_environment(
            camera_height_offset=self.scene_helpers_camera_height_offset,
            camera_dolly_offset=self.scene_helpers_camera_dolly_offset,
        )
        if success:
            self.last_render_camera_preset = "perspective"
            preset_success, preset_message = _apply_scene_helpers_camera_preset("perspective")
            if preset_success:
                message = "{0} {1}".format(message, preset_message)
        self._emit_status(message, success)
        return success, message

    def delete_render_environment(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        if not cmds.objExists(SCENE_HELPERS_RENDER_ROOT_NAME) and not cmds.objExists(SCENE_HELPERS_ROOT_NAME):
            self.reset_scene_helpers_camera_offsets()
            self.last_render_camera_preset = "perspective"
            preset_success, preset_message = _apply_scene_helpers_camera_preset("perspective")
            message = "No render environment to delete."
            if preset_success:
                message = "{0} {1}".format(message, preset_message)
            self._emit_status(message, True)
            return True, message
        _delete_existing_scene_helpers()
        self.reset_scene_helpers_camera_offsets()
        self.last_render_camera_preset = "perspective"
        message = "Deleted the render environment."
        preset_success, preset_message = _apply_scene_helpers_camera_preset("perspective")
        if preset_success:
            message = "{0} {1}".format(message, preset_message)
        self._emit_status(message, True)
        return True, message

    def set_scene_helpers_camera_offsets(self, height_offset=None, dolly_offset=None):
        if height_offset is not None:
            self.scene_helpers_camera_height_offset = float(height_offset)
        if dolly_offset is not None:
            self.scene_helpers_camera_dolly_offset = float(dolly_offset)
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        if not cmds.objExists(SCENE_HELPERS_RENDER_ROOT_NAME):
            return True, "Camera offsets saved. Build the render environment to apply them."
        camera_map_payload = ""
        try:
            camera_map_payload = cmds.getAttr(SCENE_HELPERS_RENDER_ROOT_NAME + "." + SCENE_HELPERS_CAMERA_MAP_ATTR)
        except Exception:
            camera_map_payload = ""
        try:
            camera_map = json.loads(camera_map_payload or "{}")
        except Exception:
            camera_map = {}
        height_span = 1.0
        camera_distance = 1.0
        try:
            height_span = float(cmds.getAttr(SCENE_HELPERS_RENDER_ROOT_NAME + "." + SCENE_HELPERS_HEIGHT_SPAN_ATTR))
        except Exception:
            pass
        try:
            camera_distance = float(cmds.getAttr(SCENE_HELPERS_RENDER_ROOT_NAME + "." + SCENE_HELPERS_CAMERA_DISTANCE_ATTR))
        except Exception:
            pass
        try:
            center_payload = cmds.getAttr(SCENE_HELPERS_RENDER_ROOT_NAME + "." + "sceneHelpersCenter")
            center = json.loads(center_payload or "[0,0,0]")
        except Exception:
            center = [0.0, 0.0, 0.0]
        success, message = _apply_scene_helpers_camera_offsets(
            SCENE_HELPERS_RENDER_ROOT_NAME,
            center,
            height_span,
            camera_distance,
            self.scene_helpers_camera_height_offset,
            self.scene_helpers_camera_dolly_offset,
        )
        if success:
            message = "Updated helper cameras: up/down {0:.2f}, in/out {1:.2f}.".format(
                self.scene_helpers_camera_height_offset,
                self.scene_helpers_camera_dolly_offset,
            )
        self._emit_status(message, success)
        return success, message

    def activate_scene_camera_preset(self, preset_key):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        normalized_key = (preset_key or "").strip().lower().replace(" ", "_").replace("-", "_")
        success, message = _apply_scene_helpers_camera_preset(normalized_key)
        if success and (normalized_key in SCENE_HELPERS_CAMERA_NAMES or normalized_key == "perspective"):
            self.last_render_camera_preset = normalized_key
        self._emit_status(message, success)
        return success, message


if QtWidgets:
    if MayaQWidgetDockableMixin is not None:
        _WindowBase = type("MayaTimingToolsWindowBase", (MayaQWidgetDockableMixin, QtWidgets.QDialog), {})
    else:
        _WindowBase = type("MayaTimingToolsWindowBase", (QtWidgets.QDialog,), {})

    class MayaTimingToolsWindow(_WindowBase):
        def __init__(self, controller, parent=None):
            super(MayaTimingToolsWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller
            self.controller.set_status_callback(self._set_status)
            self.setObjectName(WINDOW_OBJECT_NAME)
            self.setWindowTitle("Scene Helpers")
            self.setMinimumSize(420, 220)
            if hasattr(self, "setSizePolicy"):
                self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
            self._build_ui()
            self._sync_from_controller()

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(12, 12, 12, 12)
            main_layout.setSpacing(10)

            intro = QtWidgets.QLabel(
            "Use Auto Key when you want Maya to key changes as you animate. "
            "Use Auto Snap To Frames when keys land between frames after a timing change. "
            "Use Game Animation Mode to prep the scene for 30 fps game animation. "
            "Use Set Up Render Environment to build the cyclorama helper, helper cameras, and a sky dome or fallback light around the selected character."
            )
            intro.setWordWrap(True)
            main_layout.addWidget(intro)

            quick_label = QtWidgets.QLabel("Scene Helpers")
            quick_label.setStyleSheet("font-weight: 600;")
            main_layout.addWidget(quick_label)

            action_row = QtWidgets.QHBoxLayout()
            action_row.setSpacing(8)
            self.auto_key_button = QtWidgets.QToolButton()
            self.auto_key_button.setCheckable(True)
            self.auto_key_button.setChecked(self.controller.auto_key_enabled)
            self.auto_key_button.setText("Auto Key")
            self.auto_key_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            self.auto_key_button.setIcon(_make_key_icon())
            self.auto_key_button.setToolTip(
                "Toggle Maya's Auto Key button on or off. Use this when you want Maya to key changes as you move controls."
            )
            action_row.addWidget(self.auto_key_button, 1)

            self.auto_snap_button = QtWidgets.QToolButton()
            self.auto_snap_button.setCheckable(True)
            self.auto_snap_button.setChecked(self.controller.auto_snap_enabled)
            self.auto_snap_button.setText("Auto Snap To Frames")
            self.auto_snap_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            self.auto_snap_button.setIcon(_make_snap_icon())
            self.auto_snap_button.setToolTip(
                "Keep keyframes snapped to whole frames when the time unit changes. "
                "When this is on, the tool watches for a frame-rate change and snaps the current controls or "
                "keyed scene controls into whole frames."
            )
            action_row.addWidget(self.auto_snap_button, 1)

            self.game_mode_button = QtWidgets.QPushButton("Game Animation Mode")
            self.game_mode_button.setToolTip(
                "Set the scene to 30 fps, real-time playback, autosave with five backups, and mark every viewport "
                "active."
            )
            action_row.addWidget(self.game_mode_button, 1)
            self.render_env_button = QtWidgets.QPushButton("Set Up Render Environment")
            self.render_env_button.setToolTip(
                "Build a first-pass render setup around the selected character or largest visible mesh. "
                "The tool builds the cyclorama helper directly in Python, then adds front, side, and three-quarter cameras, a sky dome when Arnold is available, and camera bookmarks."
            )
            action_row.addWidget(self.render_env_button, 1)
            self.delete_render_env_button = QtWidgets.QPushButton("Delete Render Environment")
            self.delete_render_env_button.setToolTip("Delete the Scene Helpers render environment, including the cameras, cyclorama, sky light, and bookmarks.")
            action_row.addWidget(self.delete_render_env_button, 1)
            main_layout.addLayout(action_row)

            camera_row = QtWidgets.QHBoxLayout()
            camera_row.setSpacing(8)
            camera_row.addWidget(QtWidgets.QLabel("Camera Preset"))
            self.render_preset_combo = QtWidgets.QComboBox()
            self.render_preset_combo.setObjectName("sceneHelpersCameraPresetCombo")
            for preset_key, preset_label in SCENE_HELPERS_CAMERA_PRESET_LABELS.items():
                self.render_preset_combo.addItem(preset_label, preset_key)
            self.render_preset_combo.setToolTip("Pick which helper camera to show in the viewport.")
            camera_row.addWidget(self.render_preset_combo, 1)
            self.render_preset_button = QtWidgets.QPushButton("Switch View")
            self.render_preset_button.setObjectName("sceneHelpersCameraPresetButton")
            self.render_preset_button.setToolTip("Switch the active viewport to the selected helper camera preset.")
            camera_row.addWidget(self.render_preset_button)
            main_layout.addLayout(camera_row)

            offset_row = QtWidgets.QHBoxLayout()
            offset_row.setSpacing(8)
            offset_row.addWidget(QtWidgets.QLabel("Camera Height Offset"))
            self.camera_height_offset_spin = QtWidgets.QDoubleSpinBox()
            self.camera_height_offset_spin.setObjectName("sceneHelpersCameraHeightOffsetSpin")
            self.camera_height_offset_spin.setRange(-100.0, 100.0)
            self.camera_height_offset_spin.setDecimals(2)
            self.camera_height_offset_spin.setSingleStep(0.25)
            self.camera_height_offset_spin.setToolTip("Move all helper cameras up or down together.")
            offset_row.addWidget(self.camera_height_offset_spin)
            offset_row.addWidget(QtWidgets.QLabel("Camera Dolly Offset"))
            self.camera_dolly_offset_spin = QtWidgets.QDoubleSpinBox()
            self.camera_dolly_offset_spin.setObjectName("sceneHelpersCameraDollyOffsetSpin")
            self.camera_dolly_offset_spin.setRange(-100.0, 100.0)
            self.camera_dolly_offset_spin.setDecimals(2)
            self.camera_dolly_offset_spin.setSingleStep(0.25)
            self.camera_dolly_offset_spin.setToolTip("Move the helper cameras closer or farther in their view direction.")
            offset_row.addWidget(self.camera_dolly_offset_spin)
            main_layout.addLayout(offset_row)

            snap_row = QtWidgets.QHBoxLayout()
            snap_row.setSpacing(8)
            self.snap_now_button = QtWidgets.QPushButton("Snap Selected Keys To Frames")
            self.snap_now_button.setToolTip(
                "Snap the currently selected controls to whole frames right now. If nothing is selected, the tool "
                "snaps the keyed controls it can find in the scene."
            )
            snap_row.addWidget(self.snap_now_button, 1)
            main_layout.addLayout(snap_row)

            help_box = QtWidgets.QPlainTextEdit()
            help_box.setReadOnly(True)
            help_box.setPlainText(
                "1. Use Auto Key when you want Maya to key changes as you animate.\n"
                "2. Leave Auto Snap To Frames on if you want the tool to catch timing changes for you.\n"
                "3. If keys are already off-frame, click Snap Selected Keys To Frames.\n"
                "4. If you are setting up a student game shot, click Game Animation Mode.\n"
                "5. Use Set Up Render Environment to build the cyclorama helper, then add the cameras and sky light for the shot.\n"
                "6. Use Delete Render Environment when you want to remove that whole setup again.\n"
                "7. Use Camera Height Offset and Camera Dolly Offset to move all helper cameras up/down or in/out together.\n"
                "8. Use Camera Preset to jump between the Front, Side, and Three Quarter cameras.\n"
                "9. Select controls first when you want the snap to act only on part of the scene."
            )
            help_box.setMaximumHeight(110)
            main_layout.addWidget(help_box)

            self.status_label = QtWidgets.QLabel("Ready.")
            self.status_label.setWordWrap(True)
            main_layout.addWidget(self.status_label)

            footer_layout = QtWidgets.QHBoxLayout()
            self.brand_label = QtWidgets.QLabel('Built by Amir. Follow Amir at <a href="{0}">followamir.com</a>.'.format(FOLLOW_AMIR_URL))
            self.brand_label.setOpenExternalLinks(False)
            self.brand_label.linkActivated.connect(self._open_follow_url)
            self.brand_label.setWordWrap(True)
            footer_layout.addWidget(self.brand_label, 1)
            self.version_label = QtWidgets.QLabel("Version 0.2 BETA")
            footer_layout.addWidget(self.version_label)
            self.donate_button = QtWidgets.QPushButton("Donate")
            _style_donate_button(self.donate_button)
            self.donate_button.clicked.connect(self._open_donate_url)
            footer_layout.addWidget(self.donate_button)
            main_layout.addLayout(footer_layout)

            self.auto_key_button.toggled.connect(self._toggle_auto_key)
            self.auto_snap_button.toggled.connect(self._toggle_auto_snap)
            self.snap_now_button.clicked.connect(self._snap_now)
            self.game_mode_button.clicked.connect(self._game_mode)
            self.render_env_button.clicked.connect(self._render_environment)
            self.delete_render_env_button.clicked.connect(self._delete_render_environment)
            self.render_preset_button.clicked.connect(self._go_to_render_camera)
            self.camera_height_offset_spin.valueChanged.connect(self._camera_offsets_changed)
            self.camera_dolly_offset_spin.valueChanged.connect(self._camera_offsets_changed)

        def _sync_from_controller(self):
            self.auto_key_button.blockSignals(True)
            self.auto_key_button.setChecked(bool(self.controller.auto_key_enabled))
            self.auto_key_button.blockSignals(False)
            self.auto_snap_button.blockSignals(True)
            self.auto_snap_button.setChecked(bool(self.controller.auto_snap_enabled))
            self.auto_snap_button.blockSignals(False)
            self.render_preset_combo.blockSignals(True)
            current_key = getattr(self.controller, "last_render_camera_preset", "front")
            target_index = self.render_preset_combo.findData(current_key)
            if target_index < 0:
                target_index = 0
            self.render_preset_combo.setCurrentIndex(target_index)
            self.render_preset_combo.blockSignals(False)
            self.camera_height_offset_spin.blockSignals(True)
            self.camera_height_offset_spin.setValue(float(getattr(self.controller, "scene_helpers_camera_height_offset", 0.0)))
            self.camera_height_offset_spin.blockSignals(False)
            self.camera_dolly_offset_spin.blockSignals(True)
            self.camera_dolly_offset_spin.setValue(float(getattr(self.controller, "scene_helpers_camera_dolly_offset", 0.0)))
            self.camera_dolly_offset_spin.blockSignals(False)

        def _toggle_auto_key(self, enabled):
            success, message = self.controller.set_auto_key_enabled(enabled)
            if not success:
                self.auto_key_button.blockSignals(True)
                self.auto_key_button.setChecked(bool(self.controller.auto_key_enabled))
                self.auto_key_button.blockSignals(False)
            self._set_status(message, success)

        def _toggle_auto_snap(self, enabled):
            success, message = self.controller.set_auto_snap_enabled(enabled)
            self._set_status(message, success)

        def _snap_now(self):
            success, message = self.controller.snap_current_targets()
            self._set_status(message, success)

        def _game_mode(self):
            success, message = self.controller.apply_game_animation_mode()
            self._set_status(message, success)

        def _render_environment(self):
            success, message = self.controller.setup_render_environment()
            self._sync_from_controller()
            self._set_status(message, success)

        def _delete_render_environment(self):
            if QtWidgets:
                delete_result = QtWidgets.QMessageBox.question(
                    self,
                    "Delete Render Environment",
                    "Delete the Scene Helpers render environment? This removes the cameras, cyclorama, sky light, and bookmarks.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                    QtWidgets.QMessageBox.No,
                )
                if delete_result != QtWidgets.QMessageBox.Yes:
                    self._set_status("Kept the render environment.", True)
                    return
            success, message = self.controller.delete_render_environment()
            self._sync_from_controller()
            self._set_status(message, success)

        def _go_to_render_camera(self):
            preset_key = self.render_preset_combo.currentData() or "front"
            success, message = self.controller.activate_scene_camera_preset(preset_key)
            self._set_status(message, success)

        def _camera_offsets_changed(self, *_args):
            success, message = self.controller.set_scene_helpers_camera_offsets(
                height_offset=self.camera_height_offset_spin.value(),
                dolly_offset=self.camera_dolly_offset_spin.value(),
            )
            self._set_status(message, success)

        def _set_status(self, message, success=True):
            self.status_label.setText(message)
            palette = self.status_label.palette()
            role = self.status_label.foregroundRole()
            palette.setColor(role, QtGui.QColor("#24A148" if success else "#DA1E28"))
            self.status_label.setPalette(palette)

        def _open_follow_url(self, url=None):
            if _open_external_url(url or FOLLOW_AMIR_URL):
                self._set_status("Opened followamir.com.", True)
            else:
                self._set_status("Could not open followamir.com from this Maya session.", False)

        def _open_donate_url(self):
            if DONATE_URL and _open_external_url(DONATE_URL):
                self._set_status("Opened the Donate link.", True)
            else:
                self._set_status("Could not open the Donate link from this Maya session.", False)

        def closeEvent(self, event):
            try:
                self.controller.shutdown()
            except Exception:
                pass
            try:
                super(MayaTimingToolsWindow, self).closeEvent(event)
            except TypeError:
                QtWidgets.QDialog.closeEvent(self, event)


def _close_existing_window():
    global GLOBAL_WINDOW
    if GLOBAL_WINDOW is not None:
        try:
            GLOBAL_WINDOW.close()
        except Exception:
            pass
        GLOBAL_WINDOW = None


def launch_maya_timing_tools(dock=False):
    global GLOBAL_CONTROLLER
    global GLOBAL_WINDOW
    if not MAYA_AVAILABLE:
        raise RuntimeError("maya_timing_tools.launch_maya_timing_tools() must run inside Autodesk Maya.")
    if not QtWidgets:
        raise RuntimeError("maya_timing_tools.launch_maya_timing_tools() needs PySide inside Maya.")
    _close_existing_window()
    GLOBAL_CONTROLLER = MayaTimingToolsController()
    GLOBAL_WINDOW = MayaTimingToolsWindow(GLOBAL_CONTROLLER, parent=_maya_main_window())
    if dock and hasattr(GLOBAL_WINDOW, "show"):
        try:
            GLOBAL_WINDOW.show(dockable=True, floating=True, area="right")
        except Exception:
            GLOBAL_WINDOW.show()
    else:
        GLOBAL_WINDOW.show()
    return GLOBAL_WINDOW


__all__ = [
    "MayaTimingToolsController",
    "MayaTimingToolsWindow",
    "launch_maya_timing_tools",
]
