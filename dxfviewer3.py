import math
import re
import sys
import time
from cam.tool import *
from cam.operation import *

import dxfgrabber

from PyQt4 import QtCore, QtGui
from sender.jobviewer import *
from helpers.dxf import dxfToObjects
from helpers.gui import MenuHelper
from helpers.geom import *
from helpers.flatitems import *

class MyRubberBand(QtGui.QRubberBand):
    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        pen = QtGui.QPen(QtGui.QColor(255, 0, 0))
        brush = QtGui.QBrush(QtGui.QColor(255, 0, 0))
        qp.setPen(pen)
        qp.setBrush(brush)
        qp.drawRect(self.rect().adjusted(0, 0, -1, -1))
        qp.fillRect(self.rect().adjusted(0, 0, -1, -1), QtGui.QBrush(QtGui.QColor(255, 0, 0)))
        qp.end()

class DXFViewer(PreviewBase):
    def __init__(self, drawing):
        PreviewBase.__init__(self)
        self.objects = dxfToObjects(drawing)
        self.operations = []
        self.selection = None
        self.updateCursor()
    def getPen(self, item, is_virtual):
        if is_virtual:
            pen = QtGui.QPen(QtGui.QColor(160, 160, 160), defaultTool.diameter * self.getScale())
            pen.setCapStyle(QtCore.Qt.RoundCap)
            pen.setJoinStyle(QtCore.Qt.RoundJoin)
            return pen
        if item.marked:
            return self.activeItemPen
        return self.drawingPen
    def createPainters(self):
        self.initPainters()
        self.drawingPath = QtGui.QGraphicsScene()
        self.previewPen = QtGui.QPen(QtGui.QColor(160, 160, 160), 0)
        self.drawingPen = QtGui.QPen(QtGui.QColor(0, 0, 0), 0)
        self.drawingPen2 = QtGui.QPen(QtGui.QColor(255, 0, 0), 0)
        self.activeItemPen = QtGui.QPen(QtGui.QColor(0, 255, 0), 0)
        #self.drawingPen.setCapStyle(QtCore.Qt.RoundCap)
        #self.drawingPen.setJoinStyle(QtCore.Qt.RoundJoin)
        for o in self.operations:
            for n in o.previewPaths:
                n.addToPath(self, self.drawingPath, True)
        for o in self.objects:
            o.addToPath(self, self.drawingPath, False)
    def renderDrawing(self, qp):
        trect = QtCore.QRectF(self.rect()).translated(self.translation)
        if self.drawingPath is not None:
            self.drawingPath.render(qp, QtCore.QRectF(self.rect()), trect)
    def updateCursor(self):
        self.setCursor(QtCore.Qt.CrossCursor)
    def getItemAtPoint(self, p):
        matches = sorted([(i, i.distanceTo(p)) for i in self.objects], lambda o1, o2: cmp(o1[1], o2[1]))
        mind = matches[0][1] if len(matches) > 0 else None
        second = matches[1][1] if len(matches) > 1 else None
        if second is not None and abs(second - mind) < 1 / self.getScale():
            print "Warning: Multiple items at similar distance"
        if mind < 10 / self.getScale():
            return matches[0][0]
    def mousePressEvent(self, e):
        b = e.button()
        if b == QtCore.Qt.LeftButton:
            p = e.posF()
            lp = self.physToLog(p)
            item = self.getItemAtPoint(lp)
                
            if item:
                item.setMarked(not item.marked)
                self.createPainters()
                self.repaint()
            else:
                if self.selection is None:
                    self.selection = MyRubberBand(QtGui.QRubberBand.Rectangle, self)
                self.selectionOrigin = e.pos()
                self.selection.setGeometry(QtCore.QRect(e.pos(), QtCore.QSize()))
                self.selection.show()
        elif b == QtCore.Qt.RightButton:
            self.start_point = e.posF()
            self.prev_point = e.posF()
            self.start_origin = (self.x0, self.y0)
            self.dragging = True
    def mouseMoveEvent(self, e):
        if self.selection and self.selection.isVisible():
            self.selection.setGeometry(QtCore.QRect(self.selectionOrigin, e.pos()).normalized())
        PreviewBase.mouseMoveEvent(self, e)
    def mouseReleaseEvent(self, e):
        if self.selection and self.selection.isVisible():
            ps = self.unproject(self.selectionOrigin.x(), self.selectionOrigin.y())
            pe = self.unproject(e.pos().x(), e.pos().y())
            box = QtCore.QRectF(qp(ps), qp(pe)).normalized()
            
            self.selectByBox(box)
            self.selection.hide()
            self.selection = None
        PreviewBase.mouseReleaseEvent(self, e)
    def selectByBox(self, box):
        for o in self.objects:
            if box.contains(o.bounds):
                o.setMarked(True)
        self.createPainters()
        self.repaint()
    
class DXFApplication(QtGui.QApplication):
    pass

class DXFMainWindow(QtGui.QMainWindow, MenuHelper):
    def __init__(self, drawing):
        QtGui.QMainWindow.__init__(self)
        self.drawing = drawing
        self.toolbar = QtGui.QToolBar("Operations")
        self.toolbar.setToolButtonStyle(QtCore.Qt.ToolButtonTextOnly)
        self.toolbar.addAction("Profile").triggered.connect(self.onOperationProfile)
        self.toolbar.addAction("Cutout").triggered.connect(self.onOperationCutout)
        self.toolbar.addAction("Pocket").triggered.connect(self.onOperationPocket)
        self.toolbar.addAction("Engrave").triggered.connect(self.onOperationEngrave)
        self.toolbar.addAction("Delete").triggered.connect(self.onOperationDelete)
        self.toolbar.addAction("Generate").triggered.connect(self.onOperationGenerate)
        self.addToolBar(self.toolbar)
        self.viewer = DXFViewer(drawing)
        self.setCentralWidget(self.viewer)
        self.setMinimumSize(800, 600)
    def onOperationProfile(self):
        self.createOperations(ShapeDirection.OUTSIDE)
    def onOperationCutout(self):
        self.createOperations(ShapeDirection.INSIDE)
    def onOperationPocket(self):
        self.createOperations(ShapeDirection.POCKET)
    def onOperationEngrave(self):
        self.createOperations(ShapeDirection.OUTLINE)
    def onOperationDelete(self):
        toDelete = set([])
        for i in self.viewer.objects:
            if i.marked:
                toDelete.add(i)
                i.setMarked(False)
        self.viewer.operations = [o for o in self.viewer.operations if o.parent not in toDelete]
        self.viewer.createPainters()
        self.viewer.repaint()
    def createOperations(self, dir):
        for i in self.viewer.objects:
            if i.marked:
                if dir == ShapeDirection.OUTLINE or isinstance(i, DrawingPolyline):
                    op = CAMOperation(dir, i, defaultTool)
                    self.viewer.operations.append(op)
                    i.setMarked(False)
        self.viewer.createPainters()
        self.viewer.repaint()
    def onOperationGenerate(self):
        ops = ["G90 G17"]
        tool = defaultTool
        lastTool = None
        for o in self.viewer.operations:
            if o.tool != lastTool:
                ops += tool.begin()
                lastTool = tool
            lastz = 5
            last = None
            for p in o.fullPaths:
                z = defaultZStart
                tabs = o.generateTabs(p)
                while z > defaultZEnd:
                    z -= o.tool.depth
                    if z < defaultZEnd:
                        z = defaultZEnd
                    for start, end, is_tab in tabs:
                        opsc, last, lastz = o.tool.followContour([p.cut(start, end)], z if not is_tab else max(z, defaultZTab), last, lastz)
                        ops += opsc
        ops += lastTool.moveTo(qpxy(0, 0), lastTool.clearance, last, lastz)
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
