"""
maya_contact_hold.py

Keep picked hand or foot controls locked to the same world-space spot across
an animation frame range.
"""

from __future__ import absolute_import, division, print_function

import math
import os
import re
import traceback

import maya_skinning_cleanup as skin_cleanup

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.OpenMayaUI as omui

    MAYA_AVAILABLE = True
except Exception:
    cmds = None
    om = None
    omui = None
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


WINDOW_OBJECT_NAME = "mayaContactHoldWindow"
WORKSPACE_CONTROL_NAME = WINDOW_OBJECT_NAME + "WorkspaceControl"
FOLLOW_AMIR_URL = "https://followamir.com"
DEFAULT_DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=2U2GXSKFJKJCA"
DONATE_URL = os.environ.get("AMIR_PAYPAL_DONATE_URL") or os.environ.get("AMIR_DONATE_URL") or DEFAULT_DONATE_URL
VALUE_EPSILON = 1.0e-5
DEFAULT_CONTACT_MIN_FRAMES = 3

GLOBAL_CONTROLLER = None
GLOBAL_WINDOW = None

_qt_flag = skin_cleanup._qt_flag
_style_donate_button = skin_cleanup._style_donate_button
_open_external_url = skin_cleanup._open_external_url
_maya_main_window = skin_cleanup._maya_main_window
_dedupe_preserve_order = skin_cleanup._dedupe_preserve_order
_short_name = skin_cleanup._short_name
_node_long_name = skin_cleanup._node_long_name


def _debug(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayInfo("[Maya Contact Hold] {0}".format(message))


def _warning(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayWarning("[Maya Contact Hold] {0}".format(message))


def _selected_controls():
    transforms = cmds.ls(selection=True, long=True, type="transform") or []
    joints = cmds.ls(selection=True, long=True, type="joint") or []
    return _dedupe_preserve_order(transforms + joints)


def _current_frame():
    return int(round(float(cmds.currentTime(query=True))))


def _leaf_name(node_name):
    return node_name.rsplit("|", 1)[-1]


def _split_namespace(node_name):
    leaf_name = _leaf_name(node_name)
    if ":" in leaf_name:
        namespace, local_name = leaf_name.rsplit(":", 1)
        return namespace + ":", local_name
    return "", leaf_name


def _swap_side_names(local_name):
    swaps = []
    boundary = r"(^|[_.\-])"
    tail = r"(?=$|[_.\-])"
    pattern_pairs = [
        (boundary + r"left" + tail, r"\1right"),
        (boundary + r"right" + tail, r"\1left"),
        (boundary + r"Left" + tail, r"\1Right"),
        (boundary + r"Right" + tail, r"\1Left"),
        (boundary + r"LEFT" + tail, r"\1RIGHT"),
        (boundary + r"RIGHT" + tail, r"\1LEFT"),
        (boundary + r"lft" + tail, r"\1rgt"),
        (boundary + r"rgt" + tail, r"\1lft"),
        (boundary + r"lf" + tail, r"\1rt"),
        (boundary + r"rt" + tail, r"\1lf"),
        (boundary + r"l" + tail, r"\1r"),
        (boundary + r"r" + tail, r"\1l"),
        (boundary + r"L" + tail, r"\1R"),
        (boundary + r"R" + tail, r"\1L"),
    ]
    for pattern, replacement in pattern_pairs:
        swapped_name, count = re.subn(pattern, replacement, local_name, count=1)
        if count and swapped_name != local_name:
            swaps.append(swapped_name)

    edge_pairs = [
        ("left", "right"),
        ("right", "left"),
        ("Left", "Right"),
        ("Right", "Left"),
        ("LEFT", "RIGHT"),
        ("RIGHT", "LEFT"),
        ("lft", "rgt"),
        ("rgt", "lft"),
        ("lf", "rt"),
        ("rt", "lf"),
    ]
    for source, replacement in edge_pairs:
        if local_name.startswith(source):
            swaps.append(replacement + local_name[len(source):])
        if local_name.endswith(source):
            swaps.append(local_name[:-len(source)] + replacement)

    return _dedupe_preserve_order(swaps)


def _scene_controls():
    transforms = cmds.ls(long=True, type="transform") or []
    joints = cmds.ls(long=True, type="joint") or []
    return _dedupe_preserve_order(transforms + joints)


def _find_other_side_control(node_name, taken_nodes=None):
    taken_lookup = set(_node_long_name(item) for item in (taken_nodes or []))
    current_name = _node_long_name(node_name)
    taken_lookup.add(current_name)

    namespace, local_name = _split_namespace(node_name)
    candidate_leaves = [namespace + item for item in _swap_side_names(local_name)]
    if not candidate_leaves:
        return None, "{0} does not look like a left or right control name yet.".format(_short_name(node_name))

    all_controls = _scene_controls()
    for candidate_leaf in candidate_leaves:
        matches = []
        for candidate_node in all_controls:
            candidate_long = _node_long_name(candidate_node)
            if candidate_long in taken_lookup:
                continue
            if _leaf_name(candidate_node) == candidate_leaf:
                matches.append(candidate_long)
        if len(matches) == 1:
            return matches[0], None
        if len(matches) > 1:
            return None, "Found more than one match for {0}. Pick the other side by hand for this one.".format(_short_name(node_name))

    return None, "Could not find the matching other-side control for {0}.".format(_short_name(node_name))


def _world_matrix(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, matrix=True)


def _world_translation(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, translation=True) or [0.0, 0.0, 0.0]


def _world_rotation(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, rotation=True) or [0.0, 0.0, 0.0]


def _playback_frame_range():
    start_frame = int(round(float(cmds.playbackOptions(query=True, minTime=True))))
    end_frame = int(round(float(cmds.playbackOptions(query=True, maxTime=True))))
    if end_frame < start_frame:
        start_frame, end_frame = end_frame, start_frame
    return start_frame, end_frame


def _distance(a_values, b_values):
    return math.sqrt(sum((float(a_values[index]) - float(b_values[index])) ** 2 for index in range(min(len(a_values), len(b_values)))))


def _wrapped_angle_delta(value_a, value_b):
    delta = (float(value_b) - float(value_a) + 180.0) % 360.0 - 180.0
    return abs(delta)


def _max_rotation_delta(rotation_a, rotation_b):
    return max(_wrapped_angle_delta(rotation_a[index], rotation_b[index]) for index in range(min(len(rotation_a), len(rotation_b))))


def _percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, float(fraction))) * float(len(ordered) - 1)
    low_index = int(math.floor(position))
    high_index = int(math.ceil(position))
    if low_index == high_index:
        return ordered[low_index]
    blend = position - float(low_index)
    return ordered[low_index] * (1.0 - blend) + ordered[high_index] * blend


def _sample_contact_metrics(control_nodes, start_frame, end_frame, keep_rotation):
    if end_frame <= start_frame:
        return []
    current_time = float(cmds.currentTime(query=True))
    try:
        previous_data = None
        metrics = []
        for frame_value in range(start_frame, end_frame + 1):
            cmds.currentTime(frame_value, edit=True)
            frame_data = {}
            for node_name in control_nodes:
                frame_data[node_name] = {
                    "translation": [float(value) for value in _world_translation(node_name)],
                }
                if keep_rotation:
                    frame_data[node_name]["rotation"] = [float(value) for value in _world_rotation(node_name)]
            if previous_data is not None:
                max_distance = 0.0
                max_height = 0.0
                max_rotation = 0.0
                for node_name in control_nodes:
                    previous_pose = previous_data[node_name]
                    current_pose = frame_data[node_name]
                    max_distance = max(max_distance, _distance(previous_pose["translation"], current_pose["translation"]))
                    max_height = max(max_height, abs(float(previous_pose["translation"][1]) - float(current_pose["translation"][1])))
                    if keep_rotation:
                        max_rotation = max(max_rotation, _max_rotation_delta(previous_pose["rotation"], current_pose["rotation"]))
                metrics.append(
                    {
                        "prev_frame": int(frame_value - 1),
                        "frame": int(frame_value),
                        "distance": float(max_distance),
                        "height": float(max_height),
                        "rotation": float(max_rotation),
                    }
                )
            previous_data = frame_data
    finally:
        cmds.currentTime(current_time, edit=True)
    return metrics


def _suggest_contact_run(control_nodes, current_frame, keep_rotation):
    playback_start, playback_end = _playback_frame_range()
    metrics = _sample_contact_metrics(control_nodes, playback_start, playback_end, keep_rotation)
    if not metrics:
        return None

    distances = [item["distance"] for item in metrics]
    heights = [item["height"] for item in metrics]
    rotations = [item["rotation"] for item in metrics] if keep_rotation else []
    move_threshold = max(0.05, _percentile(distances, 0.25) * 2.5)
    height_threshold = max(0.02, _percentile(heights, 0.25) * 2.5)
    rotation_threshold = max(4.0, _percentile(rotations, 0.25) * 2.5) if keep_rotation else None

    runs = []
    index = 0
    while index < len(metrics):
        item = metrics[index]
        calm = item["distance"] <= move_threshold and item["height"] <= height_threshold
        if calm and keep_rotation:
            calm = item["rotation"] <= rotation_threshold
        if not calm:
            index += 1
            continue
        run_start = item["prev_frame"]
        run_end = item["frame"]
        total_distance = item["distance"]
        total_height = item["height"]
        total_rotation = item["rotation"]
        sample_count = 1
        index += 1
        while index < len(metrics):
            next_item = metrics[index]
            next_calm = next_item["distance"] <= move_threshold and next_item["height"] <= height_threshold
            if next_calm and keep_rotation:
                next_calm = next_item["rotation"] <= rotation_threshold
            if not next_calm:
                break
            run_end = next_item["frame"]
            total_distance += next_item["distance"]
            total_height += next_item["height"]
            total_rotation += next_item["rotation"]
            sample_count += 1
            index += 1
        if int(run_end - run_start + 1) >= DEFAULT_CONTACT_MIN_FRAMES:
            runs.append(
                {
                    "start_frame": int(run_start),
                    "end_frame": int(run_end),
                    "avg_distance": total_distance / float(sample_count),
                    "avg_height": total_height / float(sample_count),
                    "avg_rotation": total_rotation / float(sample_count) if keep_rotation else 0.0,
                    "move_threshold": move_threshold,
                    "height_threshold": height_threshold,
                    "rotation_threshold": rotation_threshold,
                }
            )
        index += 1

    if not runs:
        return None

    inside_runs = [item for item in runs if item["start_frame"] <= int(current_frame) <= item["end_frame"]]
    if inside_runs:
        return sorted(inside_runs, key=lambda item: (item["avg_distance"], item["avg_height"], -(item["end_frame"] - item["start_frame"])))[0]

    return sorted(
        runs,
        key=lambda item: (
            min(abs(int(current_frame) - item["start_frame"]), abs(int(current_frame) - item["end_frame"])),
            item["avg_distance"],
            item["avg_height"],
            -(item["end_frame"] - item["start_frame"]),
        ),
    )[0]


def _attr_unlocked(node_name, attribute):
    plug = "{0}.{1}".format(node_name, attribute)
    if not cmds.objExists(plug):
        return False
    try:
        return not bool(cmds.getAttr(plug, lock=True))
    except Exception:
        return False


def _channels_for_hold(node_name, keep_rotation):
    attributes = []
    for attribute in ("translateX", "translateY", "translateZ"):
        if _attr_unlocked(node_name, attribute):
            attributes.append(attribute)
    if keep_rotation:
        for attribute in ("rotateX", "rotateY", "rotateZ"):
            if _attr_unlocked(node_name, attribute):
                attributes.append(attribute)
    return attributes


def _capture_pose(node_name, keep_rotation):
    data = {
        "translation": [float(value) for value in _world_translation(node_name)],
    }
    if keep_rotation:
        data["matrix"] = [float(value) for value in _world_matrix(node_name)]
    return data


def _apply_pose(node_name, pose, keep_rotation):
    if keep_rotation and pose.get("matrix"):
        cmds.xform(node_name, worldSpace=True, matrix=list(pose["matrix"]))
        return
    cmds.xform(node_name, worldSpace=True, translation=list(pose["translation"]))


def _set_keys(node_name, attributes):
    for attribute in attributes:
        if not _attr_unlocked(node_name, attribute):
            continue
        try:
            cmds.setKeyframe(node_name, attribute=attribute)
        except Exception:
            pass


def _capture_boundary_poses(control_nodes, frames, keep_rotation):
    result = {}
    for frame_value in frames:
        cmds.currentTime(frame_value, edit=True)
        result[frame_value] = {node_name: _capture_pose(node_name, keep_rotation) for node_name in control_nodes}
    return result


def _format_report(report):
    if not report:
        return "Pick the hand or foot control, choose the first planted frame and the frame it lets go, then click Check Setup."

    lines = [
        "Controls: {0}".format(len(report.get("controls", []))),
        "Start Frame: {0}".format(int(report.get("start_frame", 0))),
        "End Frame: {0}".format(int(report.get("end_frame", 0))),
        "Keep Turn Too: {0}".format("Yes" if report.get("keep_rotation", True) else "No"),
        "",
    ]

    errors = report.get("errors", [])
    warnings = report.get("warnings", [])
    if errors:
        lines.append("RED")
        for item in errors:
            lines.append("- " + item)
        lines.append("")
    if warnings:
        lines.append("YELLOW")
        for item in warnings:
            lines.append("- " + item)
        lines.append("")
    if not errors and not warnings:
        lines.append("GREEN")
        lines.append("- This hold looks ready to bake.")
        lines.append("")

    if report.get("controls"):
        lines.append("Picked Controls")
        for node_name in report["controls"]:
            lines.append("- " + _short_name(node_name))

    suggestion = report.get("suggestion")
    if suggestion:
        lines.append("")
        lines.append("Suggested Plant Range")
        lines.append("- Frames: {0} to {1}".format(int(suggestion["start_frame"]), int(suggestion["end_frame"])))
        lines.append("- Calm move limit used: {0:.3f}".format(float(suggestion["move_threshold"])))
        lines.append("- Calm height limit used: {0:.3f}".format(float(suggestion["height_threshold"])))
        if report.get("keep_rotation") and suggestion.get("rotation_threshold") is not None:
            lines.append("- Calm turn limit used: {0:.3f}".format(float(suggestion["rotation_threshold"])))

    return "\n".join(lines).strip()


class MayaContactHoldController(object):
    def __init__(self):
        self.control_nodes = []
        self.start_frame = 1
        self.end_frame = 1
        self.keep_rotation = True
        self.key_before_after = True
        self.report = None
        self.last_suggestion = None
        self.status_callback = None
        if MAYA_AVAILABLE:
            current = _current_frame()
            self.start_frame = current
            self.end_frame = current

    def shutdown(self):
        pass

    def set_status_callback(self, callback):
        self.status_callback = callback

    def _set_status(self, message, success):
        if self.status_callback:
            self.status_callback(message, success)
        if success:
            _debug(message)
        else:
            _warning(message)

    def report_text(self):
        return _format_report(self.report)

    def set_controls_from_selection(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        control_nodes = _selected_controls()
        if not control_nodes:
            return False, "Pick one or more hand or foot controls first."
        self.control_nodes = control_nodes
        self.last_suggestion = None
        return True, "Picked {0} control(s).".format(len(control_nodes))

    def add_matching_other_side(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        if not self.control_nodes:
            return False, "Pick a hand or foot first, then add the matching other side."

        current_nodes = [_node_long_name(node_name) for node_name in self.control_nodes if node_name and cmds.objExists(node_name)]
        current_nodes = _dedupe_preserve_order(current_nodes)
        if not current_nodes:
            self.control_nodes = []
            return False, "Your picked controls are no longer in the scene."

        added_nodes = []
        notes = []
        for node_name in current_nodes:
            match, note = _find_other_side_control(node_name, taken_nodes=current_nodes + added_nodes)
            if match:
                added_nodes.append(match)
            elif note:
                notes.append(note)

        added_nodes = _dedupe_preserve_order(added_nodes)
        if not added_nodes:
            message = "I could not find a matching other-side control."
            if notes:
                message += " " + " ".join(notes)
            return False, message

        self.control_nodes = _dedupe_preserve_order(current_nodes + added_nodes)
        self.last_suggestion = None
        message = "Added {0} matching other-side control(s).".format(len(added_nodes))
        if notes:
            message += " " + " ".join(notes)
        return True, message

    def set_start_from_current(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        self.start_frame = _current_frame()
        if self.end_frame < self.start_frame:
            self.end_frame = self.start_frame
        return True, "Start frame set to {0}.".format(int(self.start_frame))

    def set_end_from_current(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        self.end_frame = _current_frame()
        if self.end_frame < self.start_frame:
            self.start_frame = self.end_frame
        return True, "End frame set to {0}.".format(int(self.end_frame))

    def suggest_range(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        controls = []
        for node_name in self.control_nodes:
            if node_name and cmds.objExists(node_name):
                controls.append(_node_long_name(node_name))
        controls = _dedupe_preserve_order(controls)
        if not controls:
            return False, "Pick one or more hand or foot controls first."

        suggestion = _suggest_contact_run(controls, _current_frame(), self.keep_rotation)
        if not suggestion:
            return False, "I could not find a calm planted range in the playback range yet."

        self.control_nodes = controls
        self.start_frame = int(suggestion["start_frame"])
        self.end_frame = int(suggestion["end_frame"])
        self.last_suggestion = suggestion
        return True, "Suggested frames {0} to {1} from the calmest nearby contact range.".format(self.start_frame, self.end_frame)

    def analyze_setup(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."

        controls = []
        errors = []
        warnings = []
        for node_name in self.control_nodes:
            if not node_name or not cmds.objExists(node_name):
                errors.append("One of the picked controls no longer exists.")
                continue
            controls.append(_node_long_name(node_name))
        controls = _dedupe_preserve_order(controls)

        if not controls:
            errors.append("Pick one or more hand or foot controls first.")
        if int(self.end_frame) < int(self.start_frame):
            errors.append("End Frame must be the same as or after Start Frame.")

        for node_name in controls:
            key_channels = _channels_for_hold(node_name, self.keep_rotation)
            if len([item for item in key_channels if item.startswith("translate")]) < 3:
                errors.append("{0} needs unlocked move channels so it can stay in place.".format(_short_name(node_name)))
            if self.keep_rotation and len([item for item in key_channels if item.startswith("rotate")]) < 3:
                errors.append("{0} needs unlocked turn channels, or turn off Keep Turn Too.".format(_short_name(node_name)))

        if int(self.start_frame) == int(self.end_frame):
            warnings.append("Start and End are the same frame, so this will only key one frame.")

        self.report = {
            "controls": controls,
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "keep_rotation": bool(self.keep_rotation),
            "key_before_after": bool(self.key_before_after),
            "suggestion": dict(self.last_suggestion) if self.last_suggestion else None,
            "errors": _dedupe_preserve_order(errors),
            "warnings": _dedupe_preserve_order(warnings),
        }

        if errors:
            return False, "This hold is not safe yet. Read the red notes below."
        if warnings:
            return True, "This hold can work, but read the yellow notes first."
        return True, "This hold looks ready."

    def apply_hold(self):
        if not self.report or self.report.get("errors"):
            success, message = self.analyze_setup()
            if not success:
                return False, message

        controls = list(self.report["controls"])
        start_frame = int(self.report["start_frame"])
        end_frame = int(self.report["end_frame"])
        keep_rotation = bool(self.report["keep_rotation"])
        current_time = float(cmds.currentTime(query=True))
        attributes = {node_name: _channels_for_hold(node_name, keep_rotation) for node_name in controls}

        if not all(attributes.values()):
            return False, "One or more controls could not be keyed."

        boundary_frames = []
        if self.key_before_after:
            boundary_frames = [start_frame - 1, end_frame + 1]
        boundary_frames = _dedupe_preserve_order(boundary_frames)

        try:
            cmds.undoInfo(openChunk=True, chunkName="MayaContactHold")
            boundary_poses = _capture_boundary_poses(controls, boundary_frames, keep_rotation) if boundary_frames else {}

            cmds.currentTime(start_frame, edit=True)
            anchor_poses = {node_name: _capture_pose(node_name, keep_rotation) for node_name in controls}

            for frame_value in range(start_frame, end_frame + 1):
                cmds.currentTime(frame_value, edit=True)
                for node_name in controls:
                    _apply_pose(node_name, anchor_poses[node_name], keep_rotation)
                    _set_keys(node_name, attributes[node_name])

            for frame_value in boundary_frames:
                poses = boundary_poses.get(frame_value, {})
                if not poses:
                    continue
                cmds.currentTime(frame_value, edit=True)
                for node_name in controls:
                    if node_name not in poses:
                        continue
                    _apply_pose(node_name, poses[node_name], keep_rotation)
                    _set_keys(node_name, attributes[node_name])
        except Exception as exc:
            _warning(traceback.format_exc())
            return False, "Could not make the hold: {0}".format(exc)
        finally:
            try:
                cmds.currentTime(current_time, edit=True)
            except Exception:
                pass
            try:
                cmds.undoInfo(closeChunk=True)
            except Exception:
                pass

        return True, "Kept {0} control(s) in place from frame {1} to {2}.".format(len(controls), start_frame, end_frame)


class _WindowBase(QtWidgets.QDialog if QtWidgets else object):
    pass


if QtWidgets:
    class MayaContactHoldWindow(_WindowBase):
        def __init__(self, controller, parent=None):
            super(MayaContactHoldWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller
            self.controller.set_status_callback(self._set_status)
            self.setObjectName(WINDOW_OBJECT_NAME)
            self.setWindowTitle("Maya Hand / Foot Hold")
            self.setMinimumWidth(640)
            self.setMinimumHeight(520)
            self._build_ui()
            self._sync_from_controller()

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            intro = QtWidgets.QLabel(
                "Keep a hand or foot exactly where it touches, even while the body keeps moving. "
                "This is good for planted feet, hands on props, and other contact moments."
            )
            intro.setWordWrap(True)
            main_layout.addWidget(intro)

            controls_row = QtWidgets.QHBoxLayout()
            self.controls_line = QtWidgets.QLineEdit()
            self.controls_line.setReadOnly(True)
            self.controls_line.setToolTip("The hand or foot controls this tool will keep in place.")
            self.use_selection_button = QtWidgets.QPushButton("Use Picked Hand / Foot")
            self.use_selection_button.setToolTip("Pick one or more hand or foot controls in Maya, then click this.")
            self.add_other_side_button = QtWidgets.QPushButton("Add Matching Other Side")
            self.add_other_side_button.setToolTip("Try to find the other hand or foot that matches the one you picked, like left foot to right foot.")
            controls_row.addWidget(QtWidgets.QLabel("Picked Controls"))
            controls_row.addWidget(self.controls_line, 1)
            controls_row.addWidget(self.use_selection_button)
            controls_row.addWidget(self.add_other_side_button)
            main_layout.addLayout(controls_row)

            frame_grid = QtWidgets.QGridLayout()
            self.start_spin = QtWidgets.QSpinBox()
            self.start_spin.setRange(-100000, 100000)
            self.start_spin.setToolTip("The first frame where the hand or foot should stay planted.")
            self.use_start_button = QtWidgets.QPushButton("Use Current For Start")
            self.use_start_button.setToolTip("Go to the first planted frame in Maya, then click this.")
            self.end_spin = QtWidgets.QSpinBox()
            self.end_spin.setRange(-100000, 100000)
            self.end_spin.setToolTip("The last frame where the hand or foot should stay planted.")
            self.use_end_button = QtWidgets.QPushButton("Use Current For End")
            self.use_end_button.setToolTip("Go to the frame where the hand or foot stops sticking, then click this.")
            self.suggest_range_button = QtWidgets.QPushButton("Suggest Range")
            self.suggest_range_button.setToolTip("Look through the playback range and guess a calm planted range near the current frame.")
            frame_grid.addWidget(QtWidgets.QLabel("Start Frame"), 0, 0)
            frame_grid.addWidget(self.start_spin, 0, 1)
            frame_grid.addWidget(self.use_start_button, 0, 2)
            frame_grid.addWidget(QtWidgets.QLabel("End Frame"), 1, 0)
            frame_grid.addWidget(self.end_spin, 1, 1)
            frame_grid.addWidget(self.use_end_button, 1, 2)
            frame_grid.addWidget(self.suggest_range_button, 2, 1, 1, 2)
            main_layout.addLayout(frame_grid)

            self.keep_rotation_check = QtWidgets.QCheckBox("Keep Turn Too")
            self.keep_rotation_check.setToolTip("Leave this on if the hand or foot should keep the same turn as well as the same position.")
            self.key_neighbors_check = QtWidgets.QCheckBox("Add Clean Keys Before And After")
            self.key_neighbors_check.setToolTip("This adds a helper key just before and just after the hold so the change is cleaner.")
            main_layout.addWidget(self.keep_rotation_check)
            main_layout.addWidget(self.key_neighbors_check)

            button_row = QtWidgets.QHBoxLayout()
            self.analyze_button = QtWidgets.QPushButton("Check Setup")
            self.analyze_button.setToolTip("Check that the picked controls and frame range are ready.")
            self.apply_button = QtWidgets.QPushButton("Hold Still")
            self.apply_button.setToolTip("Bake the picked hand or foot so it stays in the same place over the chosen frames.")
            button_row.addWidget(self.analyze_button)
            button_row.addWidget(self.apply_button)
            main_layout.addLayout(button_row)

            self.report_box = QtWidgets.QPlainTextEdit()
            self.report_box.setReadOnly(True)
            self.report_box.setToolTip("Helpful notes about the current hold setup.")
            main_layout.addWidget(self.report_box, 1)

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
            _style_donate_button(self.donate_button)
            self.donate_button.setToolTip("Open Amir's PayPal donate link. Set AMIR_PAYPAL_DONATE_URL or AMIR_DONATE_URL to customize it.")
            self.donate_button.clicked.connect(self._open_donate_url)
            footer_layout.addWidget(self.donate_button)
            main_layout.addLayout(footer_layout)

            self.use_selection_button.clicked.connect(self._use_selection)
            self.add_other_side_button.clicked.connect(self._add_other_side)
            self.use_start_button.clicked.connect(self._use_start_frame)
            self.use_end_button.clicked.connect(self._use_end_frame)
            self.suggest_range_button.clicked.connect(self._suggest_range)
            self.keep_rotation_check.toggled.connect(self._sync_to_controller)
            self.key_neighbors_check.toggled.connect(self._sync_to_controller)
            self.start_spin.valueChanged.connect(self._sync_to_controller)
            self.end_spin.valueChanged.connect(self._sync_to_controller)
            self.analyze_button.clicked.connect(self._analyze)
            self.apply_button.clicked.connect(self._apply)

        def _sync_from_controller(self):
            self.controls_line.setText(", ".join(_short_name(node_name) for node_name in self.controller.control_nodes))
            self.start_spin.setValue(int(self.controller.start_frame))
            self.end_spin.setValue(int(self.controller.end_frame))
            self.keep_rotation_check.setChecked(bool(self.controller.keep_rotation))
            self.key_neighbors_check.setChecked(bool(self.controller.key_before_after))
            self.report_box.setPlainText(self.controller.report_text())

        def _sync_to_controller(self):
            self.controller.start_frame = int(self.start_spin.value())
            self.controller.end_frame = int(self.end_spin.value())
            self.controller.keep_rotation = bool(self.keep_rotation_check.isChecked())
            self.controller.key_before_after = bool(self.key_neighbors_check.isChecked())

        def _set_status(self, message, success=True):
            self.status_label.setText(message)
            palette = self.status_label.palette()
            role = self.status_label.foregroundRole()
            palette.setColor(role, QtGui.QColor("#24A148" if success else "#DA1E28"))
            self.status_label.setPalette(palette)
            self.report_box.setPlainText(self.controller.report_text())

        def _use_selection(self):
            success, message = self.controller.set_controls_from_selection()
            self._sync_from_controller()
            self._set_status(message, success)

        def _add_other_side(self):
            success, message = self.controller.add_matching_other_side()
            self._sync_from_controller()
            self._set_status(message, success)

        def _use_start_frame(self):
            success, message = self.controller.set_start_from_current()
            self._sync_from_controller()
            self._set_status(message, success)

        def _use_end_frame(self):
            success, message = self.controller.set_end_from_current()
            self._sync_from_controller()
            self._set_status(message, success)

        def _suggest_range(self):
            self._sync_to_controller()
            success, message = self.controller.suggest_range()
            self._sync_from_controller()
            self._set_status(message, success)

        def _analyze(self):
            self._sync_to_controller()
            success, message = self.controller.analyze_setup()
            self._sync_from_controller()
            self._set_status(message, success)

        def _apply(self):
            self._sync_to_controller()
            success, message = self.controller.apply_hold()
            self._sync_from_controller()
            self._set_status(message, success)

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


if QtWidgets:
    def _delete_workspace_control(name):
        if MAYA_AVAILABLE and cmds and cmds.workspaceControl(name, exists=True):
            cmds.deleteUI(name)


def launch_maya_contact_hold(dock=False):
    global GLOBAL_CONTROLLER, GLOBAL_WINDOW
    if not (MAYA_AVAILABLE and QtWidgets):
        raise RuntimeError("Maya Contact Hold must be launched inside Maya with PySide available.")

    _close_existing_window()
    if dock:
        _delete_workspace_control(WORKSPACE_CONTROL_NAME)

    GLOBAL_CONTROLLER = MayaContactHoldController()
    GLOBAL_WINDOW = MayaContactHoldWindow(GLOBAL_CONTROLLER, parent=_maya_main_window())
    GLOBAL_WINDOW.show()
    return GLOBAL_WINDOW


__all__ = [
    "DONATE_URL",
    "FOLLOW_AMIR_URL",
    "MayaContactHoldController",
    "MayaContactHoldWindow",
    "launch_maya_contact_hold",
]
