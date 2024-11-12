from __future__ import annotations

import operator
from functools import partial
from typing import TYPE_CHECKING

import networkx as nx
import numpy as np
from napari._qt.qt_resources import QColoredSVGIcon
from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer


class Rule(QWidget):
    """Widget for constructing a condition to filter by"""

    def __init__(self, graph: nx.diGraph):
        super().__init__()

        self.graph = graph

        # assign node attributes as items to filter by
        self.items = set()
        for _, attrs in self.graph.nodes(data=True):
            self.items.update(attrs.keys())
        if (
            "pos" in self.items
        ):  # not using position information right now, consider splitting in x, y, (z) coordinates for filtering?
            self.items.remove("pos")

        self.item_dropdown = QComboBox()
        self.item_dropdown.addItems(self.items)
        self.item_dropdown.currentIndexChanged.connect(self._set_sign_value_widget)

        # create a dropdown with signs for comparisons
        self.signs = ["<", "<=", ">", ">=", "=", "\u2260"]
        self.sign_dropdown = QComboBox()
        self.sign_dropdown.addItems(self.signs)

        # create a dropdown with different logical operators for combining multiple conditions
        self.logic = ["AND", "OR", "NOT", "XOR"]
        self.logic_dropdown = QComboBox()
        self.logic_dropdown.addItems(self.logic)

        # Placeholder for the dynamic value widget
        self.value_widget = QWidget()
        self.value_layout = QVBoxLayout()
        self.value_widget.setLayout(self.value_layout)

        # Create a delete button for removing the rule
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)

        # Combine widgets and assign layout
        layout = QHBoxLayout()
        layout.addWidget(self.delete)
        layout.addWidget(self.item_dropdown)
        layout.addWidget(self.sign_dropdown)
        layout.addWidget(self.logic_dropdown)
        layout.addWidget(self.value_widget)
        self.setLayout(layout)

        # Initialize value widget
        self._set_sign_value_widget()

    def _set_sign_value_widget(self) -> None:
        """Replaces self.value_widget with a new widget of the appropriate type: combobox for string types, spinboxes for numerical values, QLineEdit for values in tuples or lists.
        Also assigns the correct signs to self.sign_dropdown, as >, >=, <=, and < cannot be used for string comparisons.
        """

        # Remove the existing value widget from the layout
        self.layout().removeWidget(self.value_widget)
        self.value_widget.deleteLater()

        # Get the selected item (attribute name)
        selected_item = self.item_dropdown.currentText()

        # Determine the attribute type by checking the nodes
        attr_type = None
        for _, attrs in self.graph.nodes(data=True):
            if selected_item in attrs:
                attr_type = type(attrs[selected_item])
                break

        # Set up the value widget based on the attribute type
        if attr_type == str:
            # Use a dropdown for string attributes
            unique_values = {
                attrs[selected_item]
                for _, attrs in self.graph.nodes(data=True)
                if selected_item in attrs and isinstance(attrs[selected_item], str)
            }
            self.value_widget = QComboBox()
            self.value_widget.addItems(unique_values)

            # update the signs, cannot use >, >=, <=, < for string comparison
            self.sign_dropdown.clear()
            signs = ["=", "\u2260"]
            self.sign_dropdown.addItems(signs)

        elif attr_type in (int, float, np.float64):
            # Use a spin box for numeric attributes (int or float)
            self.value_widget = QSpinBox() if attr_type == int else QDoubleSpinBox()
            self.value_widget.setMinimum(0)
            self.value_widget.setMaximum(100000000)

            # all signs should be allowed
            self.sign_dropdown.clear()
            self.sign_dropdown.addItems(self.signs)

        elif attr_type in (list, tuple):
            self.value_widget = QLineEdit("Type your value here")
            # update the signs, cannot use >. >=, <=, < for string comparison
            self.sign_dropdown.clear()
            signs = ["=", "\u2260"]
            self.sign_dropdown.addItems(signs)

        else:
            # Fallback if attribute type is not  a string of number
            self.value_widget = QLabel("No valid attribute type")

        # Add the new value widget to the layout
        self.layout().addWidget(self.value_widget)


class Filter(QWidget):
    """Filter widget containing a single filter, composed of multiple Rule widgets formulating conditions to filter by"""

    filter_updated = Signal()

    def __init__(self, tracks_viewer, item: QListWidgetItem):
        super().__init__()

        self.tracks_viewer = tracks_viewer
        self.item = item

        # rule list widget
        self.rule_list = QListWidget()
        self.rule_list.setSelectionMode(QAbstractItemView.NoSelection)  # no selection
        self.item.setBackground(QColor("#262931"))
        self.setStyleSheet("""
                QListWidget::item:selected {
                    background-color: #262931;
                }
        """)
        self.rule_list.setFixedHeight(200)
        self.setFixedHeight(220)

        # available colors
        self.color = QComboBox()
        self.color.addItems(["red", "green", "blue", "magenta", "yellow", "orange"])
        self.color.currentIndexChanged.connect(self._update_filter)

        # adding, removing, updating rules
        add_button = QPushButton("Add rule")
        add_button.clicked.connect(self._add_rule)
        update_button = QPushButton("Apply")
        update_button.clicked.connect(self._update_filter)
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(40, 40)
        self.rule_list = QListWidget()
        layout = QHBoxLayout()
        layout.setSpacing(1)

        # combine settings widgets
        settings_layout = QVBoxLayout()
        settings_layout.addWidget(self.color)
        settings_layout.addWidget(add_button)
        settings_layout.addWidget(update_button)
        settings_layout.addWidget(self.delete)

        layout.addWidget(self.rule_list)
        layout.addLayout(settings_layout)
        self.setLayout(layout)

    def sizeHint(self) -> None:
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint

    def _update_filter(self) -> None:
        if not self.item.isSelected():
            self.item.setSelected(True)
        self.filter_updated.emit()

    def _add_rule(self) -> None:
        """Create a new custom group"""

        item = QListWidgetItem(self.rule_list)
        group_row = Rule(self.tracks_viewer.tracks.graph)
        self.rule_list.setItemWidget(item, group_row)
        item.setSizeHint(group_row.minimumSizeHint())
        item.setBackground(QColor("#262931"))
        self.rule_list.addItem(item)
        group_row.delete.clicked.connect(partial(self._remove_rule, item))

    def _remove_rule(self, item: QListWidgetItem) -> None:
        """Remove a rule from the list. You must pass the list item that
        represents the rule, not the rule object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the Rule that represents a set of node_ids.
        """
        row = self.rule_list.indexFromItem(item).row()
        self.rule_list.takeItem(row)


class FilterWidget(QGroupBox):
    """Widget for construction filters to 'soft' select nodes that meet certain criteria. A new group can be created based on the filtered nodes. Sends a signal when a new filter is selected or when the user clicks the 'apply' button to update the filter criteria."""

    apply_filter = Signal()

    def __init__(self, tracks_viewer: TracksViewer):
        super().__init__(title="Filters")

        self.tracks_viewer = tracks_viewer

        # filter list widget
        self.filter_list = QListWidget()
        self.filter_list.setSelectionMode(1)  # single selection
        self.filter_list.itemSelectionChanged.connect(self._selection_changed)

        # edit widget
        edit_widget = QWidget()
        edit_layout = QHBoxLayout()
        self.add_filter_btn = QPushButton("Add new filter")
        self.add_filter_btn.clicked.connect(self._add_filter)
        self.clear_selection_btn = QPushButton("Deactivate filter")
        self.clear_selection_btn.clicked.connect(self.filter_list.clearSelection)
        self.create_group_btn = QPushButton("Create group")
        self.create_group_btn.clicked.connect(self._create_group)
        edit_layout.addWidget(self.clear_selection_btn)
        edit_layout.addWidget(self.create_group_btn)
        edit_layout.addWidget(self.add_filter_btn)
        edit_widget.setLayout(edit_layout)

        # combine widgets
        layout = QVBoxLayout()
        layout.addWidget(self.filter_list)
        layout.addWidget(edit_widget)
        self.setLayout(layout)

        self.update_buttons()

    def update_buttons(self) -> None:
        """Activate or deactivates the buttons depending on whether a filter is selected or can be created"""

        if self.tracks_viewer.tracks is not None:
            self.add_filter_btn.setEnabled(True)
        else:
            self.add_filter_btn.setEnabled(False)

        selected = self.filter_list.selectedItems()
        if selected:
            self.clear_selection_btn.setEnabled(True)
        else:
            self.clear_selection_btn.setEnabled(False)

        if len(self.tracks_viewer.filtered_nodes) > 0 and selected:
            self.create_group_btn.setEnabled(True)
        else:
            self.create_group_btn.setEnabled(False)

    def _selection_changed(self) -> None:
        """Check whether a filter is selected, and if so call the function to apply it"""

        selected = self.filter_list.selectedItems()
        if selected:
            self.selected_filter = self.filter_list.itemWidget(selected[0])

            color = self.selected_filter.color.currentText()
            color = QColor(color)
            color.setAlpha(150)

            self.setStyleSheet(f"""
                QListWidget::item:selected {{
                    background-color: {color.name()};
                }}
            """)

            rgb_color = color.getRgb()[:3]
            rgb_color = [c / 255 for c in rgb_color]
            self.tracks_viewer.filter_color = rgb_color
            self._filter_nodes()
        else:
            self.tracks_viewer.filtered_nodes = {}
            self.apply_filter.emit()

        self.update_buttons()

    def _filter_nodes(self) -> None:
        """Assign a filtered set of nodes to the tracks_viewer based on the criteria of the selected filter"""

        if self.selected_filter.rule_list.count() == 0:
            result_set = set()

        else:
            OP_MAP = {
                "<": operator.lt,
                "<=": operator.le,
                ">": operator.gt,
                ">=": operator.ge,
                "=": operator.eq,
                "\u2260": operator.ne,
            }

            result_set = set(self.tracks_viewer.tracks.graph.nodes)

            for i in range(self.selected_filter.rule_list.count()):
                item = self.selected_filter.rule_list.item(i)  # Get the QListWidgetItem
                rule = self.selected_filter.rule_list.itemWidget(
                    item
                )  # Get the Rule widget

                # Extract information from each rule
                item_value = rule.item_dropdown.currentText()
                sign_value = rule.sign_dropdown.currentText()
                logic_value = rule.logic_dropdown.currentText()

                if isinstance(rule.value_widget, QSpinBox | QDoubleSpinBox):
                    value = rule.value_widget.value()
                elif isinstance(rule.value_widget, QLineEdit):
                    value = rule.value_widget.text()
                else:
                    value = rule.value_widget.currentText()

                # Define a set for nodes that satisfy this rule
                current_set = set()

                # Get the correct operator function
                compare_op = OP_MAP.get(sign_value)

                # Iterate over nodes and apply the rule condition
                for node, attrs in self.tracks_viewer.tracks.graph.nodes(data=True):
                    node_attr_value = attrs.get(item_value)

                    try:
                        if (
                            type(node_attr_value) in (tuple, list)
                            or node_attr_value is None
                        ):  # not all nodes may have a value for given attribute, e.g. not all nodes may belong to a group, and therefore do not have a 'group' attribute
                            if node_attr_value is None:
                                node_attr_value = []
                            node_attr_value = [str(v) for v in node_attr_value]
                            if sign_value == "=":
                                condition = (
                                    value in node_attr_value
                                )  # we consider the condition to be true if the requested value is present in the list (even if other values are also present in the list).
                            else:
                                condition = value not in node_attr_value
                        elif isinstance(value, str):
                            condition = compare_op(str(node_attr_value), value)
                        else:
                            node_attr_value = float(node_attr_value)
                            value = float(value)
                            condition = compare_op(node_attr_value, value)

                        # If the condition is true, add the node to the current set
                        if condition:
                            current_set.add(node)
                    except (
                        ValueError,
                        TypeError,
                    ):  # If there's a type mismatch or conversion issue, skip this node
                        continue

                # Apply logic to chain the result sets
                if logic_value == "AND":
                    result_set &= current_set
                elif logic_value == "OR":
                    result_set |= current_set
                elif logic_value == "NOT":
                    result_set -= current_set
                elif logic_value == "XOR":
                    result_set ^= current_set

        self.tracks_viewer.filtered_nodes = result_set
        self.apply_filter.emit()

    def _create_group(self) -> None:
        """Add a new group collection based on the current filter"""

        name, ok_pressed = QInputDialog.getText(
            None, "Enter group name", "Please enter a group name:", text="New Group"
        )
        if ok_pressed and name:
            self.tracks_viewer.collection_widget.add_group(name, select=True)
            self.tracks_viewer.collection_widget.add_nodes(
                self.tracks_viewer.filtered_nodes
            )

    def _add_filter(self) -> None:
        """Create a new empty filter"""

        item = QListWidgetItem(self.filter_list)
        filter_row = Filter(self.tracks_viewer, item)
        filter_row.filter_updated.connect(self._selection_changed)
        self.filter_list.setItemWidget(item, filter_row)
        item.setSizeHint(filter_row.minimumSizeHint())
        self.filter_list.addItem(item)
        filter_row.delete.clicked.connect(partial(self._remove_filter, item))
        self.filter_list.setCurrentRow(len(self.filter_list) - 1)

    def _remove_filter(self, item: QListWidgetItem) -> None:
        """Remove a filter from the list. You must pass the list item that
        represents the filter, not the filter object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the CollectionButton that represents a set of node_ids.
        """
        row = self.filter_list.indexFromItem(item).row()
        self.filter_list.takeItem(row)
