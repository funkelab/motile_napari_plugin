import os

import pandas as pd
import tifffile
import zarr
from psygnal import Signal
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .load_tracks import tracks_from_df


class ChoiceMenu(QWidget):
    """Menu to choose tracks name, data dimensions, scaling, and optional segmentation"""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        # Name of the tracks
        name_layout = QVBoxLayout()
        name_box = QGroupBox("Tracks Name")
        self.name_widget = QLineEdit("External Tracks from CSV")
        name_layout.addWidget(self.name_widget)
        name_box.setLayout(name_layout)
        name_box.setMaximumHeight(100)
        layout.addWidget(name_box)

        # Dimensions of the tracks
        dimensions_layout = QVBoxLayout()
        dimension_box = QGroupBox("Data Dimensions")
        data_button_group = QButtonGroup()
        button_layout = QHBoxLayout()
        self.radio_2D = QRadioButton("2D + time")
        self.radio_2D.setChecked(True)
        self.radio_3D = QRadioButton("3D + time")
        data_button_group.addButton(self.radio_2D)
        data_button_group.addButton(self.radio_3D)
        button_layout.addWidget(self.radio_2D)
        button_layout.addWidget(self.radio_3D)
        dimensions_layout.addLayout(button_layout)
        dimension_box.setLayout(dimensions_layout)
        dimension_box.setMaximumHeight(80)
        layout.addWidget(dimension_box)

        # Scale information
        scale_layout = QVBoxLayout()
        scale_box = QGroupBox("Spatial Calibration")
        self.scale_checkbox = QCheckBox("My data uses scaled units")
        scale_layout.addWidget(self.scale_checkbox)
        scale_box.setLayout(scale_layout)
        scale_box.setMaximumHeight(80)
        layout.addWidget(scale_box)

        # Whether or not a segmentation file exists
        segmentation_layout = QVBoxLayout()
        segmentation_box = QGroupBox("Segmentation Image")
        self.segmentation_checkbox = QCheckBox("I have a segmentation image")
        segmentation_layout.addWidget(self.segmentation_checkbox)
        segmentation_box.setLayout(segmentation_layout)
        segmentation_box.setMaximumHeight(80)
        layout.addWidget(segmentation_box)

        layout.setContentsMargins(0, 3, 0, 0)
        self.setLayout(layout)
        self.setMinimumHeight(400)


class CSVFieldMapWidget(QWidget):
    """QWidget accepting a CSV file and displaying the different column names in QComboBoxes"""

    def __init__(self, csv_columns: list[str], seg: bool = False, incl_z: bool = False):
        super().__init__()

        self.standard_fields = [
            "time",
            "y",
            "x",
            "id",
            "parent_id",
        ]

        if incl_z:
            self.standard_fields.insert(1, "z")
        if seg:
            self.standard_fields.insert(-2, "seg_id")

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

    def _set_view(self, csv_columns: list[str], seg: bool = False) -> None:
        """Create the layout for mapping csv columns to track features"""

        self.mapping_widgets = {}
        self.mapping_layout = QFormLayout()

        self.csv_columns = csv_columns
        self.seg = seg

        # QComboBox dictionary from feature name to csv column
        initial_mapping = self._get_initial_mapping()
        for attribute, csv_column in initial_mapping.items():
            combo = QComboBox(self)
            combo.addItems(self.csv_columns)
            combo.setCurrentText(csv_column)
            label: QLabel | QLineEdit = (
                QLabel(attribute)
                if attribute in self.standard_fields
                else QLineEdit(text=attribute)
            )
            self.mapping_widgets[label] = combo
            self.mapping_layout.addRow(label, combo)

    def _get_initial_mapping(self) -> dict[str, str]:
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
            label.text(): combo.currentText()
            for label, combo in self.mapping_widgets.items()
        }


class DataWidget(QWidget):
    """QWidget for selecting CSV file and optional segmentation image"""

    csv_loaded = Signal()

    def __init__(self, add_segmentation: bool = False, incl_z: bool = False):
        super().__init__()

        self.add_segmentation = add_segmentation
        self.incl_z = incl_z
        self.df = None

        self.layout = QVBoxLayout(self)

        # QlineEdit for CSV file path and browse button
        self.csv_path_line = QLineEdit(self)
        self.csv_path_line.setFocusPolicy(Qt.StrongFocus)
        self.csv_path_line.editingFinished.connect(
            lambda: self._load_csv(self.csv_path_line.text())
        )
        self.csv_path_line.returnPressed.connect(
            lambda: self._load_csv(self.csv_path_line.text())
        )
        self.csv_browse_button = QPushButton("Browse Tracks CSV file", self)
        self.csv_browse_button.setAutoDefault(0)
        self.csv_browse_button.clicked.connect(self._browse_csv)

        csv_layout = QHBoxLayout()
        csv_layout.addWidget(QLabel("CSV File Path:"))
        csv_layout.addWidget(self.csv_path_line)
        csv_layout.addWidget(self.csv_browse_button)

        self.layout.addLayout(csv_layout)

        # Optional QlineEdit for segmentation image path and browse button
        if self.add_segmentation:
            self.image_path_line = QLineEdit(self)
            self.image_browse_button = QPushButton("Browse Segmentation", self)
            self.image_browse_button.setAutoDefault(0)
            self.image_browse_button.clicked.connect(self._browse_segmentation)

            image_layout = QHBoxLayout()
            image_layout.addWidget(QLabel("Segmentation File Path:"))
            image_layout.addWidget(self.image_path_line)
            image_layout.addWidget(self.image_browse_button)
            self.layout.addLayout(image_layout)

        # Initialize the CSVFieldMapWidget as None
        self.csv_field_widget: CSVFieldMapWidget | None = None

    def _browse_csv(self) -> None:
        """Open File dialog to select CSV file"""

        csv_file, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )
        if csv_file:
            self._load_csv(csv_file)
        else:
            QMessageBox.warning(self, "Input Required", "Please select a CSV file.")

    def _load_csv(self, csv_file: str) -> None:
        """Load the csv file and display the CSVFieldMapWidget"""

        if csv_file == "":
            self.df = None
            return
        if not os.path.exists(csv_file):
            QMessageBox.critical(self, "Error", "The specified file was not found.")
            self.df = None
            return

        self.csv_path_line.setText(csv_file)

        # Ensure CSV path is valid
        try:
            self.df = pd.read_csv(csv_file)
            if self.csv_field_widget is not None:
                self.layout.removeWidget(self.csv_field_widget)
            self.csv_field_widget = CSVFieldMapWidget(
                list(self.df.columns), seg=self.add_segmentation, incl_z=self.incl_z
            )
            self.layout.addWidget(self.csv_field_widget)
            self.csv_loaded.emit()

        except pd.errors.EmptyDataError:
            QMessageBox.critical(self, "Error", "The file is empty or has no data.")
            self.df = None
            return
        except pd.errors.ParserError:
            self.df = None
            QMessageBox.critical(
                self, "Error", "The file could not be parsed as a valid CSV."
            )
            return

    def _browse_segmentation(self) -> None:
        """File dialog to select image file (tif, tiff, or zarr)"""

        image_file, _ = QFileDialog.getOpenFileName(
            self,
            "Select Segmentation File",
            "",
            "Segmentation Files (*.tiff *.zarr *.tif)",
        )
        if image_file:
            self.image_path_line.setText(image_file)

    def _load_segmentation(self) -> None:
        """Load the segmentation image file"""

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


class ScaleWidget(QWidget):
    """QWidget for specifying pixel calibration"""

    def __init__(self, incl_z=True):
        super().__init__()

        self.incl_z = incl_z

        layout = QVBoxLayout()

        # Spinboxes for scaling in x, y, and z (optional)
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
        """Return a QDoubleSpinBox for scaling values"""

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


class ImportTracksDialog(QDialog):
    """Multipage dialog for importing external tracks from a CSV file"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Import external tracks from CSV")

        self.csv = None
        self.segmentation = None

        self.layout = QVBoxLayout(self)
        self.stacked_widget = QStackedWidget()
        self.layout.addWidget(self.stacked_widget)

        # navigation buttons
        self.button_layout = QHBoxLayout()
        self.previous_button = QPushButton("Previous")
        self.next_button = QPushButton("Next")
        self.finish_button = QPushButton("Finish")
        self.button_layout.addWidget(self.previous_button)
        self.button_layout.addWidget(self.next_button)
        self.button_layout.addWidget(self.finish_button)
        self.layout.addLayout(self.button_layout)

        # Connect button signals
        self.previous_button.clicked.connect(self._go_to_previous_page)
        self.next_button.clicked.connect(self._go_to_next_page)
        self.finish_button.clicked.connect(self._finish)

        # Page 1 for user choices
        self.page1 = QWidget()
        page1_layout = QVBoxLayout()
        self.menu_widget = ChoiceMenu()
        page1_layout.addWidget(self.menu_widget)
        self.page1.setLayout(page1_layout)
        self.stacked_widget.addWidget(self.page1)

        # Connect signals for updating pages
        self.menu_widget.scale_checkbox.stateChanged.connect(self._update_pages)
        self.menu_widget.segmentation_checkbox.stateChanged.connect(self._update_pages)
        self.menu_widget.radio_2D.clicked.connect(self._update_pages)
        self.menu_widget.radio_3D.clicked.connect(self._update_pages)

        # Page 2 for data selection
        self.data_widget = DataWidget(
            add_segmentation=self.menu_widget.segmentation_checkbox.isChecked()
        )
        self.data_widget.csv_loaded.connect(self._update_buttons)
        self.stacked_widget.addWidget(self.data_widget)

        # Optional Page 3 with scaling is None until specified otherwise
        self.scale_page = None

        self._update_buttons()

    def _update_pages(self) -> None:
        """Recreate page2 and page3 when the user changes the options in the menu"""

        self.stacked_widget.removeWidget(self.data_widget)
        if self.scale_page is not None:
            self.stacked_widget.removeWidget(self.scale_page)

        self.data_widget = DataWidget(
            add_segmentation=self.menu_widget.segmentation_checkbox.isChecked(),
            incl_z=self.menu_widget.radio_3D.isChecked(),
        )
        self.data_widget.csv_loaded.connect(self._update_buttons)

        self.stacked_widget.addWidget(self.data_widget)

        if self.menu_widget.scale_checkbox.isChecked():
            self.scale_page = ScaleWidget(self.menu_widget.radio_3D.isChecked())
            self.stacked_widget.addWidget(self.scale_page)

        self.stacked_widget.hide()
        self.stacked_widget.show()

    def _go_to_previous_page(self) -> None:
        """Go to the previous page."""

        current_index = self.stacked_widget.currentIndex()
        if current_index > 0:
            self.stacked_widget.setCurrentIndex(current_index - 1)
        self._update_buttons()

    def _go_to_next_page(self) -> None:
        """Go to the next page."""

        current_index = self.stacked_widget.currentIndex()
        if current_index < self.stacked_widget.count() - 1:
            self.stacked_widget.setCurrentIndex(current_index + 1)
        self._update_buttons()

    def _update_buttons(self) -> None:
        """Enable or disable buttons based on the current page."""

        current_index = self.stacked_widget.currentIndex()
        if current_index + 1 == self.stacked_widget.count():
            self.next_button.hide()
            self.finish_button.show()
        else:
            self.next_button.show()
            self.finish_button.hide()
        self.previous_button.setEnabled(current_index > 0)
        self.next_button.setEnabled(current_index < self.stacked_widget.count() - 1)
        self.finish_button.setAutoDefault(0)

        # Do not allow to finish if no CSV file is loaded
        if self.data_widget.df is None or (
            self.menu_widget.segmentation_checkbox.isChecked()
            and self.data_widget.image_path_line.text() == ""
        ):
            self.finish_button.setEnabled(False)
        else:
            self.finish_button.setEnabled(True)

        self.next_button.setAutoDefault(0)
        self.previous_button.setAutoDefault(0)

    def _finish(self):
        """Tries to read the CSV file and optional segmentation image,
        and apply the attribute to column mapping to construct a Tracks object"""

        # Retrieve selected columns for each required field, and optional columns for additional attributes
        name_map = self.data_widget.csv_field_widget.get_name_map()

        # note: this will fail if one column is used for two features
        name_map_reversed = {value: key for key, value in name_map.items()}
        self.data_widget.df.rename(columns=name_map_reversed, inplace=True)

        # Read scaling information from the spinboxes
        if self.scale_page is not None:
            scale = self.scale_page.get_scale()
        else:
            scale = [1, 1, 1] if self.data_widget.incl_z is False else [1, 1, 1, 1]

        # Try to create a Tracks object with the provided CSV file, the attr:column dictionaries, and the scaling information
        self.name = self.menu_widget.name_widget.text()

        if self.data_widget.add_segmentation:
            self.data_widget._load_segmentation()
        else:
            self.data_widget.segmentation = None

        try:
            self.tracks = tracks_from_df(
                self.data_widget.df, self.data_widget.segmentation, scale
            )

        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
            return
        self.accept()
