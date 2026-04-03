"""
maya_anim_workflow_tools.py

Canonical entrypoint for the combined Maya Anim Workflow Tools UI.
"""

from __future__ import absolute_import, division, print_function

import importlib

import maya_dynamic_parent_pivot as _impl  # noqa: F401
import maya_dynamic_parenting_tool as _parenting  # noqa: F401
import maya_contact_hold as _contact_hold  # noqa: F401
import maya_onion_skin as _onion  # noqa: F401
import maya_rotation_doctor as _rotation  # noqa: F401
import maya_skinning_cleanup as _skin  # noqa: F401
import maya_rig_scale_export as _rig_scale  # noqa: F401
import maya_video_reference_tool as _video_reference  # noqa: F401
import maya_timeline_notes as _timeline_notes  # noqa: F401


def _reloaded_impl():
    importlib.reload(_parenting)
    importlib.reload(_contact_hold)
    importlib.reload(_onion)
    importlib.reload(_rotation)
    importlib.reload(_skin)
    importlib.reload(_rig_scale)
    importlib.reload(_video_reference)
    importlib.reload(_timeline_notes)
    return importlib.reload(_impl)


DEFAULT_SHELF_BUTTON_LABEL = _impl.DEFAULT_SHELF_BUTTON_LABEL
DEFAULT_SHELF_NAME = _impl.DEFAULT_SHELF_NAME
DONATE_URL = _impl.DONATE_URL
FOLLOW_AMIR_URL = _impl.FOLLOW_AMIR_URL
MayaAnimWorkflowController = _impl.MayaAnimWorkflowController
MayaAnimWorkflowWindow = _impl.MayaAnimWorkflowWindow
SHELF_BUTTON_DOC_TAG = _impl.SHELF_BUTTON_DOC_TAG


def launch_maya_anim_workflow_tools(dock=False, initial_tab="quick_start"):
    impl = _reloaded_impl()
    return impl.launch_maya_dynamic_parent_pivot(dock=dock, initial_tab=initial_tab)


def install_maya_anim_workflow_tools_shelf_button(
    shelf_name=DEFAULT_SHELF_NAME,
    button_label=DEFAULT_SHELF_BUTTON_LABEL,
    repo_path=None,
):
    impl = _reloaded_impl()
    return impl.install_maya_dynamic_parent_pivot_shelf_button(
        shelf_name=shelf_name,
        button_label=button_label,
        repo_path=repo_path,
    )


__all__ = [
    "DEFAULT_SHELF_BUTTON_LABEL",
    "DEFAULT_SHELF_NAME",
    "DONATE_URL",
    "FOLLOW_AMIR_URL",
    "MayaAnimWorkflowController",
    "MayaAnimWorkflowWindow",
    "SHELF_BUTTON_DOC_TAG",
    "install_maya_anim_workflow_tools_shelf_button",
    "launch_maya_anim_workflow_tools",
]
