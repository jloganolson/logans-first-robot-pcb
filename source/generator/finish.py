"""Route leftovers with Freerouting, pour planes, fill, DRC. Shared by both boards."""
import os, re, subprocess
import pcbnew

JAR = "/opt/freerouting/freerouting-2.4.1-executable.jar"
JAVA = "/usr/lib/jvm/java-25-openjdk-amd64/bin/java"
MM = pcbnew.FromMM


def cls_of(n):
    if n in ("GND", "VIN"):
        return "plane"
    if n.startswith("+") or n.endswith("_SW") or n in ("VBAT_L", "VBAT", "VMOT") or n.startswith("SPK_"):
        return "rail"
    if n.startswith("AMP_OUT") or n.startswith("AMP_BS") or n == "VBUS_IN":
        return "amp"
    if n in ("T_HO", "T_LO", "T_BST", "T_VCC", "Q1_G") or n.endswith("_BST"):
        return "drive"
    return "sig"


RULES = {"plane": (400, 200), "rail": (800, 250), "drive": (400, 200), "sig": (250, 200), "amp": (400, 200)}


def export_dsn(board, dsn, skip_nets=()):
    assert pcbnew.ExportSpecctraDSN(board, dsn)
    t = open(dsn).read()
    for n in skip_nets:
        t = re.sub(r'\(net "?%s"?\s*\(pins[^)]*\)\s*\)' % re.escape(n), "", t)
    m = re.search(r'\(class kicad_default "?"?(.*?)\(circuit', t, re.S)
    names = [x for x in re.findall(r'"[^"]*"|\S+', m.group(1)) if x.strip('"') not in skip_nets]
    use_via = re.search(r'\(use_via [^)]*\)', t[m.start():]).group(0)
    i, depth = m.start(), 0
    while True:
        if t[i] == "(":
            depth += 1
        elif t[i] == ")":
            depth -= 1
            if depth == 0:
                break
        i += 1
    groups = {}
    for n in names:
        groups.setdefault(cls_of(n.strip('"')), []).append(n)
    new = [f'(class {g} {" ".join(ns)}\n      (circuit {use_via})\n      (rule (width {RULES[g][0]}) (clearance {RULES[g][1]}))\n    )'
           for g, ns in groups.items()]
    t = t[:m.start()] + "\n    ".join(new) + t[i + 1:]
    # keep the inner ground plane solid: no autorouted signals on In1
    t = re.sub(r'(\(layer In1\.Cu\s*\(type )signal\)', r'\1power)', t)
    # hand-drawn wiring stays put
    t = t.replace("(type route)", "(type fix)")
    t = re.sub(r'\(wire(\s+\(path)', r'(wire\1', t)
    open(dsn, "w").write(t)
    return {g: len(v) for g, v in groups.items()}


def import_ses(board, path):
    t = open(path).read()
    k = lambda v: int(round(float(v) * 1e3 / 10))
    no = t.index("(network_out")
    nt = nv = 0
    for m in re.finditer(r'\(net\s+("([^"]*)"|\S+)', t[no:]):
        name = m.group(2) if m.group(2) is not None else m.group(1)
        start = no + m.end()
        nxt = re.search(r'\n\s*\(net\s', t[start:])
        body = t[start: start + nxt.start()] if nxt else t[start:]
        net = board.FindNet(name)
        for w in re.finditer(r'\(path\s+(\S+)\s+(\d+)\s+([-\d\s]+)\)', body):
            layer = board.GetLayerID(w.group(1))
            width = k(w.group(2))
            xy = list(map(int, w.group(3).split()))
            pts = [(xy[i], xy[i + 1]) for i in range(0, len(xy), 2)]
            for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
                tr = pcbnew.PCB_TRACK(board)
                tr.SetStart(pcbnew.VECTOR2I(k(x0), -k(y0))); tr.SetEnd(pcbnew.VECTOR2I(k(x1), -k(y1)))
                tr.SetWidth(width); tr.SetLayer(layer); tr.SetNet(net)
                board.Add(tr); nt += 1
        for v in re.finditer(r'\(via\s+"([^"]+)"\s+(-?\d+)\s+(-?\d+)', body):
            ps = re.search(r'_(\d+):(\d+)_um', v.group(1))
            via_ = pcbnew.PCB_VIA(board)
            via_.SetPosition(pcbnew.VECTOR2I(k(v.group(2)), -k(v.group(3))))
            via_.SetWidth(MM(int(ps.group(1)) / 1000)); via_.SetDrill(MM(int(ps.group(2)) / 1000))
            via_.SetNet(net); board.Add(via_); nv += 1
    return nt, nv


def route(B, out, name, passes=20, skip_nets=(), reroute=True):
    board = B.b
    dsn, ses = f"{out}/{name}.dsn", f"{out}/{name}.ses"
    classes = export_dsn(board, dsn, skip_nets)
    print("classes", classes)
    if reroute or not os.path.exists(ses):
        r = subprocess.run([JAVA, "-jar", JAR, "-de", dsn, "-do", ses, "-mp", str(passes), "-mt", "4",
                            "--gui.enabled=false", "--router.optimizer.enabled=false"],
                           capture_output=True, text=True, timeout=3000)
        print(r.stdout[-1500:], r.stderr[-800:])
    # SES holds only the new wiring; hand-drawn (fixed) tracks stay on the board
    print("imported tracks/vias", import_ses(board, ses))


def finish(B, out, name, W, H):
    m = 0.5
    for L in ("F", "B"):
        B.zone("GND", L, [(m, m), (W - m, m), (W - m, H - m), (m, H - m)], prio=0, clearance=0.35, thermal=True)
    tmp = f"{out}/{name}_prefill.kicad_pcb"
    pcbnew.SaveBoard(tmp, B.b)
    board = pcbnew.LoadBoard(tmp)
    filler = pcbnew.ZONE_FILLER(board)
    filler.Fill(board.Zones())
    pcb = f"{out}/{name}.kicad_pcb"
    pcbnew.SaveBoard(pcb, board)
    rep = f"{out}/drc.rpt"
    pcbnew.WriteDRCReport(board, rep, pcbnew.EDA_UNITS_MILLIMETRES, True)
    txt = open(rep).read()
    print(re.findall(r"\*\* Found \d+ [^\n]*", txt))
    return pcb, rep


def drc_summary(rep):
    txt = open(rep).read()
    cnt = {}
    for m in re.finditer(r"\[(\w+)\]:", txt):
        cnt[m.group(1)] = cnt.get(m.group(1), 0) + 1
    return cnt


def render(pcb, png, layers="F.Cu,B.Cu,F.SilkS,Edge.Cuts,F.Fab", scale=12):
    svg = png.replace(".png", ".svg")
    subprocess.run(["kicad-cli", "pcb", "export", "svg", "--layers", layers, "--page-size-mode", "2",
                    "--exclude-drawing-sheet", "-o", svg, pcb], check=True, capture_output=True)
    subprocess.run(["rsvg-convert", "-z", str(scale / 3.0), "-b", "white", "-o", png, svg], check=True)
