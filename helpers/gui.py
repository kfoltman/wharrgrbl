from PyQt4 import QtCore, QtGui

class MenuHelper(object):
    def __init__(self):
        self.update_actions = []
    
    def addEnabledHandler(self, action, isEnabled):
        def updater(action, isEnabled):
            action.setEnabled(isEnabled())
        self.update_actions.append(lambda: updater(action, isEnabled))
        return action

    def updateActions(self):
        for fn in self.update_actions:
            fn()

    def makeAction(self, name, shortcut, tip, handler):
        action = QtGui.QAction(QtGui.QIcon(), name, self)
        action.setShortcut(shortcut)
        action.setStatusTip(tip)
        action.triggered.connect(handler)
        return action

    def makeRadioAction(self, name, shortcut, tip, group, handler, isChecked):
        action = QtGui.QAction(QtGui.QIcon(), name, self)
        action.setShortcut(shortcut)
        action.setStatusTip(tip)
        action.setActionGroup(group)
        action.setCheckable(True)
        action.setChecked(isChecked())
        action.triggered.connect(handler)
        def updater(action, isChecked):
            action.setChecked(isChecked())
        self.update_actions.append(lambda: updater(action, isChecked))
        return action

    def makeCheckAction(self, name, shortcut, tip, handler, isChecked):
        action = QtGui.QAction(QtGui.QIcon(), name, self)
        action.setShortcut(shortcut)
        action.setStatusTip(tip)
        action.setCheckable(True)
        action.setChecked(isChecked())
        def updater(action, isChecked):
            action.setChecked(isChecked())
        self.update_actions.append(lambda: updater(action, isChecked))
        action.triggered.connect(handler)
        return action

    def makeSeparator(self):
        action = QtGui.QAction(self)
        action.setSeparator(True)
        return action

