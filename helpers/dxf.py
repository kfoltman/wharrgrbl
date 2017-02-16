from helpers.flatitems import *
import dxfgrabber
import dxfgrabber.dxfentities

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
                    nodes.append(bulgeToArc(p1, p2, i.bulge[p]))
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
    
