from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request


REPO_ROOT = pathlib.Path(__file__).resolve().parent
BROKER = REPO_ROOT.parent / "codex-desktop-broker" / "broker.py"
BOOTSTRAP = REPO_ROOT / "maya_live_bridge_bootstrap.py"
BRIDGE_URL = "http://127.0.0.1:62225"
OUTPUT_DIR = REPO_ROOT / "release_screenshots"


def run_broker(*args: str) -> dict:
    completed = subprocess.run(
        [sys.executable, str(BROKER), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if not completed.stdout.strip():
        raise RuntimeError("Broker did not produce JSON output: {0}".format(completed.stderr))
    payload = json.loads(completed.stdout)
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(payload, indent=2))
    return payload


def ensure_bridge() -> None:
    try:
        run_broker(
            "app-command",
            "run",
            "--app",
            "maya",
            "--command",
            "capture_status",
            "--ensure-bridge",
            "--allow-foreground-bootstrap",
        )
        return
    except Exception:
        completed = subprocess.run(
            [sys.executable, str(BOOTSTRAP)],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr or completed.stdout or "Maya bridge bootstrap failed.")
        run_broker(
            "app-command",
            "run",
            "--app",
            "maya",
            "--command",
            "capture_status",
            "--ensure-bridge",
        )


def run_bridge_exec_python(code: str, timeout: int = 120) -> dict:
    payload = json.dumps({"action": "exec_python", "args": {"code": code}}).encode("utf-8")
    request = urllib.request.Request(
        BRIDGE_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(raw)

    result = json.loads(raw)
    if not result.get("ok"):
        raise RuntimeError(json.dumps(result, indent=2))
    return result


def main() -> int:
    ensure_bridge()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    code = """
import importlib
import os
import sys
import traceback

repo_path = r"{repo_path}"
output_dir = r"{output_dir}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya_anim_workflow_tools
    import maya_dynamic_parent_pivot
    importlib.reload(maya_anim_workflow_tools)
    importlib.reload(maya_dynamic_parent_pivot)
    maya_dynamic_parent_pivot._close_existing_window()
    window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True, initial_tab="quick_start")
    app = maya_dynamic_parent_pivot.QtWidgets.QApplication.instance()
    if app:
        app.processEvents()
    tab_map = [
        ("quick_start", "Quick Start"),
        ("dynamic_parenting", "Dynamic Parenting"),
        ("hand_foot_hold", "Hand / Foot Hold"),
        ("dynamic_pivot", "Dynamic Pivot"),
        ("universal_ikfk", "Universal IK/FK"),
        ("onion_skin", "Onion Skin"),
        ("rotation_doctor", "Rotation Doctor"),
        ("skinning_cleanup", "Skinning Cleanup"),
        ("rig_scale", "Rig Scale"),
        ("video_reference", "Video Reference"),
        ("timeline_notes", "Timeline Notes"),
    ]
    saved_files = []
    for file_stem, label in tab_map:
        for index in range(window.tab_widget.count()):
            if window.tab_widget.tabText(index) == label:
                window.tab_widget.setCurrentIndex(index)
                if app:
                    app.processEvents()
                file_path = os.path.join(output_dir, file_stem + ".png")
                window.grab().save(file_path)
                saved_files.append(file_path)
                break
    result = {{"ok": True, "files": saved_files}}
except Exception:
    result = {{"ok": False, "traceback": traceback.format_exc()}}
""".format(
        repo_path=str(REPO_ROOT).replace("\\", "\\\\"),
        output_dir=str(OUTPUT_DIR).replace("\\", "\\\\"),
    )
    payload = run_bridge_exec_python(code, timeout=180)
    result = payload.get("result") or {}
    if not result.get("ok"):
        raise AssertionError(json.dumps(payload, indent=2))
    print("MAYA_ANIM_WORKFLOW_TOOL_SCREENSHOTS: PASS")
    for path in result.get("files") or []:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
