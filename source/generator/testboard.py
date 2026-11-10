if __name__ == "__main__":
    raise SystemExit("Historical v0.3 alternate board; not supported by the v0.4 review build. See docs/HANDOFF.md.")
"""Small test board: input protection + 24V LM5146 cell + one TPS54560 cell (5V).
Same cells as the big board. 100 x 82 mm, 4 layers.
usage: python3 testboard.py OUTDIR [--noroute]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from blocks import Netlist, RAILS, FP_XT30F, FP_HOLE
import cells
from cells import Board
import finish

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
NAME = "pdb_test"
W, H = 100.0, 82.0

N = Netlist()
N.input_block(motor=False, bulk=1)
N.thor_block(out_conn=True)
k, net, title, lval, rtop, rbot, rcomp, rled = RAILS[0]
N.tps_block(0, k, net, "C. 5V / 5A test rail (TPS54560; 12V option: see notes)", lval, rtop, rbot, rcomp, rled)
N.P("J101", "Connector_Generic:Conn_01x02", "5V OUT (XT30 female)", FP_XT30F,
    {"1": "GND", "2": net}, "C. 5V", "C2913282", "Amass XT30PW-F", "verified")
for i in range(4):
    N.P(f"H{i+1}", "Mechanical:MountingHole", "M3", FP_HOLE, {}, "H. Mounting", "", "", "", dnp=True)
PARTS = N.parts

if __name__ == "__main__":
    B = Board(PARTS)
    # ---------------- input block (bottom-left)
    B.place("J1", 17.5, 74.5, 90)          # pin2 VBAT (17.5,67.3), pin1 GND (17.5,74.5); mating face at x=0
    B.place("F2", 8.5, 45.5, 270)          # pad1 VBAT_L cluster y45.5-49, pad2 VBAT cluster y54.8-58.3
    B.place("Q1", 14.0, 36.6, 0)           # sources (VBAT_L) left, drain (VIN) right
    B.place("U1", 16.5, 45.0, 0)
    B.place("C2", 16.5, 47.6, 0)
    B.place("C1", 12.6, 46.0, 0)           # straddles the VBAT_L zone edge
    B.place("D1", 22.5, 47.5, 90)          # TVS: pad1 VBAT_L bottom, pad2 GND top
    B.place("C3", 7.0, 14.0, 90)           # bulk: pad1 VIN bottom, pad2 GND top
    B.place("C5", 13.5, 42.2, 270)         # straddles the VIN zone edge
    B.place("R1", 27.0, 42.4, 270); B.place("D2", 27.0, 45.5, 90)
    B.place("TP1", 25.5, 38.5); B.place("TP2", 27.5, 50.5)
    vbat = [(3.0, 52.8), (22.0, 52.8), (22.0, 70.0), (3.0, 70.0)]
    vbl = [(2.0, 32.6), (11.9, 32.6), (11.9, 48.6), (25.0, 48.6), (25.0, 52.0), (2.0, 52.0)]
    for L in ("F", "B"):
        B.zone("VBAT", L, vbat, prio=5, clearance=0.5)
        B.zone("VBAT_L", L, vbl, prio=5, clearance=0.4)
    B.zone("VIN", "F", [(2, 17.0), (30.6, 17.0), (30.6, 31.8), (28.0, 31.8), (28.0, 41.5), (12.5, 41.5),
                        (12.5, 32.0), (2, 32.0)], prio=3)
    for x in [3.0, 4.5]:
        for y in [34.0, 36.0, 38.0, 40.0, 42.0, 44.0, 46.0, 48.0, 50.0]:
            B.via("VBAT_L", x, y)
    for x in [10.5]:
        for y in [34.0, 40.5, 42.5]:
            B.via("VBAT_L", x, y)
    for x in cells.frange(14.0, 27.0, 1.5):
        for y in [19.0, 21.0, 23.0, 25.0, 27.0, 29.0]:
            B.via("VIN", x, y)
    for y in [33.5, 35.0, 36.5, 38.0, 39.5]:
        B.via("VIN", 18.5, y)

    # ---------------- 24V cell (middle) and its XT30 on the bottom edge
    cells.thor_cell(B, 38.0, 31.0)
    B.place("J3", 35.5, 67.0, 180)         # pin1 GND (35.5,67), pin2 +24V (30.5,67); mating face down

    # ---------------- 5V cell (right) and its XT30 on the top edge
    cells.tps_cell(B, 0, net, 75.5, 37.0, label="5V TEST RAIL")
    B.place("J101", 90.0, 15.0, 0)         # pin1 GND (90,15), pin2 5V (95,15); mating face up

    for i, (x, y) in enumerate([(3.5, 3.5), (61.5, 3.5), (55.0, 78.5), (96.5, 78.5)]):
        B.place(f"H{i+1}", x, y)

    # ---------------- inner planes
    m = 0.5
    B.zone("GND", "In1", [(m, m), (W - m, m), (W - m, H - m), (m, H - m)], prio=0)
    B.zone("VIN", "In2", [(m, m), (W - m, m), (W - m, H - m), (m, H - m)], prio=0, thermal=True)

    # ---------------- silkscreen
    B.text("BATTERY 27-33V", 10.5, 79.8, 1.3)
    B.text("24V THOR", 33.0, 63.0, 1.3)
    B.text("5V", 92.5, 18.6, 1.3)
    B.text("ROBOT PDB TEST v0.2", 78.0, 60.0, 1.5)
    B.text("LM5146 24V + TPS54560 5V", 78.0, 63.0, 1.0)
    B.text("Bridge JP to switch a rail off", 78.0, 65.5, 0.9)
    B.outline(W, H)

    pcbnew.SaveBoard(f"{OUT}/{NAME}_placed.kicad_pcb", B.b)
    if "--noroute" in sys.argv:
        pcb, rep = finish.finish(B, OUT, NAME, W, H)
    else:
        finish.route(B, OUT, NAME, passes=int(os.environ.get("PASSES", "16")), skip_nets=("VBAT",))
        pcb, rep = finish.finish(B, OUT, NAME, W, H)
    print(finish.drc_summary(rep))
    finish.render(pcb, f"{OUT}/top.png", "F.Cu,F.SilkS,Edge.Cuts", 12)
    finish.render(pcb, f"{OUT}/bottom.png", "B.Cu,Edge.Cuts", 12)
