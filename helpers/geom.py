import math
from PyQt5.QtCore import *

defaultEps = 1e-10
twopi = 2 * math.pi

def expandRect(rc):
    dx = 0 if rc.width() else 0.1
    dy = 0 if rc.height() else 0.1
    return rc.adjusted(-dx, -dy, dx, dy)
def sign(x):
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0
def qp(p):
    return QPointF(p[0], p[1])
def qpxy(x, y):
    return QPointF(x, y)
def unqp(p):
    return (p.x(), p.y())
def r2d(r):
    return r * 180 / math.pi
def d2r(r):
    return r * math.pi / 180
def norm(dx, dy):
    return math.sqrt(dx ** 2 + dy ** 2)
def pdist(p1, p2):
    return norm(p1.x() - p2.x(), p1.y() - p2.y())
def tdist(p1, p2):
    return norm(p1[0] - p2[0], p1[1] - p2[1])
def circ(p, r, a):
    return QPointF(p.x() + r * math.cos(a), p.y() + r * math.sin(a))
def circ2(p, r, a):
    return (p.x() + r * math.cos(a), p.y() + r * math.sin(a))
def circ3(x, y, r, a):
    return (x + r * math.cos(a), y + r * math.sin(a))
def circ4(x, y, r, a):
    return QPointF(x + r * math.cos(a), y + r * math.sin(a))
def nangle(a):
    if a > -math.pi and a <= math.pi:
        return a
    return (a + math.pi) % twopi - math.pi
def tang(p1, p2):
    return math.atan2(p2.y() - p1.y(), p2.x() - p1.x())
def interp(p1, p2, c):
    return QPointF(p1.x() * (1 - c) + p2.x() * c, p1.y() * (1 - c) + p2.y() * c)
def eqtol(value, expected, eps = defaultEps):
    return abs(value - expected) < eps
def assert_eqtol(value, expected, eps = defaultEps):
    if abs(value - expected) >= eps:
        assert False, "Value %f, expected %f, difference %f, tolerance %f" % (value, expected, (value - expected), eps)
def assert_ptclose(p1, p2, eps = defaultEps):
    dist = pdist(p1, p2)
    if dist >= eps:
        assert False, "Distance %f, tolerance %f, p1 %s, p2 %s" % (dist, eps, p1, p2)
def assert_dist(p1, p2, expdist, eps = defaultEps):
    dist = pdist(p1, p2)
    if abs(dist - expdist) >= eps:
        assert False, "Distance %f, expected %f, difference %f, tolerance %f, p1 %s, p2 %s" % (dist, expdist, abs(dist - expdist), eps, p1, p2)

def distPointToLine(posF, line):
    line2 = QLineF(line.p1(), posF)
    a = d2r(line.angleTo(line2))
    across = line2.length() * math.sin(a)
    along = line2.length() * math.cos(a)
    if along >= 0 and along <= line.length():
        return abs(across)
    elif along < 0:
        return norm(along, across)
    else:
        return norm((along - line.length()), across)

def test_norm():
    assert_eqtol(norm(0, 0), 0)
    assert_eqtol(norm(0, 1), 1)
    assert_eqtol(norm(1, 0), 1)
    assert_eqtol(norm(1, 1), math.sqrt(2))
def test_d2r():
    assert_eqtol(math.cos(d2r(90)), 0)
    assert_eqtol(math.sin(d2r(90)), 1)
def test_r2d():
    assert_eqtol(r2d(0), 0)
    assert_eqtol(r2d(twopi), 360)
def test_pdist():
    assert_eqtol(pdist(QPointF(0, 1), QPointF(1, 0)), norm(1, -1))
    assert_eqtol(pdist(QPointF(0, 0), QPointF(1, 1)), norm(1, 1))
    assert_eqtol(pdist(QPointF(0, 0), QPointF(1, 0)), 1)
    assert_eqtol(pdist(QPointF(0, 0), QPointF(0, 1)), 1)
def test_circ():
    for caller in [
        (lambda p, r, a: circ(p, r, a)),
        (lambda p, r, a: qp(circ2(p, r, a))),
        (lambda p, r, a: qp(circ3(p.x(), p.y(), r, a))),
        (lambda p, r, a: circ4(p.x(), p.y(), r, a))]:
        assert_ptclose(caller(qpxy(1, 0), 5, 0), qpxy(6, 0))
        assert_ptclose(caller(qpxy(1, 0), 5, d2r(90)), qpxy(1, 5))
        assert_ptclose(caller(qpxy(1, 0), 5, d2r(45)), qpxy(1 + 5 * math.sqrt(2) / 2, 5 * math.sqrt(2) / 2))
def test_interp():
    for i in range(11):
        t = i / 10.0
        assert_ptclose(interp(qpxy(10, 0), qpxy(0, 10), t), qpxy(10 - 10 * t, 10 * t))
def test_distPointToLine():
    hl = QLineF(2, 0, 2, 2)
    vl = QLineF(0, 2, 2, 2)
    for x in range(5):
        d = abs(x - 2)
        assert_eqtol(distPointToLine(qpxy(x, 0), hl), d)
        assert_eqtol(distPointToLine(qpxy(x, 1), hl), d)
        assert_eqtol(distPointToLine(qpxy(x, 2), hl), d)
        assert_eqtol(distPointToLine(qpxy(x, 3), hl), norm(d, 1))
        assert_eqtol(distPointToLine(qpxy(x, 4), hl), norm(d, 2))
        assert_eqtol(distPointToLine(qpxy(x, -1), hl), norm(d, 1))
        assert_eqtol(distPointToLine(qpxy(x, -2), hl), norm(d, 2))
        
        assert_eqtol(distPointToLine(qpxy(0, x), vl), d)
        assert_eqtol(distPointToLine(qpxy(1, x), vl), d)
        assert_eqtol(distPointToLine(qpxy(2, x), vl), d)
        assert_eqtol(distPointToLine(qpxy(3, x), vl), norm(d, 1))
        assert_eqtol(distPointToLine(qpxy(4, x), vl), norm(d, 2))
        assert_eqtol(distPointToLine(qpxy(-1, x), vl), norm(d, 1))
        assert_eqtol(distPointToLine(qpxy(-2, x), vl), norm(d, 2))

if __name__ == "__main__":
    test_norm()
    test_d2r()
    test_r2d()
    test_pdist()
    test_circ()
    test_interp()
    test_distPointToLine()
    