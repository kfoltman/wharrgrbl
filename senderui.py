import math
import sys
from PyQt4 import QtCore, QtGui
from sender import sender
from helpers.gui import MenuHelper
from sender.config import Settings, Fonts
from sender.config_window import *

class CNCApplication(QtGui.QApplication):
    pass

class GcodeExecCommand:
    def __init__(self, command, status):
        self.command = command
        self.status = status

class GcodeExecHistoryModel(QtCore.QAbstractTableModel):
    def __init__(self):
        QtCore.QAbstractTableModel.__init__(self)
        self.commands = []
        self.history_pos = 0
    def pull(self):
        if self.history_pos >= len(self.commands):
            return None
        cmd = self.commands[self.history_pos]
        self.history_pos += 1
        return cmd
    def unpull(self):
        self.history_pos -= 1
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
        context = GcodeExecCommand(cmd, "Queued")
        l = len(self.commands)
        context.pos = l
        self.beginInsertRows(QtCore.QModelIndex(), l, l)
        self.commands.append(context)
        self.endInsertRows()
        return context
    def changeStatus(self, context, new_status):
        context.status = new_status
        self.dataChanged.emit(self.index(context.pos, 1), self.index(context.pos, 1))
    def flags(self, index):
        if index.column() == 0:
            return QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsEnabled
        return QtCore.Qt.NoItemFlags

class GrblStateMachineWithSignals(QtCore.QObject, sender.GrblStateMachine):
    status = QtCore.pyqtSignal([])
    line_received = QtCore.pyqtSignal([str])
    def __init__(self, history_model, config_model, *args, **kwargs):
        QtCore.QObject.__init__(self)
        self.config_model = config_model
        self.history_model = history_model
        self.current_status = ('Initialized', {})
        sender.GrblStateMachine.__init__(self, Settings.device, Settings.speed)
    def handle_line(self, line):
        if not (line.startswith('<') and line.endswith('>')):
            self.line_received.emit(line)
        return sender.GrblStateMachine.handle_line(self, line)
    def process_cooked_status(self, mode, args):
        self.current_status = (mode, args)
        self.status.emit()
    def get_status(self):
        return self.current_status
    def send_line(self, line):
        self.history_model.addCommand(line)
    def confirm(self, line, context):
        self.history_model.changeStatus(context, 'Confirmed')
    def error(self, line, context, error):
        self.history_model.changeStatus(context, error)
    def handle_variable_value(self, var, value, comment):
        self.config_model.handleVariableValue(var, value, comment)
    def try_pull(self):
        while True:
            context = self.history_model.pull()
            if context is None:
                return
            error = sender.GrblStateMachine.send_line(self, context.command, context)
            if error is not None:
                self.history_model.unpull()
                return
            else:
                context.status = "Sent"

class GrblInterface(QtCore.QObject):
    status = QtCore.pyqtSignal([])
    line_received = QtCore.pyqtSignal([str])
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.grbl = None
        self.history = GcodeExecHistoryModel()
        self.config_model = GrblConfigModel(self)
        self.startTimer(Settings.timer_interval)
    def connectToGrbl(self):
        self.grbl = GrblStateMachineWithSignals(self.history, self.config_model)
        self.grbl.status.connect(self.onStatus)
        self.grbl.line_received.connect(self.onLineReceived)
    def disconnectFromGrbl(self):
        if self.grbl is not None:
            self.grbl.close()
        self.grbl = None
    def getStatus(self):
        if self.grbl:
            return self.grbl.get_status()
        else:
            return ('Not connected', {})
    def onStatus(self):
        self.status.emit()
    def onLineReceived(self, line):
        self.line_received.emit(line)
    def timerEvent(self, e):
        if self.grbl is not None:
            self.grbl.ask_for_status()
            while self.grbl.handle_input():
                pass
            self.grbl.try_pull()
        else:
            self.onStatus('Disconnected', {})
    def send_line(self, line):
        if self.grbl is not None:
            self.grbl.send_line(line)
        else:
            raise ValueError("connection not established")
            
    def canAcceptCommands(self, mode):
        return mode not in ['Home', 'Alarm']

class CNCJogger(QtGui.QGroupBox):
    steps_changed = QtCore.pyqtSignal([])
    def __init__(self, grbl):
        QtGui.QGroupBox.__init__(self)
        self.setTitle("Jogging (Alt+arrows/PgUp/PgDn)")
        self.grbl = grbl
        self.distxy = 10
        self.distz = 1
        self.initUI()
    def checkKeyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Left:
            self.handleButton('X', -1)
        elif e.key() == QtCore.Qt.Key_Up:
            self.handleButton('Y', 1)
        elif e.key() == QtCore.Qt.Key_Down:
            self.handleButton('Y', -1)
        elif e.key() == QtCore.Qt.Key_Right:
            self.handleButton('X', 1)
        elif e.key() == QtCore.Qt.Key_PageUp:
            self.handleButton('Z', 1)
        elif e.key() == QtCore.Qt.Key_PageDown:
            self.handleButton('Z', -1)
        else:
            return False
        return True
    def makeButton(self, name, layout, locx, locy):
        button = QtGui.QPushButton(name)
        button.setFont(Fonts.bigBoldFont)
        button.clicked.connect(lambda: self.handleButton(name[0], 1 if name[1] == '+' else -1))
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(button, locx, locy)
    def handleButton(self, axis, dist):
        dx = 1 if axis == 'X' else 0
        dy = 1 if axis == 'Y' else 0
        dz = 1 if axis == 'Z' else 0
        if axis == 'Z':
            m = self.distz * dist
        else:
            m = self.distxy * dist
        if QtGui.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
            m *= 10
        self.grbl.send_line("G91 G0 X%f Y%f Z%f" % (m * dx, m * dy, m * dz))
    def handleSteps(self, var, dist):
        print var, dist
        setattr(self, var, dist)
        self.steps_changed.emit()
    def initUI(self):        
        layout = QtGui.QGridLayout()
        self.setLayout(layout)
        self.makeButton("Y+", layout, 0, 1)
        self.makeButton("X-", layout, 1, 0)
        self.makeButton("X+", layout, 1, 2)
        self.makeButton("Y-", layout, 2, 1)
        self.makeButton("Z+", layout, 0, 5)
        self.makeButton("Z-", layout, 2, 5)
        def addButton(steps, var, d):
            rb = QtGui.QRadioButton("%smm" % d)
            rb.setAutoExclusive(False)
            rb.clicked.connect(lambda: self.handleSteps(var, d))
            self.steps_changed.connect(lambda: rb.setChecked(getattr(self, var) == d))
            steps.addWidget(rb)
        steps = QtGui.QVBoxLayout()
        layout.addLayout(steps, 0, 3, 4, 1)
        for d in [0.1, 1, 10, 50]:
            addButton(steps, 'distxy', d)

        frm = QtGui.QFrame()
        frm.setFrameStyle(QtGui.QFrame.VLine)
        layout.addWidget(frm, 0, 4, 4, 1)

        steps = QtGui.QVBoxLayout()
        layout.addLayout(steps, 0, 6, 4, 1)
        for d in [0.1, 1, 10, 50]:
            addButton(steps, 'distz', d)
        self.steps_changed.emit()

class HistoryLineEdit(QtGui.QLineEdit):
    def __init__(self, history):
        QtGui.QLineEdit.__init__(self)
        self.history = history
        self.history_cursor = 0
        self.history.rowsInserted.connect(self.onHistoryRowsInserted)
    def onHistoryRowsInserted(self, index, ifrom, ito):
        print "Insert %d-%d" % (ifrom, ito)
        #if self.history_cursor >= ifrom:
        #    self.history_cursor += ito - ifrom + 1
        self.history_cursor = ito + 1
    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Up:
            if self.history_cursor > 0:
                self.history_cursor -= 1
                self.setText(self.history.data(self.history.index(self.history_cursor, 0), QtCore.Qt.DisplayRole))
                self.selectAll()
        elif e.key() == QtCore.Qt.Key_Down:
            if self.history_cursor < self.history.rowCount(QtCore.QModelIndex()) - 1:
                self.history_cursor += 1
                self.setText(self.history.data(self.history.index(self.history_cursor, 0), QtCore.Qt.DisplayRole))
                self.selectAll()
        else:
            QtGui.QLineEdit.keyPressEvent(self, e)

class CNCPendant(QtGui.QGroupBox):
    def __init__(self, grbl):
        QtGui.QWidget.__init__(self)
        self.setTitle("Machine control")
        self.grbl = grbl
        self.initUI()
        self.updateStatusWidgets(*grbl.getStatus())
        self.grbl.status.connect(self.onStatus)
        self.grbl.line_received.connect(self.onLineReceived)
        self.cmdHistory = []
        
    def keyPressEvent(self, e):
        if e.key() == QtCore.Qt.Key_Return or e.key() == QtCore.Qt.Key_Enter:
            self.cmdButton.animateClick()
        if e.modifiers() & QtCore.Qt.AltModifier:
            if self.jogger.checkKeyPressEvent(e):
                return
        return QtGui.QGroupBox.keyPressEvent(self, e)
    def initUI(self):        
        cmdLayout = QtGui.QHBoxLayout()
        self.cmdWidget = HistoryLineEdit(self.grbl.history)
        cmdLayout.addWidget(self.cmdWidget)
        self.cmdButton = QtGui.QPushButton("Send")
        self.cmdButton.clicked.connect(self.sendCommand)
        self.cmdButton.setDefault(True)
        cmdLayout.addWidget(self.cmdButton)
        
        self.modeWidget = QtGui.QLabel()
        self.modeWidget.setFont(Fonts.mediumBoldFont)
        self.workWidgets = {}
        self.machineWidgets = {}

        grid = QtGui.QGridLayout()

        layout = QtGui.QFormLayout()
        layout.setLabelAlignment(QtCore.Qt.AlignRight)
        self.tableview = QtGui.QTableView()
        self.tableview.setModel(self.grbl.history)
        self.tableview.setColumnWidth(0, 480)
        self.tableview.setColumnWidth(1, 160)
        self.tableview.setMinimumWidth(700)
        self.tableview.setMinimumHeight(300)
        self.tableview.verticalHeader().hide()
        self.tableview.resizeRowsToContents()
        self.tableMax = 0
        self.grbl.history.dataChanged.connect(self.onTableDataChanged)
        self.grbl.history.rowsInserted.connect(self.onTableRowsInserted)
        layout.addWidget(self.tableview)
        layout.addRow("Command:", cmdLayout)
        layout.addRow("Status:", self.modeWidget)
        grid.addLayout(layout, 0, 0, 1, 3)
        
        layout = QtGui.QGridLayout()
        layout.setColumnMinimumWidth(1, 14 * 6)
        layout.setColumnMinimumWidth(2, 14 * 6)
        alignment = {"|" : QtCore.Qt.AlignCenter, "<" : QtCore.Qt.AlignLeft, ">" : QtCore.Qt.AlignRight}
        for col, name in enumerate(['|Coord', ">Work", ">Machine", "|Zero"]):
            label = QtGui.QLabel(name[1:])
            label.setAlignment(alignment[name[0]] | QtCore.Qt.AlignBottom)
            layout.addWidget(label, 0, col)
        alignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
        for index, axis in enumerate(['X', 'Y', 'Z']):
            label = QtGui.QLabel(axis)
            label.setFont(Fonts.bigBoldFont)
            label.setAlignment(QtCore.Qt.AlignCenter | QtCore.Qt.AlignVCenter)
            layout.addWidget(label, index + 1, 0)
            coordWidget = QtGui.QLabel("-")
            coordWidget.setFont(Fonts.bigFont)
            coordWidget.setAlignment(alignment)
            layout.addWidget(coordWidget, index + 1, 1)
            self.workWidgets[axis] = coordWidget
            coordWidget = QtGui.QLabel("-")
            coordWidget.setFont(Fonts.bigFont)
            coordWidget.setAlignment(alignment)
            layout.addWidget(coordWidget, index + 1, 2)
            self.machineWidgets[axis] = coordWidget
            zeroWidget = QtGui.QPushButton("Zero")
            def q(axis):
                return lambda: self.zeroAxis(axis)
            zeroWidget.clicked.connect(q(axis))
            layout.addWidget(zeroWidget, index + 1, 3)
        grid.addLayout(layout, 1, 0)

        self.jogger = CNCJogger(self.grbl)
        grid.addWidget(self.jogger, 1, 2, 1, 1)
        
        self.setLayout(grid)

    def zeroAxis(self, axis):
        print "Zero axis %s" % axis
        self.grbl.send_line('G90 G10 L20 P0 %s0' % axis)
        
    def onTableDataChanged(self, topleft, bottomright):
        if bottomright.row() > self.tableMax:
            self.tableMax = bottomright.row()
            self.tableview.resizeRowToContents(bottomright.row())
            self.tableview.scrollTo(bottomright.sibling(bottomright.row() + 1, 1))
        self.repaint()
    
    def onTableRowsInserted(self, index, ifrom, ito):
        self.tableview.resizeRowToContents(ifrom)
    
    def sendCommand(self):
        cmd = str(self.cmdWidget.text())
        self.cmdHistory.append(cmd)
        self.grbl.send_line(cmd)
        self.cmdWidget.setText('')
    def updateStatusWidgets(self, mode, args):
        fmt = "%0.3f"
        self.modeWidget.setText(mode)
        self.cmdButton.setEnabled(self.grbl.canAcceptCommands(mode))
        self.jogger.setEnabled(self.grbl.canAcceptCommands(mode))
        def update(axis, pos):
            for i, a in enumerate(['X', 'Y', 'Z']):
                axis[a].setText(fmt % pos[i])
        def noUpdate(axis):
            for a in ('X', 'Y', 'Z'):
                axis[a].setText('')
        if 'WPos' in args:
            update(self.workWidgets, args['WPos'])
        else:
            noUpdate(self.workWidgets)
        if 'MPos' in args:
            update(self.machineWidgets, args['MPos'])
        else:
            noUpdate(self.machineWidgets)

    def onStatus(self):
        self.updateStatusWidgets(*self.grbl.getStatus())
    def onLineReceived(self, line):
        print "Received:", line

class CNCMainWindow(QtGui.QMainWindow, MenuHelper):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        MenuHelper.__init__(self)
        self.grbl = GrblInterface()
        self.initUI()
        self.grbl.connectToGrbl()
        
    def initUI(self):
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu("&File")
        fileMenu.addAction(self.makeAction("&Open", "Ctrl+O", "Open a file", self.onFileOpen))
        fileMenu.addAction(self.makeAction("E&xit", "Ctrl+Q", "Exit the application", self.close))
        fileMenu = menuBar.addMenu("&Job")
        fileMenu.addAction(self.makeAction("&Run", "F5", "Run the job", self.onJobRun))
        fileMenu.addAction(self.makeAction("&Cancel", "F9", "Cancel the job", self.onJobCancel))
        machineMenu = menuBar.addMenu("&Machine")
        machineMenu.addAction(self.makeAction("&Go home", "F4", "Go to zero point", self.onMachineHome))
        machineMenu.addAction(self.makeAction("&Homing cycle", "Ctrl+H", "Disarm the alarm", self.onMachineKillAlarm))
        machineMenu.addAction(self.makeAction("&Feed hold", "F8", "Pause the machine", self.onMachineFeedHold))
        machineMenu.addAction(self.makeAction("&Restart", "F6", "Restart the machine", self.onMachineRestart))
        machineMenu.addAction(self.makeAction("&Soft reset", "Ctrl+X", "Soft reset the machine", self.onMachineSoftReset))
        machineMenu.addAction(self.makeAction("&Kill alarm", "", "Disarm the alarm", self.onMachineKillAlarm))
        machineMenu.addAction(self.makeAction("&Configuration", "Ctrl+P", "Set machine configuration", self.onMachineConfiguration))
        self.updateActions()
        self.pendant = CNCPendant(self.grbl)
        self.setCentralWidget(self.pendant)
        self.setWindowTitle("KF's GRBL controller")
        self.configDialog = MachineConfigDialog(self.grbl.config_model)
        self.pendant.cmdWidget.setFocus()
        
    def loadFile(self, fname):
        for l in open(fname, "r").readlines():
            l = l.strip()
            if l != '':
                self.grbl.send_line(l.strip())
    def onFileOpen(self):
        fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file', '.', "Gcode files (*.nc)")
        if fname != '':
            self.loadFile(fname)

    def onJobRun(self):
        pass
    def onJobCancel(self):
        pass

    def onMachineHome(self):
        self.grbl.send_line('G28')
    def onMachineFeedHold(self):
        self.grbl.grbl.pause()
    def onMachineRestart(self):
        self.grbl.grbl.restart()
    def onMachineSoftReset(self):
        self.grbl.grbl.soft_reset()
    def onMachineKillAlarm(self):
        self.grbl.send_line('$X')
    def onMachineHomingCycle(self):
        self.grbl.send_line('$H')
    def onMachineConfiguration(self):
        self.grbl.send_line('$$')
        self.configDialog.show()

def main():    
    app = CNCApplication(sys.argv)
    w = CNCMainWindow()
    if len(sys.argv) > 1:
        w.loadFile(sys.argv[1])
    w.show()
    
    sys.exit(app.exec_())

main()
