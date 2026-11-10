if __name__ == "__main__":
    raise SystemExit("Historical v0.3 alternate board; not supported by the v0.4 review build. See docs/HANDOFF.md.")
"""Cheapest check: one TPS54560 cell (12V / 5A) on a 50 x 50 mm 4-layer board.
Identical cell to the big board. Bench-supply wires in, XT30 out.
usage: python3 miniboard.py OUTDIR
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from blocks import Netlist, FP_XT30F, FP_HOLE
import cells
from cells import Board
import finish

OUT = sys.argv[1] if len(sys.argv) > 1 else "out_mini"
NAME = "pdb_mini"
W, H = 50.0, 50.0
NET = "+12V"

N = Netlist()
B_ = "A. Bench input"
N.P("J1", "Connector_Generic:Conn_01x02", "IN 27-33V (solder wires)", "Connector_Wire:SolderWire-1sqmm_1x02_P5.4mm_D1.4mm_OD2.7mm",
    {"1": "VIN", "2": "GND"}, B_, "", "solder pads for bench-supply wires", "", dnp=True)
N.CP("C1", "220uF 63V", "10x12.6", "VIN", "GND", B_)
N.tps_block(0, "H", NET, "B. 11.7V / 5A (TPS54560, same cell as the main board)", "10uH", "30k", "2.2k", "20k", "10k")
N.P("J101", "Connector_Generic:Conn_01x02", "12V OUT (XT30 female)", FP_XT30F,
    {"1": "GND", "2": NET}, "B. 12V", "C2913282", "Amass XT30PW-F", "verified")
for i in range(2):
    N.P(f"H{i+1}", "Mechanical:MountingHole", "M3", FP_HOLE, {}, "H. Mounting", "", "", "", dnp=True)
PARTS = N.parts

if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    B = Board(PARTS)
    cells.tps_cell(B, 0, NET, 12.5, 37.0)
    B.place("J101", 27.0, 15.0, 0)
    B.place("C1", 42.5, 22.0, 90)          # pad1 VIN bottom, pad2 GND top
    B.place("J1", 40.0, 42.0, 0)           # pin1 VIN (40,42), pin2 GND (45.4,42)
    B.place("H1", 5.0, 5.0); B.place("H2", 44.5, 5.0)
    B.zone("VIN", "F", [(36.0, 25.0), (49.3, 25.0), (49.3, 39.0), (42.4, 39.0), (42.4, 45.5), (36.0, 45.5)], prio=3)
    for x in [37.0, 38.5, 40.0]:
        for y in [29.0, 31.0, 33.0, 35.0]:
            B.via("VIN", x, y)
    for x in [38.5, 40.0, 41.5, 46.5]:
        B.via("GND", x, 14.8)
    m = 0.5
    B.zone("GND", "In1", [(m, m), (W - m, m), (W - m, H - m), (m, H - m)], prio=0)
    B.zone("VIN", "In2", [(m, m), (W - m, m), (W - m, H - m), (m, H - m)], prio=0, thermal=True)
    B.text("+ IN 27-33V -", 42.5, 47.6, 0.9)
    B.text("12V", 34.0, 18.8, 1.2)
    B.text("PDB MINI v0.2", 42.5, 10.5, 1.0)
    B.outline(W, H, 2.0)
    pcbnew.SaveBoard(f"{OUT}/{NAME}_placed.kicad_pcb", B.b)
    finish.route(B, OUT, NAME, passes=10)
    pcb, rep = finish.finish(B, OUT, NAME, W, H)
    print(finish.drc_summary(rep))
    finish.render(pcb, f"{OUT}/top.png", "F.Cu,F.SilkS,Edge.Cuts", 20)
