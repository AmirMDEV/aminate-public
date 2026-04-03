from __future__ import annotations

import json
import pathlib
import tempfile
import time
import urllib.request

import win32clipboard
from pywinauto import Desktop
from pywinauto.keyboard import send_keys


REPO_ROOT = pathlib.Path(__file__).resolve().parent
BRIDGE_PORT = 62225


def _ping_bridge() -> dict | None:
    try:
        with urllib.request.urlopen("http://127.0.0.1:{0}/ping".format(BRIDGE_PORT), timeout=0.5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def _set_clipboard(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardText(text)
    finally:
        win32clipboard.CloseClipboard()


def _find_maya_window():
    desktop = Desktop(backend="uia")
    for candidate in desktop.windows():
        title = candidate.window_text() or ""
        if "Autodesk MAYA 2026" in title or title == "Maya":
            return candidate
    return None


def _small_command_line_field(window):
    candidates = []
    for child in window.descendants(control_type="Edit"):
        if (child.element_info.class_name or "") != "TcommandLineField":
            continue
        rect = child.rectangle()
        candidates.append((rect.right - rect.left, child))
    if len(candidates) < 2:
        raise RuntimeError("Expected two Maya command-line fields, found {0}.".format(len(candidates)))
    return sorted(candidates, key=lambda item: item[0])[0][1]


def _write_bootstrap_script() -> pathlib.Path:
    bootstrap_code = r"""
import json
import threading
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer

import maya.cmds as cmds
import maya.mel as mel
import maya.utils

STATE_KEY = "_codex_desktop_broker_http_bridge"
HOST = "127.0.0.1"
PORT = 62225


def _bridge_state():
    state = globals().get(STATE_KEY)
    if state is None:
        state = {}
        globals()[STATE_KEY] = state
    return state


def _capture_status():
    return {
        "scene_name": cmds.file(query=True, sceneName=True) or "",
        "current_time": cmds.currentTime(query=True),
        "selection": cmds.ls(selection=True, long=True) or [],
        "maya_version": cmds.about(version=True),
    }


def _run_action(payload):
    action = payload.get("action")
    args = payload.get("args") or {}
    if action == "exec_python":
        namespace = {
            "__name__": "__codex_desktop_broker_exec__",
            "cmds": cmds,
            "mel": mel,
        }
        exec(args.get("code", ""), namespace, namespace)
        return namespace.get("result")
    if action == "exec_mel":
        return mel.eval(args.get("code", ""))
    if action == "query_selection":
        return cmds.ls(selection=True, long=True) or []
    if action == "open_scene":
        path = args["path"]
        force = bool(args.get("force", True))
        cmds.file(path, open=True, force=force)
        return cmds.file(query=True, sceneName=True) or ""
    if action == "run_tool_entrypoint":
        import importlib
        import sys

        module_path = args.get("module_path")
        module_name = args["module"]
        entrypoint = args.get("entrypoint", "launch")
        call_args = args.get("call_args") or []
        call_kwargs = args.get("call_kwargs") or {}
        if module_path and module_path not in sys.path:
            sys.path.insert(0, module_path)
        module = importlib.import_module(module_name)
        module = importlib.reload(module)
        function = getattr(module, entrypoint)
        value = function(*call_args, **call_kwargs)
        return {"repr": repr(value)}
    if action == "capture_status":
        return _capture_status()
    raise ValueError("Unsupported action: {0}".format(action))


class Handler(BaseHTTPRequestHandler):
    def _send(self, status_code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return

    def do_GET(self):
        try:
            if self.path == "/ping":
                result = maya.utils.executeInMainThreadWithResult(_capture_status)
                self._send(200, {"ok": True, "result": result})
                return
            self._send(404, {"ok": False, "error": "not-found"})
        except Exception:
            self._send(500, {"ok": False, "error": traceback.format_exc()})

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw.decode("utf-8"))

            def _run():
                return _run_action(payload)

            result = maya.utils.executeInMainThreadWithResult(_run)
            self._send(200, {"ok": True, "result": result})
        except Exception:
            self._send(500, {"ok": False, "error": traceback.format_exc()})


def _ensure_server():
    state = _bridge_state()
    server = state.get("server")
    thread = state.get("thread")
    if server and thread and thread.is_alive():
        try:
            server.shutdown()
            server.server_close()
        except Exception:
            pass
    server = HTTPServer((HOST, PORT), Handler)
    thread = threading.Thread(target=server.serve_forever, name="CodexDesktopBrokerBridge", daemon=True)
    thread.start()
    state["server"] = server
    state["thread"] = thread
    return "started"


print("CODEX_DESKTOP_BROKER_BOOTSTRAP", _ensure_server())
""".strip()
    bootstrap_path = pathlib.Path(tempfile.gettempdir()) / "codex_maya_bridge_bootstrap.py"
    bootstrap_path.write_text(bootstrap_code, encoding="utf-8")
    return bootstrap_path


def main() -> int:
    payload = _ping_bridge()
    if payload:
        print("MAYA_LIVE_BRIDGE_BOOTSTRAP: ALREADY_RUNNING")
        return 0

    window = _find_maya_window()
    if window is None:
        raise RuntimeError("No live Maya window was found.")
    try:
        window.restore()
    except Exception:
        pass
    window.set_focus()

    bootstrap_path = _write_bootstrap_script()
    mel = 'python("exec(compile(open(r\\\"{0}\\\").read(), r\\\"{0}\\\", \\\"exec\\\"))");'.format(
        str(bootstrap_path).replace("\\", "/")
    )

    input_field = _small_command_line_field(window)
    _set_clipboard(mel)
    input_field.click_input()
    time.sleep(0.2)
    send_keys("^a{BACKSPACE}")
    send_keys("^v")
    send_keys("{ENTER}")

    deadline = time.time() + 10.0
    while time.time() < deadline:
        payload = _ping_bridge()
        if payload:
            print("MAYA_LIVE_BRIDGE_BOOTSTRAP: PASS")
            return 0
        time.sleep(0.5)
    raise RuntimeError("The Maya bridge did not come online after command-line bootstrap.")


if __name__ == "__main__":
    raise SystemExit(main())
