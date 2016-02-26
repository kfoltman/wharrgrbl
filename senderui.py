import math
import re
import sys
import time
from PyQt4 import QtCore, QtGui
from sender import sender
from helpers.gui import MenuHelper
from sender.config import Global
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
        self.current_status = ('Initialized', {}, '', None)
        sender.GrblStateMachine.__init__(self, Global.settings.device, Global.settings.speed)
    def handle_line(self, line):
        if not (line.startswith('<') and line.endswith('>')):
            self.line_received.emit(line)
        return sender.GrblStateMachine.handle_line(self, line)
    def process_cooked_status(self, mode, args):
        extra = self.current_status[3]
        if mode != self.current_status[0]:
            extra = None
        self.current_status = (mode, args, self.current_status[2], extra)
        self.status.emit()
    def get_status(self):
        return self.current_status
    def send_line(self, line):
        self.history_model.addCommand(line)
    def confirm(self, line, context):
        context.set_status('Confirmed')
    def alarm(self, line, context, message):
        self.current_status = ('Alarm', self.current_status[1], self.current_status[2], message)
    def error(self, line, context, error):
        context.set_status(error)
    def handle_variable_value(self, var, value, comment):
        self.config_model.handleVariableValue(var, value, comment)
    def set_comment(self, comment):
        cs = self.current_status
        self.current_status = (cs[0], cs[1], comment, cs[3])
    def prepare(self, line):
        line = line.strip()
        if '(' in line or ';' in line:
            is_comment = False
            is_siemens_comment = False
            line2 = ''
            comment = None
            for item in re.split('\((.*?)\)', line):
                if is_siemens_comment:
                    if is_comment:
                        comment += "(%s)" % item
                    else:
                        comment += item
                else:
                    if not is_comment:
                        sc = item.find(';')
                        if sc > 0:
                            comment = item[sc + 1:]
                            is_siemens_comment = True
                            line2 += item[0:sc]
                        else:
                            line2 += item
                    else:
                        comment = item
                is_comment = not is_comment
            line = line2
            if comment is not None:
                self.set_comment(comment)
        return line
    def try_pull(self):
        while True:
            cmd = None
            if self.job_model is not None and self.job_model.running:
                cmd = self.job_model.getNextCommand()
            if cmd is None:
                cmd = self.history_model.getNextCommand()
            if cmd is None:
                return
            command = self.prepare(cmd.command)
            if command == '':
                cmd.set_status("Empty - Ignored")
                return
            error = sender.GrblStateMachine.send_line(self, command, cmd)
            if error is not None:
                cmd.rollback()
                return
            else:
                cmd.set_status("Sent")
    def set_job(self, job):
        self.job_model = job

class GrblInterface(QtCore.QThread):
    status = QtCore.pyqtSignal([])
    # signal: line has been received
    line_received = QtCore.pyqtSignal([str])
    # internal
    line_sent = QtCore.pyqtSignal([str])
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.grbl = None
        self.job = None
        self.history = GcodeJobModel()
        self.config_model = GrblConfigModel(self)
        self.exiting = False
        self.out_queue = []
        self.line_sent.connect(self.onLineSent)
        self.start()
    def __del__(self):
        self.exiting = True
        self.wait()
    def run(self):
        while not self.exiting:
            if self.grbl is not None:
                if len(self.out_queue):
                    self.grbl.send_line(self.out_queue.pop(0))
                self.grbl.ask_for_status_if_idle()
                while self.grbl.handle_input():
                    pass
                self.grbl.try_pull()
            else:
                self.onStatus()
            time.sleep(0.01)
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
            return ('Not connected', {}, '', None)
    def onStatus(self):
        self.status.emit()
    def onLineReceived(self, line):
        self.line_received.emit(line)
    def onLineSent(self, line):
        self.out_queue.append(str(line))
    def sendLine(self, line):
        if self.grbl is not None:
            self.line_sent.emit(line)
        else:
            raise ValueError("connection not established")
    def setJob(self, job):
        self.job = job
        if self.grbl is not None:
            self.grbl.set_job(job)
    def canAcceptCommands(self, mode):
        return mode not in ['Home', 'Alarm']
    def isRunningAJob(self):
        return (self.job is not None) and self.job.running
    def isJobPaused(self):
        return (self.job is not None) and self.job.isPaused()
    def isJobCancellable(self):
        return (self.job is not None) and self.job.isCancellable()

class CNCJogger(QtGui.QGroupBox):
    steps_changed = QtCore.pyqtSignal([])
    def __init__(self, grbl):
        QtGui.QGroupBox.__init__(self)
        self.setTitle("Jogging (Alt+arrows/PgUp/PgDn)")
        self.grbl = grbl
        self.distxy = 10
        self.distz = 1
        self.speedxy = None
        self.speedz = None
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
        button.setFont(Global.fonts.bigBoldFont)
        button.setMaximumWidth(QtGui.QFontMetrics(button.font()).width(name.replace("-", "+")) + 10)
        button.clicked.connect(lambda: self.handleButton(name[0], 1 if name[1] == '+' else -1))
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(button, locx, locy)
    def handleButton(self, axis, dist):
        if axis == 'Z':
            m = self.distz * dist
            s = self.speedz
        else:
            m = self.distxy * dist
            s = self.speedxy
        if QtGui.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
            m *= 10
        if s is None:
            self.grbl.sendLine("G91 G0 %s%s" % (axis, m))
        else:
            self.grbl.sendLine("G91 G1 F%s %s%s" % (s, axis, m))
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
        self.makeButton("Z+", layout, 0, 6)
        self.makeButton("Z-", layout, 2, 6)
        def addButton(steps, var, d, v):
            rb = QtGui.QRadioButton(d)
            rb.setAutoExclusive(False)
            rb.clicked.connect(lambda: self.handleSteps(var, v))
            self.steps_changed.connect(lambda: rb.setChecked(getattr(self, var) == v))
            steps.addWidget(rb)
        def fmtfloat(v):
            if v == int(v):
                return str(int(v))
            return str(v)
        steps = QtGui.QVBoxLayout()
        for d in Global.settings.xysteps:
            addButton(steps, 'distxy', "%smm" % fmtfloat(d), d)
        layout.addLayout(steps, 0, 3, 4, 1)
        speeds = QtGui.QVBoxLayout()
        for d in Global.settings.xyspeeds:
            addButton(speeds, 'speedxy', "F%s" % fmtfloat(d) if d is not None else "Rapid", d)
        layout.addLayout(speeds, 0, 4, 4, 1)

        frm = QtGui.QFrame()
        frm.setFrameStyle(QtGui.QFrame.VLine)
        layout.addWidget(frm, 0, 5, 4, 1)

        steps = QtGui.QVBoxLayout()
        for d in Global.settings.zsteps:
            addButton(steps, 'distz', "%smm" % fmtfloat(d), d)
        layout.addLayout(steps, 0, 7, 4, 1)
        speeds = QtGui.QVBoxLayout()
        for d in Global.settings.zspeeds:
            addButton(speeds, 'speedz', "F%s" % fmtfloat(d) if d is not None else "Rapid", d)
        layout.addLayout(speeds, 0, 8, 4, 1)

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
        if int(e.modifiers() & QtCore.Qt.AltModifier) == 0:
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
        statusLayout = QtGui.QHBoxLayout()

        self.cmdWidget = HistoryLineEdit(self.grbl.history)
        cmdLayout.addWidget(self.cmdWidget)
        self.cmdButton = QtGui.QPushButton("Send")
        self.cmdButton.clicked.connect(self.sendCommand)
        self.cmdButton.setDefault(True)
        cmdLayout.addWidget(self.cmdButton)
        
        self.modeWidget = QtGui.QLabel()
        self.modeWidget.setFont(Global.fonts.mediumBoldFont)
        statusLayout.addWidget(self.modeWidget)
        def addButton(name, func):
            b = QtGui.QPushButton(name)
            b.clicked.connect(func)
            statusLayout.addWidget(b)
            return b
        self.holdButton = addButton("Hold", self.onMachineFeedHold)
        self.resumeButton = addButton("Resume", self.onMachineResume)
        self.resetButton = addButton("Soft Reset", self.onMachineSoftReset)
        self.killAlarmButton = addButton("Kill Alarm", self.onMachineKillAlarm)
        self.commentWidget = QtGui.QLabel("")

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
        
        layout.addRow(self.tableview)
        layout.addRow("Command:", cmdLayout)
        layout.addRow("Status:", statusLayout)
        layout.addRow("Last comment:", self.commentWidget)
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
            label.setFont(Global.fonts.bigBoldFont)
            layout.addWidget(label, index + 1, 0, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
            coordWidget = QtGui.QLabel("-")
            coordWidget.setFont(Global.fonts.bigBoldFont)
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
            coordWidget.setFont(Global.fonts.bigFont)
            coordWidget.setAlignment(alignment)
            layout.addWidget(coordWidget, index + 1, 3)
            self.machineWidgets[axis] = coordWidget
        widget = QtGui.QGroupBox("Coordinates")
        widget.setLayout(layout)
        grid.addWidget(widget, 1, 0)

        self.jogger = CNCJogger(self.grbl)
        grid.addWidget(self.jogger, 1, 2, 1, 1)
        self.macros = QtGui.QHBoxLayout()
        for name, command in Global.settings.macros:
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
        cmds = str(self.cmdWidget.text())
        for cmd in cmds.split(":"):
            cmd = cmd.strip()
            self.cmdHistory.append(cmd)
            self.grbl.sendLine(cmd)
        self.cmdWidget.setText('')
    def updateStatusWidgets(self, mode, args, last_comment, extra):
        fmt = "%0.3f"
        self.killAlarmButton.setEnabled(mode == "Alarm")
        if extra is not None:
            mode = "%s - %s" % (mode, extra)
        self.modeWidget.setText(mode)
        self.commentWidget.setText(last_comment)
        self.cmdButton.setEnabled(self.grbl.canAcceptCommands(mode) and not self.grbl.isRunningAJob())
        self.jogger.setEnabled(self.grbl.canAcceptCommands(mode))
        self.holdButton.setEnabled(mode not in ["Hold", "Alarm"])
        self.resumeButton.setEnabled(mode == "Hold")
        self.resetButton.setEnabled(mode != "Alarm")
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
    def onMachineHome(self):
        self.grbl.sendLine('G28')
    def onMachineFeedHold(self):
        self.grbl.grbl.pause()
    def onMachineResume(self):
        self.grbl.grbl.restart()
    def onMachineSoftReset(self):
        self.grbl.grbl.soft_reset()
    def onMachineKillAlarm(self):
        self.grbl.sendLine('$X')
    def onMachineHomingCycle(self):
        self.grbl.sendLine('$H')

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
        self.updateButtons()
    def initButtons(self):
        buttonList = [
            ('Load', self.onFileOpen),
            ('Run', self.onJobRun),
            ('Pause', self.onJobPause),
            ('Resume', self.onJobResume),
            ('Cancel', self.onJobCancel),
        ]
        self.buttons = {}
        buttons = QtGui.QHBoxLayout()
        for name, func in buttonList:
            button = QtGui.QPushButton(name)
            button.clicked.connect(func)
            buttons.addWidget(button)
            self.buttons[name] = button
        return buttons
    def onJobTableDataChanged(self, topleft, bottomright):
        self.jobCommands.resizeRowToContents(bottomright.row())
        self.jobCommands.scrollTo(bottomright.sibling(bottomright.row() + 1, 1))
        self.jobCommands.repaint()
        self.updateButtons()
    def updateButtons(self):
        self.buttons['Run'].setEnabled(self.grbl.job is not None and not self.grbl.isRunningAJob())
        self.buttons['Pause'].setEnabled(self.grbl.isRunningAJob())
        self.buttons['Resume'].setEnabled(self.grbl.isJobPaused())
        self.buttons['Cancel'].setEnabled(self.grbl.isJobCancellable())
    def setJob(self, job):
        job.dataChanged.connect(self.onJobTableDataChanged)    
        self.jobCommands.setModel(job)
        self.jobCommands.scrollTo(job.index(0, 0))
        self.jobCommands.resizeRowsToContents()
        self.updateButtons()
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
        self.updateButtons()
    def onJobPauseResume(self):
        job = self.grbl.job
        if job is not None:
            job.running = not job.running
        self.updateButtons()
    def onJobPause(self):
        job = self.grbl.job
        if job is not None:
            job.running = False
        self.updateButtons()
    def onJobResume(self):
        job = self.grbl.job
        if job is not None:
            job.running = True
        self.updateButtons()
    def onJobCancel(self):
        job = self.grbl.job
        if job is not None:
            job.cancel()
        self.updateButtons()
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
        fileMenu.addSeparator()
        fileMenu.addAction(self.makeAction("&Preferences", "Ctrl+T", "Set application configuration", self.onFilePreferences))
        fileMenu.addAction(self.makeAction("E&xit", "Ctrl+Q", "Exit the application", self.close))
        fileMenu = menuBar.addMenu("&Job")
        fileMenu.addAction(self.makeAction("&Run", "F5", "Run the job", self.jobs.onJobRun))
        fileMenu.addAction(self.makeAction("&Pause/resume", "F7", "Pause/resume the job", self.jobs.onJobPauseResume))
        fileMenu.addAction(self.makeAction("&Cancel", "F9", "Cancel the job", self.jobs.onJobCancel))
        machineMenu = menuBar.addMenu("&Machine")
        machineMenu.addAction(self.makeAction("&Go home", "F4", "Go to G28 predefined position", self.pendant.onMachineHome))
        machineMenu.addAction(self.makeAction("&Homing cycle", "Ctrl+H", "Start homing cycle", self.pendant.onMachineHomingCycle))
        machineMenu.addAction(self.makeAction("&Feed hold", "F8", "Pause the machine", self.pendant.onMachineFeedHold))
        machineMenu.addAction(self.makeAction("&Resume", "F6", "Resume the machine", self.pendant.onMachineResume))
        machineMenu.addAction(self.makeAction("&Soft reset", "Ctrl+E", "Soft reset the machine", self.pendant.onMachineSoftReset))
        machineMenu.addAction(self.makeAction("&Kill alarm", "", "Disarm the alarm", self.pendant.onMachineKillAlarm))
        machineMenu.addSeparator()
        machineMenu.addAction(self.makeAction("&Machine configuration", "Ctrl+M", "Set machine configuration", self.onMachineConfiguration))
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
    def onMachineConfiguration(self):
        self.grbl.sendLine('$$')
        self.configDialog.show()
    def onFilePreferences(self):
        prefs = AppConfigDialog()
        if prefs.exec_():
            prefs.save()

def main():    
    app = CNCApplication(sys.argv)
    Global.settings.load()
    w = CNCMainWindow()
    if len(sys.argv) > 1:
        w.jobs.loadFile(sys.argv[1])
    w.show()
    
    sys.exit(app.exec_())

main()
