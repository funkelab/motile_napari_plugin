from typing import Tuple

import pyqtgraph as pg
from PyQt5.QtCore import QObject, Qt, pyqtSignal

from .tree_widget_utils import normalize_modifiers


class NodeSelectionList(QObject):
    """Updates the current selection (0, 1, or 2) of nodes. Sends a signal on every update."""

    list_updated = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._list = []

    def append(
        self, item, modifiers: Qt.KeyboardModifiers | Tuple | None = None
    ):
        """Append or replace an item to the list, depending on the number of items present and the keyboard modifiers used. Emit update signal"""

        if len(self) == 2:
            self._list = []

        if isinstance(modifiers, tuple):
            modifiers = normalize_modifiers(modifiers)

        # single selection plus shift modifier: append to list to have two items in it
        if modifiers == pg.QtCore.Qt.ShiftModifier and len(self) == 1:
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
