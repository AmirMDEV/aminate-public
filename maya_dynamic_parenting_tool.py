"""
maya_dynamic_parenting_tool.py

Simple scene-backed dynamic parenting for props and controls.
"""

from __future__ import absolute_import, division, print_function

import json
import math
import os
import uuid

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
except Exception:
    try:
        from PySide2 import QtCore, QtGui, QtWidgets
        import shiboken2 as shiboken
    except Exception:
        QtCore = None
        QtGui = None
        QtWidgets = None
        shiboken = None


WINDOW_OBJECT_NAME = "mayaDynamicParentingWindow"
FOLLOW_AMIR_URL = "https://followamir.com"
DEFAULT_DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=2U2GXSKFJKJCA"
DONATE_URL = os.environ.get("AMIR_PAYPAL_DONATE_URL") or os.environ.get("AMIR_DONATE_URL") or DEFAULT_DONATE_URL
ROOT_GROUP_NAME = "amirDynamicParentingSystems_GRP"
WORLD_LOCATOR_NAME = "amirDynamicParentingWorld_LOC"
SETUP_TYPE = "amirDynamicParentSetupV2"
TARGETS_GROUP_SUFFIX = "_adpTargets_GRP"
TARGET_LOCATOR_SUFFIX = "_adpTarget_LOC"
DRIVEN_CONSTRAINT_SUFFIX = "_adpDriven_parentConstraint"
FOLLOW_CONSTRAINT_SUFFIX = "_adpFollow_parentConstraint"
EPSILON = 1.0e-4
DEFAULT_SWITCH_STEP = 1.0
ROTATE_ORDER_TO_EULER = (
    om.MEulerRotation.kXYZ if om else 0,
    om.MEulerRotation.kYZX if om else 1,
    om.MEulerRotation.kZXY if om else 2,
    om.MEulerRotation.kXZY if om else 3,
    om.MEulerRotation.kYXZ if om else 4,
    om.MEulerRotation.kZYX if om else 5,
)


def _debug(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayInfo("[Maya Dynamic Parenting] {0}".format(message))


def _warning(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayWarning("[Maya Dynamic Parenting] {0}".format(message))


def _qt_flag(scope_name, member_name, fallback=None):
    if not QtCore:
        return fallback
    if hasattr(QtCore.Qt, member_name):
        return getattr(QtCore.Qt, member_name)
    scoped_enum = getattr(QtCore.Qt, scope_name, None)
    if scoped_enum and hasattr(scoped_enum, member_name):
        return getattr(scoped_enum, member_name)
    return fallback


def _style_donate_button(button):
    if not button or not QtWidgets:
        return
    button.setMinimumWidth(92)
    button.setStyleSheet(
        """
        QPushButton {
            background-color: #FFC439;
            color: #111111;
            border: 1px solid #D9A000;
            border-radius: 5px;
            font-weight: 600;
            padding: 4px 12px;
        }
        QPushButton:hover {
            background-color: #FFD55C;
            border-color: #C89200;
        }
        QPushButton:pressed {
            background-color: #E6B12E;
            border-color: #AD7A00;
        }
        """
    )


def _open_external_url(url):
    if not url or not QtGui:
        return False
    return QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))


def _maya_main_window():
    if not (MAYA_AVAILABLE and QtWidgets and shiboken and omui):
        return None
    pointer = omui.MQtUtil.mainWindow()
    if not pointer:
        return None
    return shiboken.wrapInstance(int(pointer), QtWidgets.QWidget)


def _dedupe_preserve_order(items):
    result = []
    seen = set()
    for item in items or []:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _short_name(node_name):
    return (node_name or "").split("|")[-1].split(":")[-1]


def _safe_node_name(node_name):
    return "".join(character if character.isalnum() else "_" for character in _short_name(node_name)).strip("_") or "node"


def _frame_display(frame_value):
    value = float(frame_value)
    if abs(value - round(value)) < 1.0e-3:
        return str(int(round(value)))
    return "{0:.2f}".format(value).rstrip("0").rstrip(".")


def _selected_transforms():
    if not MAYA_AVAILABLE:
        return []
    return _dedupe_preserve_order(cmds.ls(selection=True, long=True, type="transform") or [])


def _matrix_to_list(matrix):
    return [matrix[index] for index in range(16)]


def _matrix_from_node(node_name):
    return om.MMatrix(cmds.xform(node_name, query=True, matrix=True, worldSpace=True))


def _set_world_matrix(node_name, matrix):
    cmds.xform(node_name, worldSpace=True, matrix=_matrix_to_list(matrix))


def _set_world_translation_rotation_preserve_scale(node_name, matrix):
    if not om:
        _set_world_matrix(node_name, matrix)
        return
    transform = om.MTransformationMatrix(matrix)
    translation = transform.translation(om.MSpace.kWorld)
    rotation = transform.rotation(asQuaternion=True).asEulerRotation()
    rotate_order = 0
    if cmds.objExists(node_name + ".rotateOrder"):
        try:
            rotate_order = int(cmds.getAttr(node_name + ".rotateOrder"))
        except Exception:
            rotate_order = 0
    rotation.reorderIt(ROTATE_ORDER_TO_EULER[rotate_order])
    cmds.xform(
        node_name,
        worldSpace=True,
        translation=(translation.x, translation.y, translation.z),
    )
    cmds.xform(
        node_name,
        worldSpace=True,
        rotation=tuple(math.degrees(angle) for angle in (rotation.x, rotation.y, rotation.z)),
    )


def _set_keyable_channels(node_name, attrs):
    for attr_name in attrs:
        plug = "{0}.{1}".format(node_name, attr_name)
        if not cmds.objExists(plug):
            continue
        try:
            if cmds.getAttr(plug, lock=True):
                continue
            cmds.setKeyframe(node_name, attribute=attr_name)
        except Exception:
            pass


def _dynamic_parent_blend_attrs(node_name):
    attrs = []
    for attr_name in cmds.listAttr(node_name, keyable=True) or []:
        lower_name = attr_name.lower()
        if not lower_name.startswith("blend"):
            continue
        if "adpdrivenparent" in lower_name or "parent" in lower_name:
            attrs.append(attr_name)
    if attrs:
        return attrs
    return [attr_name for attr_name in (cmds.listAttr(node_name, keyable=True) or []) if attr_name.lower().startswith("blend")]


def _get_blend_attr_values(node_name):
    values = {}
    for attr_name in _dynamic_parent_blend_attrs(node_name):
        plug = "{0}.{1}".format(node_name, attr_name)
        if not cmds.objExists(plug):
            continue
        try:
            values[attr_name] = float(cmds.getAttr(plug))
        except Exception:
            continue
    return values


def _set_blend_attr_values(node_name, values, keyframe=True):
    for attr_name, value in (values or {}).items():
        plug = "{0}.{1}".format(node_name, attr_name)
        if not cmds.objExists(plug):
            continue
        try:
            cmds.setAttr(plug, float(value))
            if keyframe:
                cmds.setKeyframe(node_name, attribute=attr_name)
        except Exception:
            pass


def _ensure_attr(node_name, attr_name, attr_type="string", default_value=None):
    if cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return
    if attr_type == "string":
        cmds.addAttr(node_name, longName=attr_name, dataType="string")
    elif attr_type == "bool":
        kwargs = {"attributeType": "bool"}
        if default_value is not None:
            kwargs["defaultValue"] = bool(default_value)
        cmds.addAttr(node_name, longName=attr_name, **kwargs)
    else:
        cmds.addAttr(node_name, longName=attr_name, attributeType=attr_type)


def _set_string_attr(node_name, attr_name, value):
    _ensure_attr(node_name, attr_name, "string")
    cmds.setAttr("{0}.{1}".format(node_name, attr_name), value or "", type="string")


def _get_string_attr(node_name, attr_name, default=""):
    if not cmds.objExists(node_name) or not cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return default
    value = cmds.getAttr("{0}.{1}".format(node_name, attr_name))
    return value if value is not None else default


def _get_bool_attr(node_name, attr_name, default=False):
    if not cmds.objExists(node_name) or not cmds.attributeQuery(attr_name, node=node_name, exists=True):
        return bool(default)
    try:
        return bool(cmds.getAttr("{0}.{1}".format(node_name, attr_name)))
    except Exception:
        return bool(default)


def _get_json_attr(node_name, attr_name, default=None):
    default = [] if default is None else default
    raw_value = _get_string_attr(node_name, attr_name, "")
    if not raw_value:
        return default
    try:
        payload = json.loads(raw_value)
    except Exception:
        return default
    return payload if isinstance(payload, type(default)) else default


def _parent_constraint_targets(constraint_name):
    targets = cmds.parentConstraint(constraint_name, query=True, targetList=True) or []
    aliases = cmds.parentConstraint(constraint_name, query=True, weightAliasList=True) or []
    mapping = {}
    for index, target in enumerate(targets):
        mapping[target] = aliases[index] if index < len(aliases) else ""
    return mapping


def _constraint_weight(constraint_name, target_name):
    alias = _parent_constraint_targets(constraint_name).get(target_name, "")
    if not alias:
        return 0.0
    try:
        return float(cmds.getAttr("{0}.{1}".format(constraint_name, alias)))
    except Exception:
        return 0.0


def _set_constraint_weights(constraint_name, weight_map, keyframe=True):
    target_map = _parent_constraint_targets(constraint_name)
    for target_name, alias in target_map.items():
        if not alias:
            continue
        value = float(weight_map.get(target_name, 0.0))
        cmds.setAttr("{0}.{1}".format(constraint_name, alias), value)
        if keyframe:
            try:
                cmds.setKeyframe(constraint_name, attribute=alias)
            except Exception:
                pass


def _ensure_root_hierarchy():
    if cmds.objExists(ROOT_GROUP_NAME):
        root_group = ROOT_GROUP_NAME
    else:
        root_group = cmds.createNode("transform", name=ROOT_GROUP_NAME)
    if cmds.objExists(WORLD_LOCATOR_NAME):
        world_locator = WORLD_LOCATOR_NAME
    else:
        world_locator = cmds.spaceLocator(name=WORLD_LOCATOR_NAME)[0]
        cmds.parent(world_locator, root_group)
        cmds.setAttr(world_locator + ".visibility", 0)
    return root_group, world_locator


def _find_setup_groups():
    if not MAYA_AVAILABLE or not cmds.objExists(ROOT_GROUP_NAME):
        return []
    children = cmds.listRelatives(ROOT_GROUP_NAME, children=True, type="transform", fullPath=True) or []
    return [child for child in children if _get_string_attr(child, "adpSetupType") == SETUP_TYPE]


def _save_target_entries(setup_group, entries):
    _set_string_attr(setup_group, "adpTargetsJson", json.dumps(entries, sort_keys=True))


def _save_event_log(setup_group, events):
    _set_string_attr(setup_group, "adpEventLog", json.dumps(events, sort_keys=True))


def _find_setup_for_driven(driven_node):
    if not driven_node:
        return None
    long_name = (cmds.ls(driven_node, long=True) or [driven_node])[0]
    for setup_group in _find_setup_groups():
        if _get_string_attr(setup_group, "adpDriven") == long_name:
            return setup_group
    return None


def _load_setup_data(setup_group):
    if not setup_group or not cmds.objExists(setup_group):
        return None
    driven_node = _get_string_attr(setup_group, "adpDriven")
    if not driven_node or not cmds.objExists(driven_node):
        return None
    data = {
        "setup_group": setup_group,
        "driven": driven_node,
        "label": _get_string_attr(setup_group, "adpLabel", _short_name(driven_node)),
        "targets_group": _get_string_attr(setup_group, "adpTargetsGroup"),
        "driven_constraint": _get_string_attr(setup_group, "adpDrivenConstraint"),
        "maintain_offset": _get_bool_attr(setup_group, "adpMaintainOffset", True),
        "targets": [],
        "event_log": _get_json_attr(setup_group, "adpEventLog", []),
    }
    for entry in _get_json_attr(setup_group, "adpTargetsJson", []):
        locator_name = entry.get("locator", "")
        if not locator_name or not cmds.objExists(locator_name):
            continue
        follow_constraint = entry.get("follow_constraint", "")
        driver_node = entry.get("driver", "")
        if driver_node and not cmds.objExists(driver_node):
            driver_node = ""
        data["targets"].append(
            {
                "id": entry.get("id", ""),
                "label": entry.get("label") or ("World" if entry.get("is_world") else _short_name(driver_node or locator_name)),
                "driver": driver_node,
                "locator": locator_name,
                "follow_constraint": follow_constraint if follow_constraint and cmds.objExists(follow_constraint) else "",
                "is_world": bool(entry.get("is_world")),
            }
        )
    return data


class MayaDynamicParentingController(object):
    def __init__(self):
        self.active_setup_group = ""
        self.pending_target_node = ""
        self.maintain_offset = True
        self.status_callback = None

    def set_status_callback(self, callback):
        self.status_callback = callback

    def _set_status(self, message, ok=True):
        if self.status_callback:
            self.status_callback(message, ok)
        if ok:
            _debug(message)
        else:
            _warning(message)

    def all_setups(self):
        return [item for item in (_load_setup_data(group) for group in _find_setup_groups()) if item]

    def setup_payloads(self, from_selection=False):
        if from_selection:
            selected = []
            for node_name in _selected_transforms():
                setup_group = _find_setup_for_driven(node_name)
                if setup_group:
                    selected.append(setup_group)
            seen = set()
            payloads = []
            for setup_group in selected:
                if setup_group in seen:
                    continue
                seen.add(setup_group)
                data = _load_setup_data(setup_group)
                if data:
                    payloads.append(self._payload_for_setup(data))
            return payloads
        return [self._payload_for_setup(item) for item in self.all_setups()]

    def _payload_for_setup(self, setup_data):
        current_weights = self.current_weights(setup_data)
        active_names = [
            "{0} ({1:.2f})".format(target["label"], current_weights.get(target["id"], 0.0))
            for target in setup_data["targets"]
            if current_weights.get(target["id"], 0.0) > EPSILON
        ]
        return {
            "setup_group": setup_data["setup_group"],
            "driven": setup_data["driven"],
            "label": setup_data["label"],
            "maintain_offset": setup_data["maintain_offset"],
            "targets": list(setup_data["targets"]),
            "event_log": list(setup_data["event_log"]),
            "current_weights": current_weights,
            "state_text": ", ".join(active_names) if active_names else "Nothing active",
        }

    def current_setup(self):
        if self.active_setup_group:
            data = _load_setup_data(self.active_setup_group)
            if data:
                return data
        for node_name in _selected_transforms():
            setup_group = _find_setup_for_driven(node_name)
            if setup_group:
                self.active_setup_group = setup_group
                data = _load_setup_data(setup_group)
                if data:
                    self.maintain_offset = bool(data["maintain_offset"])
                return data
        all_setups = self.all_setups()
        if all_setups:
            self.active_setup_group = all_setups[0]["setup_group"]
            self.maintain_offset = bool(all_setups[0]["maintain_offset"])
            return all_setups[0]
        self.active_setup_group = ""
        return None

    def set_active_setup(self, setup_group):
        data = _load_setup_data(setup_group)
        if not data:
            return False, "Pick an object from the list first."
        self.active_setup_group = setup_group
        self.maintain_offset = bool(data["maintain_offset"])
        return True, "Now editing {0}.".format(data["label"])

    def _create_world_target_entry(self, driven_node, targets_group):
        locator_name = cmds.spaceLocator(name="{0}_world{1}".format(_safe_node_name(driven_node), TARGET_LOCATOR_SUFFIX))[0]
        locator_name = cmds.parent(locator_name, targets_group)[0]
        cmds.setAttr(locator_name + ".visibility", 0)
        _set_world_matrix(locator_name, _matrix_from_node(driven_node))
        return {
            "id": "world",
            "label": "World",
            "driver": "",
            "locator": locator_name,
            "follow_constraint": "",
            "is_world": True,
        }

    def _ensure_setup(self, driven_node):
        driven_node = (cmds.ls(driven_node, long=True) or [driven_node])[0]
        existing = _find_setup_for_driven(driven_node)
        if existing:
            data = _load_setup_data(existing)
            if data:
                return data, False, "{0} is already in the constrained-object list.".format(data["label"])

        root_group, _world_locator = _ensure_root_hierarchy()
        safe_name = _safe_node_name(driven_node)
        setup_group = cmds.createNode("transform", name="{0}_adpSetup_GRP".format(safe_name), parent=root_group)
        targets_group = cmds.createNode("transform", name="{0}{1}".format(safe_name, TARGETS_GROUP_SUFFIX), parent=setup_group)
        _set_string_attr(setup_group, "adpSetupType", SETUP_TYPE)
        _set_string_attr(setup_group, "adpDriven", driven_node)
        _set_string_attr(setup_group, "adpTargetsGroup", targets_group)
        _set_string_attr(setup_group, "adpLabel", _short_name(driven_node))
        _ensure_attr(setup_group, "adpMaintainOffset", "bool", default_value=True)
        cmds.setAttr(setup_group + ".adpMaintainOffset", 1)

        world_entry = self._create_world_target_entry(driven_node, targets_group)
        driven_constraint = cmds.parentConstraint(
            world_entry["locator"],
            driven_node,
            maintainOffset=False,
            name="{0}{1}".format(safe_name, DRIVEN_CONSTRAINT_SUFFIX),
        )[0]
        _set_string_attr(setup_group, "adpDrivenConstraint", driven_constraint)
        _save_target_entries(setup_group, [world_entry])
        _save_event_log(setup_group, [])
        data = _load_setup_data(setup_group)
        self.active_setup_group = setup_group
        self.maintain_offset = True
        return data, True, "Added {0} as a constrained object.".format(_short_name(driven_node))

    def add_driven_from_nodes(self, driven_nodes):
        created = []
        messages = []
        for node_name in _dedupe_preserve_order(driven_nodes or []):
            if not cmds.objExists(node_name):
                continue
            data, _was_created, message = self._ensure_setup(node_name)
            if data:
                created.append(data)
            messages.append(message)
        if not created:
            return False, "Pick one or more props or controls first."
        self.active_setup_group = created[-1]["setup_group"]
        self.maintain_offset = bool(created[-1]["maintain_offset"])
        return True, "\n".join(messages)

    def add_driven_from_selection(self):
        return self.add_driven_from_nodes(_selected_transforms())

    def remove_active_setup(self):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a constrained object from the list first."
        label = setup["label"]
        try:
            cmds.delete(setup["setup_group"])
        except Exception:
            pass
        self.active_setup_group = ""
        return True, "Removed {0} from the constrained-object list.".format(label)

    def rename_active_setup(self, label_text):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a constrained object from the list first."
        label_text = (label_text or "").strip() or _short_name(setup["driven"])
        _set_string_attr(setup["setup_group"], "adpLabel", label_text)
        return True, "Renamed this list entry to {0}.".format(label_text)

    def set_pending_target_from_selection(self):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        for node_name in reversed(_selected_transforms()):
            if node_name == setup["driven"]:
                continue
            self.pending_target_node = node_name
            return True, "Picked {0} as the next parent choice.".format(_short_name(node_name))
        return False, "Pick the constrained object first, then also pick the hand, gun, or object it should follow."

    def _target_entry_by_id(self, setup, target_id):
        for target in setup["targets"]:
            if target["id"] == target_id:
                return target
        return None

    def _target_entry_by_driver(self, setup, driver_node):
        for target in setup["targets"]:
            if target["driver"] == driver_node:
                return target
        return None

    def _target_snap_matrix(self, target_entry):
        if not target_entry:
            return None
        if target_entry.get("driver") and cmds.objExists(target_entry["driver"]):
            return _matrix_from_node(target_entry["driver"])
        if target_entry.get("locator") and cmds.objExists(target_entry["locator"]):
            return _matrix_from_node(target_entry["locator"])
        return None

    def _save_targets(self, setup, targets):
        serialized = []
        for target in targets:
            serialized.append(
                {
                    "id": target["id"],
                    "label": target["label"],
                    "driver": target["driver"],
                    "locator": target["locator"],
                    "follow_constraint": target["follow_constraint"],
                    "is_world": bool(target["is_world"]),
                }
            )
        _save_target_entries(setup["setup_group"], serialized)

    def add_targets_from_nodes(self, target_nodes):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        targets = list(setup["targets"])
        added_labels = []
        for target_node in _dedupe_preserve_order(target_nodes or []):
            if not cmds.objExists(target_node):
                continue
            target_node = (cmds.ls(target_node, long=True) or [target_node])[0]
            if target_node == setup["driven"]:
                continue
            existing = self._target_entry_by_driver(setup, target_node)
            if existing:
                continue
            locator_name = cmds.spaceLocator(name="{0}{1}".format(_safe_node_name(target_node), TARGET_LOCATOR_SUFFIX))[0]
            locator_name = cmds.parent(locator_name, setup["targets_group"])[0]
            cmds.setAttr(locator_name + ".visibility", 0)
            _set_world_matrix(locator_name, _matrix_from_node(setup["driven"]))
            follow_constraint = cmds.parentConstraint(
                target_node,
                locator_name,
                maintainOffset=True,
                name="{0}{1}".format(_safe_node_name(target_node), FOLLOW_CONSTRAINT_SUFFIX),
            )[0]
            cmds.parentConstraint(locator_name, setup["driven"], edit=True, weight=0.0)
            target_entry = {
                "id": uuid.uuid4().hex[:8],
                "label": _short_name(target_node),
                "driver": target_node,
                "locator": locator_name,
                "follow_constraint": follow_constraint,
                "is_world": False,
            }
            targets.append(target_entry)
            added_labels.append(target_entry["label"])
        if not added_labels:
            return False, "Pick at least one new hand, gun, or object to add."
        self._save_targets(setup, targets)
        return True, "Added parent choices: {0}.".format(", ".join(added_labels))

    def add_targets_from_selection(self):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        target_nodes = [node_name for node_name in _selected_transforms() if node_name != setup["driven"]]
        return self.add_targets_from_nodes(target_nodes)

    def set_maintain_offset(self, enabled):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a constrained object from the list first."
        cmds.setAttr(setup["setup_group"] + ".adpMaintainOffset", int(bool(enabled)))
        self.maintain_offset = bool(enabled)
        return True, "Maintain Current Offset is now {0}.".format("on" if enabled else "off")

    def snap_to_target_id(self, target_id):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        target_entry = self._target_entry_by_id(setup, target_id)
        if not target_entry:
            return False, "Pick a parent first."
        if target_entry.get("is_world"):
            return False, "World does not have a snap place. Move the object by hand, then switch to World."
        target_matrix = self._target_snap_matrix(target_entry)
        if target_matrix is None:
            return False, "That parent is missing."
        _set_world_translation_rotation_preserve_scale(setup["driven"], target_matrix)
        return True, "Snapped {0} onto {1}. Move it if you want, then click Switch.".format(
            setup["label"],
            target_entry["label"],
        )

    def current_weights(self, setup=None):
        setup = setup or self.current_setup()
        if not setup or not setup.get("driven_constraint") or not cmds.objExists(setup["driven_constraint"]):
            return {}
        weights = {}
        for target in setup["targets"]:
            weights[target["id"]] = _constraint_weight(setup["driven_constraint"], target["locator"])
        return weights

    def _sanitize_weight_map(self, setup, weight_map):
        sanitized = {}
        total = 0.0
        for target in setup["targets"]:
            value = float(weight_map.get(target["id"], 0.0))
            value = max(0.0, min(1.0, value))
            sanitized[target["id"]] = value
            total += value
        return sanitized, total

    def _active_weight_labels(self, setup, weight_map):
        labels = []
        for target in setup["targets"]:
            weight_value = float(weight_map.get(target["id"], 0.0))
            if weight_value > EPSILON:
                labels.append("{0} {1:.2f}".format(target["label"], weight_value))
        return labels

    def _active_target_names(self, setup, weight_map):
        names = []
        for target in setup["targets"]:
            if float(weight_map.get(target["id"], 0.0)) > EPSILON:
                names.append(target["label"])
        return names

    def _reseed_target(self, setup, target_entry, maintain_offset, reference_matrix=None):
        locator_name = target_entry["locator"]
        if not cmds.objExists(locator_name):
            return
        if target_entry["follow_constraint"] and cmds.objExists(target_entry["follow_constraint"]):
            try:
                cmds.delete(target_entry["follow_constraint"])
            except Exception:
                pass
            target_entry["follow_constraint"] = ""
        if target_entry["is_world"] or not target_entry["driver"]:
            _set_world_matrix(locator_name, reference_matrix or _matrix_from_node(setup["driven"]))
            return
        if maintain_offset:
            _set_world_matrix(locator_name, reference_matrix or _matrix_from_node(setup["driven"]))
        target_entry["follow_constraint"] = cmds.parentConstraint(
            target_entry["driver"],
            locator_name,
            maintainOffset=bool(maintain_offset),
            name="{0}{1}".format(_safe_node_name(target_entry["driver"]), FOLLOW_CONSTRAINT_SUFFIX),
        )[0]

    def _record_event(self, setup, action_label, weight_map):
        event_log = list(setup.get("event_log") or [])
        frame_value = float(cmds.currentTime(query=True))
        event_log = [
            item
            for item in event_log
            if abs(float(item.get("frame", 0.0)) - frame_value) >= EPSILON
        ]
        target_labels = {}
        for target in setup["targets"]:
            weight_value = float(weight_map.get(target["id"], 0.0))
            if weight_value > EPSILON:
                target_labels[target["label"]] = round(weight_value, 4)
        event_log.append(
            {
                "frame": frame_value,
                "action": action_label,
                "weights": target_labels,
                "maintain_offset": bool(setup.get("maintain_offset", True)),
            }
        )
        event_log.sort(key=lambda item: float(item.get("frame", 0.0)))
        _save_event_log(setup["setup_group"], event_log)
        setup["event_log"] = event_log

    def _key_weight_map_on_frame(self, setup, weight_map, maintain_offset, frame_value, action_label=None, record_event=False, reseed_active=False, reference_matrix=None):
        original_frame = float(cmds.currentTime(query=True))
        frame_value = float(frame_value)
        changed_time = abs(original_frame - frame_value) >= EPSILON
        if changed_time:
            cmds.currentTime(frame_value, edit=True)
        try:
            if reseed_active:
                for target in setup["targets"]:
                    if float(weight_map.get(target["id"], 0.0)) > EPSILON:
                        self._reseed_target(setup, target, maintain_offset, reference_matrix=reference_matrix)
                self._save_targets(setup, setup["targets"])
            constraint_weights = {}
            for target in setup["targets"]:
                constraint_weights[target["locator"]] = float(weight_map.get(target["id"], 0.0))
            _set_constraint_weights(setup["driven_constraint"], constraint_weights, keyframe=True)
            _set_keyable_channels(setup["driven"], ("translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"))
            if record_event and action_label:
                self._record_event(setup, action_label, weight_map)
        finally:
            if changed_time:
                cmds.currentTime(original_frame, edit=True)

    def _active_constraint_blend_values(self, setup, active=True):
        active_value = 1.0 if active else 0.0
        current_values = _get_blend_attr_values(setup["driven"])
        if current_values:
            return {attr_name: active_value for attr_name in current_values}
        return {}

    def apply_weight_map(self, weight_map, action_label="blend"):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        maintain_offset = bool(self.maintain_offset)
        cmds.setAttr(setup["setup_group"] + ".adpMaintainOffset", int(maintain_offset))
        sanitized, total = self._sanitize_weight_map(setup, weight_map)
        if total <= EPSILON:
            return False, "Turn at least one parent on before you key the weights."
        reference_matrix = _matrix_from_node(setup["driven"])
        self._key_weight_map_on_frame(
            setup,
            sanitized,
            maintain_offset,
            frame_value=float(cmds.currentTime(query=True)),
            action_label=action_label,
            record_event=True,
            reseed_active=True,
            reference_matrix=reference_matrix,
        )
        _set_blend_attr_values(setup["driven"], self._active_constraint_blend_values(setup, active=True), keyframe=True)
        return True, "Saved the parent weights on frame {0}.".format(_frame_display(cmds.currentTime(query=True)))

    def switch_weight_map_next_frame(self, weight_map, action_label="switch"):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        maintain_offset = bool(self.maintain_offset)
        cmds.setAttr(setup["setup_group"] + ".adpMaintainOffset", int(maintain_offset))
        sanitized, total = self._sanitize_weight_map(setup, weight_map)
        if total <= EPSILON:
            return False, "Turn at least one parent on before you switch."
        current_frame = float(cmds.currentTime(query=True))
        target_frame = current_frame + DEFAULT_SWITCH_STEP
        reference_matrix = _matrix_from_node(setup["driven"])
        current_weights = self.current_weights(setup)
        current_blend_values = _get_blend_attr_values(setup["driven"])
        self._key_weight_map_on_frame(
            setup,
            current_weights,
            maintain_offset,
            frame_value=current_frame,
            action_label=None,
            record_event=False,
            reseed_active=False,
        )
        if current_blend_values:
            original_frame = float(cmds.currentTime(query=True))
            cmds.currentTime(current_frame, edit=True)
            try:
                _set_blend_attr_values(setup["driven"], current_blend_values, keyframe=True)
            finally:
                cmds.currentTime(original_frame, edit=True)
        self._key_weight_map_on_frame(
            setup,
            sanitized,
            maintain_offset,
            frame_value=target_frame,
            action_label=action_label,
            record_event=True,
            reseed_active=True,
            reference_matrix=reference_matrix,
        )
        original_frame = float(cmds.currentTime(query=True))
        cmds.currentTime(target_frame, edit=True)
        try:
            _set_blend_attr_values(setup["driven"], self._active_constraint_blend_values(setup, active=True), keyframe=True)
        finally:
            cmds.currentTime(original_frame, edit=True)
        cmds.currentTime(target_frame, edit=True)
        active_target_names = self._active_target_names(setup, sanitized)
        if len(active_target_names) == 1:
            target_text = active_target_names[0]
        else:
            target_text = ", ".join(active_target_names)
        return True, "Kept the old parent on frame {0} and switched to {1} on frame {2}.".format(
            _frame_display(current_frame),
            target_text,
            _frame_display(target_frame),
        )

    def parent_fully_to_target(self, target_id, action_label="switch"):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        if not self._target_entry_by_id(setup, target_id):
            return False, "Pick a parent row first."
        weight_map = {}
        for target in setup["targets"]:
            weight_map[target["id"]] = 1.0 if target["id"] == target_id else 0.0
        return self.switch_weight_map_next_frame(weight_map, action_label=action_label)

    def parent_to_world(self):
        return self.parent_fully_to_target("world", action_label="world")

    def apply_pending_target(self):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        target_node = self.pending_target_node
        if not target_node or not cmds.objExists(target_node):
            return False, "Pick the next hand, gun, prop, or object first."
        existing = self._target_entry_by_driver(setup, target_node)
        if not existing:
            success, message = self.add_targets_from_nodes([target_node])
            if not success:
                return success, message
            setup = self.current_setup()
            existing = self._target_entry_by_driver(setup, target_node)
        return self.parent_fully_to_target(existing["id"], action_label="switch")

    def snap_pending_target(self):
        setup = self.current_setup()
        if not setup:
            return False, "Add or pick the constrained object first."
        target_node = self.pending_target_node
        if not target_node or not cmds.objExists(target_node):
            return False, "Pick the next hand, gun, prop, or object first."
        existing = self._target_entry_by_driver(setup, target_node)
        if not existing:
            success, message = self.add_targets_from_nodes([target_node])
            if not success:
                return success, message
            setup = self.current_setup()
            existing = self._target_entry_by_driver(setup, target_node)
        return self.snap_to_target_id(existing["id"])

    def reseed_active_weights(self):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a constrained object from the list first."
        return self.apply_weight_map(self.current_weights(setup), action_label="reseed")

    def remove_target_ids(self, target_ids):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a constrained object from the list first."
        target_ids = set(target_ids or [])
        targets = []
        removed = []
        for target in setup["targets"]:
            if target["id"] in target_ids and not target["is_world"]:
                removed.append(target["label"])
                try:
                    cmds.parentConstraint(target["locator"], setup["driven"], edit=True, remove=True)
                except Exception:
                    pass
                if target["follow_constraint"] and cmds.objExists(target["follow_constraint"]):
                    try:
                        cmds.delete(target["follow_constraint"])
                    except Exception:
                        pass
                if target["locator"] and cmds.objExists(target["locator"]):
                    try:
                        cmds.delete(target["locator"])
                    except Exception:
                        pass
                continue
            targets.append(target)
        if not removed:
            return False, "Pick a non-World parent row first."
        self._save_targets(setup, targets)
        return True, "Removed parent choices: {0}.".format(", ".join(removed))

    def event_items(self, setup=None):
        setup = setup or self.current_setup()
        if not setup:
            return []
        results = []
        for item in setup.get("event_log") or []:
            frame_value = float(item.get("frame", 0.0))
            weights = item.get("weights") or {}
            weight_text = ", ".join("{0} {1:.2f}".format(name, float(value)) for name, value in sorted(weights.items()))
            if not weight_text:
                weight_text = "nothing active"
            results.append(
                {
                    "frame": frame_value,
                    "display": "F{0}: {1} -> {2}".format(
                        _frame_display(frame_value),
                        item.get("action", "switch").title(),
                        weight_text,
                    ),
                }
            )
        return results

    def delete_event_frame(self, frame_value):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a saved object first."
        frame_value = float(frame_value)
        event_log = list(setup.get("event_log") or [])
        kept_events = [item for item in event_log if abs(float(item.get("frame", 0.0)) - frame_value) >= EPSILON]
        if len(kept_events) == len(event_log):
            return False, "Pick a saved switch first."
        _save_event_log(setup["setup_group"], kept_events)
        setup["event_log"] = kept_events
        return True, "Deleted the saved switch on frame {0}.".format(_frame_display(frame_value))

    def clear_event_log(self):
        setup = self.current_setup()
        if not setup:
            return False, "Pick a saved object first."
        if not (setup.get("event_log") or []):
            return False, "There are no saved switches to delete."
        _save_event_log(setup["setup_group"], [])
        setup["event_log"] = []
        return True, "Deleted all saved switches for {0}.".format(setup["label"])

    def jump_to_event(self, frame_value):
        cmds.currentTime(float(frame_value), edit=True)
        return True, "Jumped to frame {0}.".format(_frame_display(frame_value))

    def summary_text(self, setup=None):
        setup = setup or self.current_setup()
        if not setup:
            return "Add an object, then add the hands, guns, world, or other things it should follow."
        current_weights = self.current_weights(setup)
        lines = [
            "Object: {0}".format(setup["label"]),
            "Real node: {0}".format(setup["driven"]),
            "Maintain Current Offset: {0}".format("On" if setup["maintain_offset"] else "Off"),
            "Parents:",
        ]
        for target in setup["targets"]:
            lines.append("- {0}: {1:.2f}".format(target["label"], current_weights.get(target["id"], 0.0)))
        return "\n".join(lines)

    def shutdown(self):
        return


class _WindowBase(QtWidgets.QDialog if QtWidgets else object):
    pass


if QtWidgets:
    class MayaDynamicParentingWindow(_WindowBase):
        def __init__(self, controller, parent=None):
            super(MayaDynamicParentingWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller
            self.controller.set_status_callback(self._set_status)
            self._weight_widgets = {}
            self.setObjectName(WINDOW_OBJECT_NAME)
            self.setWindowTitle("Maya Dynamic Parenting")
            self.setMinimumWidth(720)
            self.setMinimumHeight(560)
            self._build_ui()
            self._sync_from_controller()

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            intro = QtWidgets.QLabel(
                "Make one object switch between hand, gun, world, or any other parent."
            )
            intro.setWordWrap(True)
            main_layout.addWidget(intro)

            step_box = QtWidgets.QGroupBox("How To Use")
            step_layout = QtWidgets.QVBoxLayout(step_box)
            for text in (
                "1. Pick the object that should move. Example: the magazine.",
                "2. Click Add Object.",
                "3. Pick the new parent. Example: the gun or the hand.",
                "4. Click Pick Parent.",
                "5. Choose one of these:",
                "   - Click Snap To Parent if you want the object to jump onto that parent now.",
                "   - Or move the object by hand, leave Maintain Current Offset on, and then click Switch to this Parent.",
                "6. Click World if you want it to stop following everything.",
            ):
                label = QtWidgets.QLabel(text)
                label.setWordWrap(True)
                step_layout.addWidget(label)
            example_label = QtWidgets.QLabel(
                "Example: Gun + Magazine\n"
                "Keep it exactly where it is:\n"
                "1. Pick the magazine.\n"
                "2. Click Add Object.\n"
                "3. Pick the gun.\n"
                "4. Click Pick Parent.\n"
                "5. Put the magazine exactly where you want it.\n"
                "6. Leave Maintain Current Offset on.\n"
                "7. Click Switch to this Parent.\n"
                "8. On the next frame, it follows the gun but stays in that exact place.\n\n"
                "Snap it onto the gun first:\n"
                "1. Pick the magazine.\n"
                "2. Pick the gun.\n"
                "3. Click Pick Parent.\n"
                "4. Click Snap To Parent.\n"
                "5. If needed, move it a little more.\n"
                "6. Click Switch to this Parent.\n\n"
                "Take it out with the hand:\n"
                "1. Pick the hand.\n"
                "2. Click Pick Parent.\n"
                "3. Move the magazine if needed.\n"
                "4. Click Switch to this Parent.\n\n"
                "Let go:\n"
                "1. Click World."
            )
            example_label.setWordWrap(True)
            step_layout.addWidget(example_label)
            main_layout.addWidget(step_box)

            object_row = QtWidgets.QHBoxLayout()
            self.objects_line = QtWidgets.QLineEdit()
            self.objects_line.setReadOnly(True)
            self.objects_line.setPlaceholderText("Pick the object that should switch parents, then add it here.")
            self.add_object_button = QtWidgets.QPushButton("Add Object")
            self.remove_object_button = QtWidgets.QPushButton("Remove Object")
            object_row.addWidget(QtWidgets.QLabel("Move Object"))
            object_row.addWidget(self.objects_line, 1)
            object_row.addWidget(self.add_object_button)
            object_row.addWidget(self.remove_object_button)
            main_layout.addLayout(object_row)

            list_row = QtWidgets.QHBoxLayout()
            self.object_list = QtWidgets.QListWidget()
            self.object_list.setToolTip("Every saved object in this scene that uses parent switching.")
            list_row.addWidget(self.object_list, 1)
            name_column = QtWidgets.QVBoxLayout()
            self.list_name_line = QtWidgets.QLineEdit()
            self.list_name_line.setPlaceholderText("Magazine")
            self.rename_button = QtWidgets.QPushButton("Rename")
            name_column.addWidget(QtWidgets.QLabel("Label"))
            name_column.addWidget(self.list_name_line)
            name_column.addWidget(self.rename_button)
            name_column.addStretch(1)
            list_row.addLayout(name_column)
            main_layout.addLayout(list_row)

            self.maintain_offset_check = QtWidgets.QCheckBox("Maintain Current Offset")
            self.maintain_offset_check.setChecked(True)
            self.maintain_offset_check.setToolTip("Leave this on if the object should stay where it is when the new parent turns on. Turn it off if it should snap.")
            main_layout.addWidget(self.maintain_offset_check)
            keep_position_hint = QtWidgets.QLabel(
                "Maintain Current Offset: keep the object exactly where it is, then switch.\n"
                "Snap To Parent: move it onto the parent first, then switch.\n"
                "Scale Safe: this tool should not change the object's scale."
            )
            keep_position_hint.setWordWrap(True)
            main_layout.addWidget(keep_position_hint)

            target_row = QtWidgets.QHBoxLayout()
            self.target_line = QtWidgets.QLineEdit()
            self.target_line.setReadOnly(True)
            self.target_line.setPlaceholderText("Pick a hand, gun, or other thing to follow.")
            self.use_target_button = QtWidgets.QPushButton("Pick Parent")
            self.use_target_button.setToolTip("Take the thing you picked and put it into the Parent To box.")
            self.snap_to_picked_button = QtWidgets.QPushButton("Snap To Parent")
            self.snap_to_picked_button.setToolTip("Move the object onto this parent now. You can still adjust it before you switch.")
            self.parent_to_picked_button = QtWidgets.QPushButton("Switch to this Parent")
            self.parent_to_picked_button.setToolTip("Keep the old parent on this frame, then turn this picked parent on next frame.")
            self.add_target_button = QtWidgets.QPushButton("Add Parent")
            self.add_target_button.setToolTip("Remember this parent so you can switch to it later.")
            target_row.addWidget(QtWidgets.QLabel("Parent To"))
            target_row.addWidget(self.target_line, 1)
            target_row.addWidget(self.use_target_button)
            target_row.addWidget(self.snap_to_picked_button)
            target_row.addWidget(self.parent_to_picked_button)
            main_layout.addLayout(target_row)

            switch_hint = QtWidgets.QLabel(
                "You can also move the object by hand in the viewport before you click Switch to this Parent. "
                "If Maintain Current Offset is on, the switch keeps that exact spot."
            )
            switch_hint.setWordWrap(True)
            main_layout.addWidget(switch_hint)

            self.targets_table = QtWidgets.QTableWidget(0, 4)
            self.targets_table.setHorizontalHeaderLabels(["Parent", "Weight", "On", "Switch"])
            self.targets_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.targets_table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.targets_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            header = self.targets_table.horizontalHeader()
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            main_layout.addWidget(self.targets_table, 1)

            action_row = QtWidgets.QHBoxLayout()
            self.parent_to_row_button = QtWidgets.QPushButton("Reparent to Selected Parent")
            self.parent_to_row_button.setToolTip("Use the parent row you picked and switch to it on the next frame.")
            self.parent_to_world_button = QtWidgets.QPushButton("World")
            self.parent_to_world_button.setToolTip("Stop following everything and switch to World on the next frame.")
            action_row.addWidget(self.parent_to_row_button)
            action_row.addWidget(self.parent_to_world_button)
            main_layout.addLayout(action_row)

            self.advanced_toggle = QtWidgets.QToolButton()
            self.advanced_toggle.setText("More")
            self.advanced_toggle.setCheckable(True)
            self.advanced_toggle.setChecked(False)
            self.advanced_toggle.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
            main_layout.addWidget(self.advanced_toggle)

            self.advanced_widget = QtWidgets.QWidget()
            self.advanced_widget.setVisible(False)
            advanced_layout = QtWidgets.QVBoxLayout(self.advanced_widget)
            advanced_layout.setContentsMargins(0, 0, 0, 0)

            advanced_actions = QtWidgets.QHBoxLayout()
            self.add_target_button.setParent(self.advanced_widget)
            self.apply_weights_button = QtWidgets.QPushButton("Blend Parents")
            self.apply_weights_button.setToolTip("Save the weights you see now on this frame, like half gun and half World.")
            self.fix_pop_button = QtWidgets.QPushButton("Fix Jump Here")
            self.fix_pop_button.setToolTip("If the object pops on this frame, click this to rebuild the current follow setup here.")
            self.remove_target_button = QtWidgets.QPushButton("Forget Parent")
            self.remove_target_button.setToolTip("Remove the picked parent row from this object's saved parent list.")
            advanced_actions.addWidget(self.add_target_button)
            advanced_actions.addWidget(self.apply_weights_button)
            advanced_actions.addWidget(self.fix_pop_button)
            advanced_actions.addWidget(self.remove_target_button)
            advanced_layout.addLayout(advanced_actions)

            advanced_help = QtWidgets.QLabel(
                "What these extra buttons mean:\n"
                "- Add Parent: remember a parent for later.\n"
                "- Blend Parents: let two parents share the object on this frame.\n"
                "- Fix Jump Here: fix a pop on this frame.\n"
                "- Forget Parent: remove that parent from the list."
            )
            advanced_help.setWordWrap(True)
            advanced_layout.addWidget(advanced_help)

            history_group = QtWidgets.QGroupBox("History")
            history_layout = QtWidgets.QVBoxLayout(history_group)
            self.event_list = QtWidgets.QListWidget()
            self.event_list.setToolTip("Every saved switch for this object in this scene.")
            history_layout.addWidget(self.event_list)
            history_button_row = QtWidgets.QHBoxLayout()
            self.jump_button = QtWidgets.QPushButton("Jump To Frame")
            self.delete_switch_button = QtWidgets.QPushButton("Delete Chosen")
            self.clear_switches_button = QtWidgets.QPushButton("Delete All")
            history_button_row.addWidget(self.jump_button)
            history_button_row.addWidget(self.delete_switch_button)
            history_button_row.addWidget(self.clear_switches_button)
            history_layout.addLayout(history_button_row)
            advanced_layout.addWidget(history_group, 1)

            self.summary_box = QtWidgets.QPlainTextEdit()
            self.summary_box.setReadOnly(True)
            self.summary_box.setMaximumHeight(120)
            advanced_layout.addWidget(self.summary_box)
            main_layout.addWidget(self.advanced_widget, 1)

            self.status_label = QtWidgets.QLabel("Ready.")
            self.status_label.setWordWrap(True)
            main_layout.addWidget(self.status_label)

            footer_layout = QtWidgets.QHBoxLayout()
            self.brand_label = QtWidgets.QLabel('Built by Amir. Follow Amir at <a href="{0}">followamir.com</a>.'.format(FOLLOW_AMIR_URL))
            self.brand_label.setOpenExternalLinks(False)
            self.brand_label.linkActivated.connect(self._open_follow_url)
            footer_layout.addWidget(self.brand_label, 1)
            self.donate_button = QtWidgets.QPushButton("Donate")
            _style_donate_button(self.donate_button)
            self.donate_button.clicked.connect(self._open_donate_url)
            footer_layout.addWidget(self.donate_button)
            main_layout.addLayout(footer_layout)

            self.add_object_button.clicked.connect(self._add_object)
            self.remove_object_button.clicked.connect(self._remove_object)
            self.object_list.itemSelectionChanged.connect(self._pick_object_from_list)
            self.rename_button.clicked.connect(self._rename_object)
            self.maintain_offset_check.toggled.connect(self._toggle_maintain_offset)
            self.use_target_button.clicked.connect(self._use_target)
            self.snap_to_picked_button.clicked.connect(self._snap_to_picked_target)
            self.parent_to_picked_button.clicked.connect(self._parent_to_picked_target)
            self.add_target_button.clicked.connect(self._add_target)
            self.parent_to_row_button.clicked.connect(self._parent_to_row)
            self.parent_to_world_button.clicked.connect(self._parent_to_world)
            self.apply_weights_button.clicked.connect(self._apply_weights)
            self.fix_pop_button.clicked.connect(self._refresh_active_weights)
            self.remove_target_button.clicked.connect(self._remove_target)
            self.jump_button.clicked.connect(self._jump_to_event)
            self.delete_switch_button.clicked.connect(self._delete_event)
            self.clear_switches_button.clicked.connect(self._clear_events)
            self.event_list.itemDoubleClicked.connect(self._jump_to_event)
            self.advanced_toggle.toggled.connect(self._toggle_advanced)

        def _selected_target_ids(self):
            rows = sorted(set(index.row() for index in self.targets_table.selectionModel().selectedRows()))
            target_ids = []
            for row_index in rows:
                item = self.targets_table.item(row_index, 0)
                target_id = item.data(QtCore.Qt.UserRole) if item else ""
                if target_id:
                    target_ids.append(target_id)
            return target_ids

        def _selected_event_frame(self):
            item = self.event_list.currentItem()
            if not item:
                return None
            return item.data(QtCore.Qt.UserRole)

        def _weight_map_from_ui(self):
            return {target_id: float(spin_box.value()) for target_id, spin_box in self._weight_widgets.items()}

        def _sync_from_controller(self):
            setup = self.controller.current_setup()
            self.objects_line.setText(setup["driven"] if setup else "")
            self.target_line.setText(_short_name(self.controller.pending_target_node))
            self.object_list.blockSignals(True)
            self.object_list.clear()
            for payload in self.controller.setup_payloads(from_selection=False):
                item = QtWidgets.QListWidgetItem(payload["label"])
                item.setData(QtCore.Qt.UserRole, payload["setup_group"])
                item.setToolTip(payload["driven"])
                self.object_list.addItem(item)
                if setup and payload["setup_group"] == setup["setup_group"]:
                    self.object_list.setCurrentItem(item)
            self.object_list.blockSignals(False)
            self.list_name_line.setText(setup["label"] if setup else "")
            self.maintain_offset_check.blockSignals(True)
            self.maintain_offset_check.setChecked(bool(setup["maintain_offset"]) if setup else True)
            self.maintain_offset_check.blockSignals(False)

            self._weight_widgets = {}
            self.targets_table.setRowCount(0)
            self.event_list.clear()
            if setup:
                payload = self.controller._payload_for_setup(setup)
                for row_index, target in enumerate(payload["targets"]):
                    self.targets_table.insertRow(row_index)
                    name_item = QtWidgets.QTableWidgetItem(target["label"])
                    name_item.setData(QtCore.Qt.UserRole, target["id"])
                    self.targets_table.setItem(row_index, 0, name_item)
                    spin_box = QtWidgets.QDoubleSpinBox()
                    spin_box.setRange(0.0, 1.0)
                    spin_box.setDecimals(2)
                    spin_box.setSingleStep(0.1)
                    spin_box.setValue(float(payload["current_weights"].get(target["id"], 0.0)))
                    self.targets_table.setCellWidget(row_index, 1, spin_box)
                    self._weight_widgets[target["id"]] = spin_box
                    state_item = QtWidgets.QTableWidgetItem("On" if payload["current_weights"].get(target["id"], 0.0) > EPSILON else "Off")
                    self.targets_table.setItem(row_index, 2, state_item)
                    quick_button = QtWidgets.QPushButton("Switch to this Parent")
                    quick_button.setToolTip("Keep the current parent on this frame, then switch fully to this parent on the next frame.")
                    quick_button.clicked.connect(lambda _checked=False, target_id=target["id"]: self._parent_to_target_id(target_id))
                    self.targets_table.setCellWidget(row_index, 3, quick_button)
                for event in self.controller.event_items(setup):
                    item = QtWidgets.QListWidgetItem(event["display"])
                    item.setData(QtCore.Qt.UserRole, event["frame"])
                    self.event_list.addItem(item)
                if self.event_list.count():
                    self.event_list.setCurrentRow(self.event_list.count() - 1)
                self.summary_box.setPlainText(self.controller.summary_text(setup))
            else:
                self.summary_box.setPlainText(self.controller.summary_text(None))

        def _set_status(self, message, success=True):
            self.status_label.setText(message)
            palette = self.status_label.palette()
            role = self.status_label.foregroundRole()
            palette.setColor(role, QtGui.QColor("#24A148" if success else "#DA1E28"))
            self.status_label.setPalette(palette)
            self._sync_from_controller()

        def _toggle_advanced(self, enabled):
            self.advanced_widget.setVisible(bool(enabled))
            self.advanced_toggle.setText("Less" if enabled else "More")

        def _add_object(self):
            success, message = self.controller.add_driven_from_selection()
            self._set_status(message, success)

        def _remove_object(self):
            success, message = self.controller.remove_active_setup()
            self._set_status(message, success)

        def _pick_object_from_list(self):
            item = self.object_list.currentItem()
            if not item:
                return
            success, message = self.controller.set_active_setup(item.data(QtCore.Qt.UserRole))
            self._set_status(message, success)

        def _rename_object(self):
            success, message = self.controller.rename_active_setup(self.list_name_line.text())
            self._set_status(message, success)

        def _toggle_maintain_offset(self):
            success, message = self.controller.set_maintain_offset(self.maintain_offset_check.isChecked())
            self._set_status(message, success)

        def _use_target(self):
            success, message = self.controller.set_pending_target_from_selection()
            self._set_status(message, success)

        def _add_target(self):
            success, message = self.controller.add_targets_from_selection()
            self._set_status(message, success)

        def _parent_to_picked_target(self):
            if not self.controller.pending_target_node or not cmds.objExists(self.controller.pending_target_node):
                success, message = self.controller.set_pending_target_from_selection()
                if not success:
                    self._set_status(message, success)
                    return
            success, message = self.controller.apply_pending_target()
            self._set_status(message, success)

        def _snap_to_picked_target(self):
            if not self.controller.pending_target_node or not cmds.objExists(self.controller.pending_target_node):
                success, message = self.controller.set_pending_target_from_selection()
                if not success:
                    self._set_status(message, success)
                    return
            success, message = self.controller.snap_pending_target()
            self._set_status(message, success)

        def _parent_to_target_id(self, target_id):
            success, message = self.controller.parent_fully_to_target(target_id, action_label="switch")
            self._set_status(message, success)

        def _parent_to_row(self):
            target_ids = self._selected_target_ids()
            if not target_ids:
                self._set_status("Pick a parent row first.", False)
                return
            success, message = self.controller.parent_fully_to_target(target_ids[0], action_label="switch")
            self._set_status(message, success)

        def _parent_to_world(self):
            success, message = self.controller.parent_to_world()
            self._set_status(message, success)

        def _apply_weights(self):
            success, message = self.controller.apply_weight_map(self._weight_map_from_ui(), action_label="blend")
            self._set_status(message, success)

        def _refresh_active_weights(self):
            success, message = self.controller.reseed_active_weights()
            self._set_status(message, success)

        def _remove_target(self):
            success, message = self.controller.remove_target_ids(self._selected_target_ids())
            self._set_status(message, success)

        def _jump_to_event(self, *_args):
            frame_value = self._selected_event_frame()
            if frame_value is None:
                self._set_status("Pick a saved switch first.", False)
                return
            success, message = self.controller.jump_to_event(frame_value)
            self._set_status(message, success)

        def _delete_event(self):
            frame_value = self._selected_event_frame()
            if frame_value is None:
                self._set_status("Pick a saved switch first.", False)
                return
            success, message = self.controller.delete_event_frame(frame_value)
            self._set_status(message, success)

        def _clear_events(self):
            success, message = self.controller.clear_event_log()
            self._set_status(message, success)

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


__all__ = ["MayaDynamicParentingController", "MayaDynamicParentingWindow"]
