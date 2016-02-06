from shapely.geometry import *
from shapely.affinity import *

def inch2mm(inches):
    return inches * 25.4

class Material:
    def __init__(self, thickness, layer_depth, feed, plunge, surface = 0.0, safe_z = 0.8, end_z = 30):
        self.thickness = float(thickness)
        self.layer_depth = float(layer_depth)
        self.feed = int(feed)
        self.plunge = int(plunge)
        self.surface = float(surface)
        self.safe_z = safe_z
        self.end_z = end_z
    def get_init_depth(self):
        return self.surface
    def get_final_depth(self):
        return self.surface - self.thickness
    # For shallow cuts and deepening of shallow cuts
    def range(self, thickness = None, init_rel_depth = None):
        if init_rel_depth is None:
            init_rel_depth = self.surface
        if thickness is None:
            thickness = init_rel_depth - self.get_final_depth()
        return Material(thickness = thickness, layer_depth = self.layer_depth, feed = self.feed, plunge = self.plunge, surface = init_rel_depth)

material_hips_1mm = Material(thickness = 1.0, layer_depth = 0.5, feed = 1000, plunge = 100)
# XXX needs extra pass for better finish
material_acrylic_2mm = Material(thickness = 2.0, layer_depth = 0.5, feed = 1000, plunge = 100)
material_pcb_copper = Material(thickness = 0.1, layer_depth = 0.1, feed = 500, plunge = 500)
# XXX separate material for milling edges and drilling holes/slots
material_pcb_fr4 = Material(thickness = 1.6, layer_depth = 0.4, feed = 500, plunge = 500)

material_plywood_4mm = Material(thickness = 4.0, layer_depth = 0.5, feed = 500, plunge = 500)
material_plywood_4mm_slow = Material(thickness = 4.0, layer_depth = 0.5, feed = 300, plunge = 500)
material_hdf_9mm = Material(thickness = 9.0, layer_depth = 1.0, feed = 800, plunge = 500)

#this breaks the bit at ~20k rpm
#material_aluminium_2mm = Material(thickness = 2.0, layer_depth = 0.15, feed = 800, plunge = 500)
#this also breaks the bit at ~10k rpm
#material_aluminium_2mm = Material(thickness = 2.0, layer_depth = 0.1, feed = 300, plunge = 500)

laser_focus_z = 34

class GcodeOutputBase:
    def __init__(self, operation = None, material = None, tool = None):
        self.grid = 1
        self.z = None
        self.operation = operation
        self.material = material
        self.tool = tool
        self.last_feed = None
        if operation is not None:
            self.zdepth = operation.zsurface
        elif material is not None:
            self.zdepth = material.get_final_depth()
    def get_tool(self):
        return self.tool
    def set_tool(self, tool):
        self.tool = tool
    def preamble(self):
        self.last_feed = None
        self.write("G90 G17\n")
    def set_depth(self, depth):
        self.zdepth = depth
    def set_material(self, material):
        self.material = material
    def get_surface(self):
        if self.operation is None:
            return self.material.get_init_depth()
        return self.operation.zsurface
    def get_feed(self):
        if self.operation is None:
            return self.material.feed
        return self.operation.feed
    def get_plunge(self):
        if self.operation is None:
            return self.material.plunge
        return self.operation.plunge
    def get_safe(self):
        if self.operation is None:
            self.move_z(self.material.safe_z)
        else:
            self.move_z(self.operation.zsafe)
    def move_z(self, z):
        if self.z is None or abs(z - self.z) > 0.001:
            # If the target is above the surface, always use rapids
            if z >= self.get_surface():
                self.write("G0Z%0.3f" % z)
            else:
                if self.z is None or self.z > self.get_surface():
                    # if Z unknown or above surface, rapid to surface first
                    self.write("G0Z%0.3f" % self.get_surface())
                elif z > self.z:
                    # move upwards
                    self.write("G0Z%0.3f" % z)
                    self.z = z
                    return
                # slowly plunge to the target depth
                self.emit_feed(self.get_plunge())
                self.write("G1Z%0.3f" % z)
            self.z = z
    def move_to(self, x, y):
        self.get_safe()
        self.write("G0X%0.3fY%0.3f" % (self.grid * x, self.grid * y))
    def line_to(self, x, y):
        self.move_z(self.zdepth)
        self.emit_feed(self.get_feed())
        self.write("G1X%0.3fY%0.3f" % (self.grid * x, self.grid * y))
    def arc_cw_to(self, x, y, i, j, feed):
        self.move_z(self.zdepth)
        self.emit_feed(feed)
        self.write("G2X%0.3fY%0.3fI%0.3fJ%0.3f" % (x, y, i, j))
    def arc_ccw_to(self, x, y, i, j, feed):
        self.move_z(self.zdepth)
        self.emit_feed(feed)
        self.write("G3X%0.3fY%0.3fI%0.3fJ%0.3f" % (x, y, i, j))
    def emit_feed(self, feed):
        if self.last_feed != feed:
            self.last_feed = feed
            self.write("F%0.1f" % feed)
    def end(self):
        if self.operation is not None and self.operation.zend is not None:
            self.move_z(self.operation.zend)
            self.write("G00 X0 Y0")
        elif self.material is not None:
            self.move_z(self.material.end_z)
            self.write("G00 X0 Y0")

class GcodeOutput(GcodeOutputBase):
    def __init__(self, filename, operation = None, material = None, tool = None):
        GcodeOutputBase.__init__(self, operation = operation, material = material, tool = tool)
        self.f = file(filename, "w")
        self.preamble()
    def write(self, line):
        self.f.write(line + "\n")
    def end(self):
        GcodeOutputBase.end(self)
        self.f.close()

def mill_ring(gc, r):
    gc.move_to(r.coords[-1][0], r.coords[-1][1])
    for pt in r.coords:
        gc.line_to(pt[0], pt[1])

def mill_shape(gc, p, tool):
    milled = None
    if type(p) is Polygon:
        milled = p.exterior.buffer(tool * 0.5, cap_style = 1, join_style = 1, mitre_limit = 0.05)
        mill_ring(gc, p.exterior)
        for i in p.interiors:
            milled = milled.union(i.buffer(tool * 0.5, cap_style = 1, join_style = 1, mitre_limit = 0.05))
            mill_ring(gc, i)
    elif type(p) is MultiPolygon:
        milled = MultiPolygon()
        for poly in p.geoms:
            milled = milled.union(mill_shape(gc, poly, tool))
    else:
        raise ValueError, "Unsupported type"
    return milled

def mill_poly(gc, p, tool):
    p = p.buffer(-tool * 0.5, 30, 2, 2, mitre_limit = 0.1)
    while not p.is_empty:
        milled = mill_shape(gc, p, tool)
        if milled.is_empty:
            break
        p = p.difference(milled)
        #p = p.buffer(-tool, 30, 2, 2, mitre_limit = 0.1)
        if p.is_empty:
            break

def layerbylayer(gc, operation, depth = None, init_depth = None):
    if depth is None:
        depth = gc.operation.zdepth
    if init_depth is None:
        zdepth = gc.operation.zsurface
    else:
        zdepth = init_depth
    while zdepth > depth:
        zdepth = max(depth, zdepth - abs(gc.operation.zstep))
        gc.set_depth(zdepth)
        operation(gc)

def layerbylayer2(gc, operation, zstep, final_depth, init_depth):
    zdepth = init_depth
    while zdepth > final_depth:
        zdepth = max(final_depth, zdepth - abs(zstep))
        gc.set_depth(zdepth)
        operation(gc)

def pocket_poly(gc, p, tool, depth = None, init_depth = None):
    layerbylayer(gc, lambda gc: mill_poly(gc, p, tool), depth, init_depth)

def profile_poly(gc, p, depth = None, init_depth = None):
    layerbylayer(gc, lambda gc: mill_ring(gc, p.exterior), depth, init_depth)

# For outline milling
def profile_poly_tooloutside(gc, p, tool, depth = None, init_depth = None):
    p = p.buffer(tool / 2.0).exterior
    layerbylayer(gc, lambda gc: mill_ring(gc, p), depth, init_depth)

# For cutout milling
def profile_poly_toolinside(gc, p, tool, depth = None, init_depth = None):
    p = p.buffer(-tool / 2.0).exterior
    layerbylayer(gc, lambda gc: mill_ring(gc, p), depth, init_depth)


def get_ring_or_line(shape, is_last):
    if type(shape) is LinearRing:
        return shape
    if type(shape) is LineString:
        return shape
    if type(shape) is Polygon:
        return get_ring_or_line(shape.exterior, is_last)
    if type(self.shape) is GeometryCollection:
        return get_ring_or_line(shape.geoms[-1 if is_last else 0], is_last)
    raise ValueError, "Cannot determine first/last ring of type " % type(self.shape)
    
def find_material_and_tool(gc, material, tool):
    return material if material is not None else gc.material, tool if tool is not None else gc.tool

class BaseCut:
    def __init__(self, shape, init_depth = None, final_depth = None):
        self.shape = shape
        self.init_depth = init_depth
        self.final_depth = final_depth
    def get_init_depth(self, material):
        return material.surface if self.init_depth is None else self.init_depth
    def get_final_depth(self, material):
        return (material.surface - material.thickness) if self.final_depth is None else self.final_depth
    def get_start(self):
        return Point(get_ring_or_line(self.shape, False).coords[0])
    def get_end(self):
        r = get_ring_or_line(self.shape, True)
        # if circular then start = end
        if type(r) is LinearRing:
            return Point(r.coords[0])
        return Point(r.coords[-1])

class ProfileCut(BaseCut):
    TOOL_IS_OUTSIDE = +1.0
    TOOL_IS_INSIDE = -1.0
    TOOL_IS_ENGRAVING = 0.0
    def __init__(self, shape, tool_location, init_depth = None, final_depth = None):
        BaseCut.__init__(self, shape, init_depth, final_depth)
        self.tool_location = tool_location
    @staticmethod
    def outside(shape):
        return ProfileCut(shape, ProfileCut.TOOL_IS_OUTSIDE)
    @staticmethod
    def inside(shape):
        return ProfileCut(shape, ProfileCut.TOOL_IS_INSIDE)
    @staticmethod
    def engrave(shape):
        return ProfileCut(shape, ProfileCut.TOOL_IS_ENGRAVING)
    @staticmethod
    def hole(x, y, diameter):
        return ProfileCut(Point(x, y).buffer(0.5 * diameter), ProfileCut.TOOL_IS_INSIDE)
    def run(self, gc, material = None, tool = None):
        material, tool = find_material_and_tool(gc, material, tool)
        p = self.shape.buffer(self.tool_location * tool / 2.0).exterior
        if p is None:
            raise ValueError, "Cannot mill the shape with tool diameter %f" % tool
        layerbylayer2(gc, lambda gc: mill_ring(gc, p), material.layer_depth, self.get_final_depth(material), self.get_init_depth(material))

class PocketingCut(BaseCut):
    def __init__(self, shape, init_depth = None, final_depth = None):
        BaseCut.__init__(self, shape, init_depth, final_depth)
    @staticmethod
    def hole(x, y, diameter):
        return PocketingCut(Point(x, y).buffer(0.5 * diameter))
    def run(self, gc, material = None, tool = None):
        material, tool = find_material_and_tool(gc, material, tool)
        layerbylayer2(gc, lambda gc: mill_poly(gc, self.shape, tool), material.layer_depth, self.get_final_depth(material), self.get_init_depth(material))

class CutSequence:
    def __init__(self, material = None, tool = None):
        self.material = material
        self.tool = tool
        self.cuts = []
    def add(self, operation):
        self.cuts.append(operation)
    def run(self, gc):
        material, tool = find_material_and_tool(gc, self.material, self.tool)
        for cut in self.cuts:
            cut.run(gc, material, tool)
    def optimize(self):
        if len(self.cuts) == 0:
            return
        # Minimize the rapids (using some crappy greedy optimisation algorithm)
        newcuts = []
        oldcuts = list(self.cuts)
        while len(oldcuts) > 0:
            if len(newcuts):
                lastpt = newcuts[-1].get_end()
            else:
                lastpt = Point(0, 0)
            pt = oldcuts[0].get_start()
            mindist2 = pt.distance(lastpt)
            minp = 0
            minpt = 0
            for p in xrange(len(oldcuts)):
                dist2 = oldcuts[p].get_start().distance(lastpt)
                if dist2 < mindist2:
                    mindist2 = dist2
                    minp = p
            newcuts.append(oldcuts.pop(minp))
        self.cuts = newcuts
