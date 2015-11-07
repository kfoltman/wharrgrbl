import math
import sys
from PyQt4 import QtCore, QtGui

class GcodeExecCommand(object):
    def __init__(self, model, command, status, pos):
        self.model = model
        self.command = command
        self.status = status
        self.pos = pos
    def __str__(self):
        return "command: %s, status: %s" % (self.command, self.status)
    def set_status(self, status, refresh = True):
        self.status = status
        if refresh:
            cell = self.model.index(self.pos, 1)
            self.model.dataChanged.emit(cell, cell)
    def rollback(self):
        self.model.rollback()

class GcodeJobModel(QtCore.QAbstractTableModel):
    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self.commands = []
        self.history_pos = 0
        self.running = False
    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            if index.row() < len(self.commands):
                if index.column() == 0:
                    return self.commands[index.row()].command
                else:
                    return self.commands[index.row()].status
        return None
    def headerData(self, section, orientation, role):
        if orientation == QtCore.Qt.Horizontal and role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "Command"
            else:
                return "Status"
        #if orientation == QtCore.Qt.Vertical and role == QtCore.Qt.DisplayRole:
        #    return "%d" % (1 + section)
    def rowCount(self, parent):
        if parent.isValid():
            return 0
        return len(self.commands)
    def columnCount(self, parent):
        return 2
    def addCommand(self, cmd):
        context = GcodeExecCommand(self, cmd, "Queued", len(self.commands))
        self.beginInsertRows(QtCore.QModelIndex(), context.pos, context.pos)
        self.commands.append(context)
        self.endInsertRows()
        return context
    def flags(self, index):
        if index.column() == 0:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.NoItemFlags
    def getNextCommand(self):
        if self.history_pos >= len(self.commands):
            return None
        cmd = self.commands[self.history_pos]
        self.history_pos += 1
        return cmd
    def rollback(self):
        self.history_pos -= 1
    def rewind(self):
        self.history_pos = 0
        for cmd in self.commands:
            cmd.set_status("Queued", False)
        self.refreshAllStatuses()
    def cancel(self):
        self.running = False
        self.history_pos = len(self.commands)
        for cmd in self.commands:
            if cmd.status == "Queued":
                cmd.set_status("Cancelled", False)
        self.refreshAllStatuses()
    def refreshAllStatuses(self):
        cell1 = self.index(0, 1)
        cell2 = self.index(len(self.commands), 1)
        self.dataChanged.emit(cell1, cell2)
    def isPaused(self):
        return not self.running and self.history_pos > 0 and self.history_pos < len(self.commands)
