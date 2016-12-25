from PyQt4.QtCore import *
from PyQt4.QtGui import *
from helpers.gui import *
import tool
import sys

defaultTool = tool.CAMTool(diameter = 2.0, feed = 200.0, plunge = 100.0, depth = 0.3)

class ToolEditDlg(QDialog):
    properties = [
        FloatEditableProperty("Diameter", "diameter", "%0.2f", min = 0),
        FloatEditableProperty("Depth of cut", "depth", "%0.2f", min = 0, allow_none = True),
        FloatEditableProperty("Length", "length", "%0.2f", min = 0, allow_none = True, none_value = "Unknown"),
        FloatEditableProperty("Feed rate", "feed", "%0.1f", min = 0),
        FloatEditableProperty("Plunge rate", "plunge", "%0.1f", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f", min = 0),
    ]
    def __init__(self, tool):
        QDialog.__init__(self)
        self.tool = tool
        self.origValues = { prop.attribute: getattr(self.tool, prop.attribute) for prop in self.properties }
        self.initUI()
    def initUI(self):
        def lineEdit():
            return QLineEdit()
        self.grid = PropertySheetWidget(self.properties)
        self.grid.setObjects([self.tool])
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.grid)
        buttons = QHBoxLayout()
        pb = QPushButton("Cancel")
        pb.clicked.connect(self.reject)
        buttons.addWidget(pb)
        pb = QPushButton("&OK")
        pb.setDefault(True)
        pb.clicked.connect(self.accept)
        buttons.addWidget(pb)
        self.layout().addLayout(buttons)
    def rollback(self):
        for k, v in self.origValues.items():
            setattr(self.tool, k, v)
