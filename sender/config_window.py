import math
import sys
from config import Global
from sender import SerialDeviceFinder
from PyQt5 import QtCore, QtGui, QtWidgets
from helpers.gui import MenuHelper

class GrblConfigModel(QtCore.QAbstractTableModel):
    def __init__(self, grbl):
        QtCore.QAbstractTableModel.__init__(self)
        self.config = {}
        self.configRows = []
        self.grbl = grbl
    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            return ["Value", "Comment"][section]
        if orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
            return self.configRows[section]
    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            if index.row() < len(self.configRows):
                key = self.configRows[index.row()]
                if index.column() == 0:
                    return self.config[key]['value']
                elif index.column() == 1:
                    return self.config[key]['comment']
    def flags(self, index):
        if index.column() == 0:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEditable | QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.NoItemFlags
    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.config)
    def columnCount(self, parent):
        return 2
    def handleVariableValue(self, var, value, comment):
        if var not in self.configRows:
            row = len(self.configRows)
            self.beginInsertRows(QtCore.QModelIndex(), row, row)
            self.config[var] = {'value' : value, 'comment' : comment}
            self.configRows.append(var)
            self.endInsertRows()
        else:
            pos = self.configRows.index(var)
            self.config[var] = {'value' : value, 'comment' : comment}
            self.dataChanged.emit(self.index(pos, 0), self.index(pos, 1))
    def setData(self, index, value, role):
        if role == QtCore.Qt.EditRole:
            cmd = "%s=%s" % (self.configRows[index.row()], value.toString())
            self.grbl.sendLine(str(cmd))
            self.grbl.sendLine("$$")
            return True
        return False
    
class ConfigTableView(QtWidgets.QTableView):
    def __init__(self, parent, config_model):
        QtWidgets.QTableView.__init__(self, parent)
        self.setModel(config_model)
        self.setColumnWidth(0, 80)
        self.setColumnWidth(1, 500)
        self.setMinimumWidth(700)
        self.setMinimumHeight(300)
        self.verticalHeader().show()
        self.resizeRowsToContents()

class MachineConfigDialog(QtWidgets.QDialog):
    def __init__(self, config_model):
        QtWidgets.QDialog.__init__(self)
        self.setWindowTitle("Grbl configuration")
        layout = QtWidgets.QVBoxLayout(self)
        self.tableView = ConfigTableView(self, config_model)
        layout.addWidget(self.tableView)
    def showEvent(self, e):
        self.tableView.setFocus()
        #self.add(self.tableView)

class AppConfigDialog(QtWidgets.QDialog):
    def __init__(self):
        QtWidgets.QDialog.__init__(self)
        self.finder = SerialDeviceFinder()
        self.comPorts = QtGui.QStandardItemModel()
        devices = [(None, "Autodetect the device")] + list(self.finder.devices)
        self.defaultDeviceIndex = 0
        for device, name in sorted(devices, cmp = lambda i1, i2: cmp(i1[0], i2[0])):
            if device == Global.settings.device:
                self.defaultDeviceIndex = self.comPorts.rowCount()
            self.comPorts.appendRow([QtGui.QStandardItem(device or "Autodetect"), QtGui.QStandardItem(name)])
        self.initUI()
        self.setWindowTitle("Wharrgrbl configuration")
    def initUI(self):
        layout = QtWidgets.QFormLayout()
        self.comboPorts = QtWidgets.QComboBox()
        self.comboPorts.setModel(self.comPorts)
        self.comboPorts.setCurrentIndex(self.defaultDeviceIndex)
        self.labelPortName = QtWidgets.QLabel()
        self.gcodeDirectory = QtWidgets.QLineEdit()
        self.gcodeDirectoryButton = QtWidgets.QPushButton("Select")
        self.gcodeDirectoryButton.clicked.connect(self.selectGcodeDirectory)
        buttons = QtWidgets.QHBoxLayout()
        button = QtWidgets.QPushButton("Cancel")
        button.clicked.connect(self.reject)
        buttons.addWidget(button)
        button = QtWidgets.QPushButton("&OK")
        button.setDefault(True)
        button.clicked.connect(self.accept)
        buttons.addWidget(button)
        
        gcodeDirectoryLayout = QtWidgets.QHBoxLayout()
        gcodeDirectoryLayout.addWidget(self.gcodeDirectory)
        gcodeDirectoryLayout.addWidget(self.gcodeDirectoryButton)
        
        layout.addRow("Serial port", self.comboPorts)
        layout.addRow("Description", self.labelPortName)
        layout.addRow("G-Code directory", gcodeDirectoryLayout)
        layout.addRow(buttons)
        self.setLayout(layout)
        self.comboPorts.activated.connect(self.updatePortName)
        self.updatePortName(self.defaultDeviceIndex)
        self.gcodeDirectory.setText(Global.settings.gcode_directory)
    def selectGcodeDirectory(self):
        newdir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select G-Code directory", self.gcodeDirectory.text())
        if newdir != "":
            self.gcodeDirectory.setText(newdir)
    def updatePortName(self, i):
        self.labelPortName.setText("%s" % self.comPorts.data(self.comPorts.index(i, 1)))
        dev = str(self.comPorts.data(self.comPorts.index(i, 0)))
        if dev == "Autodetect":
            dev = None
        self.selectedDevice = dev
    def showEvent(self, e):
        #self.tableView.setFocus()
        #self.add(self.tableView)
        pass
    def save(self):
        Global.settings.gcode_directory = self.gcodeDirectory.text()
        Global.settings.device = self.selectedDevice
        Global.settings.save()
