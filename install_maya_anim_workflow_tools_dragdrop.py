from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import sys
import traceback


PACKAGE_FOLDER_NAME = "Aminate"
PAYLOAD_DIR_NAME = "maya_anim_workflow_tools_package"
MANIFEST_FILE_NAME = "manifest.json"
RUNTIME_FILES = [
    "maya_anim_workflow_tools.py",
    "maya_animators_pencil.py",
    "maya_contact_hold.py",
    "maya_crash_recovery.py",
    "maya_dynamic_parent_pivot.py",
    "maya_dynamic_parenting_tool.py",
    "maya_control_picker.py",
    "maya_face_retarget.py",
    "maya_reference_manager.py",
    "maya_onion_skin.py",
    "maya_surface_contact.py",
    "maya_rig_scale_export.py",
    "maya_rotation_doctor.py",
    "maya_timing_tools.py",
    "maya_shelf_utils.py",
    "maya_skinning_cleanup.py",
    "maya_timeline_notes.py",
    "maya_universal_ikfk_switcher.py",
    "maya_video_reference_tool.py",
    "maya_anim_workflow_tools_icon.png",
]


def _managed_user_setup_block(destination_root):
    return "\n".join(
        [
            "try:",
            "    import sys",
            "    import maya.utils as _amir_maya_utils",
            "    _amir_workflow_root = r\"{0}\"".format(destination_root),
            "    if _amir_workflow_root not in sys.path:",
            "        sys.path.insert(0, _amir_workflow_root)",
            "    def _amir_workflow_bootstrap_startup():",
            "        try:",
            "            import maya_crash_recovery as _amir_maya_crash_recovery",
            "            _amir_maya_crash_recovery.bootstrap_crash_recovery(startup_prompt=True)",
            "        except Exception:",
            "            pass",
            "        try:",
            "            import maya_anim_workflow_tools as _amir_maya_anim_workflow_tools",
            "            _amir_maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True, initial_tab='quick_start')",
            "        except Exception:",
            "            pass",
            "    _amir_maya_utils.executeDeferred(_amir_workflow_bootstrap_startup)",
            "except Exception:",
            "    pass",
        ]
    )


def _upsert_block(text_value, begin_marker, end_marker, block_body):
    managed_block = "{0}\n{1}\n{2}\n".format(begin_marker, block_body.rstrip(), end_marker)
    if begin_marker in text_value and end_marker in text_value:
        prefix, remainder = text_value.split(begin_marker, 1)
        _, suffix = remainder.split(end_marker, 1)
        updated = prefix.rstrip() + "\n\n" + managed_block + suffix.lstrip("\r\n")
        return updated
    if text_value and not text_value.endswith(("\n", "\r")):
        text_value += "\n"
    if text_value:
        text_value += "\n"
    return text_value + managed_block


def _ensure_user_setup_hook(cmds, destination_root):
    import maya_crash_recovery

    scripts_dir = cmds.internalVar(userScriptDir=True)
    user_setup_path = os.path.join(scripts_dir, "userSetup.py")
    existing_text = ""
    if os.path.exists(user_setup_path):
        with open(user_setup_path, "r") as handle:
            existing_text = handle.read()
    updated_text = _upsert_block(
        existing_text,
        maya_crash_recovery.USER_SETUP_BEGIN,
        maya_crash_recovery.USER_SETUP_END,
        _managed_user_setup_block(destination_root),
    )
    if updated_text != existing_text:
        with open(user_setup_path, "w") as handle:
            handle.write(updated_text)


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
    for module_name in list(sys.modules):
        if module_name.startswith("maya_"):
            sys.modules.pop(module_name, None)
    import maya_anim_workflow_tools

    importlib.reload(maya_anim_workflow_tools)
    import maya_crash_recovery
    importlib.reload(maya_crash_recovery)
    _ensure_user_setup_hook(cmds, destination_root)
    maya_crash_recovery.bootstrap_crash_recovery(startup_prompt=False)
    button_name = maya_anim_workflow_tools.install_maya_anim_workflow_tools_shelf_button(repo_path=destination_root)
    window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True)
    version = manifest.get("version") or "unknown"
    cmds.inViewMessage(
        amg='Installed <hl>Aminate</hl> {0}'.format(version),
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
