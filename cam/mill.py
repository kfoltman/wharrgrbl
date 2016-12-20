import math
import sys
from gcode import GcodeOutput
from PyQt4 import QtCore, QtGui

def addvec(v1, v2):
    return (v1[0] + v2[0], v1[1] + v2[1])

class MillingParams(object):
    def __init__(self):
        self.tool_width = 0.3
        self.doubleIsolation = False

class ViewParams(object):
    def __init__(self, ymirror = False):
        self.scale = 96/25.4
        self.cur_layer = "B.Cu"
        self.rainbow_mode = False
        self.realistic_mode = True
        self.board = None
        self.ymirror = ymirror
    def is_mirrored(self):
        return self.cur_layer == "B.Cu"
    def is_ymirrored(self):
        return self.ymirror

class BoardSizer(object):
    def __init__(self, board):
        self.board = board
        self.sizeBoard()
        
    def sizeBoard(self):
        self.minpt = None
        self.maxpt = None
        if self.board is not None:
            for l in self.board.layers.values():
                for seg in l.segments:
                    self.addPointToBB(seg.start)
                    self.addPointToBB(seg.end)
                for seg in l.gr_lines:
                    self.addPointToBB(seg.start)
                    self.addPointToBB(seg.end)
                for net, polygons in l.polygons.items():
                    for p in polygons:
                        for pt in p:
                            self.addPointToBB(pt)
        if self.minpt is None:
            self.minpt = (0, 0)
            self.maxpt = (0, 0)

    def addPointToBB(self, curPt):
        if self.minpt is None:
            self.minpt = curPt
            self.maxpt = curPt
        else:
            self.minpt = (min(self.minpt[0], curPt[0]), min(self.minpt[1], curPt[1]))
            self.maxpt = (max(self.maxpt[0], curPt[0]), max(self.maxpt[1], curPt[1]))

class PathGenerator(object):
    def __init__(self, view, milling_params):
        super(PathGenerator, self).__init__()
        self.view = view
        self.milling_params = milling_params
        self.sizeBoard()
    
    def sizeBoard(self):
        self.sizer = BoardSizer(self.view.board)

    def mapPoint(self, x, y):
        if self.view.is_mirrored():
            x = self.sizer.maxpt[0] - x
        else:
            x = x - self.sizer.minpt[0]
        if self.view.is_ymirrored():
            y = self.sizer.maxpt[1] - y
        else:
            y = y - self.sizer.minpt[1]
        return (x * self.view.scale, y * self.view.scale)
        
    def getArea(self):
        xs, ys = self.mapPoint(*self.sizer.minpt)
        xe, ye = self.mapPoint(*self.sizer.maxpt)
        if self.view.is_mirrored():
            xs, xe = xe, xs
        if self.view.is_ymirrored():
            ys, ye = ye, ys
        return xs, ys, xe, ye
        
    def generatePathsForLayer(self, layer, addCleanup = False):
        paths = {}
        drills = []
        if self.view.board is None:
            return
        layer = self.view.board.layers[layer]
        for seg in layer.segments:
            
            path = QtGui.QPainterPath()
            lastPt = self.mapPoint(*seg.start)
            curPt = self.mapPoint(*seg.end)
            self.addTrackToPath(path, lastPt, curPt, seg.width + self.milling_params.tool_width)
            #qp.drawPath(path)
            #path.setFillRule(1)
            if seg.net in paths:
                path = paths[seg.net].united(path)
            paths[seg.net] = path
        for pad in layer.pads:
            path = QtGui.QPainterPath()
            path.setFillRule(1)
            w = (pad.w + self.milling_params.tool_width) / 2.0
            h = (pad.h + self.milling_params.tool_width) / 2.0
            sx, sy = self.mapPoint(pad.x - w, pad.y - h)
            ex, ey = self.mapPoint(pad.x + w, pad.y + h)
            if pad.pad_type != 'np_thru_hole':
                if pad.shape == 'rect':
                    path.addRect(min(sx, ex), min(sy, ey), abs(ex - sx), abs(ey - sy))
                elif pad.shape == 'oval':
                    r = min(abs(ex - sx) / 2.0, abs(ey - sy) / 2.0)
                    path.addRoundedRect(min(sx, ex), min(sy, ey), abs(ex - sx), abs(ey - sy), r, r)
                elif pad.shape == 'circle':
                    wh = min(abs(ex - sx), abs(ey - sy))
                    path.addEllipse(min(sx, ex), min(sy, ey), wh - 1, wh - 1)
            if pad.pad_type in ('thru_hole', 'np_thru_hole') and pad.drillx > 0 and pad.drilly > 0:
                drills.append((pad.x, pad.y, pad.drillx, pad.drilly, pad.net))
            if pad.net in paths:
                path = paths[pad.net].united(path)
            paths[pad.net] = path
        #pen.setWidth(0)
        #qp.setPen(pen)
        #qp.setBrush(QtGui.QColor(200, 0, 0))
        for net, polygons in layer.polygons.items():
            for p in polygons:
                path = QtGui.QPainterPath()
                path.setFillRule(1)
                path.moveTo(*self.mapPoint(*p[0]))
                for pt in p[1:]:
                    path.lineTo(*self.mapPoint(*pt))
                path.lineTo(*self.mapPoint(*p[0]))
                path.closeSubpath()
                
                path3 = QtGui.QPainterPathStroker()
                path3.setWidth(self.view.scale * self.milling_params.tool_width)
                path3 = path3.createStroke(path).simplified()

                path = path.united(path3)
                if net in paths:
                    path = paths[net].united(path)
                paths[net] = path
        if self.milling_params.doubleIsolation:
            allpath = QtGui.QPainterPath()
            stroker = QtGui.QPainterPathStroker()
            stroker.setWidth(self.view.scale * self.milling_params.tool_width)
            allpathlist = []
            for p in paths.values():
                ps = p.united(stroker.createStroke(p))
                allpathlist.append(ps)
            while len(allpathlist) > 1:
                p1 = allpathlist[0]
                p2 = allpathlist[1]
                allpathlist = allpathlist[2:] + [p1.united(p2)]
            allpath = allpathlist[0]
            
            #allpath2.subtracted(allpath)
            allpath3 = QtGui.QPainterPath()
            allpath3.addRect(*self.getArea())
            allpath4 = allpath3.subtracted(allpath)
            paths['cleanup'] = allpath4

        return paths, drills
        
    def addTrackToPath(self, path, lastPt, curPt, width):
        w = self.view.scale * width / 2
        angle = math.atan2(curPt[1] - lastPt[1], curPt[0] - lastPt[0])
        angledeg = 180 * angle / math.pi
        dx, dy = (w * math.cos(angle), w * math.sin(angle))
        nvec = (-dy, dx)
        mnvec = (dy, -dx)
        
        path.moveTo(*addvec(lastPt, nvec))
        path.lineTo(*addvec(curPt, nvec))
        v = addvec(curPt, (-w, -w))
        path.arcTo(v[0], v[1], 2 * w, 2 * w, -angledeg-90, 180)
        path.lineTo(*addvec(lastPt, mnvec))
        v = addvec(lastPt, (-w, -w))
        path.arcTo(v[0], v[1], 2 * w, 2 * w, -angledeg+90, 180)
        
def optimize_paths(paths):
    # Minimize the rapids (using some crappy greedy optimisation algorithm)
    newpaths = paths[0:1]
    paths = paths[1:]
    while len(paths) > 0:
        lastpt = newpaths[-1][-1]
        pt = paths[0][0]
        mindist2 = (pt[0] - lastpt[0])**2 + (pt[1] - lastpt[1])**2
        minp = 0
        minpt = 0
        for p in xrange(len(paths)):
            for ptidx in xrange(0, len(paths[p])):
                pt = paths[p][ptidx]
                dist2 = (pt[0] - lastpt[0])**2 + (pt[1] - lastpt[1])**2
                if dist2 < mindist2:
                    mindist2 = dist2
                    minpt = ptidx
                    minp = p
        p = paths[minp]
        if minpt > 0:
            newpaths.append(p[minpt:] + p[:minpt])
        else:
            newpaths.append(p)
        paths[minp:minp + 1] = []
    return newpaths

def _convpt(pt, view, sizer):
    if view.is_ymirrored():
        y = sizer.maxpt[1] - pt[1]
    else:
        y = pt[1] - sizer.minpt[1]
    if view.is_mirrored():
        x = sizer.maxpt[0] - pt[0]
    else:
        x = pt[0] - sizer.minpt[0]
    return (x, y)

class EngravingOperation:
    zsafe = 0.8
    zend = 30
    zsurface = 0
    zstep = 0.1
    zdepth = -0.1
    # orig: 500
    feed = 800
    # orig: 500
    plunge = 400

class EdgeCuttingOperation:
    endmill_dia = 0.8
    zsafe = 0.8
    zend = 30
    zsurface = 0
    zstep = 0.4
    zdepth = -1.6
    feed = 500
    plunge = 500

class PeckDrillingOperation:
    endmill_dia = 0.8
    zsurface = 0
    zdepth = -1.7
    zsafe = 0.8
    zstep = 0.6
    zend = 30
    feed = 400
    plunge = 60
    peck = 3

def peck_drill(gc, x, y, operation):
    gc.move_to(x, y)
    gc.move_z(operation.zsurface)
    for p in range(operation.peck):
        gc.move_z(operation.zsurface + ((p + 1) * (operation.zdepth - operation.zsurface) / operation.peck))
        gc.move_z(operation.zsurface)
    gc.get_safe()

def profile_mill(gc, xs, ys, xe, ye, reqdia, operation):
    endmill_dia = operation.endmill_dia
    dist = ((ye - ys) ** 2 + (xe - xs) ** 2) ** 0.5
    if reqdia < endmill_dia + 0.05 and dist < 0.05:
        peck_drill(gc, xs, ys, operation)
        return
    angle = 0
    if dist > 0.001:
        angle = math.atan2(ye - ys, xe - xs) + math.pi / 2.0
    zdepth = operation.zsurface
    while zdepth > operation.zdepth:
        zdepth = max(zdepth - operation.zstep, operation.zdepth)
        gc.set_depth(zdepth)

        if reqdia < 2 * endmill_dia:
            radius = (reqdia - endmill_dia) / 2
        else:
            radius = endmill_dia / 2

        first = True
        last = False
        while True:
            dx = radius * math.cos(angle)
            dy = radius * math.sin(angle)
            if first:
                gc.move_to(xs + dx, ys + dy)
                first = False
            else:
                gc.line_to(xs + dx, ys + dy)
            gc.arc_cw_to(x = xs - dx, y = ys - dy, i = -dx, j = -dy, feed = operation.feed)
            gc.line_to(xe - dx, ye - dy)
            gc.arc_cw_to(x = xe + dx, y = ye + dy, i = dx, j = dy, feed = operation.feed)
            gc.line_to(xs + dx, ys + dy)
            if last:
                break
            radius += endmill_dia
            if 2 * radius + endmill_dia > reqdia + 0.01:
                last = True
                # was last radius close enough?
                if abs(radius - endmill_dia - (reqdia - endmill_dia) / 2.0) < 0.1:
                    break
                radius = (reqdia - endmill_dia) / 2.0
    gc.get_safe()

def cmpguess(g1, g2, tol = 0.02, stol = 0.1):
    if g1 is None or g2 is None:
        return False
    c1, r1, s1 = g1
    c2, r2, s2 = g2
    d = QtCore.QLineF(c1, c2)
    if d.length() > tol:
        return False
    dr = abs(r1 - r2)
    if dr > tol:
        return False
    if max(s1, s2) > max(stol, 2 * math.pi * max(r1, r2) / 5):
        return False
    return True

def calign(pt, cx, cy, r):
    x, y = pt
    angle = math.atan2(y - cy, x - cx)
    return (cx + r * math.cos(angle), cy + r * math.sin(angle))

def path_to_optimized_gcode(gc, points):
    guesses = []
    for i in xrange(len(points)):
        if i + 2 >= len(points):
            guesses.append(None)
            continue
        p1 = QtCore.QPointF(*points[i])
        p2 = QtCore.QPointF(*points[i + 1])
        p3 = QtCore.QPointF(*points[i + 2])
        l1 = QtCore.QLineF(p1, p2)
        l2 = QtCore.QLineF(p2, p3)
        n1 = l1.normalVector().translated(l1.dx() / 2, l1.dy() / 2)
        n2 = l2.normalVector().translated(l2.dx() / 2, l2.dy() / 2)
        centre = QtCore.QPointF(0, 0)
        if n1.intersect(n2, centre) > 0:
            r = QtCore.QLineF(p1, centre).length()
            step = max(l1.length(), l2.length())
            if r > 0.1:
                guesses.append((centre, r, step))
            else:
                guesses.append(None)
        else:
            guesses.append(None)
    gc.move_to(points[0][0], points[0][1])
    i = 1
    while i < len(points):
        p = points[i]
        if i + 1 < len(points) and cmpguess(guesses[i - 1], guesses[i]):
            j = i
            while j < len(points) and cmpguess(guesses[i - 1], guesses[j + 1]):
                j += 1
            # (i - 1, i, i + 1) =~ ... =~ (j, j + 1, j + 2)
            cx = sum([guesses[k][0].x() for k in range(i - 1, j)]) / (j - i + 1)
            cy = sum([guesses[k][0].y() for k in range(i - 1, j)]) / (j - i + 1)
            r = sum([guesses[k][1] for k in range(i - 1, j)]) / (j - i + 1)
            start = calign(points[i - 1], cx, cy, r)
            end = calign(points[j + 2], cx, cy, r)
            gc.arc_cw_to(x = end[0], y = end[1], i = cx - start[0], j = cy - start[1])
            #print "G2 X%0.4f Y%0.4f I%0.4f J%0.4f" % (end[0], end[1], cx - start[0], cy - start[1])
            #print "Arc to: %s centre: %s" % (points[j], (cx, cy))
            i = j + 3
        else:
            gc.line_to(points[i][0], points[i][1])
            i += 1
    gc.line_to(points[0][0], points[0][1])

def mill_contours(gc, board, layer, milling_params):
    operation = gc.operation
    view = ViewParams(ymirror = True)
    view.board = board
    view.scale = 10.0
    gcodefile = "paths.nc"
    pp = PathGenerator(view, milling_params)
    paths, drills = pp.generatePathsForLayer(layer)
    pathlist = []
    for net, path in paths.items():
        for poly in path.simplified().toSubpathPolygons():
            pts = []
            for pt in poly:
                pts.append((pt.x() / view.scale, pt.y() / view.scale))
            pathlist.append(pts)
    pathlist = optimize_paths(pathlist)
    
    gc.feed = operation.feed
    gc.plunge = operation.plunge
    depth = 0
    while depth > operation.zdepth:
        depth -= abs(operation.zstep)
        if depth < operation.zdepth:
            depth = operation.zdepth
        gc.zdepth = depth
        gc.get_safe()
        for p in pathlist:
            path_to_optimized_gcode(gc, p)

def drill_holes_and_slots(gc, board, layer, milling_params):
    operation = gc.operation
    view = ViewParams(ymirror = True)
    view.board = board
    view.scale = 10.0
    view.cur_layer = layer
    pp = PathGenerator(view, milling_params)
    paths, drills = pp.generatePathsForLayer(layer)
    all_holes = list(drills)
    sorted_holes = []
    sizer = pp.sizer
    def convpt(pt):
        return _convpt(pt, view, sizer)

    lastpt = (0, 0)
    while len(all_holes) > 0:
        pt = None
        min_dist = None
        min_line = None
        for h in range(len(all_holes)):
            pt = convpt(all_holes[h][0:2])
            dist = (pt[0] - lastpt[0])**2 + (pt[1] - lastpt[1])**2
            if min_dist is None or dist < min_dist:
                min_hole = h
                min_dist = dist
        
        sorted_holes.append(all_holes[min_hole])
        lastpt = convpt(all_holes[min_hole][0:2])
        all_holes = all_holes[:min_hole] + all_holes[min_hole + 1:]
        
    for x, y, drillx, drilly, net in sorted_holes:
        drillx += 0.05
        drilly += 0.05
        x, y = convpt((x, y))
        if drillx < drilly:
            profile_mill(gc, x, y - (drilly - drillx) / 2.0, x, y + (drilly - drillx) / 2.0, drillx, operation)
        else:
            profile_mill(gc, x - (drillx - drilly) / 2.0, y, x + (drillx - drilly) / 2.0, y, drilly, operation)
    gc.get_safe()

def cut_edges(gc, board, layer, milling_params):
    view = ViewParams(ymirror = True)
    view.board = board
    view.scale = 10.0
    view.cur_layer = layer
    sizer = BoardSizer(board)
    def convpt(pt):
        return _convpt(pt, view, sizer)

    operation = gc.operation
    cuts = board.layers[layer]
    all_lines = list(cuts.gr_lines)
    lastpt = (0, 0)
    
    sorted_lines = []
    while len(all_lines) > 0:
        pt = all_lines[0].start[0]
        min_dist = None
        min_line = None
        for line in range(len(all_lines)):
            for ptt in ('start', 'end'):
                pt = convpt(getattr(all_lines[line], ptt))
                dist = (pt[0] - lastpt[0])**2 + (pt[1] - lastpt[1])**2
                if min_dist is None or dist < min_dist:
                    min_line = (line, ptt)
                    min_dist = dist
        ml = all_lines[min_line[0]]
        if min_line[1] == 'start':
            lastpt = convpt((ml.end[0], ml.end[1]))
            sorted_lines.append((convpt((ml.start[0], ml.start[1])), lastpt))
        else:
            lastpt = convpt((ml.start[0], ml.start[1]))
            sorted_lines.append((convpt((ml.end[0], ml.end[1])), lastpt))
        all_lines = all_lines[:min_line[0]] + all_lines[min_line[0] + 1:]
    depth = operation.zsurface
    while depth > operation.zdepth:
        depth = max(operation.zdepth, depth - abs(operation.zstep))
        gc.set_depth(depth)
        last = None
        for start, end in sorted_lines:
            if last is None or (((start[0] - last[0])**2 + (start[1] - last[1])**2)**0.5) > 0.01:
                gc.move_to(*start)
            gc.line_to(*end)
            last = end
        
    gc.get_safe()
