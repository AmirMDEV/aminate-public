from __future__ import absolute_import, division, print_function

import json
import os
import shutil
import time
import zipfile

try:
    import maya.cmds as cmds
    MAYA_AVAILABLE = True
except Exception:
    cmds = None
    MAYA_AVAILABLE = False

try:
    from PySide6 import QtCore, QtWidgets
except Exception:
    try:
        from PySide2 import QtCore, QtWidgets
    except Exception:
        QtCore = QtWidgets = None

try:
    from maya.app.general.mayaMixin import MayaQWidgetDockableMixin
except Exception:
    MayaQWidgetDockableMixin = None

WINDOW_OBJECT_NAME = "mayaReferenceManagerWindow"
PACKAGE_FOLDER_NAME = "reference_packages"
MANIFEST_FILE_NAME = "reference_package_manifest.json"

REFERENCE_MANAGER_ATTR_SPECS = (
    ("file", "fileTextureName", "sourceimages"),
    ("imagePlane", "imageName", "sourceimages"),
    ("audio", "filename", "audio"),
    ("AlembicNode", "abc_File", "cache"),
    ("gpuCache", "cacheFileName", "cache"),
)


def _maya_main_window():
    if not MAYA_AVAILABLE or not QtWidgets:
        return None
    try:
        import maya.OpenMayaUI as omui
        try:
            import shiboken6 as shiboken
        except Exception:
            import shiboken2 as shiboken
        ptr = omui.MQtUtil.mainWindow()
        if ptr is None:
            return None
        return shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        return None


def _normalize_path(path_value):
    if not path_value:
        return ""
    path_value = os.path.expandvars(str(path_value)).replace("/", os.sep)
    return os.path.normpath(path_value)


def _resolve_existing_path(path_value):
    normalized = _normalize_path(path_value)
    if not normalized:
        return ""
    if os.path.exists(normalized) or os.path.isabs(normalized):
        return normalized
    roots = [
        _scene_folder(),
        _workspace_root(),
        os.path.join(_workspace_root(), "sourceimages"),
        os.path.join(_workspace_root(), "textures"),
        os.path.join(_scene_folder(), "sourceimages"),
        os.path.join(_scene_folder(), "textures"),
    ]
    for root_path in roots:
        if not root_path:
            continue
        candidate = _normalize_path(os.path.join(root_path, normalized))
        if os.path.exists(candidate):
            return candidate
    return normalized


def _scene_path():
    if not cmds:
        return ""
    return _normalize_path(cmds.file(query=True, sceneName=True) or "")


def _workspace_root():
    if not cmds:
        return os.getcwd()
    try:
        return _normalize_path(cmds.workspace(query=True, rootDirectory=True) or "")
    except Exception:
        return os.getcwd()


def _scene_folder():
    scene_name = _scene_path()
    if scene_name:
        return os.path.dirname(scene_name)
    return _workspace_root() or os.getcwd()


def _safe_slug(value, fallback="scene"):
    value = os.path.splitext(os.path.basename(value or ""))[0] or fallback
    cleaned = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or fallback


def _unique_path(path_value):
    if not os.path.exists(path_value):
        return path_value
    root, ext = os.path.splitext(path_value)
    index = 1
    while os.path.exists("{0}_{1}{2}".format(root, index, ext)):
        index += 1
    return "{0}_{1}{2}".format(root, index, ext)


def _unique_dest_path(folder_path, file_name):
    safe_name = os.path.basename(file_name or "file")
    candidate = os.path.join(folder_path, safe_name)
    return _unique_path(candidate)


def _copy_file(source_path, destination_path):
    folder_path = os.path.dirname(destination_path)
    if folder_path and not os.path.isdir(folder_path):
        os.makedirs(folder_path)
    shutil.copy2(source_path, destination_path)


def _relative_to_scene(package_scene_path, copied_path):
    try:
        return os.path.relpath(copied_path, os.path.dirname(package_scene_path)).replace(os.sep, "/")
    except Exception:
        return copied_path.replace(os.sep, "/")


def _relative_to_package(package_dir, copied_path):
    try:
        return os.path.relpath(copied_path, package_dir).replace(os.sep, "/")
    except Exception:
        return copied_path.replace(os.sep, "/")


def _rewrite_packaged_scene_paths(package_scene_path, package_dir, copied_records):
    if not package_scene_path.lower().endswith(".ma") or not os.path.exists(package_scene_path):
        return False
    try:
        with open(package_scene_path, "r") as handle:
            scene_text = handle.read()
    except Exception:
        return False
    updated_text = scene_text
    for record in copied_records:
        absolute_path = _normalize_path(record.get("package_path", ""))
        if not absolute_path:
            continue
        relative_path = _relative_to_package(package_dir, absolute_path)
        path_variants = [
            absolute_path,
            absolute_path.replace(os.sep, "/"),
            absolute_path.replace("/", "\\"),
            absolute_path.replace("\\", "/"),
            absolute_path.replace("\\", "\\\\"),
        ]
        for path_variant in path_variants:
            updated_text = updated_text.replace(path_variant, relative_path)
    if updated_text == scene_text:
        return False
    with open(package_scene_path, "w") as handle:
        handle.write(updated_text)
    return True


def _dedupe_records(records):
    deduped = []
    seen = set()
    for record in records:
        source = _normalize_path(record.get("source", ""))
        key = (record.get("kind", ""), source.lower(), record.get("node", ""), record.get("attr", ""))
        if key in seen:
            continue
        seen.add(key)
        record["source"] = source
        record["exists"] = bool(source and os.path.exists(source))
        deduped.append(record)
    return deduped


def _reference_node_path(ref_node):
    try:
        return cmds.referenceQuery(ref_node, filename=True, withoutCopyNumber=True)
    except Exception:
        try:
            return cmds.referenceQuery(ref_node, filename=True)
        except Exception:
            return ""


def _collect_reference_records():
    if not cmds:
        return []
    records = []
    ref_nodes = cmds.ls(type="reference") or []
    for ref_node in ref_nodes:
        if ref_node == "sharedReferenceNode":
            continue
        source_path = _resolve_existing_path(_reference_node_path(ref_node))
        if not source_path:
            continue
        try:
            loaded = bool(cmds.referenceQuery(ref_node, isLoaded=True))
        except Exception:
            loaded = False
        records.append(
            {
                "kind": "reference",
                "node": ref_node,
                "attr": "",
                "source": source_path,
                "folder": "references",
                "loaded": loaded,
            }
        )
    return _dedupe_records(records)


def _collect_external_records():
    if not cmds:
        return []
    records = []
    try:
        available_node_types = set(cmds.allNodeTypes() or [])
    except Exception:
        available_node_types = set()
    for node_type, attr_name, folder_name in REFERENCE_MANAGER_ATTR_SPECS:
        if available_node_types and node_type not in available_node_types:
            continue
        try:
            nodes = cmds.ls(type=node_type) or []
        except Exception:
            nodes = []
        for node_name in nodes:
            try:
                if not cmds.attributeQuery(attr_name, node=node_name, exists=True):
                    continue
                source_path = cmds.getAttr("{0}.{1}".format(node_name, attr_name)) or ""
            except Exception:
                source_path = ""
            source_path = _resolve_existing_path(source_path)
            if not source_path:
                continue
            records.append(
                {
                    "kind": "external",
                    "node": node_name,
                    "attr": attr_name,
                    "source": source_path,
                    "folder": folder_name,
                    "loaded": True,
                }
            )
    return _dedupe_records(records)


class ReferencePackageController(object):
    def __init__(self, status_callback=None):
        self.status_callback = status_callback
        self.last_result = {}

    def set_status_callback(self, callback):
        self.status_callback = callback

    def _emit_status(self, message, ok=True):
        if self.status_callback:
            self.status_callback(message, ok)

    def collect_dependencies(self, include_references=True, include_external=True):
        if not MAYA_AVAILABLE:
            raise RuntimeError("Reference Manager must run inside Maya.")
        records = []
        if include_references:
            records.extend(_collect_reference_records())
        if include_external:
            records.extend(_collect_external_records())
        return {
            "scene": _scene_path(),
            "records": _dedupe_records(records),
        }

    def default_output_dir(self):
        return os.path.join(_scene_folder(), PACKAGE_FOLDER_NAME)

    def package_current_scene(
        self,
        output_dir=None,
        package_name=None,
        include_references=True,
        include_external=True,
        save_scene=True,
        retarget_package_scene=True,
    ):
        if not MAYA_AVAILABLE:
            raise RuntimeError("Reference Manager must run inside Maya.")
        original_scene = _scene_path()
        if not original_scene:
            raise RuntimeError("Save the scene once before packaging.")
        if save_scene:
            cmds.file(save=True, force=True)

        dependencies = self.collect_dependencies(include_references=include_references, include_external=include_external)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        base_name = _safe_slug(package_name or original_scene)
        output_dir = _normalize_path(output_dir or self.default_output_dir())
        package_dir = _unique_path(os.path.join(output_dir, "{0}_{1}".format(base_name, timestamp)))
        scenes_dir = os.path.join(package_dir, "scenes")
        os.makedirs(scenes_dir)
        package_scene_path = os.path.join(scenes_dir, "{0}_packaged.ma".format(base_name))

        copy_map = {}
        copied_records = []
        missing_records = []
        for record in dependencies["records"]:
            source_path = record["source"]
            if not source_path or not os.path.exists(source_path):
                missing_records.append(dict(record))
                continue
            destination_dir = os.path.join(package_dir, record.get("folder") or "external")
            destination_path = _unique_dest_path(destination_dir, os.path.basename(source_path))
            _copy_file(source_path, destination_path)
            packaged_record = dict(record)
            packaged_record["package_path"] = destination_path
            packaged_record["package_relpath"] = os.path.relpath(destination_path, package_dir).replace(os.sep, "/")
            copy_map[source_path.lower()] = packaged_record
            copied_records.append(packaged_record)

        warnings = []
        old_selection = cmds.ls(selection=True, long=True) or []
        try:
            cmds.file(rename=package_scene_path)
            if retarget_package_scene:
                for record in copied_records:
                    node_name = record.get("node") or ""
                    attr_name = record.get("attr") or ""
                    if record.get("kind") == "reference" and node_name:
                        try:
                            cmds.file(record["package_path"], loadReference=node_name)
                        except Exception as exc:
                            warnings.append("Could not retarget reference {0}: {1}".format(node_name, exc))
                    elif node_name and attr_name and cmds.objExists(node_name):
                        try:
                            if cmds.attributeQuery(attr_name, node=node_name, exists=True):
                                cmds.setAttr("{0}.{1}".format(node_name, attr_name), record["package_path"], type="string")
                        except Exception as exc:
                            warnings.append("Could not retarget {0}.{1}: {2}".format(node_name, attr_name, exc))
            cmds.file(save=True, type="mayaAscii", force=True)
            if retarget_package_scene:
                _rewrite_packaged_scene_paths(package_scene_path, package_dir, copied_records)
        finally:
            try:
                cmds.file(original_scene, open=True, force=True, prompt=False)
            except Exception as exc:
                warnings.append("Packaged scene saved, but original scene could not reopen: {0}".format(exc))
            if old_selection:
                try:
                    cmds.select(old_selection, replace=True)
                except Exception:
                    pass

        manifest = {
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "original_scene": original_scene,
            "packaged_scene": os.path.relpath(package_scene_path, package_dir).replace(os.sep, "/"),
            "copied_files": [
                {
                    "kind": record.get("kind"),
                    "node": record.get("node"),
                    "attr": record.get("attr"),
                    "source": record.get("source"),
                    "package_relpath": record.get("package_relpath"),
                    "loaded": record.get("loaded"),
                }
                for record in copied_records
            ],
            "missing_files": missing_records,
            "warnings": warnings,
        }
        manifest_path = os.path.join(package_dir, MANIFEST_FILE_NAME)
        with open(manifest_path, "w") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)

        zip_path = shutil.make_archive(package_dir, "zip", output_dir, os.path.basename(package_dir))
        result = {
            "package_dir": package_dir,
            "zip_path": zip_path,
            "package_scene": package_scene_path,
            "copied_count": len(copied_records),
            "missing_count": len(missing_records),
            "warnings": warnings,
            "manifest_path": manifest_path,
        }
        self.last_result = result
        message = "Packaged scene zip with {0} file(s): {1}".format(len(copied_records), zip_path)
        if missing_records:
            message += " Missing {0} file(s).".format(len(missing_records))
        self._emit_status(message, not bool(missing_records))
        return result


if QtWidgets:
    if MayaQWidgetDockableMixin is not None:
        _WindowBase = type("MayaReferenceManagerWindowBase", (MayaQWidgetDockableMixin, QtWidgets.QDialog), {})
    else:
        _WindowBase = type("MayaReferenceManagerWindowBase", (QtWidgets.QDialog,), {})

    class ReferenceManagerPanel(QtWidgets.QWidget):
        def __init__(self, controller=None, status_callback=None, parent=None):
            super(ReferenceManagerPanel, self).__init__(parent)
            self.controller = controller or ReferencePackageController()
            self.status_callback = status_callback
            self.controller.set_status_callback(self._set_status)
            self._build_ui()
            self.refresh_files()

        def _build_ui(self):
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(12, 12, 12, 12)
            layout.setSpacing(8)

            intro = QtWidgets.QLabel(
                "Package the current scene plus Maya references, textures, image planes, audio, caches, and a manifest into one zip."
            )
            intro.setWordWrap(True)
            layout.addWidget(intro)

            output_row = QtWidgets.QHBoxLayout()
            output_row.addWidget(QtWidgets.QLabel("Output folder"))
            self.output_path = QtWidgets.QLineEdit(self.controller.default_output_dir() if MAYA_AVAILABLE else "")
            self.output_path.setToolTip("Folder where Reference Manager writes package folder plus zip.")
            output_row.addWidget(self.output_path, 1)
            self.browse_button = QtWidgets.QPushButton("Browse")
            self.browse_button.setToolTip("Choose folder for created package zip.")
            output_row.addWidget(self.browse_button)
            layout.addLayout(output_row)

            name_row = QtWidgets.QHBoxLayout()
            name_row.addWidget(QtWidgets.QLabel("Package name"))
            default_name = _safe_slug(_scene_path(), "maya_scene") if MAYA_AVAILABLE else "maya_scene"
            self.package_name = QtWidgets.QLineEdit(default_name)
            self.package_name.setToolTip("Base name used for package folder, packaged scene, zip file.")
            name_row.addWidget(self.package_name, 1)
            layout.addLayout(name_row)

            options_row = QtWidgets.QHBoxLayout()
            self.save_scene_box = QtWidgets.QCheckBox("Save current scene first")
            self.save_scene_box.setChecked(True)
            self.save_scene_box.setToolTip("Save current Maya file before copying dependencies so latest edits get packaged.")
            self.references_box = QtWidgets.QCheckBox("Include Maya references")
            self.references_box.setChecked(True)
            self.references_box.setToolTip("Copy referenced Maya scenes from reference nodes into package references folder.")
            self.external_box = QtWidgets.QCheckBox("Include textures, audio, caches")
            self.external_box.setChecked(True)
            self.external_box.setToolTip("Copy file textures, image planes, audio, Alembic caches, GPU caches into package folders.")
            self.relative_box = QtWidgets.QCheckBox("Make packaged scene use relative paths")
            self.relative_box.setChecked(True)
            self.relative_box.setToolTip("Write packaged scene paths so extracted package can move to another computer.")
            for widget in (self.save_scene_box, self.references_box, self.external_box, self.relative_box):
                options_row.addWidget(widget)
            options_row.addStretch(1)
            layout.addLayout(options_row)

            action_row = QtWidgets.QHBoxLayout()
            self.refresh_button = QtWidgets.QPushButton("Refresh Needed Files")
            self.refresh_button.setToolTip("Scan current Maya scene for references plus external files before packaging.")
            self.package_button = QtWidgets.QPushButton("Package Scene To Zip")
            self.package_button.setToolTip("Save scene, copy needed files, write manifest, create final zip package.")
            self.open_folder_button = QtWidgets.QPushButton("Open Package Folder")
            self.open_folder_button.setToolTip("Open folder containing latest package zip in Windows Explorer.")
            action_row.addWidget(self.refresh_button)
            action_row.addWidget(self.package_button)
            action_row.addWidget(self.open_folder_button)
            action_row.addStretch(1)
            layout.addLayout(action_row)

            self.files_table = QtWidgets.QTableWidget(0, 4)
            self.files_table.setHorizontalHeaderLabels(["Type", "Node", "Source", "Status"])
            self.files_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            self.files_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.files_table.setToolTip("Shows each referenced or external file found, source path, node, found or missing state.")
            self.files_table.horizontalHeader().setStretchLastSection(True)
            self.files_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
            layout.addWidget(self.files_table, 1)

            self.status_label = QtWidgets.QLabel("Ready.")
            self.status_label.setWordWrap(True)
            layout.addWidget(self.status_label)

            self.refresh_button.clicked.connect(self.refresh_files)
            self.package_button.clicked.connect(self.package_scene)
            self.open_folder_button.clicked.connect(self.open_package_folder)
            self.browse_button.clicked.connect(self.pick_output_folder)

        def _set_status(self, message, ok=True):
            self.status_label.setText(message)
            if self.status_callback:
                self.status_callback(message, ok)

        def pick_output_folder(self):
            start_dir = self.output_path.text() or self.controller.default_output_dir()
            folder_path = QtWidgets.QFileDialog.getExistingDirectory(self, "Choose package output folder", start_dir)
            if folder_path:
                self.output_path.setText(folder_path)

        def refresh_files(self):
            self.files_table.setRowCount(0)
            try:
                data = self.controller.collect_dependencies(
                    include_references=self.references_box.isChecked(),
                    include_external=self.external_box.isChecked(),
                )
            except Exception as exc:
                self._set_status(str(exc), False)
                return
            for record in data["records"]:
                row = self.files_table.rowCount()
                self.files_table.insertRow(row)
                values = [
                    record.get("kind", ""),
                    record.get("node", ""),
                    record.get("source", ""),
                    "Found" if record.get("exists") else "Missing",
                ]
                for column, value in enumerate(values):
                    self.files_table.setItem(row, column, QtWidgets.QTableWidgetItem(str(value)))
            self._set_status("Found {0} file(s) needed by this scene.".format(len(data["records"])), True)

        def package_scene(self):
            try:
                result = self.controller.package_current_scene(
                    output_dir=self.output_path.text(),
                    package_name=self.package_name.text(),
                    include_references=self.references_box.isChecked(),
                    include_external=self.external_box.isChecked(),
                    save_scene=self.save_scene_box.isChecked(),
                    retarget_package_scene=self.relative_box.isChecked(),
                )
            except Exception as exc:
                self._set_status(str(exc), False)
                return
            self._set_status("Zip ready: {0}".format(result["zip_path"]), True)
            self.refresh_files()

        def open_package_folder(self):
            result = self.controller.last_result or {}
            folder_path = result.get("package_dir") or self.output_path.text()
            if folder_path and os.path.exists(folder_path):
                try:
                    os.startfile(folder_path)
                except Exception:
                    self._set_status("Package folder is {0}".format(folder_path), True)

    class MayaReferenceManagerWindow(_WindowBase):
        def __init__(self, controller=None, parent=None):
            super(MayaReferenceManagerWindow, self).__init__(parent or _maya_main_window())
            self.controller = controller or ReferencePackageController()
            self.setObjectName(WINDOW_OBJECT_NAME)
            self.setWindowTitle("Reference Manager")
            self.setMinimumSize(640, 360)
            layout = QtWidgets.QVBoxLayout(self)
            self.panel = ReferenceManagerPanel(self.controller, parent=self)
            layout.addWidget(self.panel)


GLOBAL_WINDOW = None
GLOBAL_CONTROLLER = None


def launch_maya_reference_manager(dock=False):
    global GLOBAL_WINDOW
    global GLOBAL_CONTROLLER
    if not MAYA_AVAILABLE:
        raise RuntimeError("launch_maya_reference_manager() must run inside Maya.")
    if not QtWidgets:
        raise RuntimeError("PySide is not available in this Maya session.")
    GLOBAL_CONTROLLER = ReferencePackageController()
    GLOBAL_WINDOW = MayaReferenceManagerWindow(GLOBAL_CONTROLLER)
    if dock:
        try:
            GLOBAL_WINDOW.show(dockable=True, floating=True, area="right")
        except Exception:
            GLOBAL_WINDOW.show()
    else:
        GLOBAL_WINDOW.show()
    return GLOBAL_WINDOW


__all__ = [
    "ReferencePackageController",
    "ReferenceManagerPanel",
    "MayaReferenceManagerWindow",
    "launch_maya_reference_manager",
]
