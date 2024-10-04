from __future__ import annotations

from typing import TYPE_CHECKING

from napari.utils.notifications import show_warning

if TYPE_CHECKING:
    from .actions import TracksAction


class ActionHistory:
    """A list of actions in chronological order and a pointer to the last performed
    action. Actions after the pointer have been un-done, and will be removed if a new
    action is added to the list.
    """

    def __init__(self):
        self.action_list = []
        self.pointer = -1

    def append(self, action: TracksAction) -> None:
        """Delete any actions after the current pointer position and then append the new
        action and set the pointer to that action

        Args:
            action (TracksAction): The new action to be added to the list.
        """
        self.action_list = self.action_list[: self.pointer + 1]
        self.action_list.append(action)
        self.pointer = len(self.action_list) - 1

    def previous(self) -> TracksAction | None:
        """Get the previous performed action (the one under the pointer), and update the
        pointer to the action before that. Assumes that the returned action will be
        un-done (its inverse will be applied).

        Returns:
            TracksAction | None: The last performed action, to be un-done, or None
            if there is no previous action.
        """

        if self.pointer >= 0 and self.pointer < len(self.action_list):
            action = self.action_list[self.pointer]
            self.pointer -= 1
            return action
        else:
            show_warning("No more actions to undo")
            return None

    def next(self) -> TracksAction | None:
        """Get the next action to be performed (the one after the pointer), and
        update the pointer to that action. Assumes that the returned action will
        be applied.

        Returns:
            TracksAction | None: The next action to apply, or None if the pointer
            is already at the end of the list or the list is empty.
        """

        if self.pointer < len(self.action_list) - 1:
            self.pointer += 1
            return self.action_list[self.pointer]
        else:
            show_warning("No more actions to redo")
            return None
