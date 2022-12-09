import math
import re
import sys
import time
from .cam.tool import *
from .cam.operation import *
from .cam.tooledit import *
from .cam.matedit import *

import dxfgrabber

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from .sender.jobviewer import *
from .helpers.dxf import dxfToObjects
from .helpers.gui import *
from .helpers.geom import *
from .helpers.flatitems import *

debugToolPaths = False

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
    mouseMoved = pyqtSignal([])
    def __init__(self, drawing):
        PreviewBase.__init__(self)
        self.objects = dxfToObjects(drawing)
        self.operations = CAMOperationsModel()
        self.selection = None
        self.opSelection = []
        self.curOperation = None
        self.lastMousePos = None
        self.updateCursor()
    def getPen(self, item, is_virtual, is_debug):
        if is_virtual:
            color = QColor(160, 160, 160)
            if self.curOperation in self.opSelection:
                color = QColor(255, 0, 0)
            if not is_debug:
                pen = QPen(color, self.curOperation.tool.diameter * self.getScale())
            else:
                pen = QPen(QColor(0, 255, 255), 1)
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
        for i in range(self.operations.rowCount()):
            op = self.operations.item(i).operation
            self.curOperation = op
            for n in op.previewPaths:
                n.addToPath(self, self.drawingPath, True, False)
        if debugToolPaths:
            for i in range(self.operations.rowCount()):
                op = self.operations.item(i).operation
                self.curOperation = op
                for n in op.previewPaths:
                    n.addToPath(self, self.drawingPath, True, True)
        self.curOperation = None
        for o in self.objects:
            o.addToPath(self, self.drawingPath, False, False)
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
            print("Warning: Multiple items at similar distance")
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
            p = e.localPos()
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
            self.start_point = e.localPos()
            self.prev_point = e.localPos()
            self.start_origin = (self.x0, self.y0)
            self.dragging = True
    def mouseMoveEvent(self, e):
        if self.selection and self.selection.isVisible():
            self.selection.setGeometry(QRect(self.selectionOrigin, e.pos()).normalized())
        PreviewBase.mouseMoveEvent(self, e)
        self.lastMousePos = self.physToLog(e.localPos())
        self.mouseMoved.emit()
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
        self.deleteButton = QPushButton("Delete")
        self.deleteButton.clicked.connect(self.onOperationDelete)
        self.toolbar.setLayout(QHBoxLayout())
        self.toolbar.layout().addWidget(self.deleteButton)
        self.w.layout().addWidget(self.list)
        self.w.layout().addWidget(self.toolbar)
        self.onSelectionChanged(None, None)
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
        items = self.getSelected()
        self.deleteButton.setEnabled(len(items) > 0)
        self.viewer.setOpSelection(items)
    def select(self, item):
        self.list.selectionModel().select(QModelIndex(item), QItemSelectionModel.ClearAndSelect)

class ObjectPropertiesWidget(QDockWidget):
    properties = [
        FloatEditableProperty("End depth", "zend", "%0.3f", allow_none = True, none_value = "Full depth"),
        FloatEditableProperty("Start depth", "zstart", "%0.3f"),
        FloatEditableProperty("Tab height", "tab_height", "%0.3f", allow_none = True, none_value = "Full height"),
        FloatEditableProperty("Tab width", "tab_width", "%0.3f", allow_none = True, none_value = "1/2 tool diameter"),
        FloatEditableProperty("Tab spacing", "tab_spacing", "%0.3f"),
        IntEditableProperty('Min tabs', "min_tabs", min = 0, max = 10),
        IntEditableProperty('Max tabs', "max_tabs", min = 0, max = 10),
    ]
    def __init__(self, viewer):
        QDockWidget.__init__(self, "Properties")
        self.viewer = viewer
        self.updating = False
        self.operations = None
        self.initUI()
    def initUI(self):
        self.table = PropertySheetWidget(self.properties)
        self.table.propertyChanged.connect(self.onPropertyChanged)
        self.setWidget(self.table)
    def onPropertyChanged(self, changed):
        for o in changed:
            o.update()
        self.viewer.updateSelection()
    def setOperations(self, operations):
        self.table.setObjects(operations)

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
        self.toolbar.addAction("Tool").triggered.connect(self.onOperationTool)
        self.toolbar.addAction("Material").triggered.connect(self.onOperationMaterial)
        self.toolbar.addAction("Debug").triggered.connect(self.onOperationDebug)
        self.addToolBar(self.toolbar)
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.viewer = DXFViewer(drawing)
        self.operationTree = OperationTreeWidget(self.viewer)
        self.objectProperties = ObjectPropertiesWidget(self.viewer)
        self.addDockWidget(Qt.RightDockWidgetArea, self.operationTree)
        self.addDockWidget(Qt.RightDockWidgetArea, self.objectProperties)
        self.setCentralWidget(self.viewer)
        self.setMinimumSize(1024, 600)
        self.operationTree.list.selectionModel().selectionChanged.connect(self.onOperationsSelected)
        self.onOperationsSelected()
        
        self.viewer.mouseMoved.connect(self.updateStatus)
    def updateStatus(self):
        self.statusBar().showMessage("(%0.3f, %0.3f)" % (self.viewer.lastMousePos))
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
    def updateOperationsAndRedraw(self):
        for o in self.viewer.operations:
            o.update()
        self.viewer.updateSelection()
    def onOperationDebug(self):
        global debugToolPaths
        debugToolPaths = not debugToolPaths
        self.viewer.updateSelection()
    def onOperationTool(self):
        tooledit = ToolEditDlg(defaultTool)
        tooledit.grid.propertyChanged.connect(self.updateOperationsAndRedraw)
        if tooledit.exec_() < 1:
            tooledit.rollback()
        self.updateOperationsAndRedraw()
    def onOperationMaterial(self):
        matedit = MaterialEditDlg(defaultMaterial)
        matedit.grid.propertyChanged.connect(self.updateOperationsAndRedraw)
        if matedit.exec_() < 1:
            matedit.rollback()
        self.updateOperationsAndRedraw()
    def onOperationGenerate(self):
        ops = self.viewer.operations.toGcode()
        f = file("test.nc", "w")
        for op in ops:
            print(op)
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
