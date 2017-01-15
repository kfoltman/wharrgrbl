from PyQt4.QtCore import *
from PyQt4.QtGui import *
from helpers.gui import *
import tool
import sys

defaultTool = tool.CAMTool(diameter = 2.0, feed = 200.0, plunge = 100.0, depth = 0.3)

class ToolEditDlg(PropertyDialog):
    properties = [
        FloatEditableProperty("Diameter", "diameter", "%0.2f", min = 0),
        FloatEditableProperty("Depth of cut", "depth", "%0.2f", min = 0, allow_none = True),
        FloatEditableProperty("Length", "length", "%0.2f", min = 0, allow_none = True, none_value = "Unknown"),
        FloatEditableProperty("Feed rate", "feed", "%0.1f", min = 0),
        FloatEditableProperty("Plunge rate", "plunge", "%0.1f", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f", min = 0),
    ]
    def __init__(self, tool):
        PropertyDialog.__init__(self, tool, ToolEditDlg.properties)
