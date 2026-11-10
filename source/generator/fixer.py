"""Small grid maze router for the last few connections the autorouter left open.

Works on a saved (unfilled) board: adds tracks/vias for named connections and GND stitching vias
next to GND pads, checking clearance against every other-net item on each layer.
"""
import heapq, math
import pcbnew

MM, T = pcbnew.FromMM, pcbnew.ToMM
CLR = 0.23
VIA_D, VIA_DR = 0.6, 0.3
LAY = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu}
ALL = [pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]


class Fixer:
    def __init__(self, board):
        self.b = board
        self.edge = board.GetBoardEdgesBoundingBox()

    def _items(self, layer, net, x, y, r):
        """other-net copper on `layer` near (x,y) within r (mm)."""
        out = []
        for t in self.b.GetTracks():
            if t.GetNetname() == net:
                continue
            if t.GetClass() == "PCB_VIA" or t.GetLayer() == layer:
                bb = t.GetBoundingBox()
                if T(bb.GetLeft()) - r < x < T(bb.GetRight()) + r and T(bb.GetTop()) - r < y < T(bb.GetBottom()) + r:
                    out.append(t)
        for fp in self.b.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() == net and net:
                    continue
                if not p.IsOnLayer(layer):
                    continue
                bb = p.GetBoundingBox()
                if T(bb.GetLeft()) - r < x < T(bb.GetRight()) + r and T(bb.GetTop()) - r < y < T(bb.GetBottom()) + r:
                    out.append(p)
        return out

    def free(self, layer, net, x, y, half):
        """is a disc of radius `half` at (x,y) on layer clear of other nets (+CLR)?"""
        acc = MM(half + CLR)
        pt = pcbnew.VECTOR2I(MM(x), MM(y))
        if not (T(self.edge.GetLeft()) + half + 0.5 < x < T(self.edge.GetRight()) - half - 0.5 and
                T(self.edge.GetTop()) + half + 0.5 < y < T(self.edge.GetBottom()) - half - 0.5):
            return False
        for it in self._items(layer, net, x, y, half + CLR + 2.0):
            if isinstance(it, pcbnew.PAD):
                if it.HitTest(pt, acc):
                    return False
                if it.GetDrillSize().x > 0 and it.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH and it.HitTest(pt, acc):
                    return False
            elif it.HitTest(pt, acc):
                return False
        if layer in (pcbnew.F_Cu, pcbnew.B_Cu):
            for z in self.b.Zones():
                if z.GetLayer() == layer and z.GetNetname() not in (net, "GND"):
                    if z.Outline().Collide(pt, acc):
                        return False
        return True

    def via_ok(self, net, x, y):
        return all(self.free(L, net, x, y, VIA_D / 2) for L in ALL if L in (pcbnew.F_Cu, pcbnew.B_Cu)) and \
            self._inner_ok(net, x, y)

    def _inner_ok(self, net, x, y):
        # inner layers: only tracks/vias of other nets matter (planes refill around vias)
        acc = MM(VIA_D / 2 + CLR)
        pt = pcbnew.VECTOR2I(MM(x), MM(y))
        for t in self.b.GetTracks():
            if t.GetNetname() != net and (t.GetClass() == "PCB_VIA" or t.GetLayer() in (pcbnew.In1_Cu, pcbnew.In2_Cu)):
                if t.HitTest(pt, acc):
                    return False
        return True

    def add_track(self, net, pts, w, layer):
        ni = self.b.FindNet(net)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I(MM(x0), MM(y0))); t.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
            t.SetWidth(MM(w)); t.SetLayer(layer); t.SetNet(ni)
            self.b.Add(t)

    def add_via(self, net, x, y):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(VIA_D)); v.SetDrill(MM(VIA_DR)); v.SetNet(self.b.FindNet(net))
        self.b.Add(v)

    def pad(self, ref, num):
        fp = self.b.FindFootprintByReference(ref)
        for p in fp.Pads():
            if p.GetNumber() == num:
                return p
        raise KeyError(ref + "." + num)

    # ------------------------------------------------------------------ maze route
    def route(self, net, a, b, w=0.25, step=0.1, win=6.0, layers=("F", "B")):
        """A* from point a to point b (both on F.Cu pads). Returns True on success."""
        (ax, ay), (bx, by) = a, b
        x0, y0 = min(ax, bx) - win, min(ay, by) - win
        nx, ny = int((abs(ax - bx) + 2 * win) / step) + 1, int((abs(ay - by) + 2 * win) / step) + 1
        g = lambda i, j: (x0 + i * step, y0 + j * step)
        si, sj = round((ax - x0) / step), round((ay - y0) / step)
        ti, tj = round((bx - x0) / step), round((by - y0) / step)
        cache = {}

        def ok(i, j, L):
            k = (i, j, L)
            if k not in cache:
                x, y = g(i, j)
                near_end = math.hypot(x - ax, y - ay) < 0.5 or math.hypot(x - bx, y - by) < 0.5
                cache[k] = self.free(LAY[layers[L]], net, x, y, w / 2)
            return cache[k]

        vcache = {}

        def vok(i, j):
            if (i, j) not in vcache:
                vcache[(i, j)] = self.via_ok(net, *g(i, j))
            return vcache[(i, j)]

        start, goal = (si, sj, 0), (ti, tj, 0)
        h = lambda n: math.hypot(n[0] - ti, n[1] - tj)
        openq = [(h(start), 0, start)]
        came, cost = {start: None}, {start: 0}
        dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
        found = None
        it = 0
        while openq and it < 400000:
            it += 1
            _, c, n = heapq.heappop(openq)
            if n == goal:
                found = n
                break
            i, j, L = n
            nbrs = []
            for di, dj in dirs:
                m = (i + di, j + dj, L)
                if 0 <= m[0] < nx and 0 <= m[1] < ny and ok(*m):
                    nbrs.append((m, math.hypot(di, dj) * (1.0 if L == 0 else 1.3)))
            if len(layers) > 1 and vok(i, j):
                nbrs.append(((i, j, 1 - L), 15.0))
            for m, dc in nbrs:
                nc = c + dc
                if nc < cost.get(m, 1e18):
                    cost[m] = nc
                    came[m] = n
                    heapq.heappush(openq, (nc + h(m), nc, m))
        if not found:
            return False
        path = []
        n = found
        while n:
            path.append(n)
            n = came[n]
        path.reverse()
        # emit: split into same-layer runs, simplify collinear points
        runs, cur = [], [path[0]]
        for p in path[1:]:
            if p[2] != cur[-1][2]:
                runs.append(cur); cur = [p]
            else:
                cur.append(p)
        runs.append(cur)
        for k, r in enumerate(runs):
            pts = [g(i, j) for i, j, _ in r]
            simp = [pts[0]]
            for q in range(1, len(pts) - 1):
                d1 = (pts[q][0] - simp[-1][0], pts[q][1] - simp[-1][1])
                d2 = (pts[q + 1][0] - pts[q][0], pts[q + 1][1] - pts[q][1])
                if abs(d1[0] * d2[1] - d1[1] * d2[0]) > 1e-9:
                    simp.append(pts[q])
            simp.append(pts[-1])
            if k == 0:
                simp[0] = (ax, ay)
            if k == len(runs) - 1:
                simp[-1] = (bx, by)
            if len(simp) > 1:
                self.add_track(net, simp, w, LAY[layers[r[0][2]]])
            if k < len(runs) - 1:
                self.add_via(net, *simp[-1])
        return True

    def gnd_via(self, pad, w=0.3, rmax=3.0):
        """stitch a GND pad down to the In1 plane: nearest legal via + straight F.Cu stub."""
        p = pad.GetPosition()
        px, py = T(p.x), T(p.y)
        best = None
        r = 0.6
        while r <= rmax and not best:
            for k in range(24):
                a = 2 * math.pi * k / 24
                x, y = px + r * math.cos(a), py + r * math.sin(a)
                if not self.via_ok("GND", x, y):
                    continue
                # stub clear?
                n = max(2, int(r / 0.1))
                if all(self.free(pcbnew.F_Cu, "GND", px + (x - px) * s / n, py + (y - py) * s / n, w / 2)
                       or pad.HitTest(pcbnew.VECTOR2I(MM(px + (x - px) * s / n), MM(py + (y - py) * s / n)))
                       for s in range(n + 1)):
                    best = (x, y)
                    break
            r += 0.2
        if not best:
            return False
        self.add_track("GND", [(px, py), best], w, pcbnew.F_Cu)
        self.add_via("GND", *best)
        return True
