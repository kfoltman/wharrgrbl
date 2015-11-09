import math
import sys
from config import Settings
from sender import SerialDeviceFinder
from PyQt4 import QtCore, QtGui
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
    
class ConfigTableView(QtGui.QTableView):
    def __init__(self, parent, config_model):
        QtGui.QTableView.__init__(self, parent)
        self.setModel(config_model)
        self.setColumnWidth(0, 80)
        self.setColumnWidth(1, 500)
        self.setMinimumWidth(700)
        self.setMinimumHeight(300)
        self.verticalHeader().show()
        self.resizeRowsToContents()

class MachineConfigDialog(QtGui.QDialog):
    def __init__(self, config_model):
        QtGui.QDialog.__init__(self)
        self.setWindowTitle("Grbl configuration")
        self.tableView = ConfigTableView(self, config_model)
    def showEvent(self, e):
        self.tableView.setFocus()
        #self.add(self.tableView)

class AppConfigDialog(QtGui.QDialog):
    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.finder = SerialDeviceFinder()
        self.comPorts = QtGui.QStandardItemModel()
        devices = [(None, "Autodetect the device")] + list(self.finder.devices)
        self.defaultDeviceIndex = 0
        for device, name in sorted(devices, cmp = lambda i1, i2: cmp(i1[0], i2[0])):
            if device == Settings.device:
                self.defaultDeviceIndex = self.comPorts.rowCount()
            self.comPorts.appendRow([QtGui.QStandardItem(device or "Autodetect"), QtGui.QStandardItem(name)])

        self.initUI()
        self.setWindowTitle("Wharrgrbl configuration")
    def initUI(self):
        layout = QtGui.QFormLayout()
        self.comboPorts = QtGui.QComboBox()
        self.comboPorts.setModel(self.comPorts)
        self.labelPortName = QtGui.QLabel()
        buttons = QtGui.QHBoxLayout()
        button = QtGui.QPushButton("Cancel")
        button.clicked.connect(self.reject)
        buttons.addWidget(button)
        button = QtGui.QPushButton("&OK")
        button.setDefault(True)
        button.clicked.connect(self.accept)
        buttons.addWidget(button)
        
        layout.addRow("Serial port", self.comboPorts)
        layout.addRow("Description", self.labelPortName)
        layout.addRow(buttons)
        self.setLayout(layout)
        self.comboPorts.activated.connect(self.updatePortName)
        self.updatePortName(self.defaultDeviceIndex)
    def updatePortName(self, i):
        self.labelPortName.setText("%s" % self.comPorts.data(self.comPorts.index(i, 1)).toString())
    def showEvent(self, e):
        #self.tableView.setFocus()
        #self.add(self.tableView)
        pass
    def save(self):
        print "Not implemented yet"
