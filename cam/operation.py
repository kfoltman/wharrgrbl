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
defaultNumTabs = 4

class CAMOperation(object):
    def __init__(self, direction, parent, tool):
        self.zstart = float(defaultZStart)
        self.zend = float(defaultZEnd)
        self.tab_height = float(defaultTabHeight)
        self.direction = direction
        self.parent = parent
        self.tool = tool
        self.ntabs = 0 if direction == ShapeDirection.OUTLINE or direction == ShapeDirection.POCKET else 4
        self.tab_width = 1.5 * self.tool.diameter
        self.fullPaths = self.generateFullPaths()
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
        s += ": " + type(self.parent).__name__.replace("Drawing", "")
        return s
    def generateFullPaths(self):
        if self.direction == ShapeDirection.OUTLINE:
            return [self.parent]
        elif self.direction == ShapeDirection.POCKET:
            paths = []
            r = -self.tool.diameter / 2.0
            while True:
                newparts = offset(self.parent.nodes, r)
                if not newparts:
                    break
                paths.append(newparts)
                r -= 0.75 * 0.5 * self.tool.diameter
            offsets = []
            for p in reversed(paths):
                offsets += p
            return offsets
        elif self.direction == ShapeDirection.OUTSIDE:
            r = self.tool.diameter / 2.0
        elif self.direction == ShapeDirection.INSIDE:
            r = -self.tool.diameter / 2.0

        return offset(self.parent.nodes, r)

    def generateTabs(self, path):
        l = path.length()
        n = self.ntabs
        if not n:
            return [(0, l, False)]
        slices = []
        for i in range(n):
            slices.append((i * l / n, (i + 1) * l / n - self.tab_width, False))
            slices.append(((i + 1) * l / n - self.tab_width, (i + 1) * l / n, True))
        return slices

    def generatePreviewPaths(self):
        paths = []
        for p in self.fullPaths:
            for start, end, is_tab in self.generateTabs(p):
                if not is_tab:
                    c = p.cut(start, end)
                    if c is not None:
                        paths.append(c)
        return paths

