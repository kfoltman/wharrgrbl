from helpers.flatitems import *
from helpers.gui import *

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

class CAMMaterial(Serialisable):
    properties = [
        FloatEditableProperty("Thickness", "thickness", "%0.2f", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f", min = 0),
    ]
    def __init__(self, thickness, clearance):
        self.thickness = thickness
        self.clearance = clearance

class CAMTool(Serialisable):
    properties = [
        FloatEditableProperty("Diameter", "diameter", "%0.2f mm", min = 0),
        FloatEditableProperty("Depth of cut", "depth", "%0.2f mm", min = 0),
        FloatEditableProperty("Length", "length", "%0.2f mm", min = 0, allow_none = True, none_value = "Unknown"),
        FloatEditableProperty("Feed rate", "feed", "%0.1f mm/min", min = 0),
        FloatEditableProperty("Plunge rate", "plunge", "%0.1f mm/min", min = 0),
        FloatEditableProperty("Stepover", "stepover", "%0.1f %%", min = 0),
        FloatEditableProperty("Clearance height", "clearance", "%0.1f mm", min = 0, allow_none = True, none_value = "Material default"),
        FloatEditableProperty("Ramp depth", "ramp_depth", "%0.2f mm", min = 0),
    ]
    def __init__(self, diameter, feed, plunge, depth):
        self.diameter = float(diameter)
        self.feed = float(feed)
        self.plunge = float(plunge)
        self.depth = float(depth)
        self.length = None
        self.clearance = 5
        self.stepover = 77
        self.ramp_depth = 0.1
    def begin(self):
        return []
    def addOp(self, op, startz, endz, last, lastz):
        if type(op) is DrawingLine:
            ops = self.moveTo(op.start, startz, last, lastz)
            if op.start != op.end:
                ops += self.lineTo(op.end, endz)
            return ops, op.end
        elif type(op) is DrawingArc:
            ops = self.moveTo(op.start, startz, last, lastz)
            ops += self.arc(op.start, op.end, op.centre, op.span < 0, endz)
            return ops, op.end
        else:
            raise ValueError, "Unexpected type %s" % type(op)
    def addRamp(self, nodes, z, last, lastz, depth):
        ops = []
        while lastz > z:
            destz = max(z, lastz - depth)
            pl = DrawingPolyline(nodes).cut(0, self.diameter)

            initz = lastz
            tlength = pl.length()
            sofar = 0
            # ramp into layer
            for i in pl.flatten():
                startz = initz + (destz - initz) * sofar / tlength
                sofar += i.length()
                endz = initz + (destz - initz) * sofar / tlength
                dops, last = self.addOp(i, startz, endz, last, lastz)
                lastz = endz
                ops += dops
            # clean up the ramp by doing a flat pass in reverse
            dops, last, lastz = self.followContourNoRamp(pl.reversed().flatten(), destz, last, lastz)
            ops += dops
        return ops, last, lastz
    def followContour(self, nodes, z, last, lastz, topz):
        ops = []
        # this should be calculated based on ramp angle instead
        depth = self.ramp_depth
        topz = max(topz, z)
        if lastz > topz:
            ops += self.plungeTo(topz, lastz)
            lastz = topz
        if z < lastz and depth > 0:
            dops, last, lastz = self.addRamp(nodes, z, last, lastz, depth)
            ops += dops
        dops, last, lastz = self.followContourNoRamp(nodes, z, last, lastz)
        ops += dops
        return ops, last, lastz
    def followContourNoRamp(self, nodes, z, last, lastz):
        ops = []
        nodes2 = []
        for i in nodes:
            dops, last = self.addOp(i, z, z, last, lastz)
            ops += dops
            lastz = z
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
