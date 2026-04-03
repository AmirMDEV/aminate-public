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
    import maya_rig_scale_export
    importlib.reload(maya_rig_scale_export)
    window = maya_rig_scale_export.launch_maya_rig_scale_export()
    result = {{
        "ok": True,
        "window_title": window.windowTitle(),
        "use_character_text": window.use_character_button.text(),
        "use_skeleton_text": window.use_skeleton_button.text(),
        "analyze_text": window.analyze_button.text(),
        "create_text": window.create_button.text(),
        "select_text": window.select_button.text(),
        "delete_text": window.delete_button.text(),
        "character_placeholder": window.character_line.placeholderText(),
        "skeleton_placeholder": window.skeleton_line.placeholderText(),
        "suffix_value": window.suffix_line.text(),
        "report_read_only": window.report_text.isReadOnly(),
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
    if result.get("window_title") != "Maya Rig Scale":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("use_character_text") != "Use Selected Character":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("use_skeleton_text") != "Use Selected Skeleton":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("analyze_text") != "Check Setup":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("create_text") != "Make Export Copy":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("select_text") != "Select Export Copy":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("delete_text") != "Delete Export Copy":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "character root" not in (result.get("character_placeholder") or "").lower():
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "skeleton joint" not in (result.get("skeleton_placeholder") or "").lower():
        raise AssertionError(json.dumps(ui_result, indent=2))
    if result.get("suffix_value") != "_rigScaleExport":
        raise AssertionError(json.dumps(ui_result, indent=2))
    if not result.get("report_read_only"):
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "followamir.com" not in (result.get("brand_text") or ""):
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "AMIR_PAYPAL_DONATE_URL" not in (result.get("donate_tooltip") or ""):
        raise AssertionError(json.dumps(ui_result, indent=2))
    if "#FFC439" not in (result.get("donate_style") or ""):
        raise AssertionError(json.dumps(ui_result, indent=2))

    print("MAYA_RIG_SCALE_EXPORT_LIVE_UI_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
