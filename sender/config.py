from PyQt4 import QtCore, QtGui

class Settings:
    device = '/dev/ttyACM0'
    speed = 115200
    timer_interval = 100
    xysteps = [50, 10, 1, 0.1]
    zsteps = [10, 1, 0.1, 0.05]
    macros = [
        ('Probe', 'G91 G38.2 Z-10 F100'),
        ('Set Z=20', 'G91 G10 L20 P1 Z20'),
        ('Set XY=0', 'G91 G10 L20 P1 X0 Y0'),
    ]

class Fonts:
    mediumFont = QtGui.QFont("Sans", 12)
    mediumBoldFont = QtGui.QFont("Sans", 12, QtGui.QFont.Bold)
    bigFont = QtGui.QFont("Sans", 14, QtGui.QFont.Bold)
    bigBoldFont = QtGui.QFont("Sans", 14)

