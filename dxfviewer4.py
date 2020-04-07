import math
import re
import sys
import time
from cam.tool import *
from cam.operation import *
from cam.tooledit import *
from cam.matedit import *

import dxfgrabber

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from sender.jobviewer import *
from helpers.dxf import dxfToObjects
from helpers.gui import *
from helpers.geom import *
from helpers.flatitems import *

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
        for i in xrange(self.operations.rowCount()):
            op = self.operations.item(i).operation
            self.curOperation = op
            for n in op.previewPaths:
                n.addToPath(self, self.drawingPath, True, False)
        for i in xrange(self.operations.rowCount()):
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
    def selectByBox(self, box):
        for o in self.objects:
            if box.contains(o.bounds):
                o.setMarked(True)
        self.updateSelection()
    
class DXFApplication(QApplication):
    pass

class DXFMainWindow(QMainWindow, MenuHelper):
    def __init__(self, drawing):
        QMainWindow.__init__(self)
        self.drawing = drawing
        self.toolbar = QToolBar("Operations")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(self.toolbar)
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.viewer = DXFViewer(drawing)
        self.setCentralWidget(self.viewer)
        self.setMinimumSize(1024, 600)
        
        for i in self.viewer.objects:
            i.setMarked(True)
        self.createOperations(ShapeDirection.POCKET)
        self.viewer.mouseMoved.connect(self.updateStatus)
    def updateStatus(self):
        self.statusBar().showMessage("(%0.3f, %0.3f)" % (self.viewer.lastMousePos))
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
        self.viewer.updateSelection()
    def updateOperationsAndRedraw(self):
        for o in self.viewer.operations:
            o.update()
        self.viewer.updateSelection()

def main():    
    app = DXFApplication(sys.argv)
    drawing = dxfgrabber.readfile(sys.argv[1])
    defaultTool.diameter = float(sys.argv[2])
    w = DXFMainWindow(drawing)
    w.show()
    retcode = app.exec_()
    w = None
    app = None
    return retcode
    
sys.exit(main())
