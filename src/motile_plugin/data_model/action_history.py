from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .actions import TracksAction


class ActionHistory:
    """An action history implementing the ideas from this blog:
    https://github.com/zaboople/klonk/blob/master/TheGURQ.md
    Essentially, if you go back and change something after undo-ing, you can always get
    back to every state if you undo far enough (instead of throwing out
    the undone actions)
    """

    def __init__(self):
        self.undo_stack: list[TracksAction] = []  # list of actions that can be undone
        self.redo_stack: list[TracksAction] = []  # list of actions that can be redone

    @property
    def undo_pointer(self):
        return len(self.undo_stack) - len(self.redo_stack) - 1

    def add_new_action(self, action: TracksAction) -> None:
        """Add a newly performed action to the history.
        Args:
            action (TracksAction): The new action to be added to the history.
        """
        if len(self.redo_stack) > 0:
            # add all the redo stuff to the undo stack, so that both the originial and
            # inverse are on the stack
            self.undo_stack.extend(self.redo_stack)
            self.redo_stack = []
        self.undo_stack.append(action)

    def undo(self) -> bool:
        """Undo the last performed action

        Returns:
            bool: True if an action was undone, and False
            if there was no previous action to undo.
        """
        if self.undo_pointer < 0:
            return False
        else:
            action = self.undo_stack[self.undo_pointer]
            inverse = action.inverse()
            self.redo_stack.append(inverse)
            return True

    def redo(self) -> bool:
        """Redo the last undone action

        Returns:
            bool: True if an action was redone, and False
            if there was no undone action to redo.
        """
        if len(self.redo_stack) == 0:
            return False
        else:
            action = self.redo_stack.pop(-1)
            # apply the inverse but don't save it
            # (the original is already on the undo stack)
            action.inverse()
            return True
