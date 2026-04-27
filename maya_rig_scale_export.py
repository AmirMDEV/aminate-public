"""
maya_rig_scale_export.py

Non-destructive rig-scale export copy builder for Maya 2022-2026.
"""

from __future__ import absolute_import, division, print_function

import os
import traceback

import maya_skinning_cleanup as skin_cleanup

try:
    import maya.cmds as cmds
    import maya.api.OpenMaya as om
    import maya.api.OpenMayaAnim as oma
    import maya.OpenMayaUI as omui

    MAYA_AVAILABLE = True
except Exception:
    cmds = None
    om = None
    oma = None
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


WINDOW_OBJECT_NAME = "mayaRigScaleExportWindow"
WORKSPACE_CONTROL_NAME = WINDOW_OBJECT_NAME + "WorkspaceControl"
FOLLOW_AMIR_URL = "https://followamir.com"
DEFAULT_DONATE_URL = "https://www.paypal.com/donate/?hosted_button_id=2U2GXSKFJKJCA"
DONATE_URL = os.environ.get("AMIR_PAYPAL_DONATE_URL") or os.environ.get("AMIR_DONATE_URL") or DEFAULT_DONATE_URL
DEFAULT_COPY_SUFFIX = "_rigScaleExport"
GROUP_SCALE_ATTR = "amirRigScaleFactor"
GROUP_NOTE_ATTR = "amirExportNote"
VALUE_EPSILON = 1.0e-5
NORMAL_EPSILON = 1.0e-4

GLOBAL_CONTROLLER = None
GLOBAL_WINDOW = None

_qt_flag = skin_cleanup._qt_flag
_style_donate_button = skin_cleanup._style_donate_button
_open_external_url = skin_cleanup._open_external_url
_maya_main_window = skin_cleanup._maya_main_window
_dedupe_preserve_order = skin_cleanup._dedupe_preserve_order
_short_name = skin_cleanup._short_name
_uuid_for_node = skin_cleanup._uuid_for_node
_node_long_name = skin_cleanup._node_long_name
_unique_name = skin_cleanup._unique_name
_dag_path = skin_cleanup._dag_path
_depend_node = skin_cleanup._depend_node
_mesh_fn = skin_cleanup._mesh_fn
_all_vertex_component = skin_cleanup._all_vertex_component
_distance_between_points = skin_cleanup._distance_between_points
_find_skin_cluster = skin_cleanup._find_skin_cluster
_unsupported_history_nodes = skin_cleanup._unsupported_history_nodes
_capture_shading_assignments = skin_cleanup._capture_shading_assignments
_normalized_shading_assignments = skin_cleanup._normalized_shading_assignments
_apply_shading_assignments = skin_cleanup._apply_shading_assignments
_capture_uv_summary = skin_cleanup._capture_uv_summary
_capture_color_summary = skin_cleanup._capture_color_summary
_capture_edge_smoothing = skin_cleanup._capture_edge_smoothing
_capture_world_normals = skin_cleanup._capture_world_normals
_capture_topology_signature = skin_cleanup._capture_topology_signature
_capture_world_points = skin_cleanup._capture_world_points
_capture_skin_data = skin_cleanup._capture_skin_data
_max_normal_delta = skin_cleanup._max_normal_delta
_unlock_transform_channels = skin_cleanup._unlock_transform_channels


def _debug(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayInfo("[Maya Rig Scale] {0}".format(message))


def _warning(message):
    if MAYA_AVAILABLE and om:
        om.MGlobal.displayWarning("[Maya Rig Scale] {0}".format(message))


def _selected_nodes():
    return cmds.ls(selection=True, long=True) or []


def _visible_mesh_shape(transform_name):
    shapes = cmds.listRelatives(transform_name, shapes=True, noIntermediate=True, fullPath=True, type="mesh") or []
    return shapes[0] if shapes else ""


def _selected_character_candidate():
    selected = _selected_nodes()
    if not selected:
        return "", "Pick the character root or any object under the character first."
    node_name = selected[0]
    if cmds.nodeType(node_name) == "mesh":
        parent = cmds.listRelatives(node_name, parent=True, fullPath=True) or []
        if parent:
            return parent[0], ""
    return _node_long_name(node_name), ""


def _selected_skeleton_candidate():
    selected = _selected_nodes()
    if not selected:
        return "", "Pick the top skeleton joint first."
    node_name = _node_long_name(selected[0])
    if cmds.nodeType(node_name) == "joint":
        return node_name, ""
    descendants = cmds.listRelatives(node_name, allDescendents=True, fullPath=True, type="joint") or []
    top_level = []
    for joint_name in descendants:
        parent = cmds.listRelatives(joint_name, parent=True, fullPath=True) or []
        if not parent or parent[0] == node_name or cmds.nodeType(parent[0]) != "joint":
            top_level.append(joint_name)
    top_level = sorted(_dedupe_preserve_order(top_level), key=lambda item: item.count("|"))
    if len(top_level) == 1:
        return top_level[0], ""
    if top_level:
        return "", "More than one top skeleton joint was found. Pick the exact skeleton root joint."
    return "", "The selected object does not contain a joint hierarchy."


def _is_descendant_or_same(node_name, root_name):
    long_node = _node_long_name(node_name)
    long_root = _node_long_name(root_name)
    return long_node == long_root or long_node.startswith(long_root + "|")


def _joint_hierarchy(root_joint):
    if not root_joint or not cmds.objExists(root_joint):
        return []
    descendants = cmds.listRelatives(root_joint, allDescendents=True, fullPath=True, type="joint") or []
    descendants = sorted(_dedupe_preserve_order(descendants), key=lambda item: item.count("|"))
    return [_node_long_name(root_joint)] + descendants


def _mesh_targets_under_character(character_root):
    roots = [_node_long_name(character_root)]
    descendants = cmds.listRelatives(character_root, allDescendents=True, fullPath=True, type="transform") or []
    targets = []
    for transform_name in _dedupe_preserve_order(roots + descendants):
        shape_name = _visible_mesh_shape(transform_name)
        if not shape_name:
            continue
        skin_cluster = _find_skin_cluster(shape_name)
        if not skin_cluster:
            continue
        targets.append(
            {
                "transform": _node_long_name(transform_name),
                "shape": _node_long_name(shape_name),
                "skin_cluster": skin_cluster,
            }
        )
    return targets


def _mesh_targets_from_skeleton(skeleton_root, character_root=""):
    joint_names = _joint_hierarchy(skeleton_root)
    skin_clusters = []
    for joint_name in joint_names:
        skin_clusters.extend(cmds.listConnections(joint_name, source=False, destination=True, type="skinCluster") or [])
    targets = []
    for skin_cluster in _dedupe_preserve_order(skin_clusters):
        shapes = cmds.skinCluster(skin_cluster, query=True, geometry=True) or []
        for shape_name in shapes:
            if not cmds.objExists(shape_name):
                continue
            node_type = cmds.nodeType(shape_name)
            if node_type == "transform":
                transform_name = _node_long_name(shape_name)
                shape_name = _visible_mesh_shape(transform_name)
            elif node_type == "mesh":
                parent = cmds.listRelatives(shape_name, parent=True, fullPath=True) or []
                if not parent:
                    continue
                transform_name = parent[0]
            else:
                continue
            if not shape_name:
                continue
            if character_root and not _is_descendant_or_same(transform_name, character_root):
                continue
            targets.append(
                {
                    "transform": _node_long_name(transform_name),
                    "shape": _node_long_name(shape_name),
                    "skin_cluster": skin_cluster,
                }
            )
    return _dedupe_preserve_order(targets)


def _safe_get_vector_attr(node_name, attribute):
    plug = "{0}.{1}".format(node_name, attribute)
    if not cmds.objExists(plug):
        return (0.0, 0.0, 0.0)
    return tuple(float(value) for value in cmds.getAttr(plug)[0])


def _has_locked_normals(shape_name):
    try:
        values = cmds.polyNormalPerVertex(shape_name + ".vtxFace[*][*]", query=True, freezeNormal=True) or []
    except Exception:
        values = []
    return any(bool(value) for value in values)


def _ancestor_transform_warnings(root_joint):
    warnings = []
    current = root_joint
    while True:
        parent = cmds.listRelatives(current, parent=True, fullPath=True) or []
        if not parent:
            break
        current = parent[0]
        scale = _safe_get_vector_attr(current, "scale")
        if any(abs(value - 1.0) > 0.001 for value in scale):
            warnings.append(
                "The parent group {0} is already scaled. The export copy will bake the current visible size, not a hidden original size.".format(
                    _short_name(current)
                )
            )
            if abs(scale[0] - scale[1]) > 0.001 or abs(scale[1] - scale[2]) > 0.001 or abs(scale[0] - scale[2]) > 0.001:
                warnings.append(
                    "The parent group {0} uses non-uniform scale. Exact shading normals may need manual cleanup after export.".format(
                        _short_name(current)
                    )
                )
            break
        rotation = _safe_get_vector_attr(current, "rotate")
        if any(abs(value) > 0.001 for value in rotation):
            warnings.append(
                "The parent group {0} is rotated. Exact viewport normals can differ after baking scale, so verify the export copy before sending it to Unreal.".format(
                    _short_name(current)
                )
            )
            break
    return warnings


def _linear_unit_warning():
    try:
        unit_name = cmds.currentUnit(query=True, linear=True)
    except Exception:
        return []
    if unit_name != "cm":
        return ["The scene unit is {0}. Unreal usually expects centimeters, so double-check your export settings.".format(unit_name)]
    return []


def _world_translation(node_name):
    values = cmds.xform(node_name, query=True, worldSpace=True, translation=True)
    return om.MVector(float(values[0]), float(values[1]), float(values[2]))


def _world_quaternion(node_name):
    matrix_values = cmds.xform(node_name, query=True, worldSpace=True, matrix=True)
    matrix = om.MMatrix(matrix_values)
    transform = om.MTransformationMatrix(matrix)
    return transform.rotation(asQuaternion=True)


def _matrix_to_list(matrix):
    return [matrix[index] for index in range(16)]


def _world_matrix_without_scale(node_name):
    source_matrix = om.MMatrix(cmds.xform(node_name, query=True, worldSpace=True, matrix=True))
    source_transform = om.MTransformationMatrix(source_matrix)
    clean_transform = om.MTransformationMatrix()
    clean_transform.setTranslation(source_transform.translation(om.MSpace.kWorld), om.MSpace.kWorld)
    clean_transform.setRotation(source_transform.rotation(asQuaternion=True))
    return clean_transform.asMatrix()


def _scaled_child_world_position(source_parent, source_child, duplicate_parent, scale_factor):
    source_parent_world = _world_translation(source_parent)
    source_child_world = _world_translation(source_child)
    duplicate_parent_world = _world_translation(duplicate_parent)
    world_delta = source_child_world - source_parent_world
    return om.MPoint(
        duplicate_parent_world.x + (world_delta.x * scale_factor),
        duplicate_parent_world.y + (world_delta.y * scale_factor),
        duplicate_parent_world.z + (world_delta.z * scale_factor),
    )


def _point_in_parent_space(world_point, parent_node):
    local_point = om.MPoint(world_point) * _dag_path(parent_node).inclusiveMatrixInverse()
    return (float(local_point.x), float(local_point.y), float(local_point.z))


def _capture_true_world_points(shape_name):
    iterator = om.MItMeshVertex(_dag_path(shape_name))
    points = om.MPointArray()
    while not iterator.isDone():
        points.append(iterator.position(om.MSpace.kWorld))
        iterator.next()
    return points


def _scaled_local_translate(source_parent, source_child, scale_factor):
    world_delta = _world_translation(source_child) - _world_translation(source_parent)
    parent_quaternion = _world_quaternion(source_parent)
    local_delta = world_delta.rotateBy(parent_quaternion.inverse())
    return (float(local_delta.x * scale_factor), float(local_delta.y * scale_factor), float(local_delta.z * scale_factor))


def _set_translate(node_name, values):
    cmds.setAttr(node_name + ".translateX", float(values[0]))
    cmds.setAttr(node_name + ".translateY", float(values[1]))
    cmds.setAttr(node_name + ".translateZ", float(values[2]))


def _copy_joint_attribute(source_joint, duplicate_joint, attribute):
    source_plug = "{0}.{1}".format(source_joint, attribute)
    target_plug = "{0}.{1}".format(duplicate_joint, attribute)
    if not cmds.objExists(source_plug) or not cmds.objExists(target_plug):
        return
    try:
        value = cmds.getAttr(source_plug)
    except Exception:
        return
    try:
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (list, tuple)):
            values = value[0]
            cmds.setAttr(target_plug, *values)
        elif isinstance(value, str):
            cmds.setAttr(target_plug, value, type="string")
        else:
            cmds.setAttr(target_plug, value)
    except Exception:
        pass


def _copy_joint_settings(source_joint, duplicate_joint):
    for attribute in (
        "rotateOrder",
        "jointOrient",
        "rotateAxis",
        "rotate",
        "preferredAngle",
        "segmentScaleCompensate",
        "radius",
        "side",
        "type",
        "drawStyle",
        "visibility",
    ):
        _copy_joint_attribute(source_joint, duplicate_joint, attribute)

    other_type_plug = source_joint + ".otherType"
    if cmds.objExists(other_type_plug):
        try:
            other_type = cmds.getAttr(other_type_plug)
            if isinstance(other_type, str):
                cmds.setAttr(duplicate_joint + ".otherType", other_type, type="string")
        except Exception:
            pass

    for axis in ("X", "Y", "Z"):
        _copy_joint_attribute(source_joint, duplicate_joint, "jointType" + axis)


def _connect_inverse_scale(parent_joint, child_joint):
    parent_scale = parent_joint + ".scale"
    child_inverse = child_joint + ".inverseScale"
    if not cmds.objExists(parent_scale) or not cmds.objExists(child_inverse):
        return
    existing = cmds.listConnections(child_inverse, source=True, destination=False, plugs=True) or []
    if existing:
        return
    try:
        cmds.connectAttr(parent_scale, child_inverse, force=True)
    except Exception:
        pass


def _scaled_points_about_anchor(points, anchor_point, scale_factor):
    scaled = om.MPointArray()
    anchor = om.MPoint(anchor_point.x, anchor_point.y, anchor_point.z)
    for point in points:
        scaled.append(
            om.MPoint(
                anchor.x + ((point.x - anchor.x) * scale_factor),
                anchor.y + ((point.y - anchor.y) * scale_factor),
                anchor.z + ((point.z - anchor.z) * scale_factor),
            )
        )
    return scaled


def _scale_mesh_points_about_anchor(shape_name, anchor_point, scale_factor):
    dag_path = _dag_path(shape_name)
    mesh_fn = om.MFnMesh(dag_path)
    inverse = dag_path.inclusiveMatrixInverse()
    scaled_object_points = om.MPointArray()
    world_points = mesh_fn.getPoints(om.MSpace.kWorld)
    for point in _scaled_points_about_anchor(world_points, anchor_point, scale_factor):
        scaled_object_points.append(point * inverse)
    mesh_fn.setPoints(scaled_object_points, om.MSpace.kObject)
    mesh_fn.updateSurface()


def _set_mesh_world_points(shape_name, world_points):
    dag_path = _dag_path(shape_name)
    mesh_fn = om.MFnMesh(dag_path)
    inverse = dag_path.inclusiveMatrixInverse()
    object_points = om.MPointArray()
    for point in world_points:
        object_points.append(point * inverse)
    mesh_fn.setPoints(object_points, om.MSpace.kObject)
    mesh_fn.updateSurface()


def _apply_world_normals(shape_name, world_normals):
    if not world_normals:
        return
    mesh_fn = om.MFnMesh(_dag_path(shape_name))
    normals = om.MVectorArray()
    face_ids = om.MIntArray()
    vertex_ids = om.MIntArray()
    for face_id, vertex_id, vector in world_normals:
        normals.append(om.MVector(float(vector[0]), float(vector[1]), float(vector[2])))
        face_ids.append(int(face_id))
        vertex_ids.append(int(vertex_id))
    mesh_fn.setFaceVertexNormals(normals, face_ids, vertex_ids, om.MSpace.kWorld)


def _pair_joint_trees(source_joint, duplicate_joint, pairs):
    pairs.append((_node_long_name(source_joint), _node_long_name(duplicate_joint)))
    source_children = cmds.listRelatives(source_joint, children=True, fullPath=True, type="joint") or []
    duplicate_children = cmds.listRelatives(duplicate_joint, children=True, fullPath=True, type="joint") or []
    if len(source_children) != len(duplicate_children):
        raise RuntimeError("The copied skeleton no longer matches the source joint hierarchy.")
    for source_child, duplicate_child in zip(source_children, duplicate_children):
        _pair_joint_trees(source_child, duplicate_child, pairs)


def _rename_duplicate_joint_tree(source_joint, duplicate_joint):
    source_short = _short_name(source_joint)
    duplicate_short = _short_name(duplicate_joint)
    current_duplicate = duplicate_joint
    if source_short != duplicate_short:
        current_duplicate = _node_long_name(cmds.rename(duplicate_joint, source_short))
    source_children = cmds.listRelatives(source_joint, children=True, fullPath=True, type="joint") or []
    duplicate_children = cmds.listRelatives(current_duplicate, children=True, fullPath=True, type="joint") or []
    if len(source_children) != len(duplicate_children):
        raise RuntimeError("Could not rename the copied skeleton cleanly.")
    for source_child, duplicate_child in zip(source_children, duplicate_children):
        _rename_duplicate_joint_tree(source_child, duplicate_child)
    return current_duplicate


def _delete_non_joint_descendants(root_joint):
    descendants = cmds.listRelatives(root_joint, allDescendents=True, fullPath=True) or []
    for node_name in sorted(descendants, key=lambda item: item.count("|"), reverse=True):
        if cmds.nodeType(node_name) == "joint":
            continue
        try:
            cmds.delete(node_name)
        except Exception:
            pass


def _duplicate_scaled_skeleton(skeleton_root, export_group, scale_factor):
    joint_map = {}

    def rebuild_joint(source_joint, duplicate_parent):
        duplicate_joint = cmds.createNode("joint", name=_short_name(source_joint), parent=duplicate_parent, skipSelect=True)
        duplicate_joint = _node_long_name(duplicate_joint)
        joint_map[_node_long_name(source_joint)] = duplicate_joint

        _copy_joint_settings(source_joint, duplicate_joint)
        cmds.setAttr(duplicate_joint + ".scaleX", 1.0)
        cmds.setAttr(duplicate_joint + ".scaleY", 1.0)
        cmds.setAttr(duplicate_joint + ".scaleZ", 1.0)

        source_parent = cmds.listRelatives(source_joint, parent=True, fullPath=True, type="joint") or []
        if source_parent:
            scaled_world = _scaled_child_world_position(source_parent[0], source_joint, duplicate_parent, scale_factor)
            _set_translate(duplicate_joint, _point_in_parent_space(scaled_world, duplicate_parent))
            duplicate_joint_parent = cmds.listRelatives(duplicate_joint, parent=True, fullPath=True, type="joint") or []
            if duplicate_joint_parent:
                _connect_inverse_scale(duplicate_joint_parent[0], duplicate_joint)
        else:
            cmds.xform(duplicate_joint, worldSpace=True, matrix=_matrix_to_list(_world_matrix_without_scale(source_joint)))
            cmds.setAttr(duplicate_joint + ".scaleX", 1.0)
            cmds.setAttr(duplicate_joint + ".scaleY", 1.0)
            cmds.setAttr(duplicate_joint + ".scaleZ", 1.0)

        child_joints = cmds.listRelatives(source_joint, children=True, fullPath=True, type="joint") or []
        for child_joint in child_joints:
            rebuild_joint(child_joint, duplicate_joint)
        return duplicate_joint

    duplicate_root = rebuild_joint(_node_long_name(skeleton_root), _node_long_name(export_group))
    return duplicate_root, joint_map


def _visible_mesh_shape_in_duplicate(transform_name):
    shapes = cmds.listRelatives(transform_name, shapes=True, fullPath=True, type="mesh") or []
    visible_shapes = []
    for shape_name in shapes:
        try:
            if cmds.getAttr(shape_name + ".intermediateObject"):
                continue
        except Exception:
            pass
        visible_shapes.append(shape_name)
    return visible_shapes[0] if visible_shapes else ""


def _build_scaled_mesh_snapshot(mesh_report, export_group, anchor_point, scale_factor):
    source_transform = mesh_report["source_transform"]
    duplicate_name = _unique_name(_short_name(source_transform) + "_scaledPreview")
    duplicate_transform = cmds.duplicate(source_transform, renameChildren=True, returnRootsOnly=True, name=duplicate_name)[0]
    duplicate_transform = cmds.parent(duplicate_transform, export_group, relative=False)[0]
    duplicate_transform = _node_long_name(duplicate_transform)
    duplicate_transform = _node_long_name(cmds.rename(duplicate_transform, _short_name(source_transform)))

    try:
        cmds.delete(duplicate_transform, constructionHistory=True)
    except Exception:
        pass

    duplicate_shape = _visible_mesh_shape_in_duplicate(duplicate_transform)
    if not duplicate_shape:
        raise RuntimeError("Could not find a visible mesh after copying {0}.".format(_short_name(source_transform)))

    _unlock_transform_channels(duplicate_transform)
    original_world_points = _capture_true_world_points(duplicate_shape)
    cmds.setAttr(duplicate_transform + ".scaleX", 1.0)
    cmds.setAttr(duplicate_transform + ".scaleY", 1.0)
    cmds.setAttr(duplicate_transform + ".scaleZ", 1.0)
    _set_mesh_world_points(duplicate_shape, original_world_points)
    baseline_world_points = _capture_true_world_points(duplicate_shape)
    _scale_mesh_points_about_anchor(duplicate_shape, anchor_point, scale_factor)

    if mesh_report["uv_summary"].get("current"):
        try:
            cmds.polyUVSet(duplicate_shape, currentUVSet=True, uvSet=mesh_report["uv_summary"]["current"])
        except Exception:
            pass
    _apply_shading_assignments(duplicate_transform, duplicate_shape, mesh_report["shading_assignments"])
    return duplicate_transform, duplicate_shape, baseline_world_points


def _mapped_influences(mesh_report, joint_map):
    mapped = []
    missing = []
    for entry in mesh_report["skin_data"]["influences"]:
        source_path = entry.get("path", "")
        duplicate_path = joint_map.get(source_path)
        if not duplicate_path or not cmds.objExists(duplicate_path):
            missing.append(source_path or entry.get("uuid", ""))
            continue
        mapped.append(
            {
                "path": duplicate_path,
                "uuid": _uuid_for_node(duplicate_path),
                "weights": list(entry.get("weights", [])),
            }
        )
    return mapped, missing


def _bind_scaled_mesh(duplicate_transform, duplicate_shape, mesh_report, joint_map):
    mapped_influences, missing = _mapped_influences(mesh_report, joint_map)
    if missing:
        raise RuntimeError("Missing copied joints for: {0}".format(", ".join(_short_name(item) for item in missing if item)))

    skin_data = mesh_report["skin_data"]
    influence_paths = [entry["path"] for entry in mapped_influences]
    settings = skin_data["settings"]
    cluster_name = _unique_name(_short_name(mesh_report["skin_cluster"]) + "_scaled")
    new_skin_cluster = cmds.skinCluster(
        influence_paths,
        duplicate_transform,
        name=cluster_name,
        toSelectedBones=True,
        bindMethod=int(settings.get("bindMethod", 0)),
        skinMethod=int(settings.get("skinningMethod", 0)),
        normalizeWeights=int(settings.get("normalizeWeights", 1)),
        maximumInfluences=int(settings.get("maxInfluences", 5)),
        obeyMaxInfluences=bool(settings.get("maintainMaxInfluences", False)),
        weightDistribution=int(settings.get("weightDistribution", 0)),
        removeUnusedInfluence=False,
    )[0]

    for attribute in ("maintainMaxInfluences", "useComponents", "deformUserNormals"):
        if attribute in settings and cmds.attributeQuery(attribute, node=new_skin_cluster, exists=True):
            try:
                cmds.setAttr("{0}.{1}".format(new_skin_cluster, attribute), settings[attribute])
            except Exception:
                pass

    skin_fn = oma.MFnSkinCluster(_depend_node(new_skin_cluster))
    shape_dag = _dag_path(duplicate_shape)
    component = _all_vertex_component(skin_data["vertex_count"])

    influence_order = []
    for influence_dag in skin_fn.influenceObjects():
        physical_index = int(skin_fn.indexForInfluenceObject(influence_dag))
        full_path = influence_dag.fullPathName()
        influence_order.append(
            {
                "path": full_path,
                "uuid": _uuid_for_node(full_path),
                "physical_index": physical_index,
            }
        )
    influence_order.sort(key=lambda item: item["physical_index"])

    source_weight_map = {}
    for entry in mapped_influences:
        source_weight_map[entry["uuid"] or entry["path"]] = list(entry["weights"])

    indices = om.MIntArray()
    weights = om.MDoubleArray()
    for entry in influence_order:
        indices.append(entry["physical_index"])
    for vertex_index in range(skin_data["vertex_count"]):
        for entry in influence_order:
            weights.append(float(source_weight_map[entry["uuid"] or entry["path"]][vertex_index]))

    skin_fn.setWeights(shape_dag, component, indices, weights, normalize=False)
    skin_fn.setBlendWeights(shape_dag, component, om.MDoubleArray(skin_data["blend_weights"]))
    return new_skin_cluster


def _max_point_delta(source_points, target_points):
    if len(source_points) != len(target_points):
        return float("inf")
    max_delta = 0.0
    for source_point, target_point in zip(source_points, target_points):
        max_delta = max(max_delta, _distance_between_points(source_point, target_point))
    return max_delta


def _verify_scaled_mesh(mesh_report, duplicate_transform, duplicate_shape, new_skin_cluster, joint_map, anchor_point, scale_factor, baseline_world_points):
    checks = []

    def add_check(label, passed, details):
        checks.append({"label": label, "passed": bool(passed), "details": details})

    duplicate_signature = _capture_topology_signature(duplicate_shape)
    source_signature = mesh_report["topology_signature"]
    topology_ok = (
        duplicate_signature["vertex_count"] == source_signature["vertex_count"]
        and duplicate_signature["face_count"] == source_signature["face_count"]
        and duplicate_signature["counts"] == source_signature["counts"]
        and duplicate_signature["indices"] == source_signature["indices"]
    )
    add_check("Topology + vertex order", topology_ok, "{0} verts, {1} faces".format(duplicate_signature["vertex_count"], duplicate_signature["face_count"]))

    scale = cmds.getAttr(duplicate_transform + ".scale")[0]
    scale_ok = all(abs(value - 1.0) <= VALUE_EPSILON for value in scale)
    add_check("Mesh scale is 1,1,1", scale_ok, "scale = {0:.6f}, {1:.6f}, {2:.6f}".format(scale[0], scale[1], scale[2]))

    expected_points = _scaled_points_about_anchor(baseline_world_points, anchor_point, scale_factor)
    duplicate_points = _capture_true_world_points(duplicate_shape)
    point_delta = _max_point_delta(expected_points, duplicate_points)
    add_check("Viewport shape matches scaled result", point_delta <= VALUE_EPSILON, "max point delta = {0:.8f}".format(point_delta))

    duplicate_skin_data = _capture_skin_data(duplicate_shape, new_skin_cluster)
    source_weight_map = {}
    for entry in mesh_report["skin_data"]["influences"]:
        duplicate_path = joint_map.get(entry["path"])
        if duplicate_path:
            source_weight_map[_uuid_for_node(duplicate_path) or duplicate_path] = entry["weights"]

    max_weight_delta = 0.0
    influence_mismatch = []
    for entry in duplicate_skin_data["influences"]:
        key = entry["uuid"] or entry["path"]
        if key not in source_weight_map:
            influence_mismatch.append(entry["path"])
            continue
        for source_value, duplicate_value in zip(source_weight_map[key], entry["weights"]):
            max_weight_delta = max(max_weight_delta, abs(source_value - duplicate_value))
    add_check("Skin weights match by vertex", not influence_mismatch and max_weight_delta <= VALUE_EPSILON, "max weight delta = {0:.8f}".format(max_weight_delta))

    max_blend_delta = 0.0
    for source_value, duplicate_value in zip(mesh_report["skin_data"]["blend_weights"], duplicate_skin_data["blend_weights"]):
        max_blend_delta = max(max_blend_delta, abs(source_value - duplicate_value))
    add_check("Skin blend weights match", max_blend_delta <= VALUE_EPSILON, "max blend delta = {0:.8f}".format(max_blend_delta))

    duplicate_assignments = _capture_shading_assignments(duplicate_transform, duplicate_shape)
    add_check("Face-based materials match", _normalized_shading_assignments(duplicate_assignments) == _normalized_shading_assignments(mesh_report["shading_assignments"]), "{0} material slot groups".format(len(duplicate_assignments)))

    duplicate_uv = _capture_uv_summary(duplicate_shape)
    add_check("UV sets match", duplicate_uv["names"] == mesh_report["uv_summary"]["names"] and duplicate_uv["current"] == mesh_report["uv_summary"]["current"], "current UV set = {0}".format(duplicate_uv["current"] or "None"))

    duplicate_color = _capture_color_summary(duplicate_shape)
    add_check("Color sets match", duplicate_color["names"] == mesh_report["color_summary"]["names"] and duplicate_color["current"] == mesh_report["color_summary"]["current"], "current color set = {0}".format(duplicate_color["current"] or "None"))

    duplicate_smoothing = _capture_edge_smoothing(duplicate_shape)
    add_check("Hard/soft edges match", duplicate_smoothing == mesh_report["edge_smoothing"], "{0} edges checked".format(len(duplicate_smoothing)))

    duplicate_normals = _capture_world_normals(duplicate_shape)
    normal_delta = _max_normal_delta(mesh_report["world_normals"], duplicate_normals)
    add_check("Normals stay the same", normal_delta <= NORMAL_EPSILON, "max normal delta = {0:.8f}".format(normal_delta))

    return {"checks": checks, "passed": all(check["passed"] for check in checks)}


def _validate_joint_scales(joint_names):
    failing = []
    for joint_name in joint_names:
        scale = _safe_get_vector_attr(joint_name, "scale")
        if any(abs(value - 1.0) > 0.001 for value in scale):
            failing.append("{0} ({1:.4f}, {2:.4f}, {3:.4f})".format(_short_name(joint_name), scale[0], scale[1], scale[2]))
    return failing


def _format_report(report):
    if not report:
        return "Pick the character and top skeleton joint, then click Check Setup."

    lines = [
        "Character Root: {0}".format(report.get("character_root") or "(auto from skeleton)"),
        "Skeleton Root: {0}".format(report.get("skeleton_root") or "(none)"),
        "Size Multiplier: {0:.3f}".format(float(report.get("scale_factor") or 1.0)),
        "Meshes Found: {0}".format(len(report.get("meshes", []))),
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
        lines.append("- This setup looks ready for an export copy.")
        lines.append("")

    if report.get("meshes"):
        lines.append("Meshes")
        for mesh_report in report["meshes"]:
            lines.append("- {0}: {1} influences".format(_short_name(mesh_report["source_transform"]), len(mesh_report["skin_data"]["influences"])))
        lines.append("")

    result = report.get("result")
    if result:
        lines.append("Export Copy")
        lines.append("- Group: {0}".format(result.get("export_group", "")))
        lines.append("- Joints kept at 1,1,1: {0}".format("Yes" if result.get("joints_verified") else "No"))
        lines.append("- Meshes rebuilt: {0}".format(len(result.get("mesh_results", []))))
        lines.append("")

    return "\n".join(lines).strip()


class MayaRigScaleExportController(object):
    def __init__(self):
        self.character_root = ""
        self.skeleton_root = ""
        self.scale_factor = 1.0
        self.copy_suffix = DEFAULT_COPY_SUFFIX
        self.report = None
        self.result = None
        self.status_callback = None

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

    def set_character_from_selection(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        character_root, message = _selected_character_candidate()
        if not character_root:
            return False, message
        self.character_root = character_root
        return True, "Character root set to {0}.".format(_short_name(character_root))

    def set_skeleton_from_selection(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."
        skeleton_root, message = _selected_skeleton_candidate()
        if not skeleton_root:
            return False, message
        self.skeleton_root = skeleton_root
        return True, "Skeleton root set to {0}.".format(_short_name(skeleton_root))

    def analyze_setup(self):
        if not MAYA_AVAILABLE:
            return False, "This tool only works inside Maya."

        character_root = _node_long_name(self.character_root) if self.character_root and cmds.objExists(self.character_root) else ""
        skeleton_root = _node_long_name(self.skeleton_root) if self.skeleton_root and cmds.objExists(self.skeleton_root) else ""
        errors = []
        warnings = []

        if not skeleton_root:
            errors.append("Pick the top skeleton joint first.")
        elif cmds.nodeType(skeleton_root) != "joint":
            errors.append("The skeleton root must be a joint.")
        if self.scale_factor <= VALUE_EPSILON:
            errors.append("Size Multiplier must be bigger than zero.")

        mesh_targets = []
        if not errors:
            if character_root:
                mesh_targets = _mesh_targets_under_character(character_root)
            if not mesh_targets:
                mesh_targets = _mesh_targets_from_skeleton(skeleton_root, character_root)
            if not mesh_targets:
                errors.append("No skinned polygon meshes were found for this character and skeleton.")

        joint_names = _joint_hierarchy(skeleton_root) if skeleton_root else []
        if joint_names:
            bad_scales = _validate_joint_scales(joint_names)
            if bad_scales:
                errors.append("These joints already have local scale values. V1 only supports clean source joints: {0}".format(", ".join(bad_scales[:8])))
            warnings.extend(_ancestor_transform_warnings(skeleton_root))
        warnings.extend(_linear_unit_warning())
        self.character_root = character_root
        self.skeleton_root = skeleton_root

        mesh_reports = []
        if not errors:
            joint_set = set(joint_names)
            for target in sorted(mesh_targets, key=lambda item: item["transform"].count("|")):
                source_transform = target["transform"]
                source_shape = target["shape"]
                skin_cluster = target["skin_cluster"]
                mesh_errors = []
                mesh_warnings = []
                unsupported_history = _unsupported_history_nodes(source_shape, skin_cluster)
                if unsupported_history:
                    names = ", ".join("{0} ({1})".format(_short_name(node_name), node_type) for node_name, node_type in unsupported_history)
                    mesh_errors.append("Unsupported extra deformation history on {0}: {1}".format(_short_name(source_transform), names))

                skin_data = _capture_skin_data(source_shape, skin_cluster)
                outside_influences = []
                non_joint_influences = []
                for entry in skin_data["influences"]:
                    influence_path = entry.get("path", "")
                    if not cmds.objExists(influence_path):
                        outside_influences.append(influence_path or entry.get("uuid", ""))
                        continue
                    if cmds.nodeType(influence_path) != "joint":
                        non_joint_influences.append(influence_path)
                        continue
                    if influence_path not in joint_set:
                        outside_influences.append(influence_path)
                if non_joint_influences:
                    mesh_errors.append("{0} uses influences that are not joints: {1}".format(_short_name(source_transform), ", ".join(_short_name(item) for item in non_joint_influences[:8])))
                if outside_influences:
                    mesh_errors.append("{0} uses joints outside the chosen skeleton: {1}".format(_short_name(source_transform), ", ".join(_short_name(item) for item in outside_influences[:8])))

                shading_assignments = _capture_shading_assignments(source_transform, source_shape)
                if len(shading_assignments) > 1:
                    mesh_warnings.append("{0} uses more than one material. The face-based split will be kept.".format(_short_name(source_transform)))
                if ":" in source_transform:
                    mesh_warnings.append("{0} uses extra name tags. The copy will keep checking full paths.".format(_short_name(source_transform)))
                if skin_cleanup._referenced_warning(source_transform):
                    mesh_warnings.append("{0} comes from a reference. The export copy is safe, but the source rig stays untouched.".format(_short_name(source_transform)))
                if _has_locked_normals(source_shape):
                    mesh_warnings.append("{0} has locked normals. The tool will check them again on the export copy.".format(_short_name(source_transform)))

                mesh_reports.append(
                    {
                        "source_transform": source_transform,
                        "source_shape": source_shape,
                        "skin_cluster": skin_cluster,
                        "skin_data": skin_data,
                        "shading_assignments": shading_assignments,
                        "uv_summary": _capture_uv_summary(source_shape),
                        "color_summary": _capture_color_summary(source_shape),
                        "edge_smoothing": _capture_edge_smoothing(source_shape),
                        "world_normals": _capture_world_normals(source_shape),
                        "topology_signature": _capture_topology_signature(source_shape),
                        "world_points": _capture_true_world_points(source_shape),
                        "errors": mesh_errors,
                        "warnings": mesh_warnings,
                    }
                )
            for mesh_report in mesh_reports:
                errors.extend(mesh_report["errors"])
                warnings.extend(mesh_report["warnings"])

        self.report = {
            "character_root": character_root,
            "skeleton_root": skeleton_root,
            "scale_factor": float(self.scale_factor),
            "copy_suffix": self.copy_suffix or DEFAULT_COPY_SUFFIX,
            "errors": errors,
            "warnings": _dedupe_preserve_order(warnings),
            "meshes": mesh_reports,
            "result": None,
        }
        self.result = None

        if errors:
            return False, "The setup is not safe yet. Read the red notes below."
        if warnings:
            return True, "The setup can work, but read the yellow notes first."
        return True, "The setup looks ready for an export copy."

    def create_export_copy(self):
        if not self.report or self.report.get("errors"):
            success, message = self.analyze_setup()
            if not success:
                return False, message

        if self.result and self.result.get("export_group") and cmds.objExists(self.result["export_group"]):
            try:
                cmds.delete(self.result["export_group"])
            except Exception:
                pass

        report = self.report
        anchor_point = _world_translation(report["skeleton_root"])
        export_group_name = _unique_name(_short_name(report["skeleton_root"]) + (report["copy_suffix"] or DEFAULT_COPY_SUFFIX))

        try:
            export_group = _node_long_name(cmds.group(empty=True, name=export_group_name))
            duplicate_root, joint_map = _duplicate_scaled_skeleton(report["skeleton_root"], export_group, report["scale_factor"])

            mesh_results = []
            for mesh_report in report["meshes"]:
                duplicate_transform, duplicate_shape, baseline_world_points = _build_scaled_mesh_snapshot(mesh_report, export_group, anchor_point, report["scale_factor"])
                new_skin_cluster = _bind_scaled_mesh(duplicate_transform, duplicate_shape, mesh_report, joint_map)
                _apply_shading_assignments(duplicate_transform, duplicate_shape, mesh_report["shading_assignments"])
                verification = _verify_scaled_mesh(
                    mesh_report,
                    duplicate_transform,
                    duplicate_shape,
                    new_skin_cluster,
                    joint_map,
                    anchor_point,
                    report["scale_factor"],
                    baseline_world_points,
                )
                mesh_results.append(
                    {
                        "source_transform": mesh_report["source_transform"],
                        "duplicate_transform": duplicate_transform,
                        "duplicate_shape": duplicate_shape,
                        "skin_cluster": new_skin_cluster,
                        "baseline_world_points": baseline_world_points,
                        "verification": verification,
                    }
                )

            joints_verified = True
            for duplicate_joint in joint_map.values():
                scale = _safe_get_vector_attr(duplicate_joint, "scale")
                if any(abs(value - 1.0) > VALUE_EPSILON for value in scale):
                    joints_verified = False
                    break

            if not cmds.attributeQuery(GROUP_SCALE_ATTR, node=export_group, exists=True):
                cmds.addAttr(export_group, longName=GROUP_SCALE_ATTR, attributeType="double")
            cmds.setAttr(export_group + "." + GROUP_SCALE_ATTR, float(report["scale_factor"]))
            if not cmds.attributeQuery(GROUP_NOTE_ATTR, node=export_group, exists=True):
                cmds.addAttr(export_group, longName=GROUP_NOTE_ATTR, dataType="string")
            cmds.setAttr(
                export_group + "." + GROUP_NOTE_ATTR,
                "Export this copied group to Unreal. The original rig stays untouched. Joints are rebuilt with scale 1,1,1.",
                type="string",
            )

            verified = joints_verified and all(item["verification"]["passed"] for item in mesh_results)
        except Exception as exc:
            _warning(traceback.format_exc())
            return False, "Could not build the export copy: {0}".format(exc)

        self.result = {
            "export_group": export_group,
            "duplicate_root": duplicate_root,
            "joint_map": joint_map,
            "mesh_results": mesh_results,
            "joints_verified": joints_verified,
            "verified": verified,
        }
        self.report["result"] = self.result

        if verified:
            return True, "Export copy ready. Export the copied group, not the animation rig."
        return False, "The export copy was built, but one or more checks failed. The original rig is still untouched."

    def select_export_copy(self):
        if not self.result or not self.result.get("export_group") or not cmds.objExists(self.result["export_group"]):
            return False, "There is no export copy to select yet."
        cmds.select(self.result["export_group"], replace=True)
        return True, "Selected the export copy group."

    def delete_export_copy(self):
        if not self.result or not self.result.get("export_group"):
            return False, "There is no export copy to delete."
        export_group = self.result["export_group"]
        if cmds.objExists(export_group):
            cmds.delete(export_group)
        self.result = None
        if self.report:
            self.report["result"] = None
        return True, "Deleted the export copy."


class _WindowBase(QtWidgets.QDialog if QtWidgets else object):
    pass


if QtWidgets:
    try:
        from maya.OpenMayaUI import MQtUtil
        from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

        if MQtUtil.mainWindow() is not None:
            _WindowBase = type("MayaRigScaleExportBase", (MayaQWidgetDockableMixin, QtWidgets.QDialog), {})
        else:
            _WindowBase = type("MayaRigScaleExportBase", (QtWidgets.QDialog,), {})
    except Exception:
        _WindowBase = type("MayaRigScaleExportBase", (QtWidgets.QDialog,), {})


if QtWidgets:
    class MayaRigScaleExportWindow(_WindowBase):
        def __init__(self, controller, parent=None):
            super(MayaRigScaleExportWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller
            self.controller.set_status_callback(self._set_status)
            self.setObjectName(WINDOW_OBJECT_NAME)
            self.setWindowTitle("Maya Rig Scale")
            self.setMinimumWidth(780)
            self.setMinimumHeight(660)
            self._build_ui()
            self._refresh_report()

        def _build_ui(self):
            main_layout = QtWidgets.QVBoxLayout(self)
            main_layout.setContentsMargins(12, 12, 12, 12)
            main_layout.setSpacing(10)

            description = QtWidgets.QLabel(
                "Make a clean export copy of a character at a new size. The copy is meant for Unreal or other game exports, and the original rig stays untouched."
            )
            description.setWordWrap(True)
            main_layout.addWidget(description)

            note = QtWidgets.QLabel(
                "Best results: put the character in the pose you want to export first, then build the copy. The copy keeps joint scale at 1,1,1 and changes bone lengths instead."
            )
            note.setWordWrap(True)
            note.setStyleSheet("color: #B8D7FF;")
            main_layout.addWidget(note)

            form = QtWidgets.QGridLayout()
            form.setHorizontalSpacing(8)
            form.setVerticalSpacing(8)

            self.character_line = QtWidgets.QLineEdit()
            self.character_line.setPlaceholderText("Optional character root or top group")
            self.skeleton_line = QtWidgets.QLineEdit()
            self.skeleton_line.setPlaceholderText("Top skeleton joint")
            self.scale_spin = QtWidgets.QDoubleSpinBox()
            self.scale_spin.setDecimals(3)
            self.scale_spin.setRange(0.001, 1000.0)
            self.scale_spin.setSingleStep(0.1)
            self.scale_spin.setValue(1.0)
            self.suffix_line = QtWidgets.QLineEdit(DEFAULT_COPY_SUFFIX)

            form.addWidget(QtWidgets.QLabel("Character Root"), 0, 0)
            form.addWidget(self.character_line, 0, 1)
            form.addWidget(QtWidgets.QLabel("Skeleton Root"), 1, 0)
            form.addWidget(self.skeleton_line, 1, 1)
            form.addWidget(QtWidgets.QLabel("Size Multiplier"), 2, 0)
            form.addWidget(self.scale_spin, 2, 1)
            form.addWidget(QtWidgets.QLabel("Copy Name Ending"), 3, 0)
            form.addWidget(self.suffix_line, 3, 1)
            main_layout.addLayout(form)

            button_grid = QtWidgets.QGridLayout()
            button_grid.setHorizontalSpacing(8)
            button_grid.setVerticalSpacing(8)
            self.use_character_button = QtWidgets.QPushButton("Use Selected Character")
            self.use_skeleton_button = QtWidgets.QPushButton("Use Selected Skeleton")
            self.analyze_button = QtWidgets.QPushButton("Check Setup")
            self.create_button = QtWidgets.QPushButton("Make Export Copy")
            self.select_button = QtWidgets.QPushButton("Select Export Copy")
            self.delete_button = QtWidgets.QPushButton("Delete Export Copy")
            button_grid.addWidget(self.use_character_button, 0, 0)
            button_grid.addWidget(self.use_skeleton_button, 0, 1)
            button_grid.addWidget(self.analyze_button, 1, 0)
            button_grid.addWidget(self.create_button, 1, 1)
            button_grid.addWidget(self.select_button, 2, 0)
            button_grid.addWidget(self.delete_button, 2, 1)
            main_layout.addLayout(button_grid)

            self.report_text = QtWidgets.QPlainTextEdit()
            self.report_text.setReadOnly(True)
            main_layout.addWidget(self.report_text, 1)

            self.status_label = QtWidgets.QLabel("Pick the character and top skeleton joint, then click Check Setup.")
            self.status_label.setWordWrap(True)
            selectable_flag = _qt_flag("TextInteractionFlag", "TextSelectableByMouse", 0)
            self.status_label.setTextInteractionFlags(selectable_flag)
            main_layout.addWidget(self.status_label)

            footer_layout = QtWidgets.QHBoxLayout()
            self.brand_label = QtWidgets.QLabel('Built by Amir. Follow Amir at <a href="{0}">followamir.com</a>.'.format(FOLLOW_AMIR_URL))
            self.brand_label.setWordWrap(True)
            self.brand_label.setOpenExternalLinks(False)
            self.brand_label.linkActivated.connect(self._open_follow_url)
            footer_layout.addWidget(self.brand_label, 1)
            self.donate_button = QtWidgets.QPushButton("Donate")
            _style_donate_button(self.donate_button)
            self.donate_button.setToolTip("Open Amir's PayPal donate link. Set AMIR_PAYPAL_DONATE_URL or AMIR_DONATE_URL to customize it.")
            self.donate_button.clicked.connect(self._open_donate_url)
            footer_layout.addWidget(self.donate_button)
            main_layout.addLayout(footer_layout)

            self.use_character_button.clicked.connect(self._use_character)
            self.use_skeleton_button.clicked.connect(self._use_skeleton)
            self.analyze_button.clicked.connect(self._analyze)
            self.create_button.clicked.connect(self._create_copy)
            self.select_button.clicked.connect(self._select_copy)
            self.delete_button.clicked.connect(self._delete_copy)
            self.scale_spin.valueChanged.connect(self._sync_controller_values)
            self.character_line.editingFinished.connect(self._sync_controller_values)
            self.skeleton_line.editingFinished.connect(self._sync_controller_values)
            self.suffix_line.editingFinished.connect(self._sync_controller_values)

        def _sync_controller_values(self):
            self.controller.character_root = self.character_line.text().strip()
            self.controller.skeleton_root = self.skeleton_line.text().strip()
            self.controller.scale_factor = float(self.scale_spin.value())
            self.controller.copy_suffix = self.suffix_line.text().strip() or DEFAULT_COPY_SUFFIX

        def _refresh_report(self):
            self.report_text.setPlainText(self.controller.report_text())

        def _set_status(self, message, success):
            self.status_label.setText(message)

        def _use_character(self):
            success, message = self.controller.set_character_from_selection()
            if success:
                self.character_line.setText(self.controller.character_root)
            self._refresh_report()
            self._set_status(message, success)

        def _use_skeleton(self):
            success, message = self.controller.set_skeleton_from_selection()
            if success:
                self.skeleton_line.setText(self.controller.skeleton_root)
            self._refresh_report()
            self._set_status(message, success)

        def _analyze(self):
            self._sync_controller_values()
            success, message = self.controller.analyze_setup()
            self._refresh_report()
            self._set_status(message, success)

        def _create_copy(self):
            self._sync_controller_values()
            success, message = self.controller.create_export_copy()
            self._refresh_report()
            self._set_status(message, success)

        def _select_copy(self):
            success, message = self.controller.select_export_copy()
            self._set_status(message, success)

        def _delete_copy(self):
            success, message = self.controller.delete_export_copy()
            self._refresh_report()
            self._set_status(message, success)

        def _open_follow_url(self, url=None):
            if _open_external_url(url or FOLLOW_AMIR_URL):
                self._set_status("Opened followamir.com.", True)
            else:
                self._set_status("Could not open followamir.com from this Maya session.", False)

        def _open_donate_url(self):
            if not DONATE_URL:
                self._set_status("Donate link is not set. Use AMIR_PAYPAL_DONATE_URL or AMIR_DONATE_URL.", False)
                return
            if _open_external_url(DONATE_URL):
                self._set_status("Opened the donate page.", True)
            else:
                self._set_status("Could not open the donate page from this Maya session.", False)


def _close_existing_window():
    global GLOBAL_CONTROLLER
    global GLOBAL_WINDOW
    if GLOBAL_WINDOW is not None:
        try:
            GLOBAL_WINDOW.close()
            GLOBAL_WINDOW.deleteLater()
        except Exception:
            pass
    if MAYA_AVAILABLE and cmds and cmds.workspaceControl(WORKSPACE_CONTROL_NAME, exists=True):
        try:
            cmds.deleteUI(WORKSPACE_CONTROL_NAME, control=True)
        except Exception:
            pass
    if QtWidgets:
        application = QtWidgets.QApplication.instance()
        if application and hasattr(application, "topLevelWidgets"):
            for widget in application.topLevelWidgets():
                try:
                    if widget.objectName() == WINDOW_OBJECT_NAME:
                        widget.close()
                        widget.deleteLater()
                except Exception:
                    pass
    GLOBAL_CONTROLLER = None
    GLOBAL_WINDOW = None


def launch_maya_rig_scale_export(dock=False):
    global GLOBAL_CONTROLLER
    global GLOBAL_WINDOW
    if not MAYA_AVAILABLE:
        raise RuntimeError("maya_rig_scale_export.launch_maya_rig_scale_export() must run inside Autodesk Maya.")
    if not QtWidgets:
        raise RuntimeError("PySide is not available in this Maya session.")
    _close_existing_window()
    GLOBAL_CONTROLLER = MayaRigScaleExportController()
    GLOBAL_WINDOW = MayaRigScaleExportWindow(GLOBAL_CONTROLLER, parent=_maya_main_window())
    GLOBAL_WINDOW.show()
    GLOBAL_WINDOW.raise_()
    GLOBAL_WINDOW.activateWindow()
    return GLOBAL_WINDOW


__all__ = [
    "launch_maya_rig_scale_export",
    "MayaRigScaleExportController",
]
