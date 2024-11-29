import os

import pandas as pd
import tifffile
import zarr
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .load_tracks import tracks_from_csv


class ScaleWidget(QWidget):
    """QWidget for specifying pixel calibration"""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Specify scaling"))
        scale_form_layout = QFormLayout()
        self.z_spin_box = QDoubleSpinBox()
        self.z_spin_box.setValue(1.0)
        self.z_spin_box.setSingleStep(0.1)
        self.z_spin_box.setMinimum(0)
        self.z_spin_box.setDecimals(3)
        self.y_spin_box = QDoubleSpinBox()
        self.y_spin_box.setValue(1.0)
        self.y_spin_box.setSingleStep(0.1)
        self.y_spin_box.setMinimum(0)
        self.y_spin_box.setDecimals(3)
        self.x_spin_box = QDoubleSpinBox()
        self.x_spin_box.setMinimum(0)
        self.x_spin_box.setValue(1.0)
        self.x_spin_box.setSingleStep(0.1)
        self.x_spin_box.setDecimals(3)

        scale_form_layout.addRow(QLabel("z"), self.z_spin_box)
        scale_form_layout.addRow(QLabel("y"), self.y_spin_box)
        scale_form_layout.addRow(QLabel("x"), self.x_spin_box)

        layout.addLayout(scale_form_layout)
        layout.setAlignment(Qt.AlignTop)

        self.setLayout(layout)

    def get_scale(self) -> list[float]:
        """Return the scaling values in the spinboxes as a list of floats"""

        scale = [
            self.z_spin_box.value(),
            self.y_spin_box.value(),
            self.x_spin_box.value(),
        ]

        return scale


class CSVFieldMapWidget(QWidget):
    """QWidget accepting a CSV file and displaying the different column names in QComboBoxes"""

    def __init__(self):
        super().__init__()

        self.csv_headers = []  # to be populated with column names from csv
        self.extra_columns = []  # to be populated later with optional additional attributes

        # Field Mapping Layout
        csv_column_layout = QVBoxLayout()
        csv_column_layout.addWidget(QLabel("Choose columns from CSV"))
        self.mapping_layout = QFormLayout()
        self.mapping_widgets = {}  # To store QComboBox widgets for each field

        # Fields to map key:display name
        self.fields_to_map = {
            "t": "time",
            "z": "z (optional)",
            "y": "y",
            "x": "x",
            "id": "id",
            "seg_id": "seg_id (if seg provided)",
            "parent_id": "parent_id",
        }

        # populate the for with display name: QComboBox
        for key, field in self.fields_to_map.items():
            combo = QComboBox(self)
            combo.addItem("Select Column")
            self.mapping_widgets[key] = combo
            self.mapping_layout.addRow(QLabel(f"{field}:"), combo)

        # Button to add custom attribute mappings
        self.add_attr_button = QPushButton("Add Attribute", self)
        self.add_attr_button.clicked.connect(self._add_custom_attribute)

        # Assemble layouts
        csv_column_layout.addLayout(self.mapping_layout)
        csv_column_layout.addWidget(self.add_attr_button)
        layout = QVBoxLayout()
        layout.addLayout(csv_column_layout)
        self.setLayout(layout)

    def load_csv_headers(self, csv_file: str) -> None:
        """Tries to read the csv file and if successful, updates Comboboxes with the header names"""

        if csv_file != "":
            if not csv_file.endswith(".csv"):
                QMessageBox.warning(self, "Input Required", "Please select a CSV file.")
                return

            # Load only the header of the CSV file
            try:
                df = pd.read_csv(csv_file, nrows=0)
                self.csv_headers = list(df.columns)

                # Populate dropdowns with CSV headers
                for _, combo in self.mapping_widgets.items():
                    combo.clear()
                    combo.addItem("Select Column")
                    combo.addItems(self.csv_headers)

                # Update custom attribute dropdowns, if any
                self._update_custom_attributes()

                # If there are any 1:1 field mappings possible, suggest these to make it easier for the user
                self._preset_columns()

            except FileNotFoundError:
                QMessageBox.critical(self, "Error", "The specified file was not found.")
            except pd.errors.EmptyDataError:
                QMessageBox.critical(self, "Error", "The file is empty or has no data.")
            except pd.errors.ParserError:
                QMessageBox.critical(
                    self, "Error", "The file could not be parsed as a valid CSV."
                )

    def _preset_columns(self):
        """Preset choices in QComboBoxes if there is 1:1 match between field key and csv column name"""

        for key in self.fields_to_map:
            if key in self.csv_headers:
                self.mapping_widgets[key].setCurrentText(key)

    def _add_custom_attribute(self):
        """Add a custom attribute field mapping with a dropdown"""

        custom_attr_label = QLineEdit(
            f"Custom Attribute {len(self.mapping_layout.children()) // 2 + 1}:"
        )
        custom_attr_combo = QComboBox(self)
        custom_attr_combo.addItem("Select Column")
        custom_attr_combo.addItems(self.csv_headers)
        current_index = len(self.fields_to_map.keys()) + len(self.extra_columns)
        custom_attr_combo.currentIndexChanged.connect(
            lambda: self._update_custom_field_name(
                current_index, custom_attr_combo.currentText()
            )
        )

        self.extra_columns.append(custom_attr_label)
        self.mapping_widgets[custom_attr_label] = custom_attr_combo
        self.mapping_layout.addRow(custom_attr_label, custom_attr_combo)

    def _update_custom_field_name(self, index: int, column_name: str) -> None:
        """Update the field name with the column name"""

        self.mapping_layout.itemAt(index * 2).widget().setText(column_name)

    def _update_custom_attributes(self):
        """Update custom attribute dropdowns with new headers (if CSV headers are reloaded)"""

        for i in range(
            len(self.fields_to_map), self.mapping_layout.rowCount()
        ):  # all the items beyond the default ones
            widget_pair = self.mapping_layout.itemAt(i * 2 + 1)
            if widget_pair:
                combo = widget_pair.widget()
                if isinstance(combo, QComboBox):
                    combo.clear()
                    combo.addItem("Select Column")
                    combo.addItems(self.csv_headers)

    def get_selected_columns(self) -> tuple[dict[str:str], dict[str:str]]:
        """Return the node attribute:column mapping for the default and optional extra attributes"""

        selected_columns = {
            field: self.mapping_widgets[field].currentText()
            for field in self.fields_to_map
        }
        extra_columns = {
            field.text(): self.mapping_widgets[field].currentText()
            for field in self.extra_columns
        }

        return selected_columns, extra_columns


class ImportTracksDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Import external tracks from CSV")

        self.tracks = None
        self.name = "External Tracks"

        # Layouts
        self.layout = QVBoxLayout(self)

        # Construct widget for the column name to field mapping
        self.csv_field_widget = CSVFieldMapWidget()

        # Construct widget for the pixel scaling information
        self.scale_widget = ScaleWidget()

        # CSV File Selection
        self.csv_path_line = QLineEdit(self)
        self.csv_path_line.editingFinished.connect(
            lambda: self.csv_field_widget.load_csv_headers(self.csv_path_line.text())
        )
        self.csv_browse_button = QPushButton("Browse Tracks CSV file", self)
        self.csv_browse_button.clicked.connect(self._browse_csv)

        csv_layout = QHBoxLayout()
        csv_layout.addWidget(QLabel("CSV File Path:"))
        csv_layout.addWidget(self.csv_path_line)
        csv_layout.addWidget(self.csv_browse_button)

        # Image File Selection
        self.image_path_line = QLineEdit(self)
        self.image_browse_button = QPushButton("Browse Segmentation", self)
        self.image_browse_button.clicked.connect(self._browse_image)

        image_layout = QHBoxLayout()
        image_layout.addWidget(QLabel("Image File Path:"))
        image_layout.addWidget(self.image_path_line)
        image_layout.addWidget(self.image_browse_button)

        # Name the tracks
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Choose a name"))
        self.name_widget = QLineEdit(self.name)
        name_layout.addWidget(self.name_widget)

        # Place scaling and field map side by side
        scaling_field_layout = QHBoxLayout()
        scaling_field_layout.addWidget(self.csv_field_widget)
        scaling_field_layout.addWidget(self.scale_widget)
        scaling_field_layout.setAlignment(Qt.AlignTop)

        # OK and Cancel buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._ok_clicked)
        self.button_box.rejected.connect(self.reject)

        # Add widgets to main layout
        self.layout.addLayout(csv_layout)
        self.layout.addLayout(image_layout)
        self.layout.addLayout(name_layout)
        self.layout.addLayout(scaling_field_layout)
        self.layout.addWidget(self.button_box)

    def _browse_csv(self):
        """Open File dialog to select CSV file"""

        csv_file, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if csv_file:
            self.csv_path_line.setText(csv_file)
            self.csv_field_widget.load_csv_headers(csv_file)

    def _browse_image(self):
        """File dialog to select image file (TIFF or Zarr)"""

        image_file, _ = QFileDialog.getOpenFileName(
            self, "Select Image File", "", "Image Files (*.tiff *.zarr)"
        )
        if image_file:
            self.image_path_line.setText(image_file)

    def _ok_clicked(self):
        """Tries to read the CSV file and optional segmentation image, and apply the attribute to column mapping to construct a Tracks object"""

        # Ensure CSV path is provided and valid
        csv_file = self.csv_path_line.text()
        if not csv_file:
            QMessageBox.warning(self, "Input Required", "Please select a CSV file.")
            return

        try:
            pd.read_csv(csv_file, nrows=0)
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "The specified file was not found.")
            return
        except pd.errors.EmptyDataError:
            QMessageBox.critical(self, "Error", "The file is empty or has no data.")
            return
        except pd.errors.ParserError:
            QMessageBox.critical(
                self, "Error", "The file could not be parsed as a valid CSV."
            )
            return

        # Check if a valid path to a segmentation image file is provided and if so load it
        if os.path.exists(self.image_path_line.text()):
            if self.image_path_line.text().endswith(".tif"):
                segmentation = tifffile.imread(
                    self.image_path_line.text()
                )  # Assuming no segmentation is needed at this step
            elif ".zarr" in self.image_path_line.text():
                segmentation = zarr.open(self.image_path_line.text())
            else:
                QMessageBox.warning(
                    self,
                    "Invalid file type",
                    "Please provide a tiff or zarr file for the segmentation image stack",
                )
                return
        else:
            segmentation = None

        # Retrieve selected columns for each required field, and optional columns for additional attributes
        selected_columns, extra_columns = self.csv_field_widget.get_selected_columns()

        # Ensure all required fields have been selected
        for field, column in selected_columns.items():
            if column == "Select Column" and field in (
                "t",
                "y",
                "x",
                "id",
                "parent_id",
            ):
                QMessageBox.warning(
                    self, "Input Required", f"Please select a column for {field}."
                )
                return
        if segmentation is not None and selected_columns["seg_id"] == "Select Column":
            QMessageBox.warning(
                self,
                "Input Required",
                "Please select a column for 'seg_id' to map object ID to segmentation ID (label) if you want to provide a segmentation image with the tracks.",
            )
            return

        # Read scaling information from the spinboxes, and name from the name_widget
        scale = self.scale_widget.get_scale()
        self.name = self.name_widget.text()

        # Try to create a Tracks object with the provided CSV file, the attr:column dictionaries, and the scaling information
        try:
            self.tracks = tracks_from_csv(
                csv_file, selected_columns, extra_columns, segmentation, scale
            )
        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
            return
        self.accept()
