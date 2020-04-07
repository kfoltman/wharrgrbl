from PyQt5.QtCore import *
from PyQt5.QtGui import *
from helpers.gui import *
import tool

class MaterialEditDlg(PropertyDialog):
    properties = [
        FloatEditableProperty("Thickness", "thickness", "%0.2f", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f", min = 0),
    ]
    def __init__(self, material):
        PropertyDialog.__init__(self, material, MaterialEditDlg.properties)
