from .tool import *
from helpers.flatitems import *

class ShapeDirection:
    OUTSIDE = 1
    INSIDE = 2
    OUTLINE = 3
    POCKET = 4

# defaultTool = CAMTool(diameter = 2.0, feed = 200.0, plunge = 100.0, depth = 0.3)
#defaultTool = CAMTool(diameter = 8, feed = 1200.0, plunge = 600.0, depth = 1.5)
defaultTool = CAMTool(diameter = 8.0, feed = 1200.0, plunge = 600.0, depth = 1.5)
#defaultTool = CAMTool(diameter = 24, feed = 1200.0, plunge = 600.0, depth = 1.5)
#defaultTool = CAMTool(diameter = 3.7, feed = 1200.0, plunge = 600.0, depth = 1.5)
defaultZStart = 0
defaultZEnd = None
defaultTabHeight = 1
defaultMinTabs = 2
defaultMaxTabs = 4
defaultMaterial = CAMMaterial(thickness = 6, clearance = 5)

class CAMOperationShape(object):
    def __init__(self, item, parent):
        self.item = item
        self.parent = parent
    def update(self):
        if self.parent.direction in (ShapeDirection.OUTLINE, ShapeDirection.POCKET) or self.parent.tab_height == 0:
            self.ntabs = 0
        else:
            self.ntabs = max(self.parent.min_tabs, min(self.parent.max_tabs, int(1 + self.item.length() // self.parent.tab_spacing)))
        self.fullPaths = self.generateFullPaths()
    def generateTabs(self, path, tool):
        l = path.length()
        n = self.ntabs
        if not n:
            return [(0, l, False)]
        slices = []
        tw = self.parent.tab_width if self.parent.tab_width is not None else 0.5 * tool.diameter
        tw += tool.diameter
        for i in range(n):
            slices.append((i * l / n, (i + 1) * l / n - tw, False))
            slices.append(((i + 1) * l / n - tw, (i + 1) * l / n, True))
        return slices
    def generateFullPaths(self):
        p = self.parent
        if p.direction == ShapeDirection.OUTLINE:
            if type(self.item) is DrawingPolyline:
                return self.item.nodes
            else:
                return [self.item]
        elif p.direction == ShapeDirection.POCKET:
            safeAreas = offset(self.item.nodes, -p.tool.diameter / 2.0 + defaultEps)
            paths = []
            r = -p.tool.diameter / 2.0
            count = 0
            while True:
                newparts = offset(self.item.nodes, r)
                if not newparts:
                    break
                paths.append(newparts)
                r -= p.tool.stepover * 0.005 * p.tool.diameter
            offsets = []
            lastpt = None
            for path in reversed(paths):
                if lastpt is not None and len(path) == 1:
                    dl = DrawingLine(lastpt, path[0].start)
                    # Avoid adding long slotting cuts
                    if dl.length() < 3 * p.tool.diameter:
                        for sa in safeAreas:
                            for i in sa.nodes:
                                if len(intersections(i, dl)):
                                    dl = None
                                    break
                        if dl is not None:
                            offsets[-1].nodes += [ dl, path[0]]
                            lastpt = path[0].end
                            continue
                offsets += path
                lastpt = path[-1].end
            return offsets
        elif p.direction == ShapeDirection.OUTSIDE:
            r = p.tool.diameter / 2.0
        elif p.direction == ShapeDirection.INSIDE:
            r = -p.tool.diameter / 2.0

        return offset(self.item.nodes, r)


class CAMOperation(object):
    def __init__(self, direction, shapes, tool):
        self.tool = tool
        self.zstart = float(defaultZStart)
        self.zend = None
        self.tab_height = None
        self.tab_width = None
        self.tab_spacing = 200
        self.min_tabs = defaultMinTabs
        self.max_tabs = defaultMaxTabs
        self.direction = direction
        self.shapes = [CAMOperationShape(shape, self) for shape in shapes]
        self.update()
    def update(self):
        for i in self.shapes:
            i.update()
        self.previewPaths = self.generatePreviewPaths()        
    def description(self):
        s = ""
        if self.direction == ShapeDirection.OUTLINE:
            s += "engrave"
        elif self.direction == ShapeDirection.POCKET:
            s += "pocket"
        elif self.direction == ShapeDirection.OUTSIDE:
            s += "profile"
        elif self.direction == ShapeDirection.INSIDE:
            s += "cutout"
        s += ": " + (", ".join([i.item.typeName() for i in self.shapes]))
        if self.zend is not None:
            s += ", depth=%0.2fmm" % (-self.zend)
        return s
    def generatePreviewPaths(self):
        paths = []
        for s in self.shapes:
            for p in s.fullPaths:
                for start, end, is_tab in s.generateTabs(p, self.tool):
                    if not is_tab:
                        c = p.cut(start, end)
                        if c is not None:
                            paths.append(c)
        return paths

class CAMOperationItem(QStandardItem):
    def __init__(self, operation):
        QStandardItemModel.__init__(self, operation.description())
        self.operation = operation

class StandardModelIterator:
    def __init__(self, model, itemFn = None):
        self.model = model
        self.i = 0
        self.itemFn = itemFn
    def __iter__(self):
        return self
    def __next__(self):
        if self.i < self.model.rowCount():
            self.i += 1
            if self.itemFn:
                return self.itemFn(self.model.item(self.i - 1))
            else:
                return self.model.item(self.i - 1)
        else:
            raise StopIteration()

class CAMOperationsModel(QStandardItemModel):
    def __init__(self):
        QStandardItemModel.__init__(self)
    def addOperation(self, op):
        nrows = self.rowCount()
        self.appendRow(CAMOperationItem(op))
        return self.index(nrows, 0)
    def delOperations(self, fn):
        for i in range(self.rowCount() - 1, -1, -1):
            if fn(self.item(i).operation):
                self.removeRow(i)
    def __iter__(self):
        return StandardModelIterator(self, lambda smi: smi.operation)
    def toGcode(self):
        ops = ["G90 G17 G21"]
        lastTool = None
        for o in self:
            if o.tool != lastTool:
                ops += o.tool.begin()
                lastTool = o.tool
            lastz = 5
            last = None
            zend = o.zend or -defaultMaterial.thickness
            for s in o.shapes:
                for p in s.fullPaths:
                    z = o.zstart
                    tabs = s.generateTabs(p, o.tool)
                    while z > zend:
                        z -= o.tool.depth
                        if z < zend:
                            z = zend
                        if o.tab_height is None:
                            ztab = o.zstart
                        else:
                            ztab = min(zend + o.tab_height, o.zstart)
                        if z < ztab:
                            for start, end, is_tab in tabs:
                                opsc, last, lastz = o.tool.followContour([p.cut(start, end)], z if not is_tab else max(z, ztab), last, lastz)
                                ops += opsc
                        else:
                            opsc, last, lastz = o.tool.followContour([p], z, last, lastz)
                            ops += opsc
        if lastTool is not None:
            ops += lastTool.moveTo(qpxy(0, 0), lastTool.clearance, last, lastz)
        return ops
