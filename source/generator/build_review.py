"""Apply v0.4 changes to the immutable v0.3 board. KiCad 7 pcbnew required.

Usage: python3 build_review.py BASELINE_PCB OUTPUT_DIR
The baseline is available with git show 8bee42e:kicad/robot_pdb.kicad_pcb.
Output is an engineering-review candidate, not a fabrication release.
"""
import sys, os, json, math, hashlib
from pathlib import Path
import pcbnew
from bigboard import PARTS
from indexed_fixer import IndexedFixer as Fixer
from cells import Board

src, out = Path(sys.argv[1]), Path(sys.argv[2])
assert hashlib.sha256(src.read_bytes()).hexdigest() == '089d4b7b1b0367bdb56e9bf4c3d6fe93223345cf5db1b1a94a5e05934916f7a4', 'Use the immutable v0.3 baseline board'
out.mkdir(parents=True, exist_ok=True)
b = pcbnew.LoadBoard(str(src))
MM, T = pcbnew.FromMM, pcbnew.ToMM
parts = {p['ref']: p for p in PARTS}
libs=sorted({p['fp'].split(':')[0] for p in PARTS})
(out/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f'  (lib (name "{l}")(type "KiCad")(uri "${{KICAD7_FOOTPRINT_DIR}}/{l}.pretty")(options "")(descr ""))\n' for l in libs)+')\n')
removed = []
# Keep detached SWIG wrappers alive (KiCad 7 / Python 3.12 ownership quirk).
detached = []
def remove(item):
    detached.append(item)
    b.Remove(item)
for fp in list(b.GetFootprints()):
    if fp.GetReference() not in parts:
        removed.append(fp.GetReference()); remove(fp)
# New parts use official KiCad library land patterns; all original footprints stay embedded.
newpos = {'C27':(60,24,0), 'U17':(188,87,0), 'C65':(184.5,87,90), 'C66':(192,87,90)}
for ref, p in parts.items():
    fp = b.FindFootprintByReference(ref)
    if fp is None:
        lib, name = p['fp'].split(':')
        fp = pcbnew.FootprintLoad(os.path.join(os.environ.get('KICAD7_FOOTPRINT_DIR','/usr/share/kicad/footprints'),lib+'.pretty'), name)
        assert fp is not None, p['fp']
        fp.SetReference(ref); fp.SetFPID(pcbnew.LIB_ID(lib,name)); b.Add(fp)
        x,y,rot = newpos[ref]
        fp.SetPosition(pcbnew.VECTOR2I(MM(x),MM(y))); fp.SetOrientationDegrees(rot)
        fp.Value().SetVisible(False)
        fp.Reference().SetTextSize(pcbnew.VECTOR2I(MM(.8),MM(.8)))
        fp.Reference().SetTextThickness(MM(.12))
    elif str(fp.GetFPID().GetLibItemName()) != p['fp'].split(':')[1]:
        # Footprint changed for an existing part (C3/C4: 10x12.6 -> 10x10): swap in place.
        lib, name = p['fp'].split(':')
        new = pcbnew.FootprintLoad(os.path.join(os.environ.get('KICAD7_FOOTPRINT_DIR','/usr/share/kicad/footprints'),lib+'.pretty'), name)
        assert new is not None, p['fp']
        new.SetReference(ref); new.SetFPID(pcbnew.LIB_ID(lib,name))
        new.SetPosition(fp.GetPosition()); new.SetOrientation(fp.GetOrientation())
        new.Reference().SetPosition(fp.Reference().GetPosition()); new.Reference().SetTextSize(fp.Reference().GetTextSize())
        new.Value().SetVisible(False)
        remove(fp); b.Add(new); fp = new
    fp.SetValue(p['value'])
    for pad in fp.Pads():
        name = p['pins'].get(pad.GetNumber(),'')
        net = b.FindNet(name) if name else None
        if name and net is None:
            net=pcbnew.NETINFO_ITEM(b,name); b.Add(net)
        if net is not None: pad.SetNet(net)
        else: pad.SetNetCode(0)
# Remove copper whose terminal assignments changed, and the v0.3 autorouted upstream USB
# routes (replaced by the hand-placed pair below).
rip = {'H_XO','H_XI','V5_USB','A_REG33','USB_DP','USB_DM',
       'P3_DM','P3_DP','P4_DM','P4_DP'}
for t in list(b.GetTracks()):
    if t.GetNetname() in rip: remove(t)
# Input copper (J1 -> F1 motor pass-through -> J2, J1 -> F2 logic -> VBAT_L) is the
# unchanged v0.3 copper. F1/F2 keep the FLR_178.6165 footprint; only the BOM part changed.
# Keep labels consistent with actual circuitry, while retaining the mechanical envelope.
for d in list(b.GetDrawings()):
    if not isinstance(d,pcbnew.PCB_TEXT):continue
    t=d.GetText()
    if any(s in t for s in ('EXT U2D2','SPARE USB')):
        remove(d);continue
    t=t.replace('v0.3','v0.4 REVIEW').replace('27-33V','8S / 33.6V MAX').replace('27–33V','8S / 33.6V MAX')
    t=t.replace('24V 9A','24V / 8A MAX').replace('XL430 SERVOS 12V','XL430 10.8V').replace('15A','20A')
    if '5V x3' in t:t='ENGINEERING REVIEW - NOT FOR FABRICATION'
    d.SetText(t)
    if t == "8S / 33.6V MAX":
        d.SetPosition(pcbnew.VECTOR2I(MM(18),d.GetPosition().y))
fx=Fixer(b)
# Route only changed low-speed nets. Ground fills connect new ground pads, with
# explicit short plane stitches where possible. High-speed USB is intentionally open.
results=[]
def xy(p):return tuple(T(p.GetPosition()))
for net in ['H_XI','H_XO','A_REG33','V3_IO','V5_USB']:
    pads=[p for f in b.GetFootprints() for p in f.Pads() if p.GetNetname()==net and p.GetNumber()]
    done=[pads.pop(0)]
    while pads:
        _,i,a=min((math.dist(xy(a),xy(p)),i,a) for i,p in enumerate(pads) for a in done)
        p=pads.pop(i)
        # narrower breakout only on fine-pitch IC nets; DRC is run after fill.
        ok=fx.route(net,xy(a),xy(p),w=.2,step=.1,win=3)
        if not ok: ok=fx.route(net,xy(a),xy(p),w=.15,step=.05,win=5)
        results.append({'net':net,'from':a.GetParent().GetReference()+'.'+a.GetNumber(),'to':p.GetParent().GetReference()+'.'+p.GetNumber(),'routed':ok})
        print(results[-1],flush=True);done.append(p)
fx.route('T_ILIM',xy(fx.pad('U2','11')),xy(fx.pad('C27','1')),w=.2,step=.05,win=2,layers=('F',))
for ref,num in [('C27','2'),('U10','18'),('R70','1'),('U17','2'),('C65','2'),('C66','2')]:
    results.append({'ground':ref+'.'+num,'stitched':fx.gnd_via(fx.pad(ref,num),w=.2,rmax=2)})
# Route the bus-power strap to an existing ground pad; a blind straight stub can
# cross the adjacent V5 breakout, so use the same clearance-aware routing check.
results.append({'ground':'U10.18 via C61.2', 'routed':fx.route('GND',xy(fx.pad('U10','18')),xy(fx.pad('C61','2')),w=.15,step=.05,win=3)})
# Upstream USB pair (v0.4.1). Short, all on F.Cu over the solid In1 GND plane, no vias:
# J10 -> U11 (flow-through ESD, pins 6->1 / 4->3) -> U10. The two receptacle rows are joined
# beside the pads: DP on the inboard side, DM under the receptacle (as in v0.3). Each length is ~12 mm,
# far below the length where 90-ohm control matters at 480 Mbit/s. 0.2 mm traces, 0.3 mm gap where coupled.
# Two local nets that crossed this corridor (VBUS_IN to the ESD reference pin, and a V5_USB jog
# through the hub escape) are ripped here and rerouted around the pair by the clearance-checked router.
def _seg_key(t):
    a,c=T(t.GetStart()),T(t.GetEnd())
    return tuple(sorted([(round(a[0],2),round(a[1],2)),(round(c[0],2),round(c[1],2))]))
rip_local={
 'VBUS_IN':{((216.64,82.0),(217.13,82.0)),((217.13,82.0),(218.14,80.99)),((218.14,80.14),(218.14,80.99)),
            ((218.14,80.14),(218.73,79.55)),((217.13,82.0),(217.74,82.61)),((217.74,82.61),(217.74,83.97))},
 'V5_USB':{((209.45,80.26),(209.75,80.56)),((209.75,80.56),(209.75,81.86)),((209.75,81.86),(210.85,82.96)),
           ((210.85,82.96),(210.85,83.06)),((210.85,83.06),(210.95,83.16)),((210.95,83.16),(210.95,83.66)),
           ((210.85,83.76),(210.95,83.66)),((210.75,83.96),(210.85,83.76)),((210.65,83.96),(210.75,83.96))}}
for t in list(b.GetTracks()):
    if t.GetClass()=='PCB_TRACK' and t.GetNetname() in rip_local and _seg_key(t) in {tuple(sorted(k)) for k in rip_local[t.GetNetname()]}:
        remove(t)
fx=Fixer(b)
P=lambda r,n: xy(fx.pad(r,n))
jb6,ja6,ja7,jb7=P('J10','B6'),P('J10','A6'),P('J10','A7'),P('J10','B7')
e1,e6,e3,e4=P('U11','1'),P('U11','6'),P('U11','3'),P('U11','4')
h15,h14=P('U10','15'),P('U10','14')
W=.2
fx.add_track('USB_DP',[jb6,(218.8,jb6[1])],W,pcbnew.F_Cu)
fx.add_track('USB_DP',[ja6,(218.8,ja6[1]),(218.8,jb6[1])],W,pcbnew.F_Cu)
fx.add_track('USB_DP',[(218.8,jb6[1]),(218.6,e6[1]),e6,e1,(212.9,e1[1]),(211.7,h15[1]),h15],W,pcbnew.F_Cu)
fx.add_track('USB_DM',[ja7,(220.9,ja7[1]),(220.9,jb7[1]),jb7],W,pcbnew.F_Cu)
fx.add_track('USB_DM',[jb7,(218.8,jb7[1]),(218.6,e4[1]),e4,e3,(212.2,e3[1]),(212.0,h14[1]),h14],W,pcbnew.F_Cu)
# ESD VBUS reference pin: one via beside pad 5 (not in the pad), B.Cu jumpers to both receptacle VBUS groups.
e5=P('U11','5')
fx.add_track('VBUS_IN',[e5,(217.65,e5[1])],.4,pcbnew.F_Cu)
for x,y in [(217.65,e5[1]),(218.44,79.45),(216.9,83.85)]: fx.add_via('VBUS_IN',x,y)
fx.add_track('VBUS_IN',[(217.65,e5[1]),(218.44,81.2),(218.44,79.45)],.4,pcbnew.B_Cu)
fx.add_track('VBUS_IN',[(218.44,79.45),(218.73,79.55)],.4,pcbnew.F_Cu)
fx.add_track('VBUS_IN',[(217.65,e5[1]),(216.9,82.75),(216.9,83.85)],.4,pcbnew.B_Cu)
fx.add_track('VBUS_IN',[(216.9,83.85),(216.9,83.97)],.4,pcbnew.F_Cu)
usb_reroute=[]
for net,a,c,w in [('V5_USB',(209.45,80.26),(210.65,83.96),.2)]:
    ok=fx.route(net,a,c,w=w,step=.1,win=3)
    usb_reroute.append({'net':net,'from':a,'to':c,'routed':ok}); print(usb_reroute[-1],flush=True)
results.append({'usb_pair':'hand-placed F.Cu, 0.2mm','local_reroutes':usb_reroute})
# Avoid stale filled polygons. Final DRC is evidence, including unresolved airwires.
boardfile=out/'robot_pdb.kicad_pcb'
pcbnew.SaveBoard(str(boardfile),b)
b=pcbnew.LoadBoard(str(boardfile));pcbnew.ZONE_FILLER(b).Fill(b.Zones());pcbnew.SaveBoard(str(boardfile),b)
pcbnew.WriteDRCReport(b,str(out/'drc.rpt'),pcbnew.EDA_UNITS_MILLIMETRES,True)
(out/'revision_changes.json').write_text(json.dumps({'baseline_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'removed':removed,'new':list(newpos),'routing':results,'release_status':'ENGINEERING REVIEW ONLY; see docs/HANDOFF.md'},indent=2)+'\n')
print('Saved',boardfile,flush=True)
