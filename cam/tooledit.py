from PyQt4.QtCore import *
from PyQt4.QtGui import *
from helpers.gui import *
from tool import CAMTool

class ToolEditDlg(PropertyDialog):
    def __init__(self, tool):
        PropertyDialog.__init__(self, tool, CAMTool.properties)
        self.setWindowTitle("Tool properties")
