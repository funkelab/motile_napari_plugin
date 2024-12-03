from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd
from napari._qt.qt_resources import QColoredSVGIcon
from qtpy.QtCore import Signal
from qtpy.QtGui import QColor
from qtpy.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from motile_plugin.data_views.views_coordinator.tracks_viewer import TracksViewer

import pyqtgraph as pg
from qtpy.QtCore import Qt


class HistogramRangeSliderWidget(QWidget):
    update_rule = Signal()

    def __init__(self, df: pd.DataFrame, fill_color: QColor):
        super().__init__()

        self.data = df.dropna()
        self.fill_color = fill_color
        self.data_min = self.data.min()
        self.data_max = self.data.max()
        self.dtype = self.data.dtypes

        # Create a PlotWidget for the histogram
        self.plot_widget = pg.PlotWidget()
        self.plot_item = self.plot_widget.plotItem

        # Customize the axes
        self.plot_item.getAxis("bottom").setTicks([])
        self.plot_item.getAxis("left").setTicks([])

        # Set ViewBox limits to restrict panning and zooming
        self.plot_item.getViewBox().setMouseEnabled(x=False, y=False)
        self.plot_item.getViewBox().setLimits(
            xMin=self.data_min,
            xMax=self.data_max,  # Restrict horizontal panning
            yMin=0,  # Prevent panning below 0 (optional, for clarity)
        )

        # Create the histogram data
        hist, edges = np.histogram(self.data, bins="rice")
        bar_graph = pg.BarGraphItem(
            x=edges[:-1], height=hist, width=np.diff(edges), brush="white"
        )
        self.plot_item.addItem(bar_graph)

        # Add a movable region (range slider)
        slider_range = self.data_max - self.data_min
        if self.dtype == int:
            slider_range = int(slider_range)
        self.region = pg.LinearRegionItem(
            values=[
                self.data_min + 0.25 * slider_range,
                self.data_max - 0.25 * slider_range,
            ]
        )
        self.region.setZValue(10)  # Ensure it is on top of the bars
        self.region.sigRegionChangeFinished.connect(self.update_range_label)

        # Customize the region's appearance
        self.fill_color.setAlpha(100)
        self.region.setBrush(pg.mkBrush(self.fill_color))
        self.fill_color.setAlpha(120)
        self.region.setHoverBrush(pg.mkBrush(self.fill_color))
        self.plot_item.addItem(self.region)

        # Add QSpinBoxes to view and adjust the region range
        if self.dtype == int:
            self.min_spinbox = QSpinBox()
            self.max_spinbox = QSpinBox()
            self.min_spinbox.setValue(self.data_min + int(0.25 * slider_range))
            self.max_spinbox.setValue(self.data_max - int(0.25 * slider_range))

        else:
            self.min_spinbox = QDoubleSpinBox()
            self.max_spinbox = QDoubleSpinBox()
            self.min_spinbox.setValue(self.data_min + 0.25 * slider_range)
            self.max_spinbox.setValue(self.data_max - 0.25 * slider_range)

        self.min_spinbox.setMinimum(self.data_min)
        self.min_spinbox.setMaximum(self.data_max)
        self.max_spinbox.setMinimum(self.data_min)
        self.max_spinbox.setMaximum(self.data_max)

        self.min_spinbox.editingFinished.connect(self.update_min_value)
        self.max_spinbox.editingFinished.connect(self.update_max_value)

        min_spin_box_layout = QHBoxLayout()
        min_spin_box_layout.addWidget(QLabel("Min value"))
        min_spin_box_layout.addWidget(self.min_spinbox)
        max_spin_box_layout = QHBoxLayout()
        max_spin_box_layout.addWidget(QLabel("Max value"))
        max_spin_box_layout.addWidget(self.max_spinbox)
        spinbox_layout = QVBoxLayout()
        spinbox_layout.addLayout(min_spin_box_layout)
        spinbox_layout.addLayout(max_spin_box_layout)

        # combine layouts
        layout = QVBoxLayout()
        layout.addLayout(spinbox_layout)
        layout.addWidget(self.plot_widget)
        layout.setContentsMargins(1, 1, 1, 2)
        layout.setSpacing(0)
        self.setLayout(layout)

    def update_range_label(self):
        """Update the displayed range based on the region slider."""
        region = self.region.getRegion()

        if self.dtype == int:
            self.min_spinbox.setValue(int(region[0]))
            self.max_spinbox.setValue(int(region[1]))
        else:
            self.min_spinbox.setValue(region[0])
            self.max_spinbox.setValue(region[1])

        self.update_rule.emit()

    def update_min_value(self):
        """Update the region by the value in the min_spinbox"""

        min_value = self.min_spinbox.value()
        max_value = self.region.getRegion()[1]
        if self.dtype == int:
            min_value = int(min_value)
            max_value = int(max_value)

        self.region.setRegion([min_value, max_value])
        self.update_rule.emit()

    def update_max_value(self):
        """Update the region by the value in the max_spinbox"""

        min_value = self.region.getRegion()[0]
        max_value = self.max_spinbox.value()

        if self.dtype == int:
            min_value = int(min_value)
            max_value = int(max_value)

        self.region.setRegion([min_value, max_value])
        self.update_rule.emit()

    def update_color(self, color: QColor):
        """Update the color of the region"""

        self.fill_color = color
        self.fill_color.setAlpha(100)
        self.region.setBrush(pg.mkBrush(self.fill_color))
        self.fill_color.setAlpha(120)
        self.region.setHoverBrush(pg.mkBrush(self.fill_color))


class MultipleChoiceWidget(QWidget):
    update_rule = Signal()

    def __init__(self, dataframe, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Get the unique values from the dataframe column
        self.unique_values = dataframe.dropna().unique()

        # Create a scroll area for the checkboxes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_area.setWidget(scroll_widget)
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        # Create a checkbox for each unique value
        self.checkboxes = []
        for value in self.unique_values:
            checkbox = QCheckBox(str(value))
            checkbox.stateChanged.connect(self._update)
            self.checkboxes.append(checkbox)
            scroll_layout.addWidget(checkbox)

        # Add the scroll area to the layout
        layout = QVBoxLayout()
        layout.addWidget(scroll_area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.setLayout(layout)

    def _update(self):
        """Emit update signal"""

        self.update_rule.emit()

    def get_selected_choices(self):
        """Return the list of selected choices."""

        selected = [
            checkbox.text() for checkbox in self.checkboxes if checkbox.isChecked()
        ]
        return selected


class Rule(QWidget):
    """Widget for constructing a condition to filter by"""

    update = Signal()

    def __init__(self, df: pd.DataFrame, fill_color: tuple[int, int, int, int]):
        super().__init__()

        self.data = df
        self.fill_color = fill_color

        # assign node attributes as items to filter by
        self.items = self.data.columns
        self.item_dropdown = QComboBox()
        self.item_dropdown.addItems(self.items)
        self.item_dropdown.currentIndexChanged.connect(self._set_value_widget)

        # create a dropdown with different logical operators for combining multiple conditions
        self.logic = ["AND", "OR", "NOT", "XOR"]
        self.logic_dropdown = QComboBox()
        self.logic_dropdown.addItems(self.logic)
        self.logic_dropdown.currentIndexChanged.connect(self._update)

        # Placeholder for the dynamic value widget
        self.value_widget = QWidget()
        self.value_layout = QVBoxLayout()
        self.value_layout.addWidget(self.value_widget)

        # Create a delete button for removing the rule
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)

        # Combine widgets and assign layout
        layout = QHBoxLayout()
        menu_widget_layout = QVBoxLayout()
        menu_widget_layout.addWidget(self.item_dropdown)
        menu_widget_layout.addWidget(self.logic_dropdown)
        menu_widget_layout.addWidget(self.delete)
        layout.addLayout(menu_widget_layout)
        layout.addLayout(self.value_layout)
        layout.setContentsMargins(0, 1, 0, 0)
        layout.setSpacing(1)

        self.setLayout(layout)

    def update_color(self, color: QColor):
        """Update the color on the value_widget"""

        self.fill_color = color
        if isinstance(self.value_widget, HistogramRangeSliderWidget):
            self.value_widget.update_color(color)

    def _update(self):
        self.update.emit()

    def _set_value_widget(self):
        """Replaces self.value_widget with a new widget of the appropriate type: multiplechoice widget for categorical values, and a histogram for numerical values."""

        self.layout().removeWidget(self.value_widget)
        self.value_widget.deleteLater()

        df = self.data[self.item_dropdown.currentText()]
        if df.dtype == int or df.dtype == float:
            self.value_widget = HistogramRangeSliderWidget(df, self.fill_color)
            self.value_layout = QVBoxLayout()
            self.value_widget.setLayout(self.value_layout)

        else:
            self.value_widget = MultipleChoiceWidget(df)
            self.value_layout = QVBoxLayout()
            self.value_widget.setLayout(self.value_layout)

        # Add the new value widget to the layout
        self.value_widget.update_rule.connect(self._update)
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

        # available colors
        self.color = QComboBox()
        self.color.addItems(["red", "green", "blue", "magenta", "yellow", "orange"])
        self.color.setFixedSize(100, 20)
        self.color.currentIndexChanged.connect(self._update_filter)
        self.current_color = "red"

        # adding, removing, updating rules
        add_button = QPushButton("+")
        add_button.setFixedSize(20, 20)
        add_button.clicked.connect(self._add_rule)
        delete_icon = QColoredSVGIcon.from_resources("delete").colored("white")
        self.delete = QPushButton(icon=delete_icon)
        self.delete.setFixedSize(20, 20)
        self.rule_list = QListWidget()
        layout = QVBoxLayout()
        layout.setSpacing(1)

        # combine settings widgets
        settings_layout = QHBoxLayout()
        settings_layout.addWidget(add_button)
        settings_layout.addWidget(self.color)
        settings_layout.addWidget(self.delete)
        settings_layout.setAlignment(Qt.AlignLeft)
        settings_layout.setSpacing(1)
        settings_layout.setContentsMargins(1, 0, 1, 0)

        layout.addLayout(settings_layout)
        layout.addWidget(self.rule_list)

        self.setLayout(layout)

        # Set fixed size (keep this at the end of the init!)
        self.rule_list.setFixedHeight(200)
        self.setFixedHeight(220)

    def sizeHint(self) -> None:
        hint = super().sizeHint()
        hint.setHeight(30)
        return hint

    def _update_filter(self) -> None:
        """Send a signal to apply the filter"""

        if not self.item.isSelected():
            self.item.setSelected(True)

        # update the colors if necessary
        if self.color.currentText() != self.current_color:
            for i in range(self.rule_list.count()):
                item = self.rule_list.item(i)  # Get the QListWidgetItem
                self.rule_list.itemWidget(item).update_color(
                    QColor(self.color.currentText())
                )  # Get the Rule widget
            self.current_color = self.color.currentText()

        self.filter_updated.emit()

    def _add_rule(self) -> None:
        """Create a new custom group"""

        item = QListWidgetItem(self.rule_list)
        group_row = Rule(self.tracks_viewer.track_df, QColor(self.color.currentText()))
        self.rule_list.setItemWidget(item, group_row)
        item.setSizeHint(group_row.minimumSizeHint())
        item.setBackground(QColor("#262931"))
        self.rule_list.addItem(item)
        group_row.delete.clicked.connect(partial(self._remove_rule, item))
        group_row.update.connect(self._update_filter)

    def _remove_rule(self, item: QListWidgetItem) -> None:
        """Remove a rule from the list. You must pass the list item that
        represents the rule, not the rule object itself.

        Args:
            item (QListWidgetItem): The list item to remove. This list item
                contains the Rule that represents a set of node_ids.
        """
        row = self.rule_list.indexFromItem(item).row()
        self.rule_list.takeItem(row)
        self._update_filter()


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
            self.tracks_viewer.filtered_nodes = []

        else:
            mask = pd.Series(True, index=self.tracks_viewer.track_df.index)

            def apply_logic(existing_mask, new_condition, logic):
                if logic == "AND":
                    return existing_mask & new_condition
                elif logic == "OR":
                    return existing_mask | new_condition
                elif logic == "NOT":
                    return existing_mask & ~new_condition
                elif logic == "XOR":
                    return existing_mask ^ new_condition
                else:
                    raise ValueError(f"Unknown logic operator: {logic}")

            for i in range(self.selected_filter.rule_list.count()):
                item = self.selected_filter.rule_list.item(i)  # Get the QListWidgetItem
                rule = self.selected_filter.rule_list.itemWidget(
                    item
                )  # Get the Rule widget

                column_name = rule.item_dropdown.currentText()
                logic = rule.logic_dropdown.currentText()
                column_data = self.tracks_viewer.track_df[column_name]

                if column_data.dtype == int or column_data.dtype == float:
                    # Filtering based on numerical values
                    min_val, max_val = rule.value_widget.region.getRegion()
                    new_condition = column_data.between(min_val, max_val)
                else:
                    # Categorical filtering based on selected choices
                    selected_choices = rule.value_widget.get_selected_choices()
                    new_condition = column_data.isin(selected_choices)

                # Apply the condition to the mask with the specified logic
                mask = apply_logic(mask, new_condition, logic)

            self.tracks_viewer.filtered_nodes = self.tracks_viewer.track_df[mask][
                "node_id"
            ].tolist()
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
