from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import textwrap
import time
import urllib.error
import urllib.request

from PIL import ImageGrab
from pywinauto import Desktop


REPO_ROOT = pathlib.Path(__file__).resolve().parent
BROKER = REPO_ROOT.parent / "codex-desktop-broker" / "broker.py"
SCREENSHOT_DIR = REPO_ROOT / "screenshots"
MAYA_TITLE_RE = ".*Autodesk MAYA 2026.*"


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


def maya_window():
    return Desktop(backend="uia").window(title_re=MAYA_TITLE_RE)


def focus_maya_window():
    window = maya_window()
    try:
        if window.is_minimized():
            window.restore()
    except Exception:
        pass
    window.set_focus()
    return window


def capture_window(path: pathlib.Path, crop_right=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    window = focus_maya_window()
    time.sleep(1.0)
    rect = window.rectangle()
    image = ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom))
    if crop_right is not None:
        crop_width = min(crop_right, image.width)
        image = image.crop((image.width - crop_width, 0, image.width, image.height))
    image.save(str(path))
    return str(path)


def capture_tool_crop(source_path: pathlib.Path, path: pathlib.Path):
    code = textwrap.dedent(
        """
import maya_onion_skin

window = maya_onion_skin.GLOBAL_WINDOW
if not window:
    result = {{"ok": False, "message": "Maya Onion Skin window is not open."}}
else:
    window.show()
    window.raise_()
    window.activateWindow()
    if maya_onion_skin.QtWidgets:
        maya_onion_skin.QtWidgets.QApplication.processEvents()
    saved = window.grab().save(r"{path}")
    result = {{"ok": bool(saved), "path": r"{path}"}}
"""
    ).format(path=str(path).replace("\\", "\\\\"))
    payload = run_exec_python(code)
    result = payload.get("result") or {}
    if not result.get("ok"):
        raise RuntimeError(json.dumps(payload, indent=2))
    return str(path)


def run_exec_python(code: str) -> dict:
    payload = json.dumps({"action": "exec_python", "args": {"code": code}}).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:62225/command",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        raise RuntimeError("Bridge HTTP {0}: {1}".format(exc.code, body))


def set_frame(frame: int):
    code = textwrap.dedent(
        """
import maya.cmds as cmds
import maya_onion_skin

cmds.currentTime({frame}, edit=True, update=True)
if maya_onion_skin.GLOBAL_WINDOW and maya_onion_skin.GLOBAL_WINDOW.controller:
    maya_onion_skin.GLOBAL_WINDOW.controller.refresh(rebuild=False, reason="demo")
result = {{"frame": cmds.currentTime(query=True)}}
"""
    ).format(frame=frame)
    run_exec_python(code)


def main() -> int:
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

    setup_code = textwrap.dedent(
        """
import importlib
import sys
import traceback

repo_path = r"{repo_path}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya_onion_skin_demo_setup
    maya_onion_skin_demo_setup = importlib.reload(maya_onion_skin_demo_setup)
    result = {{"ok": True, "data": maya_onion_skin_demo_setup.prepare_demo(open_tool=True, dock=False)}}
except Exception:
    result = {{"ok": False, "traceback": traceback.format_exc()}}
"""
    ).format(repo_path=str(REPO_ROOT).replace("\\", "\\\\"))

    setup_result = run_exec_python(setup_code)
    setup_payload = setup_result.get("result") or {}
    if not setup_payload.get("ok"):
        raise RuntimeError(json.dumps(setup_result, indent=2))

    time.sleep(1.5)
    overview_path = SCREENSHOT_DIR / "maya_onion_skin_demo_overview.png"
    overview = capture_window(overview_path)
    panel = capture_tool_crop(overview_path, SCREENSHOT_DIR / "maya_onion_skin_demo_panel.png")

    set_frame(32)
    time.sleep(0.8)
    frame32 = capture_window(SCREENSHOT_DIR / "maya_onion_skin_demo_frame32.png")

    print(
        json.dumps(
            {
                "overview": overview,
                "panel": panel,
                "frame32": frame32,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
