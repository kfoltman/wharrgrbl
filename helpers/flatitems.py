import math
from helpers.geom import *

class DrawingItem(object):
    def __init__(self):
        self.marked = False
        self.windings = None
    def setMarked(self, marked):
        self.marked = marked
    def addArrow(self, viewer, center, path, angle, is_virtual):
        r = 4
        c = QtCore.QPointF(*center)
        sa = angle
        da = angle + 0.4 + math.pi
        path.addLine(QtCore.QLineF(circ(c, r, -sa), circ(c, r, -da)), viewer.getPen(self, is_virtual))
        da2 = angle - 0.4 + math.pi
        path.addLine(QtCore.QLineF(circ(c, r, -sa), circ(c, r, -da2)), viewer.getPen(self, is_virtual))
        path.addLine(QtCore.QLineF(circ(c, r, -da2), circ(c, r, -da)), viewer.getPen(self, is_virtual))
    def addDebug(self, path, center):
        if self.windings:
            txt = path.addSimpleText("%s" % self.windings)
            txt.setX(center[0])
            txt.setY(center[1])
    def calcBounds(self):
        return expandRect(QtCore.QRectF(qpxy(self.minX(), self.minY()), qpxy(self.maxX(), self.maxY())))

class DrawingLine(DrawingItem):
    def __init__(self, start, end):
        DrawingItem.__init__(self)
        self.start = start
        self.end = end
        self.startAngle = self.endAngle = math.atan2(self.end.y() - self.start.y(), self.end.x() - self.start.x())
        self.bounds = self.calcBounds()
    def addToPath(self, viewer, path, is_virtual):
        start = viewer.project(self.start.x(), self.start.y(), 0)
        end = viewer.project(self.end.x(), self.end.y(), 0)
        center = viewer.project((self.start.x() + self.end.x()) / 2.0, (self.start.y() + self.end.y()) / 2.0, 0)
        self.addDebug(path, center)
        path.addLine(start[0], start[1], end[0], end[1], viewer.getPen(self, is_virtual))
        if not is_virtual:
            self.addArrow(viewer, center, path, self.startAngle, is_virtual)
    def reversed(self):
        return DrawingLine(self.end, self.start)
    def distanceTo(self, p):
        return distPointToLine(QtCore.QPointF(*p), QtCore.QLineF(self.start, self.end))
    def toLine(self):
        return QtCore.QLineF(self.start, self.end)
    def length(self):
        return QtCore.QLineF(self.start, self.end).length()
    def clone(self):
        return DrawingLine(self.start, self.end)
    def cut(self, start, end):
        cur = self.length()
        if cur <= 0:
            return self.clone()
        return DrawingLine(interp(self.start, self.end, max(start, 0) * 1.0 / cur), interp(self.start, self.end, min(end, cur) * 1.0 / cur))
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
    def addToPath(self, viewer, path, is_virtual):
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
        path.addPath(pp, viewer.getPen(self, is_virtual))
        if not is_virtual:
            a = self.sangle
            self.addArrow(viewer, circ3(xc, yc, r, -a), path, self.startAngle, is_virtual)
            a = self.sangle + self.span
            self.addArrow(viewer, circ3(xc, yc, r, -a), path, self.endAngle, is_virtual)
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
    def clone(self):
        return DrawingArc(self.centre, self.radius, self.sangle, self.span)
    def cut(self, start, end):
        cur = self.length()
        if cur <= 0:
            return self.clone()
        else:
            start = max(start, 0)
            end = min(end, cur)
            return DrawingArc(self.centre, self.radius, self.sangle + self.span * start / cur, self.span * (end - start) / cur)

class DrawingPolyline(DrawingItem):
    def __init__(self, nodes):
        DrawingItem.__init__(self)
        self.nodes = nodes
        self.startAngle = nodes[0].startAngle
        self.endAngle = nodes[-1].endAngle
        self.start = nodes[0].start
        self.end = nodes[-1].end
        self.bounds = self.calcBounds()
    def addToPath(self, viewer, path, is_virtual):
        for i in self.nodes:
            i.addToPath(viewer, path, is_virtual)
    def distanceTo(self, p):
        if len(self.nodes) == 0:
            return None
        return min([i.distanceTo(p) for i in self.nodes])
    def setMarked(self, marked):
        self.marked = marked
        for i in self.nodes:
            i.setMarked(marked)
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
        return reduce(QtCore.QRectF.united, [o.bounds for o in self.nodes])
            
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
            angle += la
    if abs(angle) < 1.99 * math.pi:
        print "Not a closed shape ? %f" % (angle * 180 / math.pi)
    if angle < 0:
        return -1
        print "Shape to the right"
    else:
        return +1
        print "Shape to the left"
    return 0

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
                    if p != e[2].start and p != e[2].end:
                        splitpoints[e[2]].append(p)
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
    if not nodes2:
        return []
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
    reverse = findOrientation(nodes) > 0
    if reverse:
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
                arc = DrawingArc.fromtangents(prev.end, this.start, prev.endAngle + math.pi / 2, this.startAngle + math.pi / 2)
                if arc:
                    nodes2.append(arc)
                else:
                    nodes2.append(DrawingLine(prev.end, this.start))
            else:
                nodes2.append(DrawingLine(prev.end, this.orig_start))
                nodes2.append(DrawingLine(this.orig_start, this.start))
        nodes2.append(this)
    nodes2 = removeLoops(nodes2)
    if len(nodes2) < 2:
        return []
    if reverse:
        return [DrawingPolyline(reversed_nodes(nodes2))]
    else:
        return [DrawingPolyline(nodes2)]

