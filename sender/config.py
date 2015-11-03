from PyQt4 import QtCore, QtGui

class Settings:
    device = '/dev/ttyACM0'
    speed = 115200
    timer_interval = 200

class Fonts:
    mediumFont = QtGui.QFont("Sans", 12)
    mediumBoldFont = QtGui.QFont("Sans", 12, QtGui.QFont.Bold)
    bigFont = QtGui.QFont("Sans", 14, QtGui.QFont.Bold)
    bigBoldFont = QtGui.QFont("Sans", 14)

