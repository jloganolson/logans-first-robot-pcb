"""Generate a KiCad 7 schematic (.kicad_sch) + project-local symbol library from circuit.py."""
import re, uuid, sys, os, math
from collections import OrderedDict, defaultdict
sys.path.insert(0, os.path.dirname(__file__))
import importlib
circuit = importlib.import_module(os.environ.get("CIRCUIT", "bigboard"))
PARTS = circuit.PARTS
revision = getattr(circuit, "REVISION", "0.4-review")

OUT = sys.argv[1]
os.makedirs(OUT, exist_ok=True)
PROJ = os.environ.get("PROJ", "robot_pdb")
SYMDIR = os.environ.get("KICAD7_SYMBOL_DIR", "/usr/share/kicad/symbols")
U = lambda: str(uuid.uuid4())


# ------------------------------------------------------------ s-expr helpers
def extract_symbol(lib, name):
    txt = open(f"{SYMDIR}/{lib}.kicad_sym").read()
    i = txt.index(f'\n  (symbol "{name}"')
    depth, j = 0, i + 1
    while True:
        ch = txt[j]
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    block = txt[i + 1:j + 1]
    inherited = re.search(r'\(extends "([^"]+)"\)', block)
    if inherited:
        # KiCad derived symbols reuse their parent's graphics and pin geometry.
        # Instance properties below come from the circuit inventory, so resolve
        # the parent before embedding a self-contained library symbol.
        parent = inherited.group(1)
        block = extract_symbol(lib, parent)
        block = block.replace(f'"{lib}:{parent}"', f'"{lib}:{name}"', 1)
        block = block.replace(f'(symbol "{parent}_', f'(symbol "{name}_')
        return block
    return block.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)


PIN_RE = re.compile(r'\(pin \w+ \w+ \(at ([-\d.]+) ([-\d.]+) (\d+)\) \(length ([\d.]+)\).*?\(number "([^"]+)"', re.S)


def pins_of(block):
    return {m.group(5): (float(m.group(1)), float(m.group(2)), int(m.group(3)))
            for m in PIN_RE.finditer(block)}


# ------------------------------------------------------------ custom symbols
def ic_symbol(name, left, right, width=20.32, ref="U"):
    """left/right: list of (number, name). Pins passive to keep ERC simple."""
    n = max(len(left), len(right))
    h = (n + 1) * 2.54
    top = h / 2
    lines = [f'  (symbol "pdb:{name}" (pin_names (offset 1.016)) (in_bom yes) (on_board yes)',
             f'    (property "Reference" "{ref}" (at 0 {top+1.27:.2f} 0) (effects (font (size 1.27 1.27))))',
             f'    (property "Value" "{name}" (at 0 {-top-1.27:.2f} 0) (effects (font (size 1.27 1.27))))',
             f'    (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
             f'    (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) hide))',
             f'    (symbol "{name}_0_1"',
             f'      (rectangle (start {-width/2:.2f} {top:.2f}) (end {width/2:.2f} {-top:.2f}) (stroke (width 0.254) (type default)) (fill (type background)))',
             '    )', f'    (symbol "{name}_1_1"']
    for side, lst in (("L", left), ("R", right)):
        for k, (num, pname) in enumerate(lst):
            y = top - 2.54 * (k + 1)
            x = -width / 2 - 5.08 if side == "L" else width / 2 + 5.08
            ang = 0 if side == "L" else 180
            if pname is None:
                continue
            lines.append(f'      (pin passive line (at {x:.2f} {y:.2f} {ang}) (length 5.08) '
                         f'(name "{pname}" (effects (font (size 1.27 1.27)))) '
                         f'(number "{num}" (effects (font (size 1.27 1.27)))))')
    lines += ['    )', '  )']
    return "\n".join(lines)


CUSTOM = {
    "TPS22918": ic_symbol("TPS22918", [("1", "VIN"), ("3", "ON"), ("2", "GND")], [("6", "VOUT"), ("4", "CT"), ("5", "QOD")]),
    "AP2112K": ic_symbol("AP2112K", [("1", "VIN"), ("3", "EN"), ("2", "GND")], [("5", "VOUT"), ("4", "NC")]),
    "TPS54560": ic_symbol("TPS54560", [("2", "VIN"), ("3", "EN"), ("4", "RT/CLK"), ("7", "GND"), ("9", "PAD")],
                          [("1", "BOOT"), ("8", "SW"), ("5", "FB"), ("6", "COMP")]),
    "LM5146": ic_symbol("LM5146", [("20", "VIN"), ("1", "EN/UVLO"), ("2", "RT"), ("3", "SS/TRK"), ("8", "SYNCIN"),
                                   ("7", "SYNCOUT"), ("6", "AGND"), ("12", "PGND"), ("15", "EP15"), ("21", "PAD"),
                                   ("9", "NC"), ("16", "NC")],
                        [("17", "BST"), ("18", "HO"), ("19", "SW"), ("13", "LO"), ("11", "ILIM"), ("14", "VCC"),
                         ("10", "PGOOD"), ("5", "FB"), ("4", "COMP")], width=22.86),
    "LM74700": ic_symbol("LM74700", [("6", "ANODE"), ("3", "EN"), ("2", "GND")],
                         [("4", "CATHODE"), ("5", "GATE"), ("1", "VCAP")]),
    "NMOS_TDSON8": ic_symbol("NMOS_TDSON8", [("4", "G")], [("5", "D"), ("1", "S"), ("2", "S"), ("3", "S")],
                             width=10.16, ref="Q"),
    "USB_C_USB2": ic_symbol("USB_C_USB2", [("A4", "VBUS"), ("A9", "VBUS"), ("B4", "VBUS"), ("B9", "VBUS"),
                                           ("A5", "CC1"), ("B5", "CC2"), ("S1", "SHIELD")],
                            [("A6", "D+"), ("B6", "D+"), ("A7", "D-"), ("B7", "D-"), ("A1", "GND"), ("A12", "GND"),
                             ("B1", "GND"), ("B12", "GND"), ("A8", "SBU1"), ("B8", "SBU2")], ref="J"),
    "USBLC6": ic_symbol("USBLC6", [("1", "IO1"), ("3", "IO2"), ("2", "GND")], [("6", "IO1"), ("4", "IO2"), ("5", "VBUS")]),
    "XTAL4": ic_symbol("XTAL4", [("1", "X1"), ("2", "GND")], [("3", "X2"), ("4", "GND")], width=10.16, ref="Y"),
    "CH334F": ic_symbol("CH334F", [("15", "DPU"), ("14", "DMU"), ("19", "V5"), ("20", "VDD33"), ("4", "XI"), ("3", "XO"),
                                   ("1", "OVCUR#"), ("16", "RESET#"), ("18", "PSELF"), ("25", "GND"),
                                   ("2", "NC"), ("17", "NC")],
                        [("12", "DP1"), ("11", "DM1"), ("10", "DP2"), ("9", "DM2"), ("8", "DP3"), ("7", "DM3"),
                         ("6", "DP4"), ("5", "DM4"), ("22", "LED1"), ("23", "LED2"), ("13", "LED3/SCL"),
                         ("21", "LED4/SDA"), ("24", "PWREN#")], width=22.86),
    "CH342F": ic_symbol("CH342F", [("3", "UD+"), ("4", "UD-"), ("7", "VDD5"), ("5", "VIO"), ("6", "V3"), ("8", "VBUS"),
                                   ("9", "RST#"), ("2", "GND"), ("25", "EP")],
                        [("21", "TXD0"), ("20", "RXD0"), ("23", "DTR0/TNOW0"), ("19", "RTS0"), ("18", "CTS0"),
                         ("22", "DSR0"), ("24", "DCD0"), ("1", "RI0"), ("13", "TXD1"), ("12", "RXD1"),
                         ("15", "DTR1/TNOW1"), ("11", "RTS1"), ("10", "CTS1"), ("14", "DSR1"), ("16", "DCD1"),
                         ("17", "RI1")], width=25.4),
    "CM108B": ic_symbol("CM108B", [("41", "USBDP"), ("42", "USBDM"), ("35", "DVDD"), ("29", "AVDD"), ("34", "AVDD"),
                                   ("8", "DREG18"), ("9", "DREG33"), ("37", "AREG36"), ("26", "VREF"), ("10", "MODE"),
                                   ("7", "PWRSEL"), ("23", "TEST"), ("22", "ADSEL"), ("14", "DVSS"), ("36", "DVSS"),
                                   ("24", "AVSS"), ("33", "AVSS")]
                        + [(str(n), nm) for n, nm in ((1, "SPDIFO"), (2, "DR"), (3, "DW"), (4, "SK"), (5, "CS"))],
                        [("30", "LOL"), ("32", "LOR"), ("31", "LOBS"), ("27", "MICIN"), ("25", "VBIAS"),
                         ("6", "MUTER"), ("18", "MUTEP"), ("39", "VOLUP"), ("48", "VOLDN"), ("12", "LEDO"),
                         ("21", "LEDR"), ("40", "PDSW"), ("38", "MSEL"), ("13", "GPIO3"), ("15", "GPIO4"),
                         ("43", "GPIO1"), ("16", "SDIN"), ("17", "ADSCLK"), ("19", "ADLRCK"), ("20", "ADMCLK"),
                         ("44", "SDOUT"), ("45", "DAMCLK"), ("46", "DALRCK"), ("47", "DASCLK"), ("11", "NC"),
                         ("28", "NC")], width=25.4),
    "TPA3118D2": ic_symbol("TPA3118D2", [("4", "RINP"), ("5", "RINN"), ("10", "LINP"), ("11", "LINN"), ("2", "SDZ"),
                                         ("3", "FAULTZ"), ("12", "MUTE"), ("8", "GAIN/SLV"), ("6", "PLIMIT"),
                                         ("7", "GVDD"), ("1", "MODSEL"), ("13", "AM2"), ("14", "AM1"), ("15", "AM0"),
                                         ("16", "SYNC"), ("9", "GND"), ("33", "PAD")],
                           [("17", "AVCC"), ("18", "PVCC"), ("19", "PVCC"), ("31", "PVCC"), ("32", "PVCC"),
                            ("29", "OUTPR"), ("30", "BSPR"), ("27", "OUTNR"), ("26", "BSNR"), ("23", "OUTPL"),
                            ("24", "BSPL"), ("21", "OUTNL"), ("20", "BSNL"), ("22", "GND"), ("25", "GND"),
                            ("28", "GND")], width=25.4),
    "74LVC2G241": ic_symbol("74LVC2G241", [("1", "1OE#"), ("2", "1A"), ("5", "2A"), ("7", "2OE"), ("4", "GND")],
                            [("6", "1Y"), ("3", "2Y"), ("8", "VCC")]),
}

# Optional circuit-owned pin tables keep new boards independent of legacy symbols.
for lid, mapping in getattr(circuit, "CUSTOM_SYMBOL_PINS", {}).items():
    name = lid.split(":", 1)[1]
    items = list(mapping.items())
    split = (len(items) + 1) // 2
    CUSTOM[name] = ic_symbol(name, items[:split], items[split:], ref="Q" if name.startswith("CSD") else "U")

# ------------------------------------------------------------ collect symbols
sym_blocks, sym_pins = {}, {}
for p in PARTS:
    lid = p["sym"]
    if lid in sym_blocks:
        continue
    lib, name = lid.split(":")
    blk = CUSTOM[name] if lib == "pdb" else extract_symbol(lib, name)
    sym_blocks[lid] = blk
    sym_pins[lid] = pins_of(blk)

# project symbol library (so the project opens with its custom symbols)
with open(f"{OUT}/pdb.kicad_sym", "w") as f:
    f.write("(kicad_symbol_lib (version 20220914) (generator robot_pdb_gen)\n")
    for k, v in CUSTOM.items():
        f.write(v.replace(f'"pdb:{k}"', f'"{k}"', 1) + "\n")
    f.write(")\n")
with open(f"{OUT}/sym-lib-table", "w") as f:
    f.write('(sym_lib_table\n  (lib (name "pdb")(type "KiCad")(uri "${KIPRJMOD}/pdb.kicad_sym")(options "")(descr "Robot PDB custom symbols"))\n)\n')

# ------------------------------------------------------------ placement
G = 2.54
snap = lambda v: round(v / G) * G
blocks = OrderedDict()
for p in PARTS:
    blocks.setdefault(p["block"], []).append(p)

ROOT = U()
out = [f'(kicad_sch (version 20230121) (generator eeschema)', f'  (uuid {ROOT})', '  (paper "User" 1189 1050)',
       '  (title_block (title "' + os.environ.get("TITLE", "Robot power distribution board") + '") (rev "' + revision + '") (company "")'
       ' (comment 1 "8S battery, 33.6V full. Engineering review only. See docs/HANDOFF.md."))',
       '  (lib_symbols']
out += ["    " + l for b in sym_blocks.values() for l in b.split("\n")]
out.append('  )')

NC_NETS = re.compile(r'(NC\d*|SYNCOUT|_NC)$')
net_count = defaultdict(int)
for p in PARTS:
    for n in p["pins"].values():
        net_count[n] += 1

COLS = 2
BW, BH = 400.0, 0  # block width
x0, y0 = 20.32, 30.48
col_x = [x0, x0 + 560]
col_y = [y0, y0]
instances = []
texts = []

for bi, (bname, parts) in enumerate(blocks.items()):
    c = (0 if bi in (0, 1, 7, 8, 9, 10) else 1) if bi < 11 else min(range(COLS), key=lambda i: col_y[i])
    bx, by = col_x[c], col_y[c]
    texts.append((bname, bx, by))
    # ICs/connectors first row, passives grid
    big = [p for p in parts if not p["sym"].startswith("Device:") or p["sym"] in ("Device:Fuse",)]
    small = [p for p in parts if p not in big]
    cx, cy = bx + 25.4, by + 20.32
    rowh = 0
    for p in big:
        pins = sym_pins[p["sym"]]
        ys = [v[1] for v in pins.values()] or [0]
        hgt = (max(ys) - min(ys)) + 15
        instances.append((p, snap(cx), snap(cy + max(ys))))
        rowh = max(rowh, hgt)
        cx += 76.2
        if cx > bx + 520:
            cx = bx + 25.4
            cy += rowh + 15
            rowh = 0
    cy += rowh + 20.32
    cx = bx + 20.32
    for i, p in enumerate(small):
        instances.append((p, snap(cx), snap(cy)))
        cx += 40.64
        if cx > bx + 520:
            cx = bx + 20.32
            cy += 25.4
    col_y[c] = cy + 45.72

# Larger integration inventories must not run beyond a fixed drawing sheet.
out[2] = f'  (paper "User" 1189 {max(1050, math.ceil(max(col_y)+150))})'

# ------------------------------------------------------------ emit
wires, labels, ncs = [], [], []
for p, sx, sy in instances:
    lid = p["sym"]
    pinmap = sym_pins[lid]
    fp = p["fp"]
    props = [("Reference", p["ref"]), ("Value", p["value"]), ("Footprint", fp), ("Datasheet", ""),
             ("LCSC", p["lcsc"]), ("MPN", p["mpn"])]
    s = [f'  (symbol (lib_id "{lid}") (at {sx:.2f} {sy:.2f} 0) (unit 1)',
         f'    (in_bom {"no" if p["dnp"] else "yes"}) (on_board yes) (dnp no)', f'    (uuid {U()})']
    for k, (nm, val) in enumerate(props):
        hide = "" if nm in ("Reference", "Value") else " hide"
        dy = -5.08 if nm == "Reference" else (-2.54 if nm == "Value" else 0)
        dx = 7.62 if lid.startswith("Device:") else 0
        if not lid.startswith("Device:"):
            ys = [v[1] for v in pinmap.values()] or [0]
            dy = -(max(ys) + 3.81) if nm == "Reference" else (-(min(ys) - 3.81) if nm == "Value" else 0)
        val = val.replace('"', "'")
        s.append(f'    (property "{nm}" "{val}" (at {sx+dx:.2f} {sy+dy:.2f} 0) '
                 f'(effects (font (size 1.27 1.27)) (justify left){hide}))')
    for num in pinmap:
        s.append(f'    (pin "{num}" (uuid {U()}))')
    s.append(f'    (instances (project "{PROJ}" (path "/{ROOT}" (reference "{p["ref"]}") (unit 1))))')
    s.append('  )')
    out += s
    # wires + labels on every pin
    for num, (px, py, ang) in pinmap.items():
        net = p["pins"].get(num)
        X, Y = sx + px, sy - py  # schematic y is down
        # outward direction = opposite of pin angle
        od = (ang + 180) % 360
        dx, dy = {0: (1, 0), 90: (0, -1), 180: (-1, 0), 270: (0, 1)}[od]
        if net is None or NC_NETS.search(net) or net_count[net] == 1:
            ncs.append((X, Y))
            continue
        L = 2.54
        X2, Y2 = X + dx * L, Y + dy * L
        wires.append((X, Y, X2, Y2))
        lang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(dx, dy)]
        labels.append((net, X2, Y2, lang))

for (a, b, c2, d) in wires:
    out.append(f'  (wire (pts (xy {a:.2f} {b:.2f}) (xy {c2:.2f} {d:.2f})) (stroke (width 0) (type default)) (uuid {U()}))')
for net, x, y, a in labels:
    just = {0: "left bottom", 180: "right bottom", 90: "left bottom", 270: "right bottom"}[a]
    out.append(f'  (label "{net}" (at {x:.2f} {y:.2f} {a}) (fields_autoplaced) '
               f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid {U()}))')
for x, y in ncs:
    out.append(f'  (no_connect (at {x:.2f} {y:.2f}) (uuid {U()}))')
for t, x, y in texts:
    out.append(f'  (text "{t}" (at {x:.2f} {y:.2f} 0) (effects (font (size 3 3) (thickness 0.6) bold) (justify left bottom)) (uuid {U()}))')

NOTES = ("DESIGN NOTES (v0.4-review)\\n"
         "- Engineering review only. PCB routing and qualification remain open: see docs/HANDOFF.md.\\n"
         "- On-board split: F1 30A motor pass-through to J2, F2 20A logic. Holders 178.6165.0002; use 58V ATO fuses. Pack fusing per pack is still advised.\\n"
         "- Two Nexus 8S1P P30B packs, Daly TH 60A BMS: 28.8V nominal / 33.6V full; detailed BMS limits unconfirmed.\\n"
         "- Thor is the developer kit: 9-28V input, 8A connector ceiling. Never connect raw 8S power.\\n"
         "- 24.33V output retained; regulation below 27V is unqualified. ILIM 180R + 33pF, exact Bourns L1.\\n"
         "- XL430 supply set to 10.8V nominal (30k/2.4k, basic parts); servo regeneration clamps still required.\\n"
         "- USB hub crystal corrected; bus-power strap grounded. Codec uses 100mA headset topology.\\n"
         "- CH342 VIO, LVC buffers and bus pullups run from separate AP2112 3.3V regulator.\\n"
         "- No external U2D2/spare USB headers; single onboard servo master. Battery telemetry is external and isolated.\\n"
         "- Inrush, USB current/suspend budget, thermal limits, compensation, stackup and assembly review remain release gates.")

NOTES = getattr(circuit, 'SCHEMATIC_NOTES', NOTES)
out.append(f'  (text "{NOTES}" (at {col_x[0]:.2f} {col_y[0]:.2f} 0) (effects (font (size 2 2)) (justify left top)) (uuid {U()}))')
out.append('  (sheet_instances (path "/" (page "1")))')
out.append(')')
open(f"{OUT}/{PROJ}.kicad_sch", "w").write("\n".join(out) + "\n")
print("symbols", len(instances), "labels", len(labels), "nc", len(ncs))
