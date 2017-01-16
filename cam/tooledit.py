from PyQt4.QtCore import *
from PyQt4.QtGui import *
from helpers.gui import *
import tool

class ToolEditDlg(PropertyDialog):
    properties = [
        FloatEditableProperty("Diameter", "diameter", "%0.2f", min = 0),
        FloatEditableProperty("Depth of cut", "depth", "%0.2f", min = 0),
        FloatEditableProperty("Length", "length", "%0.2f", min = 0, allow_none = True, none_value = "Unknown"),
        FloatEditableProperty("Feed rate", "feed", "%0.1f", min = 0),
        FloatEditableProperty("Plunge rate", "plunge", "%0.1f", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f", min = 0, allow_none = True, none_value = "Material default"),
    ]
    def __init__(self, tool):
        PropertyDialog.__init__(self, tool, ToolEditDlg.properties)
