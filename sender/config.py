from PyQt5 import QtCore, QtGui, QtWidgets

def store_array(qs, name, arr, writer):
    qs.beginWriteArray(name)
    for i in xrange(len(arr)):
        qs.setArrayIndex(i)
        writer(qs, arr[i])
    qs.endArray()
def restore_array(qs, name, defvalue, reader):
    if int(qs.value(name + "/size", -1)) == -1:
        return defvalue
    data = []
    size = qs.beginReadArray(name)
    for i in xrange(size):
        qs.setArrayIndex(i)
        data.append(reader(qs))
    qs.endArray()
    return data

class Settings:
    device = None
    speed = 115200
    timer_interval = 100
    xysteps = [50, 10, 1, 0.1]
    zsteps = [10, 1, 0.1, 0.05]
    xyspeeds = [None, 2000, 1000, 500, 100]
    zspeeds = [None, 1000, 500, 100, 50]
    macros = [
        ('Probe', 'G91 G38.2 Z-10 F100'),
        ('Set Z=20', 'G91 G10 L20 P1 Z20'),
        ('Set XY=0', 'G91 G10 L20 P1 X0 Y0'),
        ('Retract', 'G90 G0 Z30'),
    ]
    gcode_directory = "."
    def restore(self, qs):
        def unp(v):
            return float(v) if v is not None else None
        def restoremacro(qs):
            return (str(qs.value("name")), str(qs.value("command")))
        self.device = str(qs.value("serial/device", None))
        if self.device == "":
            self.device = None
        self.speed = int(qs.value("serial/speed", 115200))

        self.gcode_directory = qs.value("directories/gcode_directory", ".")

        self.timer_interval = int(qs.value("serial/timer", 100))
        self.xysteps = restore_array(qs, "xysteps", self.xysteps, lambda qs: unp(qs.value("step")))
        self.xyspeeds = restore_array(qs, "xyspeeds", self.xyspeeds, lambda qs: unp(qs.value("speed")))
        self.zsteps = restore_array(qs, "zsteps", self.zsteps, lambda qs: unp(qs.value("step")))
        self.zspeeds = restore_array(qs, "zspeeds", self.zspeeds, lambda qs: unp(qs.value("speed")))
        self.macros = restore_array(qs, "macros", self.macros, restoremacro)
    def store(self, qs):
        qs.setValue("directories/gcode_directory", self.gcode_directory)
        qs.setValue("serial/device", self.device or "")
        qs.setValue("serial/speed", self.speed)
        qs.setValue("serial/timer", self.timer_interval)
        store_array(qs, "xysteps", self.xysteps, lambda qs, item: qs.setValue("step", item))
        store_array(qs, "xyspeeds", self.xyspeeds, lambda qs, item: qs.setValue("speed", item))
        store_array(qs, "zsteps", self.zsteps, lambda qs, item: qs.setValue("step", item))
        store_array(qs, "zspeeds", self.zspeeds, lambda qs, item: qs.setValue("speed", item))
        def storemacro(qs, item):
            qs.setValue("name", item[0])
            qs.setValue("command", item[1])
        store_array(qs, "macros", self.macros, storemacro)
    def save(self):
        self.store(QtCore.QSettings("kfoltman", "wharrgrbl"))
    def load(self):
        self.restore(QtCore.QSettings("kfoltman", "wharrgrbl"))

class Fonts:
    mediumFont = QtGui.QFont("Sans", 12)
    mediumBoldFont = QtGui.QFont("Sans", 12, QtGui.QFont.Bold)
    bigFont = QtGui.QFont("Sans", 14)
    bigBoldFont = QtGui.QFont("Sans", 14, QtGui.QFont.Bold)

class Global:
    settings = Settings()
    fonts = Fonts()
