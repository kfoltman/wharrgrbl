from PyQt4.QtCore import *
from PyQt4.QtGui import *

class RefMap(dict):
    def __init__(self):
        self.seqcnt = 0
    def ref(self, ob):
        if ob in self:
            return ob
        self[ob] = "%s/%d" % (type(ob).__name__, self.seqcnt)
        self.seqcnt += 1
        return ob
    def refn(self, ob):
        return self[self.ref(ob)]

class MyRubberBand(QRubberBand):
    def paintEvent(self, e):
        qp = QPainter()
        qp.begin(self)
        pen = QPen(QColor(255, 0, 0))
        brush = QBrush(QColor(255, 0, 0))
        qp.setPen(pen)
        qp.setBrush(brush)
        qp.drawRect(self.rect().adjusted(0, 0, -1, -1))
        qp.fillRect(self.rect().adjusted(0, 0, -1, -1), QBrush(QColor(255, 0, 0)))
        qp.end()

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
    def toTextColor(self, value):
        return None
    def toEditString(self, value):
        return self.format % (value,)
    def toDisplayString(self, value):
        return self.toEditString(value)
    def validate(self, value):
        return value

class NumEditableProperty(EditableProperty):
    def __init__(self, name, attribute, format = None, min = None, max = None, allow_none = False, none_value = "none"):
        EditableProperty.__init__(self, name, attribute, self.defaultFormat() if format is None else format)
        self.min = min
        self.max = max
        self.allow_none = allow_none
        self.none_value = none_value
    def toTextColor(self, value):
        return "gray" if value is None else None
    def toDisplayString(self, value):
        if value is None:
            return self.none_value
        return self.format % (value,)
    def toEditString(self, value):
        if value is None:
            return ""
        return self.format % (value,)
    def validate(self, value):
        if value == "" and self.allow_none:
            return None
        value = self.fromEditString(value)
        if self.min is not None and value < self.min:
            value = self.min
        if self.max is not None and value > self.max:
            value = self.max
        return value

class FloatEditableProperty(NumEditableProperty):
    def fromEditString(self, value):
        return float(value)
    def defaultFormat(self):
        raise ValueError, "No format specified"

class IntEditableProperty(NumEditableProperty):
    def fromEditString(self, value):
        return int(value)
    def defaultFormat(self):
        return "%d"

class MultipleItem(object):
    @staticmethod
    def __str__(self):
        return "(multiple)"

class PropertyTableWidgetItem(QTableWidgetItem):
    def __init__(self, prop, value):
        self.prop = prop
        self.value = value
        if value is MultipleItem:
            QTableWidgetItem.__init__(self, "")
        else:
            QTableWidgetItem.__init__(self, prop.toEditString(value))
    def data(self, role):
        if self.value is MultipleItem:
            if role == Qt.DisplayRole:
                return "(multiple)"
            if role == Qt.ForegroundRole:
                return QBrush(QColor("gray"))
        else:
            if role == Qt.DisplayRole:
                return self.prop.toDisplayString(self.value)
            if role == Qt.ForegroundRole:
                color = self.prop.toTextColor(self.value)
                if color is not None:
                    return QBrush(QColor(color))
        return QTableWidgetItem.data(self, role)

class PropertySheetWidget(QTableWidget):
    propertyChanged = pyqtSignal([str, list])
    def __init__(self, properties):
        QTableWidget.__init__(self, len(properties), 1)
        self.properties = properties
        self.updating = False
        self.objects = None
        self.setHorizontalHeaderLabels(['Value'])
        self.setVerticalHeaderLabels([p.name for p in self.properties])
        self.verticalHeader().setResizeMode(QHeaderView.ResizeToContents)
        self.verticalHeader().setClickable(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setClickable(False)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setCurrentCell(0, 0)
        self.cellChanged.connect(self.onCellChanged)
    def onCellChanged(self, row, column):
        if self.objects and not self.updating:
            item = self.item(row, column)
            newValueText = item.data(Qt.EditRole).toString()
            prop = self.properties[row]
            changed = []
            try:
                value = prop.validate(newValueText)
                for o in self.objects:
                    if value != prop.getData(o):
                        prop.setData(o, value)
                        changed.append(o)
            except Exception as e:
                print e
            finally:
                self.refreshRow(row)
            self.propertyChanged.emit(prop.attribute, changed)
    def refreshRow(self, row):
        if self.objects is None:
            self.setItem(row, 0, None)
            return
        prop = self.properties[row]
        values = []
        for o in self.objects:
            values.append(prop.getData(o))
        i = self.item(row, 0)
        if len(values):
            if any([v != values[0] for v in values]):
                v = MultipleItem
            else:
                v = values[0]
            try:
                self.updating = True
                self.setItem(row, 0, PropertyTableWidgetItem(prop, v))
            finally:
                self.updating = False
        else:
            if i is not None:
                self.setItem(row, 0, None)
    def setObjects(self, objects):
        self.objects = objects
        self.setEnabled(len(self.objects) > 0)
        for i in xrange(len(self.properties)):
            self.refreshRow(i)

class Serialisable(object):
    def serialise(self, refmap):
        return { v.attribute: v.getData(self) for v in self.properties }
    def unserialise(self, data):
        for prop in self.properties:
            if prop.attribute in data:
                prop.setData(self, data[prop.attribute])

class PropertyDialog(QDialog):
    def __init__(self, subject, properties):
        QDialog.__init__(self)
        self.subject = subject
        self.properties = properties
        self.origValues = { prop.attribute: getattr(subject, prop.attribute) for prop in self.properties }
        self.initUI()
    def initUI(self):
        self.grid = PropertySheetWidget(self.properties)
        self.grid.setObjects([self.subject])
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self.grid)
        buttons = QHBoxLayout()
        pb = QPushButton("Cancel")
        pb.clicked.connect(self.reject)
        buttons.addWidget(pb)
        pb = QPushButton("&OK")
        pb.setDefault(True)
        pb.clicked.connect(self.accept)
        buttons.addWidget(pb)
        self.layout().addLayout(buttons)
    def rollback(self):
        for k, v in self.origValues.items():
            setattr(self.subject, k, v)
