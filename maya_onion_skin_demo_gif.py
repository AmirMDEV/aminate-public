from __future__ import annotations

import json
import pathlib
import textwrap
import time

from PIL import Image, ImageDraw, ImageFont, ImageOps

from maya_onion_skin_demo_capture import (
    SCREENSHOT_DIR,
    capture_tool_crop,
    capture_window,
    run_broker,
    run_exec_python,
    set_frame,
)


FRAME_SEQUENCE = [16, 20, 24, 28, 32, 36, 32, 28, 24, 20]
GIF_OUTPUT = SCREENSHOT_DIR / "maya_onion_skin_demo.gif"
FRAME_DURATION_MS = 180
FRAME_WIDTH = 1100
FRAME_HEIGHT = 620
VIEWPORT_BOX = (700, 500)
PANEL_BOX = (340, 500)


def _prepare_demo():
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
    ).format(repo_path=str(pathlib.Path(__file__).resolve().parent).replace("\\", "\\\\"))

    setup_result = run_exec_python(setup_code)
    payload = setup_result.get("result") or {}
    if not payload.get("ok"):
        raise RuntimeError(json.dumps(setup_result, indent=2))


def _render_frame(view_path: pathlib.Path, panel_path: pathlib.Path, frame_number: int) -> Image.Image:
    view = Image.open(str(view_path)).convert("RGB")
    panel = Image.open(str(panel_path)).convert("RGB")

    view = ImageOps.contain(view, VIEWPORT_BOX, Image.Resampling.LANCZOS)
    panel = ImageOps.contain(panel, PANEL_BOX, Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (FRAME_WIDTH, FRAME_HEIGHT), (36, 36, 39))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    draw.text((20, 16), "Maya Onion Skin demo  |  2 roots  |  Frame Step 2  |  Frame {0}".format(frame_number), fill=(240, 240, 240), font=font)
    draw.text((20, 34), "Adaptive scrub preview with live past/future ghost updates", fill=(190, 190, 190), font=font)

    canvas.paste(view, (20, 76))
    canvas.paste(panel, (FRAME_WIDTH - panel.width - 20, 76))
    return canvas


def build_demo_gif(output_path: pathlib.Path = GIF_OUTPUT) -> pathlib.Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    working_dir = output_path.parent / "_gif_frames"
    working_dir.mkdir(parents=True, exist_ok=True)

    _prepare_demo()
    time.sleep(1.25)

    rendered_frames = []
    for index, frame_number in enumerate(FRAME_SEQUENCE):
        set_frame(frame_number)
        time.sleep(0.3)

        view_path = working_dir / "view_{0:02d}.png".format(index)
        panel_path = working_dir / "panel_{0:02d}.png".format(index)
        capture_window(view_path)
        capture_tool_crop(None, panel_path)
        rendered_frames.append(_render_frame(view_path, panel_path, frame_number))

    palette_frames = [frame.convert("P", palette=Image.ADAPTIVE, colors=128) for frame in rendered_frames]
    durations = [FRAME_DURATION_MS] * len(palette_frames)
    durations[0] = 320
    durations[-1] = 420
    palette_frames[0].save(
        str(output_path),
        save_all=True,
        append_images=palette_frames[1:],
        duration=durations,
        loop=0,
        optimize=False,
        disposal=2,
    )

    for file_path in working_dir.glob("*.png"):
        try:
            file_path.unlink()
        except OSError:
            pass
    try:
        working_dir.rmdir()
    except OSError:
        pass
    return output_path


def main() -> int:
    output = build_demo_gif()
    print(
        json.dumps(
            {
                "gif": str(output),
                "frames": len(FRAME_SEQUENCE),
                "frame_sequence": FRAME_SEQUENCE,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
