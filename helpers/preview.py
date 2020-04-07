import math
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from cam.mill import BoardSizer, PathGenerator

class PathPreview(QtWidgets.QWidget):
    
    def __init__(self, view, milling_params):
        super(PathPreview, self).__init__()
        self.pathgen = PathGenerator(view, milling_params)
        self.view = view

        self.initUI()
        self.recalcAndRepaint()
        self.start_point = None
        self.dragging = False
        self.highlight_net = None
        self.rubberband_rect = None
        
    def initUI(self):
        self.setMinimumSize(1024, 768)
        self.setMouseTracking(True)
    
    def mousePressEvent(self, e):
        self.highlight_net = None
        self.start_point = e.localPos()
        self.dragging = False
        self.rubberband_rect = None
        self.repaint()
        
    def mouseReleaseEvent(self, e):
        pt = e.localPos()
        if not self.dragging:
            self.highlight_net = None
            for net, path in self.paths.items():
                if path.contains(pt):
                    self.highlight_net = net
                    print "Highlight %s" % net
            self.repaint()
        
    def mouseMoveEvent(self, e):
        if not self.dragging and self.start_point:
            dist = e.localPos() - self.start_point
            if dist.manhattanLength() < 5:
                self.dragging = True
        if self.dragging:
            self.rubberband_rect = QtCore.QRectF(self.start_point, e.localPos())
            self.repaint()
            #print self.rubberbandRect

    def wheelEvent(self, e):
        if e.delta() > 0:
            self.view.scale *= 1.25
            self.recalcAndRepaint()
        if e.delta() < 0:
            self.view.scale /= 1.25
            self.recalcAndRepaint()

    def recalcAndRepaint(self):
        if self.view.board is not None:
            self.paths, self.drills = self.pathgen.generatePathsForLayer(self.view.cur_layer, addCleanup = True)
        else:
            self.paths, self.drills = {}, []
        self.repaint()
        
    def paintEvent(self, e):
        qp = QtGui.QPainter()
        qp.begin(self)
        qp.setRenderHint(1, True)
        qp.setRenderHint(8, True)
        #pen = QtGui.QPen(QtGui.QColor(200, 200, 200))
        pen = QtGui.QPen(QtGui.QColor(150, 150, 110))
        pen.setJoinStyle(0x40)
        pen.setWidth(self.view.scale * self.pathgen.milling_params.tool_width)

        if self.view.realistic_mode:
            pen2 = QtGui.QPen(QtGui.QColor(150, 150, 110))
        else:
            pen2 = QtGui.QPen(QtGui.QColor(230, 230, 110))
        pen2.setJoinStyle(0x40)
        pen2.setWidth(self.view.scale * self.pathgen.milling_params.tool_width)
        
        copper = QtGui.QColor(220, 160, 130)
        qp.setPen(pen)
        #pen.setCosmetic(True)
        #qp.setBrush(QtGui.QColor(150, 150, 110))
        
        if self.view.realistic_mode:
            qp.setBrush(copper)
        else:
            qp.setBrush(QtGui.QBrush(QtGui.QColor(240, 0, 120), 4))
        qp.drawRect(*self.pathgen.getArea())
        
        if self.view.realistic_mode:
            brush = QtGui.QBrush(copper)
        else:
            brush = QtGui.QBrush(QtGui.QColor(100, 0, 0))
        qp.setBrush(brush)
        highlight_brush = QtGui.QBrush(QtGui.QColor(255, 255, 192))
        #qp.setBrush(QtGui.QColor(150, 150, 110))
        #qp.setBrush(QtGui.QColor(255, 0, 0))
        for net, path in self.paths.items():
            if net == self.highlight_net:
                qp.setPen(pen)
                qp.setBrush(highlight_brush)
            elif net == 'cleanup':
                qp.setBrush(0)
                qp.setPen(pen2)
            else:
                qp.setPen(pen)
                if self.view.rainbow_mode:
                    qp.setBrush(self.view.board.net2color(net))
                else:
                    qp.setBrush(brush)
            qp.drawPath(path)
        pen = QtGui.QPen(QtGui.QColor(192, 192, 192))
        pen.setStyle(0)
        for x, y, diameterx, diametery, net in self.drills:
            qp.setPen(pen)
            if net == self.highlight_net:
                qp.setBrush(QtGui.QColor(255, 0, 0))
            else:
                qp.setBrush(QtGui.QColor(255, 255, 255))
            path = QtGui.QPainterPath()
            if diameterx <= diametery:
                self.pathgen.addTrackToPath(path, self.pathgen.mapPoint(x, y - (diametery - diameterx) / 2), self.pathgen.mapPoint(x, y + (diametery - diameterx) / 2), diameterx)
            else:
                self.pathgen.addTrackToPath(path, self.pathgen.mapPoint(x - (diameterx - diametery) / 2, y), self.pathgen.mapPoint(x + (diameterx - diametery) / 2, y), diametery)
            qp.drawPath(path)
        if self.rubberband_rect:
            qp.setOpacity(0.5)
            qp.drawRect(self.rubberband_rect)
            qp.setOpacity(1.0)
        qp.end()

    def sizeBoard(self):
        self.pathgen.sizeBoard()
