import math
import re
import sys
import time

import dxfgrabber

from PyQt4 import QtCore, QtGui
from sender.jobviewer import *
from helpers.gui import MenuHelper
from helpers.geom import *
from helpers.flatitems import *

class DXFViewer(PreviewBase):
    def __init__(self, drawing):
        PreviewBase.__init__(self)
        self.drawing = drawing
        self.generateObjects()
        self.updateCursor()
    def getPen(self, item):
        if item.marked:
            return self.activeItemPen
        return self.drawingPen
    def generateObjects(self):
        self.objects = []
        for i in self.drawing.entities.get_entities():
            it = type(i)
            if it is dxfgrabber.entities.Circle:
                self.objects.append(DrawingCircle(QtCore.QPointF(i.center[0], i.center[1]), i.radius))
            elif it is dxfgrabber.entities.Arc:
                if i.endangle > i.startangle:
                    self.objects.append(DrawingArc(QtCore.QPointF(i.center[0], i.center[1]), i.radius, i.endangle * math.pi / 180.0, (i.startangle - i.endangle) * math.pi / 180.0))
                else:
                    self.objects.append(DrawingArc(QtCore.QPointF(i.center[0], i.center[1]), i.radius, i.startangle * math.pi / 180.0, twopi + (i.endangle - i.startangle) * math.pi / 180.0))
            elif it is dxfgrabber.entities.Line:
                self.objects.append(DrawingLine(QtCore.QPointF(i.start[0], i.start[1]), QtCore.QPointF(i.end[0], i.end[1])))
            elif it is dxfgrabber.entities.LWPolyline:
                nodes = []
                points = []
                for p in range(len(i.points)):
                    points.append(i.points[p])
                if i.is_closed:
                    points.append(points[0])
                for p in range(len(points) - 1):
                    if i.bulge[p]:
                        #print i.bulge[p]
                        p1 = i.points[p]
                        p2 = i.points[(p + 1) % len(i.points)]
                        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
                        theta = 4 * math.atan(i.bulge[p])
                        dist = math.sqrt(dx ** 2 + dy ** 2)
                        a = math.atan2(dy, dx)
                        d = dist / 2.0
                        r = abs(d / math.sin(theta / 2))
                        c = d / math.tan(theta / 2)
                        da = math.pi / 2.0
                        xm0 = (p1[0] + p2[0]) / 2.0
                        ym0 = (p1[1] + p2[1]) / 2.0
                        xm = xm0 - c * math.sin(a)
                        ym = ym0 + c * math.cos(a)
                        sangle = math.atan2(p1[1] - ym, p1[0] - xm)
                        span = theta
                        nodes.append(DrawingArc(QtCore.QPointF(xm, ym), r, sangle, span))
                        #self.drawArcImpl(xm, ym, 0, 0, r, sangle, theta * 360 / (2 * math.pi), self.drawingPath, self.drawingPen)
                    else:
                        if points[p] != points[p + 1]:
                            nodes.append(DrawingLine(QtCore.QPointF(*points[p]), QtCore.QPointF(*points[p + 1])))
                        #if p == 0:
                        #    polyline.moveTo(points[p][0], points[p][1])
                        #polyline.lineTo(points[p + 1][0], points[p + 1][1])
                polyline = DrawingPolyline(nodes)
                self.objects.append(polyline)
            else:
                print str(it)
        
    def createPainters(self):
        self.initPainters()
        self.drawingPath = QtGui.QGraphicsScene()
        self.drawingPen = QtGui.QPen(QtGui.QColor(0, 0, 0), 0)
        self.drawingPen2 = QtGui.QPen(QtGui.QColor(255, 0, 0), 0)
        self.activeItemPen = QtGui.QPen(QtGui.QColor(0, 255, 0), 0)
        #self.drawingPen.setCapStyle(QtCore.Qt.RoundCap)
        #self.drawingPen.setJoinStyle(QtCore.Qt.RoundJoin)
        for o in self.objects:
            o.addToPath(self, self.drawingPath)
    def renderDrawing(self, qp):
        trect = QtCore.QRectF(self.rect()).translated(self.translation)
        if self.drawingPath is not None:
            self.drawingPath.render(qp, QtCore.QRectF(self.rect()), trect)
    def updateCursor(self):
        self.setCursor(QtCore.Qt.CrossCursor)
    def getItemAtPoint(self, p):
        mind = None
        for i in self.objects:
            id = i.distanceTo(p)
            if mind is None or mind > id:
                mind = id
                item = i
        if mind < 20 / self.getScale():
            return item
    def mousePressEvent(self, e):
        b = e.button()
        if b == QtCore.Qt.LeftButton or b == QtCore.Qt.MiddleButton:
            p = e.posF()
            lp = self.physToLog(p)
            item = self.getItemAtPoint(lp)
                
            if item:
                if issubclass(type(item), DrawingPolyline):
                    if b == QtCore.Qt.LeftButton:
                        newnodes = offset(item.nodes, 3)
                    else:
                        newnodes = offset(item.nodes, -1)
                    if newnodes:
                        self.objects.append(DrawingPolyline(newnodes))
                        self.createPainters()
                        self.repaint()
                else:
                    item.setMarked(not item.marked)
                    self.createPainters()
                    self.repaint()
        elif b == QtCore.Qt.RightButton:
            self.start_point = e.posF()
            self.prev_point = e.posF()
            self.start_origin = (self.x0, self.y0)
            self.dragging = True
    
class DXFApplication(QtGui.QApplication):
    pass

class DXFMainWindow(QtGui.QMainWindow, MenuHelper):
    def __init__(self, drawing):
        QtGui.QMainWindow.__init__(self)
        self.drawing = drawing
        self.viewer = DXFViewer(drawing)
        self.setCentralWidget(self.viewer)
        self.setMinimumSize(800, 600)

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
