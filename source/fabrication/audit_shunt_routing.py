"""Independent physical screen: sense lead joins the shunt, not load copper."""
import json,math,hashlib
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
def xy(item):return p.ToMM(item.GetPosition())
def near(a,b,tol=.015):return math.dist(a,b)<tol
def segment_distance(q,a,b):
 dx,dy=b[0]-a[0],b[1]-a[1];d=dx*dx+dy*dy
 f=0 if not d else max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/d))
 return math.dist(q,(a[0]+f*dx,a[1]+f*dy))
def audit(folder,project,sense):
 path=ROOT/'revisions'/folder/'kicad'/f'{project}.kicad_pcb';b=p.LoadBoard(str(path));fps={f.GetReference():f for f in b.GetFootprints()}
 def pad(r,n):return next(a for a in fps[r].Pads() if a.GetNumber()==n)
 shunt=pad('R21','1');sensor=pad('R13','2');q3=[pad('Q3',n) for n in ('1','2','3')]
 copper=[t for t in b.GetTracks() if t.GetNetname()==sense and t.GetClass()=='PCB_TRACK']
 thin=[t for t in copper if p.ToMM(t.GetWidth())<.6];power=[t for t in copper if p.ToMM(t.GetWidth())>=.6]
 graph={}
 for t in thin:
  a=tuple(round(v,4) for v in p.ToMM(t.GetStart()));z=tuple(round(v,4) for v in p.ToMM(t.GetEnd()));graph.setdefault(a,[]).append(z);graph.setdefault(z,[]).append(a)
 ends=[a for a,neighbours in graph.items() if len(neighbours)==1]
 end_ok=len(ends)==2 and all(any(near(a,xy(q)) for a in ends) for q in (shunt,sensor))
 seen=set();stack=[next(iter(graph))] if graph else []
 while stack:
  q=stack.pop()
  if q in seen:continue
  seen.add(q);stack.extend(graph[q])
 violations=[];zones=[z.GetFilledPolysList(p.F_Cu) for z in b.Zones() if z.GetNetname()==sense and z.GetLayer()==p.F_Cu]
 for t in thin:
  a=p.ToMM(t.GetStart());z=p.ToMM(t.GetEnd());steps=max(1,math.ceil(math.dist(a,z)/.025))
  for i in range(steps+1):
   q=(a[0]+(z[0]-a[0])*i/steps,a[1]+(z[1]-a[1])*i/steps);point=p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
   if shunt.HitTest(point):continue
   shared=any(segment_distance(q,p.ToMM(w.GetStart()),p.ToMM(w.GetEnd()))<p.ToMM(w.GetWidth()+t.GetWidth())/2 for w in power)
   shared|=any(poly.Contains(point) for poly in zones)
   if shared:violations.append(q)
 source_zone_ok=all(any(poly.Contains(q.GetPosition()) for poly in zones) for q in q3)
 # Direct PGND branch is separate from the positive sense trace and reaches a
 # plated return at the shunt ground land. It remains part of common GND.
 pgnd=xy(pad('U2','12'));ground_tracks=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='GND']
 def has_segment(a,z,layer):return any(t.GetLayer()==layer and ((near(p.ToMM(t.GetStart()),a) and near(p.ToMM(t.GetEnd()),z)) or(near(p.ToMM(t.GetStart()),z) and near(p.ToMM(t.GetEnd()),a))) for t in ground_tracks)
 direct_ground=has_segment(pgnd,(28.1,36.8),p.F_Cu) and has_segment((28.1,36.8),(29.5,36.8),p.B_Cu) and has_segment((29.5,36.8),(29.5,30),p.B_Cu) and has_segment((29.5,30),xy(pad('R21','2')),p.F_Cu)
 checks={'thin_sense_chain_runs_R13_to_shunt_only':end_ok and len(seen)==len(graph),'sense_does_not_join_power_copper_outside_shunt_pad':not violations,'all_three_low_side_source_pads_join_wide_power_zone':source_zone_ok,'direct_PGND_to_shunt_ground_path':direct_ground}
 report={'board':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'thin_trace_endpoints_mm':ends,'sampled_shared_copper_violations':violations,'qualification':'Geometric routing screen only. Common-ground offsets, current-limit transients, temperature and parasitics require measurement.'}
 out=ROOT/'outputs'/f'{folder}-design';out.mkdir(exist_ok=True);(out/'shunt-routing-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));return all(checks.values())
if __name__=='__main__':
 results=[audit('motor-addon','motor_supply','M_SENSE'),audit('usb-power','usb_power','USB_SENSE')];raise SystemExit(0 if all(results) else 1)
