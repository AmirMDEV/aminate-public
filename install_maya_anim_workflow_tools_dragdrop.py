from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import traceback


PACKAGE_FOLDER_NAME = "AmirMayaAnimWorkflowTools"
PAYLOAD_DIR_NAME = "maya_anim_workflow_tools_package"
MANIFEST_FILE_NAME = "manifest.json"
RUNTIME_FILES = [
    "maya_anim_workflow_tools.py",
    "maya_contact_hold.py",
    "maya_dynamic_parent_pivot.py",
    "maya_dynamic_parenting_tool.py",
    "maya_onion_skin.py",
    "maya_rig_scale_export.py",
    "maya_rotation_doctor.py",
    "maya_shelf_utils.py",
    "maya_skinning_cleanup.py",
    "maya_timeline_notes.py",
    "maya_universal_ikfk_switcher.py",
    "maya_video_reference_tool.py",
]


def _maya_api():
    import maya.cmds as cmds  # type: ignore

    return cmds


def _source_root():
    here = os.path.dirname(os.path.abspath(__file__))
    packaged_root = os.path.join(here, PAYLOAD_DIR_NAME)
    if os.path.isdir(packaged_root):
        return packaged_root
    return here


def _load_manifest(source_root):
    manifest_path = os.path.join(source_root, MANIFEST_FILE_NAME)
    if not os.path.exists(manifest_path):
        return {
            "package_name": PACKAGE_FOLDER_NAME,
            "version": "dev",
            "runtime_files": list(RUNTIME_FILES),
        }
    with open(manifest_path, "r") as handle:
        return json.load(handle)


def _install_root(cmds):
    scripts_dir = cmds.internalVar(userScriptDir=True)
    return os.path.join(scripts_dir, PACKAGE_FOLDER_NAME)


def _copy_runtime_files(source_root, destination_root, runtime_files):
    if not os.path.isdir(destination_root):
        os.makedirs(destination_root)
    for file_name in runtime_files:
        source_path = os.path.join(source_root, file_name)
        if not os.path.exists(source_path):
            raise RuntimeError("Missing runtime file in installer payload: {0}".format(file_name))
        shutil.copy2(source_path, os.path.join(destination_root, file_name))
    manifest_path = os.path.join(source_root, MANIFEST_FILE_NAME)
    if os.path.exists(manifest_path):
        shutil.copy2(manifest_path, os.path.join(destination_root, MANIFEST_FILE_NAME))


def install_maya_anim_workflow_tools_from_dragdrop():
    cmds = _maya_api()
    source_root = _source_root()
    manifest = _load_manifest(source_root)
    runtime_files = manifest.get("runtime_files") or list(RUNTIME_FILES)
    destination_root = _install_root(cmds)
    _copy_runtime_files(source_root, destination_root, runtime_files)

    if destination_root not in sys.path:
        sys.path.insert(0, destination_root)

    import importlib
    import maya_anim_workflow_tools

    importlib.reload(maya_anim_workflow_tools)
    button_name = maya_anim_workflow_tools.install_maya_anim_workflow_tools_shelf_button(repo_path=destination_root)
    window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True)
    version = manifest.get("version") or "unknown"
    cmds.inViewMessage(
        amg='Installed <hl>Maya Anim Workflow Tools</hl> {0}'.format(version),
        pos="midCenterTop",
        fade=True,
    )
    return {
        "button_name": button_name,
        "destination_root": destination_root,
        "version": version,
        "window_title": window.windowTitle() if window else "",
    }


def onMayaDroppedPythonFile(*_args):
    try:
        result = install_maya_anim_workflow_tools_from_dragdrop()
        print("MAYA_ANIM_WORKFLOW_TOOLS_DRAGDROP_INSTALL: {0}".format(json.dumps(result, sort_keys=True)))
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    try:
        result = install_maya_anim_workflow_tools_from_dragdrop()
        print("MAYA_ANIM_WORKFLOW_TOOLS_DRAGDROP_INSTALL: {0}".format(json.dumps(result, sort_keys=True)))
    except Exception:
        traceback.print_exc()
        raise
