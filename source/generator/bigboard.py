"""Robot PDB v0.4 part definitions: battery input with fused motor pass-through (30A) and fused logic (20A), 24V Thor, 5 TPS54560 rails, one USB -> hub -> USB audio + amp
and 2 Dynamixel buses. 228 x 108 mm, 4 layers.
usage: python3 bigboard.py OUTDIR [--noroute]
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pcbnew
from blocks import Netlist, RAILS, FP_XT30F, FP_EH3, FP_HOLE
import cells
from cells import Board
import finish

OUT = sys.argv[1] if len(sys.argv) > 1 else "out_big"
NAME = "robot_pdb"
W, H = 228.0, 108.0

N = Netlist()
N.input_block(motor=True, bulk=2)
N.thor_block(out_conn=True)
LABEL = {"P": "RASPBERRY PI 5V", "O": "OAK-D 5V", "A": "12V AUX (amp is on board)"}
for n, (k, net, title, lval, rtop, rbot, rcomp, rled) in enumerate(RAILS):
    b = N.tps_block(n, k, net, title, lval, rtop, rbot, rcomp, rled)
    if k in LABEL:
        N.P(f"J{b+1}", "Connector_Generic:Conn_01x02", f"{LABEL[k]} (XT30 female)", FP_XT30F,
            {"1": "GND", "2": net}, title, "C2913282", "Amass XT30PW-F", "verified")
    else:
        data = "DXL330_DATA" if k == "S" else "DXL430_DATA"
        N.CP(f"C{b+11}", "470uF 25V", "10x10", net, "GND", title)
        for j in range(4 if k == "S" else 3):
            N.P(f"J{b+1+j}", "Connector_Generic:Conn_01x03", f"DXL PORT {j+1} (GND/VDD/DATA)", FP_EH3,
                {"1": "GND", "2": net, "3": data}, title, "C160259", "JST B3B-EH-A", "verified")
N.usb_block()
N.audio_block()
N.dxl_block()
for i in range(7):
    N.P(f"H{i+1}", "Mechanical:MountingHole", "M3", FP_HOLE, {}, "H. Mounting", "", "", "", dnp=True)
PARTS = N.parts

TOP = {"P": 83.5, "O": 117.5, "A": 151.5}       # TPS cells along the top edge (XT30 up)
BOT = {"S": 93.0, "H": 127.5}                  # servo cells, rotated 180 (outputs down)
JST_X = {"S": [69.0, 80.3, 91.6, 102.9], "H": [114.0, 125.3, 136.6]}
JST_Y = 103.0

if __name__ == "__main__":
    raise SystemExit("v0.4: use build_review.py BASELINE_PCB OUTPUT_DIR; see docs/HANDOFF.md")
