from __future__ import absolute_import, division, print_function

import json
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

import maya_timeline_notes  # noqa: E402


def _assert(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    cmds.file(new=True, force=True)
    cmds.playbackOptions(minTime=1, maxTime=24)

    controller = maya_timeline_notes.MayaTimelineNotesController()
    success, message = controller.create_note(
        "Shot <1> & Plan",
        5,
        12,
        (0.9, 0.3, 0.2),
        0.65,
        "Line 1\nLine <2>",
    )
    _assert(success, "Timeline Notes create failed: {0}".format(message))
    notes = controller.notes()
    _assert(len(notes) == 1, "Exactly one timeline note should exist after create")
    note = notes[0]
    _assert(note["title"] == "Shot <1> & Plan", "Timeline note title should round-trip")
    _assert(note["start_frame"] == 5 and note["end_frame"] == 12, "Timeline note range should match the created range")

    success, message = controller.update_note(
        note["node"],
        "Updated <Note> & Mark",
        6,
        14,
        (0.2, 0.6, 0.8),
        0.8,
        "Updated line 1\nUpdated <line 2>",
    )
    _assert(success, "Timeline Notes update failed: {0}".format(message))
    updated_note = controller.notes()[0]
    _assert(updated_note["title"] == "Updated <Note> & Mark", "Timeline note title should update cleanly")
    _assert(updated_note["start_frame"] == 6 and updated_note["end_frame"] == 14, "Timeline note range should update cleanly")
    _assert(updated_note["text"] == "Updated line 1\nUpdated <line 2>", "Timeline note text should update cleanly")
    _assert(len(controller.notes_at_frame(10)) == 1, "Timeline note lookup should find the note at an in-range frame")
    _assert(len(controller.notes_at_frame(2)) == 0, "Timeline note lookup should skip frames outside every note range")

    tooltip_html = controller.tooltip_html(updated_note)
    _assert("&lt;Note&gt;" in tooltip_html and "&amp;" in tooltip_html, "Tooltip HTML should escape the note title")
    _assert("Updated line 1<br>Updated &lt;line 2&gt;" in tooltip_html, "Tooltip HTML should escape and preserve note line breaks")
    _assert(
        tooltip_html.index("Updated line 1<br>Updated &lt;line 2&gt;") < tooltip_html.index("Title: Updated &lt;Note&gt; &amp; Mark"),
        "Tooltip HTML should show the full note before the short title",
    )

    temp_dir = tempfile.mkdtemp(prefix="maya_timeline_notes_")
    export_path = os.path.join(temp_dir, "timeline_notes.json")
    success, message = controller.export_notes(export_path)
    _assert(success, "Timeline Notes export failed: {0}".format(message))
    with open(export_path, "r") as handle:
        payload = json.load(handle)
    _assert(len(payload.get("notes") or []) == 1, "Export should contain one note")

    success, message = controller.delete_note(note["node"])
    _assert(success, "Timeline Notes delete failed: {0}".format(message))
    _assert(not controller.notes(), "All notes should be gone after delete")

    success, message = controller.import_notes(export_path)
    _assert(success, "Timeline Notes import failed: {0}".format(message))
    imported_notes = controller.notes()
    _assert(len(imported_notes) == 1, "Import should restore one note")
    _assert(imported_notes[0]["title"] == "Updated <Note> & Mark", "Imported note title should match the exported note")

    print("MAYA_TIMELINE_NOTES_SMOKE_TEST: PASS")


if __name__ == "__main__":
    exit_code = 0
    try:
        run()
    except Exception:
        exit_code = 1
        traceback.print_exc()
        print("MAYA_TIMELINE_NOTES_SMOKE_TEST: FAIL")
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        try:
            maya.standalone.uninitialize()
        except Exception:
            pass
        os._exit(exit_code)
