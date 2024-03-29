from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from helpers.gui import *
from . import tool

class ToolEditDlg(PropertyDialog):
    properties = [
        FloatEditableProperty("Diameter", "diameter", "%0.2f mm", min = 0),
        FloatEditableProperty("Depth of cut", "depth", "%0.2f mm", min = 0),
        FloatEditableProperty("Length", "length", "%0.2f mm", min = 0, allow_none = True, none_value = "Unknown"),
        FloatEditableProperty("Feed rate", "feed", "%0.1f mm/min", min = 0),
        FloatEditableProperty("Plunge rate", "plunge", "%0.1f mm/min", min = 0),
        FloatEditableProperty("Stepover", "stepover", "%0.1f %%", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f mm", min = 0, allow_none = True, none_value = "Material default"),
    ]
    def __init__(self, tool):
        PropertyDialog.__init__(self, tool, ToolEditDlg.properties)
