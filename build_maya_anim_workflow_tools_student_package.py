from __future__ import absolute_import, division, print_function

import json
import pathlib
import shutil
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent
PACKAGE_ROOT = REPO_ROOT / "student_package" / "maya_anim_workflow_tools"
PAYLOAD_ROOT = PACKAGE_ROOT / "maya_anim_workflow_tools_package"
ZIP_PATH = REPO_ROOT / "student_package" / "Amirs_Maya_Anim_Workflow_Tools_v0.1_BETA.zip"
INSTALLER_SOURCE = REPO_ROOT / "install_maya_anim_workflow_tools_dragdrop.py"
MANIFEST_FILE_NAME = "manifest.json"
RELEASE_VERSION_LABEL = "Version 0.1 BETA"
RELEASE_TAG = "v0.1-beta"
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


def build_student_package():
    if PACKAGE_ROOT.exists():
        shutil.rmtree(PACKAGE_ROOT)
    PAYLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    if ZIP_PATH.exists():
        ZIP_PATH.unlink()

    shutil.copy2(str(INSTALLER_SOURCE), str(PACKAGE_ROOT / INSTALLER_SOURCE.name))
    for file_name in RUNTIME_FILES:
        shutil.copy2(str(REPO_ROOT / file_name), str(PAYLOAD_ROOT / file_name))

    manifest = {
        "package_name": "AmirMayaAnimWorkflowTools",
        "version": RELEASE_VERSION_LABEL,
        "release_tag": RELEASE_TAG,
        "runtime_files": list(RUNTIME_FILES),
    }
    (PAYLOAD_ROOT / MANIFEST_FILE_NAME).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (PACKAGE_ROOT / "README.txt").write_text(
        "\n".join(
            [
                "Maya Anim Workflow Tools student package",
                "",
                "How to install or update:",
                "1. Open Maya.",
                "2. Drag install_maya_anim_workflow_tools_dragdrop.py into the Maya viewport.",
                "3. The tool will update the installed files, refresh the shelf button, open the tool, and dock it.",
                "",
                "If you already installed an older version, drag the new installer into Maya again.",
            ]
        ),
        encoding="utf-8",
    )
    for pycache_dir in PACKAGE_ROOT.rglob("__pycache__"):
        shutil.rmtree(pycache_dir, ignore_errors=True)
    shutil.make_archive(str(ZIP_PATH.with_suffix("")), "zip", str(PACKAGE_ROOT.parent), PACKAGE_ROOT.name)
    return manifest


def main():
    manifest = build_student_package()
    print("Built student package at {0}".format(PACKAGE_ROOT))
    print("Version: {0}".format(manifest["version"]))
    print("Zip: {0}".format(ZIP_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
