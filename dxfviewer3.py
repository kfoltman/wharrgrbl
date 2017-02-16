import json
import math
import re
import sys
import time
import os.path
from cam.tool import *
from cam.operation import *
from cam.tooledit import *
from cam.matedit import *

import dxfgrabber

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from sender.jobviewer import *
from helpers.dxf import dxfToObjects
from helpers.gui import *
from helpers.geom import *
from helpers.flatitems import *

debugToolPaths = False

class DXFViewer(PreviewBase):
    selected = pyqtSignal([])
    mouseMoved = pyqtSignal([])
    def __init__(self):
        PreviewBase.__init__(self)
        self.operations = CAMOperationsModel()
        self.setDrawing([])
    def setDrawing(self, objects = []):
        self.operations.clear()
        self.selection = None
        self.opSelection = []
        self.curOperation = None
        self.lastMousePos = None
        self.updateCursor()
        self.objects = objects
    def getPen(self, item, is_virtual, is_debug):
        if is_virtual:
            color = QColor(160, 160, 160)
            if getattr(item, 'is_tab', False) != self.is_tab:
                return None
            if self.is_tab:
                color = QColor(180, 180, 180)
            if self.curOperation in self.opSelection:
                color = QColor(255, 0, 0)
                if self.is_tab:
                    color = QColor(255, 128, 128)
            if not is_debug:
                pen = QPen(color, self.curOperation.tool.diameter * self.getScale())
            else:
                pen = QPen(QColor(0, 255, 255), 1)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            return pen
        if item.marked:
            return self.activeItemPen
        return self.drawingPen
    def createPainters(self):
        self.initPainters()
        self.drawingPath = QGraphicsScene()
        self.previewPen = QPen(QColor(160, 160, 160), 0)
        self.drawingPen = QPen(QColor(0, 0, 0), 0)
        self.drawingPen2 = QPen(QColor(255, 0, 0), 0)
        self.activeItemPen = QPen(QColor(0, 255, 0), 0)
        #self.drawingPen.setCapStyle(Qt.RoundCap)
        #self.drawingPen.setJoinStyle(Qt.RoundJoin)
        for i in xrange(self.operations.rowCount()):
            op = self.operations.item(i).operation
            self.curOperation = op
            self.is_tab = True
            for n in op.previewPaths:
                for i in n:
                    i.addToPath(self, self.drawingPath, True, False)
            self.is_tab = False
            for n in op.previewPaths:
                for i in n:
                    i.addToPath(self, self.drawingPath, True, False)
        if debugToolPaths:
            for i in xrange(self.operations.rowCount()):
                op = self.operations.item(i).operation
                self.curOperation = op
                for n in op.previewPaths:
                    for i in n:
                        i.addToPath(self, self.drawingPath, True, True)
        self.curOperation = None
        for o in self.objects:
            o.addToPath(self, self.drawingPath, False, False)
    def renderDrawing(self, qp):
        trect = QRectF(self.rect()).translated(self.translation)
        if self.drawingPath is not None:
            self.drawingPath.render(qp, QRectF(self.rect()), trect)
    def updateCursor(self):
        self.setCursor(Qt.CrossCursor)
    def getItemAtPoint(self, p):
        matches = sorted([(i, i.distanceTo(p)) for i in self.objects], lambda o1, o2: cmp(o1[1], o2[1]))
        mind = matches[0][1] if len(matches) > 0 else None
        second = matches[1][1] if len(matches) > 1 else None
        if second is not None and abs(second - mind) < 1 / self.getScale():
            print "Warning: Multiple items at similar distance"
        if mind < 10 / self.getScale():
            return matches[0][0]
    def updateSelection(self):
        self.createPainters()
        self.repaint()
        self.selected.emit()
    def getSelected(self):
        return [i for i in self.objects if i.marked]
    def setOpSelection(self, selection):
        self.opSelection = selection
        self.updateSelection()
    def mousePressEvent(self, e):
        b = e.button()
        if b == Qt.LeftButton:
            p = e.posF()
            lp = self.physToLog(p)
            item = self.getItemAtPoint(lp)
            if item:
                item.setMarked(not item.marked)
                self.updateSelection()
            else:
                if self.selection is None:
                    self.selection = MyRubberBand(QRubberBand.Rectangle, self)
                self.selectionOrigin = e.pos()
                self.selection.setGeometry(QRect(e.pos(), QSize()))
                self.selection.show()
        elif b == Qt.RightButton:
            self.start_point = e.posF()
            self.prev_point = e.posF()
            self.start_origin = (self.x0, self.y0)
            self.dragging = True
    def mouseMoveEvent(self, e):
        if self.selection and self.selection.isVisible():
            self.selection.setGeometry(QRect(self.selectionOrigin, e.pos()).normalized())
        PreviewBase.mouseMoveEvent(self, e)
        self.lastMousePos = self.physToLog(e.posF())
        self.mouseMoved.emit()
    def mouseReleaseEvent(self, e):
        if self.selection and self.selection.isVisible():
            ps = self.unproject(self.selectionOrigin.x(), self.selectionOrigin.y())
            pe = self.unproject(e.pos().x(), e.pos().y())
            box = QRectF(qp(ps), qp(pe)).normalized()
            
            self.selectByBox(box)
            self.selection.hide()
            self.selection = None
        PreviewBase.mouseReleaseEvent(self, e)
    def selectByBox(self, box):
        for o in self.objects:
            if box.contains(o.bounds):
                o.setMarked(True)
        self.updateSelection()
    def loadDrawing(self, js):
        objs = []
        ops = []
        refmap = {}
        for k, v in js['objects'].items():
            data = jsonToDrawingObject(v)
            refmap[k] = data
            objs.append(data)
        # Only one tool for now
        for k, v in js['tools'].items():
            refmap[k] = defaultTool
            defaultTool.unserialise(v)
        defaultMaterial.unserialise(js['material'])
        self.setDrawing(objs)
        for i in js['operations']:
            op = CAMOperation(None, [], None)
            op.unserialise(i, refmap)
            op.update()
            self.operations.appendRow(CAMOperationItem(op))
        self.updateSelection()
    def serialise(self):
        refmap = RefMap()
        objs = {}
        ops = []
        tools = {}
        cnt = 0
        for i in self.objects:
            objs[refmap.refn(i)] = i.serialise()
        for i in self.operations:
            ops.append(i.serialise(refmap))
        tools[refmap.refn(defaultTool)] = defaultTool.serialise(refmap)
        return { 'objects' : objs, 'operations' : ops, 'tools' : tools,
            'material' : defaultMaterial.serialise(refmap) }
    
class DXFApplication(QApplication):
    pass

class OperationTreeWidget(QDockWidget):
    def __init__(self, viewer):
        QDockWidget.__init__(self, "Operations")
        self.viewer = viewer
        self.initUI()
    def initUI(self):
        self.w = QWidget()
        self.w.setLayout(QVBoxLayout())
        self.w.layout().setSpacing(0)
        self.setWidget(self.w)
        self.list = QListView()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setModel(self.viewer.operations)
        self.list.selectionModel().selectionChanged.connect(self.onSelectionChanged)
        self.toolbar = QWidget()
        self.deleteButton = QPushButton("Delete")
        self.deleteButton.clicked.connect(self.onOperationDelete)
        self.toolbar.setLayout(QHBoxLayout())
        self.toolbar.layout().addWidget(self.deleteButton)
        self.w.layout().addWidget(self.list)
        self.w.layout().addWidget(self.toolbar)
        self.onSelectionChanged(None, None)
    def sort(self):
        self.list.model().sort(0)
    def getSelected(self):
        sm = self.list.selectionModel()
        ops = []
        for i in sm.selectedRows():
            ops.append(self.viewer.operations.item(i.row()).operation)
        return ops
    def onOperationDelete(self):
        ops = self.getSelected()
        self.viewer.operations.delOperations(lambda o: o in ops)
        self.viewer.updateSelection()
    def onSelectionChanged(self, selected, deselected):
        items = self.getSelected()
        self.deleteButton.setEnabled(len(items) > 0)
        self.viewer.setOpSelection(items)
    def select(self, item):
        self.list.selectionModel().select(QModelIndex(item), QItemSelectionModel.ClearAndSelect)

class ObjectPropertiesWidget(QDockWidget):
    properties = [
        FloatEditableProperty("End depth", "zend", "%0.3f", allow_none = True, none_value = "Full depth"),
        FloatEditableProperty("Start depth", "zstart", "%0.3f"),
        FloatEditableProperty("Tab height", "tab_height", "%0.3f", allow_none = True, none_value = "Full height"),
        FloatEditableProperty("Tab width", "tab_width", "%0.3f", allow_none = True, none_value = "1/2 tool diameter"),
        FloatEditableProperty("Tab spacing", "tab_spacing", "%0.3f"),
        IntEditableProperty('Min tabs', "min_tabs", min = 0, max = 10),
        IntEditableProperty('Max tabs', "max_tabs", min = 0, max = 10),
        IntEditableProperty('Priority', "priority", min = 0, max = 100, allow_none = True, none_value = "Default"),
    ]
    def __init__(self, viewer, tree):
        QDockWidget.__init__(self, "Properties")
        self.viewer = viewer
        self.operationTree = tree
        self.updating = False
        self.initUI()
    def initUI(self):
        self.table = PropertySheetWidget(self.properties)
        self.table.propertyChanged.connect(self.onPropertyChanged)
        self.setWidget(self.table)
    def onPropertyChanged(self, attribute, changed):
        for o in changed:
            o.update()
        if attribute == "priority":
            self.operationTree.sort()
        self.viewer.updateSelection()
    def setOperations(self, operations):
        self.table.setObjects(operations)

class DXFMainWindow(QMainWindow, MenuHelper):
    def __init__(self):
        QMainWindow.__init__(self)
        MenuHelper.__init__(self)
        self.directory = None
        menuBar = self.menuBar()
        self.documentFile = None
        fileMenu = menuBar.addMenu("&File")
        fileMenu.addAction(self.makeAction("&Open", "Ctrl+O", "Open a drawing or a project", self.onFileOpen))
        fileMenu.addSeparator()
        fileMenu.addAction(self.makeAction("&Save a project", "Ctrl+S", "Save a project", self.onFileSave))
        fileMenu.addAction(self.makeAction("&Generate", "Ctrl+E", "Generate toolpaths and write them to a file", self.onOperationGenerate))
        fileMenu.addSeparator()
        fileMenu.addAction(self.makeAction("E&xit", "Ctrl+Q", "Exit the application", self.close))
        toolpathMenu = menuBar.addMenu("&Toolpaths")
        toolpathMenu.addAction(self.makeAction("&Profile", "", "Cut on the outside of a shape", self.onOperationProfile))
        toolpathMenu.addAction(self.makeAction("&Cutout", "", "Cut on the inside of a shape", self.onOperationCutout))
        toolpathMenu.addAction(self.makeAction("P&ocket", "", "Cut the entire inside of a shape", self.onOperationPocket))
        toolpathMenu.addAction(self.makeAction("&Engrave", "", "Cut along the shape", self.onOperationEngrave))
        optionsMenu = menuBar.addMenu("&Options")
        optionsMenu.addAction(self.makeAction("&Tool", "Ctrl+T", "Tool settings (only one tool supported for now)", self.onOperationTool))
        optionsMenu.addAction(self.makeAction("&Material", "Ctrl+M", "Material settings", self.onOperationMaterial))
        optionsMenu.addAction(self.makeAction("&Debug", "Ctrl+G", "Debug mode on/off", self.onOperationDebug))
        self.updateActions()
        
        self.toolbar = QToolBar("Operations")
        self.toolbar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.toolbar.addAction("Profile").triggered.connect(self.onOperationProfile)
        self.toolbar.addAction("Cutout").triggered.connect(self.onOperationCutout)
        self.toolbar.addAction("Pocket").triggered.connect(self.onOperationPocket)
        self.toolbar.addAction("Engrave").triggered.connect(self.onOperationEngrave)
        self.toolbar.addAction("Generate").triggered.connect(self.onOperationGenerate)
        self.toolbar.addAction("Unselect").triggered.connect(self.onOperationUnselect)
        self.toolbar.addAction("Tool").triggered.connect(self.onOperationTool)
        self.toolbar.addAction("Material").triggered.connect(self.onOperationMaterial)
        self.toolbar.addAction("Debug").triggered.connect(self.onOperationDebug)
        self.addToolBar(self.toolbar)
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)
        self.viewer = DXFViewer()
        self.operationTree = OperationTreeWidget(self.viewer)
        self.objectProperties = ObjectPropertiesWidget(self.viewer, self.operationTree)
        self.addDockWidget(Qt.RightDockWidgetArea, self.operationTree)
        self.addDockWidget(Qt.RightDockWidgetArea, self.objectProperties)
        self.setCentralWidget(self.viewer)
        self.setMinimumSize(1024, 600)
        self.operationTree.list.selectionModel().selectionChanged.connect(self.onOperationsSelected)
        self.onOperationsSelected()
        
        self.viewer.mouseMoved.connect(self.updateStatus)
    def updateStatus(self):
        self.statusBar().showMessage("(%0.3f, %0.3f)" % (self.viewer.lastMousePos))
    def onFileSave(self):
        opendlg = QtGui.QFileDialog(self, 'Save a project', '.', "CAM project files (*.camp)")
        opendlg.setFileMode(0)
        opendlg.setAcceptMode(QtGui.QFileDialog.AcceptSave)
        if self.documentFile is not None:
            opendlg.selectFile(self.documentFile)
        if opendlg.exec_():
            self.directory = opendlg.directory().absolutePath()
            fnames = opendlg.selectedFiles()
            if len(fnames) == 1:
                self.saveFile(str(fnames[0]))
    def saveFile(self, fname):
        f = open(fname, "w")
        f.write(json.dumps(self.viewer.serialise(), indent = 4))
        f.close()
    def onFileOpen(self):
        opendlg = QtGui.QFileDialog(self, 'Open a file', '.', "DXF files (*.dxf);;CAM project files (*.camp)")
        opendlg.setFileMode(QtGui.QFileDialog.ExistingFile)
        if self.documentFile is not None:
            opendlg.selectFile(self.documentFile)
        if self.directory is not None:
            opendlg.setDirectory(self.directory)
        if opendlg.exec_():
            self.directory = opendlg.directory().absolutePath()
            fnames = opendlg.selectedFiles()
            if len(fnames) == 1:
                self.loadFile(str(fnames[0]))
    def loadFile(self, fname):
        path, ext = os.path.splitext(fname)
        if ext.lower() == ".camp":
            self.documentFile = path + ext
            self.viewer.loadDrawing(json.load(file(fname, "r")))
        else:
            self.documentFile = path + '.camp'
            self.viewer.setDrawing(dxfToObjects(dxfgrabber.readfile(fname)))
        self.viewer.updateSelection()
    def onOperationsSelected(self):
        selected = self.operationTree.getSelected()
        self.objectProperties.setOperations(selected)
    def onOperationProfile(self):
        self.createOperations(ShapeDirection.OUTSIDE)
    def onOperationCutout(self):
        self.createOperations(ShapeDirection.INSIDE)
    def onOperationPocket(self):
        self.createOperations(ShapeDirection.POCKET)
    def onOperationEngrave(self):
        self.createOperations(ShapeDirection.OUTLINE)
    def onOperationUnselect(self):
        for i in self.viewer.objects:
            if i.marked:
                i.setMarked(False)
        self.viewer.updateSelection()
    def createOperations(self, dir):
        shapes = []
        for i in self.viewer.objects:
            if i.marked:
                if dir == ShapeDirection.OUTLINE or isinstance(i, DrawingPolyline):
                    shapes.append(i)
                    i.setMarked(False)
        if len(shapes):
            op = CAMOperation(dir, shapes, defaultTool)
            index = self.viewer.operations.addOperation(op)
            self.operationTree.select(index)
        self.operationTree.sort()
        self.viewer.updateSelection()
    def updateOperationsAndRedraw(self):
        for o in self.viewer.operations:
            o.update()
        self.viewer.updateSelection()
    def onOperationDebug(self):
        global debugToolPaths
        debugToolPaths = not debugToolPaths
        self.viewer.updateSelection()
    def onOperationTool(self):
        tooledit = ToolEditDlg(defaultTool)
        tooledit.grid.propertyChanged.connect(self.updateOperationsAndRedraw)
        if tooledit.exec_() < 1:
            tooledit.rollback()
        self.updateOperationsAndRedraw()
    def onOperationMaterial(self):
        matedit = MaterialEditDlg(defaultMaterial)
        matedit.grid.propertyChanged.connect(self.updateOperationsAndRedraw)
        if matedit.exec_() < 1:
            matedit.rollback()
        self.updateOperationsAndRedraw()
    def onOperationGenerate(self):
        ops = self.viewer.operations.toGcode()
        f = file("test.nc", "w")
        for op in ops:
            print op
            f.write("%s\n" % op)
        f.close()

def main():    
    app = DXFApplication(sys.argv)
    w = DXFMainWindow()
    if len(sys.argv) > 1:
        w.loadFile(sys.argv[1])
    w.show()
    retcode = app.exec_()
    w = None
    app = None
    return retcode
    
sys.exit(main())
