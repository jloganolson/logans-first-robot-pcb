"""Read-only saved-board USB2 cell screen, separate from its route search."""
import sys,json,hashlib,math,re,collections
from pathlib import Path
import pcbnew as p
import usb2_control as circuit
import audit_usb3_signals as geometry
ROOT=Path(__file__).resolve().parents[2];K=ROOT/'revisions/usb2-control/kicad'
path=K/'usb2_control.kicad_pcb';b=p.LoadBoard(str(path));issues=[]
def fail(kind,**data):issues.append(dict(kind=kind,**data))
HS={'USB_DP','USB_DM','HUB_UP_DP','HUB_UP_DM'}
geometry.hs_key=lambda net:'USB2_UPSTREAM' if net in HS else None
records=geometry.load_records(b)
region=dict(reference='U9902',box_mm=[11.25,1.5,18.75,9.5],body_expansion_mm=3,
    pair_groups=['USB2_UPSTREAM'],nets=list(next(s for s in circuit.PARTS if s['ref']=='U9902')['pins'].values()),
    reason='Bounded 3mm package escape: short supply/select/enable/unused-channel landings; no general corridor exception')
mins,exceptions=geometry.spacing(records,[region])
for row in mins:
    if row['edge_spacing_mm']<row['target_mm']-1e-4:fail('outside_package_spacing',**row)
# Reuse geometric plane sampling with these USB2 nets selected; this changes
# only the selector and introduces no USB3-specific length/skew acceptance.
geometry.pair_key=lambda net:'USB2_UPSTREAM' if net in HS else None
refs=geometry.reference_audit(b)
for row in refs['missing_reference_samples']:fail('reference_gap',**row)
spec={s['ref']:s for s in circuit.PARTS}
fps={f.GetReference():f for f in b.GetFootprints()}
if set(spec)!=set(fps):fail('reference_set',missing=sorted(set(spec)-set(fps)),extra=sorted(set(fps)-set(spec)))
for ref,s in spec.items():
    f=fps[ref]
    lid=f.GetFPID();actual=str(lid.GetLibNickname())+':'+str(lid.GetLibItemName())
    if actual!=s['fp']:fail('footprint',ref=ref,actual=actual,expected=s['fp'])
    for q in f.Pads():
        if q.GetNetname()!=s['pins'].get(q.GetNumber(),''):fail('pad_net',ref=ref,pin=q.GetNumber(),actual=q.GetNetname(),expected=s['pins'].get(q.GetNumber(),''))
for via in (t for t in b.GetTracks() if t.GetClass()=='PCB_VIA'):
    xy=via.GetPosition();radius=p.ToMM(via.GetWidth())/2
    for f in b.GetFootprints():
        for q in f.Pads():
            if q.GetAttribute()==p.PAD_ATTRIB_SMD and q.HitTest(xy,p.FromMM(radius)):
                fail('via_overlaps_SMD_land',via_mm=p.ToMM(xy),ref=f.GetReference(),pin=q.GetNumber())
lengths=collections.defaultdict(float);signal_vias=[]
for t in b.GetTracks():
    if t.GetNetname()not in HS:continue
    if t.GetClass()=='PCB_VIA':signal_vias.append(dict(net=t.GetNetname(),at_mm=p.ToMM(t.GetPosition())));continue
    if t.GetLayer()!=p.F_Cu:fail('unexpected_USB_layer',net=t.GetNetname(),layer=b.GetLayerName(t.GetLayer()))
    lengths[t.GetNetname()]+=p.ToMM(t.GetLength())
if signal_vias:fail('unexpected_USB_signal_vias',vias=signal_vias)
pairs=[]
for pn in [('USB_DP','USB_DM'),('HUB_UP_DP','HUB_UP_DM')]:
    lens=[lengths[n] for n in pn];row=dict(nets=pn,lengths_mm=lens,skew_mm=abs(lens[0]-lens[1]));pairs.append(row)
    if row['skew_mm']>.15:fail('USB2_segment_skew_over_design_budget',**row)
connectivity=geometry.net_connectivity(b,{net for s in circuit.PARTS for net in s['pins'].values() if net!='GND'and not net.endswith('_NC')})
for row in connectivity:
    if not row['connected']:fail('pad_connectivity',**row)
drc=(K/'drc.rpt').read_text();counts={name:int(re.search(r'Found (\d+) '+name,drc).group(1))for name in ['DRC violations','unconnected pads','Footprint errors']}
if any(counts.values()):fail('native_DRC',counts=counts)
inputs=[path,K/'usb2_control.kicad_pro',K/'drc.rpt',K/'route-report.json',Path(__file__),ROOT/'source/generator/usb2_control.py',ROOT/'source/generator/build_usb2_control.py',ROOT/'source/generator/audit_usb3_signals.py']
out={'status':'PASS'if not issues else'FAIL','scope':'Saved 45x30mm support cell only; full J10-to-CH334 channel and base integration not covered',
 'parts':len(spec),'native_drc':counts,'ground_connectivity':'Native DRC includes filled GND zones; track/pad-only BFS intentionally excludes GND',
 'pair_copper':pairs,'reference':refs,'outside_package_minima':mins,
 'bounded_package_subtarget_minima':exceptions,'package_regions':[region],'source_pad_connectivity':connectivity,'issues':issues,
 'sha256':{str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest()for q in inputs}}
(K/'signal-audit.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'status':out['status'],'issues':issues[:15],'parts':len(spec),'pair_copper':pairs},indent=2))
raise SystemExit(bool(issues))
