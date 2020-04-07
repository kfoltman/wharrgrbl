import math
import sys
from PyQt5 import QtCore, QtGui

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
        self.cur_commands = self.commands
        self.exec_stack = []
        self.history_pos = 0
        self.running = False
    def toVis(self, cmd):
        return cmd.replace("\x85", "<Jog cancel>")
    def toHist(self, cmd):
        return cmd.replace("\x85", "")
    def getHistoryCmd(self, pos):
        if pos < len(self.commands):
            return self.toHist(self.commands[pos].command)
        return ""
    def data(self, index, role):
        if role == QtCore.Qt.DisplayRole:
            if index.row() < len(self.commands):
                if index.column() == 0:
                    return self.toVis(self.commands[index.row()].command)
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
        if parent is not None and parent.isValid():
            return 0
        return len(self.commands)
    def columnCount(self, parent):
        return 2
    def addCommand(self, cmd):
        return self.addCommands([cmd])[0]
    def addCommands(self, cmds):
        pos = len(self.commands)
        contexts = []
        self.beginInsertRows(QtCore.QModelIndex(), pos, pos + len(cmds) - 1)
        for i, cmd in enumerate(cmds):
            context = GcodeExecCommand(self, cmd, "Queued", pos + i)
            self.commands.append(context)
            contexts.append(context)
        self.endInsertRows()
        return contexts
    def flags(self, index):
        if index.column() == 0:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.NoItemFlags
    def getNextCommand(self):
        while self.history_pos >= len(self.cur_commands):
            if len(self.exec_stack) > 0:
                self.history_pos, self.cur_commands = self.exec_stack.pop()
            else:
                self.running = False
                return None
        cmd = self.commands[self.history_pos]        
        self.history_pos += 1
        return cmd
    def rollback(self):
        self.history_pos -= 1
    def rewind(self):
        self.exec_stack = []
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
    def isCancellable(self):
        return len(self.exec_stack) or (self.history_pos > 0 and self.history_pos < len(self.commands))
