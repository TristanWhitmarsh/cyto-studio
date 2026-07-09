    
import sys
import re

# if 'PyQt5' in sys.modules:
#     print("Using PyQt5")
#     from qtpy import QtCore, QtWidgets
#     from qtpy.QtWidgets import QComboBox, QApplication, QCompleter, QMessageBox
#     from qtpy.QtCore import QSortFilterProxyModel, Qt
#     from qtpy.QtGui import QColor, QPixmap, QIcon, QStandardItemModel, QStandardItem, QPainter, QFont
#     from qtpy.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea,
#                                 QComboBox, QCheckBox, QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QMainWindow)
# else:
print("Using PySide2")
from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtCore import Qt, QSortFilterProxyModel
from PySide2.QtGui import QColor, QPixmap, QIcon, QStandardItemModel, QStandardItem, QPainter, QFont
from PySide2.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QScrollArea,
                               QComboBox, QCheckBox, QListWidget, QListWidgetItem, QMessageBox, QFileDialog, QMainWindow, QCompleter)


class ExtendedComboBox(QComboBox):
    def __init__(self, parent=None):
        super(ExtendedComboBox, self).__init__(parent)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setEditable(True)

        # add a filter model to filter matching items
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.pFilterModel.setSourceModel(self.model())

        # add a completer, which uses the filter model
        self.completer = QCompleter(self.pFilterModel, self)
        # always show all (filtered) completions
        self.completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)

        # connect signals
        self.lineEdit().textEdited[str].connect(self.pFilterModel.setFilterFixedString)
        self.completer.activated.connect(self.on_completer_activated)


    # on selection of an item from the completer, select the corresponding item from combobox
    def on_completer_activated(self, text):
        if text:
            index = self.findText(text)
            self.setCurrentIndex(index)
            self.activated[str].emit(self.itemText(index))


    # on model change, update the models of the filter and completer as well
    def setModel(self, model):
        super(ExtendedComboBox, self).setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer.setModel(self.pFilterModel)


    # on model column change, update the model column of the filter and completer as well
    def setModelColumn(self, column):
        self.completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super(ExtendedComboBox, self).setModelColumn(column)

        
        
class CheckableItemWidget(QtWidgets.QWidget):
    def __init__(self, text, parent=None):
        super().__init__(parent)

        self.checkBox = QtWidgets.QCheckBox()
        self.label = QtWidgets.QLabel(text)

        layout = QtWidgets.QHBoxLayout(self)
        layout.addWidget(self.checkBox)
        layout.addWidget(self.label)
        layout.addStretch()

        # Adjust these margins and spacing as needed
        layout.setContentsMargins(0, 0, 0, 0)  # Reduce the margins
        layout.setSpacing(0)  # Reduce the spacing between the checkbox and label

        self.setLayout(layout)

    def isChecked(self):
        return self.checkBox.isChecked()

    

class CustomComboBox(QtWidgets.QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._listWidget = QtWidgets.QListWidget()
        self.setModel(self._listWidget.model())
        self.setView(self._listWidget)

    def addItem(self, text):
        item = QtWidgets.QListWidgetItem(self._listWidget)
        widget = CheckableItemWidget(text)
        item.setSizeHint(widget.sizeHint())
        self._listWidget.setItemWidget(item, widget)

    def itemChecked(self, index):
        item = self._listWidget.item(index)
        widget = self._listWidget.itemWidget(item)
        return widget.isChecked()
    
    def checkItem(self, index, check=True):
        if 0 <= index < self._listWidget.count():
            item = self._listWidget.item(index)
            widget = self._listWidget.itemWidget(item)
            if widget:
                widget.checkBox.setChecked(check)
    
    def clearItems(self):
        self._listWidget.clear()

    def getCheckedItems(self):
        checkedItems = []
        for index in range(self._listWidget.count()):
            item = self._listWidget.item(index)
            check = self._listWidget.itemWidget(item)
            if check.isChecked():
                #checkedItems.append(item.text())
                checkedItems.append(index)
        return checkedItems
    
    
    
    
    


class LegendWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setAutoFillBackground(True)
        p = self.palette()
        p.setColor(self.backgroundRole(), Qt.black)  # Set the widget's background to black
        self.setPalette(p)

        self.layout = QVBoxLayout(self)  # Set the main layout for the widget

        # Create a scroll area to contain the frame
        self.scrollArea = QScrollArea(self)
        self.scrollArea.setWidgetResizable(True)  # Allow the contained widget to resize
        self.layout.addWidget(self.scrollArea)  # Add the scroll area to the widget's main layout

        # Frame setup
        self.frame = QFrame()
        self.frame.setAutoFillBackground(False)
        self.frameLayout = QVBoxLayout(self.frame)  # Create a layout for the frame
        self.frame.setLayout(self.frameLayout)  # Set the layout on the frame

        self.scrollArea.setWidget(self.frame)  # Set the frame as the scroll area's widget

        self.channel_names = None
        self.colors = None

        # Ensure there's a stretch at the end of the frameLayout to push items to the top
        self.frameLayout.addStretch(1)

    def clear_layout(self, layout):
        """Clears a layout."""
        while layout.count():
            item = layout.takeAt(0)
            if item.layout() is not None:
                # Clear nested layout first
                self.clear_layout(item.layout())
                item.layout().deleteLater()
            elif item.widget() is not None:
                item.widget().deleteLater()

    def populate_legend(self, channel_names, colors):
        # First, clear the existing content in the layout
        self.clear_layout(self.frameLayout)
        
        self.channel_names = channel_names
        self.colors = colors

        # Removing the stretch before repopulating
        while self.frameLayout.count() > 0:
            self.frameLayout.takeAt(0)

        for name, color in zip(channel_names, colors):
            channel_layout = QHBoxLayout()
            color_label = QLabel()
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(*color))
            color_label.setPixmap(pixmap)

            name_str = str(name) if isinstance(name, int) else name
            
            name_str2 = name_str
            # name_str2 = re.sub(r'\d+\s*', '', name_str, count=1)
            # if name_str2 == "" or name_str2 == " ":
            #     name_str2 = name_str
            
            text_label = QLabel(name_str2)
            text_label.setStyleSheet("QLabel { color : white; }")

            channel_layout.addWidget(color_label)
            channel_layout.addWidget(text_label)
            channel_layout.addStretch(1)

            self.frameLayout.addLayout(channel_layout)

        # Add a final stretch to ensure all items are aligned at the top
        self.frameLayout.addStretch(1)

        self.add_save_button()  # Consider whether you need to re-add the save button every time

    def add_save_button(self):
        # Check if the save button already exists
        if hasattr(self, 'save_button'):
            return  # The button already exists, so don't add it again

        self.save_button = QPushButton("Save to Image")
        self.save_button.clicked.connect(self.save_legend_to_image)
        self.layout.addWidget(self.save_button)  # Add the save button to the widget's main layout



    def save_legend_to_image(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Save Image", "", "BMP Files (*.bmp);;All Files (*)")
        if filename:
            self.render_legend_to_image(filename)

    def render_legend_to_image(self, filename):
        width = 200
        height_per_item = 20
        canvas_height = len(self.channel_names) * height_per_item

        pixmap = QPixmap(width, canvas_height)
        pixmap.fill(Qt.black)

        painter = QPainter(pixmap)
        painter.setFont(QFont("Arial", 10))
        text_offset_x = 30
        box_size = 15

        for index, (name, color) in enumerate(zip(self.channel_names, self.colors)):
            painter.setBrush(QColor(*color))
            painter.setPen(Qt.NoPen)

            y_pos = index * height_per_item
            painter.drawRect(5, y_pos + 2, box_size, box_size)
            painter.setPen(Qt.white)
            
            name_str = str(name) if isinstance(name, int) else name
            
            name_str2 = re.sub(r'\d+\s*', '', name_str, count=1)
            if name_str2 == "" or name_str2 == " ":
                name_str2 = name_str
                
            painter.drawText(text_offset_x, y_pos + box_size, name_str2)

        painter.end()
        pixmap.save(filename, "BMP")
        print(f"Legend saved as {filename}")




        

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
        
# import numpy as np

# from PySide2.QtWidgets import (
#     QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame, QLabel,
#     QComboBox, QLineEdit, QPushButton, QRadioButton, QGroupBox, QMessageBox
# )
# from PySide2.QtCore import Qt

# from stardist.models import StarDist2D
# from csbdeep.utils import normalize
# from skimage.measure import regionprops


# class StardistWidget(QWidget):
#     def __init__(self, viewer, parent=None):
#         super().__init__(parent)
#         self.viewer = viewer
#         self.model = None
#         self._model_name = None

#         self.setAutoFillBackground(True)
#         p = self.palette()
#         p.setColor(self.backgroundRole(), Qt.black)
#         self.setPalette(p)

#         # main layout
#         self.layout = QVBoxLayout(self)

#         # scroll area
#         self.scrollArea = QScrollArea(self)
#         self.scrollArea.setWidgetResizable(True)
#         self.layout.addWidget(self.scrollArea)

#         # inner frame
#         self.frame = QFrame()
#         self.frame.setAutoFillBackground(False)
#         self.frameLayout = QVBoxLayout(self.frame)
#         self.scrollArea.setWidget(self.frame)

#         # build UI
#         self._build_ui()

#         # keep layer list updated
#         self._update_layer_list()
#         self.viewer.layers.events.inserted.connect(lambda e: self._update_layer_list())
#         self.viewer.layers.events.removed.connect(lambda e: self._update_layer_list())
#         self.viewer.layers.events.reordered.connect(lambda e: self._update_layer_list())

#         # stretch at end
#         self.frameLayout.addStretch(1)

#     # ---------------- UI ----------------

#     def _build_ui(self):
#         # --- Layer selection ---
#         layer_box = QGroupBox("Input layer")
#         layer_layout = QVBoxLayout()

#         hl = QHBoxLayout()
#         hl.addWidget(QLabel("Image layer:"))
#         self.layer_combo = QComboBox()
#         self.layer_combo.currentIndexChanged.connect(self._on_layer_changed)
#         hl.addWidget(self.layer_combo)

#         refresh_btn = QPushButton("Refresh")
#         refresh_btn.clicked.connect(self._update_layer_list)
#         hl.addWidget(refresh_btn)

#         hl.addStretch(1)
#         layer_layout.addLayout(hl)

#         # Multiscale level selection
#         hl2 = QHBoxLayout()
#         self.level_label = QLabel("Multiscale level:")
#         hl2.addWidget(self.level_label)
#         self.level_combo = QComboBox()
#         self.level_combo.setEnabled(False)
#         self.level_combo.setToolTip("If layer is multiscale, select which level to segment (0 = highest resolution).")
#         hl2.addWidget(self.level_combo)
#         hl2.addStretch(1)
#         layer_layout.addLayout(hl2)

#         layer_box.setLayout(layer_layout)
#         self.frameLayout.addWidget(layer_box)

#         # --- Model + parameters ---
#         params_box = QGroupBox("StarDist parameters")
#         params_layout = QVBoxLayout()

#         # model name (pretrained)
#         hl = QHBoxLayout()
#         hl.addWidget(QLabel("Pretrained model:"))
#         self.model_name_edit = QLineEdit("2D_versatile_fluo")
#         self.model_name_edit.setToolTip("StarDist2D.from_pretrained(model_name)")
#         hl.addWidget(self.model_name_edit)
#         hl.addStretch(1)
#         params_layout.addLayout(hl)

#         # prob_thresh / nms_thresh
#         hl = QHBoxLayout()
#         hl.addWidget(QLabel("prob_thresh:"))
#         self.prob_thresh_edit = QLineEdit("0.5")
#         self.prob_thresh_edit.setMaximumWidth(80)
#         hl.addWidget(self.prob_thresh_edit)

#         hl.addWidget(QLabel("nms_thresh:"))
#         self.nms_thresh_edit = QLineEdit("0.4")
#         self.nms_thresh_edit.setMaximumWidth(80)
#         hl.addWidget(self.nms_thresh_edit)

#         hl.addStretch(1)
#         params_layout.addLayout(hl)

#         # n_tiles / min size
#         hl = QHBoxLayout()
#         hl.addWidget(QLabel("n_tiles:"))
#         self.n_tiles_edit = QLineEdit("auto")
#         self.n_tiles_edit.setMaximumWidth(120)
#         self.n_tiles_edit.setToolTip("e.g. 'auto', '2x2', '1x4', '3', or empty for no tiling")
#         hl.addWidget(self.n_tiles_edit)

#         hl.addWidget(QLabel("Min object size (px):"))
#         self.min_size_edit = QLineEdit("0")
#         self.min_size_edit.setMaximumWidth(80)
#         hl.addWidget(self.min_size_edit)

#         hl.addStretch(1)
#         params_layout.addLayout(hl)

#         params_box.setLayout(params_layout)
#         self.frameLayout.addWidget(params_box)

#         # --- Slice mode (all vs current) ---
#         slice_box = QGroupBox("Apply to")
#         slice_layout = QHBoxLayout()

#         self.rb_all_slices = QRadioButton("All slices")
#         self.rb_all_slices.setChecked(True)
#         slice_layout.addWidget(self.rb_all_slices)

#         self.rb_current_slice = QRadioButton("Current slice only")
#         slice_layout.addWidget(self.rb_current_slice)

#         slice_layout.addStretch(1)
#         slice_box.setLayout(slice_layout)
#         self.frameLayout.addWidget(slice_box)

#         # --- Run button ---
#         hl = QHBoxLayout()
#         self.run_button = QPushButton("Run StarDist")
#         self.run_button.clicked.connect(self.run_stardist)
#         hl.addWidget(self.run_button)
#         hl.addStretch(1)
#         self.frameLayout.addLayout(hl)

#     # ---------------- layer / multiscale handling ----------------

#     def _update_layer_list(self):
#         """Populate combo box with napari Image layers."""
#         current = self.layer_combo.currentText()
#         self.layer_combo.blockSignals(True)
#         self.layer_combo.clear()

#         for layer in self.viewer.layers:
#             if layer.__class__.__name__ == "Image":
#                 self.layer_combo.addItem(layer.name)

#         idx = self.layer_combo.findText(current)
#         if idx >= 0:
#             self.layer_combo.setCurrentIndex(idx)
#         elif self.layer_combo.count() > 0:
#             self.layer_combo.setCurrentIndex(0)

#         self.layer_combo.blockSignals(False)
#         self._update_multiscale_levels()

#     def _on_layer_changed(self, index):
#         self._update_multiscale_levels()

#     def _update_multiscale_levels(self):
#         """If selected layer is multiscale, populate level combo."""
#         self.level_combo.blockSignals(True)
#         self.level_combo.clear()

#         layer_name = self.layer_combo.currentText()
#         if not layer_name:
#             self.level_combo.setEnabled(False)
#             self.level_label.setEnabled(False)
#             self.level_combo.blockSignals(False)
#             return

#         try:
#             layer = self.viewer.layers[layer_name]
#         except KeyError:
#             self.level_combo.setEnabled(False)
#             self.level_label.setEnabled(False)
#             self.level_combo.blockSignals(False)
#             return

#         if getattr(layer, "multiscale", False):
#             # layer.data is MultiScaleData: sequence of arrays [level0, level1, ...]
#             n_levels = len(layer.data)
#             for i in range(n_levels):
#                 self.level_combo.addItem(str(i))
#             self.level_combo.setCurrentIndex(0)
#             self.level_combo.setEnabled(True)
#             self.level_label.setEnabled(True)
#         else:
#             # not multiscale
#             self.level_combo.addItem("0")
#             self.level_combo.setCurrentIndex(0)
#             self.level_combo.setEnabled(False)
#             self.level_label.setEnabled(False)

#         self.level_combo.blockSignals(False)

#     # ---------------- parameter helpers ----------------

#     def _parse_n_tiles(self, text):
#         text = text.strip()
#         if not text:
#             return None
#         if text.lower() in ("none",):
#             return None
#         if text.lower() in ("auto",):
#             return "auto"

#         # allow '2x2' or '2,2'
#         for sep in ("x", "X", ","):
#             if sep in text:
#                 a, b = text.split(sep, 1)
#                 try:
#                     return (int(a), int(b))
#                 except ValueError:
#                     return None

#         # single int -> (n, n)
#         try:
#             n = int(text)
#             return (n, n)
#         except ValueError:
#             return None

#     def _suggest_n_tiles_for_shape(self, shape):
#         """Return a reasonable (ny, nx) for big images, or (1, 1) for small ones."""
#         if len(shape) >= 2:
#             h, w = shape[-2], shape[-1]
#         else:
#             return (1, 1)

#         max_tile = 2048  # tune if needed

#         ny = int(np.ceil(h / max_tile))
#         nx = int(np.ceil(w / max_tile))

#         ny = max(1, ny)
#         nx = max(1, nx)
#         return (ny, nx)

#     def _get_or_load_model(self):
#         model_name = self.model_name_edit.text().strip()
#         if self.model is None or self._model_name != model_name:
#             try:
#                 self.model = StarDist2D.from_pretrained(model_name)
#                 self._model_name = model_name
#             except Exception as e:
#                 QMessageBox.critical(
#                     self,
#                     "StarDist error",
#                     f"Failed to load model '{model_name}':\n{e}",
#                 )
#                 self.model = None
#         return self.model

#     # ---------------- main action ----------------

#     def run_stardist(self):
#         # ----- basic sanity checks -----
#         layer_name = self.layer_combo.currentText()
#         if not layer_name:
#             QMessageBox.warning(self, "No layer", "Please select an image layer.")
#             return

#         try:
#             layer = self.viewer.layers[layer_name]
#         except KeyError:
#             QMessageBox.warning(self, "Layer missing", "Selected layer not found.")
#             return

#         # extract data, with multiscale support
#         data = layer.data

#         try:
#             if getattr(layer, "multiscale", False):
#                 # layer.data is MultiScaleData: sequence of arrays [level0, level1, ...]
#                 level_idx = self.level_combo.currentIndex()
#                 if level_idx < 0:
#                     level_idx = 0
#                 level_arrays = list(data)
#                 level_idx = min(max(level_idx, 0), len(level_arrays) - 1)
#                 data = np.asarray(level_arrays[level_idx])
#             elif not isinstance(data, np.ndarray):
#                 data = np.asarray(data)
#         except Exception as e:
#             QMessageBox.warning(
#                 self,
#                 "Unsupported data",
#                 f"Could not convert layer data to numpy array:\n{e}",
#             )
#             return

#         if data.ndim < 2:
#             QMessageBox.warning(self, "Unsupported data", "Data must be 2D or 3D.")
#             return

#         # parameters
#         try:
#             prob_thresh = float(self.prob_thresh_edit.text())
#             nms_thresh = float(self.nms_thresh_edit.text())
#             min_size = int(self.min_size_edit.text())
#         except ValueError:
#             QMessageBox.warning(
#                 self,
#                 "Invalid parameters",
#                 "Check prob_thresh, nms_thresh and min size.",
#             )
#             return

#         n_tiles_raw = self._parse_n_tiles(self.n_tiles_edit.text())
#         if n_tiles_raw == "auto":
#             n_tiles = self._suggest_n_tiles_for_shape(data.shape)
#         else:
#             n_tiles = n_tiles_raw

#         # model
#         model = self._get_or_load_model()
#         if model is None:
#             return

#         apply_all = self.rb_all_slices.isChecked()

#         # ----- run segmentation -----
#         try:
#             if data.ndim == 2:
#                 labels, details = model.predict_instances(
#                     normalize(data),
#                     prob_thresh=prob_thresh,
#                     nms_thresh=nms_thresh,
#                     n_tiles=n_tiles,
#                 )
#                 labels = self._filter_by_size(labels, min_size)
#                 self._add_results_2d(labels, details, layer_name)

#             elif data.ndim == 3:
#                 self._run_on_3d_stack(
#                     data,
#                     layer_name,
#                     model,
#                     prob_thresh,
#                     nms_thresh,
#                     n_tiles,
#                     min_size,
#                     apply_all,
#                 )
#             else:
#                 QMessageBox.warning(
#                     self,
#                     "Unsupported shape",
#                     "Currently only 2D or 3D (z,y,x) images are supported.",
#                 )
#                 return

#         except Exception as e:
#             QMessageBox.critical(
#                 self,
#                 "StarDist error",
#                 f"Segmentation failed:\n{e}",
#             )
#             return

#     # ---------------- helpers: segmentation / output ----------------

#     def _filter_by_size(self, labels, min_size):
#         """Remove small objects (per-label pixel count)."""
#         if min_size <= 0:
#             return labels

#         labels = labels.copy()
#         for r in regionprops(labels):
#             if r.area < min_size:
#                 labels[labels == r.label] = 0
#         return labels

#     def _add_results_2d(self, labels, details, base_name):
#         """Add labels + contour shapes for a 2D result."""
#         self.viewer.add_labels(labels, name=f"{base_name}_stardist_labels")

#         shape_data = []

#         coords_list = details.get("coord", None)
#         if coords_list is not None:
#             for poly in coords_list:
#                 if poly is None or len(poly) == 0:
#                     continue
#                 shape_data.append(np.asarray(poly, dtype=float))  # (y,x)

#         if shape_data:
#             self.viewer.add_shapes(
#                 shape_data,
#                 shape_type="polygon",
#                 edge_width=1.0,
#                 edge_color="yellow",
#                 face_color="transparent",
#                 name=f"{base_name}_stardist_contours",
#             )

#     def _run_on_3d_stack(
#         self,
#         data,
#         base_name,
#         model,
#         prob_thresh,
#         nms_thresh,
#         n_tiles,
#         min_size,
#         apply_all,
#     ):
#         """Run StarDist slice-by-slice on a (z,y,x) stack."""
#         z_dim = data.shape[0]

#         if apply_all:
#             z_indices = range(z_dim)
#         else:
#             z_idx = self.viewer.dims.current_step[0]
#             if z_idx < 0 or z_idx >= z_dim:
#                 QMessageBox.warning(
#                     self,
#                     "Slice out of range",
#                     "Current slice index is out of range.",
#                 )
#                 return
#             z_indices = [z_idx]

#         labels_stack = np.zeros_like(data, dtype=np.int32)
#         shapes = []
#         current_max = 0

#         for z in z_indices:
#             img = data[z]
#             labels, details = model.predict_instances(
#                 normalize(img),
#                 prob_thresh=prob_thresh,
#                 nms_thresh=nms_thresh,
#                 n_tiles=n_tiles,
#             )
#             labels = self._filter_by_size(labels, min_size)

#             if apply_all:
#                 if labels.max() > 0:
#                     lab = labels.copy()
#                     lab[lab > 0] += current_max
#                     labels_stack[z] = lab
#                     current_max = labels_stack.max()
#             else:
#                 labels_stack[z] = labels

#             # shapes: 3D polygons with constant z
#             coords_list = details.get("coord", None)
#             if coords_list is not None:
#                 for poly in coords_list:
#                     if poly is None or len(poly) == 0:
#                         continue
#                     poly = np.asarray(poly, dtype=float)  # (N,2) y,x
#                     z_col = np.full((poly.shape[0], 1), float(z))
#                     poly3d = np.concatenate([z_col, poly], axis=1)  # (z,y,x)
#                     shapes.append(poly3d)

#         name_base = f"{base_name}_stardist"
#         self.viewer.add_labels(labels_stack, name=f"{name_base}_labels")

#         if shapes:
#             self.viewer.add_shapes(
#                 shapes,
#                 shape_type="polygon",
#                 edge_width=1.0,
#                 edge_color="yellow",
#                 face_color="transparent",
#                 name=f"{name_base}_contours",
#             )
