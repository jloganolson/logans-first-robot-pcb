"""BOM (JLCPCB format + annotated), CPL, gerbers/drill zip, renders."""
import sys, os, csv, subprocess, zipfile, glob
from collections import OrderedDict
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
PARTS = importlib.import_module(os.environ.get("CIRCUIT", "bigboard")).PARTS
PROJ = os.environ.get("PROJ", "robot_pdb")

OUT = sys.argv[1]
PCB = f"{OUT}/{PROJ}.kicad_pcb"
FAB = f"{OUT}/jlcpcb"
os.makedirs(FAB, exist_ok=True)

# ---------------- BOM
groups = OrderedDict()
for p in PARTS:
    if p["dnp"]:
        continue
    key = (p["value"], p["fp"], p["lcsc"], p["mpn"])
    groups.setdefault(key, []).append(p)

def refkey(r):
    import re
    m = re.match(r"([A-Z]+)(\d+)", r)
    return (m.group(1), int(m.group(2)))

with open(f"{FAB}/BOM_JLCPCB.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for (val, fp, lcsc, mpn), ps in groups.items():
        refs = sorted((p["ref"] for p in ps), key=refkey)
        w.writerow([val, ",".join(refs), fp.split(":")[1], lcsc])

STATUS_TXT = {"verified": "Legacy supplier identity; not requalified for release", "basic": "JLC basic part (confirm)",
              "confirm": "Pick/confirm LCSC # at order", "": "No part (copper only)"}
with open(f"{OUT}/BOM_annotated.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Qty", "Designators", "Value", "Part / description", "Footprint", "LCSC #", "Status", "Block"])
    for (val, fp, lcsc, mpn), ps in groups.items():
        refs = sorted((p["ref"] for p in ps), key=refkey)
        w.writerow([len(ps), " ".join(refs), val, mpn, fp.split(":")[1], lcsc, STATUS_TXT[ps[0]["status"]],
                    ps[0]["block"].split(".")[0]])
print("BOM lines", len(groups), "parts", sum(len(v) for v in groups.values()))

# ---------------- CPL (JLC column names)
pos = f"{OUT}/pos.csv"
subprocess.run(["kicad-cli", "pcb", "export", "pos", "--format", "csv", "--units", "mm", "--side", "both",
                "-o", pos, PCB], check=True, capture_output=True)
dnp = {p["ref"] for p in PARTS if p["dnp"]}
with open(pos) as fi, open(f"{FAB}/CPL_JLCPCB.csv", "w", newline="") as fo:
    r = csv.DictReader(fi)
    w = csv.writer(fo)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for row in r:
        if row["Ref"] in dnp:
            continue
        w.writerow([row["Ref"], row["PosX"] + "mm", row["PosY"] + "mm",
                    "Top" if row["Side"] == "top" else "Bottom", row["Rot"]])
os.remove(pos)

# ---------------- CPL with community rotation fixes (review copy; JLC's assembly preview decides)
# Patterns/rotations from matthewlai/JLCKicadTools cpl_rotations_db.csv (also used by Bouni/kicad-jlcpcb-tools).
import re
ROTFIX = [(r"^SOT-23", -90), (r"^LQFP-", 270), (r"^HTSSOP-", 270), (r"^VSSOP-8_", 180), (r"^TDSON-8-1", 270),
          (r"^CP_Elec_10x10", 180), (r"^(.*?_|V)?QFN-(16|20|24|28|40)(-|_|$)", 270),
          (r"^USB_C_Receptacle_HRO_TYPE-C-31-M-12", 180)]
# Per-designator overrides from JLC's preview check 2026-11-06; these win over the patterns.
ROTFIX_REF = {"J10": 0, "U14": 0, "J1": 90}
fpname = {p["ref"]: p["fp"].split(":")[1] for p in PARTS}
with open(f"{FAB}/CPL_JLCPCB.csv") as fi, open(f"{FAB}/CPL_JLCPCB_rotfix.csv", "w", newline="") as fo, open(f"{OUT}/rotation_fixes.csv", "w", newline="") as fl:
    rd, w, wl = csv.DictReader(fi), csv.writer(fo), csv.writer(fl)
    w.writerow(rd.fieldnames); wl.writerow(["Designator", "Footprint", "KiCad rotation", "Added", "Rotation in rotfix CPL"])
    for row in rd:
        f = fpname.get(row["Designator"], "")
        ref = row["Designator"]
        add = ROTFIX_REF[ref] if ref in ROTFIX_REF else next((d for pat, d in ROTFIX if re.match(pat, f)), 0)
        if add or ref in ROTFIX_REF:
            new = (float(row["Rotation"]) + add) % 360
            wl.writerow([row["Designator"], f, row["Rotation"], add, f"{new:.6f}"])
            row["Rotation"] = f"{new:.6f}"
        w.writerow([row[k] for k in rd.fieldnames])

# ---------------- gerbers + drill
g = f"{OUT}/gerbers"
os.makedirs(g, exist_ok=True)
layers = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts"
subprocess.run(["kicad-cli", "pcb", "export", "gerbers", "--layers", layers, "--subtract-soldermask",
                "-o", g + "/", PCB], check=True, capture_output=True)
subprocess.run(["kicad-cli", "pcb", "export", "drill", "--format", "excellon", "--excellon-separate-th",
                "--generate-map", "--map-format", "gerberx2", "-o", g + "/", PCB], check=True, capture_output=True)
with zipfile.ZipFile(f"{FAB}/gerbers_{PROJ}.zip", "w", zipfile.ZIP_DEFLATED) as z:
    for fn in sorted(glob.glob(g + "/*")):
        z.write(fn, os.path.basename(fn))
print("gerber files", len(glob.glob(g + "/*")))
