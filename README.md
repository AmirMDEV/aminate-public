# Aminate

By Amir Mansaray

A tabbed Maya toolset for animation workflow helpers.

## Sections In Use

The sections in regular use in this beta are:

- `Student Core` for compact color-coded timing buttons, a small dockable timeline bar, key nudging, inbetweens, reset pose, bake-on-twos, animated-control selection, and static-curve cleanup
- `Scene Helpers` for the Student Core strip, Animation Layer Tint, camera presets, render setup, texture loading, and game animation mode
- `Reference Manager` for saving the current scene and packaging Maya references, textures, image planes, audio, caches, and a manifest into one zip
- `Controls Retargeter (Face and Body)` for control-based retarget between rigs
- `Control Picker` for scene control mapping, grouping, reordering, attr lookup, synced Maya selection, and list / visual control maps
- `Animators Pencil` for Blue Pencil-style drawing, layers, frame markers, ghosting, retiming, and scene-native annotation marks
- `Onion Skin` in `3D Ghost` mode
- `Dynamic Parenting`
- `Hand / Foot Hold`, mainly the foot-hold workflow
- `Timeline Notes`

Other tabs are present in the interface, but they are still closer to preview or in-progress sections at the moment.

`Version 0.2 BETA`

## Install

1. Download `Aminate_v0.2_BETA.zip` from the latest release.
2. Unzip it.
3. Open the `aminate` folder inside the extracted folder.
4. Open Autodesk Maya.
5. Drag `install_maya_anim_workflow_tools_dragdrop.py` into the Maya viewport.
6. The tool installs, opens, and docks automatically.
7. After install, Maya opens Aminate and the Student Core timeline bar when Maya starts.

## How To Use

### Student Core

This section is for the small repeat jobs students do while blocking and polishing animation.

Simple example:

1. Select one or more animated controls.
2. Use `-1` or `+1` to nudge the selected keys earlier or later.
3. Use `In` to add an inbetween key on the current frame.
4. Use `Cut` to remove a key on the current frame.
5. Use `Zero` to reset selected controls to translate 0, rotate 0, and scale 1.
6. Use `2s` to bake selected controls every two frames across the playback range.
7. Use `Open Timeline Bar` if the small color-coded strip above Maya's timeline is closed.

### Scene Helpers

This section is for shot setup, timing cleanup, texture refresh, and the always-visible timeline helper strip.

Simple example:

1. Keep `Animation Layer Tint` on.
2. Select or change an animation layer in Maya.
3. The docked Student Core timeline bar shows that layer name and tint color above the timeline.
4. Use `Game Animation Mode` for 30 fps realtime playback and student-safe autosave defaults.
5. Use `Set Up Render Environment` for the helper cameras, light, and cyclorama.

### Dynamic Parenting

This section is for props that need to move between parents, like a magazine moving between a hand, a gun, and world space.

Simple example:

1. Put the magazine where you want it.
2. Click `Add Object`.
3. Pick the hand or gun.
4. Click `Pick Parent`.
5. If you want the object to line up to that parent, click `Snap To Parent`.
6. If you want to save a custom grip position for that parent, move the object and click `Save This Offset`.
7. Click `Switch to this Parent`.
8. Use `World` when you want the object to let go.

### Reference Manager

This section is for moving a shot to another computer without hunting for referenced files by hand.

Simple example:

1. Save the current scene once.
2. Open `Reference Manager`.
3. Click `Refresh Needed Files`.
4. Keep `Include Maya references` on.
5. Keep `Include textures, audio, caches` on.
6. Click `Package Scene To Zip`.
7. Use the created zip on another machine.

### Hand / Foot Hold

This section is for planted contact, especially when a foot should stay in place while the body keeps moving.

Simple example:

1. Pick the foot control.
2. Set the frame where the foot first touches down.
3. Set the frame where the foot stops sticking.
4. Choose the world axis you want to lock.
5. Save the hold.
6. Use the saved hold list to turn rows on, off, update them, or delete them later.

### Onion Skin

The dependable mode in the current beta is `3D Ghost`.

Simple example:

1. Pick the rig root or object you want to preview.
2. Open the `Onion Skin` tab.
3. Choose your past and future ghost counts.
4. Keep the mode on `3D Ghost`.
5. Attach the preview.
6. Scrub the timeline to see the ghosted poses.

### Animators Pencil

This section is for drawing animation notes, arcs, contact marks, timing plans, and simple 2D annotations inside Maya.

Simple example:

1. Open `Animators Pencil`.
2. Use `Open Blue Pencil` if you want Maya's native Blue Pencil drawing tools.
3. Use `Add Layer` for a script-managed layer.
4. Pick a tool, color, size, and opacity.
5. Click `Create Mark` to create a real Maya curve or text mark in front of the current camera.
6. Use `Add Key`, `Duplicate Previous Key`, `Retime`, `Add Frame Marker`, or `Build Ghosts` for drawing animation timing.
7. The script-managed marks are real Maya scene nodes, so the scene still shows them even without this script installed.

### Timeline Notes

This section is for colored timeline ranges with readable notes attached to them.
Use `Scene Helpers` or the docked Student Core timeline bar when you need key nudging, inbetweens, reset pose, bake-on-twos, or Animation Layer Tint next to timeline review.

Simple example:

1. Highlight a range in the time slider.
2. Open `Timeline Notes`.
3. Leave the auto highlighted-range option on if you want the note to follow the selected range.
4. Type the full note text.
5. Pick a color.
6. Add the note.
7. Scrub through the timeline to read the notes in the live reader.

## Tab Screenshots

- [Quick Start](release_screenshots/quick_start.png)
- [Student Core](release_screenshots/student_core.png)
- [Student Timeline Bar](release_screenshots/student_timeline_bar.png)
- [Reference Manager](release_screenshots/reference_manager.png)
- [Dynamic Parenting](release_screenshots/dynamic_parenting.png)
- [Hand / Foot Hold](release_screenshots/hand_foot_hold.png)
- [Scene Helpers](release_screenshots/scene_helpers.png)
- [Dynamic Pivot](release_screenshots/dynamic_pivot.png)
- [Universal IK/FK](release_screenshots/universal_ikfk.png)
- [Controls Retargeter](release_screenshots/controls_retargeter.png)
- [Control Picker](release_screenshots/control_picker.png)
- [Animators Pencil](release_screenshots/animators_pencil.png)
- [Onion Skin](release_screenshots/onion_skin.png)
- [Rotation Doctor](release_screenshots/rotation_doctor.png)
- [Skinning Cleanup](release_screenshots/skinning_cleanup.png)
- [Rig Scale](release_screenshots/rig_scale.png)
- [Video Reference](release_screenshots/video_reference.png)
- [Timeline Notes](release_screenshots/timeline_notes.png)
