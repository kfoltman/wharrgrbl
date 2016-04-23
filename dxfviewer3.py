import math
import re
import sys
import time

import dxfgrabber

from PyQt4 import QtCore, QtGui
from sender.jobviewer import *
from helpers.gui import MenuHelper
from helpers.geom import *

class DrawingItem(object):
    def __init__(self):
        self.marked = False
        self.windings = None
    def setMarked(self, marked):
        self.marked = marked
    def addArrow(self, viewer, center, path, angle):
        r = 4
        c = QtCore.QPointF(*center)
        sa = angle
        da = angle + 0.4 + math.pi
        path.addLine(QtCore.QLineF(circ(c, r, -sa), circ(c, r, -da)), viewer.getPen(self))
        da2 = angle - 0.4 + math.pi
        path.addLine(QtCore.QLineF(circ(c, r, -sa), circ(c, r, -da2)), viewer.getPen(self))
        path.addLine(QtCore.QLineF(circ(c, r, -da2), circ(c, r, -da)), viewer.getPen(self))
    def addDebug(self, path, center):
        if self.windings:
            txt = path.addSimpleText("%s" % self.windings)
            txt.setX(center[0])
            txt.setY(center[1])

class DrawingLine(DrawingItem):
    def __init__(self, start, end):
        DrawingItem.__init__(self)
        self.start = start
        self.end = end
        self.startAngle = self.endAngle = math.atan2(self.end.y() - self.start.y(), self.end.x() - self.start.x())
    def addToPath(self, viewer, path):
        start = viewer.project(self.start.x(), self.start.y(), 0)
        end = viewer.project(self.end.x(), self.end.y(), 0)
        center = viewer.project((self.start.x() + self.end.x()) / 2.0, (self.start.y() + self.end.y()) / 2.0, 0)
        self.addDebug(path, center)
        path.addLine(start[0], start[1], end[0], end[1], viewer.getPen(self))
        if True:
            self.addArrow(viewer, center, path, self.startAngle)
    def reversed(self):
        return DrawingLine(self.end, self.start)
    def distanceTo(self, p):
        return distPointToLine(QtCore.QPointF(*p), QtCore.QLineF(self.start, self.end))
    def toLine(self):
        return QtCore.QLineF(self.start, self.end)

class DrawingArc(DrawingItem):
    def __init__(self, centre, radius, sangle, span):
        DrawingItem.__init__(self)
        self.centre = centre
        self.radius = radius
        self.sangle = nangle(sangle)
        self.span = span
        d = math.pi / 2 if self.span >= 0 else -math.pi / 2
        self.startAngle = nangle(sangle + d)
        self.endAngle = nangle(sangle + span + d)
        self.start = circ(self.centre, self.radius, self.sangle)
        self.end = circ(self.centre, self.radius, self.sangle + self.span)
    def reversed(self):
        return DrawingArc(self.centre, self.radius, nangle(self.sangle + self.span), -self.span)
    def angdist(self, angle):
        angle -= self.sangle
        if self.span > 0:
            return angle % twopi
        else:
            return ((-angle) % twopi)
    def angdistp(self, p):
        return self.angdist(tang(self.centre, p))
    
    def inarc(self, theta):
        theta = nangle(theta)
        if self.span > 0:
            return (theta - self.sangle) % twopi <= self.span
        if self.span < 0:
            return (self.sangle - theta) % twopi <= -self.span
        return False
    def inarcp(self, p):
        return self.inarc(tang(self.centre, p))
    def minX(self):
        x = min(self.start.x(), self.end.x())
        # Check for crossing 
        if self.span > 0 and self.sangle + self.span > math.pi:
            x = self.centre.x() - self.radius
        if self.span < 0 and self.sangle + self.span < -math.pi:
            x = self.centre.x() - self.radius
        return x
    def maxX(self):
        x = max(self.start.x(), self.end.x())
        # Check for crossing 
        if self.span > 0 and self.sangle < 0 and self.sangle + self.span > 0:
            x = self.centre.x() + self.radius
        if self.span < 0 and self.sangle > 0 and self.sangle + self.span < 0:
            x = self.centre.x() + self.radius
        return x
    @staticmethod
    def fromtangents(p1, p2, alpha, beta):
        eps = 0.001
        dcos = math.cos(beta) - math.cos(alpha)
        if abs(dcos) > eps and abs(p1.x() - p2.x()) > eps:
            r = (p2.x() - p1.x()) / dcos
        else:
            dsin = math.sin(beta) - math.sin(alpha)
            if abs(dsin) > eps and abs(p1.y() - p2.y()) > eps:
                r = (p2.y() - p1.y()) / dsin
            else:
                print "No solution exists - bad slopes"
                return # no solution
        if r < 0:
            r = -r
            alpha += math.pi
            beta += math.pi
        c1 = circ(p1, -r, alpha)
        c2 = circ(p2, -r, beta)
        if pdist(c1, c2) > eps:
            print "No solution exists - too far away"
            return # No solution exists
        c = interp(c1, c2, 0.5)
        xc, yc = c.x(), c.y()
        if abs(pdist(QtCore.QPointF(xc, yc), p1) - abs(r)) > eps:
            print "Centre point is not at r distance to p1", p1, p2, xc, yc, r, r2d(alpha), r2d(beta), dcos, pdist(QtCore.QPointF(xc, yc), p1)
            assert False
        if abs(pdist(QtCore.QPointF(xc, yc), p2) - abs(r)) > eps:
            print "Centre point is not at r distance to p2", p1, p2, xc, yc, r, r2d(alpha), r2d(beta), dcos, pdist(QtCore.QPointF(xc, yc), p2)
            assert False
        if pdist(circ4(xc, yc, r, alpha), p1) > eps:
            print "Incorrect calculated p1", p1, p2, xc, yc, r, r2d(alpha), r2d(beta), pdist(circ4(xc, yc, r, alpha), p1)
            assert False
        if pdist(circ4(xc, yc, r, beta), p2) > eps:
            print "Incorrect calculated p2", p1, p2, xc, yc, r, r2d(alpha), r2d(beta)
            assert False
        #return DrawingArc(QtCore.QPointF(xc, yc), r, beta, -nangle(beta - alpha))
        return DrawingArc(QtCore.QPointF(xc, yc), r, alpha, nangle(beta - alpha))
    @staticmethod
    def fromangles(centre, radius, startAngle, endAngle, dir):
        span = nangle(endAngle - startAngle)
        sangle = startAngle - dir * math.pi / 2
        return DrawingArc(centre, radius, sangle, span)
    def addToPath(self, viewer, path):
        xc, yc = viewer.project(self.centre.x(), self.centre.y(), 0)
        r = self.radius * viewer.getScale()
        sangle = r2d(self.sangle)
        span = r2d(self.span)
        pp = QtGui.QPainterPath()
        pp.arcMoveTo(QtCore.QRectF(xc - r, yc - r, 2.0 * r, 2.0 * r), sangle)
        pp.arcTo(QtCore.QRectF(xc - r, yc - r, 2.0 * r, 2.0 * r), sangle, span)
        self.addDebug(path, circ3(xc, yc, r, -(self.sangle + self.span / 2)))
        if False:
            pp.moveTo(*viewer.project(self.minX(), self.centre.y() - self.radius, 0))
            pp.lineTo(*viewer.project(self.minX(), self.centre.y() + self.radius, 0))
            pp.moveTo(*viewer.project(self.maxX(), self.centre.y() - self.radius, 0))
            pp.lineTo(*viewer.project(self.maxX(), self.centre.y() + self.radius, 0))
        path.addPath(pp, viewer.getPen(self))
        a = self.sangle
        self.addArrow(viewer, circ3(xc, yc, r, -a), path, self.startAngle)
        a = self.sangle + self.span
        self.addArrow(viewer, circ3(xc, yc, r, -a), path, self.endAngle)
    def distanceTo(self, p):
        p = QtCore.QPointF(*p)
        theta = tang(self.centre, p)
        sangle = self.sangle
        span = self.span
        if span < 0:
            sangle += span
            span = -span
        theta -= sangle
        theta %= twopi
        if theta < span:
            r = pdist(p, self.centre)
            return abs(r - self.radius)
        else:
            dist = min(pdist(p, self.start), pdist(p, self.end))
            return dist

def findOrientation(nodes):
    angle = 0
    for i in range(len(nodes)):
        angle += nangle(nodes[(i + 1) % len(nodes)].startAngle - nodes[i].startAngle)
    return sign(angle)

def reversed_nodes(nodes):
    return [i.reversed() for i in reversed(nodes)]

def intersections(d1, d2):
    if type(d1) is DrawingLine and type(d2) is DrawingLine:
        p = QtCore.QPointF()
        # a > 0 -> the d2 crosses d1 right to left
        a = nangle(d2.startAngle - d1.startAngle)
        if abs(a) < defaultEps:
            a = 0
        if d1.toLine().intersect(d2.toLine(), p) == QtCore.QLineF.BoundedIntersection:
            return [(p, a)]
        return []
    if type(d1) is DrawingArc and type(d2) is DrawingArc:
        dist = pdist(d1.centre, d2.centre)
        if dist > d1.radius + d2.radius or dist == 0:
            return []
        along = (d1.radius + dist - d2.radius) * 0.5
        across2 = d1.radius ** 2 - along ** 2
        if across2 < 0:
            return []
        midpoint = interp(d1.centre, d2.centre, along / dist)
        #if across2 < defaultEps:
        #    return [midpoint]
        theta = tang(d2.centre, d1.centre)
        d = circ(qpxy(0, 0), math.sqrt(across2), theta + math.pi / 2)
        p1 = midpoint + d
        p2 = midpoint - d
        pts = []
        if d1.inarcp(p1) and d2.inarcp(p1):
            pts.append((p1, None))
        if p1 != p2 and d1.inarcp(p2) and d2.inarcp(p2):
            pts.append((p2, None))
        return pts
    if type(d1) is DrawingArc and type(d2) is DrawingLine:
        d1, d2 = d2, d1
    if type(d1) is DrawingLine and type(d2) is DrawingArc:
        line = d1.toLine()
        line2 = QtCore.QLineF(line.p1(), d2.centre)
        a = d2r(line.angleTo(line2))
        across = line2.length() * math.sin(a)
        along = line2.length() * math.cos(a)
        if abs(across) > d2.radius:
            return []
        third = math.sqrt(d2.radius ** 2 - across ** 2)
        pts = []

        def cangle(p):
            if d2.span > 0:
                a = nangle(d1.startAngle - tang(d2.centre, p) + math.pi / 2)
            else:
                a = nangle(d1.startAngle - tang(d2.centre, p) - math.pi / 2)
            return 0.0 if abs(a) < defaultEps else a
        if along + third >= 0 and along + third <= line.length():
            p = interp(line.p1(), line.p2(), (along + third) * 1.0 / line.length())
            if d2.inarcp(p):
                pts.append((p, cangle(p)))
        if along - third >= 0 and along - third <= line.length() and abs(third) > 0:
            p = interp(line.p1(), line.p2(), (along - third) * 1.0 / line.length())
            if d2.inarcp(p) and not (len(pts) and pts[0] == p):
                pts.append((p, cangle(p)))
        return pts
    return []
        
#print intersections(DrawingLine(qpxy(0, 0), qpxy(30, 0)), DrawingArc(qpxy(15, 0), 3, 0, math.pi / 2))
#print intersections(DrawingArc(qpxy(0, 0), 10, 0, math.pi / 2), DrawingArc(qpxy(20, 0), 10, math.pi / 2, math.pi / 4))
#sys.exit(1)

def removeLoops(nodes):
    orient = findOrientation(nodes)
    events = []
    splitpoints = {}
    for n in nodes:
        if type(n) is DrawingLine:
            splitpoints[n] = []
            if n.start.x() == n.end.x():
                events.append((n.start.x(), 'L', n))
            else:
                if n.start.x() < n.end.x():
                    events.append((n.start.x(), 'S', n))
                    events.append((n.end.x(), 'E', n))
                else:
                    events.append((n.end.x(), 'S', n))
                    events.append((n.start.x(), 'E', n))
        if type(n) is DrawingArc:
            splitpoints[n] = []
            assert(n.minX() <= n.maxX())
            events.append((n.minX(), 'S', n))
            events.append((n.maxX(), 'E', n))
    events = sorted(events, lambda x, y: cmp(x[0], y[0]))
    cur_lines = set()
    for e in events:
        #print e, cur_lines
        if e[1] == 'S':
            cur_lines.add(e[2])
        elif e[1] == 'E':
            cur_lines.remove(e[2])
        if e[1] == 'E' or e[1] == 'L':
            for i in cur_lines:
                pp = intersections(i, e[2])
                for p, angle in pp:
                    if p != i.start and p != i.end:
                        splitpoints[i].append(p)
                        i.setMarked(True)
                    if p != e[2].start and p != e[2].end:
                        splitpoints[e[2]].append(p)
                        e[2].setMarked(True)
    nodes2 = []
    for n in nodes:
        sp = splitpoints[n]
        if sp:
            if type(n) is DrawingLine:
                sp = sorted(sp, lambda a, b: cmp(pdist(a, n.start), pdist(b, n.start)))
                last = n.start
                for i in sp:
                    if last != i:
                        nodes2.append(DrawingLine(last, i))
                    last = i
                if last != n.end:
                    nodes2.append(DrawingLine(last, n.end))            
            elif type(n) is DrawingArc:
                sp = sorted(sp, lambda a, b: cmp(n.angdistp(a), n.angdistp(b)))
                last = 0
                dir = 1 if n.span > 0 else -1
                for i in sp:
                    this = n.angdistp(i) * dir
                    nodes2.append(DrawingArc(n.centre, n.radius, n.sangle + last, this - last))
                    last = this
                if last != n.span:
                    nodes2.append(DrawingArc(n.centre, n.radius, n.sangle + last, n.span - last))
        else:
            nodes2.append(n)
    lastAngle = nodes2[-1].startAngle
    sumAngle = 0
    points = {}
    nodes3 = []
    for n in nodes2:
        windings = 0
        if type(n) is DrawingLine:
            mid = interp(n.start, n.end, 0.5)
        else:
            mid = DrawingArc(n.centre, n.radius, n.sangle, n.span / 2).end
        if False:
            normal = circ(qpxy(0, 0), 1, tang(n.start, n.end) + math.pi / 2)
            l = DrawingLine(mid, mid + normal)
            nodes3.append(l)
        normal = circ(qpxy(0, 0), 10000, tang(n.start, n.end) + math.pi / 2)
        l = DrawingLine(mid, mid + normal)
        for m in nodes2:
            if n is m:
                continue
            for p, angle in intersections(l, m):
                windings += sign(angle)
        n.windings = windings
        if sign(windings) != orient:
            nodes3.append(n)
        #nodes3.append(n)
    return nodes3

def offset(nodes, r):
    if findOrientation(nodes) > 0:
        nodes = reversed_nodes(nodes)
    nodes2 = []
    s = math.pi / 2
    if r < 0:
        r = -r
        s = -s
    rc = r if s > 0 else -r
    rd = r / abs(r)
    sp = s > 0
    for i in xrange(len(nodes)):
        prev = nodes[(i - 1) % len(nodes)]
        this = nodes[i]
        next = nodes[(i + 1) % len(nodes)]
        pa = nangle(this.startAngle - prev.endAngle)
        na = nangle(next.startAngle - this.endAngle)
        theta = nangle(next.startAngle - this.endAngle)
        dir = 1 if theta > 0 else -1
        #print type(this), this.start, this.end, this.startAngle * 180 / math.pi, this.endAngle * 180 / math.pi
        start = circ(this.start, r, this.startAngle + s)
        end = circ(this.end, r, this.endAngle + s)
        if type(this) is DrawingLine:
            if start != end:
                newl = DrawingLine(start, end)
                newl.orig_start = this.start
                nodes2.append(newl)
        if type(this) is DrawingArc:
            if (this.span < 0) != (s > 0):
                newr = this.radius - r
            else:
                newr = this.radius + r
            if newr > 0:
                arc = DrawingArc(this.centre, newr, this.sangle, this.span)
                arc.orig_start = this.start
                nodes2.append(arc)
    nodes = list(nodes2)
    nodes2 = []
    for i in xrange(len(nodes)):
        prev = nodes[(i - 1) % len(nodes)]
        this = nodes[i]
        if pdist(this.start, prev.end) > 0.0001:
            is_concave = nangle(this.startAngle - prev.endAngle) > 0
            if (s < 0) == is_concave:
                nodes2.append(DrawingArc.fromtangents(prev.end, this.start, prev.endAngle + math.pi / 2, this.startAngle + math.pi / 2))
            else:
                nodes2.append(DrawingLine(prev.end, this.orig_start))
                nodes2.append(DrawingLine(this.orig_start, this.start))
        nodes2.append(this)
    return removeLoops(nodes2)

class DrawingPolyline(DrawingItem):
    def __init__(self, nodes):
        DrawingItem.__init__(self)
        self.nodes = nodes
        self.startAngle = nodes[0].startAngle
        self.endAngle = nodes[-1].endAngle
        self.start = nodes[0].start
        self.end = nodes[-1].end
    def addToPath(self, viewer, path):
        for i in self.nodes:
            i.addToPath(viewer, path)
    def distanceTo(self, p):
        if len(self.nodes) == 0:
            return None
        return min([i.distanceTo(p) for i in self.nodes])
    def setMarked(self, marked):
        self.marked = marked
        for i in self.nodes:
            i.setMarked(marked)
        angle = 0
        for i in range(len(self.nodes)):
            la = (self.nodes[(i + 1) % len(self.nodes)].startAngle - self.nodes[i].startAngle)
            la = nangle(la)
            angle += la
        if abs(angle) < 1.99 * math.pi:
            print "Not a closed shape ? %f" % (angle * 180 / math.pi)
        if angle < 0:
            print "Shape to the right"
        else:
            print "Shape to the left"
            
        #self.nodes = nodes2

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
                self.objects.append(DrawingArc(QtCore.QPointF(i.center[0], i.center[1]), i.radius, 0, twopi))
                #self.drawArcImpl(i.center[0], i.center[1], 0, 0, i.radius, 0, 360, self.drawingPath, self.drawingPen)
            elif it is dxfgrabber.entities.Arc:
                if i.endangle > i.startangle:
                    self.objects.append(DrawingArc(QtCore.QPointF(i.center[0], i.center[1]), i.radius, i.endangle * math.pi / 180.0, (i.startangle - i.endangle) * math.pi / 180.0))
                else:
                    self.objects.append(DrawingArc(QtCore.QPointF(i.center[0], i.center[1]), i.radius, i.startangle * math.pi / 180.0, twopi + (i.endangle - i.startangle) * math.pi / 180.0))
                #if i.endangle > i.startangle:
                #    self.drawArcImpl(i.center[0], i.center[1], 0, 0, i.radius, i.startangle, i.endangle - i.startangle, self.drawingPath, self.drawingPen)
                #else:
                #    self.drawArcImpl(i.center[0], i.center[1], 0, 0, i.radius, i.startangle, 360 + i.endangle - i.startangle, self.drawingPath, self.drawingPen)
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
                if type(item) is DrawingPolyline:
                    if b == QtCore.Qt.LeftButton:
                        self.objects.append(DrawingPolyline(offset(item.nodes, 3)))
                    else:
                        self.objects.append(DrawingPolyline(offset(item.nodes, -2)))
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
