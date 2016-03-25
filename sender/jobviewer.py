import math
import time
from PyQt4 import QtCore, QtGui
from helpers.gparser import *

class JobPreview(QtGui.QWidget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.job = None
        self.motions = None
        self.resetView()
        self.grid = 50
        self.dragging = False
        self.toolDiameter = 1
        self.initUI()
    def initUI(self):
        self.setMouseTracking(True)
    def paintEvent(self, e):
        self.millingPen = QtGui.QPen(QtGui.QColor(0, 0, 0), self.toolDiameter * self.getScale())
        self.millingPen.setCapStyle(QtCore.Qt.RoundCap)
        self.millingPen.setJoinStyle(QtCore.Qt.RoundJoin)

        qp = QtGui.QPainter()
        qp.begin(self)
        qp.setRenderHint(1, True)
        qp.setRenderHint(8, True)
        qp.setBrush(QtGui.QBrush(QtGui.QColor(192, 192, 192), 1))
        qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 0))
        qp.drawRect(self.rect())

        qp.setPen(QtGui.QPen(QtGui.QColor(208, 208, 208), 1))        
        gx = self.x0 - self.x0 % self.grid
        gy = self.y0 - self.y0 % self.grid
        while True:
            mx, my = self.project(0, gy, 0)
            if my < 0:
                break
            qp.drawLine(0, my, self.size().width(), my)
            gy += self.grid
        while True:
            mx, my = self.project(gx, 0, 0)
            if mx > self.size().width():
                break
            qp.drawLine(mx, 0, mx, self.size().height())
            gx += self.grid

        qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 1))        

        mx, my = self.project(0, 0, 0)
        qp.drawLine(0, my, self.size().width(), my)
        qp.drawLine(mx, 0, mx, self.size().height())

        if self.motions is not None:
            for m in self.motions:
                if type(m) is GcodeLine:
                    self.drawLine(qp, m)
                elif type(m) is GcodeArc:
                    self.drawArc(qp, m)
        qp.end()
    def preparePainter(self, qp, m):
        if m.zs > 0 and m.ze > 0:
            qp.setPen(QtGui.QPen(QtGui.QColor(128, 128, 128), 1))
        else:
            qp.setPen(self.millingPen)
    def drawLine(self, qp, m):        
        self.preparePainter(qp, m)
        xs, ys = self.project(m.xs, m.ys, m.zs)
        xe, ye = self.project(m.xe, m.ye, m.ze)
        qp.drawLine(xs, ys, xe, ye)
    def drawArc(self, qp, m):
        self.preparePainter(qp, m)
        xs, ys = self.project(m.xs, m.ys, m.zs)
        xe, ye = self.project(m.xe, m.ye, m.ze)
        r = ((m.xs - m.xc) ** 2 + (m.ys - m.yc) ** 2) ** 0.5
        sangle = math.atan2(m.ys - m.yc, m.xs - m.xc) * 5760 / (2 * math.pi)
        eangle = math.atan2(m.ye - m.yc, m.xe - m.xc) * 5760 / (2 * math.pi)
        # XXXKF This is limited to XY arcs
        xc, yc = self.project(m.xc, m.yc, m.zs)
        r *= self.getScale()
        span = eangle - sangle
        if m.clockwise:
            if span > 0:
                span -= 5760
        else:
            if span < 0:
                span += 5760
        qp.drawArc(QtCore.QRectF(xc - r, yc - r, 2 * r - 1, 2 * r - 1), sangle, span)
        
    def project(self, x, y, z):
        scale = self.getScale()
        return (x - self.x0) * scale, -(y - self.y0) * scale + self.rect().height()
    def getScale(self):
        return 10 * (2 ** (self.scaleLevel / 2.0))
    def findScaleLevel(self, scale):
        return math.floor(2 * (math.log(scale / 10.0) / math.log(2.0)))
    def wheelEvent(self, e):
        if e.delta() > 0:
            self.adjustScale(+1, e.pos())
            self.repaint()
        if e.delta() < 0:
            self.adjustScale(-1, e.pos())
            self.repaint()
    def adjustScale(self, rel, pt):
        h = self.rect().height()
        scale = self.getScale()
        xm = self.x0 + pt.x() / scale
        ym = self.y0 + (h - pt.y()) / scale
        self.scaleLevel += rel
        scale = self.getScale()
        self.x0 = xm - pt.x() / scale
        self.y0 = ym - (h - pt.y()) / scale

    def mousePressEvent(self, e):
        self.start_point = e.posF()
        self.start_origin = (self.x0, self.y0)
        self.dragging = True
        
    def mouseReleaseEvent(self, e):
        self.dragging = False
        
    def mouseMoveEvent(self, e):
        if self.dragging:
            self.x0 = self.start_origin[0] - (e.posF().x() - self.start_point.x()) / self.getScale()
            self.y0 = self.start_origin[1] + (e.posF().y() - self.start_point.y()) / self.getScale()
            self.repaint()
        
    def loadFromFile(self, fileName):
        self.setFromList([l.strip() for l in open(fileName, "r").readlines()])
    
    def setFromList(self, cmds):
        rec = TestGcodeReceiver()
        gs = GcodeState(rec)
        for cmd in cmds:
            gs.handle_line(cmd)
        self.motions = rec.motions
        self.zoomToBbox(rec.bbox_min, rec.bbox_max)
        self.repaint()
    
    def setJob(self, job):
        self.job = job
        if job:
            self.setFromList([cmd.command for cmd in self.job.commands])
        else:
            self.motions = None

    def resetView(self):
        self.x0 = -10
        self.y0 = -10
        self.scaleLevel = -3

    def zoomToBbox(self, pmin, pmax):
        # slight margin of one tool radius
        if pmin is None:
            self.resetView()
            return
        self.x0, self.y0 = pmin[0] - self.toolDiameter, pmin[1] - self.toolDiameter
        wx, wy = pmax[0] - pmin[0] + self.toolDiameter * 2.0, pmax[1] - pmin[1] + self.toolDiameter * 2.0
        size = self.size()
        self.scaleLevel = self.findScaleLevel(min(size.width() / wx, size.height() / wy))
        
    def sizeHint(self):
        return QtCore.QSize(400, 100)

class JobPreviewWindow(QtGui.QDialog):
    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.initUI()
    def initUI(self):
        self.layout = QtGui.QVBoxLayout()
        self.preview = JobPreview()
        self.preview.setMinimumSize(800, 600)
        self.layout.addWidget(self.preview)
        self.setLayout(self.layout)
    def setJob(self, job):
        self.preview.setJob(job)
