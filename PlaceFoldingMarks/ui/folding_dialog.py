from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(os.path.dirname(__file__), 'folding_dialog.ui'))

class FoldingDialog(QDialog, FORM_CLASS):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)