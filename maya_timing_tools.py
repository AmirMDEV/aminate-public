from __future__ import absolute_import, division, print_function

import collections
import json
import math
import os

import maya_contact_hold as hold_utils
import maya_crash_recovery as crash_recovery

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
STUDENT_TIMELINE_BAR_OBJECT_NAME = "studentCoreTimelineButtonBarWindow"
STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME = STUDENT_TIMELINE_BAR_OBJECT_NAME + "WorkspaceControl"
AUTO_SNAP_OPTION = "AmirMayaAnimWorkflowAutoSnapToFrames"
ANIMATION_LAYER_TINT_OPTION = "AmirMayaAnimWorkflowAnimationLayerTint"
GAME_ANIMATION_MODE_OPTION = "AmirMayaAnimWorkflowGameAnimationMode"
DEFAULT_AUTO_SNAP = True
DEFAULT_ANIMATION_LAYER_TINT = True
DEFAULT_GAME_ANIMATION_MODE = False
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
ANIMATION_LAYER_TINT_PALETTE = (
    "#EF6F6C",
    "#55CBCD",
    "#F6C85F",
    "#B86BFF",
    "#7BD88F",
    "#72B7F2",
    "#F4A261",
    "#2A9D8F",
    "#EF476F",
    "#06D6A0",
    "#577590",
    "#CDB4DB",
)

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
STUDENT_CORE_TEMP_POPUP_OBJECT = "studentCoreTimelineTempButtons"
STUDENT_CORE_TOOLS = (
    {
        "command": "nudge_left",
        "label": "-1",
        "group": "Timing",
        "color": "#EF6F6C",
        "glyph": "left",
        "tooltip": "Move selected Graph Editor keys, or all keys on selected controls, one frame earlier.",
    },
    {
        "command": "nudge_right",
        "label": "+1",
        "group": "Timing",
        "color": "#55CBCD",
        "glyph": "right",
        "tooltip": "Move selected Graph Editor keys, or all keys on selected controls, one frame later.",
    },
    {
        "command": "insert_inbetween",
        "label": "In",
        "group": "Keys",
        "color": "#F6C85F",
        "glyph": "diamond",
        "tooltip": "Insert an inbetween key on the current frame for selected animated controls.",
    },
    {
        "command": "remove_current",
        "label": "Cut",
        "group": "Keys",
        "color": "#B86BFF",
        "glyph": "cut",
        "tooltip": "Remove keys on the current frame for selected animated controls.",
    },
    {
        "command": "reset_pose",
        "label": "Zero",
        "group": "Pose",
        "color": "#7BD88F",
        "glyph": "zero",
        "tooltip": "Reset selected controls to translate 0, rotate 0, scale 1.",
    },
    {
        "command": "bake_twos",
        "label": "2s",
        "group": "Bake",
        "color": "#72B7F2",
        "glyph": "bars",
        "tooltip": "Bake selected controls over the playback range every 2 frames.",
    },
    {
        "command": "select_animated",
        "label": "Anim",
        "group": "Select",
        "color": "#95E6E8",
        "glyph": "dots",
        "tooltip": "Select every transform in the scene with animation curves.",
    },
    {
        "command": "clean_static",
        "label": "Clean",
        "group": "Clean",
        "color": "#B9E769",
        "glyph": "clean",
        "tooltip": "Delete static animation curves on selected controls when every keyed value is the same.",
    },
)
WORKFLOW_BAR_TOOLS = (
    {"command": "workflow_quick_start", "tab": "quick_start", "label": "QS", "color": "#9AA4FF", "glyph": "guide", "tooltip": "Quick Start: plain-language guide for every tab, with beginner steps for picking correct tool."},
    {"command": "workflow_scene_helpers", "tab": "scene_helpers", "label": "SH", "color": "#4CC9F0", "glyph": "scene", "tooltip": "Scene Helpers: Auto Key, snap keys to whole frames, game animation mode, texture reload, autosave recovery, render cameras."},
    {"command": "workflow_reference_manager", "tab": "reference_manager", "label": "PK", "color": "#F4A261", "glyph": "package", "tooltip": "Reference Manager: save current Maya scene, collect references, textures, audio, caches, create ready-to-move zip."},
    {"command": "workflow_dynamic_parenting", "tab": "dynamic_parenting", "label": "DP", "color": "#E76F51", "glyph": "parent", "tooltip": "Dynamic Parenting: switch props or controls between hand, gun, world, or mixed parents without visible pop."},
    {"command": "workflow_hand_foot_hold", "tab": "hand_foot_hold", "label": "HF", "color": "#2A9D8F", "glyph": "hold", "tooltip": "Hand / Foot Hold: keep chosen hand or foot planted on selected world axes through chosen frame range."},
    {"command": "workflow_surface_contact", "tab": "surface_contact", "label": "SC", "color": "#00B4D8", "glyph": "surface", "tooltip": "Surface Contact: live clamp chosen control to chosen mesh surface, useful for hands, feet, props, contact poses."},
    {"command": "workflow_dynamic_pivot", "tab": "dynamic_pivot", "label": "PV", "color": "#FFD166", "glyph": "pivot", "tooltip": "Dynamic Pivot: create temporary pivot marker so selected object can rotate around custom point."},
    {"command": "workflow_ikfk", "tab": "ikfk", "label": "IK", "color": "#118AB2", "glyph": "ikfk", "tooltip": "Universal IK/FK: detect arm or leg controls, save switch setup, match pose while switching IK to FK or FK to IK."},
    {"command": "workflow_retarget", "tab": "controls_retargeter", "label": "RT", "color": "#EF476F", "glyph": "retarget", "tooltip": "Controls Retargeter: pair source controls to target controls, bake animation onto target controls for editable retarget."},
    {"command": "workflow_picker", "tab": "control_picker", "label": "CP", "color": "#06D6A0", "glyph": "picker", "tooltip": "Control Picker: scan rig controls, group body plus face areas, sync picker selection with Maya selection."},
    {"command": "workflow_pencil", "tab": "animators_pencil", "label": "PN", "color": "#90BE6D", "glyph": "pencil", "tooltip": "Animators Pencil: draw notes, arcs, frame markers, ghosts, retiming marks as scene-native Maya curves or text."},
    {"command": "workflow_onion", "tab": "onion_skin", "label": "OS", "color": "#B8F2E6", "glyph": "onion", "tooltip": "Onion Skin: create 3D ghosts for past plus future poses to judge spacing, arcs, timing."},
    {"command": "workflow_rotation", "tab": "rotation_doctor", "label": "RD", "color": "#F77F00", "glyph": "rotation", "tooltip": "Rotation Doctor: inspect selected animated rotations, flag flips or gimbal risk, suggest safest fix."},
    {"command": "workflow_skin", "tab": "skinning_cleanup", "label": "SK", "color": "#CDB4DB", "glyph": "skin", "tooltip": "Skinning Cleanup: check skinned mesh scale problems, make clean replacement copy while preserving skin weights."},
    {"command": "workflow_rig_scale", "tab": "rig_scale", "label": "RS", "color": "#A7C957", "glyph": "scale", "tooltip": "Rig Scale: build export-safe scaled copy of character rig for Unreal or game-engine handoff."},
    {"command": "workflow_video", "tab": "video_reference", "label": "VR", "color": "#577590", "glyph": "video", "tooltip": "Video Reference: place video or image reference cards in Maya scene for timing, tracing, annotation."},
    {"command": "workflow_timeline", "tab": "timeline_notes", "label": "TN", "color": "#F2CC8F", "glyph": "notes", "tooltip": "Timeline Notes: add colored timeline ranges with readable notes for shot review while scrubbing."},
)

GLOBAL_CONTROLLER = None
GLOBAL_WINDOW = None
GLOBAL_TIMELINE_BAR_CONTROLLER = None
GLOBAL_TIMELINE_BAR_WINDOW = None

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


def _stable_palette_color(name):
    label = _short_name(name) or "Base Animation"
    total = sum(ord(char) for char in label)
    return ANIMATION_LAYER_TINT_PALETTE[total % len(ANIMATION_LAYER_TINT_PALETTE)]


def _maya_color_index_to_hex(index_value):
    maya_colors = (
        "#9B9B9B", "#000000", "#3F3F3F", "#666666", "#A6A6A6", "#600000", "#000060", "#004060",
        "#006000", "#600060", "#402000", "#602000", "#404000", "#204000", "#004020", "#004040",
        "#002040", "#400040", "#600040", "#400000", "#604000", "#606000", "#406000", "#006020",
        "#006060", "#004060", "#000060", "#402060", "#602060", "#600020", "#FF0000", "#00FF00",
    )
    try:
        index = int(index_value)
    except Exception:
        return ""
    if index < 0:
        return ""
    return maya_colors[index % len(maya_colors)]


def _animation_layer_color(layer_name):
    if not cmds or not layer_name or not cmds.objExists(layer_name):
        return _stable_palette_color(layer_name)
    for attr_name in ("color", "displayColor", "ghostColor"):
        try:
            if not cmds.attributeQuery(attr_name, node=layer_name, exists=True):
                continue
            value = cmds.getAttr("{0}.{1}".format(layer_name, attr_name))
            if isinstance(value, (list, tuple)):
                if value and isinstance(value[0], (list, tuple)) and len(value[0]) >= 3:
                    r_value, g_value, b_value = value[0][:3]
                    return "#{0:02X}{1:02X}{2:02X}".format(
                        max(0, min(255, int(float(r_value) * 255.0))),
                        max(0, min(255, int(float(g_value) * 255.0))),
                        max(0, min(255, int(float(b_value) * 255.0))),
                    )
                if len(value) >= 3:
                    return "#{0:02X}{1:02X}{2:02X}".format(
                        max(0, min(255, int(float(value[0]) * 255.0))),
                        max(0, min(255, int(float(value[1]) * 255.0))),
                        max(0, min(255, int(float(value[2]) * 255.0))),
                    )
            color_hex = _maya_color_index_to_hex(value)
            if color_hex:
                return color_hex
        except Exception:
            continue
    return _stable_palette_color(layer_name)


def _animation_layer_is_selected(layer_name):
    if not cmds or not layer_name or not cmds.objExists(layer_name):
        return False
    for flag_name in ("selected", "preferred"):
        try:
            if cmds.animLayer(layer_name, query=True, **{flag_name: True}):
                return True
        except Exception:
            continue
    return False


def _active_animation_layer_name():
    if not cmds:
        return ""
    try:
        layers = cmds.ls(type="animLayer") or []
    except Exception:
        layers = []
    if not layers:
        return ""
    for layer_name in layers:
        if _animation_layer_is_selected(layer_name):
            return layer_name
    for layer_name in layers:
        if _short_name(layer_name).lower() not in ("baseanimation", "base animation"):
            return layer_name
    return layers[0]


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


def _scene_texture_node_specs():
    specs = [("file", "fileTextureName")]
    if cmds:
        try:
            if "aiImage" in (cmds.allNodeTypes() or []):
                specs.append(("aiImage", "filename"))
        except Exception:
            pass
    return tuple(specs)


def _workspace_sourceimages_root():
    if not cmds:
        return ""
    workspace_root = cmds.workspace(query=True, rootDirectory=True) or ""
    if not workspace_root:
        return ""
    try:
        source_rule = cmds.workspace(fileRuleEntry="sourceImages") or ""
    except Exception:
        source_rule = ""
    if source_rule:
        if os.path.isabs(source_rule):
            return os.path.normpath(source_rule)
        return os.path.normpath(os.path.join(workspace_root, source_rule))
    return os.path.normpath(os.path.join(workspace_root, "sourceimages"))


def _texture_search_roots():
    if not cmds:
        return []
    roots = []
    workspace_root = cmds.workspace(query=True, rootDirectory=True) or ""
    scene_name = cmds.file(query=True, sceneName=True) or ""
    scene_dir = os.path.dirname(scene_name) if scene_name else ""
    sourceimages_root = _workspace_sourceimages_root()
    for root_path in (
        sourceimages_root,
        workspace_root,
        scene_dir,
        os.path.join(workspace_root, "textures") if workspace_root else "",
        os.path.join(workspace_root, "images") if workspace_root else "",
        os.path.join(scene_dir, "textures") if scene_dir else "",
        os.path.join(scene_dir, "images") if scene_dir else "",
    ):
        if not root_path:
            continue
        normalized = os.path.normpath(root_path)
        if os.path.isdir(normalized) and normalized not in roots:
            roots.append(normalized)
    return roots


def _build_texture_basename_index(search_roots):
    basename_map = collections.defaultdict(list)
    for root_path in search_roots or []:
        try:
            for current_root, dir_names, file_names in os.walk(root_path):
                dir_names[:] = [name for name in dir_names if not name.startswith(".")]
                for file_name in file_names:
                    key_name = file_name.lower()
                    full_path = os.path.normpath(os.path.join(current_root, file_name))
                    basename_map[key_name].append(full_path)
        except Exception:
            continue
    return dict(basename_map)


def _texture_refresh_mel_hooks(node_name):
    if not mel or not node_name:
        return
    safe_node_name = node_name.replace("\\", "\\\\").replace('"', '\\"')
    if cmds and cmds.objExists(node_name):
        try:
            mel.eval(
                'if (`exists updateFileNodeSwatch`) {{ catchQuiet(`updateFileNodeSwatch "{0}"`); }}'.format(
                    safe_node_name
                )
            )
        except Exception:
            pass
    try:
        mel.eval('if (`exists generateAllUvTilePreviews`) { catchQuiet(`generateAllUvTilePreviews`); }')
    except Exception:
        pass


def _refresh_texture_node(node_name, attr_name, texture_path):
    if not cmds or not node_name or not attr_name or not texture_path:
        return False
    if not cmds.objExists(node_name) or not cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return False
    try:
        if cmds.attributeQuery("disableFileLoad", node=node_name, exists=True):
            cmds.setAttr(node_name + ".disableFileLoad", 0)
    except Exception:
        pass
    try:
        cmds.setAttr(node_name + "." + attr_name, texture_path, type="string")
    except Exception:
        return False
    try:
        cmds.dgdirty(node_name)
    except Exception:
        pass
    _texture_refresh_mel_hooks(node_name)
    return True


def _resolve_texture_path(current_path, basename_map, search_roots):
    normalized_path = os.path.normpath(current_path) if current_path else ""
    if normalized_path and os.path.exists(normalized_path):
        return normalized_path, False
    base_name = os.path.basename(current_path or "").strip()
    if not base_name:
        return "", False
    key_name = base_name.lower()
    matches = list(basename_map.get(key_name) or [])
    if len(matches) == 1:
        return matches[0], True
    direct_candidates = []
    for root_path in search_roots or []:
        for subfolder in ("", "sourceimages", "textures", "images", os.path.join("sourceimages", "textures")):
            candidate = os.path.normpath(os.path.join(root_path, subfolder, base_name))
            if os.path.exists(candidate):
                direct_candidates.append(candidate)
    direct_candidates = _dedupe_preserve_order(direct_candidates)
    if len(direct_candidates) == 1:
        return direct_candidates[0], True
    return "", False


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


def _make_student_core_icon(color_hex, glyph):
    if not QtGui:
        return QtGui.QIcon() if QtGui else None
    pixmap = QtGui.QPixmap(30, 30)
    pixmap.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(pixmap)
    try:
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        color = QtGui.QColor(color_hex or "#55CBCD")
        darker = QtGui.QColor(color).darker(145)
        light = QtGui.QColor("#F1F3F4")
        painter.setPen(QtGui.QPen(darker, 2))
        painter.setBrush(color)
        painter.drawRoundedRect(4, 4, 22, 22, 5, 5)
        painter.setPen(QtGui.QPen(QtGui.QColor("#2C2C2C"), 2))
        painter.setBrush(QtGui.QColor("#2C2C2C"))
        if glyph == "left":
            points = [QtCore.QPoint(18, 9), QtCore.QPoint(10, 15), QtCore.QPoint(18, 21)]
            painter.drawPolygon(QtGui.QPolygon(points))
        elif glyph == "right":
            points = [QtCore.QPoint(12, 9), QtCore.QPoint(20, 15), QtCore.QPoint(12, 21)]
            painter.drawPolygon(QtGui.QPolygon(points))
        elif glyph == "diamond":
            points = [QtCore.QPoint(15, 7), QtCore.QPoint(23, 15), QtCore.QPoint(15, 23), QtCore.QPoint(7, 15)]
            painter.drawPolygon(QtGui.QPolygon(points))
        elif glyph == "cut":
            painter.drawLine(10, 9, 20, 21)
            painter.drawLine(20, 9, 10, 21)
        elif glyph == "zero":
            painter.setPen(QtGui.QPen(light, 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(10, 9, 10, 12)
        elif glyph == "bars":
            painter.drawRect(9, 9, 3, 12)
            painter.drawRect(15, 9, 3, 12)
            painter.drawRect(21, 9, 3, 12)
        elif glyph == "dots":
            painter.drawEllipse(9, 10, 4, 4)
            painter.drawEllipse(17, 10, 4, 4)
            painter.drawEllipse(13, 18, 4, 4)
        elif glyph == "clean":
            painter.setPen(QtGui.QPen(light, 2))
            painter.drawLine(9, 20, 20, 9)
            painter.drawLine(16, 20, 21, 15)
        elif glyph == "guide":
            painter.setPen(QtGui.QPen(QtGui.QColor("#2C2C2C"), 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(10, 7, 10, 16)
            painter.drawLine(13, 11, 18, 11)
            painter.drawLine(13, 15, 18, 15)
            painter.drawLine(13, 19, 17, 19)
        elif glyph == "scene":
            painter.drawRect(8, 13, 14, 8)
            painter.drawEllipse(11, 9, 8, 6)
            painter.setBrush(light)
            painter.drawEllipse(13, 15, 4, 4)
        elif glyph == "package":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(8, 11, 14, 10)
            painter.drawLine(8, 11, 15, 7)
            painter.drawLine(22, 11, 15, 7)
            painter.drawLine(15, 7, 15, 17)
        elif glyph == "parent":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(8, 8, 6, 6)
            painter.drawEllipse(17, 17, 6, 6)
            painter.drawLine(14, 14, 17, 17)
        elif glyph == "hold":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(8, 12, 6, 9)
            painter.drawEllipse(15, 10, 7, 11)
            painter.drawLine(8, 22, 22, 22)
        elif glyph == "surface":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawArc(6, 14, 18, 8, 0, 180 * 16)
            painter.setBrush(light)
            painter.drawEllipse(13, 9, 5, 5)
            painter.drawLine(15, 14, 15, 20)
        elif glyph == "pivot":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(9, 9, 12, 12)
            painter.drawLine(15, 7, 15, 23)
            painter.drawLine(7, 15, 23, 15)
            painter.drawArc(8, 8, 14, 14, 35 * 16, 230 * 16)
        elif glyph == "ikfk":
            painter.setBrush(light)
            painter.drawEllipse(7, 18, 4, 4)
            painter.drawEllipse(13, 11, 4, 4)
            painter.drawEllipse(20, 18, 4, 4)
            painter.drawLine(11, 18, 14, 14)
            painter.drawLine(17, 14, 20, 18)
        elif glyph == "retarget":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(7, 9, 6, 6)
            painter.drawEllipse(18, 16, 6, 6)
            painter.drawLine(13, 12, 19, 17)
            painter.drawLine(19, 17, 16, 17)
            painter.drawLine(19, 17, 18, 14)
        elif glyph == "picker":
            painter.setBrush(light)
            for x_value in (8, 15, 22):
                for y_value in (9, 16):
                    painter.drawEllipse(x_value - 2, y_value - 2, 4, 4)
            painter.setBrush(QtGui.QColor("#2C2C2C"))
            points = [QtCore.QPoint(12, 19), QtCore.QPoint(21, 22), QtCore.QPoint(16, 24)]
            painter.drawPolygon(QtGui.QPolygon(points))
        elif glyph == "pencil":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawLine(9, 21, 20, 10)
            painter.drawLine(12, 23, 23, 12)
            painter.drawLine(20, 10, 23, 12)
            painter.drawLine(9, 21, 12, 23)
        elif glyph == "onion":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.setPen(QtGui.QPen(light, 2))
            painter.drawEllipse(8, 9, 10, 12)
            painter.drawEllipse(12, 9, 10, 12)
            painter.drawLine(15, 8, 17, 5)
        elif glyph == "rotation":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawArc(8, 8, 14, 14, 30 * 16, 285 * 16)
            points = [QtCore.QPoint(20, 8), QtCore.QPoint(23, 14), QtCore.QPoint(17, 12)]
            painter.setBrush(QtGui.QColor("#2C2C2C"))
            painter.drawPolygon(QtGui.QPolygon(points))
        elif glyph == "skin":
            painter.setBrush(QtCore.Qt.NoBrush)
            for x_value in (9, 15, 21):
                painter.drawLine(x_value, 8, x_value, 22)
            for y_value in (10, 16, 22):
                painter.drawLine(8, y_value, 22, y_value)
        elif glyph == "scale":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawLine(10, 20, 20, 10)
            painter.drawLine(20, 10, 20, 15)
            painter.drawLine(20, 10, 15, 10)
            painter.drawLine(10, 20, 10, 15)
            painter.drawLine(10, 20, 15, 20)
        elif glyph == "video":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(8, 9, 14, 12)
            painter.setBrush(light)
            painter.drawPolygon(QtGui.QPolygon([QtCore.QPoint(13, 12), QtCore.QPoint(19, 15), QtCore.QPoint(13, 18)]))
        elif glyph == "notes":
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(9, 8, 12, 14)
            painter.drawLine(12, 12, 18, 12)
            painter.drawLine(12, 16, 18, 16)
            painter.drawLine(12, 20, 16, 20)
        elif glyph == "game":
            painter.setPen(QtGui.QPen(light, 2))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(8, 8, 14, 14)
            painter.drawLine(19, 12, 22, 12)
            painter.drawLine(22, 12, 22, 18)
            painter.drawLine(22, 18, 19, 18)
            painter.setBrush(light)
            painter.drawEllipse(11, 8, 4, 4)
            painter.drawLine(13, 13, 13, 18)
            painter.drawLine(13, 15, 9, 18)
            painter.drawLine(13, 15, 17, 18)
            painter.drawLine(13, 18, 10, 22)
            painter.drawLine(13, 18, 17, 22)
        else:
            painter.setPen(QtGui.QPen(light, 2))
            font = painter.font()
            font.setBold(True)
            font.setPointSize(7 if len(str(glyph)) > 1 else 9)
            painter.setFont(font)
            painter.drawText(QtCore.QRect(5, 6, 20, 18), int(QtCore.Qt.AlignCenter), str(glyph or "?")[:2])
    finally:
        painter.end()
    return QtGui.QIcon(pixmap)


def _style_student_core_button(button, color_hex):
    if not button:
        return
    button.setIconSize(QtCore.QSize(28, 28))
    button.setMinimumWidth(54)
    button.setMinimumHeight(46)
    button.setStyleSheet(
        """
        QToolButton {
            background-color: #252525;
            color: #E8E8E8;
            border: 1px solid #3A3A3A;
            border-bottom: 3px solid %(color)s;
            border-radius: 6px;
            padding: 4px;
            font-weight: 600;
        }
        QToolButton:hover {
            background-color: #303030;
            border-color: %(color)s;
        }
        QToolButton:pressed {
            background-color: %(color)s;
            color: #151515;
        }
        """
        % {"color": color_hex or "#55CBCD"}
    )


def _style_student_timeline_bar_button(button, color_hex):
    if not button:
        return
    button.setIconSize(QtCore.QSize(20, 20))
    button.setMinimumSize(30, 28)
    button.setMaximumSize(34, 30)
    button.setStyleSheet(
        """
        QToolButton {
            background-color: #242424;
            color: #E8E8E8;
            border: 1px solid #373737;
            border-bottom: 2px solid %(color)s;
            border-radius: 4px;
            padding: 2px;
            font-weight: 600;
        }
        QToolButton:hover {
            background-color: #303030;
            border-color: %(color)s;
        }
        QToolButton:pressed {
            background-color: %(color)s;
            color: #111111;
        }
        """
        % {"color": color_hex or "#55CBCD"}
    )


def _style_toolkit_game_mode_button(button):
    if not button:
        return
    button.setIconSize(QtCore.QSize(22, 22))
    button.setMinimumSize(36, 30)
    button.setMaximumSize(42, 32)
    button.setStyleSheet(
        """
        QToolButton {
            background-color: #172033;
            color: #EAF6FF;
            border: 1px solid #2C6CFF;
            border-bottom: 2px solid #2C6CFF;
            border-radius: 5px;
            padding: 2px;
            font-weight: 700;
        }
        QToolButton:hover {
            background-color: #203456;
            border-color: #5BA5FF;
        }
        QToolButton:checked {
            background-color: #176BFF;
            border-color: #8EC5FF;
            border-bottom: 2px solid #BFE3FF;
        }
        QToolButton:pressed {
            background-color: #0F55D8;
        }
        """
    )


def _open_workflow_tab(tab_alias):
    if not MAYA_AVAILABLE:
        return False, "Workflow tabs only open inside Maya."
    try:
        import maya_dynamic_parent_pivot as workflow
        window = getattr(workflow, "GLOBAL_WINDOW", None)
        if window and hasattr(window, "_set_initial_tab"):
            window._set_initial_tab(tab_alias)
            try:
                window.show()
            except Exception:
                pass
            return True, "Opened {0}.".format(tab_alias.replace("_", " ").title())
    except Exception:
        pass
    try:
        import maya_anim_workflow_tools
        maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True, initial_tab=tab_alias)
        return True, "Opened {0}.".format(tab_alias.replace("_", " ").title())
    except Exception as exc:
        return False, "Could not open workflow tab: {0}".format(exc)


def _set_attr_if_settable(node_name, attr_name, value):
    plug = "{0}.{1}".format(node_name, attr_name)
    if not cmds or not cmds.objExists(plug):
        return False
    try:
        if cmds.getAttr(plug, lock=True):
            return False
    except Exception:
        pass
    try:
        cmds.setAttr(plug, value)
        return True
    except Exception:
        return False


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


def _make_camera(name, offset, focal_length=55.0):
    camera_result = cmds.camera(name=name) or []
    camera_transform = camera_result[0] if camera_result else name
    camera_shape = camera_result[1] if len(camera_result) > 1 else ""
    if camera_transform and cmds.objExists(camera_transform):
        try:
            cmds.setAttr(camera_shape + ".focalLength", focal_length)
        except Exception:
            pass
    return camera_transform, camera_shape


def _scene_helpers_camera_driver(camera_name, camera_root=""):
    if not cmds or not camera_name or not cmds.objExists(camera_name):
        return ""
    parent_name = ""
    try:
        parent_name = (cmds.listRelatives(camera_name, parent=True, fullPath=False) or [""])[0]
    except Exception:
        parent_name = ""
    if parent_name and parent_name.endswith("_pivot_GRP") and cmds.objExists(parent_name):
        if not camera_root:
            return parent_name
        try:
            driver_parent = (cmds.listRelatives(parent_name, parent=True, fullPath=False) or [""])[0]
        except Exception:
            driver_parent = ""
        if not driver_parent or driver_parent == camera_root:
            return parent_name
    return camera_name


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
    camera_root = SCENE_HELPERS_CAMERA_ROOT_NAME if cmds.objExists(SCENE_HELPERS_CAMERA_ROOT_NAME) else ""
    if camera_root:
        try:
            cmds.xform(camera_root, worldSpace=True, translation=center)
        except Exception:
            pass
    for preset_key, (base_offset, _focal_length) in specs.items():
        camera_name = camera_map.get(preset_key) or SCENE_HELPERS_CAMERA_NAMES.get(preset_key, "")
        if not camera_name or not cmds.objExists(camera_name):
            continue
        final_offset = _scene_helpers_camera_offset_vector(base_offset, height_offset, dolly_offset)
        driver_name = _scene_helpers_camera_driver(camera_name, camera_root)
        try:
            cmds.xform(
                driver_name,
                worldSpace=True,
                translation=(
                    float(center[0] + final_offset[0]),
                    float(center[1] + final_offset[1]),
                    float(center[2] + final_offset[2]),
                ),
            )
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
    # Maya calls this callback with a single panel string on this machine.
    # Keep the stub matching that exact signature so the viewport activation step stays quiet.
    try:
        mel.eval("global proc CgAbBlastPanelOptChangeCallback(string $panel) {}")
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
    try:
        cmds.xform(camera_root, worldSpace=True, translation=center)
    except Exception:
        pass
    for key, (offset, focal_length) in camera_specs.items():
        camera_name = SCENE_HELPERS_CAMERA_NAMES[key]
        adjusted_offset = _scene_helpers_camera_offset_vector(offset, camera_height_offset, camera_dolly_offset)
        camera_transform, camera_shape = _make_camera(camera_name, adjusted_offset, focal_length=focal_length)
        if camera_transform:
            camera_pivot = cmds.createNode("transform", name=camera_name + "_pivot_GRP", parent=camera_root)
            cmds.parent(camera_transform, camera_pivot)
            try:
                cmds.setAttr(camera_transform + ".translateX", 0.0)
                cmds.setAttr(camera_transform + ".translateY", 0.0)
                cmds.setAttr(camera_transform + ".translateZ", 0.0)
                cmds.xform(
                    camera_pivot,
                    worldSpace=True,
                    translation=(
                        float(center[0] + adjusted_offset[0]),
                        float(center[1] + adjusted_offset[1]),
                        float(center[2] + adjusted_offset[2]),
                    ),
                )
            except Exception:
                pass
            _look_at(camera_pivot, (center[0], center[1] + float(camera_height_offset), center[2]))
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
        self.animation_layer_tint_enabled = _option_var_bool(ANIMATION_LAYER_TINT_OPTION, DEFAULT_ANIMATION_LAYER_TINT)
        self.game_animation_mode_enabled = _option_var_bool(GAME_ANIMATION_MODE_OPTION, DEFAULT_GAME_ANIMATION_MODE)
        self.auto_key_enabled = _current_auto_key_state()
        self._last_time_unit = _current_time_unit()
        self._idle_script_job_id = None
        self.status_callback = None
        self.last_render_camera_preset = "perspective"
        self.scene_helpers_camera_height_offset = 0.0
        self.scene_helpers_camera_dolly_offset = 0.0
        try:
            crash_recovery.bootstrap_crash_recovery(startup_prompt=False)
        except Exception:
            pass
        self._install_idle_watch()

    def set_animation_layer_tint_enabled(self, enabled):
        self.animation_layer_tint_enabled = bool(enabled)
        _save_option_var_bool(ANIMATION_LAYER_TINT_OPTION, self.animation_layer_tint_enabled)
        if self.animation_layer_tint_enabled:
            info = self.animation_layer_tint_info()
            message = "Animation Layer Tint is on. Showing {0}.".format(info.get("label") or "Base Animation")
        else:
            message = "Animation Layer Tint is off."
        self._emit_status(message, True)
        return True, message

    def animation_layer_tint_info(self):
        if not MAYA_AVAILABLE or not cmds:
            return {
                "enabled": False,
                "layer": "",
                "label": "Maya not available",
                "color": "#3A3A3A",
            }
        if not self.animation_layer_tint_enabled:
            return {
                "enabled": False,
                "layer": "",
                "label": "Animation Layer Tint Off",
                "color": "#3A3A3A",
            }
        layer_name = _active_animation_layer_name()
        if not layer_name:
            return {
                "enabled": True,
                "layer": "",
                "label": "Base Animation",
                "color": "#4A4A4A",
            }
        return {
            "enabled": True,
            "layer": layer_name,
            "label": _short_name(layer_name),
            "color": _animation_layer_color(layer_name),
        }

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

    def set_game_animation_mode_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled:
            return self.apply_game_animation_mode()
        self.game_animation_mode_enabled = False
        _save_option_var_bool(GAME_ANIMATION_MODE_OPTION, False)
        message = "Game Animation Mode visual toggle is off. Scene settings were not changed back."
        self._emit_status(message, True)
        return True, message

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

    def _student_core_targets(self):
        nodes = _selected_transform_nodes()
        if nodes:
            return nodes, "selected controls"
        nodes = _scene_keyed_transforms()
        return nodes, "all keyed controls"

    def nudge_keys(self, frame_delta):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        frame_delta = int(frame_delta)
        if not frame_delta:
            return False, "Choose a non-zero frame move."

        selected_curves = []
        try:
            selected_curves = cmds.keyframe(query=True, selected=True, name=True) or []
        except Exception:
            selected_curves = []
        if selected_curves:
            try:
                cmds.undoInfo(openChunk=True, chunkName="StudentCoreNudgeSelectedKeys")
            except Exception:
                pass
            try:
                cmds.keyframe(edit=True, selected=True, relative=True, timeChange=frame_delta)
            finally:
                try:
                    cmds.undoInfo(closeChunk=True)
                except Exception:
                    pass
            direction = "later" if frame_delta > 0 else "earlier"
            return True, "Moved selected Graph Editor keys {0} frame(s) {1}.".format(abs(frame_delta), direction)

        nodes, scope_label = self._student_core_targets()
        if not nodes:
            return False, "Select animated controls or selected keys first."
        try:
            cmds.undoInfo(openChunk=True, chunkName="StudentCoreNudgeControlKeys")
        except Exception:
            pass
        changed_nodes = 0
        try:
            for node_name in nodes:
                try:
                    key_count = len(cmds.keyframe(node_name, query=True, timeChange=True) or [])
                except Exception:
                    key_count = 0
                if not key_count:
                    continue
                cmds.keyframe(node_name, edit=True, relative=True, timeChange=frame_delta)
                changed_nodes += 1
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        if not changed_nodes:
            return False, "No keyed controls found to move."
        direction = "later" if frame_delta > 0 else "earlier"
        return True, "Moved keys on {0} {1} {2} frame(s) {3}.".format(changed_nodes, scope_label, abs(frame_delta), direction)

    def insert_inbetween_key(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes, scope_label = self._student_core_targets()
        if not nodes:
            return False, "Select animated controls first."
        current_time = float(cmds.currentTime(query=True))
        inserted = 0
        try:
            cmds.undoInfo(openChunk=True, chunkName="StudentCoreInsertInbetween")
        except Exception:
            pass
        try:
            for node_name in nodes:
                keyable_attrs = cmds.listAttr(node_name, keyable=True) or []
                for attr_name in keyable_attrs:
                    try:
                        existing = cmds.keyframe(node_name, attribute=attr_name, query=True, timeChange=True) or []
                    except Exception:
                        existing = []
                    if not existing:
                        continue
                    if any(abs(float(time_value) - current_time) <= 1.0e-4 for time_value in existing):
                        continue
                    try:
                        cmds.setKeyframe(node_name, attribute=attr_name, time=current_time, insert=True)
                        inserted += 1
                    except Exception:
                        continue
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        if not inserted:
            return False, "No inbetweens were added. Pick controls with animation and move to an unkeyed frame."
        return True, "Inserted {0} inbetween key(s) on {1}.".format(inserted, scope_label)

    def remove_current_keys(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes, scope_label = self._student_core_targets()
        if not nodes:
            return False, "Select animated controls first."
        current_time = float(cmds.currentTime(query=True))
        removed = 0
        try:
            cmds.undoInfo(openChunk=True, chunkName="StudentCoreRemoveCurrentKeys")
        except Exception:
            pass
        try:
            for node_name in nodes:
                keyable_attrs = cmds.listAttr(node_name, keyable=True) or []
                for attr_name in keyable_attrs:
                    try:
                        times = cmds.keyframe(node_name, attribute=attr_name, query=True, timeChange=True) or []
                    except Exception:
                        times = []
                    if not any(abs(float(time_value) - current_time) <= 1.0e-4 for time_value in times):
                        continue
                    try:
                        cmds.cutKey(node_name, attribute=attr_name, time=(current_time, current_time), option="keys")
                        removed += 1
                    except Exception:
                        continue
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        if not removed:
            return False, "There were no keys on this frame for the chosen controls."
        return True, "Removed {0} key(s) on frame {1:g} from {2}.".format(removed, current_time, scope_label)

    def reset_selected_transforms(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes = _selected_transform_nodes()
        if not nodes:
            return False, "Select controls to reset first."
        changed = 0
        keyed = 0
        reset_values = (
            ("translateX", 0.0), ("translateY", 0.0), ("translateZ", 0.0),
            ("rotateX", 0.0), ("rotateY", 0.0), ("rotateZ", 0.0),
            ("scaleX", 1.0), ("scaleY", 1.0), ("scaleZ", 1.0),
        )
        should_key = _current_auto_key_state()
        try:
            cmds.undoInfo(openChunk=True, chunkName="StudentCoreResetPose")
        except Exception:
            pass
        try:
            for node_name in nodes:
                for attr_name, value in reset_values:
                    if _set_attr_if_settable(node_name, attr_name, value):
                        changed += 1
                        if should_key:
                            try:
                                cmds.setKeyframe(node_name, attribute=attr_name)
                                keyed += 1
                            except Exception:
                                pass
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        if not changed:
            return False, "Selected controls did not have settable transform channels."
        message = "Reset {0} transform channel(s) on {1} control(s).".format(changed, len(nodes))
        if keyed:
            message = "{0} Keyed {1} reset channel(s) because Auto Key is on.".format(message, keyed)
        return True, message

    def bake_selected_interval(self, frame_step=2):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes = _selected_transform_nodes()
        if not nodes:
            return False, "Select controls to bake first."
        frame_step = max(1, int(frame_step or 1))
        start_time = float(cmds.playbackOptions(query=True, minTime=True))
        end_time = float(cmds.playbackOptions(query=True, maxTime=True))
        attrs = ("tx", "ty", "tz", "rx", "ry", "rz", "sx", "sy", "sz")
        try:
            cmds.undoInfo(openChunk=True, chunkName="StudentCoreBakeInterval")
        except Exception:
            pass
        try:
            cmds.bakeResults(
                nodes,
                time=(start_time, end_time),
                sampleBy=frame_step,
                simulation=True,
                preserveOutsideKeys=True,
                sparseAnimCurveBake=False,
                disableImplicitControl=True,
                attribute=attrs,
            )
        except Exception as exc:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
            return False, "Could not bake selected controls: {0}".format(exc)
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        return True, "Baked {0} selected control(s) from frame {1:g} to {2:g} every {3} frame(s).".format(len(nodes), start_time, end_time, frame_step)

    def select_animated_controls(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes = _scene_keyed_transforms()
        if not nodes:
            return False, "No animated transform controls found."
        cmds.select(nodes, replace=True)
        return True, "Selected {0} animated control(s).".format(len(nodes))

    def remove_static_animation_curves(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        nodes = _selected_transform_nodes()
        if not nodes:
            return False, "Select controls before cleaning static curves."
        deleted = 0
        try:
            cmds.undoInfo(openChunk=True, chunkName="StudentCoreCleanStaticCurves")
        except Exception:
            pass
        try:
            for node_name in nodes:
                curves = cmds.listConnections(node_name, source=True, destination=False, type="animCurve") or []
                for curve_name in _dedupe_preserve_order(curves):
                    try:
                        values = cmds.keyframe(curve_name, query=True, valueChange=True) or []
                    except Exception:
                        values = []
                    if len(values) <= 1:
                        continue
                    first_value = float(values[0])
                    if not all(abs(float(value) - first_value) <= 1.0e-5 for value in values):
                        continue
                    try:
                        cmds.delete(curve_name)
                        deleted += 1
                    except Exception:
                        continue
        finally:
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass
        if not deleted:
            return True, "No static curves needed cleaning on selected controls."
        return True, "Deleted {0} static animation curve(s) on selected controls.".format(deleted)

    def run_student_core_command(self, command):
        command = (command or "").strip().lower()
        if command == "nudge_left":
            return self.nudge_keys(-1)
        if command == "nudge_right":
            return self.nudge_keys(1)
        if command == "insert_inbetween":
            return self.insert_inbetween_key()
        if command == "remove_current":
            return self.remove_current_keys()
        if command == "reset_pose":
            return self.reset_selected_transforms()
        if command == "bake_twos":
            return self.bake_selected_interval(2)
        if command == "select_animated":
            return self.select_animated_controls()
        if command == "clean_static":
            return self.remove_static_animation_curves()
        return False, "Unknown Student Core command: {0}".format(command)

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
            cmds.playbackOptions(edit=True, view="all")
        except Exception as exc:
            return False, "Could not set Time Slider update view to All: {0}".format(exc)

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

        texture_success, texture_message, texture_details = self.load_scene_textures(emit_status=False)

        self._last_time_unit = _current_time_unit()
        self.game_animation_mode_enabled = True
        _save_option_var_bool(GAME_ANIMATION_MODE_OPTION, True)
        message = "Game Animation Mode is on. Scene set to 30 fps, real-time playback, autosave, and {0} active viewport(s).".format(active_panels)
        if texture_message:
            message = "{0} {1}".format(message, texture_message)
        self._emit_status(message, True)
        return True, message

    def load_scene_textures(self, emit_status=True):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya.", {}

        search_roots = _texture_search_roots()
        basename_map = _build_texture_basename_index(search_roots)
        scanned_nodes = 0
        reloaded_nodes = 0
        repathed_nodes = 0
        missing_nodes = []
        processed_nodes = []

        for node_type, attr_name in _scene_texture_node_specs():
            for node_name in cmds.ls(type=node_type) or []:
                scanned_nodes += 1
                try:
                    current_path = cmds.getAttr(node_name + "." + attr_name) or ""
                except Exception:
                    current_path = ""
                resolved_path, was_repathed = _resolve_texture_path(current_path, basename_map, search_roots)
                if not resolved_path:
                    missing_nodes.append(node_name)
                    continue
                if _refresh_texture_node(node_name, attr_name, resolved_path):
                    processed_nodes.append(node_name)
                    reloaded_nodes += 1
                    if was_repathed or os.path.normpath(current_path or "") != os.path.normpath(resolved_path):
                        repathed_nodes += 1
                else:
                    missing_nodes.append(node_name)

        try:
            cmds.filePathEditor(refresh=True)
        except Exception:
            pass
        try:
            cmds.refresh(force=True)
        except Exception:
            pass

        detail = {
            "scanned_nodes": scanned_nodes,
            "reloaded_nodes": reloaded_nodes,
            "repathed_nodes": repathed_nodes,
            "missing_nodes": list(missing_nodes),
            "search_roots": list(search_roots),
            "processed_nodes": list(processed_nodes),
        }

        if not scanned_nodes:
            message = "There were no scene texture nodes to load."
            success = True
        else:
            parts = ["Loaded {0} texture node(s)".format(reloaded_nodes)]
            if repathed_nodes:
                parts.append("fixed {0} broken path(s)".format(repathed_nodes))
            if missing_nodes:
                parts.append("{0} still missing".format(len(missing_nodes)))
            message = ". ".join(parts) + "."
            success = True

        if emit_status:
            self._emit_status(message, success)
        return success, message, detail

    def recover_last_autosave(self, prompt=True, force=False, prefer_current_scene=True):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya.", {}
        return crash_recovery.recover_last_autosave(
            prompt=prompt,
            force=force,
            prefer_current_scene=prefer_current_scene,
        )

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

    class StudentTimelineButtonPopup(QtWidgets.QDialog):
        def __init__(self, controller, status_callback=None, parent=None):
            super(StudentTimelineButtonPopup, self).__init__(parent)
            self.controller = controller
            self.status_callback = status_callback
            self.setObjectName(STUDENT_CORE_TEMP_POPUP_OBJECT)
            self.setWindowTitle("Toolkit Buttons")
            flags = _qt_flag("WindowType", "Tool", QtCore.Qt.Tool)
            frameless = _qt_flag("WindowType", "FramelessWindowHint", QtCore.Qt.FramelessWindowHint)
            try:
                self.setWindowFlags(flags | frameless)
            except Exception:
                pass
            self._build_ui()

        def _build_ui(self):
            self.setStyleSheet(
                """
                QDialog#studentCoreTimelineTempButtons {
                    background-color: #2A2A2A;
                    border: 1px solid #454545;
                    border-radius: 6px;
                }
                QLabel {
                    color: #D8D8D8;
                }
                """
            )
            layout = QtWidgets.QHBoxLayout(self)
            layout.setContentsMargins(8, 6, 8, 6)
            layout.setSpacing(6)
            label = QtWidgets.QLabel("Timeline")
            label.setStyleSheet("font-weight: 600;")
            layout.addWidget(label)
            for tool in STUDENT_CORE_TOOLS:
                button = QtWidgets.QToolButton()
                button.setObjectName("studentCoreTemp_{0}".format(tool["command"]))
                button.setText(tool["label"])
                button.setIcon(_make_student_core_icon(tool["color"], tool["glyph"]))
                button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                button.setToolTip(tool["tooltip"])
                _style_student_core_button(button, tool["color"])
                button.clicked.connect(lambda _checked=False, command=tool["command"]: self._run(command))
                layout.addWidget(button)
            close_button = QtWidgets.QToolButton()
            close_button.setText("x")
            close_button.setToolTip("Hide these temporary timeline buttons.")
            close_button.clicked.connect(self.hide)
            close_button.setStyleSheet(
                """
                QToolButton {
                    background-color: #3A3A3A;
                    color: #E0E0E0;
                    border: 1px solid #555555;
                    border-radius: 6px;
                    padding: 4px 8px;
                    font-weight: 700;
                }
                QToolButton:hover { background-color: #4A4A4A; }
                """
            )
            layout.addWidget(close_button)

        def _run(self, command):
            success, message = self.controller.run_student_core_command(command)
            if self.status_callback:
                self.status_callback(message, success)


    class StudentCoreToolbarPanel(QtWidgets.QFrame):
        def __init__(self, controller, status_callback=None, parent=None):
            super(StudentCoreToolbarPanel, self).__init__(parent)
            self.controller = controller
            self.status_callback = status_callback
            self._temp_popup = None
            self.setObjectName("studentCoreToolbarPanel")
            self._build_ui()

        def _build_ui(self):
            self.setStyleSheet(
                """
                QFrame#studentCoreToolbarPanel {
                    background-color: #202020;
                    border: 1px solid #3A3A3A;
                    border-radius: 6px;
                }
                QLabel#studentCoreTitle {
                    color: #F0F0F0;
                    font-weight: 700;
                }
                QLabel#studentCoreHint {
                    color: #B8B8B8;
                }
                QFrame#studentCoreTimelineTrack {
                    background-color: #151515;
                    border: 1px solid #303030;
                    border-radius: 5px;
                }
                """
            )
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(10, 8, 10, 10)
            layout.setSpacing(8)

            header = QtWidgets.QHBoxLayout()
            title = QtWidgets.QLabel("Student Core")
            title.setObjectName("studentCoreTitle")
            header.addWidget(title)
            hint = QtWidgets.QLabel("Compact color buttons for the timing jobs students use most.")
            hint.setObjectName("studentCoreHint")
            hint.setWordWrap(True)
            header.addWidget(hint, 1)
            self.show_temp_button = QtWidgets.QPushButton("Open Toolkit Bar")
            self.show_temp_button.setText("Open Toolkit Bar")
            self.show_temp_button.setToolTip("Open the small dockable Toolkit Bar above Maya's timeline.")
            self.show_temp_button.clicked.connect(self._show_temporary_buttons)
            header.addWidget(self.show_temp_button)
            layout.addLayout(header)

            track = QtWidgets.QFrame()
            track.setObjectName("studentCoreTimelineTrack")
            track_layout = QtWidgets.QHBoxLayout(track)
            track_layout.setContentsMargins(8, 6, 8, 6)
            track_layout.setSpacing(6)
            for index in range(8):
                tick = QtWidgets.QLabel("|")
                tick.setStyleSheet("color: #4D4D4D;")
                tick.setAlignment(QtCore.Qt.AlignCenter)
                track_layout.addWidget(tick)
                tool = STUDENT_CORE_TOOLS[index]
                button = QtWidgets.QToolButton()
                button.setObjectName("studentCoreTool_{0}".format(tool["command"]))
                button.setText(tool["label"])
                button.setIcon(_make_student_core_icon(tool["color"], tool["glyph"]))
                button.setToolButtonStyle(QtCore.Qt.ToolButtonTextUnderIcon)
                button.setToolTip("{0}: {1}".format(tool["group"], tool["tooltip"]))
                _style_student_core_button(button, tool["color"])
                button.clicked.connect(lambda _checked=False, command=tool["command"]: self._run(command))
                track_layout.addWidget(button)
            track_layout.addStretch(1)
            layout.addWidget(track)

        def _run(self, command):
            success, message = self.controller.run_student_core_command(command)
            if self.status_callback:
                self.status_callback(message, success)

        def _show_temporary_buttons(self):
            launch_student_timeline_button_bar(dock=True, controller=self.controller, status_callback=self.status_callback)
            if self.status_callback:
                self.status_callback("Toolkit Bar is docked above Maya's timeline.", True)


    class StudentTimelineButtonBarWindow(_WindowBase):
        def __init__(self, controller, status_callback=None, parent=None, owns_controller=False):
            super(StudentTimelineButtonBarWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller
            self.status_callback = status_callback
            self.owns_controller = bool(owns_controller)
            self.setObjectName(STUDENT_TIMELINE_BAR_OBJECT_NAME)
            self.setWindowTitle("Toolkit Bar")
            self.setMinimumSize(760, 56)
            self.setMaximumHeight(64)
            if hasattr(self, "setSizePolicy"):
                self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
            self._layer_tint_timer = None
            self._build_ui()
            self._refresh_animation_layer_tint()
            self._start_animation_layer_tint_timer()

        def _build_ui(self):
            self.setStyleSheet(
                """
                QDialog#studentCoreTimelineButtonBarWindow {
                    background-color: #2B2B2B;
                    border: 1px solid #3A3A3A;
                }
                """
            )
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(6, 3, 6, 4)
            main_layout.setSpacing(3)
            self.animation_layer_tint_label = QtWidgets.QLabel("Base Animation")
            self.animation_layer_tint_label.setObjectName("studentTimelineBarAnimationLayerTint")
            self.animation_layer_tint_label.setAlignment(QtCore.Qt.AlignCenter)
            self.animation_layer_tint_label.setMinimumHeight(16)
            self.animation_layer_tint_label.setMaximumHeight(18)
            self.animation_layer_tint_label.setToolTip(
                "Animation Layer Tint: shows the current selected animation layer above the timeline so students know which layer they are editing."
            )
            main_layout.addWidget(self.animation_layer_tint_label)

            layout = QtWidgets.QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            for tool in STUDENT_CORE_TOOLS:
                button = QtWidgets.QToolButton()
                button.setObjectName("studentTimelineBar_{0}".format(tool["command"]))
                button.setIcon(_make_student_core_icon(tool["color"], tool["glyph"]))
                button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
                button.setToolTip("{0}: {1}".format(tool["label"], tool["tooltip"]))
                _style_student_timeline_bar_button(button, tool["color"])
                button.clicked.connect(lambda _checked=False, command=tool["command"]: self._run(command))
                layout.addWidget(button)
            separator = QtWidgets.QFrame()
            separator.setObjectName("studentTimelineBarSeparator")
            separator.setFrameShape(QtWidgets.QFrame.VLine)
            separator.setStyleSheet("color: #4A4A4A;")
            layout.addWidget(separator)
            for tool in WORKFLOW_BAR_TOOLS:
                button = QtWidgets.QToolButton()
                button.setObjectName("studentTimelineBar_{0}".format(tool["command"]))
                button.setIcon(_make_student_core_icon(tool["color"], tool["glyph"]))
                button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
                button.setToolTip("{0}: {1}".format(tool["label"], tool["tooltip"]))
                _style_student_timeline_bar_button(button, tool["color"])
                button.clicked.connect(lambda _checked=False, tab=tool["tab"]: self._open_workflow_tab(tab))
                layout.addWidget(button)
            layout.addStretch(1)
            self.game_mode_button = QtWidgets.QToolButton()
            self.game_mode_button.setObjectName("toolkitBarGameAnimationModeButton")
            self.game_mode_button.setCheckable(True)
            self.game_mode_button.setChecked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
            self.game_mode_button.setIcon(_make_student_core_icon("#176BFF", "game"))
            self.game_mode_button.setToolButtonStyle(QtCore.Qt.ToolButtonIconOnly)
            self.game_mode_button.setToolTip(
                "Game Animation Mode: set scene to 30 fps, realtime playback, autosave with five backups, texture reload, and all viewports active."
            )
            _style_toolkit_game_mode_button(self.game_mode_button)
            self.game_mode_button.toggled.connect(self._toggle_game_animation_mode)
            layout.addWidget(self.game_mode_button)
            main_layout.addLayout(layout)

        def _start_animation_layer_tint_timer(self):
            if not QtCore:
                return
            self._layer_tint_timer = QtCore.QTimer(self)
            self._layer_tint_timer.setInterval(500)
            self._layer_tint_timer.timeout.connect(self._refresh_animation_layer_tint)
            self._layer_tint_timer.start()

        def _refresh_animation_layer_tint(self):
            if not getattr(self, "animation_layer_tint_label", None):
                return
            try:
                info = self.controller.animation_layer_tint_info()
            except Exception:
                info = {"enabled": False, "label": "Animation Layer Tint", "color": "#3A3A3A"}
            color_hex = info.get("color") or "#3A3A3A"
            label = info.get("label") or "Base Animation"
            if info.get("enabled"):
                text = "Animation Layer: {0}".format(label)
                text_color = "#F6F6F6"
                border_color = color_hex
            else:
                text = str(label)
                text_color = "#A8A8A8"
                border_color = "#4A4A4A"
            self.animation_layer_tint_label.setText(text)
            self.animation_layer_tint_label.setStyleSheet(
                """
                QLabel#studentTimelineBarAnimationLayerTint {{
                    background-color: {color};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: 5px;
                    font-size: 10px;
                    font-weight: 700;
                    padding: 1px 8px;
                }}
                """.format(color=color_hex, text_color=text_color, border_color=border_color)
            )

        def _run(self, command):
            success, message = self.controller.run_student_core_command(command)
            if self.status_callback:
                self.status_callback(message, success)
            elif MAYA_AVAILABLE and om2:
                if success:
                    om2.MGlobal.displayInfo("[Toolkit Bar] {0}".format(message))
                else:
                    om2.MGlobal.displayWarning("[Toolkit Bar] {0}".format(message))

        def _set_game_button_checked(self, enabled):
            if not getattr(self, "game_mode_button", None):
                return
            self.game_mode_button.blockSignals(True)
            self.game_mode_button.setChecked(bool(enabled))
            self.game_mode_button.blockSignals(False)

        def _toggle_game_animation_mode(self, enabled):
            success, message = self.controller.set_game_animation_mode_enabled(enabled)
            self._set_game_button_checked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
            self._sync_scene_helpers_game_button()
            if self.status_callback:
                self.status_callback(message, success)
            elif MAYA_AVAILABLE and om2:
                if success:
                    om2.MGlobal.displayInfo("[Toolkit Bar] {0}".format(message))
                else:
                    om2.MGlobal.displayWarning("[Toolkit Bar] {0}".format(message))

        def _sync_scene_helpers_game_button(self):
            for window in (GLOBAL_WINDOW,):
                if window is not None and hasattr(window, "game_mode_button"):
                    try:
                        window.game_mode_button.blockSignals(True)
                        window.game_mode_button.setChecked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
                        window.game_mode_button.blockSignals(False)
                    except Exception:
                        pass

        def _open_workflow_tab(self, tab_alias):
            success, message = _open_workflow_tab(tab_alias)
            if self.status_callback:
                self.status_callback(message, success)
            elif MAYA_AVAILABLE and om2:
                if success:
                    om2.MGlobal.displayInfo("[Toolkit Bar] {0}".format(message))
                else:
                    om2.MGlobal.displayWarning("[Toolkit Bar] {0}".format(message))

        def closeEvent(self, event):
            if self._layer_tint_timer is not None:
                try:
                    self._layer_tint_timer.stop()
                except Exception:
                    pass
            if self.owns_controller:
                try:
                    self.controller.shutdown()
                except Exception:
                    pass
            try:
                super(StudentTimelineButtonBarWindow, self).closeEvent(event)
            except TypeError:
                QtWidgets.QDialog.closeEvent(self, event)


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

            self.student_core_panel = StudentCoreToolbarPanel(self.controller, self._set_status, parent=self)
            main_layout.addWidget(self.student_core_panel)

            intro = QtWidgets.QLabel(
            "Use Auto Key when you want Maya to key changes as you animate. "
            "Use Auto Snap To Frames when keys land between frames after a timing change. "
            "Use Animation Layer Tint to see the current layer color and name above the timeline. "
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

            self.game_mode_button = QtWidgets.QToolButton()
            self.game_mode_button.setObjectName("sceneHelpersGameAnimationModeButton")
            self.game_mode_button.setCheckable(True)
            self.game_mode_button.setChecked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
            self.game_mode_button.setText("Game Animation Mode")
            self.game_mode_button.setIcon(_make_student_core_icon("#176BFF", "game"))
            self.game_mode_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            _style_toolkit_game_mode_button(self.game_mode_button)
            self.game_mode_button.setToolTip(
                "Set the scene to 30 fps, real-time playback, autosave with five backups, and mark every viewport "
                "active."
            )
            action_row.addWidget(self.game_mode_button, 1)
            self.load_textures_button = QtWidgets.QPushButton("Load Textures")
            self.load_textures_button.setToolTip(
                "Reload scene texture nodes and try to fix broken texture paths from the current Maya project "
                "folders like sourceimages, textures, and images."
            )
            action_row.addWidget(self.load_textures_button, 1)
            self.recover_autosave_button = QtWidgets.QPushButton("Open Last Autosave")
            self.recover_autosave_button.setToolTip(
                "Open the latest autosave for the current scene, or recover the last crash if Maya closed unexpectedly."
            )
            action_row.addWidget(self.recover_autosave_button, 1)
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
            self.animation_layer_tint_button = QtWidgets.QToolButton()
            self.animation_layer_tint_button.setObjectName("sceneHelpersAnimationLayerTintButton")
            self.animation_layer_tint_button.setCheckable(True)
            self.animation_layer_tint_button.setText("Animation Layer Tint")
            self.animation_layer_tint_button.setToolButtonStyle(QtCore.Qt.ToolButtonTextBesideIcon)
            self.animation_layer_tint_button.setIcon(_make_student_core_icon("#55CBCD", "bars"))
            self.animation_layer_tint_button.setToolTip(
                "Show a colored strip above Maya's timeline using the current selected animation layer name and color."
            )
            snap_row.addWidget(self.animation_layer_tint_button, 1)
            self.refresh_layer_tint_button = QtWidgets.QPushButton("Refresh Layer Tint")
            self.refresh_layer_tint_button.setObjectName("sceneHelpersRefreshLayerTintButton")
            self.refresh_layer_tint_button.setToolTip("Refresh the docked timeline layer tint strip after changing animation layers.")
            snap_row.addWidget(self.refresh_layer_tint_button, 1)
            main_layout.addLayout(snap_row)

            help_box = QtWidgets.QPlainTextEdit()
            help_box.setReadOnly(True)
            help_box.setPlainText(
                "1. Use Auto Key when you want Maya to key changes as you animate.\n"
                "2. Leave Auto Snap To Frames on if you want the tool to catch timing changes for you.\n"
                "3. If keys are already off-frame, click Snap Selected Keys To Frames.\n"
                "4. Leave Animation Layer Tint on if you want the bar above the timeline to show the current animation layer.\n"
                "5. Click Load Textures when textures exist locally but Maya has not refreshed or repathed them yet.\n"
                "6. Click Open Last Autosave if Maya crashed and you want to jump straight back to the latest autosave.\n"
                "7. If you are setting up a student game shot, click Game Animation Mode.\n"
                "8. Use Set Up Render Environment to build the cyclorama helper, then add the cameras and sky light for the shot.\n"
                "9. Use Delete Render Environment when you want to remove that whole setup again.\n"
                "10. Use Camera Height Offset and Camera Dolly Offset to move all helper cameras up/down or in/out together.\n"
                "11. Use Camera Preset to jump between the Front, Side, and Three Quarter cameras.\n"
                "12. Select controls first when you want the snap to act only on part of the scene."
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
            self.animation_layer_tint_button.toggled.connect(self._toggle_animation_layer_tint)
            self.refresh_layer_tint_button.clicked.connect(self._refresh_animation_layer_tint)
            self.snap_now_button.clicked.connect(self._snap_now)
            self.game_mode_button.toggled.connect(self._toggle_game_mode)
            self.load_textures_button.clicked.connect(self._load_textures)
            self.recover_autosave_button.clicked.connect(self._recover_autosave)
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
            self.game_mode_button.blockSignals(True)
            self.game_mode_button.setChecked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
            self.game_mode_button.blockSignals(False)
            self.animation_layer_tint_button.blockSignals(True)
            self.animation_layer_tint_button.setChecked(bool(getattr(self.controller, "animation_layer_tint_enabled", True)))
            self.animation_layer_tint_button.blockSignals(False)
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

        def _toggle_animation_layer_tint(self, enabled):
            success, message = self.controller.set_animation_layer_tint_enabled(enabled)
            bar_window = GLOBAL_TIMELINE_BAR_WINDOW
            if bar_window is not None and hasattr(bar_window, "_refresh_animation_layer_tint"):
                try:
                    bar_window._refresh_animation_layer_tint()
                except Exception:
                    pass
            self._set_status(message, success)

        def _refresh_animation_layer_tint(self):
            info = self.controller.animation_layer_tint_info()
            bar_window = GLOBAL_TIMELINE_BAR_WINDOW
            if bar_window is not None and hasattr(bar_window, "_refresh_animation_layer_tint"):
                try:
                    bar_window._refresh_animation_layer_tint()
                except Exception:
                    pass
            self._set_status("Animation Layer Tint refreshed: {0}.".format(info.get("label") or "Base Animation"), True)

        def _snap_now(self):
            success, message = self.controller.snap_current_targets()
            self._set_status(message, success)

        def _toggle_game_mode(self, enabled):
            success, message = self.controller.set_game_animation_mode_enabled(enabled)
            if not success:
                self.game_mode_button.blockSignals(True)
                self.game_mode_button.setChecked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
                self.game_mode_button.blockSignals(False)
            bar_window = GLOBAL_TIMELINE_BAR_WINDOW
            if bar_window is not None and hasattr(bar_window, "_set_game_button_checked"):
                try:
                    bar_window._set_game_button_checked(bool(getattr(self.controller, "game_animation_mode_enabled", False)))
                except Exception:
                    pass
            self._set_status(message, success)

        def _load_textures(self):
            success, message, _details = self.controller.load_scene_textures()
            self._set_status(message, success)

        def _recover_autosave(self):
            success, message, _details = self.controller.recover_last_autosave(
                prompt=True,
                force=True,
                prefer_current_scene=True,
            )
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


def _timeline_bar_workspace_exists():
    return bool(MAYA_AVAILABLE and cmds and cmds.workspaceControl(STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME, exists=True))


def _delete_timeline_bar_workspace():
    if not MAYA_AVAILABLE or not cmds:
        return
    if not _timeline_bar_workspace_exists():
        return
    try:
        cmds.workspaceControl(STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME, edit=True, close=True)
    except Exception:
        pass
    try:
        cmds.deleteUI(STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME, control=True)
    except Exception:
        try:
            cmds.deleteUI(STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME)
        except Exception:
            pass


def _close_existing_timeline_bar():
    global GLOBAL_TIMELINE_BAR_WINDOW
    if GLOBAL_TIMELINE_BAR_WINDOW is not None:
        try:
            GLOBAL_TIMELINE_BAR_WINDOW.close()
        except Exception:
            pass
        GLOBAL_TIMELINE_BAR_WINDOW = None


def launch_student_timeline_button_bar(dock=True, controller=None, status_callback=None):
    global GLOBAL_TIMELINE_BAR_CONTROLLER
    global GLOBAL_TIMELINE_BAR_WINDOW
    if not MAYA_AVAILABLE:
        raise RuntimeError("launch_student_timeline_button_bar() must run inside Autodesk Maya.")
    if not QtWidgets:
        raise RuntimeError("launch_student_timeline_button_bar() needs PySide inside Maya.")
    _close_existing_timeline_bar()
    if dock:
        _delete_timeline_bar_workspace()
    owns_controller = controller is None
    GLOBAL_TIMELINE_BAR_CONTROLLER = controller or MayaTimingToolsController()
    GLOBAL_TIMELINE_BAR_WINDOW = StudentTimelineButtonBarWindow(
        GLOBAL_TIMELINE_BAR_CONTROLLER,
        status_callback=status_callback,
        parent=_maya_main_window(),
        owns_controller=owns_controller,
    )
    try:
        GLOBAL_TIMELINE_BAR_WINDOW.show(dockable=True, floating=not bool(dock), area="bottom")
        app = QtWidgets.QApplication.instance()
        if app:
            app.processEvents()
    except Exception:
        GLOBAL_TIMELINE_BAR_WINDOW.show()
    if dock and _timeline_bar_workspace_exists():
        try:
            cmds.workspaceControl(
                STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME,
                edit=True,
                dockToMainWindow=("bottom", False),
                restore=True,
            )
        except Exception:
            pass
    try:
        GLOBAL_TIMELINE_BAR_WINDOW.setMaximumHeight(64)
    except Exception:
        pass
    return GLOBAL_TIMELINE_BAR_WINDOW


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
    "StudentTimelineButtonBarWindow",
    "STUDENT_TIMELINE_BAR_WORKSPACE_CONTROL_NAME",
    "launch_maya_timing_tools",
    "launch_student_timeline_button_bar",
]
