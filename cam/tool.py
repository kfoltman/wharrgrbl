from helpers.flatitems import *

def fmtfloat(f):
    fmt = '%g' % f
    if 'e' in fmt:
        return '%0.5f' % f
    return fmt

def gencode(**kwargs):
    s = ''
    for k in sorted(kwargs.keys(), key = lambda k: (k.upper() != 'G', k)):
        v = kwargs[k]
        if v is None:
            continue
        if len(s):
            s += ' '
        if hasattr(v, '__iter__'):
            for item in v:
                s += k.upper() + fmtfloat(item)
        else:
            s += k.upper() + fmtfloat(v)
    return s

class CAMMaterial(object):
    def __init__(self, thickness, clearance):
        self.thickness = thickness
        self.clearance = clearance

class CAMTool(object):
    def __init__(self, diameter, feed, plunge, depth):
        self.diameter = float(diameter)
        self.feed = float(feed)
        self.plunge = float(plunge)
        self.depth = float(depth)
        self.length = None
        self.clearance = 5
        self.stepover = 77
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
            return [gencode(G = 1, F = self.plunge, Z = z)]
        elif z > lastz:
            return [gencode(G = 0, Z = z)]
        else:
            return []
    def moveTo(self, pt, z, last, lastz):
        if pt == last and last is not None:
            return self.plungeTo(z, lastz)
        return [gencode(G = 0, Z = self.clearance), gencode(G = [0], X = pt.x(), Y = pt.y())] + self.plungeTo(z, self.clearance)
    def lineTo(self, pt, z):
        return [gencode(G = 1, F = self.feed, X = pt.x(), Y = pt.y(), Z = z)]
    def arc(self, last, pt, centre, clockwise, z):
        return [gencode(G = 2 if clockwise else 3, F = self.feed, X = pt.x(), Y = pt.y(), I = centre.x() - last.x(), J = centre.y() - last.y(), Z = z)]
