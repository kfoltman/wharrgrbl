from PyQt4.QtCore import *
from PyQt4.QtGui import *
from helpers.gui import *
from tool import CAMMaterial

class MaterialEditDlg(PropertyDialog):
    def __init__(self, material):
        PropertyDialog.__init__(self, material, CAMMaterial.properties)
        self.setWindowTitle("Material properties")
