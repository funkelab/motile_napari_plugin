from __future__ import annotations

from psygnal import Signal
from PyQt5.QtCore import QObject


class Collection(QObject):
    """A collection of nodes that sends a signal on every update.
    Stores a list of node ids only."""

    list_updated = Signal()

    def __init__(self):
        super().__init__()
        self._list = []

    def add(self, items: list, append: bool | None = True):
        """Add nodes from a list and emit a single signal"""

        if append:
            for item in items:
                if item in self._list:
                    continue
                else:
                    self._list.append(item)

        else:
            self._list = items

        self.list_updated.emit()

    def remove(self, items: list):
        """Remove nodes from a list and emit a single signal"""

        self._list = [item for item in self._list if item not in items]

        self.list_updated.emit()

    def reset(self):
        """Empty list and emit update signal"""
        self._list = []
        self.list_updated.emit()

    def __getitem__(self, index):
        return self._list[index]

    def __len__(self):
        return len(self._list)
