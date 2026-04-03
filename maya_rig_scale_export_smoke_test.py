from __future__ import absolute_import, division, print_function

import os
import sys
import traceback

import maya.standalone


try:
    maya.standalone.initialize(name="python")
except RuntimeError as exc:
    if "inside of Maya" not in str(exc):
        raise

import maya.cmds as cmds  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import maya_rig_scale_export  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _world_translation(node_name):
    return cmds.xform(node_name, query=True, worldSpace=True, translation=True)


def _distance(a, b):
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def _build_scene(prefix, group_scale, group_rotation):
    rig_group = cmds.createNode("transform", name=prefix + "_source_GRP")
    cmds.setAttr(rig_group + ".scaleX", group_scale[0])
    cmds.setAttr(rig_group + ".scaleY", group_scale[1])
    cmds.setAttr(rig_group + ".scaleZ", group_scale[2])
    cmds.setAttr(rig_group + ".rotateX", group_rotation[0])
    cmds.setAttr(rig_group + ".rotateY", group_rotation[1])
    cmds.setAttr(rig_group + ".rotateZ", group_rotation[2])

    root_joint = cmds.createNode("joint", name=prefix + "_root_jnt", parent=rig_group)
    mid_joint = cmds.createNode("joint", name=prefix + "_mid_jnt", parent=root_joint)
    cmds.setAttr(root_joint + ".translateX", 3.0)
    cmds.setAttr(root_joint + ".translateY", 5.0)
    cmds.setAttr(mid_joint + ".translateY", 4.0)

    mesh = cmds.polyCube(
        name=prefix + "_body_geo",
        width=2.0,
        height=4.0,
        depth=1.5,
        subdivisionsY=2,
    )[0]
    mesh = cmds.parent(mesh, rig_group)[0]
    cmds.xform(mesh, objectSpace=True, translation=(3.0, 2.0, 0.0))

    skin_cluster = cmds.skinCluster([root_joint, mid_joint], mesh, toSelectedBones=True, name=prefix + "_skinCluster")[0]
    cmds.skinPercent(skin_cluster, mesh + ".vtx[0:3]", transformValue=[(root_joint, 1.0), (mid_joint, 0.0)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[4:7]", transformValue=[(root_joint, 0.5), (mid_joint, 0.5)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[8:11]", transformValue=[(root_joint, 0.1), (mid_joint, 0.9)])
    return rig_group, root_joint, mid_joint, mesh


def _run_case(prefix, group_scale, group_rotation, export_scale):
    cmds.file(new=True, force=True)
    rig_group, root_joint, mid_joint, mesh = _build_scene(prefix, group_scale, group_rotation)

    controller = maya_rig_scale_export.MayaRigScaleExportController()
    controller.character_root = rig_group
    controller.skeleton_root = root_joint
    controller.scale_factor = export_scale
    source_root_long = maya_rig_scale_export._node_long_name(root_joint)
    source_mid_long = maya_rig_scale_export._node_long_name(mid_joint)

    success, message = controller.analyze_setup()
    _assert(success, message)
    _assert(not controller.report["errors"], controller.report_text())

    source_distance = _distance(_world_translation(root_joint), _world_translation(mid_joint))

    success, message = controller.create_export_copy()
    _assert(success, "Rig Scale create failed: {0}\n{1}".format(message, controller.report_text()))
    _assert(controller.result["verified"], controller.report_text())
    _assert(cmds.objExists(controller.result["export_group"]), "Export group should exist")

    root_long = source_root_long
    mid_long = source_mid_long

    for duplicate_joint in controller.result["joint_map"].values():
        scale = cmds.getAttr(duplicate_joint + ".scale")[0]
        _assert(all(abs(value - 1.0) <= 0.00001 for value in scale), "Copied joints should stay at 1,1,1 scale")

    duplicate_root = controller.result["joint_map"][root_long]
    duplicate_mid = controller.result["joint_map"][mid_long]
    duplicate_distance = _distance(_world_translation(duplicate_root), _world_translation(duplicate_mid))
    _assert(abs(duplicate_distance - (source_distance * export_scale)) <= 0.001, "Bone length should scale from the current visible size")

    mesh_result = controller.result["mesh_results"][0]
    duplicate_scale = cmds.getAttr(mesh_result["duplicate_transform"] + ".scale")[0]
    _assert(all(abs(value - 1.0) <= 0.00001 for value in duplicate_scale), "Copied mesh scale should be 1,1,1")
    _assert(mesh_result["verification"]["passed"], controller.report_text())

    success, message = controller.select_export_copy()
    _assert(success, message)
    _assert(cmds.ls(selection=True, long=True)[0] == controller.result["export_group"], "Select Export Copy should select the export group")

    success, message = controller.delete_export_copy()
    _assert(success, message)
    _assert(not cmds.objExists(controller.result["export_group"]) if controller.result else True, "Export group should delete cleanly")


def run():
    _run_case("rigScaleUniform", (1.5, 1.5, 1.5), (0.0, 0.0, 0.0), 2.0)

    cmds.file(new=True, force=True)
    rig_group, root_joint, mid_joint, mesh = _build_scene("rigScaleRotated", (1.2, 1.2, 1.2), (0.0, 35.0, 0.0))
    controller = maya_rig_scale_export.MayaRigScaleExportController()
    controller.character_root = rig_group
    controller.skeleton_root = root_joint
    controller.scale_factor = 1.8
    success, message = controller.analyze_setup()
    _assert(success, message)
    warning_text = "\n".join(controller.report.get("warnings", []))
    _assert("rotated" in warning_text.lower(), "Rotated parent rigs should warn before export copy creation")

    print("MAYA_RIG_SCALE_EXPORT_SMOKE_TEST: PASS")


if __name__ == "__main__":
    exit_code = 0
    try:
        run()
    except Exception:
        exit_code = 1
        traceback.print_exc()
        print("MAYA_RIG_SCALE_EXPORT_SMOKE_TEST: FAIL")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        os._exit(exit_code)
