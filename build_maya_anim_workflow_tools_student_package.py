from __future__ import absolute_import, division, print_function

import json
import pathlib
import shutil
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent
PACKAGE_ROOT = REPO_ROOT / "student_package" / "maya_anim_workflow_tools"
PAYLOAD_ROOT = PACKAGE_ROOT / "maya_anim_workflow_tools_package"
INSTALLER_SOURCE = REPO_ROOT / "install_maya_anim_workflow_tools_dragdrop.py"
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


def _git_version():
    completed = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=str(REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    version = completed.stdout.strip()
    return version or "unknown"


def build_student_package():
    if PACKAGE_ROOT.exists():
        shutil.rmtree(PACKAGE_ROOT)
    PAYLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    shutil.copy2(str(INSTALLER_SOURCE), str(PACKAGE_ROOT / INSTALLER_SOURCE.name))
    for file_name in RUNTIME_FILES:
        shutil.copy2(str(REPO_ROOT / file_name), str(PAYLOAD_ROOT / file_name))

    manifest = {
        "package_name": "AmirMayaAnimWorkflowTools",
        "version": _git_version(),
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
    return manifest


def main():
    manifest = build_student_package()
    print("Built student package at {0}".format(PACKAGE_ROOT))
    print("Version: {0}".format(manifest["version"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
