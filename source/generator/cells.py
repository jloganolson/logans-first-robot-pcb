"""Board builder + hand-laid converter cells (KiCad 7 pcbnew).

Coordinates inside a cell are mm relative to the cell origin, before the cell rotation.
Power nets are carried by explicit copper zones; critical small-signal and gate-drive
traces are drawn explicitly. Anything left over is finished by Freerouting.
"""
import math, os
import pcbnew

MM = pcbnew.FromMM
FPDIR = os.environ.get("KICAD7_FOOTPRINT_DIR", "/usr/share/kicad/footprints")
VIA = (0.6, 0.3)          # via diameter / drill (JLC standard)
LAYER = {"F": pcbnew.F_Cu, "B": pcbnew.B_Cu, "In1": pcbnew.In1_Cu, "In2": pcbnew.In2_Cu}


class Board:
    def __init__(self, parts, layers=4):
        self.b = pcbnew.BOARD()
        self.b.SetCopperLayerCount(layers)
        self.b.GetDesignSettings().SetBoardThickness(MM(1.6))
        self.nets = {}
        self.fps = {}
        self.parts = {p["ref"]: p for p in parts}
        self.zones = []
        self.fixed_nets = set()
        for p in parts:
            lib, name = p["fp"].split(":")
            fp = pcbnew.FootprintLoad(f"{FPDIR}/{lib}.pretty", name)
            fp.SetReference(p["ref"])
            fp.SetValue(p["value"][:24])
            fp.SetFPID(pcbnew.LIB_ID(lib, name))
            for pad in fp.Pads():
                n = p["pins"].get(pad.GetNumber())
                if n:
                    pad.SetNet(self.net(n))
            fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
            fp.Reference().SetTextThickness(MM(0.15))
            fp.Value().SetVisible(False)
            if p.get("dnp"):
                fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
            if p["ref"].startswith("U"):
                fp.SetZoneConnection(pcbnew.ZONE_CONNECTION_FULL)
            self.b.Add(fp)
            self.fps[p["ref"]] = fp

    def net(self, name):
        if name not in self.nets:
            n = self.b.FindNet(name)
            if n is None:
                n = pcbnew.NETINFO_ITEM(self.b, name)
                self.b.Add(n)
            self.nets[name] = n
        return self.nets[name]

    def cell(self, ox, oy, rot=0):
        return Cell(self, ox, oy, rot)

    # absolute-coordinate helpers -------------------------------------------------
    def place(self, ref, x, y, rot=0):
        fp = self.fps[ref]
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        fp.SetOrientationDegrees(rot % 360)

    def pad(self, ref, num):
        for p in self.fps[ref].Pads():
            if p.GetNumber() == num:
                v = p.GetPosition()
                return (pcbnew.ToMM(v.x), pcbnew.ToMM(v.y))
        raise KeyError(f"{ref}.{num}")

    def track(self, net, pts, w=0.25, layer="F"):
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(self.b)
            t.SetStart(pcbnew.VECTOR2I(MM(x0), MM(y0)))
            t.SetEnd(pcbnew.VECTOR2I(MM(x1), MM(y1)))
            t.SetWidth(MM(w)); t.SetLayer(LAYER[layer]); t.SetNet(self.net(net))
            self.b.Add(t)

    def via(self, net, x, y, d=VIA[0], drill=VIA[1]):
        v = pcbnew.PCB_VIA(self.b)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(d)); v.SetDrill(MM(drill)); v.SetNet(self.net(net))
        self.b.Add(v)

    def zone(self, net, layer, poly, prio=1, clearance=0.3, thermal=False, minw=0.25):
        z = pcbnew.ZONE(self.b)
        z.SetLayer(LAYER[layer])
        z.SetNet(self.net(net))
        ol = z.Outline(); ol.NewOutline()
        for x, y in poly:
            ol.Append(MM(x), MM(y))
        z.SetAssignedPriority(prio)
        z.SetLocalClearance(MM(clearance))
        z.SetMinThickness(MM(minw))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL if thermal else pcbnew.ZONE_CONNECTION_FULL)
        z.SetThermalReliefGap(MM(0.4)); z.SetThermalReliefSpokeWidth(MM(0.6))
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        self.b.Add(z)
        self.zones.append(z)
        return z

    def text(self, t, x, y, size=1.2, layer=pcbnew.F_SilkS, rot=0):
        tx = pcbnew.PCB_TEXT(self.b)
        tx.SetText(t)
        tx.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        tx.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
        tx.SetTextThickness(MM(max(0.15, size * 0.15)))
        tx.SetTextAngleDegrees(rot)
        tx.SetLayer(layer)
        self.b.Add(tx)

    def outline(self, W, H, r=3.0):
        def seg(a, b):
            s = pcbnew.PCB_SHAPE(self.b); s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1]))); s.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); self.b.Add(s)
        def arc(c, start, ang):
            s = pcbnew.PCB_SHAPE(self.b); s.SetShape(pcbnew.SHAPE_T_ARC)
            s.SetCenter(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
            s.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
            s.SetArcAngleAndEnd(pcbnew.EDA_ANGLE(ang, pcbnew.DEGREES_T), True)
            s.SetLayer(pcbnew.Edge_Cuts); s.SetWidth(MM(0.1)); self.b.Add(s)
        seg((r, 0), (W - r, 0)); seg((W, r), (W, H - r)); seg((W - r, H), (r, H)); seg((0, H - r), (0, r))
        arc((W - r, r), (W - r, 0), 90); arc((W - r, H - r), (W, H - r), 90)
        arc((r, H - r), (r, H), 90); arc((r, r), (0, r), 90)


class Cell:
    """A transform (translate + rotate by multiples of 90) applied to all drawing calls."""

    def __init__(self, B, ox, oy, rot):
        self.B, self.ox, self.oy, self.rot = B, ox, oy, rot % 360

    def T(self, x, y):
        a = math.radians(self.rot)
        c, s = round(math.cos(a)), round(math.sin(a))
        # KiCad rotation: +angle is counter-clockwise on screen (y down)
        return (self.ox + x * c + y * s, self.oy - x * s + y * c)

    def place(self, ref, x, y, rot=0):
        X, Y = self.T(x, y)
        self.B.place(ref, X, Y, rot + self.rot)

    def _pt(self, p):
        if isinstance(p[0], str):
            return self.B.pad(*p)
        return self.T(*p)

    def track(self, net, pts, w=0.25, layer="F"):
        self.B.track(net, [self._pt(p) for p in pts], w, layer)

    def via(self, net, x, y):
        self.B.via(net, *self.T(x, y))

    def vias(self, net, xs, ys):
        for x in xs:
            for y in ys:
                self.via(net, x, y)

    def zone(self, net, layer, poly, prio=1, **kw):
        return self.B.zone(net, layer, [self.T(x, y) for x, y in poly], prio, **kw)

    def rect(self, net, layer, x0, y0, x1, y1, prio=1, **kw):
        return self.zone(net, layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], prio, **kw)

    def text(self, t, x, y, size=1.2, rot=0):
        X, Y = self.T(x, y)
        self.B.text(t, X, Y, size, rot=rot)


def frange(a, b, step):
    out, v = [], a
    while v <= b + 1e-9:
        out.append(round(v, 3)); v += step
    return out


# ============================================================================ TPS54560 cell
# Relative extents: x -12..21.5, y -25..9.5 (incl. output strip up to the XT30 pins at y=-22)
def tps_cell(B, n, net, ox, oy, rot=0, label=""):
    b = 100 * (n + 1)
    k = None
    for p in B.parts.values():
        if p["ref"] == f"U{3+n}":
            k = p["pins"]["1"].split("_")[0]
    pf = k + "_"
    U, L = f"U{3+n}", f"L{2+n}"
    c = B.cell(ox, oy, rot)
    # --- placement
    c.place(U, 0, 0, 0)
    c.place(f"C{b+4}", -1.0, -3.6, 0)               # boot cap: pad1 BST (left), pad2 SW
    c.place(f"C{b+3}", -3.4, -4.6, 90)               # 100nF: pad1 VIN (bottom), pad2 GND (top)
    c.place(f"C{b+1}", -6.0, -4.3, 90)               # Cin
    c.place(f"C{b+2}", -9.2, -4.3, 90)
    c.place(f"D{b+1}", 0.0, -10.2, 180)              # cathode (SW) right, anode (GND) left
    c.place(L, 11.0, -5.5, 90)                       # pad1 SW bottom, pad2 VOUT top
    for j, x in enumerate([8.0, 10.4, 12.8, 15.2]):
        c.place(f"C{b+5+j}", x, -14.5, 90)           # pad1 VOUT bottom, pad2 GND top
    c.place(f"R{b+3}", -4.0, 4.4, 270)               # RT: pad1 RT top
    c.place(f"R{b+5}", -5.6, 4.4, 270)               # EN bottom: pad1 EN top
    c.place(f"R{b+4}", -7.2, 4.4, 90)                # EN top: pad1 VIN bottom, pad2 EN top
    c.place(f"JP{b+1}", -8.0, 8.6, 0)                # EN -> GND disable jumper
    c.place(f"R{b+2}", 4.0, 4.4, 270)                # FB bottom: pad1 FB top
    c.place(f"R{b+1}", 5.6, 4.4, 90)                 # FB top: pad2 FB top, pad1 VOUT bottom
    c.place(f"C{b+10}", 7.2, 4.4, 270)               # Chf: pad1 COMP top
    c.place(f"R{b+6}", 8.8, 4.4, 270)                # Rcomp: pad1 COMP top, pad2 CZ
    c.place(f"C{b+9}", 8.8, 7.4, 270)                # Cc: pad1 CZ top
    c.place(f"R{b+7}", 19.6, -2.0, 270)              # LED resistor: pad1 VOUT top
    c.place(f"D{b+2}", 19.6, 1.0, 90)                # LED: pad2 A top, pad1 GND bottom
    c.place(f"TP{b+1}", 17.6, -9.6, 0)
    c.place(f"TP{b+2}", 3.5, -15.3, 0)

    # --- power copper (top)
    c.rect("VIN", "F", -12, -4.0, -1.9, 0.0, prio=3)
    c.rect("GND", "F", -12, -14.2, -1.6, -4.6, prio=3)
    c.zone(pf + "SW", "F", [(-0.3, -4.0), (1.6, -4.0), (1.6, -16.6), (5.4, -16.6), (5.4, -3.0), (13.1, -3.0),
                           (13.1, 1.35), (8.9, 1.35), (8.9, -1.45), (1.6, -1.45), (1.6, -2.8), (-0.3, -2.8)], prio=4)
    c.zone(net, "F", [(6.0, -14.5), (18.0, -14.5), (18.0, -25.0), (21.5, -25.0), (21.5, -7.5), (6.0, -7.5)], prio=3)
    c.rect("GND", "F", 6.0, -25.0, 17.4, -14.9, prio=3)
    # --- explicit traces
    c.track(pf + "BST", [(-2.3, -1.91), (f"C{b+4}", "1")], 0.4)
    c.track("GND", [(2.3, -0.64), (0.6, -0.64)], 0.5)
    c.track(pf + "FB", [(3.2, 1.91), (4.0, 1.91), (f"R{b+2}", "1"), (f"R{b+1}", "2")])
    c.track(pf + "COMP", [(3.2, 0.64), (6.6, 0.64), (7.2, 1.24), (f"C{b+10}", "1"), (f"R{b+6}", "1")])
    c.track(pf + "CZ", [(f"R{b+6}", "2"), (f"C{b+9}", "1")])
    c.track(pf + "RT", [(-3.2, 1.91), (-4.0, 1.91), (f"R{b+3}", "1")])
    c.track(pf + "EN", [(-3.2, 0.64), (-5.0, 0.64), (-5.6, 1.24), (f"R{b+5}", "1"), (f"R{b+4}", "2")])
    c.track(pf + "EN", [(f"R{b+4}", "2"), (-8.9, 3.58), (-8.9, 7.4), (f"JP{b+1}", "1")])
    for ref, pad, (vx, vy) in [(f"R{b+2}", "2", (4.0, 6.4)), (f"C{b+10}", "2", (7.2, 6.4)),
                               (f"C{b+9}", "2", (8.8, 9.4)), (f"R{b+3}", "2", (-4.0, 6.4)),
                               (f"R{b+5}", "2", (-5.6, 6.4)), (f"JP{b+1}", "2", (-6.4, 8.6)),
                               (f"D{b+2}", "1", (19.6, 3.0))]:
        c.track("GND", [(ref, pad), (vx, vy)], 0.4)
        c.via("GND", vx, vy)
    c.track("VIN", [(f"R{b+4}", "1"), (-7.2, 6.4)], 0.4); c.via("VIN", -7.2, 6.4)
    # output sense: R_top -> via -> bottom layer -> output copper
    c.track(net, [(f"R{b+1}", "1"), (5.6, 6.4)], 0.3); c.via(net, 5.6, 6.4)
    c.track(net, [(5.6, 6.4), (6.4, 5.6), (14.5, 5.6), (16.0, 4.1), (16.0, -9.0)], 0.3, "B"); c.via(net, 16.0, -9.0)
    c.track(net, [(f"R{b+7}", "1"), (19.6, -8.0)], 0.4)
    c.track(f"D{b+2}_A", [(f"R{b+7}", "2"), (f"D{b+2}", "2")], 0.3)
    # --- vias
    c.vias("VIN", [-11.4], [-0.8, -2.2, -3.4]); c.vias("VIN", [-9.8], [-0.8]); c.vias("VIN", [-8.4, -6.8, -5.0], [-0.8])
    c.vias("GND", [-11.2, -9.8, -8.4, -7.0], [-7.2, -8.6, -10.0, -11.4, -12.8])
    c.vias("GND", [-5.6, -4.2, -2.8], [-12.6]); c.vias("GND", [-5.6], [-7.2, -8.6, -10.0, -11.4])
    c.vias("GND", frange(7.0, 16.0, 1.5), [-17.2, -18.7])
    if label:
        c.text(label, 6.0, 9.5, 1.2)
    return c


# ============================================================================ LM5146 cell
# Relative extents: x -10.5..25, y -29..40 (incl. output strip to the XT30 pins at y=36)
def thor_cell(B, ox, oy, rot=0):
    c = B.cell(ox, oy, rot)
    pl = c.place
    pl("Q2", -3.0, 0.0, 90)      # HS: drain (VIN) up, sources (SW) down, gate (-1.09, 2.9)
    pl("Q3", 3.0, 0.0, 270)      # LS: sources (GND) up, drain (SW) down, gate (1.09, -2.9)
    pl("C15", 0.0, -4.7, 0)      # 100nF: VIN left, GND right
    for ref, y in zip(["C10", "C11", "C12", "C13"], [-7.1, -10.3, -13.5, -16.7]):
        pl(ref, 0.0, y, 0)
    pl("C14", 0.0, -24.0, 0)     # bulk: VIN left, GND right
    pl("L1", 0.0, 13.5, 270)     # pad1 SW top, pad2 VOUT bottom
    for ref, x in zip(["C16", "C17", "C18", "C19"], [-3.6, 0.0, 3.6, 7.2]):
        pl(ref, x, 27.3, 270)    # pad1 VOUT top, pad2 GND bottom
    pl("C20", 17.5, 27.0, 270)   # pad1 VOUT top, pad2 GND bottom
    pl("U2", 14.0, 0.0, 180)
    pl("C22", 10.2, 1.6, 270)    # boot: pad1 BST top, pad2 SW bottom
    pl("C21", 10.2, -1.6, 90)    # VCC: pad1 VCC bottom, pad2 GND top
    pl("R13", 12.0, -4.1, 180)   # ILIM: pad1 ILIM right, pad2 SW left
    pl("R11", 13.25, 4.4, 270)   # EN top: pad1 VIN top
    pl("R12", 14.75, 6.6, 270)   # EN bottom: pad1 EN top
    pl("R10", 16.3, 4.5, 270)    # RT: pad1 top
    pl("C23", 17.8, 4.5, 270)    # SS: pad1 top
    pl("R15", 18.4, -0.9, 0)     # FB->GND: FB left
    pl("C25", 18.4, -2.5, 180)   # COMP-FB: FB left, COMP right
    pl("C24", 18.4, -4.1, 180)   # CZ-FB: FB left, CZ right
    pl("R16", 21.4, -4.1, 180)   # COMP-CZ: CZ left, COMP right
    pl("R14", 18.4, -5.7, 180)   # 24V-FB: FB left
    pl("C26", 18.4, -7.3, 180)   # C3-FB: FB left
    pl("R17", 21.4, -7.3, 180)   # 24V-C3: C3 left
    pl("JP1", 12.0, 8.4, 0)
    pl("R19", 15.0, 14.0, 0)
    pl("D3", 15.0, 16.0, 0)
    pl("TP3", -8.2, 3.0, 0)
    pl("TP4", 10.0, 22.0, 0)
    pl("TP5", 14.75, -4.4, 0)

    # --- power copper (top)
    c.rect("VIN", "F", -7.5, -26.0, -0.35, 1.0, prio=3)
    c.rect("GND", "F", 0.35, -26.0, 7.5, -2.2, prio=3)
    c.zone("T_SW", "F", [(-9.2, 1.6), (0.35, 1.6), (0.35, -1.6), (7.0, -1.6), (7.0, 7.6), (-9.2, 7.6)], prio=4)
    c.zone("+24V", "F", [(-10.5, 18.6), (23.0, 18.6), (23.0, 25.9), (-5.6, 25.9), (-5.6, 38.5), (-10.5, 38.5)], prio=3)
    c.rect("GND", "F", -5.2, 26.3, 23.0, 38.5, prio=3)

    # --- gate drive (layer B under the power stage, short)
    c.track("T_HO", [("Q2", "4"), (0.0, 2.1)], 0.4); c.via("T_HO", 0.0, 2.1)
    c.track("T_LO", [("Q3", "4"), (0.0, -1.0)], 0.4); c.via("T_LO", 0.0, -1.0)
    c.track("T_HO", [(0.0, 2.1), (0.6, 1.6), (9.0, 1.6)], 0.4, "B"); c.via("T_HO", 9.0, 1.6)
    c.track("T_LO", [(0.0, -1.0), (0.6, -1.6), (9.0, -1.6)], 0.4, "B"); c.via("T_LO", 9.0, -1.6)
    # IC fan-out (U2 rotated 180: drive pins on the left column x=12.35)
    c.track("T_HO", [(9.0, 1.6), (11.15, 1.6), (11.5, 1.25), (12.2, 1.25)], 0.25)
    c.track("T_LO", [(9.0, -1.6), (11.15, -1.6), (11.5, -1.25), (12.2, -1.25)], 0.25)
    c.track("T_BST", [(12.2, 0.75), ("C22", "1")], 0.25)
    c.track("T_SW", [(12.2, 1.75), (11.9, 2.38), ("C22", "2")], 0.25)
    c.track("T_SW", [("C22", "2"), (9.4, 3.3), (6.6, 3.3)], 0.5)
    c.track("T_VCC", [(12.2, -0.75), ("C21", "1")], 0.25)
    c.track("GND", [(12.2, -1.75), (11.9, -2.38), ("C21", "2")], 0.25)
    c.track("GND", [("C21", "2"), (9.2, -3.0)], 0.4); c.via("GND", 9.2, -3.0)
    c.track("GND", [(12.35, -0.25), (13.2, -0.25)], 0.25)            # pin 15 -> EP
    c.track("GND", [(15.65, -0.25), (14.8, -0.25)], 0.25)            # AGND -> EP
    c.track("GND", [(15.65, -1.25), (14.8, -1.25)], 0.25)            # SYNCIN -> GND (diode emulation)
    c.vias("GND", [13.5, 14.5], [-0.6, 0.6])                           # EP vias
    # current limit sense (Kelvin to the LS drain)
    c.track("T_ILIM", [(13.25, -2.45), (12.82, -3.0), ("R13", "1")], 0.25)
    c.track("T_SW", [("R13", "2"), (8.6, -4.1), (7.6, -1.4), (6.6, -1.4)], 0.3)
    c.track("T_PG", [(14.75, -2.45), ("TP5", "1")], 0.25)
    # VIN / EN
    c.track("VIN", [(13.25, 2.45), ("R11", "1")], 0.3)
    c.track("VIN", [("R11", "1"), (12.0, 3.58)], 0.3); c.via("VIN", 12.0, 3.58)
    c.track("T_EN", [(14.75, 2.45), ("R12", "1")], 0.25)
    c.track("T_EN", [("R11", "2"), (14.75, 5.22)], 0.25)
    c.track("T_EN", [("R11", "2"), (11.35, 5.22), ("JP1", "1")], 0.25)
    # RT / SS
    c.track("T_RT", [(15.8, 1.75), (16.3, 2.1), ("R10", "1")], 0.25)
    c.track("T_SS", [(15.8, 1.25), (16.9, 1.25), (17.8, 2.15), ("C23", "1")], 0.25)
    # FB / compensation
    c.track("T_FB", [(15.8, 0.25), (16.6, 0.25), (17.58, -0.73), ("R15", "1"), ("C26", "2")], 0.25)
    c.track("T_COMP", [(15.8, 0.75), (23.0, 0.75), (23.0, -4.1), ("R16", "1")], 0.25)
    c.track("T_COMP", [("C25", "1"), (23.0, -2.5)], 0.25)
    c.track("T_CZ", [("C24", "1"), ("R16", "2")], 0.25)
    c.track("T_C3", [("C26", "1"), ("R17", "2")], 0.25)
    c.track("+24V", [("R14", "1"), (22.4, -5.7), (22.4, -7.3), ("R17", "1")], 0.25)
    c.track("+24V", [(22.4, -7.3), (22.4, -8.4)], 0.25); c.via("+24V", 22.4, -8.4)
    c.track("+24V", [(22.4, -8.4), (24.5, -6.3), (24.5, 17.5), (22.0, 20.0)], 0.3, "B"); c.via("+24V", 22.0, 20.0)
    for ref, pad, (vx, vy) in [("R10", "2", (16.3, 6.4)), ("C23", "2", (17.8, 6.4)), ("R12", "2", (14.75, 8.6)),
                               ("R15", "2", (20.3, -0.9)), ("JP1", "2", (13.6, 9.6)), ("D3", "1", (14.21, 17.4))]:
        c.track("GND", [(ref, pad), (vx, vy)], 0.4)
        c.via("GND", vx, vy)
    c.track("+24V", [("R19", "1"), (13.0, 14.0), (13.0, 18.9)], 0.3)
    c.track("D3_A", [("R19", "2"), ("D3", "2")], 0.25)
    # --- stitching vias
    c.vias("VIN", [-3.0, -4.2, -5.4, -6.6], frange(-20.8, -4.0, 1.2))
    c.vias("GND", [3.0, 4.2, 5.4, 6.6], frange(-20.8, -4.0, 1.2))
    c.vias("GND", frange(-4.4, 22.0, 1.2), [30.0]); c.vias("GND", frange(-4.4, 12.0, 1.6), [33.0])
    c.text("24V THOR", 4.0, 10.0, 1.2)
    return c
