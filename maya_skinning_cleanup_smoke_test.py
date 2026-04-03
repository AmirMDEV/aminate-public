from __future__ import absolute_import, division, print_function

import importlib.util
import os
import traceback

import maya.standalone


try:
    maya.standalone.initialize(name="python")
except RuntimeError as exc:
    if "inside of Maya" not in str(exc):
        raise

import maya.cmds as cmds  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
MODULE_PATH = os.path.join(THIS_DIR, "maya_skinning_cleanup.py")


def _load_module():
    spec = importlib.util.spec_from_file_location("maya_skinning_cleanup", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _shader_group(shader_name):
    shading_group = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=shader_name + "SG")
    cmds.connectAttr(shader_name + ".outColor", shading_group + ".surfaceShader", force=True)
    return shading_group


def _build_supported_scene():
    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    root_joint = cmds.joint(name="skinClean_root_jnt", position=(0.0, 0.0, 0.0))
    mid_joint = cmds.joint(name="skinClean_mid_jnt", position=(0.0, 4.0, 0.0))
    cmds.select(clear=True)

    mesh = cmds.polyCube(name="badScale_geo", width=2.0, height=3.0, depth=1.5, subdivisionsY=2)[0]
    cmds.xform(mesh, worldSpace=True, translation=(3.0, 1.0, -2.0), rotation=(10.0, 25.0, 5.0), scale=(1.8, 0.7, 1.3))
    cmds.polySoftEdge(mesh, angle=180, constructionHistory=False)
    cmds.polySoftEdge(mesh + ".e[0:3]", angle=0, constructionHistory=False)

    try:
        cmds.polyUVSet(mesh, create=True, uvSet="detailUV")
        cmds.polyUVSet(mesh, currentUVSet=True, uvSet="detailUV")
    except Exception:
        pass

    try:
        cmds.polyColorPerVertex(mesh + ".vtx[0:3]", rgb=(1.0, 0.2, 0.2), colorDisplayOption=True)
    except Exception:
        pass

    shader_a = cmds.shadingNode("lambert", asShader=True, name="skinClean_red")
    shader_b = cmds.shadingNode("lambert", asShader=True, name="skinClean_blue")
    sg_a = _shader_group(shader_a)
    sg_b = _shader_group(shader_b)
    cmds.sets(mesh + ".f[0:2]", edit=True, forceElement=sg_a)
    cmds.sets(mesh + ".f[3:5]", edit=True, forceElement=sg_b)

    skin_cluster = cmds.skinCluster([root_joint, mid_joint], mesh, toSelectedBones=True, name="badScale_skinCluster")[0]
    cmds.skinPercent(skin_cluster, mesh + ".vtx[0:3]", transformValue=[(root_joint, 1.0), (mid_joint, 0.0)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[4:7]", transformValue=[(root_joint, 0.5), (mid_joint, 0.5)])
    cmds.skinPercent(skin_cluster, mesh + ".vtx[8:11]", transformValue=[(root_joint, 0.1), (mid_joint, 0.9)])
    return mesh


def _build_unsupported_scene():
    cmds.file(new=True, force=True)
    root_joint = cmds.joint(name="unsupported_root_jnt", position=(0.0, 0.0, 0.0))
    mid_joint = cmds.joint(name="unsupported_mid_jnt", position=(0.0, 3.0, 0.0))
    cmds.select(clear=True)
    mesh = cmds.polySphere(name="unsupported_geo")[0]
    skin_cluster = cmds.skinCluster([root_joint, mid_joint], mesh, toSelectedBones=True, name="unsupported_skinCluster")[0]
    del skin_cluster
    driver = cmds.duplicate(mesh, name="unsupported_driver")[0]
    cmds.blendShape(driver, mesh, name="unsupported_blendShape")
    return mesh


def run():
    module = _load_module()

    mesh = _build_supported_scene()
    controller = module.MayaSkinningCleanupController()
    cmds.select(mesh, replace=True)
    success, message = controller.analyze_selection()
    _assert(success, "Analyze failed: {0}".format(message))
    _assert(not controller.report["errors"], controller.report_text())

    source_scale = cmds.getAttr(mesh + ".scale")[0]
    success, message = controller.create_clean_copy()
    _assert(success, "Create clean copy failed: {0}\n{1}".format(message, controller.report_text()))
    _assert(controller.result["verified"], controller.report_text())

    clean_transform = controller.result["clean_transform"]
    clean_scale = cmds.getAttr(clean_transform + ".scale")[0]
    _assert(all(abs(value - 1.0) <= module.VALUE_EPSILON for value in clean_scale), "Clean mesh scale should be 1,1,1")
    _assert(any(abs(source_scale[index] - 1.0) > 0.001 for index in range(3)), "Source mesh should keep the bad scale before replace")
    _assert(controller.result["verification"]["passed"], controller.report_text())

    success, message = controller.replace_original()
    _assert(success, "Replace original failed: {0}".format(message))
    _assert(cmds.objExists("badScale_geo"), "Final clean mesh should keep the original name")
    _assert(controller.result.get("backup_transform"), "Original mesh should remain as a backup")

    unsupported_mesh = _build_unsupported_scene()
    failure_controller = module.MayaSkinningCleanupController()
    cmds.select(unsupported_mesh, replace=True)
    success, message = failure_controller.analyze_selection()
    _assert(not success, "Unsupported mesh should fail analysis")
    _assert("Unsupported extra deformation history" in failure_controller.report_text(), failure_controller.report_text())

    print("MAYA_SKINNING_CLEANUP_SMOKE_TEST: PASS")


if __name__ == "__main__":
    try:
        run()
    except Exception:
        traceback.print_exc()
        print("MAYA_SKINNING_CLEANUP_SMOKE_TEST: FAIL")
