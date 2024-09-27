from __future__ import annotations

from napari.utils.notifications import show_warning

from .actions import TracksAction


class ActionHistory:
    """A list of actions in chronological order and a pointer to keep track of undo and redo events."""

    def __init__(self):
        self.action_list = []
        self.pointer = -1

    def append(self, action: TracksAction) -> None:
        """Delete any actions after the current pointer position and then append the new action and set the pointer to that action"""
        self.action_list = self.action_list[: self.pointer + 1]
        self.action_list.append(action)
        self.pointer = len(self.action_list) - 1

    def move_up(self) -> TracksAction:
        """Move pointer up in the action list (for undo)"""

        if self.pointer >= 0 and self.pointer < len(self.action_list):
            action = self.action_list[self.pointer]
            self.pointer -= 1
            return action
        else:
            show_warning("No more actions to undo")

    def move_down(self) -> TracksAction:
        """Move pointer down in the action list (for redo)"""

        if self.pointer < len(self.action_list) - 1:
            self.pointer += 1
            return self.action_list[self.pointer]
        else:
            show_warning("No more actions to redo")
