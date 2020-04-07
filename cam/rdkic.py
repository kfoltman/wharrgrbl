import sexpdata
from PyQt5 import QtCore, QtGui, QtWidgets
import sys
import math

def sym2str(e):
    if type(e) is str:
        return e
    return e.value()
def rotdeg(xy, angle):
    x, y = xy
    angle = math.pi * angle / 180
    return (x * math.cos(angle) + y * math.sin(angle), -x * math.sin(angle) + y * math.cos(angle))

class Segment(object):
    def __init__(self, start, end, width, layer, net):
        self.start = (float(start[0]), float(start[1]))
        self.end = (float(end[0]), float(end[1]))
        self.width = float(width)
        self.layer = layer
        self.net = int(net)
    def __str__(self):
        return "%s: segment (%f, %f) - (%f, %f) width: %f" % (self.layer, self.start[0], self.start[1], self.end[0], self.end[1], self.width)

class GraphicLine(object):
    def __init__(self, start, end, width, layer):
        self.start = (float(start[0]), float(start[1]))
        self.end = (float(end[0]), float(end[1]))
        self.width = float(width)
        self.layer = layer
    def __str__(self):
        return "%s: gr-line (%f, %f) - (%f, %f) width: %f" % (self.layer, self.start[0], self.start[1], self.end[0], self.end[1], self.width)

class PCBPad(object):
    def __init__(self, x, y, w, h, shape, pad_type, layers, net, drillx, drilly):
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.shape = shape
        self.pad_type = pad_type
        self.layers = layers
        self.net = int(net)
        self.drillx = drillx
        self.drilly = drilly

class PCBLayer(object):
    def __init__(self, name):
        self.name = name
        self.segments = []
        self.polygons = {}
        self.pads = []
        self.gr_lines = []

class KicadBoard(object):
    def __init__(self, fileobj):
        self.sexpr = sexpdata.load(fileobj)
        self.version = None
        self.host = None
        self.host_version = None
        self.page = None
        self.general = {}
        self.setup = {}
        self.nets = {}
        self.layers = {}
        self.pcbplotparams = {}
        if self.sexpr[0].value() != 'kicad_pcb':
            raise ValueError("Not a kicad pcb file")
            
        def parsedict(dictout, node, subtrees = {}):
            for g in node[1:]:
                name = g[0].value()
                if name in subtrees:
                    parsedict(subtrees[name], g)
                elif len(g) == 2:
                    dictout[g[0].value()] = g[1]
                else:
                    dictout[g[0].value()] = g[1:]
            
        for e in self.sexpr[1:]:
            sym = e[0].value()
            if sym == 'version':
                self.version = e[1]
            elif sym == 'host':
                self.host = e[1].value()
                self.host_version = e[2]
            elif sym == 'page':
                self.page = e[1].value()
            elif sym == 'general':
                parsedict(self.general, e)
            elif sym == 'setup':
                parsedict(self.setup, e, {'pcbplotparams' : self.pcbplotparams})
            elif sym == 'net':
                self.nets[int(e[1])] = sym2str(e[2])
            elif sym == 'module':
                x, y, angle = None, None, 0
                for si in e[2:]:
                    if type(si) is sexpdata.Symbol:
                        continue
                    sym = si[0].value()
                    if sym == 'at':
                        x, y = float(si[1]), float(si[2])
                        if len(si) > 3:
                            angle = si[3]
                    elif sym == 'pad':
                        pad_type = sym2str(si[2])
                        pad_shape = sym2str(si[3])
                        padx, pady = None, None
                        padw, padh = None, None
                        padangle = angle
                        layers = None
                        net = 0
                        drillx = 0
                        drilly = 0
                        for pat in si[4:]:
                            sym = pat[0].value()
                            if sym == 'at':
                                paddx, paddy = rotdeg((float(pat[1]), float(pat[2])), angle)
                                padx, pady = float(x + paddx), float(y + paddy)
                                if len(pat) > 3:
                                    padangle = pat[3]
                            elif sym == 'size':
                                padw, padh = float(pat[1]), float(pat[2])
                            elif sym == 'drill' and len(pat) > 1:
                                if type(pat[1]) in [float, int]:
                                    drillx, drilly = float(pat[1]), float(pat[1])
                                elif sym2str(pat[1]) == 'oval':
                                    drillx = float(pat[2])
                                    if len(pat) == 3:
                                        drilly = drillx
                                    else:
                                        drilly = float(pat[3])
                            elif sym == 'layers':
                                layers = map(sym2str, pat[1:])
                            elif sym == 'net':
                                net = pat[1]
                        if padangle in [90, 270]:
                            padw, padh = padh, padw
                            drillx, drilly = drilly, drillx
                        self.add_pad(PCBPad(padx, pady, padw, padh, pad_shape, pad_type, layers, net, drillx, drilly))
            elif sym == 'zone':
                net = None
                layer = None
                for si in e[1:]:
                    sym = si[0].value()
                    if sym == 'net':
                        net = si[1]
                    elif sym == 'layer':
                        layer = sym2str(si[1])
                    elif sym == 'filled_polygon':
                        pts = []
                        for xy in si[1][1:]:
                            if sym2str(xy[0]) != 'xy':
                                raise ValueError, "Invalid item inside filled_polygon"
                            pts.append((float(xy[1]), float(xy[2])))
                        lp = self.get_layer(layer).polygons
                        if net not in lp:
                            lp[net] = [pts]
                        else:
                            lp[net].append(pts)
            elif sym == 'segment':
                start = None
                end = None
                width = None
                net = None
                for si in e[1:]:
                    sym = si[0].value()
                    if sym == 'start':
                        start = (si[1], si[2])
                    if sym == 'end':
                        end = (si[1], si[2])
                    if sym == 'width':
                        width = si[1]
                    if sym == 'layer':
                        layer = sym2str(si[1])
                    if sym == 'net':
                        net = si[1]
                self.get_layer(layer).segments.append(Segment(start = start, end = end, width = width, layer = layer, net = net))
            elif sym == 'gr_line':
                start = None
                end = None
                width = None
                for si in e[1:]:
                    sym = si[0].value()
                    if sym == 'start':
                        start = (si[1], si[2])
                    if sym == 'end':
                        end = (si[1], si[2])
                    if sym == 'width':
                        width = si[1]
                    if sym == 'layer':
                        layer = sym2str(si[1])
                self.get_layer(layer).gr_lines.append(GraphicLine(start = start, end = end, width = width, layer = layer))
                
        #print self.version, self.host, self.host_version, self.page
        #print self.general
        #print self.setup
        #print self.pcbplotparams
        #print self.nets
    def add_pad(self, pad):
        if len(pad.layers) == 0:
            # XXXKF not really correct, but there's no better alternative yet
            self.get_layer("F.Cu").pads.append(pad)
            self.get_layer("B.Cu").pads.append(pad)
        for l in pad.layers:
            if l == "*.Cu":
                self.get_layer("F.Cu").pads.append(pad)
                self.get_layer("B.Cu").pads.append(pad)
            else:
                self.get_layer(l).pads.append(pad)
    def get_layer(self, name):
        if name in self.layers:
            return self.layers[name]
        l = PCBLayer(name)
        self.layers[name] = l
        return l
    def net2color(self, net):
        if net == '':
            return QtGui.QColor(255, 255, 255)
        if net == 'cleanup':
            return QtGui.QColor(255, 255, 0)
        if self.nets[net] == 'GND':
            return QtGui.QColor(0, 0, 0)
        net += 1
        r = 0
        g = 0
        b = 0
        weight = 128
        while net > 0:
            if net & 1:
                r += weight
            if net & 2:
                g += weight
            if net & 4:
                b += weight
            weight >>= 1
            net >>= 3
        return QtGui.QColor(r, g, b)

