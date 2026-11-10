raise SystemExit("Historical v0.3 coordinate patch; do not apply to v0.4. Use build_review.py.")
"""Finish the main board after Freerouting: hand-finish the few open nets, stitch GND pads, refill, DRC.
usage: python3 postfix.py OUTDIR
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from fixer import Fixer, T, MM
import finish

OUT = sys.argv[1]
NAME = "robot_pdb"
b = pcbnew.LoadBoard(f"{OUT}/{NAME}_prefill.kicad_pcb")
F = Fixer(b)

# 1) drop dangling vias / stubs the router left on open nets
for t in list(b.GetTracks()):
    if t.GetClass() == "PCB_VIA" and t.GetNetname() in ("AMP_BSPR", "P2_DM"):
        tracks = [u for u in b.GetTracks() if u.GetClass() != "PCB_VIA" and u.GetNetname() == t.GetNetname()
                  and (u.GetStart() == t.GetPosition() or u.GetEnd() == t.GetPosition())]
        if len(tracks) <= 1:
            for u in tracks:
                b.Remove(u)
            b.Remove(t)

# 2) EP stitching vias (QFN hub + serial chip)
for ref in ("U10", "U14"):
    ep = F.pad(ref, "25")
    c = ep.GetPosition()
    for dx in (-0.65, 0.65):
        for dy in (-0.65, 0.65):
            if F.via_ok("GND", T(c.x) + dx, T(c.y) + dy):
                F.add_via("GND", T(c.x) + dx, T(c.y) + dy)
            else:
                print("EP via blocked", ref, dx, dy)

# PSELF (U10.18) left open: internal pull-up = self-powered hub
F.pad("U10", "18").SetNetCode(0)

# 2b) amp bootstrap caps: the autorouter boxed in two of them, so lay these by hand
def seg_is(t, a, z, tol=0.02):
    s, e = (T(t.GetStart().x), T(t.GetStart().y)), (T(t.GetEnd().x), T(t.GetEnd().y))
    close = lambda p, q: abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol
    return (close(s, a) and close(e, z)) or (close(s, z) and close(e, a))

trk = [t for t in b.GetTracks() if t.GetClass() != "PCB_VIA"]
for t in trk:
    if t.GetNetname() == "AMP_OUTPR" and (seg_is(t, (193.65, 22.57), (193.65, 23.03)) or
                                          seg_is(t, (196.1, 20.12), (193.65, 22.57)) or
                                          seg_is(t, (196.1, 18.1), (196.1, 20.12)) or
                                          seg_is(t, (193.65, 23.03), (193.6, 23.07), 0.03)):
        b.Remove(t)
    elif t.GetNetname() == "AMP_OUTPR" and seg_is(t, (204.75, 9.45), (196.1, 18.1)):
        t.SetStart(pcbnew.VECTOR2I(MM(204.75), MM(9.45))); t.SetEnd(pcbnew.VECTOR2I(MM(197.4), MM(16.8)))
c92 = b.FindFootprintByReference("C92")
c92.SetOrientationDegrees(270)              # pad1 (BS) up, pad2 (OUT) down
F.add_track("AMP_OUTPR", [(193.6, 23.07), (194.2, 23.075), (195.6, 21.675), (196.1, 21.68),
                          (197.4, 21.68), (197.4, 16.8)], 0.4, pcbnew.F_Cu)
F.add_track("AMP_BSPR", [(192.65, 22.425), (193.5, 22.425), (195.8, 20.125), (196.1, 20.12)], 0.3, pcbnew.F_Cu)
# BSNL: pin 20 -> via -> B.Cu -> the via already under C89
F.add_track("AMP_BSNL", [(192.65, 28.925), (193.6, 28.925), (194.1, 29.425), (194.1, 29.95)], 0.3, pcbnew.F_Cu)
F.add_via("AMP_BSNL", 194.1, 29.95)
F.add_track("AMP_BSNL", [(194.1, 29.95), (196.3, 32.15), (198.6, 32.16)], 0.3, pcbnew.B_Cu)

# U12 pin 33 (AVSS): stub out to the GND track running along C70-C77
x, y = (T(F.pad("U12", "33").GetPosition().x), T(F.pad("U12", "33").GetPosition().y))
F.add_track("GND", [(x, y), (185.78, y)], 0.25, pcbnew.F_Cu)

# 3) open signal connections (pad pairs), found from the last DRC report
import shutil
if not os.path.exists(f"{OUT}/drc_route.rpt"):
    shutil.copy(f"{OUT}/drc.rpt", f"{OUT}/drc_route.rpt")
rep = open(f"{OUT}/drc_route.rpt").read()
pairs = re.findall(r"Pad (\w+) \[([^\]]+)\] of (\w+) on F\.Cu\s+@\([\d. m,]+\):\s+Pad (\w+) \[[^\]]+\] of (\w+)", rep)
done = set()
for n1, net, r1, n2, r2 in pairs:
    if net == "GND" or (net, r1, n1, r2, n2) in done:
        continue
    done.add((net, r1, n1, r2, n2))
    a, z = F.pad(r1, n1).GetPosition(), F.pad(r2, n2).GetPosition()
    ok = F.route(net, (T(a.x), T(a.y)), (T(z.x), T(z.y)), w=0.4 if net.startswith("AMP_") else 0.25)
    print("route", net, r1, n1, "->", r2, n2, ok)
for net, (r1, n1), (r2, n2) in (("P2_DM", ("U10", "9"), ("U14", "4")),
                                 ("A_AVDD", ("U12", "34"), ("U12", "29"))):
    a, z = F.pad(r1, n1).GetPosition(), F.pad(r2, n2).GetPosition()
    # skip if already joined by copper (cheap check: any track of the net ends on both pads)
    ends = [(u.GetStart(), u.GetEnd()) for u in b.GetTracks() if u.GetNetname() == net and u.GetClass() != "PCB_VIA"]
    hit = lambda p: any(F.pad(*rp).HitTest(s) or F.pad(*rp).HitTest(e) for s, e in ends for rp in [p])
    print(net, "pad ends touched:", hit((r1, n1)), hit((r2, n2)))

# 4) stitch every GND pad in the new USB/audio section that has no GND copper on it yet
NEW = re.compile(r"^(U1[0-6]|C(6\d|7\d|8\d|9\d)|R(6\d|7\d)|Y1|J1[0-4]|D60|FB\d)$")
gtr = [u for u in b.GetTracks() if u.GetNetname() == "GND"]
added = failed = 0
for fp in b.GetFootprints():
    if not NEW.match(fp.GetReference()):
        continue
    for p in fp.Pads():
        if p.GetNetname() != "GND" or p.GetNumber() in ("25", "33") or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        touched = any(p.HitTest(u.GetPosition() if u.GetClass() == "PCB_VIA" else u.GetStart()) or
                      (u.GetClass() != "PCB_VIA" and p.HitTest(u.GetEnd())) for u in gtr)
        if touched:
            continue
        if F.gnd_via(p):
            added += 1
        else:
            failed += 1
            print("no GND via for", fp.GetReference(), p.GetNumber())
print("gnd stitches", added, "failed", failed)

tmp = f"{OUT}/{NAME}_prefill2.kicad_pcb"
for t_ in list(b.GetTracks()):
    if t_.GetClass() == "PCB_TRACK" and t_.GetLength() < pcbnew.FromMM(0.01):
        b.Remove(t_)
for z in b.Zones():
    if z.GetNetname() == "GND" and z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
pcbnew.SaveBoard(tmp, b)
board = pcbnew.LoadBoard(tmp)
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
# any F/B ground-pour fragment with no via or through-hole pad in it gets a stitching via
F2 = Fixer(board)
stitched = 0
for z in board.Zones():
    if z.GetNetname() != "GND" or z.GetLayer() not in (pcbnew.F_Cu, pcbnew.B_Cu):
        continue
    polys = z.GetFilledPolysList(z.GetLayer())
    holes = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
    holes += [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads()
              if p.GetNetname() == "GND" and p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH]
    for k in range(polys.OutlineCount()):
        out = polys.Outline(k)
        if any(polys.Contains(h, k) for h in holes):
            continue
        bb = out.BBox()
        x0, y0, x1, y1 = T(bb.GetLeft()), T(bb.GetTop()), T(bb.GetRight()), T(bb.GetBottom())
        if (x1 - x0) * (y1 - y0) > 400:
            print("big fragment without via?", round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
            continue
        done = False
        yy = y0 + 0.4
        while yy < y1 and not done:
            xx = x0 + 0.4
            while xx < x1 and not done:
                pt = pcbnew.VECTOR2I(MM(xx), MM(yy))
                if polys.Contains(pt, k) and out.PointInside(pt, MM(0.45)) is not None and F2.via_ok("GND", xx, yy):
                    # keep the via fully inside the fragment
                    if all(polys.Contains(pcbnew.VECTOR2I(MM(xx + dx), MM(yy + dy)), k)
                           for dx, dy in ((0.35, 0), (-0.35, 0), (0, 0.35), (0, -0.35))):
                        F2.add_via("GND", xx, yy); done = True; stitched += 1
                xx += 0.2
            yy += 0.2
        if not done:
            print("fragment without via spot", round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1))
print("fragment stitches", stitched)
if stitched:
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
pcb = f"{OUT}/{NAME}.kicad_pcb"
pcbnew.SaveBoard(pcb, board)
rpt = f"{OUT}/drc.rpt"
pcbnew.WriteDRCReport(board, rpt, pcbnew.EDA_UNITS_MILLIMETRES, True)
print(re.findall(r"\*\* Found \d+ [^\n]*", open(rpt).read()))
print(finish.drc_summary(rpt))
