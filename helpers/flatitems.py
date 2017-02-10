import math
import collections
from helpers.geom import *
from PyQt4.QtGui import *
import sys

# Extend the bounds to account for numerical errors
boundsMargin = 0.01

class DrawingItem(object):
    def __init__(self):
        self.marked = False
        self.windings = None
        self.weight = None
    def setMarked(self, marked):
        self.marked = marked
    def setIsTab(self, is_tab):
        self.is_tab = is_tab
    def addArrow(self, viewer, center, path, angle, is_virtual, is_debug):
        r = 4
        if is_debug:
            r = 8
        c = QPointF(*center)
        sa = angle
        da = angle + 0.4 + math.pi
        pen = viewer.getPen(self, is_virtual, is_debug)
        if pen is None:
            return
        path.addLine(QLineF(circ(c, r, -sa), circ(c, r, -da)), pen)
        da2 = angle - 0.4 + math.pi
        path.addLine(QLineF(circ(c, r, -sa), circ(c, r, -da2)), pen)
        path.addLine(QLineF(circ(c, r, -da2), circ(c, r, -da)), pen)
    def addDebug(self, viewer, path, cx, cy, angle):
        if self.weight is not None:
            def txt(s, pos):
                txt = path.addSimpleText("%s" % s)
                txt.setX(pos[0] - txt.boundingRect().width() / 2)
                txt.setY(pos[1] - txt.boundingRect().height() / 2)
            
            r = 20.0 / viewer.getScale()
            
            cl2 = QLineF.fromPolar(r, angle + 90).translated(cx, cy)
            center2 = viewer.project(cl2.x2(), cl2.y2(), 0)
            
            cl3 = QLineF.fromPolar(r, angle - 90).translated(cx, cy)
            center1 = viewer.project(cl3.x2(), cl3.y2(), 0)
            w1, w2 = self.weight.split("/")
            txt(w1, center1)
            txt(w2, center2)
    def calcBounds(self):
        return expandRect(QRectF(qpxy(self.minX() - boundsMargin, self.minY() - boundsMargin), qpxy(self.maxX() + boundsMargin, self.maxY() + boundsMargin)))
    def typeName(self):
        return type(self).__name__.replace("Drawing", "")
    def isBoundary(self):
        if self.weight is None:
            return True
        w = map(int, self.weight.split("/"))
        return (w[0] <= 0 and w[1] > 0) or (w[1] <= 0 and w[0] > 0)

class DrawingLine(DrawingItem):
    def __init__(self, start, end):
        DrawingItem.__init__(self)
        self.start = start
        self.end = end
        self.startAngle = self.endAngle = math.atan2(self.end.y() - self.start.y(), self.end.x() - self.start.x())
        self.bounds = self.calcBounds()
    def addToPath(self, viewer, path, is_virtual, is_debug):
        pen = viewer.getPen(self, is_virtual, is_debug)
        if pen is None:
            return
        start = viewer.project(self.start.x(), self.start.y(), 0)
        end = viewer.project(self.end.x(), self.end.y(), 0)
        cl = self.toLine()
        cl.setLength(cl.length() / 2.0)
        center = viewer.project(cl.x2(), cl.y2(), 0)
        if is_debug:
            self.addDebug(viewer, path, cl.x2(), cl.y2(), cl.angle())
        path.addLine(start[0], start[1], end[0], end[1], pen)
        if not is_virtual or is_debug:
            self.addArrow(viewer, center, path, self.startAngle, is_virtual, is_debug)
    def reversed(self):
        return DrawingLine(self.end, self.start)
    def distanceTo(self, p):
        return distPointToLine(QPointF(*p), QLineF(self.start, self.end))
    def toLine(self):
        return QLineF(self.start, self.end)
    def length(self):
        return QLineF(self.start, self.end).length()
    def clone(self):
        dl = DrawingLine(self.start, self.end)
        dl.weight = self.weight
        return dl
    def cut(self, start, end):
        cur = self.length()
        if cur <= 0:
            return self.clone()
        dl = DrawingLine(interp(self.start, self.end, max(start, 0) * 1.0 / cur), interp(self.start, self.end, min(end, cur) * 1.0 / cur))
        dl.weight = self.weight
        return dl
    def minX(self):
        return min(self.start.x(), self.end.x())
    def minY(self):
        return min(self.start.y(), self.end.y())
    def maxX(self):
        return max(self.start.x(), self.end.x())
    def maxY(self):
        return max(self.start.y(), self.end.y())

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
        self.bounds = self.calcBounds()
    def length(self):
        return abs(self.span) * self.radius
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
        if self.span > 0:
            return (theta - self.sangle) % twopi <= self.span
        if self.span < 0:
            return (self.sangle - theta) % twopi <= -self.span
        return False
    def inarcp(self, p):
        return self.inarc(tang(self.centre, p))
    def interp(self, theta):
        return circ(self.centre, self.radius, self.sangle + theta * self.span)
    def minY(self):
        y = min(self.start.y(), self.end.y())
        if self.inarc(-math.pi / 2):
            y = self.centre.y() - self.radius
        return y
    def maxY(self):
        y = max(self.start.y(), self.end.y())
        if self.inarc(math.pi / 2):
            y = self.centre.y() + self.radius
        return y
    def minX(self):
        x = min(self.start.x(), self.end.x())
        # Check for crossing 
        if self.inarc(math.pi):
            x = self.centre.x() - self.radius
        return x
    def maxX(self):
        x = max(self.start.x(), self.end.x())
        # Check for crossing 
        if self.inarc(0):
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
            print "No solution exists - too far away - %f" % pdist(c1, c2)
            return # No solution exists
        c = interp(c1, c2, 0.5)
        xc, yc = c.x(), c.y()
        if abs(pdist(QPointF(xc, yc), p1) - abs(r)) > eps:
            print "Centre point is not at r distance to p1", p1, p2, xc, yc, r, r2d(alpha), r2d(beta), dcos, pdist(QPointF(xc, yc), p1)
            assert False
        if abs(pdist(QPointF(xc, yc), p2) - abs(r)) > eps:
            print "Centre point is not at r distance to p2", p1, p2, xc, yc, r, r2d(alpha), r2d(beta), dcos, pdist(QPointF(xc, yc), p2)
            assert False
        if pdist(circ4(xc, yc, r, alpha), p1) > eps:
            print "Incorrect calculated p1", p1, p2, xc, yc, r, r2d(alpha), r2d(beta), pdist(circ4(xc, yc, r, alpha), p1)
            assert False
        if pdist(circ4(xc, yc, r, beta), p2) > eps:
            print "Incorrect calculated p2", p1, p2, xc, yc, r, r2d(alpha), r2d(beta)
            assert False
        #return DrawingArc(QPointF(xc, yc), r, beta, -nangle(beta - alpha))
        return DrawingArc(QPointF(xc, yc), r, alpha, nangle(beta - alpha))
    @staticmethod
    def fromangles(centre, radius, startAngle, endAngle, dir):
        span = nangle(endAngle - startAngle)
        sangle = startAngle - dir * math.pi / 2
        return DrawingArc(centre, radius, sangle, span)
    def addToPath(self, viewer, path, is_virtual, is_debug):
        xc, yc = viewer.project(self.centre.x(), self.centre.y(), 0)
        r = self.radius * viewer.getScale()
        sangle = r2d(self.sangle)
        span = r2d(self.span)
        pp = QPainterPath()
        pp.arcMoveTo(QRectF(xc - r, yc - r, 2.0 * r, 2.0 * r), sangle)
        pp.arcTo(QRectF(xc - r, yc - r, 2.0 * r, 2.0 * r), sangle, span)
        cx, cy = circ3(self.centre.x(), self.centre.y(), self.radius, (self.sangle + self.span / 2))
        if is_debug:
            self.addDebug(viewer, path, cx, cy, DrawingLine(self.start, self.end).toLine().angle())
        if False:
            pp.moveTo(*viewer.project(self.minX(), self.centre.y() - self.radius, 0))
            pp.lineTo(*viewer.project(self.minX(), self.centre.y() + self.radius, 0))
            pp.moveTo(*viewer.project(self.maxX(), self.centre.y() - self.radius, 0))
            pp.lineTo(*viewer.project(self.maxX(), self.centre.y() + self.radius, 0))
        pen = viewer.getPen(self, is_virtual, is_debug)
        if pen is not None:
            path.addPath(pp, pen)
        if not is_virtual or is_debug:
            a = self.sangle + self.span / 10
            self.addArrow(viewer, circ3(xc, yc, r, -a), path, self.startAngle, is_virtual, is_debug)
            a = self.sangle + self.span * 9 / 10
            self.addArrow(viewer, circ3(xc, yc, r, -a), path, self.endAngle, is_virtual, is_debug)
    def distanceTo(self, p):
        p = QPointF(*p)
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
    def clone(self):
        da = DrawingArc(self.centre, self.radius, self.sangle, self.span)
        da.weight = self.weight
        return da
    def cut(self, start, end):
        cur = self.length()
        if cur <= 0:
            return self.clone()
        else:
            start = max(start, 0)
            end = min(end, cur)
            da = DrawingArc(self.centre, self.radius, self.sangle + self.span * start / cur, self.span * (end - start) / cur)
            da.weight = self.weight
            return da

class DrawingPolyline(DrawingItem):
    def __init__(self, nodes):
        DrawingItem.__init__(self)
        self.nodes = nodes
        self.startAngle = nodes[0].startAngle
        self.endAngle = nodes[-1].endAngle
        self.start = nodes[0].start
        self.end = nodes[-1].end
        self.bounds = self.calcBounds()
    def addToPath(self, viewer, path, is_virtual, is_debug):
        for i in self.nodes:
            i.addToPath(viewer, path, is_virtual, is_debug)
    def distanceTo(self, p):
        if len(self.nodes) == 0:
            return None
        return min([i.distanceTo(p) for i in self.nodes])
    def setMarked(self, marked):
        self.marked = marked
        for i in self.nodes:
            i.setMarked(marked)
    def setIsTab(self, is_tab):
        self.is_tab = is_tab
        for i in self.nodes:
            i.setIsTab(is_tab)
    def length(self):
        return sum([i.length() for i in self.nodes])
    def cut(self, start, end):
        nodes = []
        total = 0
        for i in self.nodes:
            l = i.length()
            tstart = total
            if tstart > end:
                break
            tend = total + l
            if tend < start:
                total = tend
                continue
            c = i.cut(start - tstart, end - tstart)
            if c is not None:
                nodes.append(c)
            total = tend
        if nodes:
            return DrawingPolyline(nodes)
        else:
            return None
    def calcBounds(self):
        return reduce(QRectF.united, [o.bounds for o in self.nodes])
            
class DrawingCircle(DrawingPolyline):
    def __init__(self, centre, radius):
        DrawingPolyline.__init__(self, [
            DrawingArc(centre, radius, 0, math.pi),
#            DrawingArc(centre, radius, math.pi / 2, math.pi / 2),
            DrawingArc(centre, radius, math.pi, math.pi),
#            DrawingArc(centre, radius, 3 * math.pi / 2, math.pi / 2),
        ])
        self.centre = centre
        self.radius = radius

def findOrientation(nodes):
    angle = 0
    for i in range(len(nodes)):
        if type(nodes[i]) is DrawingArc:
            angle += nodes[i].span
            angle += nangle((nodes[(i + 1) % len(nodes)].startAngle - nodes[i].endAngle))
        else:
            la = (nodes[(i + 1) % len(nodes)].startAngle - nodes[i].startAngle)
            la = nangle(la)
            if abs(la) < math.pi * 0.9999:
                angle += la
    if abs(angle) < 1.99 * math.pi:
        print "Not a closed shape ? %f" % (angle * 180 / math.pi)
        if False:
            for i in range(len(nodes)):
                if type(nodes[i]) is DrawingArc:
                    da = nodes[i].span
                    da += nangle((nodes[(i + 1) % len(nodes)].startAngle - nodes[i].endAngle))
                else:
                    da = (nodes[(i + 1) % len(nodes)].startAngle - nodes[i].startAngle)
                print nodes[i], "%0.3f" % (da * 180 / math.pi)
        if abs(angle) < defaultEps:
            return 0
    if angle < 0:
        return -1
        print "Shape to the right"
    else:
        return +1
        print "Shape to the left"
    return 0

def reversed_nodes(nodes):
    return [i.reversed() for i in reversed(nodes)]

traceOffsetCode = False
removeCrossings = False
checkBoundsInIntersections = False
cacheWindingsValue = False
useStraightLinesForWindings = False
checkBoundsInWindingCheck = False

def intersections(d1, d2):
    if checkBoundsInIntersections and not d1.bounds.intersects(d2.bounds):
        return []
    if type(d1) is DrawingLine and type(d2) is DrawingLine:
        p = QPointF()
        # a > 0 -> the d2 crosses d1 right to left
        a = nangle(d2.startAngle - d1.startAngle)
        if abs(a) < defaultEps:
            if (d1.start == d2.start) and (d1.end == d2.end):
                return []
            if (d1.start == d2.end) and (d1.end == d2.start):
                return []
            pts = []
            if distPointToLine(d1.start, d2.toLine()) < defaultEps:
                pts.append(d1.start)
            if distPointToLine(d1.end, d2.toLine()) < defaultEps:
                pts.append(d1.end)
            if distPointToLine(d2.start, d1.toLine()) < defaultEps:
                pts.append(d2.start)
            if distPointToLine(d2.end, d1.toLine()) < defaultEps:
                pts.append(d2.end)
            pts = list(set(pts))
            a = 0
            return [(p, a) for p in pts]
        if d1.toLine().intersect(d2.toLine(), p) == QLineF.BoundedIntersection:
            return [(p, a)]
        return []
    if type(d1) is DrawingArc and type(d2) is DrawingArc:
        dist = pdist(d1.centre, d2.centre)
        if dist > d1.radius + d2.radius or dist == 0:
            return []
        if dist < defaultEps:
            print "Warning: concentric circles %f %f" % (d1.radius, d2.radius)
        along = (d1.radius ** 2 - d2.radius ** 2 + dist ** 2) / (2.0 * dist)
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
        line2 = QLineF(line.p1(), d2.centre)
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

def eliminateCrossings(nodes):
    def cmpEvent(ev1, ev2):
        res = cmp(ev1[0], ev2[0])
        if res:
            return res
        res = cmp(ev1[3], ev2[3])
        return res
        
    events = []
    splitpoints = {}
    if traceOffsetCode:
        print "Find intersections"
    for n in nodes:
        if type(n) is DrawingLine:
            splitpoints[n] = []
            if n.start.x() == n.end.x():
                x = n.start.x()
                events.append((x, 'S', n, min(n.start.y(), n.end.y())))
                events.append((x, 'E', n, max(n.start.y(), n.end.y())))
            else:
                if n.start.x() < n.end.x():
                    events.append((n.start.x(), 'S', n, n.start.y()))
                    events.append((n.end.x(), 'E', n, n.end.y()))
                else:
                    events.append((n.end.x(), 'S', n, n.end.y()))
                    events.append((n.start.x(), 'E', n, n.end.x()))
        if type(n) is DrawingArc:
            splitpoints[n] = []
            assert(n.minX() <= n.maxX())
            events.append((n.minX(), 'S', n, n.minY()))
            events.append((n.maxX(), 'E', n, n.maxY()))
    events = sorted(events, cmpEvent)
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
                    if p != e[2].start and p != e[2].end:
                        splitpoints[e[2]].append(p)
    nodes2 = []
    splitpoints2 = set([])
    for n in nodes:
        sp = splitpoints[n]
        if sp:
            if type(n) is DrawingLine:
                for i in sp:
                    splitpoints2.add(i)
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
                lastp = n.start
                for i in sp:
                    this = n.angdistp(i) * dir
                    arc = DrawingArc(n.centre, n.radius, n.sangle + last, this - last)
                    arc.start = lastp
                    arc.end = i
                    nodes2.append(arc)
                    splitpoints2.add(arc.start)
                    splitpoints2.add(arc.end)
                    lastp = i
                    last = this
                if last != n.span:
                    arc = DrawingArc(n.centre, n.radius, n.sangle + last, n.span - last)
                    arc.start = lastp
                    nodes2.append(arc)
                    splitpoints2.add(arc.start)
                    splitpoints2.add(arc.end)
        else:
            nodes2.append(n)
    if not nodes2:
        return []
    return nodes2

def removeLoops(nodes2):
    orient = findOrientation(nodes2)
    lastAngle = nodes2[-1].startAngle
    sumAngle = 0
    points = {}
    nodes3 = []
    if traceOffsetCode:
        print "Count windings (%d, %d)" % (len(nodes2), len(splitpoints2))
    windings = None
    ichecks = 0
    inochecks = 0
    last = None
    for n in nodes2:
        if False:
            normal = circ(qpxy(0, 0), 1, tang(n.start, n.end) + math.pi / 2)
            l = DrawingLine(mid, mid + normal)
            nodes3.append(l)
        #normal = circ(qpxy(0, 0), 10000, tang(n.start, n.end) + math.pi / 2)
        if not cacheWindingsValue or windings is None or n.start in splitpoints2 or n.start != last:
            if type(n) is DrawingLine:
                mid = interp(n.start, n.end, 0.5)
            else:
                mid = DrawingArc(n.centre, n.radius, n.sangle, n.span / 2).end
            t = tang(n.start, n.end)
            if useStraightLinesForWindings:
                t += 3 * math.pi / 4
                t -= (t % math.pi / 2)
            else:
                t += math.pi / 2
            normal = circ(qpxy(0, 0), 10000, t)
            l = DrawingLine(mid, mid + normal)
            windings = 0
            for m in nodes2:
                if n is m:
                    continue
                if checkBoundsInWindingCheck and not m.bounds.intersects(l.bounds):
                    inochecks += 1
                    continue
                ichecks += 1
                for p, angle in intersections(l, m):
                    windings += sign(angle)
        last = n.end
        n.windings = windings
        if sign(windings) != orient:
            nodes3.append(n)
        #nodes3.append(n)
    if traceOffsetCode:
        print ichecks, inochecks
    return nodes3

def removeReversals(nodes):
    i = 0
    while i < len(nodes) - 1:
        n1 = nodes[i]
        n2 = nodes[i + 1]
        if type(n1) is DrawingLine and type(n2) is DrawingLine:
            angle = n1.toLine().angleTo(n2.toLine())
            if abs(angle - 180) < defaultEps:
                print "Removing reversal"
                nodes[i] = DrawingLine(n1.start, n2.end)
                del nodes[i + 1]
                i = 0
                continue
        i += 1
    return nodes

def arcsToLines(nodes):
    res = []
    for n in nodes:
        if type(n) is DrawingLine:
            res.append(n)
        else:
            steps = int(1 + n.length() * 2)
            for i in range(steps):
                p1 = n.interp(i * 1.0/ steps)
                p2 = n.interp((i + 1) * 1.0 / steps)
                if i == 0:
                    p1 = n.start
                if i + 1 == steps:
                    p2 = n.end
                res.append(DrawingLine(p1, p2))
    return res
    
def runGluTesselator(nodes):
    from OpenGL import GL
    from OpenGL import GLU

    shapes = []
    vertexes = []
    def begin(shape):
        assert shape == GL.GL_LINE_LOOP
        shapes.append([])
    def vertex(vertex):
        if vertex is None:
            vertex = vertexes.pop()
        shapes[-1].append(vertex)
    def error(args):
        print "error", args
    def combine(coords, vertex_data, weight, theTuple):
        vertexes.append(coords)
        return coords
    #def end(*args, **kwargs):
    #    pass

    tess = GLU.gluNewTess()
    GLU.gluTessCallback(tess, GLU.GLU_TESS_BEGIN, begin)
    GLU.gluTessCallback(tess, GLU.GLU_TESS_VERTEX, vertex)
    GLU.gluTessCallback(tess, GLU.GLU_TESS_COMBINE_DATA, combine)
    GLU.gluTessCallback(tess, GLU.GLU_TESS_ERROR_DATA, error)
    #GLU.gluTessCallback(tess, GLU.GLU_TESS_END_DATA, end)
    GLU.gluTessProperty(tess, GLU.GLU_TESS_WINDING_RULE, GLU.GLU_TESS_WINDING_NEGATIVE)
    #GLU.gluTessProperty(tess, GLU.GLU_TESS_WINDING_RULE, GLU.GLU_TESS_WINDING_NONZERO)
    GLU.gluTessProperty(tess, GLU.GLU_TESS_BOUNDARY_ONLY, GLU.GLU_TRUE)
    GLU.gluTessProperty(tess, GLU.GLU_TESS_TOLERANCE, 1.0 / 2048.0)
    GLU.gluTessNormal(tess, 0.0, 0.0, 1.0)
    GLU.gluBeginPolygon(tess, None)
    def tweaked(p):
        return (int(p.x() * 1024) / 1024.0, int(p.y() * 1024) / 1024.0, 0)
    for n in nodes:
        GLU.gluTessVertex(tess, (tweaked(n.start)), (n.start.x(), n.start.y()))
    GLU.gluEndPolygon(tess)
    res = []
    for s in shapes:
        nodes = []
        for i in range(len(s)):
            p1 = s[i]
            p2 = s[(i + 1) % len(s)]
            nodes.append(DrawingLine(QPointF(p1[0], p1[1]), QPointF(p2[0], p2[1])))
        res.append(DrawingPolyline(nodes))
    return res

def replaceShortArcsWithLines(nodes2):
    nodes3 = []
    for n in nodes2:
        if type(n) is DrawingArc and abs(n.span) < 0.001:
            nodes3.append(DrawingLine(n.start, n.end))
        else:
            nodes3.append(n)
    return nodes3

def plugSmallGaps(nodes):
    last = nodes[-1]
    res = []
    for n in nodes:
        dist = pdist(n.start, last.end)
        if dist > defaultEps:
            print "Warning: points too far away (%f)" % dist
        if dist > 0:
            if type(n) is DrawingLine:
                res.append(DrawingLine(last.end, n.end))
                last = res[-1]
                continue
            elif type(last) is DrawingLine and len(res):
                res[-1] = DrawingLine(last.start, n.start)
            else:
                res.append(DrawingLine(last.end, n.start))
        res.append(n)
        last = n
    return res

class VertexEvent(object):
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.events = []
    def addEdge(self, edge, other, incoming):
        if other[0] > self.x:
            self.events.append(('S', edge, incoming, other))
        elif other[0] < self.x:
            self.events.append(('E', edge, incoming, other))
        else:
            if other[1] < self.y:
                self.events.append(('E', edge, incoming, other))
            elif other[1] > self.y:
                self.events.append(('S', edge, incoming, other))
    def sort(self):
        # This is wrong - should sort by tangent
        #def tangent(pt):
        #    return QLineF(qpxy(self.x, self.y), pt[2]).angle()
        def tangent(pt):
            return QLineF(qpxy(self.x, self.y), pt[2]).angleTo(QLineF(qpxy(0, 0), qpxy(0, 1)))
        def angle(edge, incoming):
            if incoming:
                return -nangle(-edge.endAngle - math.pi)
            else:
                return -nangle(-edge.startAngle)
            #return (edge.endAngle if incoming else edge.startAngle)
        sp = qpxy(self.x, self.y)
        #self.events = sorted(self.events, lambda a, b: cmp(a[0], b[0]) or cmp(tang(sp, qp(a[3])), tang(sp, qp(b[3]))))
        #self.events = sorted(self.events, lambda a, b: -cmp(tang(sp, qp(a[3])), tang(sp, qp(b[3]))))
        def cmpEvent(a, b):
            if cmp(angle(a[1], a[2]), angle(b[1], b[2])) == 0:
                print "undecided: %s - %s - %s" % (self, a[3], b[3])
                return -cmp(angle(a[1], not a[2]), angle(b[1], not b[2]))
            return -cmp(angle(a[1], a[2]), angle(b[1], b[2]))
        self.events = sorted(self.events, cmpEvent)
    def __repr__(self):
        s = "(%0.3f, %0.3f)" % (self.x, self.y)
        return s

class Shape(object):
    def __init__(self, incoming):
        self.incoming = incoming
        self.edges = []
    def addEdge(self, edge):
        self.edges.append(edge)

def removeLoops2old(nodes):
    def treat(x, y):
        m = 1048576.0
        return (int(x * m) / m, int(y * m) / m)
    def treatp(p):
        return treat(p.x(), p.y())
    coords = set([])
    for i, n in enumerate(nodes):
        s = treatp(n.start)
        e = treatp(n.end)
        if s not in coords:
            coords.add(s)
        if e not in coords:
            coords.add(e)
    vertexes = {}
    for c in coords:
        vertexes[c] = VertexEvent(*c)
    for i, n in enumerate(nodes):
        s = treatp(n.start)
        e = treatp(n.end)
        vertexes[s].addEdge(n, e, False)
        vertexes[e].addEdge(n, s, True)
    # XXXKF remove overlapping opposite edges
    for v in vertexes.values():
        v.sort()
    order = sorted(vertexes.keys())
    workset = {}
    shapes = []
    for i, v in enumerate(order):
        ve = vertexes[v]
        print i, ve,
        vstack = []
        for etype, edge, incoming, other in ve.events:
            if etype == 'S':
                if len(vstack) == 0:
                    shape = Shape(incoming)
                    workset[edge] = shape
                else:
                    shape = vstack.pop(0)
                    workset[edge] = shape
                shape.addEdge(edge)
            if etype == 'E':
                vstack.append(workset[edge])
                del workset[edge]
                if len(vstack) == 2:
                    vstack[0].edges += reversed(vstack[1].edges)
                    del vstack[1]
            print "%s%s%s" % (etype, "i" if incoming else "o", other),
        print len(vstack)
        while len(vstack) >= 1:
            shapes.append(vstack[0].edges)
            vstack = vstack[1:]
    assert workset == {}
    shapes = [shapes[4]]
    return [DrawingPolyline(x) for x in shapes]

def dumpVertexes(vertexes, weights, snos):
    for k, v in vertexes.items():
        print v
        for e in v.events:
            print e[0], "EDGE%d" % snos[e[1]], vertexes[e[3]], e[2], weights[e[1]]

def removeLoops2(nodes, windingRule = True):
    def treat(x, y):
        m = 1048576.0
        return (int(x * m + 0.5) / m, int(y * m + 0.5) / m)
        #return (x, y)
    def treatp(p):
        return treat(p.x(), p.y())
    coords = set([])
    weights = collections.defaultdict(lambda: 0)
    pairs = set([])
    for i, n in enumerate(nodes):
        s = treatp(n.start)
        e = treatp(n.end)
        if s not in coords:
            coords.add(s)
        if e not in coords:
            coords.add(e)
    vertexes = {}
    for c in coords:
        vertexes[c] = VertexEvent(*c)
    #print coords
    for i, n in enumerate(nodes):
        s = treatp(n.start)
        e = treatp(n.end)
        weights[(s, e)] += 1
        weights[(e, s)] -= 1
    #print "---"
    for i, n in enumerate(nodes):
        s = treatp(n.start)
        e = treatp(n.end)
        if s != e and weights[(s, e)] > 0:
            assert weights[(e, s)] == -weights[(s, e)]
            weights[n] = weights[(s, e)]
            vertexes[s].addEdge(n, e, False)
            vertexes[e].addEdge(n, s, True)
            del weights[(s, e)]
            del weights[(e, s)]
    sno = 0
    snos = {}
    for edge in nodes:
        snos[edge] = sno
        sno += 1

    for v in vertexes.values():
        v.sort()
        vp = treat(v.x, v.y)
        wc = 0
        for etype, edge, incoming, other in v.events:
            w = weights[edge] * (1 if incoming else -1)
            wc += w
        assert wc == 0
    #return nodes
    windings = {}
    shapes = []
    order = sorted(vertexes.keys())
    first = vertexes[order[0]]
    wc = 0
    vertexq = set([])
    completed = set([])
    if traceOffsetCode:
        dumpVertexes(vertexes, weights, snos)
        print
        print "First %s" % first
    for etype, edge, incoming, other in first.events:
        if incoming:
            wc -= weights[edge]
        #print "%s %s wc=%d" % ("To" if not incoming else "From", other, wc)
        if traceOffsetCode:
            print "  Set EDGE%d to %d" % (snos[edge], wc)
        windings[edge] = wc
        if not incoming:
            wc += weights[edge]
        if not incoming:
            vertexq.add(other)
    assert wc == 0
    completed.add(first)
    while len(vertexq) > 0:
        vpos = list(vertexq).pop()
        v = vertexes[vpos]
        vertexq.remove(vpos)
        if v in completed:
            continue
        if traceOffsetCode:
            print "At %s" % v
        i = 0
        for i, ev in enumerate(v.events):        
            etype, edge, incoming, other = ev
            if edge in windings:
                break
        else:
            assert False
        wc = windings[edge]
        events = v.events[i + 1:] + v.events[:i]
        if not incoming:
            wc += weights[edge]
        #print "Checked:", etype, edge, incoming, other
        for etype, edge, incoming, other in events:
            #print "Checking:", etype, edge, incoming, other
            if incoming:
                wc -= weights[edge]
            #print "Setting to %d" % wc
            if edge not in windings:
                if traceOffsetCode:
                    print "  Set EDGE%d %s to %d" % (snos[edge], vertexes[other], wc)
                windings[edge] = wc
            else:
                if windings[edge] != wc:
                    print "At %s-%s discrepancy %d vs %d" % (v, other, windings[edge], wc)
                assert windings[edge] == wc, "%d vs %d" % (windings[edge], wc)
            if not incoming:
                wc += weights[edge]
            if other not in completed and not incoming:
                vertexq.add(other)
        wc = 0
        for etype, edge, incoming, other in v.events:
            if incoming:
                wc -= weights[edge]
            else:
                wc += weights[edge]
        assert wc == 0
        completed.add(v)
        #break
    #for edge, w in windings.items():
    #    print edge.start, edge.end, w
    #sys.exit(1)
    #return [DrawingPolyline(x) for x in shapes]
    if windingRule:
        nodes = [n for n in nodes if n in windings and windings[n] <= 0 and windings[n] + weights[n] >= 1]
    else:
        nodes = [n for n in nodes if n in windings and weights[n] != 0]
    for i in nodes:
        i.weight = "%s/%s" % (windings[i], windings[i] + weights[i])
    if len(nodes):
        return [DrawingPolyline(nodes)]
    else:
        return []

offsettingMode = 3

def setOffsettingMode(mode):
    global offsettingMode
    offsettingMode = mode

def offset(nodes, r):
    nodes = plugSmallGaps(nodes)
    reverse = findOrientation(nodes) > 0
    orig = list(nodes)
    if reverse:
        nodes = reversed_nodes(nodes)
    #return removeLoops2(eliminateCrossings(nodes))
    nodes2 = []
    s = math.pi / 2
    if r < 0:
        r = -r
        s = -s
    rc = r if s > 0 else -r
    rd = r / abs(r)
    sp = s > 0
    if traceOffsetCode:
        print "Offset parts"
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
                if removeCrossings and len(nodes2) > 0 and type(nodes2[-1]) is DrawingLine:
                    isl = intersections(nodes2[-1], newl)
                    if len(isl) == 1:
                        nodes2[-1].end = isl[0][0]
                        newl.start = isl[0][0]
                nodes2.append(newl)
        elif type(this) is DrawingArc:
            if (this.span < 0) != (s > 0):
                newr = this.radius - r
            else:
                newr = this.radius + r
            if newr > 0:
                arc = DrawingArc(this.centre, newr, this.sangle, this.span)
                arc.orig_start = this.start
                nodes2.append(arc)
            else:
                newl = DrawingLine(start, end)
                newl.orig_start = this.start
                nodes2.append(newl)
    if traceOffsetCode:
        print "Add missing segments"
    nodes = list(nodes2)
    nodes2 = []
    for i in xrange(len(nodes)):
        prev = nodes[(i - 1) % len(nodes)]
        this = nodes[i]
        if pdist(this.start, prev.end) > 0.0001:
            is_concave = nangle(this.startAngle - prev.endAngle) > 0
            if (s < 0) == is_concave:
                arc = DrawingArc.fromtangents(prev.end, this.start, prev.endAngle + math.pi / 2, this.startAngle + math.pi / 2)
                if arc:
                    arc.start = prev.end
                    arc.end = this.start
                    nodes2.append(arc)
                else:
                    nodes2.append(DrawingLine(prev.end, this.start))
            else:
                nodes2.append(DrawingLine(prev.end, this.orig_start))
                nodes2.append(DrawingLine(this.orig_start, this.start))
        nodes2.append(this)
    if traceOffsetCode:
        print "Remove loops"
    #nodes2 = removeReversals(nodes2)

    # Bugs:
    # method 1: bug.dxf, tool=4 mm - corners broken
    # method 2: bug.dxf, tool=7.3..8 mm - breaks due to numerical instability in freeglut, workaround: quantize coordinates
    # method 3: wrench1.dxf, tool=4 mm

    mode = offsettingMode

    nodes2 = replaceShortArcsWithLines(nodes2)
    #nodes2 = removeReversals(nodes2)
    nodes2 = plugSmallGaps(nodes2)
    if mode != 2:
        nodes2 = eliminateCrossings(nodes2)
        nodes2 = plugSmallGaps(nodes2)

    if mode == 1: # old method that checks the windings number by counting lines
        nodes2 = removeLoops(nodes2)
        if len(nodes2) < 2:
            return []
        if reverse:
            return [DrawingPolyline(reversed_nodes(nodes2))]
        else:
            return [DrawingPolyline(nodes2)]
    elif mode == 2: # method from the 2005 paper - approximate arcs and then run through GLU tesselator
        return runGluTesselator(arcsToLines(nodes2))
    elif mode == 0: # leave the loops in (for debugging)
        if reverse:
            return [DrawingPolyline(reversed_nodes(nodes2))]
        else:
            return [DrawingPolyline(nodes2)]
    elif mode == 3:
        res = removeLoops2(removeReversals(nodes2))
        return res
    elif mode == 4:
        res = removeLoops2(removeReversals(nodes2), windingRule = False)
        return res
