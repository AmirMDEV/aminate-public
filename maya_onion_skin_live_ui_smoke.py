from __future__ import annotations

import json
import pathlib
import subprocess
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent
BROKER = REPO_ROOT.parent / "codex-desktop-broker" / "broker.py"


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

    code = """
import importlib
import sys
import traceback

repo_path = r"{repo_path}"
if repo_path not in sys.path:
    sys.path.insert(0, repo_path)

try:
    import maya_onion_skin
    importlib.reload(maya_onion_skin)
    window = maya_onion_skin.launch_maya_onion_skin()
    result = {{
        "ok": True,
        "window_title": window.windowTitle(),
        "display_mode_count": window.display_mode_combo.count(),
        "display_mode_items": [window.display_mode_combo.itemText(index) for index in range(window.display_mode_combo.count())],
        "frame_step_min": window.frame_step_spin.minimum(),
        "frame_step_max": window.frame_step_spin.maximum(),
        "add_button_text": window.add_button.text(),
        "brand_text": window.brand_label.text(),
        "donate_tooltip": window.donate_button.toolTip(),
        "donate_style": window.donate_button.styleSheet(),
    }}
    window.close()
except Exception:
    result = {{
        "ok": False,
        "traceback": traceback.format_exc(),
    }}
""".format(repo_path=str(REPO_ROOT).replace("\\", "\\\\"))

    ui_result = run_broker(
        "app-command",
        "run",
        "--app",
        "maya",
        "--command",
        "exec_python",
        "--ensure-bridge",
        "--allow-foreground-bootstrap",
        "--args-json",
        json.dumps({"code": code}),
    )
    if not ui_result.get("ok"):
        raise AssertionError(json.dumps(ui_result, indent=2))

    result = (ui_result.get("data") or {}).get("result") or {}
    if not result.get("ok"):
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("window_title") != "Maya Onion Skin":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("display_mode_count") != 2:
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("display_mode_items") != ["3D Ghost", "Fast Silhouette (Live + Refine)"]:
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("frame_step_min") != 1 or result.get("frame_step_max", 0) < 2:
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("add_button_text") != "Add Selected":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "followamir.com" not in (result.get("brand_text") or ""):
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "AMIR_PAYPAL_DONATE_URL" not in (result.get("donate_tooltip") or ""):
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "#FFC439" not in (result.get("donate_style") or ""):
        raise AssertionError(json.dumps(ui_result, indent=2))

    print("MAYA_ONION_SKIN_LIVE_UI_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
