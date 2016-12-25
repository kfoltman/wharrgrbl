from tool import *
from helpers.flatitems import *

class ShapeDirection:
    OUTSIDE = 1
    INSIDE = 2
    OUTLINE = 3
    POCKET = 4

defaultTool = CAMTool(diameter = 2.0, feed = 200.0, plunge = 100.0, depth = 0.3)
defaultZStart = 0
defaultZEnd = -2.5
defaultTabHeight = 1
defaultMinTabs = 2
defaultMaxTabs = 4

class CAMOperationShape(object):
    def __init__(self, item, parent):
        self.item = item
        self.parent = parent
    def update(self):
        if self.parent.direction in (ShapeDirection.OUTLINE, ShapeDirection.POCKET):
            self.ntabs = 0
        else:
            self.ntabs = max(self.parent.min_tabs, min(self.parent.max_tabs, int(1 + self.item.length() // self.parent.tab_spacing)))
        self.fullPaths = self.generateFullPaths()
    def generateTabs(self, path):
        l = path.length()
        n = self.ntabs
        if not n:
            return [(0, l, False)]
        slices = []
        for i in range(n):
            slices.append((i * l / n, (i + 1) * l / n - self.parent.tab_width, False))
            slices.append(((i + 1) * l / n - self.parent.tab_width, (i + 1) * l / n, True))
        return slices
    def generateFullPaths(self):
        p = self.parent
        if p.direction == ShapeDirection.OUTLINE:
            return [self.item.nodes]
        elif p.direction == ShapeDirection.POCKET:
            paths = []
            r = -p.tool.diameter / 2.0
            while True:
                newparts = offset(self.item.nodes, r)
                if not newparts:
                    break
                paths.append(newparts)
                r -= 0.75 * 0.5 * p.tool.diameter
            offsets = []
            for p in reversed(paths):
                offsets += p
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
        self.zend = float(defaultZEnd)
        self.tab_height = float(defaultTabHeight)
        self.tab_width = 1.5 * self.tool.diameter
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
        return s

    def generatePreviewPaths(self):
        paths = []
        for s in self.shapes:
            for p in s.fullPaths:
                for start, end, is_tab in s.generateTabs(p):
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
    def next(self):
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
        for i in xrange(self.rowCount() - 1, -1, -1):
            if fn(self.item(i).operation):
                self.removeRow(i)
    def __iter__(self):
        return StandardModelIterator(self, lambda smi: smi.operation)
