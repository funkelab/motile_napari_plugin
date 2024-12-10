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

from .load_tracks import tracks_from_df
from motile_toolbox.candidate_graph import NodeAttr


class ScaleWidget(QWidget):
    """QWidget for specifying pixel calibration"""

    def __init__(self, incl_z=True):
        super().__init__()
        self.incl_z = incl_z

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Specify scaling"))
        scale_form_layout = QFormLayout()
        self.z_spin_box = self._scale_spin_box()
        self.y_spin_box = self._scale_spin_box()
        self.x_spin_box = self._scale_spin_box()

        if self.incl_z:
            scale_form_layout.addRow(QLabel("z"), self.z_spin_box)
        scale_form_layout.addRow(QLabel("y"), self.y_spin_box)
        scale_form_layout.addRow(QLabel("x"), self.x_spin_box)

        layout.addLayout(scale_form_layout)
        layout.setAlignment(Qt.AlignTop)

        self.setLayout(layout)

    def _scale_spin_box(self) -> QDoubleSpinBox:
        spin_box = QDoubleSpinBox()
        spin_box.setValue(1.0)
        spin_box.setSingleStep(0.1)
        spin_box.setMinimum(0)
        spin_box.setDecimals(3)
        return spin_box

    def get_scale(self) -> list[float]:
        """Return the scaling values in the spinboxes as a list of floats.
        Since we currently require a dummy 1 value for the time dimension, add it here."""
        if self.incl_z:
            scale = [
                1,
                self.z_spin_box.value(),
                self.y_spin_box.value(),
                self.x_spin_box.value(),
            ]
        else:
            scale = [
                1,
                self.y_spin_box.value(),
                self.x_spin_box.value(),
            ]

        return scale


class CSVFieldMapWidget(QWidget):
    """QWidget accepting a CSV file and displaying the different column names in QComboBoxes"""

    def __init__(self, csv_columns: list[str], seg=False):
        super().__init__()

        self.standard_fields = [
            "t",
            "z",
            "y",
            "x",
            "id",
            "seg_id",
            "parent_id",
        ]
        csv_column_layout = QVBoxLayout()
        csv_column_layout.addWidget(QLabel("Choose columns from CSV"))
        # Field Mapping Layout
        self.mapping_layout = QFormLayout()
        self.mapping_widgets: dict[QLabel | QLineEdit, QComboBox] = {}

        self._set_view(csv_columns, seg=seg)

        # Assemble layouts
        csv_column_layout.addLayout(self.mapping_layout)
        layout = QVBoxLayout()
        layout.addLayout(csv_column_layout)
        self.setLayout(layout)

    def _set_view(self, csv_columns, seg=False):
        self.mapping_widgets = {}
        self.mapping_layout = QFormLayout()

        self.csv_columns = csv_columns
        self.seg = seg

        # populate the for with display name: QComboBox# dictionary from feature name to csv column
        initial_mapping = self._get_initial_mapping()
        for attribute, csv_column in initial_mapping.items():
            combo = QComboBox(self)
            combo.addItems(self.csv_columns)
            combo.setCurrentText(csv_column)
            label : QLabel | QLineEdit = QLabel(attribute) if attribute in self.standard_fields else QLineEdit(text=attribute)
            self.mapping_widgets[label] = combo
            self.mapping_layout.addRow(label, combo)

    def _get_initial_mapping(self):
        """Make an initial guess for mapping of csv columns to fields"""
        mapping = {}
        columns_left: list = self.csv_columns.copy()
        # find exact matches for standard fields
        for attribute in self.standard_fields:
            if attribute in columns_left:
                mapping[attribute] = attribute
                columns_left.remove(attribute)
        # assign first remaining column as best guess for remaining standard fields
        for attribute in self.standard_fields:
            if attribute in mapping:
                continue
            mapping[attribute] = columns_left.pop(0)
        # make new features for any remaining columns
        for column in columns_left:
            mapping[column] = column
        return mapping

    def get_name_map(self) -> dict[str, str]:
        """Return a mapping from feature name to csv field name"""

        return {
            label.text: combo.currentText()
            for label, combo in self.mapping_widgets.items()
        }

class ImportTracksDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Import external tracks from CSV")

        self.tracks = None
        self.name = "External Tracks from CSV"
        self.df: pd.DataFrame | None = None

        # Layouts
        self.layout = QVBoxLayout(self)

        # Construct widget for the column name to field mapping
        self.csv_field_widget: CSVFieldMapWidget | None = None

        # Construct widget for the pixel scaling information
        self.scale_widget = ScaleWidget()

        # CSV File Selection
        self.csv_path_line = QLineEdit(self)
        self.csv_path_line.editingFinished.connect(
            lambda: self._load_csv(self.csv_path_line.text())
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
        image_layout.addWidget(QLabel("Segmentation File Path:"))
        image_layout.addWidget(self.image_path_line)
        image_layout.addWidget(self.image_browse_button)

        # Name the tracks
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Choose a name"))
        self.name_widget = QLineEdit(self.name)
        name_layout.addWidget(self.name_widget)

        # Place scaling and field map side by side
        scaling_field_layout = QHBoxLayout()
        # scaling_field_layout.addWidget(self.csv_field_widget)
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
            self._load_csv(csv_file)
        else:
            QMessageBox.warning(self, "Input Required", "Please select a CSV file.")

    def _load_csv(self, csv_file):
        self.csv_path_line.setText(csv_file)
        # Ensure CSV path is provided and valid
        try:
            self.df = pd.read_csv(csv_file, nrows=0)
            self.csv_field_widget = CSVFieldMapWidget(list(self.df.columns), False)
            self.layout.addWidget(self.csv_field_widget)
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

    def _browse_image(self):
        """File dialog to select image file (TIFF or Zarr)"""

        image_file, _ = QFileDialog.getOpenFileName(
            self, "Select Segmentation File", "", "Segmentation Files (*.tiff *.zarr)"
        )
        if image_file:
            self.image_path_line.setText(image_file)

    def _load_segmentation(self, segmentation_file):
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
        self.segmentation = segmentation

    def _ok_clicked(self):
        """Tries to read the CSV file and optional segmentation image, 
        and apply the attribute to column mapping to construct a Tracks object"""


        # Retrieve selected columns for each required field, and optional columns for additional attributes
        name_map = self.csv_field_widget.get_name_map()
        # note: this will fail if one column is used for two features
        name_map_reversed = {
            value: key for key, value in name_map.items()  
        }
        self.df.rename(columns=name_map_reversed, inplace=True)

        # Read scaling information from the spinboxes, and name from the name_widget
        scale = self.scale_widget.get_scale()
        self.name = self.name_widget.text()

        # Try to create a Tracks object with the provided CSV file, the attr:column dictionaries, and the scaling information
        try:
            self.tracks = tracks_from_df(
                self.df, self.segmentation, scale
            )

        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
            return
        self.accept()
