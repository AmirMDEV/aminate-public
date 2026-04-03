# Maya Animation Tools

This folder contains standalone Maya Python tools that stay lightweight, shelf-installable, and version-tolerant across Maya 2022-2026.

Shared shelf install logic for this repo lives in `maya_shelf_utils.py`, so new tools can reuse the same duplicate-safe `Amir's Scripts` install flow.

## Tools

### Maya Onion Skin

`maya_onion_skin.py` builds a lightweight onion-skin preview for one or more selected character roots or control rigs.

Key features:

- Multi-root onion skin previews for visible mesh shapes
- Stepped sampling and adaptive scrub updates
- Amir footer with `followamir.com` and the standard PayPal-yellow `Donate` button

Entry points:

```python
import maya_onion_skin
maya_onion_skin.launch_maya_onion_skin()
```

```python
import importlib
import maya_onion_skin
importlib.reload(maya_onion_skin)
maya_onion_skin.install_maya_onion_skin_shelf_button()
```

### Maya Rotation Doctor

`maya_rotation_doctor.py` analyzes selected animated controls, previews likely rotation problems, and offers safe repair recipes before changing anything.

Key features:

- Selected-controls-only rotation diagnosis
- Detection for Euler discontinuities, likely gimbal-prone poses, intentional long spins, and interpolation-risk cases
- Repair recipes for Euler cleanup, preserving long spins, synchronized Euler conversion, quaternion conversion, and a custom continuity pass
- Preview-first UI with the standard Amir footer and PayPal-yellow `Donate` button

Entry points:

```python
import maya_rotation_doctor
maya_rotation_doctor.launch_maya_rotation_doctor()
```

```python
import importlib
import maya_rotation_doctor
importlib.reload(maya_rotation_doctor)
maya_rotation_doctor.install_maya_rotation_doctor_shelf_button()
```

By default, the shelf installer targets `Amir's Scripts`, replaces any older Rotation Doctor shelf button with the same `docTag`, and saves the updated shelf file.

### Maya Skinning Cleanup

`maya_skinning_cleanup.py` makes a non-destructive clean copy of one selected skinned polygon mesh, bakes bad transform scale into the geometry, and restores the skin by exact vertex index.

Key features:

- Red/yellow/green checks before anything is replaced
- Exact skin-weight capture and restore through `maya.api.OpenMayaAnim`
- Preservation checks for topology, vertex order, shading assignments, UV sets, hard/soft edges, and normals
- Safe replace flow that leaves the original mesh behind as a hidden backup
- Standard Amir footer with the PayPal-yellow `Donate` button

Entry points:

```python
import maya_skinning_cleanup
maya_skinning_cleanup.launch_maya_skinning_cleanup()
```

### Maya Rig Scale Export

`maya_rig_scale_export.py` builds a clean export copy of a skinned character at a new size so the exported skeleton keeps joint scales at `1,1,1`.

Key features:

- Non-destructive export-copy workflow for one character root plus one top skeleton joint
- Exact skin-weight restore by vertex index on the copied meshes
- Rebuilt export skeleton with baked bone lengths instead of bad joint scale
- Clear warnings when parent-group transforms make the result less predictable
- Standard Amir footer with the PayPal-yellow `Donate` button

Entry points:

```python
import maya_rig_scale_export
maya_rig_scale_export.launch_maya_rig_scale_export()
```

### Maya Video Reference

`maya_video_reference_tool.py` turns a video into a Maya-friendly tracing card, lets you offset its start frame, can line up matching audio, and can still fall back to a full-screen camera overlay when you really want that.

Key features:

- Turns movie files into image-sequence proxies for the current playback range so Maya can scrub them reliably
- Default tracing-card placement behind a picked object instead of forcing a full-screen overlay
- Optional follow mode so the card can track a picked object on chosen translation axes
- Optional camera overlay mode for full-frame reference
- Start-frame offset for the reference, with live retiming for the current card when you change the field
- Optional audio import with the same offset
- Quick jump into Maya's native drawing tools when available, plus a built-in lightweight note-line fallback when Blue Pencil is missing
- Standard Amir footer with the PayPal-yellow `Donate` button

Entry points:

```python
import maya_video_reference_tool
maya_video_reference_tool.launch_maya_video_reference()
```

### Maya Timeline Notes

`maya_timeline_notes.py` adds colored note ranges to Maya's timeline using Maya's native bookmark system, with export/import and richer hover text.

Key features:

- Colored timeline ranges with title, opacity, and long-form note text
- Export and import to JSON so note sets can be reused
- Hover text that keeps line breaks and escapes note text safely
- Live `Notes At Current Frame` reader so you can scrub through note ranges and read the full note text in the UI
- Standard Amir footer with the PayPal-yellow `Donate` button

Entry points:

```python
import maya_timeline_notes
maya_timeline_notes.launch_maya_timeline_notes()
```

### Maya Tutorial Authoring

`maya_tutorial_authoring.py` records scene-bound teaching steps, stores them inside the Maya scene, and now ships four compact lanes: Author, Practice, Watch, and Compare.

Key features:

- Scene-embedded lessons stored on hidden metadata nodes so the tutorial travels with the `.ma` or `.mb` file
- Author mode now has both a manual one-step capture flow and an `Auto Record` flow that automatically splits supported Maya actions into steps
- Automatic recording currently captures supported frame changes, selection changes, auto-key toggles, keyed transform changes, node or constraint creation or deletion, and best-effort UI-target callouts
- Practice mode with `Prepare`, `Show Me`, `Check`, `Do It`, `Back`, `Next`, and `Reset`
- Watch mode with `Show Me`, `Check`, `Back`, `Next`, and `Reset`
- Pose Compare mode with frame-visible ghost snapshots that persist in the scene so students can scrub the file without installing the script
- Best-effort highlighting for stable Maya UI targets such as the time slider, shelf buttons, and top-level menu controls
- The main launcher now opens through Maya's dockable workspace-control path by default, so the tool behaves like a dockable Maya panel instead of a plain dialog and still keeps the compact `More` menu actions for `Dock Right` and `Float Window`
- A tighter tabbed author layout so tall content stays usable in narrow Maya panes
- Standard Amir footer with the PayPal-yellow `Donate` button

Entry points:

```python
import maya_tutorial_authoring
maya_tutorial_authoring.launch_maya_tutorial_authoring()
```

```python
import maya_tutorial_authoring
maya_tutorial_authoring.launch_maya_tutorial_guided_practice()
```

```python
import maya_tutorial_authoring
maya_tutorial_authoring.launch_maya_tutorial_player()
```

```python
import importlib
import maya_tutorial_authoring
importlib.reload(maya_tutorial_authoring)
maya_tutorial_authoring.install_maya_tutorial_authoring_shelf_button()
```

```python
import maya_tutorial_authoring
maya_tutorial_authoring.launch_maya_pose_compare()
```

### Maya Hand / Foot Hold

`maya_contact_hold.py` keeps a picked hand or foot control locked to the same world-space spot across a chosen frame range.

Key features:

- Good for planted feet, hands on props, and other contact moments during root motion
- Live editable hold setups instead of baking every frame
- Choose which world axis or axes should stay locked, such as `Z` for forward travel
- Reversible workflow: `Use Hold`, `Use Original Motion`, and `Delete Hold`
- `Add Matching Other Side` can pull in the other foot or hand automatically for common left/right control names
- Optional turn locking so the control can keep the same rotation as well as the same position
- Standard Amir footer with the PayPal-yellow `Donate` button

Entry points:

```python
import maya_contact_hold
maya_contact_hold.launch_maya_contact_hold()
```

### Maya Anim Workflow Tools

`maya_anim_workflow_tools.py` is the canonical combined entrypoint for the new tabbed workflow tool. It currently ships these tabs:

- `Quick Start`: in-tool workflow reminders and troubleshooting notes
- `Dynamic Parenting`: scene-backed prop and control parenting so one object can switch between hands, props, world, or blended parents without baking
- `Hand / Foot Hold`: live editable planted-contact helper that can lock chosen world axes over a chosen frame range, save many hold rows per control, then turn specific rows on, off, update them, rename them in the list, or delete them later without baking every frame
- `Dynamic Pivot`: temporary shared pivot authoring that lets you move the pivot anywhere before applying rotation
- `Universal IK/FK`: profile-driven FK/IK matching and switching with frame-1 plus current-frame keying, separate FK and IK controller fields, and a stronger first-pass auto-detect that now prefers real animator controls over nearby helper transforms, while still expecting user review
- `Onion Skin`: the full stepped multi-root mesh ghost preview tool, now available inside the global workflow window as its own tab, with both `3D Ghost` and camera-based `Fast Silhouette (Live + Refine)` preview modes
- `Rotation Doctor`: the rotation diagnosis and cleanup tool, now available inside the global workflow window as its own tab
- `Skinning Cleanup`: non-destructive bad-scale cleanup for one skinned mesh, with exact vertex-index weight restore and a safe replace step
- `Rig Scale`: non-destructive export-copy builder that bakes the chosen size into the copied skeleton and meshes for engine export
- `Video Reference`: tracing-card or camera-overlay reference import with live frame-offset retiming, optional audio, and lightweight note drawing fallback
- `Timeline Notes`: colored timeline ranges with export/import and hover text that now leads with the full note body instead of the short title

The combined window is now resizable, opens docked from the shelf by default, wraps each main tab in a scroll area so tall tools stay usable instead of clipping, starts with `Quick Start` as the first tab, lets you drag tabs into the order you prefer, and now adds a plain-English "What This Tab Helps With" explainer at the top of every tab.

Supporting modules:

- `maya_dynamic_parent_pivot.py`: full combined implementation and shelf command target
- `maya_universal_ikfk_switcher.py`: compatibility launcher that opens the `Universal IK/FK` tab directly
- `maya_live_bridge_bootstrap.py`: live Maya bridge bootstrap through the command-line field for broker-driven GUI tests after a fresh reopen

Entry points:

```python
import maya_anim_workflow_tools
maya_anim_workflow_tools.launch_maya_anim_workflow_tools()
```

```python
import maya_universal_ikfk_switcher
maya_universal_ikfk_switcher.launch_maya_universal_ikfk_switcher()
```

```python
import importlib
import maya_anim_workflow_tools
importlib.reload(maya_anim_workflow_tools)
maya_anim_workflow_tools.install_maya_anim_workflow_tools_shelf_button()
```

By default, the shelf installer targets `Amir's Scripts`, replaces the prior Anim Workflow button by stable `docTag`, and saves the updated shelf file.

## Target Versions

- Maya 2022-2026
- Python 3.7-safe syntax for Maya 2022
- `PySide2` and `PySide6` import support

## Install

1. Keep this folder on Maya's script path, or add it to `sys.path` before import.
2. Launch the tool you want directly, or install its shelf button into `Amir's Scripts`.

## Notes

- Maya Dynamic Parenting is now a scene-backed setup rather than a bake-and-clear helper. You add the moving object once, add any hand, gun, prop, or world choices it should follow, and those parent choices stay stored in the Maya scene.
- The simple Dynamic Parenting flow is: click `Add Picked Object`, click `Pick Parent From Selection`, then use `Parent To Picked Parent`, `Parent Fully To Picked Row`, `Parent To World`, or `Blend Using Shown Weights`.
- Dynamic Parenting keeps a visible `Saved Parent Switches` list in the tab, and clicking a saved row jumps you straight back to that switch frame later.
- Maya Onion Skin keeps the full user-chosen ghost count in both preview modes. `3D Ghost` is the true mesh mode, while `Fast Silhouette (Live + Refine)` is a camera-based silhouette mode that refreshes at a lower resolution while view motion is active, then sharpens after settle.
- On the current Amanda scene, the first working `Fast Silhouette` pass is correct and live-tested, but it is still best treated as an alternate view-driven mode rather than the guaranteed faster option on every mesh. The current heavy-mesh win is still more about mode choice and refresh behavior than a magic instant speed-up.
- Maya Rotation Doctor is intentionally preview-first. It does not auto-change rotate order in V1.
- Maya Skinning Cleanup currently targets one selected skinned polygon mesh at a time and blocks unsupported extra deformation history such as blendshape stacks.
- Maya Rig Scale Export is verified for common uniform grouped rigs. Rotated or non-uniform parent groups are warned up front because exact normals can differ after baking scale, so those cases should be checked carefully before Unreal export.
- Maya Hand / Foot Hold is now a live contact tool rather than a bake pass. You choose the contact range, choose which world axis or axes should stay locked, and the tool creates a reversible setup you can turn on or off later.
- Maya Hand / Foot Hold now keeps a real `Saved Holds In Scene` list. Each saved row remembers the control, frame range, chosen axes, and whether that row is currently using the saved hold or the original motion.
- You can now save more than one hold row on the same hand or foot, load a picked row back into the frame and axis controls, update picked rows, delete just one row, or delete all rows from the scene.
- The `List Name` field is only for the saved-hold table. It gives a friendlier label like `Right Foot` across every saved row for that same control without renaming the real rig node.
- The `Add Matching Other Side` helper is intentionally conservative. It swaps clear left/right name tokens and refuses to guess if more than one opposite-side control matches.
- Maya Video Reference no longer relies on Maya loading an MP4 directly into an image plane. Movie files are proxied into an image sequence for the current playback range, which avoids the yellow-X "Unable to load the image file" failure seen with direct MP4 image planes.
- Maya Video Reference still uses the active viewport to place the tracing card, so clicking the view you want first is still the safest workflow.
- Maya Video Reference now opens a lightweight `Video Notes` manager when Blue Pencil is unavailable. That fallback uses curve lines on a live drawing surface and visibility holds instead of leaving the user with a dead-end warning.
- Maya Timeline Notes falls back to direct bookmark-node authoring in `mayapy`, so note export/import logic can be tested without the full Maya UI.
- Maya Timeline Notes now has an `Auto Use Highlighted Range` checkbox. When it is on, the Start and End fields follow the highlighted time-slider range automatically, and `Use Playback Range` turns that auto-sync off so manual ranges stay put.
- Maya Timeline Notes now also has `Auto Update Picked Note` on by default, so if you pick a note and change its text, color, or frame range, the scene note updates automatically after a short debounce.
- Maya Timeline Notes now also has a live `Notes At Current Frame` reader in the UI, so as you scrub through highlighted ranges you can read the full note text without hovering the timeline.
- Maya Timeline Notes now has a `Marking Menu` button too, and right-clicking the `Scene Notes` list opens the same quick-action menu for add, update, delete, import, export, and the main note toggles.
- Maya Tutorial Authoring is intentionally not a generic macro recorder in V1. It records supported scene actions into typed checkpoints, and unsupported moments should be authored as manual note or UI-callout steps instead of pretending every Maya click can be replayed safely.
- Guided Practice is separate from Student Demo on purpose. Guided Practice resets to the pre-step checkpoint and expects the student to try the action first, while Student Demo is the watch-it-back lane that jumps through the recorded checkpoints for them.
- Pose Compare is mesh-first in V1. It duplicates visible mesh results into coloured ghost groups, keys their visibility around the chosen frame, and stores compare metadata in the scene so the ghosts still work without the tool installed.
- `Begin Corrected Capture` in Pose Compare is best-effort. It snapshots transform channels under the chosen roots, creates the corrected ghost, then restores the live pose so the original rig can stay readable beside the ghosted fix.
- The shared `Donate` button reads `AMIR_PAYPAL_DONATE_URL` first, then `AMIR_DONATE_URL`, and currently falls back to `https://www.paypal.com/donate/?hosted_button_id=2U2GXSKFJKJCA`.

## Smoke Tests

- `maya_onion_skin_smoke_test.py`: runtime controller smoke test for `mayapy.exe`
- `maya_onion_skin_batch_smoke.py`: writes `maya_onion_skin_batch_result.json` for `mayabatch.exe`
- `maya_onion_skin_qt_smoke_test.py`: best-effort standalone Qt probe that skips cleanly when Maya standalone only exposes `QGuiApplication`
- `maya_onion_skin_gui_driver.py`: external Windows desktop driver that controls the live Maya 2026 GUI, injects the setup script through Script Editor, clicks the tool, changes frames, and captures screenshots
- `maya_onion_skin_live_ui_smoke.py`: broker-driven non-destructive live Maya GUI smoke that opens the tool in the current session, verifies the footer and stepped-sampling controls, then closes the tool again
- `maya_onion_skin_gui_perf_smoke.py`: GUI-side coalescing/perf smoke that bursts timeline changes at `12` past and `12` future frames and verifies the callback refreshes collapse down to a small number of real updates
- `maya_onion_skin_real_scene_benchmark.py`: opens real `.ma`/`.mb` scenes in `mayapy`, auto-picks a plausible mesh root, and records attach/full-refresh/preview-refresh timings to JSON
- `maya_onion_skin_demo_gif.py`: captures a short live Maya loop and builds the public README GIF demo from the current demo scene
- `maya_rotation_doctor_smoke_test.py`: runtime smoke for issue detection, Euler cleanup, spin preservation, interpolation recipes, and the custom continuity pass
- `maya_rotation_doctor_live_ui_smoke.py`: broker-driven live Maya GUI smoke that opens the Rotation Doctor window and verifies its controls plus branded footer
- `maya_rotation_doctor_shelf_install_verify.py`: broker-driven live Maya shelf install check that installs Rotation Doctor into `Amir's Scripts`, confirms the selected shelf tab, and verifies the saved shelf file exists
- `maya_onion_skin_shelf_install_verify.py`: broker-driven live Maya shelf install check that installs Onion Skin into `Amir's Scripts`, confirms the selected shelf tab, and verifies the saved shelf file exists
- `maya_anim_workflow_tools_smoke_test.py`: mayapy smoke for dynamic parenting, dynamic pivot, IK/FK profile detection, profile persistence, and both switch directions
- `maya_anim_workflow_tools_live_ui_smoke.py`: broker-driven live Maya GUI smoke that opens the tabbed workflow window, verifies the tabs, and checks the branded footer
- `maya_anim_workflow_tools_shelf_install_verify.py`: broker-driven live Maya shelf install check that installs the combined Anim Workflow tool into `Amir's Scripts`, confirms the selected shelf tab, and verifies the saved shelf file on disk
- `maya_live_bridge_bootstrap.py`: direct live-Maya bridge bootstrap helper that uses Maya's command-line field instead of relying on Script Editor being open first
- `maya_live_scene_functional_verify.py`: broker-driven live Maya scene verifier that uses the already-open scene, runs a real Onion Skin attach/refresh cycle on scene geometry, and exercises Rotation Doctor plus the combined Anim Workflow tabs with temporary cleanup-only test nodes
- `maya_skinning_cleanup_smoke_test.py`: mayapy smoke for exact-weight skin cleanup, scale freeze, verification, replace, and unsupported-history failure cases
- `maya_skinning_cleanup_live_ui_smoke.py`: broker-driven live Maya GUI smoke that opens the Skinning Cleanup window and verifies its buttons plus branded footer
- `maya_contact_hold_smoke_test.py`: mayapy smoke for planted hand/foot holds over a frame range under root motion
- `maya_rig_scale_export_smoke_test.py`: mayapy smoke for export-copy scale baking, joint-scale verification, exact weight restore, and grouped-rig warnings
- `maya_rig_scale_export_live_ui_smoke.py`: live Maya GUI smoke for the Rig Scale tab controls when the Maya session is healthy enough for broker attachment
- `maya_video_reference_tool_smoke_test.py`: mayapy smoke for video/image-plane import, frame offset setup, and matching audio offset
- `maya_timeline_notes_smoke_test.py`: mayapy smoke for note create/export/delete/import and escaped hover text
- `maya_tutorial_authoring_smoke_test.py`: mayapy smoke for recorded lesson steps, guided/demo checkpoint restore, pose-compare ghost creation, and scene-embedded persistence
- `maya_tutorial_authoring_live_ui_smoke.py`: broker-driven live Maya UI smoke for the tutorial window, its guided/pose-compare modes, dockable workspace-control launch path, and native target highlighting
- `maya_tutorial_authoring_shelf_install_verify.py`: live Maya shelf install verification for the tutorial tool on `Amir's Scripts`
