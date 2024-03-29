import math
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from helpers.gparser import *
from .config import Global

class PreviewBase(QtWidgets.QWidget):
    pointerCoords = QtCore.pyqtSignal([float, float])
    clicked = QtCore.pyqtSignal([float, float])
    def __init__(self):
        QtWidgets.QWidget.__init__(self)
        self.actionMode = 0
        self.job = None
        self.motions = None
        self.resetView()
        self.grid = 50
        self.dragging = False
        self.toolDiameter = 1
        self.rapidPath = None
        self.millingPath = None
        self.translation = QtCore.QPointF(0, 0)
        self.minZ = 0
        self.initUI()

    def initUI(self):
        self.setMouseTracking(True)
        self.updateCursor()

    def paintEvent(self, e):
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

        self.renderDrawing(qp)
        qp.end()
        
    def drawLine(self, m):
        qp, pen = self.getPainterPath(m)
        xs, ys = self.project(m.xs, m.ys, m.zs)
        xe, ye = self.project(m.xe, m.ye, m.ze)
        key = "L%f,%f,%f,%f" % (xs, ys, xe, ye)
        if key in self.pastItemHash:
            return
        self.pastItemHash[key] = qp
        qp.addLine(xs, ys, xe, ye, pen)
    def drawArc(self, m):
        qp, pen = self.getPainterPath(m)
        xs, ys = self.project(m.xs, m.ys, m.zs)
        xe, ye = self.project(m.xe, m.ye, m.ze)
        r = ((m.xs - m.xc) ** 2 + (m.ys - m.yc) ** 2) ** 0.5
        sangle = math.atan2(m.ys - m.yc, m.xs - m.xc) * 360 / (2 * math.pi)
        eangle = math.atan2(m.ye - m.yc, m.xe - m.xc) * 360 / (2 * math.pi)
        # XXXKF This is limited to XY arcs
        span = eangle - sangle
        if m.clockwise:
            if span > 0:
                span -= 360
        else:
            if span < 0:
                span += 360
        self.drawArcImpl(m.xc, m.yc, m.zs, m.ze, r, sangle, span, qp, pen)
    def drawArcImpl(self, xc, yc, zs, ze, r, sangle, span, qp, pen):
        xc, yc = self.project(xc, yc, zs)
        r *= self.getScale()
        key = "A%f,%f,%f,%f,%f" % (xc, yc, r, sangle, span)
        if key in self.pastItemHash:
            return
        self.pastItemHash[key] = qp
        arc = QtGui.QPainterPath()
        arc.arcMoveTo(QtCore.QRectF(xc - r, yc - r, 2.0 * r, 2.0 * r), sangle)
        arc.arcTo(QtCore.QRectF(xc - r, yc - r, 2.0 * r, 2.0 * r), sangle, span)
        qp.addPath(arc, pen)
        
    def project(self, x, y, z):
        scale = self.getScale()
        return (x - self.x0) * scale, -(y - self.y0) * scale + self.rect().height()
    def unproject(self, x, y):
        scale = self.getScale()
        return self.x0 + (x / scale), self.y0 + ((self.rect().height() - y) / scale)
    def getScale(self):
        return 10 * (2 ** (self.scaleLevel / 2.0))
    def findScaleLevel(self, scale):
        return math.floor(2 * (math.log(scale / 10.0) / math.log(2.0)))
    def wheelEvent(self, e):
        if e.angleDelta().y() > 0:
            self.adjustScale(+1, e.pos())
            self.createPainters()
            self.repaint()
        if e.angleDelta().y() < 0:
            self.adjustScale(-1, e.pos())
            self.createPainters()
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
        b = e.button()
        if (b == QtCore.Qt.LeftButton and self.actionMode == 0) or b == QtCore.Qt.RightButton:
            self.start_point = e.localPos()
            self.prev_point = e.localPos()
            self.start_origin = (self.x0, self.y0)
            self.dragging = True
        elif b == QtCore.Qt.LeftButton:
            self.clicked.emit(self.x0 + e.localPos().x() / self.getScale(), self.y0 + (self.rect().height() - e.localPos().y()) / self.getScale())
        
    def mouseReleaseEvent(self, e):
        if self.dragging:
            self.createPainters()
            self.repaint()
        self.dragging = False

    def physToLog(self, pt):
        return self.x0 + pt.x() / self.getScale(), self.y0 + (self.rect().height() - pt.y()) / self.getScale()
        
    def mouseMoveEvent(self, e):
        if self.dragging:
            self.x0 = self.start_origin[0] - (e.localPos().x() - self.start_point.x()) / self.getScale()
            self.y0 = self.start_origin[1] + (e.localPos().y() - self.start_point.y()) / self.getScale()
            self.translation -= e.localPos() - self.prev_point
            self.prev_point = e.localPos()
            self.repaint()
        self.pointerCoords.emit(*self.physToLog(e.pos()))
        
    def loadFromFile(self, fileName):
        if os.stat(fileName).st_size >= 1048576:
            # File too large, no preview available
            self.setFromList([])
        else:
            self.setFromList([l.strip() for l in open(fileName, "r").readlines()])
    
    def setFromList(self, cmds):
        rec = TestGcodeReceiver()
        gs = GcodeState(rec)
        for cmd in cmds:
            gs.handle_line(cmd)
        self.motions = rec.motions
        if rec.bbox_min is not None:
            self.minZ = rec.bbox_min[2]
            self.zoomToBbox(rec.bbox_min, rec.bbox_max)
        else:
            self.minZ = 0
        self.createPainters()
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
    
    def updateCursor(self):
        if self.actionMode == 0:
            self.setCursor(QtCore.Qt.OpenHandCursor)
        elif self.actionMode == 1:
            self.setCursor(QtCore.Qt.CrossCursor)

    def setActionMode(self, mode):
        self.actionMode = mode
        self.updateCursor()

    def setToolDiameter(self, newDia):
        self.toolDiameter = newDia
        self.createPainters()
        self.repaint()
        
    def sizeHint(self):
        return QtCore.QSize(400, 100)
    def resizeEvent(self, e):
        self.createPainters()
        
    def initPainters(self):
        self.pastItemHash = {}
        self.translation = QtCore.QPointF(0, 0)

class JobPreview(PreviewBase):
    def __init__(self):
        PreviewBase.__init__(self)
        self.spindlePos = None
    def createPainters(self):
        self.initPainters()
        self.millingPen = QtGui.QPen(QtGui.QColor(0, 0, 0), self.toolDiameter * self.getScale())
        self.millingPen.setCapStyle(QtCore.Qt.RoundCap)
        self.millingPen.setJoinStyle(QtCore.Qt.RoundJoin)
        self.rapidPen = QtGui.QPen(QtGui.QColor(128, 128, 128), 1)
        self.cursorPen = QtGui.QPen(QtGui.QColor(0, 0, 192), 0)

        self.rapidPath = QtWidgets.QGraphicsScene()
        self.millingPath = QtWidgets.QGraphicsScene()

        if self.motions is not None:
            for m in self.motions:
                if type(m) is GcodeLine:
                    self.drawLine(m)
                elif type(m) is GcodeArc:
                    self.drawArc(m)

    def getPainterPath(self, m):
        if m.zs > 0 and m.ze > 0:
            return self.rapidPath, self.rapidPen
        else:
            return self.millingPath, self.millingPen

    def renderDrawing(self, qp):
        trect = QtCore.QRectF(self.rect()).translated(self.translation)
        if self.rapidPath is not None:
            self.rapidPath.render(qp, QtCore.QRectF(self.rect()), trect)
        if self.millingPath is not None:
            self.millingPath.render(qp, QtCore.QRectF(self.rect()), trect)
        if self.spindlePos is not None:
            x, y = self.project(*self.spindlePos)
            qp.setPen(self.cursorPen)
            qp.drawLine(x - 5, y - 5, x + 4, y + 4)
            qp.drawLine(x - 5, y + 5, x + 4, y - 4)

class JobPreviewWindow(QtWidgets.QDialog):
    def __init__(self):
        QtWidgets.QDialog.__init__(self)
        self.grbl = None
        self.initUI()
    def initUI(self):
        def boldLabel(text):
            l = QtWidgets.QLabel(text)
            l.setFont(Global.fonts.mediumBoldFont)
            return l
        def insetLabel():
            l = QtWidgets.QLabel()
            l.setFont(Global.fonts.mediumFont)
            l.setMinimumWidth(80)
            l.setFrameStyle(QtWidgets.QFrame.Panel | QtWidgets.QFrame.Sunken)
            l.setAlignment(QtCore.Qt.AlignRight)
            return l
        self.actionButtons = {}
        self.setWindowTitle("Job preview")

        self.preview = JobPreview()

        self.layout = QtWidgets.QVBoxLayout()
        self.legendLayout = QtWidgets.QHBoxLayout()
        self.xLabel = insetLabel()
        self.yLabel = insetLabel()
        self.zLabel = insetLabel()
        self.toolDiaEdit = QtWidgets.QLineEdit()
        self.legendLayout.addWidget(boldLabel("X"), 0)
        self.legendLayout.addWidget(self.xLabel, 0)
        self.legendLayout.addWidget(boldLabel("Y"), 0)
        self.legendLayout.addWidget(self.yLabel, 0)
        self.legendLayout.addWidget(boldLabel("Min Z"), 0)
        self.legendLayout.addWidget(self.zLabel, 0)
        self.legendLayout.addWidget(QtWidgets.QLabel("Tool diameter"), 0)
        self.legendLayout.addWidget(self.toolDiaEdit, 0)
        self.legendLayout.addStretch(1)
        self.legendLayout.addWidget(self.createActionButton("&Pan", 0), 0)
        self.legendLayout.addWidget(self.createActionButton("&Rapid to", 1), 0)
        self.preview.pointerCoords.connect(self.onCoordsUpdated)
        self.preview.clicked.connect(self.onPreviewClicked)
        self.preview.setMinimumSize(800, 600)
        self.layout.addWidget(self.preview)
        self.layout.addLayout(self.legendLayout)
        self.setLayout(self.layout)
        self.toolDiaEdit.setText("%0.2f" % self.preview.toolDiameter)
        self.toolDiaEdit.textEdited.connect(self.onTextEdited)
    def createActionButton(self, text, mode):
        b = QtWidgets.QRadioButton(text)
        b.setChecked(mode == self.preview.actionMode)
        b.clicked.connect(lambda: self.preview.setActionMode(mode))
        self.actionButtons[mode] = b
        return b
    def setGrbl(self, grbl):
        self.grbl = grbl
    def setJob(self, job):
        self.preview.setJob(job)
        if job:
            self.zLabel.setText("%0.3f" % self.preview.minZ)
        else:
            self.zLabel.setText("")
    def onCoordsUpdated(self, x, y):
        self.xLabel.setText("%0.3f" % x)
        self.yLabel.setText("%0.3f" % y)
    def onPreviewClicked(self, x, y):
        if self.preview.actionMode == 1:
            self.grbl.jogTo("G90 X%0.3f Y%0.3f" % (x, y))
            #self.grbl.sendLine("G90 G0 X%0.3f Y%0.3f" %  (x, y))
    def onSpindleMoved(self, x, y, z):
        self.preview.spindlePos = (x, y, z)
        self.preview.repaint()
    def onTextEdited(self, newText):
        try:
            newDia = float(newText)
            if newDia >= 0.01 and newDia < 100:
                self.preview.setToolDiameter(newDia)
        except ValueError as e:
            pass
