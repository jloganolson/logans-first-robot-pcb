"""Independent geometry screens supplement native DRC; no current-rating inference."""
from pathlib import Path
import json,math,hashlib,re
import pcbnew as p
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));o=root/'outputs/v06-order-preparation'
# Use a separate S-expression polygon parser for power cross-section measurements.
s=path.read_text();stack=[];doc=[];cur=doc
for t in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',s):
 if t=='(':a=[];cur.append(a);stack.append(cur);cur=a
 elif t==')':cur=stack.pop()
 else:cur.append(json.loads(t) if t.startswith('"') else t)
def cs(n,k):return [a for a in n if isinstance(a,list) and a and a[0]==k]
def c(n,k):return next(iter(cs(n,k)),[])
polys=[]
for z in cs(doc[0],'zone'):
 for poly in cs(z,'filled_polygon'):polys.append((c(z,'net_name')[1],c(poly,'layer')[1],[(float(x[1]),float(x[2])) for x in c(poly,'pts')[1:]]))
def spans(points,axis,v):
 cuts=[]
 for a,z in zip(points,points[1:]+points[:1]):
  if a[axis]<=v<z[axis] or z[axis]<=v<a[axis]:
   q=1-axis;cuts.append(a[q]+(v-a[axis])*(z[q]-a[q])/(z[axis]-a[axis]))
 cuts.sort();return list(zip(cuts[::2],cuts[1::2]))
def union(vals):
 ans=[]
 for lo,hi in sorted(vals):
  if ans and lo<=ans[-1][1]:ans[-1][1]=max(hi,ans[-1][1])
  else:ans.append([lo,hi])
 return ans
cuts=[]
for net,axis,v in [('PACK_A_POS',0,29.4),('PACK_B_POS',0,60.4),('VBAT',1,49.6),('+24V',1,58.3),('+24V',1,64)]:
 for layer in ('F.Cu','B.Cu'):
  vals=union([a for n,L,pts in polys if n==net and L==layer for a in spans(pts,axis,v)])
  if vals:cuts.append({'net':net,'layer':layer,'cut_axis':'xy'[axis],'cut_position_mm':v,'filled_intervals_mm':vals,'total_width_mm':sum(h-l for l,h in vals)})
# Check L2 ground directly beneath sampled upstream USB track centre lines.
ground=[z.GetFilledPolysList(p.In1_Cu) for z in b.Zones() if z.GetNetname()=='GND' and z.GetLayer()==p.In1_Cu]
missing=[];lengths={}
for n in ('USB_DP','USB_DM'):
 tracks=[t for t in b.GetTracks() if t.GetNetname()==n and t.GetClass()=='PCB_TRACK'];lengths[n]=sum(p.ToMM(t.GetLength()) for t in tracks)
 for t in tracks:
  a=p.ToMM(t.GetStart());z=p.ToMM(t.GetEnd());steps=max(1,math.ceil(math.dist(a,z)/.1))
  for i in range(steps+1):
   q=(a[0]+(z[0]-a[0])*i/steps,a[1]+(z[1]-a[1])*i/steps);pt=p.VECTOR2I(*[p.FromMM(v) for v in q])
   if not any(poly.Contains(pt) for poly in ground):missing.append({'net':n,'xy':q})
outer=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetLayer() in (p.F_Cu,p.B_Cu)]
assert min(p.ToMM(t.GetWidth()) for t in outer)>=.16
r={'source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'power_cuts':cuts,'usb_total_conductor_length_including_connector_branches_mm':lengths,'usb_L2_reference_centreline_missing_samples':missing,'outer_min_trace_width_mm':min(p.ToMM(t.GetWidth()) for t in outer),'note':'Conductor lengths include redundant USB-C branches and ESD pass-through tracks; not an exact single electrical path skew measurement. Width sums do not certify ampacity or fault withstand.'}
(o/'geometry-audit.json').write_text(json.dumps(r,indent=2));print(json.dumps(r,indent=2))
