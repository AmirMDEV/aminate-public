"""
maya_universal_ikfk_switcher.py

Compatibility entrypoint for opening the IK/FK tab of the combined
Aminate window.
"""

from __future__ import absolute_import, division, print_function

import importlib

import maya_anim_workflow_tools as _workflow  # noqa: F401


DEFAULT_SHELF_BUTTON_LABEL = _workflow.DEFAULT_SHELF_BUTTON_LABEL
DEFAULT_SHELF_NAME = _workflow.DEFAULT_SHELF_NAME
DONATE_URL = _workflow.DONATE_URL
FOLLOW_AMIR_URL = _workflow.FOLLOW_AMIR_URL
MayaAnimWorkflowController = _workflow.MayaAnimWorkflowController
MayaAnimWorkflowWindow = _workflow.MayaAnimWorkflowWindow


def _reloaded_workflow():
    return importlib.reload(_workflow)


def launch_maya_universal_ikfk_switcher(dock=False):
    workflow = _reloaded_workflow()
    return workflow.launch_maya_anim_workflow_tools(dock=dock, initial_tab="ikfk")


def install_maya_universal_ikfk_switcher_shelf_button(
    shelf_name=DEFAULT_SHELF_NAME,
    button_label="IK/FK Switcher",
    repo_path=None,
):
    workflow = _reloaded_workflow()
    return workflow.install_maya_anim_workflow_tools_shelf_button(
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
    "install_maya_universal_ikfk_switcher_shelf_button",
    "launch_maya_universal_ikfk_switcher",
]
