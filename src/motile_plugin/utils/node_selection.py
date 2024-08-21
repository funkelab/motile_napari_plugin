from psygnal import Signal
from PyQt5.QtCore import QObject


class NodeSelectionList(QObject):
    """Updates the current selection (0, 1, or 2) of nodes. Sends a signal on every update.
    Stores a list of node ids only."""

    list_updated = Signal()

    def __init__(self):
        super().__init__()
        self._list = []

    def add(self, item, append: bool | None = False):
        """Append or replace an item to the list, depending on the number of items present and the keyboard modifiers used. Emit update signal"""

        # first check if this node was already present, if so, remove it.
        if item in self._list:
            self._list.remove(item)

        # single selection plus shift modifier: append to list to have two items in it
        elif append:
            self._list.append(item)

        # replace item in list
        else:
            self._list = []
            self._list.append(item)

        # emit update signal
        self.list_updated.emit()

    def flip(self):
        """Change the order of the items in the list"""
        if len(self) == 2:
            self._list = [self._list[1], self._list[0]]

    def reset(self):
        """Empty list and emit update signal"""
        self._list = []
        self.list_updated.emit()

    def __getitem__(self, index):
        return self._list[index]

    def __len__(self):
        return len(self._list)
