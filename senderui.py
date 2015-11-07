import math
import sys
from PyQt4 import QtCore, QtGui
from sender import sender
from helpers.gui import MenuHelper
from sender.config import Settings, Fonts
from sender.config_window import *
from sender.cmdlist import *

class CNCApplication(QtGui.QApplication):
    pass
        
class GrblStateMachineWithSignals(QtCore.QObject, sender.GrblStateMachine):
    status = QtCore.pyqtSignal([])
    line_received = QtCore.pyqtSignal([str])
    def __init__(self, history_model, config_model, *args, **kwargs):
        QtCore.QObject.__init__(self)
        self.config_model = config_model
        self.history_model = history_model
        self.job_model = None
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
        context.set_status('Confirmed')
    def error(self, line, context, error):
        context.set_status(error)
    def handle_variable_value(self, var, value, comment):
        self.config_model.handleVariableValue(var, value, comment)
    def try_pull(self):
        while True:
            cmd = None
            if self.job_model is not None and self.job_model.running:
                cmd = self.job_model.getNextCommand()
            if cmd is None:
                cmd = self.history_model.getNextCommand()
            if cmd is None:
                return
            error = sender.GrblStateMachine.send_line(self, cmd.command, cmd)
            if error is not None:
                cmd.rollback()
                return
            else:
                cmd.set_status("Sent")
    def set_job(self, job):
        self.job_model = job

class GrblInterface(QtCore.QObject):
    status = QtCore.pyqtSignal([])
    line_received = QtCore.pyqtSignal([str])
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.grbl = None
        self.job = None
        self.history = GcodeJobModel()
        self.config_model = GrblConfigModel(self)
        self.startTimer(Settings.timer_interval)
    def connectToGrbl(self):
        self.grbl = GrblStateMachineWithSignals(self.history, self.config_model)
        self.grbl.status.connect(self.onStatus)
        self.grbl.line_received.connect(self.onLineReceived)
        self.grbl.set_job(self.job)
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
    def sendLine(self, line):
        if self.grbl is not None:
            self.grbl.send_line(line)
        else:
            raise ValueError("connection not established")
    def setJob(self, job):
        self.job = job
        if self.grbl is not None:
            self.grbl.set_job(job)
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
        self.grbl.sendLine("G91 G0 X%f Y%f Z%f" % (m * dx, m * dy, m * dz))
    def handleSteps(self, var, dist):
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
        for d in Settings.xysteps:
            addButton(steps, 'distxy', d)

        frm = QtGui.QFrame()
        frm.setFrameStyle(QtGui.QFrame.VLine)
        layout.addWidget(frm, 0, 4, 4, 1)

        steps = QtGui.QVBoxLayout()
        layout.addLayout(steps, 0, 6, 4, 1)
        for d in Settings.zsteps:
            addButton(steps, 'distz', d)
        self.steps_changed.emit()

class HistoryLineEdit(QtGui.QLineEdit):
    def __init__(self, history):
        QtGui.QLineEdit.__init__(self)
        self.history = history
        self.history_cursor = 0
        self.history.rowsInserted.connect(self.onHistoryRowsInserted)
    def onHistoryRowsInserted(self, index, ifrom, ito):
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
        self.tableview.setMinimumWidth(620)
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
        layout.setAlignment(QtCore.Qt.AlignTop)
        layout.setColumnMinimumWidth(1, 14 * 6)
        layout.setColumnMinimumWidth(3, 14 * 6)
        alignment = {"|" : QtCore.Qt.AlignHCenter, "<" : QtCore.Qt.AlignLeft, ">" : QtCore.Qt.AlignRight}
        for col, name in enumerate(['|', ">Work", "|Zero", ">Machine"]):
            label = QtGui.QLabel(name[1:])
            layout.addWidget(label, 0, col, alignment[name[0]] | QtCore.Qt.AlignTop)
        alignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
        for index, axis in enumerate(['X', 'Y', 'Z']):
            label = QtGui.QLabel(axis)
            label.setScaledContents(False)
            label.setFont(Fonts.bigBoldFont)
            layout.addWidget(label, index + 1, 0, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
            coordWidget = QtGui.QLabel("-")
            coordWidget.setFont(Fonts.bigBoldFont)
            coordWidget.setAlignment(alignment)
            layout.addWidget(coordWidget, index + 1, 1)
            self.workWidgets[axis] = coordWidget
            zeroWidget = QtGui.QPushButton("0")
            def q(axis):
                return lambda: self.zeroAxis(axis)
            zeroWidget.setMaximumWidth(32)
            zeroWidget.clicked.connect(q(axis))
            layout.addWidget(zeroWidget, index + 1, 2)
            coordWidget = QtGui.QLabel("-")
            coordWidget.setFont(Fonts.bigFont)
            coordWidget.setAlignment(alignment)
            layout.addWidget(coordWidget, index + 1, 3)
            self.machineWidgets[axis] = coordWidget
        widget = QtGui.QGroupBox("Coordinates")
        widget.setLayout(layout)
        grid.addWidget(widget, 1, 0)

        self.jogger = CNCJogger(self.grbl)
        grid.addWidget(self.jogger, 1, 2, 1, 1)
        self.macros = QtGui.QHBoxLayout()
        for name, command in Settings.macros:
            button = QtGui.QPushButton(name)
            def q(command):
                return lambda: self.grbl.sendLine(command)
            button.clicked.connect(q(command))
            self.macros.addWidget(button)
        grid.addLayout(self.macros, 2, 0, 1, 3)
        
        self.setLayout(grid)

    def zeroAxis(self, axis):
        print "Zero axis %s" % axis
        self.grbl.sendLine('G90 G10 L20 P0 %s0' % axis)
        
    def onTableDataChanged(self, topleft, bottomright):
        if bottomright.row() > self.tableMax:
            self.tableMax = bottomright.row()
            self.tableview.resizeRowToContents(bottomright.row())
            self.tableview.scrollTo(bottomright.sibling(bottomright.row() + 1, 1))
        self.tableview.repaint()
    
    def onTableRowsInserted(self, index, ifrom, ito):
        self.tableview.resizeRowToContents(ifrom)
    
    def sendCommand(self):
        cmd = str(self.cmdWidget.text())
        self.cmdHistory.append(cmd)
        self.grbl.sendLine(cmd)
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

class CNCJobControl(QtGui.QGroupBox):
    def __init__(self, grbl):
        QtGui.QWidget.__init__(self)
        self.setTitle("Job control")
        self.grbl = grbl
        self.initUI()
    def initUI(self):
        layout = QtGui.QVBoxLayout()
        self.jobCommands = QtGui.QTableView()
        self.jobCommands.setModel(GcodeJobModel())
        self.jobCommands.setColumnWidth(0, 380)
        self.jobCommands.setColumnWidth(1, 120)
        self.jobCommands.setMinimumWidth(520)
        self.jobCommands.setMinimumHeight(300)
        self.jobCommands.resizeRowsToContents()
        layout.addWidget(self.jobCommands)
        layout.addLayout(self.initButtons())
        self.setLayout(layout)
    def initButtons(self):
        buttonList = [
            ('Load', self.onFileOpen),
            ('Run', self.onJobRun),
            ('Pause', self.onJobPause),
            ('Cancel', self.onJobCancel),
        ]
        buttons = QtGui.QHBoxLayout()
        for name, func in buttonList:
            button = QtGui.QPushButton(name)
            button.clicked.connect(func)
            buttons.addWidget(button)
        return buttons
    def onJobTableDataChanged(self, topleft, bottomright):
        self.jobCommands.resizeRowToContents(bottomright.row())
        self.jobCommands.scrollTo(bottomright.sibling(bottomright.row() + 1, 1))
        self.jobCommands.repaint()
    def setJob(self, job):
        job.dataChanged.connect(self.onJobTableDataChanged)    
        self.jobCommands.setModel(job)
        self.jobCommands.scrollTo(job.index(0, 0))
        self.jobCommands.resizeRowsToContents()
    def loadFile(self, fname):
        job = GcodeJobModel()
        for l in open(fname, "r").readlines():
            l = l.strip()
            if l != '':
                job.addCommand(l)
        self.grbl.setJob(job)
        self.setJob(job)
    def onJobRun(self):
        job = self.grbl.job
        if job is not None:
            if not job.running:
                job.rewind()
                job.running = True
    def onJobPause(self):
        job = self.grbl.job
        if job is not None:
            job.running = not job.running
    def onJobCancel(self):
        job = self.grbl.job
        if job is not None:
            job.cancel()
    def onFileOpen(self):
        fname = QtGui.QFileDialog.getOpenFileName(self, 'Open file', '.', "Gcode files (*.nc *.gcode)")
        if fname != '':
            self.loadFile(fname)



class CNCMainWindow(QtGui.QMainWindow, MenuHelper):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)
        MenuHelper.__init__(self)
        self.grbl = GrblInterface()
        self.initUI()
        self.grbl.connectToGrbl()
        
    def initUI(self):
        self.pendant = CNCPendant(self.grbl)
        self.jobs = CNCJobControl(self.grbl)

        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu("&File")
        fileMenu.addAction(self.makeAction("&Open", "Ctrl+O", "Open a file", self.jobs.onFileOpen))
        fileMenu.addAction(self.makeAction("E&xit", "Ctrl+Q", "Exit the application", self.close))
        fileMenu = menuBar.addMenu("&Job")
        fileMenu.addAction(self.makeAction("&Run", "F5", "Run the job", self.jobs.onJobRun))
        fileMenu.addAction(self.makeAction("&Pause/resume", "F7", "Pause/resume the job", self.jobs.onJobPause))
        fileMenu.addAction(self.makeAction("&Cancel", "F9", "Cancel the job", self.jobs.onJobCancel))
        machineMenu = menuBar.addMenu("&Machine")
        machineMenu.addAction(self.makeAction("&Go home", "F4", "Go to G28 predefined position", self.onMachineHome))
        machineMenu.addAction(self.makeAction("&Homing cycle", "Ctrl+H", "Start homing cycle", self.onMachineHomingCycle))
        machineMenu.addAction(self.makeAction("&Feed hold", "F8", "Pause the machine", self.onMachineFeedHold))
        machineMenu.addAction(self.makeAction("&Restart", "F6", "Restart the machine", self.onMachineRestart))
        machineMenu.addAction(self.makeAction("&Soft reset", "Ctrl+X", "Soft reset the machine", self.onMachineSoftReset))
        machineMenu.addAction(self.makeAction("&Kill alarm", "", "Disarm the alarm", self.onMachineKillAlarm))
        machineMenu.addAction(self.makeAction("&Configuration", "Ctrl+P", "Set machine configuration", self.onMachineConfiguration))
        self.updateActions()
        layout = QtGui.QHBoxLayout()
        layout.addWidget(self.pendant)
        layout.addWidget(self.jobs)
        widget = QtGui.QGroupBox()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.setWindowTitle("KF's GRBL controller")
        self.configDialog = MachineConfigDialog(self.grbl.config_model)
        self.pendant.cmdWidget.setFocus()
        
    def onMachineHome(self):
        self.grbl.sendLine('G28')
    def onMachineFeedHold(self):
        self.grbl.grbl.pause()
    def onMachineRestart(self):
        self.grbl.grbl.restart()
    def onMachineSoftReset(self):
        self.grbl.grbl.soft_reset()
    def onMachineKillAlarm(self):
        self.grbl.sendLine('$X')
    def onMachineHomingCycle(self):
        self.grbl.sendLine('$H')
    def onMachineConfiguration(self):
        self.grbl.sendLine('$$')
        self.configDialog.show()

def main():    
    app = CNCApplication(sys.argv)
    w = CNCMainWindow()
    if len(sys.argv) > 1:
        w.loadFile(sys.argv[1])
    w.show()
    
    sys.exit(app.exec_())

main()
