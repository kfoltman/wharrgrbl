import math
from PyQt4 import QtCore, QtGui
from helpers.gparser import *

class JobPreview(QtGui.QWidget):
    def __init__(self):
        QtGui.QWidget.__init__(self)
        self.job = None
        self.motions = None
        self.scaleLevel = 1
        self.x0 = 0
        self.y0 = 0
        self.dragging = False
        self.initUI()
    def initUI(self):
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        qp.setRenderHint(1, True)
        qp.setRenderHint(8, True)
        qp.setBrush(QtGui.QBrush(QtGui.QColor(192, 192, 192), 1))
        qp.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 0))        
        qp.drawRect(self.rect())
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
            qp.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 1))
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
        sangle = -math.atan2(m.ys - m.yc, m.xs - m.xc) * 5760 / (2 * math.pi)
        eangle = -math.atan2(m.ye - m.yc, m.xe - m.xc) * 5760 / (2 * math.pi)
        # XXXKF This is limited to XY arcs
        xc, yc = self.project(m.xc, m.yc, m.zs)
        r *= self.getScale()
        span = eangle - sangle
        if not m.clockwise:
            if span > 0:
                span -= 5760
        else:
            if span < 0:
                span += 5760
        qp.drawArc(xc - r, yc - r, 2 * r, 2 * r, sangle, span)
        
    def project(self, x, y, z):
        scale = self.getScale()
        return (x - self.x0) * scale, (y - self.y0) * scale
    def getScale(self):
        return 10 * (2 ** (self.scaleLevel / 2.0))
    def wheelEvent(self, e):
        if e.delta() > 0:
            self.adjustScale(+1, e.pos())
            self.repaint()
        if e.delta() < 0:
            self.adjustScale(-1, e.pos())
            self.repaint()
    def adjustScale(self, rel, pt):
        scale = self.getScale()
        xm = self.x0 + pt.x() / scale
        ym = self.y0 + pt.y() / scale
        self.scaleLevel += rel
        scale = self.getScale()
        self.x0 = xm - pt.x() / scale
        self.y0 = ym - pt.y() / scale

    def mousePressEvent(self, e):
        self.start_point = e.posF()
        self.start_origin = (self.x0, self.y0)
        self.dragging = True
        
    def mouseReleaseEvent(self, e):
        self.dragging = False
        
    def mouseMoveEvent(self, e):
        if self.dragging:
            self.x0 = self.start_origin[0] - (e.posF().x() - self.start_point.x()) / self.getScale()
            self.y0 = self.start_origin[1] - (e.posF().y() - self.start_point.y()) / self.getScale()
            self.repaint()
        
    def setJob(self, job):
        self.job = job
        if job:
            rec = TestGcodeReceiver()
            gs = GcodeState(rec)
            for cmd in self.job.commands:
                gs.handle_line(cmd.command)
            self.motions = rec.motions
        else:
            self.motions = None
        self.repaint()

class JobPreviewWindow(QtGui.QDialog):
    def __init__(self):
        QtGui.QDialog.__init__(self)
        self.initUI()
    def initUI(self):
        self.layout = QtGui.QVBoxLayout()
        self.preview = JobPreview()
        self.layout.addWidget(self.preview)
        self.setLayout(self.layout)
    def setJob(self, job):
        self.preview.setJob(job)