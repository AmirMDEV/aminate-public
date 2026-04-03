from __future__ import absolute_import, division, print_function

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import traceback
import wave

import maya.standalone


try:
    maya.standalone.initialize(name="python")
except RuntimeError as exc:
    if "inside of Maya" not in str(exc):
        raise

import maya.cmds as cmds  # noqa: E402


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if THIS_DIR not in sys.path:
    sys.path.insert(0, THIS_DIR)

import maya_video_reference_tool  # noqa: E402


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO9n5c8AAAAASUVORK5CYII="
)


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def _write_test_png(path):
    with open(path, "wb") as handle:
        handle.write(PNG_BYTES)


def _write_test_wav(path):
    with wave.open(path, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(44100)
        handle.writeframes(b"\x00\x00" * 4410)


def _write_test_mp4(image_path, output_path):
    ffmpeg_path = shutil.which("ffmpeg")
    _assert(ffmpeg_path, "ffmpeg is required for the video proxy smoke test on this machine")
    kwargs = {
        "check": False,
        "capture_output": True,
        "text": True,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    completed = subprocess.run(
        [
            ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-loop",
            "1",
            "-i",
            image_path,
            "-t",
            "1",
            "-vf",
            "scale=2:2,fps=24",
            "-pix_fmt",
            "yuv420p",
            output_path,
        ],
        **kwargs
    )
    _assert(completed.returncode == 0, completed.stderr or completed.stdout or "ffmpeg could not create the test mp4")


def run():
    cmds.file(new=True, force=True)
    camera_transform, _camera_shape = cmds.camera(name="videoRefTest_cam")
    target_transform, _target_shape = cmds.polyCube(name="videoRefTarget")
    cmds.xform(target_transform, worldSpace=True, translation=(0.0, 4.0, 0.0))
    cmds.playbackOptions(edit=True, minTime=1, maxTime=24)

    temp_dir = tempfile.mkdtemp(prefix="maya_video_reference_")
    png_path = os.path.join(temp_dir, "reference.png")
    wav_path = os.path.join(temp_dir, "reference.wav")
    mp4_path = os.path.join(temp_dir, "reference.mp4")
    _write_test_png(png_path)
    _write_test_wav(wav_path)
    _write_test_mp4(png_path, mp4_path)

    controller = maya_video_reference_tool.MayaVideoReferenceController()
    controller.camera_name = camera_transform
    controller.media_path = png_path
    controller.audio_path = wav_path
    controller.import_audio = True
    controller.start_frame = 12
    controller.target_node = target_transform
    controller.placement_mode = "tracing_card"

    success, message = controller.import_reference()
    _assert(success, "Video Reference import failed: {0}".format(message))
    _assert("Audio was lined up too." in message, message)
    _assert(controller.last_image_plane and cmds.objExists(controller.last_image_plane), "Image plane shape should exist")
    _assert(controller.last_sound and cmds.objExists(controller.last_sound), "Sound node should exist")
    _assert(controller.last_transform and cmds.objExists(controller.last_transform), "Tracing card transform should exist")

    image_plane_shape = controller.last_image_plane
    image_plane_transform = (cmds.listRelatives(image_plane_shape, parent=True, fullPath=True) or [""])[0]
    _assert(image_plane_transform, "Image plane transform should exist")
    _assert(image_plane_transform.startswith("|amirVideoReference_GRP|"), "Tracing card should be grouped under the shared video reference root")
    _assert(cmds.getAttr(image_plane_shape + ".useFrameExtension") == 1, "Image plane should use frame extension")
    _assert(int(round(cmds.getAttr(image_plane_shape + ".frameOffset"))) == -11, "Frame offset should store the chosen start-frame offset")

    cmds.currentTime(12, edit=True)
    _assert(int(round(cmds.getAttr(image_plane_shape + ".frameExtension"))) == 12, "Image plane should stay driven by Maya time")
    cmds.currentTime(15, edit=True)
    _assert(int(round(cmds.getAttr(image_plane_shape + ".frameExtension"))) == 15, "Image plane frameExtension should keep following Maya time")
    _assert(int(round(cmds.getAttr(controller.last_sound + ".offset"))) == 12, "Sound offset should match the chosen start frame")

    controller.start_frame = 20
    success, message = controller.update_current_reference_timing()
    _assert(success, "Start-frame retime should work on the current tracing card: {0}".format(message))
    _assert(int(round(cmds.getAttr(image_plane_shape + ".frameOffset"))) == -19, "Updating the start frame should retime the tracing card")
    _assert(int(round(cmds.getAttr(controller.last_sound + ".offset"))) == 20, "Updating the start frame should also retime the sound")

    success, annotation_surface = controller.prepare_annotation_surface()
    _assert(success, "Annotation surface should be created for the current tracing card")
    _assert(cmds.objExists(annotation_surface), "Annotation surface should exist")

    note_curve = cmds.curve(name="videoNoteCurve", degree=1, point=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)])
    cmds.select(note_curve, replace=True)
    success, message = controller.apply_hold_to_selected_annotations(8, 10)
    _assert(success, "Applying note hold should succeed: {0}".format(message))
    visibility_keys = cmds.keyframe(note_curve, attribute="visibility", query=True, timeChange=True) or []
    visibility_key_set = sorted(set(int(round(value)) for value in visibility_keys))
    _assert(visibility_key_set == [7, 8, 10, 11], "Note hold should key the visibility range cleanly")
    success, message = controller.clear_annotation_surface()
    _assert(success, "Clearing the annotation surface should succeed: {0}".format(message))
    _assert(not cmds.objExists(annotation_surface), "Annotation surface should be deleted when cleared")

    movie_controller = maya_video_reference_tool.MayaVideoReferenceController()
    movie_controller.camera_name = camera_transform
    movie_controller.media_path = mp4_path
    movie_controller.import_audio = False
    movie_controller.start_frame = 5
    movie_controller.target_node = target_transform
    movie_controller.placement_mode = "follow_target"
    movie_controller.follow_x = True
    movie_controller.follow_y = True
    movie_controller.follow_z = False

    success, message = movie_controller.import_reference()
    _assert(success, "Movie proxy import failed: {0}".format(message))
    _assert("Maya-friendly image sequence" in message, message)
    _assert(movie_controller.last_media_info.get("is_proxy") is True, "Movie files should be proxied into an image sequence")
    _assert(os.path.exists(movie_controller.last_media_info.get("resolved_media_path", "")), "Proxy first frame should exist")
    _assert(int(movie_controller.last_media_info.get("frame_count", 0)) == 20, "Proxy frame count should match the current playback range from the chosen start frame")
    _assert(movie_controller.last_follow_group and cmds.objExists(movie_controller.last_follow_group), "Follow mode should create a follow group")
    follow_constraints = cmds.listRelatives(movie_controller.last_follow_group, type="pointConstraint") or []
    _assert(follow_constraints or cmds.listConnections(movie_controller.last_follow_group, type="pointConstraint"), "Follow mode should keep the tracing card tied to the target")

    print("MAYA_VIDEO_REFERENCE_TOOL_SMOKE_TEST: PASS")


if __name__ == "__main__":
    exit_code = 0
    try:
        run()
    except Exception:
        exit_code = 1
        traceback.print_exc()
        print("MAYA_VIDEO_REFERENCE_TOOL_SMOKE_TEST: FAIL")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        os._exit(exit_code)
