from __future__ import absolute_import, division, print_function

import os
import sys
import tempfile
import traceback

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

import maya_tutorial_authoring  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    cmds.file(new=True, force=True)
    cmds.currentUnit(time="film")
    cmds.playbackOptions(minTime=1, maxTime=24, animationStartTime=1, animationEndTime=24)

    ball = cmds.createNode("transform", name="tutorialBall_CTRL")
    arm = cmds.createNode("transform", name="tutorialArm_CTRL")
    world_target = cmds.createNode("transform", name="tutorialWorldTarget_CTRL")
    pose_geo = cmds.polyCube(name="tutorialPose_GEO", width=2.0, height=2.0, depth=2.0)[0]
    cmds.xform(ball, worldSpace=True, translation=(0.0, 1.0, 0.0))
    cmds.xform(arm, worldSpace=True, translation=(4.0, 2.0, 0.0))
    cmds.xform(world_target, worldSpace=True, translation=(10.0, 2.0, 0.0))
    cmds.xform(pose_geo, worldSpace=True, translation=(0.0, 0.0, 4.0))

    controller = maya_tutorial_authoring.MayaTutorialAuthoringController()
    lesson = controller.create_lesson("Parent Constraint Tutorial")

    success, message = controller.begin_recording_step()
    _assert(success, message)
    cmds.currentTime(8, edit=True)
    success, message, frame_step = controller.finish_recorded_step(
        lesson["id"],
        "Go To Pickup Frame",
        "Go to frame 8.",
        "Start the pickup on frame 8.",
    )
    _assert(success, message)
    _assert(frame_step["kind"] == "frame_change", "The first recorded step should be a frame-change step")

    cmds.currentTime(8, edit=True)
    cmds.select([ball], replace=True)
    success, message = controller.begin_recording_step()
    _assert(success, message)
    cmds.select([ball, arm], replace=True)
    success, message, selection_step = controller.finish_recorded_step(
        lesson["id"],
        "Pick Ball And Arm",
        "Pick the ball and the arm.",
        "This is the selection the student needs for the constraint.",
    )
    _assert(success, message)
    _assert(selection_step["kind"] == "selection_change", "The second recorded step should be a selection-change step")

    success, message, ui_step = controller.add_ui_callout_step(
        lesson["id"],
        "Look At The Timeline",
        "This is the Maya timeline.",
        "Use the time slider to show where students should scrub.",
        target={"type": "timeline_slider", "label": "Timeline Slider"},
    )
    _assert(success, message)
    _assert(ui_step["kind"] == "ui_callout", "The UI step should be stored as a UI callout step")

    cmds.currentTime(12, edit=True)
    cmds.select([ball, arm], replace=True)
    success, message = controller.begin_recording_step()
    _assert(success, message)
    constraint_name = cmds.parentConstraint(arm, ball, maintainOffset=True, name="tutorialBall_parentConstraint")[0]
    success, message, constraint_step = controller.finish_recorded_step(
        lesson["id"],
        "Create The Parent Constraint",
        "Make a parent constraint from the arm to the ball.",
        "This is the attach moment.",
    )
    _assert(success, message)
    _assert(constraint_step["kind"] == "constraint_create", "The constraint step should be recognized as a constraint-create step")
    _assert(cmds.objExists(constraint_name), "The constraint should exist after recording")

    success, message = controller.restore_step(constraint_step, "pre")
    _assert(success, message)
    _assert(not cmds.objExists(constraint_name), "Back should delete the parent constraint")
    _assert(int(round(float(cmds.currentTime(query=True)))) == 12, "Back should restore the recorded pre-step frame")
    _assert(cmds.ls(selection=True, long=True) == [_node for _node in cmds.ls([ball, arm], long=True)], "Back should restore the pre-step selection")

    success, message = controller.restore_step(constraint_step, "post")
    _assert(success, message)
    recreated_constraints = cmds.ls("tutorialBall_parentConstraint*", type="parentConstraint") or []
    _assert(recreated_constraints, "Next should recreate the parent constraint")

    success, message = controller.validate_step(frame_step)
    _assert(not success, "The current frame should no longer match the frame step after the later edits")
    cmds.currentTime(8, edit=True)
    success, message = controller.validate_step(frame_step)
    _assert(success, "The frame step should validate when the scene is on frame 8")

    cmds.autoKeyframe(state=False)
    auto_key_baseline = maya_tutorial_authoring._recording_scene_snapshot(focused_nodes=[ball], include_full_supported=True)
    cmds.autoKeyframe(state=True)
    auto_key_current = maya_tutorial_authoring._recording_scene_snapshot(focused_nodes=[ball], include_full_supported=True)
    success, message, auto_key_step = controller.record_snapshot_step(
        lesson["id"],
        auto_key_baseline,
        auto_key_current,
        target={"type": "control_name", "label": "Auto Key", "control_name": "autoKeyButton"},
    )
    _assert(success, message)
    _assert(auto_key_step["kind"] == "auto_key_toggle", "The auto key change should be recognized as an auto-key toggle step")
    _assert((auto_key_step.get("target") or {}).get("label") == "Auto Key", "The auto-key step should preserve its UI target label")
    success, message = controller.restore_step(auto_key_step, "pre")
    _assert(success, message)
    _assert(not cmds.autoKeyframe(query=True, state=True), "Back should restore the pre-step auto-key state")
    success, message = controller.restore_step(auto_key_step, "post")
    _assert(success, message)
    _assert(cmds.autoKeyframe(query=True, state=True), "Next should restore the post-step auto-key state")

    cmds.currentTime(10, edit=True)
    cmds.select([ball], replace=True)
    keyframe_baseline = maya_tutorial_authoring._recording_scene_snapshot(focused_nodes=[ball], include_full_supported=True)
    cmds.setAttr(ball + ".translateY", 3.5)
    cmds.setKeyframe(ball, attribute="translateY", time=10, value=3.5)
    keyframe_current = maya_tutorial_authoring._recording_scene_snapshot(focused_nodes=[ball], include_full_supported=True)
    success, message, keyframe_step = controller.record_snapshot_step(
        lesson["id"],
        keyframe_baseline,
        keyframe_current,
        target={"type": "timeline_slider", "label": "Timeline Slider"},
    )
    _assert(success, message)
    _assert(keyframe_step["kind"] == "keyframe_change", "The keyed transform change should be recognized as a keyframe-change step")
    _assert((keyframe_step.get("target") or {}).get("label") == "Timeline Slider", "The keyframe step should preserve its UI target label")
    success, message = controller.restore_step(keyframe_step, "pre")
    _assert(success, message)
    previous_keys = cmds.keyframe(ball, attribute="translateY", query=True, time=(10, 10), valueChange=True) or []
    _assert(not previous_keys, "Back should remove the recorded keyframe from frame 10")
    success, message = controller.restore_step(keyframe_step, "post")
    _assert(success, message)
    restored_keys = cmds.keyframe(ball, attribute="translateY", query=True, time=(10, 10), valueChange=True) or []
    _assert(restored_keys and abs(float(restored_keys[0]) - 3.5) <= 1.0e-4, "Next should restore the recorded keyframe value")

    cmds.currentTime(14, edit=True)
    cmds.setAttr(pose_geo + ".translateY", 1.25)
    success, message, before_snapshot = controller.create_pose_compare_snapshot(
        [pose_geo],
        "Original Pose",
        frame_value=14,
        offset_distance=8.0,
        style_key=maya_tutorial_authoring.POSE_COMPARE_BEFORE,
    )
    _assert(success, message)
    before_group = before_snapshot["group_name"]
    _assert(cmds.objExists(before_group), "The before ghost should exist in the scene")
    _assert(int(cmds.getAttr(before_group + ".visibility", time=13)) == 0, "The before ghost should be hidden before its frame")
    _assert(int(cmds.getAttr(before_group + ".visibility", time=14)) == 1, "The before ghost should show on its frame")
    _assert(int(cmds.getAttr(before_group + ".visibility", time=15)) == 0, "The before ghost should hide after its frame")

    cmds.currentTime(16, edit=True)
    cmds.setAttr(pose_geo + ".translateY", 2.0)
    success, message = controller.begin_pose_compare_capture(
        [pose_geo],
        "Corrected Pose",
        frame_value=16,
        offset_distance=8.0,
        style_key=maya_tutorial_authoring.POSE_COMPARE_AFTER,
    )
    _assert(success, message)
    cmds.setAttr(pose_geo + ".translateY", 6.0)
    success, message, after_snapshot = controller.finish_pose_compare_capture(
        label_text="Corrected Pose",
        frame_value=16,
        offset_distance=8.0,
        style_key=maya_tutorial_authoring.POSE_COMPARE_AFTER,
    )
    _assert(success, message)
    restored_value = cmds.getAttr(pose_geo + ".translateY")
    _assert(abs(float(restored_value) - 2.0) <= 1.0e-4, "Finish Corrected Snapshot should restore the live pose")
    after_group = after_snapshot["group_name"]
    _assert(cmds.objExists(after_group), "The corrected ghost should exist in the scene")
    _assert(int(cmds.getAttr(after_group + ".visibility", time=15)) == 0, "The corrected ghost should be hidden before its frame")
    _assert(int(cmds.getAttr(after_group + ".visibility", time=16)) == 1, "The corrected ghost should show on its frame")
    _assert(int(cmds.getAttr(after_group + ".visibility", time=17)) == 0, "The corrected ghost should hide after its frame")

    temp_dir = tempfile.mkdtemp(prefix="maya_tutorial_authoring_")
    scene_path = os.path.join(temp_dir, "tutorial_authoring_test.ma")
    cmds.file(rename=scene_path)
    cmds.file(save=True, type="mayaAscii", force=True)
    cmds.file(scene_path, open=True, force=True, prompt=False)

    reloaded_controller = maya_tutorial_authoring.MayaTutorialAuthoringController()
    reloaded_lessons = reloaded_controller.lessons()
    _assert(len(reloaded_lessons) == 1, "One tutorial lesson should persist in the saved scene")
    reloaded_lesson = reloaded_lessons[0]
    step_kinds = [step["kind"] for step in reloaded_lesson.get("steps") or []]
    _assert(
        step_kinds == ["frame_change", "selection_change", "ui_callout", "constraint_create", "auto_key_toggle", "keyframe_change"],
        "The saved lesson should preserve the authored step order and kinds",
    )
    pose_snapshots = reloaded_controller.pose_compare_snapshots()
    _assert(len(pose_snapshots) == 2, "Two pose compare ghosts should persist in the saved scene")

    print("MAYA_TUTORIAL_AUTHORING_SMOKE_TEST: PASS")


if __name__ == "__main__":
    exit_code = 0
    try:
        run()
    except Exception:
        exit_code = 1
        traceback.print_exc()
        print("MAYA_TUTORIAL_AUTHORING_SMOKE_TEST: FAIL")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        os._exit(exit_code)
