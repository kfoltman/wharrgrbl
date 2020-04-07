import math
import sys
sys.path += ['.']
from PyQt5 import QtCore, QtGui, QtWidgets
from cam.rdkic import *
from helpers.preview import PathPreview
from cam.mill import *
from helpers.gui import MenuHelper

class CAMApplication(QtWidgets.QApplication):
    pass

class CAMMainWindow(QtWidgets.QMainWindow, MenuHelper):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        MenuHelper.__init__(self)
        self.milling_params = MillingParams()
        self.initUI()
    
    def exportGcode(self, board):
        engraving = EngravingOperation()
        gc = GcodeOutput("back.nc", engraving)
        mill_contours(gc, board, "B.Cu", self.milling_params)
        gc.end()
        gc = GcodeOutput("drill.nc", PeckDrillingOperation())
        drill_holes_and_slots(gc, board, "B.Cu", self.milling_params)
        gc.end()
        gc = GcodeOutput("cuts.nc", EdgeCuttingOperation())
        cut_edges(gc, board, "Edge.Cuts", self.milling_params)
        gc.end()
        sizer = BoardSizer(self.view.board)
        bsizex = abs(sizer.maxpt[0] - sizer.minpt[0] + 1.6)
        bsizey = abs(sizer.maxpt[1] - sizer.minpt[1] + 1.6)
        scamfile = '''
<openscam>
  <nc-files>
    pcb.nc
  </nc-files>

  <!-- Renderer -->
  <resolution v='%f'/>
  <resolution-mode v='MANUAL'/>

  <!-- Workpiece -->
  <automatic-workpiece v='false'/>
  <workpiece-max v='(%f,%f,0)'/>
  <workpiece-min v='(-1.6,-1.6,-1.6)'/>

  <tool_table>
    <tool length='10' number='1' radius='%f' shape='CYLINDRICAL' units='MM'/>
    <tool length='10' number='2' radius='%f' shape='CYLINDRICAL' units='MM'/>
  </tool_table>
</openscam>
    ''' % (self.milling_params.tool_width / 2.0, bsizex, bsizey, self.milling_params.tool_width / 2.0, PeckDrillingOperation().endmill_dia / 2.0)
        file("pcb.openscam", "w").write(scamfile)
        f = file("pcb.nc", "w")
        f.write("M6 T1\n")
        f.write(file("back.nc", "r").read())
        f.write("M6 T2\n")
        f.write(file("drill.nc", "r").read())
        f.write(file("cuts.nc", "r").read())
        f.close()
        msgbox = QtGui.QMessageBox()
        msgbox.setText("Board files (back.nc cuts.nc drill.nc) generated, width=%0.1fmm height=%0.1fmm" % (bsizex, bsizey))
        msgbox.exec_()
    
    def hasBoard(self):
        return self.view.board is not None

    def setBoard(self, board):
        self.view.board = board
        self.w.sizeBoard()
        self.w.recalcAndRepaint()
        self.updateActions()

    def requiresBoard(self, action):
        return self.addEnabledHandler(action, self.hasBoard)

    def initUI(self):
        self.view = ViewParams()
        if len(sys.argv) > 1:
            self.view.board = KicadBoard(file(sys.argv[1], "r"))
                
        self.w = PathPreview(self.view, self.milling_params)
        menuBar = self.menuBar()
        fileMenu = menuBar.addMenu("&File")
        fileMenu.addAction(self.makeAction("&Open", "Ctrl+O", "Open a file", self.onFileOpen))
        fileMenu.addAction(self.requiresBoard(self.makeAction("&Export", "Ctrl+E", "Export gcode to a series of files", self.onFileExport)))
        fileMenu.addAction(self.makeAction("E&xit", "Ctrl+Q", "Exit the application", self.close))

        viewMenu = menuBar.addMenu("&View")
        group = QtWidgets.QActionGroup(self)
        
        viewMenu.addAction(self.requiresBoard(self.makeAction("&Zoom in", "Ctrl++", "Zoom in", self.onViewZoomIn)))
        viewMenu.addAction(self.requiresBoard(self.makeAction("Zoo&m out", "Ctrl+-", "Zoom out", self.onViewZoomOut)))
        viewMenu.addAction(self.requiresBoard(self.makeAction("&Original size", "Ctrl+0", "", self.onViewOriginalSize)))
        viewMenu.addAction(self.makeSeparator())
        viewMenu.addAction(self.requiresBoard(self.makeCheckAction("&Rainbow mode", "Shift+Ctrl+R", "", self.onViewRainbowMode, lambda: self.view.rainbow_mode)))
        viewMenu.addAction(self.requiresBoard(self.makeCheckAction("R&ealistic mode", "Shift+Ctrl+E", "", self.onViewRealisticMode, lambda: self.view.realistic_mode)))
        viewMenu.addAction(self.makeSeparator())
        viewMenu.addAction(self.requiresBoard(self.makeRadioAction("&Front", "Ctrl+F", "See the front layer", group, lambda: self.onViewLayer("F.Cu"), lambda: self.view.cur_layer == "F.Cu")))
        viewMenu.addAction(self.requiresBoard(self.makeRadioAction("&Back", "Ctrl+B", "See the back layer", group, lambda: self.onViewLayer("B.Cu"), lambda: self.view.cur_layer == "B.Cu")))
        viewMenu.addAction(self.requiresBoard(self.makeRadioAction("&Cuts", "Ctrl+T", "See the cuts layer", group, lambda: self.onViewLayer("Edge.Cuts"), lambda: self.view.cur_layer == "Edge.Cuts")))
        
        toolpathMenu = menuBar.addMenu("&Toolpath")
        group = QtWidgets.QActionGroup(self)
        toolpathMenu.addAction(self.makeRadioAction("0.&1mm", "Ctrl+1", "Set milling diameter to 0.1mm", group, lambda: self.onToolDiameter(0.1), lambda: self.milling_params.tool_width == 0.1))
        toolpathMenu.addAction(self.makeRadioAction("0.&2mm", "Ctrl+2", "Set milling diameter to 0.2mm", group, lambda: self.onToolDiameter(0.2), lambda: self.milling_params.tool_width == 0.2))
        toolpathMenu.addAction(self.makeRadioAction("0.&3mm", "Ctrl+3", "Set milling diameter to 0.3mm", group, lambda: self.onToolDiameter(0.3), lambda: self.milling_params.tool_width == 0.3))
        toolpathMenu.addAction(self.makeSeparator())
        toolpathMenu.addAction(self.makeCheckAction("&Double isolation", "", "Add extra pass to widen isolation paths (slow!)", self.onToolDouble, lambda: self.milling_params.doubleIsolation))
        
        self.coordLabel = QtWidgets.QLabel("")
        self.statusBar().insertPermanentWidget(0, self.coordLabel)
        
        self.setCentralWidget(self.w)
        self.setWindowTitle("KF's insane PCB factory")
        self.updateStatus()
        self.updateActions()

    def updateStatus(self):
        self.statusBar().showMessage("Ready to rok.")

    def onFileExport(self):
        self.exportGcode(self.view.board)
        
    def onFileOpen(self):
        fname, ffilter = QtWidgets.QFileDialog.getOpenFileName(self, 'Open file', '.', "Kicad PCB files (*.kicad_pcb)")
        if fname != '':
            self.setBoard(KicadBoard(file(fname, "r")))
        
    def onViewLayer(self, layer):
        self.view.cur_layer = layer
        self.w.recalcAndRepaint()

    def onViewZoomIn(self):
        self.view.scale *= 1.25
        self.w.recalcAndRepaint()
    
    def onViewZoomOut(self):
        self.view.scale /= 1.25
        self.w.recalcAndRepaint()

    def onViewRainbowMode(self):
        self.view.rainbow_mode = not self.view.rainbow_mode
        if self.view.rainbow_mode:
            self.view.realistic_mode = False
        self.w.recalcAndRepaint()
        self.updateActions()

    def onViewRealisticMode(self):
        self.view.realistic_mode = not self.view.realistic_mode
        if self.view.realistic_mode:
            self.view.rainbow_mode = False
        self.w.recalcAndRepaint()
        self.updateActions()

    def onViewOriginalSize(self):
        self.view.scale = 96 / 25.4
        self.w.recalcAndRepaint()
        self.updateActions()

    def onToolDiameter(self, dia):
        self.milling_params.tool_width = dia
        self.w.recalcAndRepaint()
        self.updateActions()
    
    def onToolDouble(self):
        self.milling_params.doubleIsolation = not self.milling_params.doubleIsolation
        self.w.recalcAndRepaint()
        self.updateActions()
    
def main():    
    app = CAMApplication(sys.argv)
    w = CAMMainWindow()
    w.show()
    
    sys.exit(app.exec_())

main()
