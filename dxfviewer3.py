import math
import re
import sys
import time
from cam.tool import *
from cam.operation import *

import dxfgrabber

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from sender.jobviewer import *
from helpers.dxf import dxfToObjects
from helpers.gui import *
from helpers.geom import *
from helpers.flatitems import *

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

class DXFViewer(PreviewBase):
    selected = pyqtSignal([])
    def __init__(self, drawing):
        PreviewBase.__init__(self)
        self.objects = dxfToObjects(drawing)
        self.operations = CAMOperationsModel()
        self.selection = None
        self.opSelection = []
        self.curOperation = None
        self.updateCursor()
    def getPen(self, item, is_virtual):
        if is_virtual:
            color = QColor(160, 160, 160)
            if self.curOperation in self.opSelection:
                color = QColor(255, 0, 0)
            pen = QPen(color, self.curOperation.tool.diameter * self.getScale())
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            return pen
        if item.marked:
            return self.activeItemPen
        return self.drawingPen
    def createPainters(self):
        self.initPainters()
        self.drawingPath = QGraphicsScene()
        self.previewPen = QPen(QColor(160, 160, 160), 0)
        self.drawingPen = QPen(QColor(0, 0, 0), 0)
        self.drawingPen2 = QPen(QColor(255, 0, 0), 0)
        self.activeItemPen = QPen(QColor(0, 255, 0), 0)
        #self.drawingPen.setCapStyle(Qt.RoundCap)
        #self.drawingPen.setJoinStyle(Qt.RoundJoin)
        for i in xrange(self.operations.rowCount()):
            op = self.operations.item(i).operation
            self.curOperation = op
            for n in op.previewPaths:
                n.addToPath(self, self.drawingPath, True)
        self.curOperation = None
        for o in self.objects:
            o.addToPath(self, self.drawingPath, False)
    def renderDrawing(self, qp):
        trect = QRectF(self.rect()).translated(self.translation)
        if self.drawingPath is not None:
            self.drawingPath.render(qp, QRectF(self.rect()), trect)
    def updateCursor(self):
        self.setCursor(Qt.CrossCursor)
    def getItemAtPoint(self, p):
        matches = sorted([(i, i.distanceTo(p)) for i in self.objects], lambda o1, o2: cmp(o1[1], o2[1]))
        mind = matches[0][1] if len(matches) > 0 else None
        second = matches[1][1] if len(matches) > 1 else None
        if second is not None and abs(second - mind) < 1 / self.getScale():
            print "Warning: Multiple items at similar distance"
        if mind < 10 / self.getScale():
            return matches[0][0]
    def updateSelection(self):
        self.createPainters()
        self.repaint()
        self.selected.emit()
    def getSelected(self):
        return [i for i in self.objects if i.marked]
    def setOpSelection(self, selection):
        self.opSelection = selection
        self.updateSelection()
    def mousePressEvent(self, e):
        b = e.button()
        if b == Qt.LeftButton:
            p = e.posF()
            lp = self.physToLog(p)
            item = self.getItemAtPoint(lp)
            if item:
                item.setMarked(not item.marked)
                self.updateSelection()
            else:
                if self.selection is None:
                    self.selection = MyRubberBand(QRubberBand.Rectangle, self)
                self.selectionOrigin = e.pos()
                self.selection.setGeometry(QRect(e.pos(), QSize()))
                self.selection.show()
        elif b == Qt.RightButton:
            self.start_point = e.posF()
            self.prev_point = e.posF()
            self.start_origin = (self.x0, self.y0)
            self.dragging = True
    def mouseMoveEvent(self, e):
        if self.selection and self.selection.isVisible():
            self.selection.setGeometry(QRect(self.selectionOrigin, e.pos()).normalized())
        PreviewBase.mouseMoveEvent(self, e)
    def mouseReleaseEvent(self, e):
        if self.selection and self.selection.isVisible():
            ps = self.unproject(self.selectionOrigin.x(), self.selectionOrigin.y())
            pe = self.unproject(e.pos().x(), e.pos().y())
            box = QRectF(qp(ps), qp(pe)).normalized()
            
            self.selectByBox(box)
            self.selection.hide()
            self.selection = None
        PreviewBase.mouseReleaseEvent(self, e)
    def selectByBox(self, box):
        for o in self.objects:
            if box.contains(o.bounds):
                o.setMarked(True)
        self.updateSelection()
    
class DXFApplication(QApplication):
    pass

class OperationTreeWidget(QDockWidget):
    def __init__(self, viewer):
        QDockWidget.__init__(self, "Operations")
        self.viewer = viewer
        self.initUI()
    def initUI(self):
        self.w = QWidget()
        self.w.setLayout(QVBoxLayout())
        self.w.layout().setSpacing(0)
        self.setWidget(self.w)
        self.list = QListView()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setModel(self.viewer.operations)
        self.list.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.toolbar = QWidget()
        pb = QPushButton("Delete")
        pb.clicked.connect(self.onOperationDelete)
        self.toolbar.setLayout(QHBoxLayout())
        self.toolbar.layout().addWidget(pb)
        self.w.layout().addWidget(self.list)
        self.w.layout().addWidget(self.toolbar)
    def getSelected(self):
        sm = self.list.selectionModel()
        ops = []
        for i in sm.selectedRows():
            ops.append(self.viewer.operations.item(i.row()).operation)
        return ops
    def onOperationDelete(self):
        ops = self.getSelected()
        self.viewer.operations.delOperations(lambda o: o in ops)
        self.viewer.updateSelection()
    def onSelectionChanged(self, selected, deselected):
        self.viewer.setOpSelection(self.getSelected())
    def select(self, item):
        self.list.selectionModel().select(QModelIndex(item), QItemSelectionModel.ClearAndSelect)

class ObjectPropertiesWidget(QDockWidget):
    def __init__(self, viewer):
        QDockWidget.__init__(self, "Properties")
        self.viewer = viewer
        self.updating = False
        self.initUI()
    def initUI(self):
        self.properties = [
            FloatEditableProperty("End depth", "zend", "%0.3f"),
            FloatEditableProperty("Start depth", "zstart", "%0.3f"),
            FloatEditableProperty("Tab height", "tab_height", "%0.3f", allow_none = True),
            FloatEditableProperty("Tab width", "tab_width", "%0.3f", allow_none = True),
            FloatEditableProperty("Tab spacing", "tab_spacing", "%0.3f", allow_none = True),
            IntEditableProperty('Min tabs', "min_tabs", min = 0, max = 10),
            IntEditableProperty('Max tabs', "max_tabs", min = 0, max = 10),
        ]
        self.table = QTableWidget(len(self.properties), 1)
        self.table.setHorizontalHeaderLabels(['Value'])
        self.table.setVerticalHeaderLabels([p.name for p in self.properties])
        self.table.cellChanged.connect(self.onCellChanged)
        self.operations = None
        self.setWidget(self.table)
    def onCellChanged(self, row, column):
        if self.operations and not self.updating:
            item = self.table.item(row, column)
            newValueText = item.data(Qt.EditRole).toString()
            prop = self.properties[row]
            try:
                value = prop.validate(newValueText)
                for o in self.operations:
                    if value != prop.getData(o):
                        prop.setData(o, value)
                    o.update()
            except Exception as e:
                print e
            finally:
                self.refreshRow(row)
            self.viewer.updateSelection()
    def refreshRow(self, row):
        prop = self.properties[row]
        values = []
        for o in self.operations:
            values.append(prop.getData(o))
        i = self.table.item(row, 0)
        if len(values):
            if any([v != values[0] for v in values]):
                s = MultipleItem
            else:
                s = prop.toEditString(values[0])
            if i is None or i.text() != s:
                try:
                    self.updating = True
                    self.table.setItem(row, 0, PropertyTableWidgetItem(s))
                finally:
                    self.updating = False
        else:
            if i is not None:
                self.table.setItem(row, 0, None)
    def setOperations(self, operations):
        self.operations = operations
        self.table.setEnabled(len(self.operations) > 0)
        if self.operations:
            o = operations[0]
            for i in xrange(len(self.properties)):
                self.refreshRow(i)
        else:
            for i in xrange(len(self.properties)):
                self.table.setItem(i, 0, None)

class DXFMainWindow(QMainWindow, MenuHelper):
    def __init__(self, drawing):
        QMainWindow.__init__(self)
        self.drawing = drawing
        self.toolbar = QToolBar("Operations")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.toolbar.addAction("Profile").triggered.connect(self.onOperationProfile)
        self.toolbar.addAction("Cutout").triggered.connect(self.onOperationCutout)
        self.toolbar.addAction("Pocket").triggered.connect(self.onOperationPocket)
        self.toolbar.addAction("Engrave").triggered.connect(self.onOperationEngrave)
        self.toolbar.addAction("Generate").triggered.connect(self.onOperationGenerate)
        self.toolbar.addAction("Unselect").triggered.connect(self.onOperationUnselect)
        self.addToolBar(self.toolbar)
        self.viewer = DXFViewer(drawing)
        self.operationTree = OperationTreeWidget(self.viewer)
        self.objectProperties = ObjectPropertiesWidget(self.viewer)
        self.addDockWidget(Qt.RightDockWidgetArea, self.operationTree)
        self.addDockWidget(Qt.RightDockWidgetArea, self.objectProperties)
        self.setCentralWidget(self.viewer)
        self.setMinimumSize(1024, 600)
        self.operationTree.list.selectionModel().selectionChanged.connect(self.onOperationsSelected)
        self.onOperationsSelected()
    def onOperationsSelected(self):
        selected = self.operationTree.getSelected()
        self.objectProperties.setOperations(selected)
    def onOperationProfile(self):
        self.createOperations(ShapeDirection.OUTSIDE)
    def onOperationCutout(self):
        self.createOperations(ShapeDirection.INSIDE)
    def onOperationPocket(self):
        self.createOperations(ShapeDirection.POCKET)
    def onOperationEngrave(self):
        self.createOperations(ShapeDirection.OUTLINE)
    def onOperationUnselect(self):
        for i in self.viewer.objects:
            if i.marked:
                i.setMarked(False)
        self.viewer.updateSelection()
    def createOperations(self, dir):
        shapes = []
        for i in self.viewer.objects:
            if i.marked:
                if dir == ShapeDirection.OUTLINE or isinstance(i, DrawingPolyline):
                    shapes.append(i)
                    i.setMarked(False)
        if len(shapes):
            op = CAMOperation(dir, shapes, defaultTool)
            index = self.viewer.operations.addOperation(op)
            self.operationTree.select(index)
        self.viewer.updateSelection()
    def onOperationGenerate(self):
        ops = self.viewer.operations.toGcode()
        f = file("test.nc", "w")
        for op in ops:
            print op
            f.write("%s\n" % op)
        f.close()

def main():    
    app = DXFApplication(sys.argv)
    drawing = dxfgrabber.readfile(sys.argv[1])
    w = DXFMainWindow(drawing)
    w.show()
    retcode = app.exec_()
    w = None
    app = None
    return retcode
    
sys.exit(main())
