## Maya Animation Tools

Shared MCP configuration and cross-project environment knowledge live in:

- `C:\Users\Amir Mansaray\.codex\config.toml`
- `C:\Users\Amir Mansaray\.codex\AGENTS.md`

This folder is the canonical Windows source-of-truth for standalone Maya animation helpers that should stay lightweight, shelf-installable, and version-tolerant across recent Maya releases.

### Start Here

- `WORKSPACE_MAP.md`
- `README.md`
- `maya_shelf_utils.py`
- `maya_anim_workflow_tools.py`
- `maya_dynamic_parent_pivot.py`
- `maya_dynamic_parenting_tool.py`
- `maya_contact_hold.py`
- `maya_onion_skin.py`
- `maya_rotation_doctor.py`
- `maya_skinning_cleanup.py`
- `maya_rig_scale_export.py`
- `maya_tutorial_authoring.py`

### Scope

Keep this folder focused on Maya and animation tooling. Browser automation, NAS, and general OpenClaw helpers belong in their own routed projects instead of here.

### Recovery

- If Maya is not healthy on startup or the workspace restore is broken, stop and repair Maya before continuing script work.
- Known live-machine corruption case: malformed duplicate shelf files such as `shelf_Amir_s_Scripts.mel.mel` under `C:\Users\Amir Mansaray\Documents\maya\2026\prefs\shelves\`.
- Shelf installers in this repo must not leave malformed `.mel.mel` files in the live Maya shelf prefs folder.

### Shelf Defaults

- New shelf-installable Maya tools in this folder should expose a repo-owned `install_*_shelf_button()` function.
- Default the installer target to `Amir's Scripts` unless the user explicitly asks for another shelf.
- Use a stable `docTag`, replace older copies of the same tool button on reinstall, and save the shelf after installation.
- If Maya is already open and the task adds a new Maya tool, install or refresh that shelf button in the live Maya GUI before finishing.

### UI Defaults

- New visible Maya tools should include the standard Amir footer plus the PayPal-yellow `Donate` button unless the user explicitly asks for a different treatment.
- Prefer combined tabbed UIs for related Maya workflows instead of scattering tightly related tools across unrelated floating windows.
- `maya_tutorial_authoring.py` is an allowed standalone exception while the author/player workflow remains its own reusable teaching tool rather than a tab inside the main animation workflow window.
- When `maya_tutorial_authoring.py` grows, prefer adding new lanes as explicit modes or internal tabs instead of stacking more full-height sections into one long scrolling page.
- Treat Guided Practice and Pose Compare as part of the tutorial tool's core scope; update their smoke coverage and scene-persistence docs whenever they change.
- When embedding sibling Maya tools into the combined Anim Workflow window, make them behave like real child panels inside the tabs instead of leaving them as floating dialog-style widgets.
- For dockable Maya UIs in this repo, use a real dock host widget with its own object name, let Maya create the `workspaceControl` from that host name, and keep the content widget parented under that host. Do not name the host like the final workspace control or Maya can dock an empty shell while the real UI still floats.
- When adding a new workflow to the combined tool, update the tabbed UI, README, workspace map, and smoke coverage in the same task so the main entrypoint stays truthful.
