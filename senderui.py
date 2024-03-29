import math
import re
import sys
import time
from PyQt5 import QtCore, QtGui, QtWidgets

from sender import sender
from helpers.gui import MenuHelper
from sender.jobviewer import *
from sender.config import Global
from sender.config_window import *
from sender.cmdlist import *
from sender.sender_thread import *

class CNCApplication(QtWidgets.QApplication):
    pass
        
class CNCJogger(QtWidgets.QGroupBox):
    steps_changed = QtCore.pyqtSignal([])
    def __init__(self, grbl):
        QtWidgets.QGroupBox.__init__(self)
        self.setTitle("Jogging (Alt+arrows/PgUp/PgDn, End to cancel)")
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
        elif e.key() == QtCore.Qt.Key_End or e.key() == QtCore.Qt.Key_Clear:
            self.cancelJog()
        elif e.key() == QtCore.Qt.Key_0:
            self.grbl.grbl.feed_reset()
        elif e.key() == QtCore.Qt.Key_BracketRight:
            self.grbl.grbl.feed_add10()
        elif e.key() == QtCore.Qt.Key_BracketLeft:
            self.grbl.grbl.feed_sub10()
        else:
            return False
        return True
    def makeButton(self, name, layout, locx, locy, fn = None, iconId = None):
        if iconId is not None:
            icon = QtWidgets.QApplication.style().standardIcon(iconId)
            button = QtWidgets.QPushButton(icon, name)
        else:
            button = QtWidgets.QPushButton(name)
            button.setFont(Global.fonts.bigBoldFont)
            button.setMaximumWidth(QtGui.QFontMetrics(button.font()).width(name.replace("-", "+")) + 10)
        if fn is None:
            button.clicked.connect(lambda: self.handleButton(name[0], 1 if name[1] == '+' else -1))
        else:
            button.clicked.connect(fn)
        button.setFocusPolicy(QtCore.Qt.NoFocus)
        layout.addWidget(button, locx, locy)
    def handleButton(self, axis, dist):
        if axis == 'Z':
            m = self.distz * dist
            s = self.speedz
        else:
            m = self.distxy * dist
            s = self.speedxy
        if QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier:
            m *= 10
        if s is None:
            self.grbl.jogTo("G91 %s%s" % (axis, m))
        else:
            self.grbl.jogTo("G91 %s%s" % (axis, m), feed = s)
    def cancelJog(self):
        self.grbl.jogTo("")
    def handleSteps(self, var, dist):
        setattr(self, var, dist)
        self.steps_changed.emit()
    def initUI(self):        
        layout = QtWidgets.QGridLayout()
        self.setLayout(layout)
        self.makeButton("Y+", layout, 0, 1)
        self.makeButton("X-", layout, 1, 0)
        self.makeButton("", layout, 1, 1, iconId = 59, fn = self.cancelJog)
        self.makeButton("X+", layout, 1, 2)
        self.makeButton("Y-", layout, 2, 1)
        self.makeButton("Z+", layout, 0, 6)
        self.makeButton("Z-", layout, 2, 6)
        def addButton(steps, var, d, v):
            rb = QtWidgets.QRadioButton(d)
            rb.setAutoExclusive(False)
            rb.clicked.connect(lambda: self.handleSteps(var, v))
            self.steps_changed.connect(lambda: rb.setChecked(getattr(self, var) == v))
            steps.addWidget(rb)
        def fmtfloat(v):
            if v == int(v):
                return str(int(v))
            return str(v)
        steps = QtWidgets.QVBoxLayout()
        for d in Global.settings.xysteps:
            addButton(steps, 'distxy', "%smm" % fmtfloat(d), d)
        layout.addLayout(steps, 0, 3, 4, 1)
        speeds = QtWidgets.QVBoxLayout()
        for d in Global.settings.xyspeeds:
            addButton(speeds, 'speedxy', "F%s" % fmtfloat(d) if d is not None else "Rapid", d)
        layout.addLayout(speeds, 0, 4, 4, 1)

        frm = QtWidgets.QFrame()
        frm.setFrameStyle(QtWidgets.QFrame.VLine)
        layout.addWidget(frm, 0, 5, 4, 1)

        steps = QtWidgets.QVBoxLayout()
        for d in Global.settings.zsteps:
            addButton(steps, 'distz', "%smm" % fmtfloat(d), d)
        layout.addLayout(steps, 0, 7, 4, 1)
        speeds = QtWidgets.QVBoxLayout()
        for d in Global.settings.zspeeds:
            addButton(speeds, 'speedz', "F%s" % fmtfloat(d) if d is not None else "Rapid", d)
        layout.addLayout(speeds, 0, 8, 4, 1)

        self.steps_changed.emit()

class HistoryLineEdit(QtWidgets.QLineEdit):
    def __init__(self, history):
        QtWidgets.QLineEdit.__init__(self)
        self.jogger = None
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
                    self.setText(self.history.getHistoryCmd(self.history_cursor))
                    self.selectAll()
            elif e.key() == QtCore.Qt.Key_Down:
                if self.history_cursor < self.history.rowCount(QtCore.QModelIndex()) - 1:
                    self.history_cursor += 1
                    self.setText(self.history.getHistoryCmd(self.history_cursor))
                    self.selectAll()
            else:
                QtWidgets.QLineEdit.keyPressEvent(self, e)
        else:
            if self.jogger and self.jogger.checkKeyPressEvent(e):
                return
            QtWidgets.QLineEdit.keyPressEvent(self, e)

class CNCPendant(QtWidgets.QGroupBox):
    def __init__(self, grbl):
        QtWidgets.QWidget.__init__(self)
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
        if e.key() == QtCore.Qt.Key_Escape:
            self.cmdWidget.setFocus()
        if e.modifiers() & QtCore.Qt.AltModifier:
            if self.jogger.checkKeyPressEvent(e):
                return
        return QtWidgets.QGroupBox.keyPressEvent(self, e)
    def initUI(self):        
        cmdLayout = QtWidgets.QHBoxLayout()
        statusLayout = QtWidgets.QHBoxLayout()
        commentLayout = QtWidgets.QHBoxLayout()

        self.cmdWidget = HistoryLineEdit(self.grbl.history)
        cmdLayout.addWidget(self.cmdWidget)
        self.cmdButton = QtWidgets.QPushButton("Send")
        self.cmdButton.clicked.connect(self.sendCommand)
        self.cmdButton.setDefault(True)
        cmdLayout.addWidget(self.cmdButton)
        
        self.modeWidget = QtWidgets.QLabel()
        self.modeWidget.setFont(Global.fonts.mediumBoldFont)
        statusLayout.addWidget(self.modeWidget)
        def addButton(name, func):
            b = QtWidgets.QPushButton(name)
            b.clicked.connect(func)
            statusLayout.addWidget(b)
            return b
        self.holdButton = addButton("Hold", self.onMachineFeedHold)
        self.resumeButton = addButton("Resume", self.onMachineResume)
        self.resetButton = addButton("Soft Reset", self.onMachineSoftReset)
        self.killAlarmButton = addButton("Kill Alarm", self.onMachineKillAlarm)
        
        self.commentWidget = QtWidgets.QLabel("")
        commentLayout.addWidget(self.commentWidget)
        self.feedSpeedWidget = QtWidgets.QLabel("")
        commentLayout.addWidget(self.feedSpeedWidget)

        self.workWidgets = {}
        self.machineWidgets = {}

        grid = QtWidgets.QGridLayout()

        layout = QtWidgets.QFormLayout()
        layout.setLabelAlignment(QtCore.Qt.AlignRight)
        self.tableview = QtWidgets.QTableView()
        self.tableview.setModel(self.grbl.history)
        self.tableview.setColumnWidth(0, 400)
        self.tableview.setColumnWidth(1, 160)
        self.tableview.setMinimumWidth(560)
        self.tableview.setMinimumHeight(300)
        self.tableview.verticalHeader().hide()
        self.tableview.resizeRowsToContents()
        self.tableMax = 0
        self.grbl.history.dataChanged.connect(self.onTableDataChanged)
        self.grbl.history.rowsInserted.connect(self.onTableRowsInserted)
        
        layout.addRow(self.tableview)
        layout.addRow("Command:", cmdLayout)
        layout.addRow("Status:", statusLayout)
        layout.addRow("Last comment:", commentLayout)
        grid.addLayout(layout, 0, 0, 1, 3)
        
        layout = QtWidgets.QGridLayout()
        layout.setAlignment(QtCore.Qt.AlignTop)
        layout.setColumnMinimumWidth(1, 14 * 6)
        layout.setColumnMinimumWidth(3, 14 * 6)
        alignment = {"|" : QtCore.Qt.AlignHCenter, "<" : QtCore.Qt.AlignLeft, ">" : QtCore.Qt.AlignRight}
        for col, name in enumerate(['|', ">Work", "|Zero", ">Machine"]):
            label = QtWidgets.QLabel(name[1:])
            layout.addWidget(label, 0, col, alignment[name[0]] | QtCore.Qt.AlignTop)
        alignment = QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter
        for index, axis in enumerate(['X', 'Y', 'Z']):
            label = QtWidgets.QLabel(axis)
            label.setScaledContents(False)
            label.setFont(Global.fonts.bigBoldFont)
            layout.addWidget(label, index + 1, 0, QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
            coordWidget = QtWidgets.QPushButton("-")
            coordWidget.setFlat(True)
            coordWidget.setFont(Global.fonts.bigBoldFont)
            #coordWidget.setAlignment(alignment)
            def mkLocal(axis, coordWidget):
                def returnPressedFunc():
                    newValue, ok = QtWidgets.QInputDialog.getDouble(self, "Reset %s axis" % axis, "New current position", float(coordWidget.text()), -10000, 10000, 2)
                    if ok:
                        self.zeroAxis(axis, newValue)
                return returnPressedFunc
            coordWidget.clicked.connect(mkLocal(axis, coordWidget))
            layout.addWidget(coordWidget, index + 1, 1, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.workWidgets[axis] = coordWidget
            zeroWidget = QtWidgets.QPushButton("0")
            def q(axis):
                return lambda: self.zeroAxis(axis)
            zeroWidget.setMaximumWidth(32)
            zeroWidget.clicked.connect(q(axis))
            layout.addWidget(zeroWidget, index + 1, 2)
            coordWidget = QtWidgets.QLabel("-")
            coordWidget.setFont(Global.fonts.bigFont)
            coordWidget.setAlignment(alignment)
            layout.addWidget(coordWidget, index + 1, 3)
            self.machineWidgets[axis] = coordWidget
        widget = QtWidgets.QGroupBox("Coordinates")
        widget.setLayout(layout)
        grid.addWidget(widget, 1, 0)

        self.jogger = CNCJogger(self.grbl)
        self.cmdWidget.jogger = self.jogger
        grid.addWidget(self.jogger, 1, 2, 1, 1)
        self.macros = QtWidgets.QHBoxLayout()
        for name, command in Global.settings.macros:
            button = QtWidgets.QPushButton(name)
            def q(command):
                return lambda: self.grbl.sendLine(command)
            button.clicked.connect(q(command))
            self.macros.addWidget(button)
        grid.addLayout(self.macros, 2, 0, 1, 3)
        
        self.setLayout(grid)

    def zeroAxis(self, axis, newValue = 0):
        self.grbl.sendLine('G90 G10 L20 P0 %s%s' % (axis, newValue))
        
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
        isConnected = self.grbl.isConnected()
        canAcceptCommands = isConnected and self.grbl.canAcceptCommands(mode) and not self.grbl.isRunningAJob()
        fmt = "%0.3f"
        self.resetButton.setEnabled(isConnected and mode != "Alarm")
        self.killAlarmButton.setEnabled(isConnected and mode == "Alarm")
        self.cmdButton.setEnabled(canAcceptCommands)
        for w in list(self.workWidgets.values()):
            w.setEnabled(mode == "Idle")
        for i in range(self.macros.count()):
            self.macros.itemAt(i).widget().setEnabled(canAcceptCommands)
        if extra is not None:
            mode = "%s - %s" % (mode, extra)
        self.modeWidget.setText(mode)
        self.commentWidget.setText(last_comment)
        if self.grbl.grbl:
            g = self.grbl.grbl
            fs = []
            if g.last_feed:
                fs.append("Feed: %s" % g.last_feed)
            if g.last_speed:
                fs.append("RPM: %s" % g.last_speed)
            if g.accessories != '':
                accNames = {
                    'S' : "Fwd",
                    'C' : "Rev",
                    'F' : "Flood",
                    'M' : "Mist",
                }
                for a in g.accessories:
                    fs.append(accNames[a])
            if g.overrides != [100, 100, 100]:
                fs.append("Ov: %s" % g.overrides)
            if g.pins != "":
                accNames = {
                    'S' : "Start",
                    'D' : "Door",
                    'H' : "Hold",
                    'R' : "Reset",
                    'P' : "Probe",
                    'X' : "EndX",
                    'Y' : "EndY",
                    'Z' : "EndZ",
                }
                fs.append("Pins: %s" % "".join(accNames.get(pin, '(%s)' % pin) for pin in g.pins))
            self.feedSpeedWidget.setText(" | ".join(fs))
        self.jogger.setEnabled(self.grbl.canAcceptCommands(mode))
        self.holdButton.setEnabled(isConnected and mode != "Hold")
        self.resumeButton.setEnabled(mode == "Hold")
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
        print(("Received:", line))
    def onMachineHome(self):
        self.grbl.sendLine('G28')
    def onMachineFeedHold(self):
        self.grbl.grbl.pause()
    def onMachineResume(self):
        self.grbl.grbl.restart()
    def onMachineSoftReset(self):
        if self.grbl.job:
            self.grbl.job.cancel()
        self.grbl.grbl.soft_reset()
    def onMachineKillAlarm(self):
        self.grbl.sendLine('$X')
    def onMachineHomingCycle(self):
        self.grbl.sendLine('$H')

class CNCJobControl(QtWidgets.QGroupBox):
    def __init__(self, grbl):
        QtWidgets.QWidget.__init__(self)
        self.setTitle("Job control")
        self.grbl = grbl
        self.jobFile = None
        self.jobViewer = None
        self.directory = Global.settings.gcode_directory
        self.initUI()
    def initUI(self):
        self.buttons = {}
        layout = QtWidgets.QVBoxLayout()
        self.jobCommands = QtWidgets.QTableView()
        self.jobCommands.setModel(GcodeJobModel())
        self.jobCommands.setColumnWidth(0, 320)
        self.jobCommands.setColumnWidth(1, 120)
        self.jobCommands.setMinimumWidth(460)
        self.jobCommands.setMinimumHeight(300)
        self.jobCommands.resizeRowsToContents()
        layout.addLayout(self.initFileArea())
        layout.addWidget(self.jobCommands)
        layout.addLayout(self.initButtons())
        self.setLayout(layout)
        self.updateButtons()
    def initFileArea(self):
        area = QtWidgets.QHBoxLayout()
        button = QtWidgets.QPushButton("Load")
        button.clicked.connect(self.onFileOpen)
        self.buttons["Load"] = button
        area.addWidget(button, 0)
        self.fileLabel = QtWidgets.QLabel("")
        self.fileLabel.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken);
        area.addWidget(self.fileLabel, 1)
        button = QtWidgets.QPushButton("Reload")
        button.clicked.connect(self.onFileReopen)
        self.buttons["Reload"] = button
        area.addWidget(button, 0)
        return area

    def initButtons(self):
        buttonList = [
            ('Run', self.onJobRun),
            ('Pause', self.onJobPause),
            ('Resume', self.onJobResume),
            ('Cancel', self.onJobCancel),
            ('View', self.onJobView),
        ]
        buttons = QtWidgets.QHBoxLayout()
        for name, func in buttonList:
            button = QtWidgets.QPushButton(name)
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
        self.buttons['Reload'].setEnabled(self.jobFile is not None)
        self.buttons['Run'].setEnabled(self.grbl.job is not None and not self.grbl.isRunningAJob())
        self.buttons['Pause'].setEnabled(self.grbl.isRunningAJob())
        self.buttons['Resume'].setEnabled(self.grbl.isJobPaused())
        self.buttons['Cancel'].setEnabled(self.grbl.isJobCancellable())
    def setJob(self, job):
        job.dataChanged.connect(self.onJobTableDataChanged)    
        self.jobCommands.setModel(job)
        self.jobCommands.scrollTo(job.index(0, 0))
        rc = job.rowCount(None)
        if rc < 10000:
            self.jobCommands.resizeRowsToContents()
        else:
            # Do the second best thing - resize first 500 rows
            for i in range(1, 500):
                self.jobCommands.resizeRowToContents(i)
        self.updateButtons()
    def loadFile(self, fname):
        job = GcodeJobModel()
        f = open(fname, "r")
        accum = []
        for l in f:
            l = l.strip()
            if l != '':
                if len(accum) >= 100:
                    job.addCommands(accum)
                    accum = []
                accum.append(l)
        job.addCommands(accum)
        self.jobFile = fname
        self.fileLabel.setText(self.jobFile)
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
    def onJobView(self):
        if self.jobViewer is None:
            self.jobViewer = JobPreviewWindow()
        self.jobViewer.setGrbl(self.grbl)
        self.jobViewer.setJob(self.grbl.job)
        self.jobViewer.show()
    def onFileReopen(self):
        if self.jobFile:
            self.loadFile(self.jobFile)
    def onFileOpen(self):
        #fname = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '.', "Gcode files (*.nc *.gcode)")
        opendlg = QtWidgets.QFileDialog(self, 'Open file', '.', "Gcode files (*.nc *.gcode *.ngc)")
        opendlg.setFileMode(QtWidgets.QFileDialog.ExistingFile)
        opendlg.setOptions(QtWidgets.QFileDialog.DontUseNativeDialog)
        if self.jobFile is not None:
            opendlg.selectFile(self.jobFile)
        mainLayout = opendlg.layout()
        preview = JobPreview()
        mainLayout.addWidget(preview, 0, mainLayout.columnCount(), mainLayout.rowCount(), 1)
        #mainLayout.setColumnStretch(mainLayout.columnCount() - 1, 1)
        opendlg.resize(opendlg.size().width() + preview.size().width() + 10, opendlg.size().height())
        def setJob(filename):
            success = False
            if filename != '':
                try:
                    if filename != '':
                        preview.loadFromFile(filename)
                        success = True
                except:
                    pass
            if not success:
                preview.setFromList([])
        if self.directory is not None:
            opendlg.setDirectory(self.directory)
        opendlg.currentChanged.connect(setJob)
        if opendlg.exec_():
            self.directory = opendlg.directory().absolutePath()
            fnames = opendlg.selectedFiles()
            if len(fnames) == 1:
                self.loadFile(fnames[0])

class CNCMainWindow(QtWidgets.QMainWindow, MenuHelper):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
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
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.pendant)
        layout.addWidget(self.jobs)
        widget = QtWidgets.QGroupBox()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.setWindowTitle("KF's GRBL controller")
        self.configDialog = MachineConfigDialog(self.grbl.config_model)
        self.pendant.cmdWidget.setFocus()
        self.pendant.grbl.status.connect(self.onGrblStatus)
    def onGrblStatus(self):
        if self.jobs.jobViewer is not None:
            status = self.pendant.grbl.getStatus()
            pos = status[1]
            if 'WPos' in pos:
                self.jobs.jobViewer.onSpindleMoved(*pos['WPos'])
    def onMachineConfiguration(self):
        self.grbl.sendLine('$$')
        self.configDialog.show()
    def onFilePreferences(self):
        prefs = AppConfigDialog()
        oldDevice = Global.settings.device
        if prefs.exec_():
            prefs.save()
            if Global.settings.device != oldDevice:
                self.reconnect()
        prefs = None
    def disconnect(self):
        self.grbl.disconnectFromGrbl()
        self.grbl.shutdown()
    def reconnect(self):
        self.grbl.disconnectFromGrbl()
        self.grbl.connectToGrbl()

def main():    
    app = CNCApplication(sys.argv)
    Global.settings.load()
    w = CNCMainWindow()
    if len(sys.argv) > 1:
        w.jobs.loadFile(sys.argv[1])
    w.show()
    retcode = app.exec_()
    w.disconnect()
    w = None
    app = None
    if retcode != 0:
        sys.exit(retcode)

main()
