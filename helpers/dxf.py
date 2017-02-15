from helpers.flatitems import *
import dxfgrabber
import dxfgrabber.dxfentities

def bulgeToArcParams(p1, p2, bulge):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    theta = 4 * math.atan(bulge)
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
    pc = QPointF(xm, ym)
    return pc, r, sangle, span

def dxfToObjects(drawing):
    objects = []
    entities = dxfgrabber.dxfentities
    for i in drawing.entities.get_entities():
        it = type(i)
        if it is entities.Circle:
            objects.append(DrawingCircle(QPointF(i.center[0], i.center[1]), i.radius))
        elif it is entities.Arc:
            if i.endangle > i.startangle:
                objects.append(DrawingArc(QPointF(i.center[0], i.center[1]), i.radius, i.endangle * math.pi / 180.0, (i.startangle - i.endangle) * math.pi / 180.0))
            else:
                objects.append(DrawingArc(QPointF(i.center[0], i.center[1]), i.radius, i.startangle * math.pi / 180.0, twopi + (i.endangle - i.startangle) * math.pi / 180.0))
        elif it is entities.Line:
            objects.append(DrawingLine(QPointF(i.start[0], i.start[1]), QPointF(i.end[0], i.end[1])))
        elif it is entities.LWPolyline:
            nodes = []
            points = []
            for p in range(len(i.points)):
                points.append(i.points[p])
            if i.is_closed:
                points.append(points[0])
            for p in range(len(points) - 1):
                if i.bulge[p]:
                    p1 = i.points[p]
                    p2 = i.points[(p + 1) % len(i.points)]
                    pc, r, sangle, span = bulgeToArcParams(p1, p2, i.bulge[p])
                    nodes.append(DrawingArc(pc, r, sangle, span))
                    #self.drawArcImpl(xm, ym, 0, 0, r, sangle, theta * 360 / (2 * math.pi), self.drawingPath, self.drawingPen)
                else:
                    if points[p] != points[p + 1]:
                        nodes.append(DrawingLine(QPointF(*points[p]), QPointF(*points[p + 1])))
                    #if p == 0:
                    #    polyline.moveTo(points[p][0], points[p][1])
                    #polyline.lineTo(points[p + 1][0], points[p + 1][1])
            polyline = DrawingPolyline(nodes)
            objects.append(polyline)
        else:
            print "Unknown DXF type:", str(it)
    return objects
    
