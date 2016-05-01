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

class ShapeDirection:
    OUTSIDE = 1
    INSIDE = 2
    OUTLINE = 3
    POCKET = 4

class CAMTool(object):
    def __init__(self, diameter, feed, plunge, depth):
        self.diameter = float(diameter)
        self.feed = float(feed)
        self.plunge = float(plunge)
        self.depth = float(depth)
        self.clearance = 5
    def begin(self):
        return []
    def followContour(self, nodes, z, last, lastz):
        ops = []
        for i in nodes:
            if type(i) is DrawingLine:
                ops += self.moveTo(i.start, z, last, lastz)
                ops += self.lineTo(i.end, z)
                last = i.end
                lastz = z
            elif type(i) is DrawingArc:
                ops += self.moveTo(i.start, z, last, lastz)
                ops += self.arc(i.start, i.end, i.centre, i.span < 0, z)
                last = i.end
                lastz = z
            elif isinstance(i, DrawingPolyline):
                dops, last, lastz = self.followContour(i.nodes, z, last, lastz)
                ops += dops
        return ops, last, lastz
    def plungeTo(self, z, lastz):
        if z < lastz:
            return ["G1 F%f Z%f" % (self.plunge, z)]
        elif z > lastz:
            return ["G0 Z%f" % (z)]
        else:
            return []
    def moveTo(self, pt, z, last, lastz):
        if pt == last:
            return self.plungeTo(z, lastz)
        return ["G0 Z%f" % self.clearance, "G0 X%f Y%f" % (pt.x(), pt.y())] + self.plungeTo(z, self.clearance)
    def lineTo(self, pt, z):
        return ["G1 F%f X%f Y%f Z%f" % (self.feed, pt.x(), pt.y(), z)]
    def arc(self, last, pt, centre, clockwise, z):
        return ["G%d F%f X%f Y%f I%f J%f Z%f" % (2 if clockwise else 3, self.feed, pt.x(), pt.y(), centre.x() - last.x(), centre.y() - last.y(), z)]

defaultTool = CAMTool(diameter = 2.0, feed = 200.0, plunge = 100.0, depth = 0.3)
defaultZStart = 0
defaultZEnd = -2.5
defaultZTab = -2
defaultNumTabs = 4

class CAMOperation(object):
    def __init__(self, direction, parent):
        self.zstart = float(defaultZStart)
        self.zend = float(defaultZEnd)
        self.direction = direction
        self.parent = parent
        self.tool = defaultTool
        self.ntabs = 0 if direction == ShapeDirection.OUTLINE or direction == ShapeDirection.POCKET else 4
        self.tab_width = 1.5 * self.tool.diameter
        self.fullPaths = self.generateFullPaths()
        self.previewPaths = self.generatePreviewPaths()
    def generateFullPaths(self):
        if self.direction == ShapeDirection.OUTLINE:
            return [self.parent]
        elif self.direction == ShapeDirection.POCKET:
            offsets = []
            r = -self.tool.diameter / 2.0
            while True:
                newparts = offset(self.parent.nodes, r)
                if not newparts:
                    break
                offsets += newparts
                r -= 0.75 * 0.5 * self.tool.diameter
            return offsets
        elif self.direction == ShapeDirection.OUTSIDE:
            r = self.tool.diameter / 2.0
        elif self.direction == ShapeDirection.INSIDE:
            r = -self.tool.diameter / 2.0

        return offset(self.parent.nodes, r)

    def generateTabs(self, path):
        l = path.length()
        n = self.ntabs
        if not n:
            return [(0, l, False)]
        slices = []
        for i in range(n):
            slices.append((i * l / n, (i + 1) * l / n - self.tab_width, False))
            slices.append(((i + 1) * l / n - self.tab_width, (i + 1) * l / n, True))
        return slices

    def generatePreviewPaths(self):
        paths = []
        for p in self.fullPaths:
            for start, end, is_tab in self.generateTabs(p):
                if not is_tab:
                    c = p.cut(start, end)
                    if c is not None:
                        paths.append(c)
        return paths

class DXFViewer(PreviewBase):
    def __init__(self, drawing):
        PreviewBase.__init__(self)
        self.drawing = drawing
        self.operations = []
        self.generateObjects()
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
                    op = CAMOperation(dir, i)
                    self.viewer.operations.append(op)
                    i.setMarked(False)
        self.viewer.createPainters()
        self.viewer.repaint()
    def onOperationGenerate(self):
        f = file("test.nc", "w")
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
