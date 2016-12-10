from PyQt4 import QtCore, QtGui
import re
import sender
import time
from config import *
from config_window import *
from cmdlist import *

class GrblStateMachineWithSignals(QtCore.QObject, sender.GrblStateMachine):
    status = QtCore.pyqtSignal([])
    line_received = QtCore.pyqtSignal([str])
    def __init__(self, history_model, config_model, *args, **kwargs):
        QtCore.QObject.__init__(self)
        self.config_model = config_model
        self.history_model = history_model
        self.job_model = None
        self.last_feed = None
        self.last_speed = None
        self.accessories = ""
        self.overrides = [100, 100, 100]
        self.inputs = ""
        self.pins = ""
        self.current_status = ('Initialized', {}, '', None)
        sender.GrblStateMachine.__init__(self, Global.settings.device, Global.settings.speed)
    def handle_line(self, line):
        if not (line.startswith('<') and line.endswith('>')):
            self.line_received.emit(line)
        return sender.GrblStateMachine.handle_line(self, line)
    def process_cooked_status(self, mode, args):
        if 'F' in args:
            self.last_feed = int(args['F'])
        if 'FS' in args:
            self.last_feed, self.last_speed = map(float, args['FS'])
        if 'Ov' in args:
            self.overrides = args['Ov']
            self.accessories = args.get('A', '')
        self.pins = args.get('Pn', '')
        self.last_status = time.time()
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
    def __init__(self):
        QtCore.QObject.__init__(self)
        self.grbl = None
        self.job = None
        self.history = GcodeJobModel()
        self.config_model = GrblConfigModel(self)
        self.exiting = False
        self.out_queue = []
        self.task_queue = []
        self.start()
    # UI thread
    def shutdown(self):
        self.exiting = True
        self.wait()
    # Worker thread
    def run(self):
        while not self.exiting:
            if len(self.task_queue):
                self.task_queue.pop(0)()
            try:
                if self.grbl is not None:
                    if len(self.out_queue):
                        self.grbl.send_line(self.out_queue.pop(0))
                    self.grbl.ask_for_status_if_idle()
                    while self.grbl.handle_input():
                        pass
                    self.grbl.try_pull()
                    time.sleep(0.01)
                else:
                    self.onStatus()
                    time.sleep(0.1)
            except Exception as e:
                print str(e)
    # Worker thread
    def onStatus(self):
        self.status.emit()
    # Worker thread
    def onLineReceived(self, line):
        self.line_received.emit(line)
    # UI thread
    def connectToGrbl(self):
        self.grbl = GrblStateMachineWithSignals(self.history, self.config_model)
        self.grbl.status.connect(self.onStatus)
        self.grbl.line_received.connect(self.onLineReceived)
        self.grbl.set_job(self.job)
        self.onStatus()
    def disconnectFromGrbl(self):
        def disconnectTask():
            if self.grbl is not None:
                self.grbl.close()        
            self.grbl = None
        self.addTask(disconnectTask)
        self.waitForEmptyTaskQueue()
    def getStatus(self):
        if self.grbl:
            return self.grbl.get_status()
        else:
            return ('Not connected', {}, '', None)
    def setJob(self, job):
        self.job = job
        if self.grbl is not None:
            self.grbl.set_job(job)
    # Worker thread
    def onLineSent(self, line):
        self.out_queue.append(str(line))
    # UI thread
    def addTask(self, task):
        self.task_queue.append(task)
    def waitForEmptyTaskQueue(self):
        # XXXKF convert to cond-variables at some point
        while len(self.task_queue) > 0:
            time.sleep(0.01)
    def jogTo(self, line):
        if self.grbl is not None:
            self.sendLine(self.grbl.version.jog_cmd(line))
        else:
            raise ValueError("connection not established")
    def sendLine(self, line):
        def addLineTask(line):
            self.out_queue.append(line)
        if self.grbl is not None:
            self.addTask(lambda: addLineTask(line))
        else:
            raise ValueError("connection not established")
    @staticmethod
    def canAcceptCommands(mode):
        return mode not in ['Home', 'Alarm']
    def isConnected(self):
        return (self.grbl is not None) and self.getStatus()[0] not in ['Connecting', 'Resetting']
    def isRunningAJob(self):
        return (self.job is not None) and self.job.running
    def isJobPaused(self):
        return (self.job is not None) and self.job.isPaused()
    def isJobCancellable(self):
        return (self.job is not None) and self.job.isCancellable()

