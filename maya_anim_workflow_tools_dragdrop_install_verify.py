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
    package_root = REPO_ROOT / "student_package" / "maya_anim_workflow_tools"
    code = """
import importlib
import json
import os
import sys
import traceback

repo_path = r"{repo_path}"
package_root = r"{package_root}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)
if package_root not in sys.path:
    sys.path.insert(0, package_root)

try:
    import maya.cmds as cmds
    import maya_dynamic_parent_pivot
    import install_maya_anim_workflow_tools_dragdrop
    importlib.reload(maya_dynamic_parent_pivot)
    importlib.reload(install_maya_anim_workflow_tools_dragdrop)

    maya_dynamic_parent_pivot._close_existing_window()
    install_result = install_maya_anim_workflow_tools_dragdrop.install_maya_anim_workflow_tools_from_dragdrop()
    import maya_anim_workflow_tools
    importlib.reload(maya_anim_workflow_tools)
    docked_window = maya_anim_workflow_tools.launch_maya_anim_workflow_tools(dock=True, initial_tab="quick_start")

    parent_chain = []
    walker = docked_window
    while walker is not None:
        try:
            parent_chain.append(walker.objectName() or walker.__class__.__name__)
        except Exception:
            parent_chain.append(str(type(walker)))
        try:
            walker = walker.parentWidget()
        except Exception:
            break

    install_root = install_maya_anim_workflow_tools_dragdrop._install_root(cmds)
    result = {{
        "ok": True,
        "install_result": install_result,
        "install_root": install_root,
        "workspace_exists": bool(cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, exists=True)),
        "workspace_floating": bool(cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, query=True, floating=True)) if cmds.workspaceControl(maya_dynamic_parent_pivot.WORKSPACE_CONTROL_NAME, exists=True) else None,
        "parent_chain": parent_chain,
        "window_title": docked_window.windowTitle(),
    }}
except Exception:
    result = {{
        "ok": False,
        "traceback": traceback.format_exc(),
    }}
""".format(
        repo_path=str(REPO_ROOT).replace("\\", "\\\\"),
        package_root=str(package_root).replace("\\", "\\\\"),
    )

    payload = run_bridge_exec_python(code, timeout=120)
    result = payload.get("result") or {}
    if not result.get("ok"):
        raise AssertionError(json.dumps(payload, indent=2))
    if not pathlib.Path(result.get("install_root") or "").exists():
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("window_title") != "Maya Anim Workflow Tools":
        raise AssertionError(json.dumps(payload, indent=2))
    if not result.get("workspace_exists"):
        raise AssertionError(json.dumps(payload, indent=2))
    if result.get("workspace_floating"):
        raise AssertionError(json.dumps(payload, indent=2))
    if "mayaAnimWorkflowToolsWindowWorkspaceControl" not in (result.get("parent_chain") or []):
        raise AssertionError(json.dumps(payload, indent=2))

    print("MAYA_ANIM_WORKFLOW_TOOLS_DRAGDROP_INSTALL_VERIFY: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
