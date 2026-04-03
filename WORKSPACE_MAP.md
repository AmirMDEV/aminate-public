# Maya Animation Tools Workspace Map

## Purpose

This folder contains standalone Maya tooling aimed at animator-facing workflows that should be easy to install as shelf scripts and easy to maintain across Maya 2022-2026.

## Active Files

- `maya_shelf_utils.py`: shared shelf installer and shelf-name normalization helpers for Maya tools in this folder
- `maya_anim_workflow_tools.py`: canonical tabbed entrypoint for dynamic parenting, hand/foot holds, dynamic pivot, universal IK/FK, onion skin, rotation cleanup, skinning cleanup, rig-scale export, video reference, and timeline-note workflows
- `maya_dynamic_parent_pivot.py`: combined implementation behind the tabbed Anim Workflow UI, including the embedded Hand / Foot Hold, Onion Skin, Rotation Doctor, Skinning Cleanup, Rig Scale, Video Reference, and Timeline Notes tabs
- `maya_dynamic_parenting_tool.py`: scene-backed dynamic parenting panel for hand/gun/world switching, stored parent choices, and weighted blends inside the combined workflow tool
- `maya_universal_ikfk_switcher.py`: compatibility launcher that opens the IK/FK tab directly
- `maya_live_bridge_bootstrap.py`: live Maya bridge bootstrap helper that uses the command-line field after a fresh Maya reopen
- `maya_contact_hold.py`: keeps picked hand or foot controls planted in place across a chosen frame range
- `maya_onion_skin.py`: stepped onion-skin preview tool for multi-part rigs, with both 3D ghost and camera-based fast silhouette modes
- `maya_rotation_doctor.py`: preview-first rotation diagnosis and repair tool for animated controls
- `maya_skinning_cleanup.py`: non-destructive skinned-mesh scale cleanup with exact vertex-index skin restore
- `maya_rig_scale_export.py`: non-destructive export-copy builder for resizing skinned character rigs without exporting joint scale
- `maya_video_reference_tool.py`: tracing-card and camera-overlay reference helper with playback-range video proxying, live start-frame retiming, optional audio import, attach/follow placement, and a built-in note-line fallback when Blue Pencil is unavailable
- `maya_timeline_notes.py`: colored timeline note ranges built on Maya bookmarks, with export/import and hover text
- `maya_tutorial_authoring.py`: scene-bound tutorial authoring with separate Guided Practice, Student Demo, and Pose Compare modes, typed checkpoints, UI callouts, and best-effort highlighting for stable Maya controls
- `README.md`: install, usage, and compatibility notes
- `maya_anim_workflow_tools_smoke_test.py`: mayapy smoke for the combined Anim Workflow tool
- `maya_anim_workflow_tools_live_ui_smoke.py`: broker-driven live Maya UI smoke for the tabbed Anim Workflow window
- `maya_anim_workflow_tools_shelf_install_verify.py`: broker-driven live Maya shelf install verification for the combined Anim Workflow tool on `Amir's Scripts`
- `maya_live_scene_functional_verify.py`: broker-driven live Maya functional verifier that uses the current open scene plus temporary cleanup-only test nodes
- `maya_rotation_doctor_smoke_test.py`: mayapy smoke for rotation diagnosis and repair recipes
- `maya_rotation_doctor_live_ui_smoke.py`: broker-driven live Maya UI smoke for the Rotation Doctor window
- `maya_rotation_doctor_shelf_install_verify.py`: broker-driven live Maya shelf install verification for Rotation Doctor on `Amir's Scripts`
- `maya_skinning_cleanup_smoke_test.py`: mayapy smoke for skinned-mesh cleanup and verification
- `maya_skinning_cleanup_live_ui_smoke.py`: broker-driven live Maya UI smoke for the Skinning Cleanup window
- `maya_contact_hold_smoke_test.py`: mayapy smoke for planted hand/foot holds across a frame range
- `maya_rig_scale_export_smoke_test.py`: mayapy smoke for rig-scale export-copy creation and grouped-rig warnings
- `maya_rig_scale_export_live_ui_smoke.py`: live Maya UI smoke for the Rig Scale controls when a healthy Maya GUI session is available
- `maya_video_reference_tool_smoke_test.py`: mayapy smoke for tracing-card placement, follow-mode proxy import, frame offset, and audio offset
- `maya_timeline_notes_smoke_test.py`: mayapy smoke for timeline note create/export/delete/import and escaped hover text
- `maya_tutorial_authoring_smoke_test.py`: mayapy smoke for recorded tutorial steps, guided/demo checkpoint restore, pose-compare ghost persistence, and scene persistence
- `maya_tutorial_authoring_live_ui_smoke.py`: broker-driven live Maya UI smoke for the tutorial author/guided/demo/pose-compare window, dockable launch path, and native-target highlighting
- `maya_tutorial_authoring_shelf_install_verify.py`: broker-driven live Maya shelf install verification for the tutorial authoring tool on `Amir's Scripts`
- `maya_onion_skin_shelf_install_verify.py`: broker-driven live Maya shelf install verification for Onion Skin on `Amir's Scripts`
- `maya_onion_skin_gui_perf_smoke.py`: GUI perf/coalescing smoke for heavy scrub bursts
- `maya_onion_skin_real_scene_benchmark.py`: real-scene perf benchmark for production Maya files

## Search Rule

Treat this folder as Maya-specific tooling. If the task is about browser automation, userscripts, NAS deployment, or OpenClaw infrastructure, route back to the appropriate sibling project instead of scanning here.

When the task is about dynamic parenting, hand/foot contact holds, dynamic pivot, IK/FK switching, onion skinning, rotation cleanup, skinning cleanup, rig-scale export, video reference, timeline notes, scene-bound tutorial authoring, guided Maya lessons, or pose-compare ghost snapshots, start with the dedicated module for that workflow first and treat `maya_anim_workflow_tools.py` as the combined-tab entrypoint only when the task explicitly needs the global tabbed window.

For the current house-standard validation anchor, start with `maya_anim_workflow_tools.py`, then use `maya_anim_workflow_tools_live_ui_smoke.py` and `maya_anim_workflow_tools_shelf_install_verify.py` to prove the docked UI and shelf-install path in live Maya.
