from qgis.PyQt.QtWidgets import QAction, QMessageBox, QCheckBox, QWidget, QHBoxLayout, QLabel, QSpacerItem, QSizePolicy, QComboBox
from qgis.PyQt.QtGui import QIcon, QColor, QPen, QPolygonF
from qgis.PyQt.QtCore import QPointF, Qt
from qgis.core import (
    QgsProject,
    QgsLayoutItemPolyline,
    QgsLineSymbol,
    QgsSimpleLineSymbolLayer,
    QgsUnitTypes,
)
import os
from .ui.folding_dialog import FoldingDialog

class PlaceFoldingMarksPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None               # menu action
        self.toolbar_action = None       # toolbar action
        self.dlg = None

    # -------------------------
    # QGIS plugin boilerplate
    # -------------------------
    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "resources", "icon_place_folding_marks.svg"))

        # Menu item
        self.action = QAction(icon, "Place Folding Marks", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu("Place Folding Marks", self.action)

        # Toolbar button in main QGIS window
        self.toolbar_action = QAction(icon, "Place Folding Marks", self.iface.mainWindow())
        self.toolbar_action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.toolbar_action)

    def unload(self):
        self.iface.removePluginMenu("Place Folding Marks", self.action)
        if self.toolbar_action:
            self.iface.removeToolBarIcon(self.toolbar_action)

    def run(self):
        self.show_dialog()

    # -------------------------
    # Dialog setup
    # -------------------------
    def show_dialog(self):
        if not self.dlg:
            self.dlg = FoldingDialog()
            # Defaults in mm
            self.dlg.spinLineLength.setValue(10)     # default line length = 10 mm
            self.dlg.spinLineThickness.setValue(1)   # default line thickness = 1 mm
            self.dlg.btnPlaceMarks.clicked.connect(self.on_btnPlaceMarks_clicked)

            # Container voor tekst + checkbox (altijd aanwezig)
            self.dlg.chkRemoveExisting = QCheckBox()
            self.dlg.chkRemoveExisting.setVisible(False)  # standaard onzichtbaar

            self.dlg.lblRemoveExisting = QLabel("Verwijder bestaande Folding lines")
            self.dlg.lblRemoveExisting.setVisible(False)

            container = QWidget()
            hbox = QHBoxLayout(container)
            hbox.setContentsMargins(0, 0, 0, 0)
            hbox.addWidget(self.dlg.lblRemoveExisting)
            hbox.addItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))
            hbox.addWidget(self.dlg.chkRemoveExisting)

            # Voeg container onder spinLineThickness en boven btnPlaceMarks toe
            if self.dlg.layout():
                layout = self.dlg.layout()
                idx = layout.indexOf(self.dlg.btnPlaceMarks)
                if idx != -1:
                    layout.insertWidget(idx, container)

            # Synchroniseer wanneer de gebruiker een andere layout kiest
            self.dlg.comboLayout.currentIndexChanged.connect(self.on_layout_changed)

        has_layouts = self.populate_layout_dropdown()
        if not has_layouts:
            return

        # Initiale sync uitvoeren
        self.on_layout_changed()

        self.dlg.exec()

    def on_layout_changed(self):
        #Update visibility of the text and checkbox depending on the chosen layout.
        layout_name = self.dlg.comboLayout.currentText()
        if self.has_existing_folding_lines(layout_name):
            self.dlg.lblRemoveExisting.setVisible(True)
            self.dlg.chkRemoveExisting.setVisible(True)
            self.dlg.chkRemoveExisting.setChecked(True)
        else:
            self.dlg.lblRemoveExisting.setVisible(False)
            self.dlg.chkRemoveExisting.setVisible(False)
            self.dlg.chkRemoveExisting.setChecked(False)

    def populate_layout_dropdown(self):
        project = QgsProject.instance()
        layout_manager = project.layoutManager()
        layouts = layout_manager.layouts()

        self.dlg.comboLayout.clear()

        if not layouts:
            self.dlg.comboLayout.setEnabled(False)
            QMessageBox.information(
                self.iface.mainWindow(),
                "No layouts available",
                "There are no layouts available in this project. Create a layout using the layout manager before using this plugin.",
            )
            return False

        self.dlg.comboLayout.setEnabled(True)
        for layout in layouts:
            self.dlg.comboLayout.addItem(layout.name())
        return True

    # -------------------------
    # Helpers
    # -------------------------
    def get_layout_size_mm(self, layout_name):
        project = QgsProject.instance()
        layout_manager = project.layoutManager()
        layout = layout_manager.layoutByName(layout_name)
        if not layout:
            return None, None
        size = layout.pageCollection().page(0).pageSize()  # QSizeF in mm
        return size.width(), size.height()

    def folded_format_mm(self, format_string):
        # Map selected string to size in mm
        if "A4 (210 × 297 mm)" in format_string:
            return 210.0, 297.0
        elif "US Letter (8.5 × 11 inch)" in format_string:
            return 215.9, 279.4
        elif "US Legal (8.5 × 14 inch)" in format_string:
            return 215.9, 355.6
        else:
            return None, None

    def has_existing_folding_lines(self, layout_name):
        """Check if layout already contains items with id == 'Folding line'."""
        project = QgsProject.instance()
        layout_manager = project.layoutManager()
        layout = layout_manager.layoutByName(layout_name)
        if not layout:
            return False
        for item in layout.items():
            if isinstance(item, QgsLayoutItemPolyline) and item.id() == "Folding line":
                return True
        return False

    def remove_existing_folding_lines(self, layout):
        """Remove all polylines with id == 'Folding line' from layout."""
        for item in list(layout.items()):
            if isinstance(item, QgsLayoutItemPolyline) and item.id() == "Folding line":
                layout.removeLayoutItem(item)

    def build_base_symbol(self, line_thickness_mm):
        # -------------------------
        # Bouw een basis-lijnsymbool (zwart, dikte in mm, flat cap).
        # We gebruiken QgsSimpleLineSymbolLayer + QgsLineSymbol en retourneren het symbool.
        # Dit symbool wordt vervolgens per polyline gecloned().
        # -------------------------
        
        layer = QgsSimpleLineSymbolLayer()
        layer.setColor(QColor(0, 0, 0))
        layer.setWidth(float(line_thickness_mm))
        layer.setWidthUnit(QgsUnitTypes.RenderMillimeters)
        # Flat line cap
        # (QGIS gebruikt Qt.PenCapStyle)
        layer.setPenCapStyle(Qt.PenCapStyle.FlatCap)

        symbol = QgsLineSymbol([layer])
        return symbol

    # -------------------------
    # Core: place folding marks
    # -------------------------
    def place_folding_marks(self, layout_name, folded_format_str, line_length_mm, line_thickness_mm):
        project = QgsProject.instance()
        layout_manager = project.layoutManager()
        layout = layout_manager.layoutByName(layout_name)
        if not layout:
            print("Layout not found:", layout_name)
            return

        # -----------------------------
        # Remove existing folding marks when checked
        # -----------------------------
        if getattr(self.dlg, "chkRemoveExisting", None) and self.dlg.chkRemoveExisting.isChecked():
            self.remove_existing_folding_lines(layout)

        layout_width, layout_height = self.get_layout_size_mm(layout_name)
        folded_width, folded_height = self.folded_format_mm(folded_format_str)

        if None in (layout_width, layout_height, folded_width, folded_height):
            print("Unknown format or layout size.")
            return

        # -----------------------------
        # Construct basic symbol and clone() later per iten
        # -----------------------------
        base_symbol = self.build_base_symbol(line_thickness_mm)

        # -----------------------------
        # Vertical folding lines (top & bottom)
        # -----------------------------
        num_vertical_lines = int(layout_width // folded_width)
        if num_vertical_lines < 1:
            num_vertical_lines = 0

        for i in range(1, num_vertical_lines + 1):
            x_pos = layout_width - (i * folded_width)
            if x_pos <= 0:
                break

            # Top edge (from top downwards)
            top_points = QPolygonF([QPointF(x_pos, 0.0), QPointF(x_pos, float(line_length_mm))])
            top_polyline = QgsLayoutItemPolyline(top_points, layout)
            top_polyline.setSymbol(base_symbol.clone())
            top_polyline.setId("Folding line")
            layout.addLayoutItem(top_polyline)

            # Bottom edge (from bottom upwards)
            bottom_points = QPolygonF([
                QPointF(x_pos, layout_height),
                QPointF(x_pos, layout_height - float(line_length_mm)),
            ])
            bottom_polyline = QgsLayoutItemPolyline(bottom_points, layout)
            bottom_polyline.setSymbol(base_symbol.clone())
            bottom_polyline.setId("Folding line")
            layout.addLayoutItem(bottom_polyline)

        # -----------------------------
        # Horizontal folding lines (left & right)
        # -----------------------------
        num_horizontal_lines = int(layout_height // folded_height)
        if num_horizontal_lines < 1:
            num_horizontal_lines = 0

        for j in range(1, num_horizontal_lines + 1):
            y_pos = layout_height - (j * folded_height)
            if y_pos <= 0:
                break

            # Left edge (from left inward)
            left_points = QPolygonF([QPointF(0.0, y_pos), QPointF(float(line_length_mm), y_pos)])
            left_polyline = QgsLayoutItemPolyline(left_points, layout)
            left_polyline.setSymbol(base_symbol.clone())
            left_polyline.setId("Folding line")
            layout.addLayoutItem(left_polyline)

            # Right edge (from right inward)
            right_points = QPolygonF([
                QPointF(layout_width, y_pos),
                QPointF(layout_width - float(line_length_mm), y_pos),
            ])
            right_polyline = QgsLayoutItemPolyline(right_points, layout)
            right_polyline.setSymbol(base_symbol.clone())
            right_polyline.setId("Folding line")
            layout.addLayoutItem(right_polyline)

    # -------------------------
    # UI event handler
    # -------------------------
    def on_btnPlaceMarks_clicked(self):
        layout_name = self.dlg.comboLayout.currentText()
        folded_format_str = self.dlg.comboPaperSize.currentText()
        line_length = self.dlg.spinLineLength.value()
        line_thickness = self.dlg.spinLineThickness.value()

        self.place_folding_marks(layout_name, folded_format_str, line_length, line_thickness)
        self.dlg.accept()