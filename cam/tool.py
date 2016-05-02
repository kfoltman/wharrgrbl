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

