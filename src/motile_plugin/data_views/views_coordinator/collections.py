from __future__ import annotations

from PyQt5.QtCore import QObject


class Collection(QObject):
    """A collection of node ids belonging to a group"""

    def __init__(self):
        super().__init__()
        self._list = []

    def add(self, items: list, append: bool | None = True):
        """Add nodes from a list"""

        if append:
            for item in items:
                if item in self._list:
                    continue
                else:
                    self._list.append(item)

        else:
            self._list = items

    def remove(self, items: list):
        """Remove nodes from a list"""

        self._list = [item for item in self._list if item not in items]

    def reset(self):
        """Empty list"""
        self._list = []

    def __getitem__(self, index):
        return self._list[index]

    def __len__(self):
        return len(self._list)
