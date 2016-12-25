from PyQt4.QtCore import *
from PyQt4.QtGui import *

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
        action = QAction(QIcon(), name, self)
        action.setShortcut(shortcut)
        action.setStatusTip(tip)
        action.triggered.connect(handler)
        return action

    def makeRadioAction(self, name, shortcut, tip, group, handler, isChecked):
        action = QAction(QIcon(), name, self)
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
        action = QAction(QIcon(), name, self)
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
        action = QAction(self)
        action.setSeparator(True)
        return action

class EditableProperty(object):
    def __init__(self, name, attribute, format = "%s"):
        self.name = name
        self.attribute = attribute
        self.format = format
    def getData(self, item):
        return getattr(item, self.attribute)
    def setData(self, item, value):
        setattr(item, self.attribute, value)
    def toEditString(self, value):
        return self.format % (value,)
    def validate(self, value):
        return value

class FloatEditableProperty(EditableProperty):
    def __init__(self, name, attribute, format, min = None, max = None, allow_none = False):
        EditableProperty.__init__(self, name, attribute, format)
        self.min = min
        self.max = max
        self.allow_none = allow_none
    def validate(self, value):
        if value == "" and self.allow_none:
            return None
        value = float(value)
        if self.min is not None and value < self.min:
            value = self.min
        if self.max is not None and value > self.max:
            value = self.max
        return value

class IntEditableProperty(EditableProperty):
    def __init__(self, name, attribute, format = "%d", min = None, max = None):
        EditableProperty.__init__(self, name, attribute, format)
        self.min = min
        self.max = max
    def validate(self, value):
        value = int(value)
        if self.min is not None and value < self.min:
            value = self.min
        if self.max is not None and value > self.max:
            value = self.max
        return value

class MultipleItem(object):
    @staticmethod
    def __str__(self):
        return "(multiple)"

class PropertyTableWidgetItem(QTableWidgetItem):
    def __init__(self, value):
        self.value = value
        if value is MultipleItem:
            QTableWidgetItem.__init__(self, "")
        else:
            QTableWidgetItem.__init__(self, value)
    def data(self, role):
        if self.value is MultipleItem:
            if role == Qt.DisplayRole:
                return "(multiple)"
            if role == Qt.ForegroundRole:
                return QBrush(QColor("gray"))
        return QTableWidgetItem.data(self, role)
