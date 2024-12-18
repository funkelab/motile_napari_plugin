import os

import pandas as pd
import tifffile
import zarr
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
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

    def __init__(self, csv_columns: list[str], seg=False, incl_z=False):
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
            label: QLabel | QLineEdit = (
                QLabel(attribute)
                if attribute in self.standard_fields
                else QLineEdit(text=attribute)
            )
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
            label.text(): combo.currentText()
            for label, combo in self.mapping_widgets.items()
        }


class ChoiceMenu(QWidget):
    """Menu to choose data dimensions, scaling, and optional segmentation"""

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout()

        layout.addWidget(QLabel("My data has dimensions"))
        data_button_group = QButtonGroup()
        button_layout = QHBoxLayout()
        self.radio_2D = QRadioButton("2D + time")
        self.radio_2D.setChecked(True)
        self.radio_3D = QRadioButton("3D + time")
        data_button_group.addButton(self.radio_2D)
        data_button_group.addButton(self.radio_3D)
        button_layout.addWidget(self.radio_2D)
        button_layout.addWidget(self.radio_3D)
        layout.addLayout(button_layout)

        self.scale_checkbox = QCheckBox("My data uses scaled units")
        layout.addWidget(self.scale_checkbox)

        self.segmentation_checkbox = QCheckBox("I have a segmentation image")
        layout.addWidget(self.segmentation_checkbox)

        self.setLayout(layout)


# class ImportTracksDialog_old(QDialog):
#     def __init__(self):
#         super().__init__()
#         self.setWindowTitle("Import external tracks from CSV")

#         self.tracks = None
#         self.name = "External Tracks from CSV"
#         self.df: pd.DataFrame | None = None

#         # Layouts
#         self.layout = QVBoxLayout(self)

#         self.choice_menu = ChoiceMenu()
#         self.layout.addWidget(self.choice_menu)

#         # Construct widget for the column name to field mapping
#         self.csv_field_widget: CSVFieldMapWidget | None = None

#         # Construct widget for the pixel scaling information
#         self.scale_widget = ScaleWidget()

#         # CSV File Selection
#         self.csv_path_line = QLineEdit(self)
#         self.csv_path_line.editingFinished.connect(
#             lambda: self._load_csv(self.csv_path_line.text())
#         )
#         self.csv_browse_button = QPushButton("Browse Tracks CSV file", self)
#         self.csv_browse_button.clicked.connect(self._browse_csv)

#         csv_layout = QHBoxLayout()
#         csv_layout.addWidget(QLabel("CSV File Path:"))
#         csv_layout.addWidget(self.csv_path_line)
#         csv_layout.addWidget(self.csv_browse_button)

#         # Image File Selection
#         self.image_path_line = QLineEdit(self)
#         self.image_browse_button = QPushButton("Browse Segmentation", self)
#         self.image_browse_button.clicked.connect(self._browse_image)

#         image_layout = QHBoxLayout()
#         image_layout.addWidget(QLabel("Segmentation File Path:"))
#         image_layout.addWidget(self.image_path_line)
#         image_layout.addWidget(self.image_browse_button)

#         # Name the tracks
#         name_layout = QHBoxLayout()
#         name_layout.addWidget(QLabel("Choose a name"))
#         self.name_widget = QLineEdit(self.name)
#         name_layout.addWidget(self.name_widget)

#         # Place scaling and field map side by side
#         scaling_field_layout = QHBoxLayout()
#         # scaling_field_layout.addWidget(self.csv_field_widget)
#         scaling_field_layout.addWidget(self.scale_widget)
#         scaling_field_layout.setAlignment(Qt.AlignTop)

#         # OK and Cancel buttons
#         self.button_box = QDialogButtonBox(
#             QDialogButtonBox.Ok | QDialogButtonBox.Cancel
#         )
#         self.button_box.accepted.connect(self._ok_clicked)
#         self.button_box.rejected.connect(self.reject)

#         # Add widgets to main layout
#         self.layout.addLayout(csv_layout)
#         self.layout.addLayout(image_layout)
#         self.layout.addLayout(name_layout)
#         self.layout.addLayout(scaling_field_layout)
#         self.layout.addWidget(self.button_box)

#     def _browse_csv(self):
#         """Open File dialog to select CSV file"""

#         csv_file, _ = QFileDialog.getOpenFileName(
#             self, "Select CSV File", "", "CSV Files (*.csv)"
#         )
#         if csv_file:
#             self._load_csv(csv_file)
#         else:
#             QMessageBox.warning(self, "Input Required", "Please select a CSV file.")

#     def _load_csv(self, csv_file):
#         self.csv_path_line.setText(csv_file)
#         # Ensure CSV path is provided and valid
#         try:
#             self.df = pd.read_csv(csv_file, nrows=0)
#             self.csv_field_widget = CSVFieldMapWidget(list(self.df.columns), False)
#             self.layout.addWidget(self.csv_field_widget)
#         except FileNotFoundError:
#             QMessageBox.critical(self, "Error", "The specified file was not found.")
#             return
#         except pd.errors.EmptyDataError:
#             QMessageBox.critical(self, "Error", "The file is empty or has no data.")
#             return
#         except pd.errors.ParserError:
#             QMessageBox.critical(
#                 self, "Error", "The file could not be parsed as a valid CSV."
#             )

#     def _browse_image(self):
#         """File dialog to select image file (TIFF or Zarr)"""

#         image_file, _ = QFileDialog.getOpenFileName(
#             self, "Select Segmentation File", "", "Segmentation Files (*.tiff *.zarr)"
#         )
#         if image_file:
#             self.image_path_line.setText(image_file)

#     def _load_segmentation(self, segmentation_file):
#         # Check if a valid path to a segmentation image file is provided and if so load it
#         if os.path.exists(self.image_path_line.text()):
#             if self.image_path_line.text().endswith(".tif"):
#                 segmentation = tifffile.imread(
#                     self.image_path_line.text()
#                 )  # Assuming no segmentation is needed at this step
#             elif ".zarr" in self.image_path_line.text():
#                 segmentation = zarr.open(self.image_path_line.text())
#             else:
#                 QMessageBox.warning(
#                     self,
#                     "Invalid file type",
#                     "Please provide a tiff or zarr file for the segmentation image stack",
#                 )
#                 return
#         else:
#             segmentation = None
#         self.segmentation = segmentation

#     def _ok_clicked(self):
#         """Tries to read the CSV file and optional segmentation image,
#         and apply the attribute to column mapping to construct a Tracks object"""


#         # Retrieve selected columns for each required field, and optional columns for additional attributes
#         name_map = self.csv_field_widget.get_name_map()
#         # note: this will fail if one column is used for two features
#         name_map_reversed = {
#             value: key for key, value in name_map.items()
#         }
#         self.df.rename(columns=name_map_reversed, inplace=True)

#         # Read scaling information from the spinboxes, and name from the name_widget
#         scale = self.scale_widget.get_scale()
#         self.name = self.name_widget.text()

#         # Try to create a Tracks object with the provided CSV file, the attr:column dictionaries, and the scaling information
#         try:
#             self.tracks = tracks_from_df(
#                 self.df, self.segmentation, scale
#             )

#         except ValueError as e:
#             QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
#             return
#         self.accept()


class ImportTracksDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Import external tracks from CSV")

        self.csv = None
        self.segmentation = None
        self.name = "External Tracks from CSV"

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
        self.previous_button.clicked.connect(self.go_to_previous_page)
        self.next_button.clicked.connect(self.go_to_next_page)
        self.finish_button.clicked.connect(self.finish)

        ## Page 1 for user choices
        self.page1 = QWidget()
        page1_layout = QVBoxLayout()
        self.menu_widget = ChoiceMenu()
        page1_layout.addWidget(self.menu_widget)
        self.page1.setLayout(page1_layout)
        self.stacked_widget.addWidget(self.page1)

        self.menu_widget.scale_checkbox.stateChanged.connect(self.update_pages)
        self.menu_widget.segmentation_checkbox.stateChanged.connect(self.update_pages)
        self.menu_widget.radio_2D.clicked.connect(self.update_pages)
        self.menu_widget.radio_3D.clicked.connect(self.update_pages)

        # Page 2 for data selection
        self.page2 = Page2(
            add_segmentation=self.menu_widget.segmentation_checkbox.isChecked()
        )
        self.stacked_widget.addWidget(self.page2)

        self.scale_page = None

        # Set initial state
        self.update_buttons()

    def update_pages(self):
        self.stacked_widget.removeWidget(self.page2)
        if self.scale_page is not None:
            self.stacked_widget.removeWidget(self.scale_page)

        self.page2 = Page2(
            add_segmentation=self.menu_widget.segmentation_checkbox.isChecked(),
            incl_z=self.menu_widget.radio_3D.isChecked(),
        )
        self.stacked_widget.addWidget(self.page2)

        if self.menu_widget.scale_checkbox.isChecked():
            self.scale_page = ScaleWidget(self.menu_widget.radio_3D.isChecked())
            self.stacked_widget.addWidget(self.scale_page)

        self.stacked_widget.hide()
        self.stacked_widget.show()

    def go_to_previous_page(self):
        """Go to the previous page."""
        current_index = self.stacked_widget.currentIndex()
        if current_index > 0:
            self.stacked_widget.setCurrentIndex(current_index - 1)
        self.update_buttons()

    def go_to_next_page(self):
        """Go to the next page."""
        current_index = self.stacked_widget.currentIndex()
        if current_index < self.stacked_widget.count() - 1:
            self.stacked_widget.setCurrentIndex(current_index + 1)
        self.update_buttons()

    def update_buttons(self):
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

    def finish(self):
        """Tries to read the CSV file and optional segmentation image,
        and apply the attribute to column mapping to construct a Tracks object"""

        # Retrieve selected columns for each required field, and optional columns for additional attributes
        name_map = self.page2.csv_field_widget.get_name_map()
        # note: this will fail if one column is used for two features
        name_map_reversed = {value: key for key, value in name_map.items()}
        print(name_map_reversed)
        print(self.page2.df)
        self.page2.df.rename(columns=name_map_reversed, inplace=True)
        print(self.page2.df.columns)

        # Read scaling information from the spinboxes, and name from the name_widget
        if self.scale_page is not None:
            scale = self.scale_page.get_scale()
        else:
            scale = [1, 1, 1] if self.page2.incl_z is False else [1, 1, 1, 1]

        # self.name = self.name_widget.text()

        # Try to create a Tracks object with the provided CSV file, the attr:column dictionaries, and the scaling information

        if self.page2.add_segmentation:
            self.page2._load_segmentation()
        else:
            self.page2.segmentation = None

        try:
            self.tracks = tracks_from_df(self.page2.df, self.page2.segmentation, scale)

        except ValueError as e:
            QMessageBox.critical(self, "Error", f"Failed to load tracks: {e}")
            return
        self.accept()


class Page2(QWidget):
    def __init__(self, add_segmentation: bool = False, incl_z: bool = False):
        super().__init__()

        self.add_segmentation = add_segmentation
        self.incl_z = incl_z

        print("create new page 2 with seg", add_segmentation, "and incl_z", incl_z)

        self.layout = QVBoxLayout(self)

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

        self.layout.addLayout(csv_layout)

        if self.add_segmentation:
            # Image File Selection
            self.image_path_line = QLineEdit(self)
            self.image_browse_button = QPushButton("Browse Segmentation", self)
            self.image_browse_button.clicked.connect(self._browse_image)

            image_layout = QHBoxLayout()
            image_layout.addWidget(QLabel("Segmentation File Path:"))
            image_layout.addWidget(self.image_path_line)
            image_layout.addWidget(self.image_browse_button)
            self.layout.addLayout(image_layout)

        self.csv_field_widget: CSVFieldMapWidget | None = None

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
        print("loading csv")
        self.csv_path_line.setText(csv_file)
        # Ensure CSV path is provided and valid
        try:
            self.df = pd.read_csv(csv_file)
            if self.csv_field_widget is not None:
                self.layout.removeWidget(self.csv_field_widget)
            self.csv_field_widget = CSVFieldMapWidget(
                list(self.df.columns), seg=self.add_segmentation, incl_z=self.incl_z
            )
            self.layout.addWidget(self.csv_field_widget)

            print(self.df)
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

    def _load_segmentation(self):
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
