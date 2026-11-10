"""Independent nominal drill/land screen against JLC multilayer 2oz rules.

Run with KiCad's Python. This supplements native DRC; it does not establish
manufacturing acceptance, copper current capacity or mechanical fit.
"""
import argparse,hashlib,json,math
from pathlib import Path
import pcbnew as p

def pt(v):return tuple(p.ToMM(v))
def sub(a,b):return (a[0]-b[0],a[1]-b[1])
def dot(a,b):return a[0]*b[0]+a[1]*b[1]
def point_segment(q,a,b):
 d=sub(b,a);n=dot(d,d);t=max(0,min(1,dot(sub(q,a),d)/n)) if n else 0
 return math.dist(q,(a[0]+t*d[0],a[1]+t*d[1]))
def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def segment_distance(a,b,c,d):
 r=sub(b,a);s=sub(d,c);det=cross(r,s)
 if abs(det)>1e-12:
  t=cross(sub(c,a),s)/det;u=cross(sub(c,a),r)/det
  if 0<=t<=1 and 0<=u<=1:return 0
 return min(point_segment(a,c,d),point_segment(b,c,d),point_segment(c,a,b),point_segment(d,a,b))
def capsule(center,size,angle):
 x,y=size;rad=min(x,y)/2;half=abs(x-y)/2
 a=math.radians(-angle+(90 if y>x else 0));v=(half*math.cos(a),half*math.sin(a))
 return ((center[0]-v[0],center[1]-v[1]),(center[0]+v[0],center[1]+v[1]),rad)

def audit(path):
 b=p.LoadBoard(str(path));holes=[];issues=[]
 def fail(rule,**data):issues.append(dict(rule=rule,**data))
 for f in b.GetFootprints():
  for pad in f.Pads():
   drill=pt(pad.GetDrillSize())
   if min(drill)<=0:continue
   name=f.GetReference()+'.'+pad.GetNumber()+'@'+','.join(f'{v:.4f}' for v in pt(pad.GetPosition()))
   thermal=any(q.GetAttribute()==p.PAD_ATTRIB_SMD and q.GetNumber()==pad.GetNumber() and q.HitTest(pad.GetPosition()) for q in f.Pads())
   kind='npth' if pad.GetAttribute()==p.PAD_ATTRIB_NPTH else ('via' if thermal else 'pth')
   size=pt(pad.GetSize());xy=pt(pad.GetPosition());cap=capsule(xy,drill,pad.GetOrientationDegrees())
   holes.append(dict(name=name,kind=kind,center_mm=xy,drill_mm=drill,cap=cap))
   if kind=='pth':
    # Concentric oval/round/rect lands: their minor axial radial annulus.
    ann=min((size[0]-drill[0])/2,(size[1]-drill[1])/2)
    if ann<.254-1e-6:fail('component PTH radial annulus >=0.254mm',pad=name,annulus_mm=ann,size_mm=size,drill_mm=drill)
   if abs(drill[0]-drill[1])>1e-6:
    width=min(drill);length=max(drill);minimum=1 if kind=='npth' else .35
    if width<minimum-1e-6:fail('slot minimum width',pad=name,kind=kind,width_mm=width,minimum_mm=minimum)
    if kind=='pth' and length<2*width-1e-6:fail('plated slot length >=2x width',pad=name,length_mm=length,width_mm=width)
   elif kind=='npth' and min(drill)<.5-1e-6:fail('round NPTH >=0.5mm',pad=name,drill_mm=drill)
 for t in b.GetTracks():
  if t.GetClass()!='PCB_VIA':continue
  xy=pt(t.GetPosition());dr=p.ToMM(t.GetDrillValue());diam=p.ToMM(t.GetWidth());name=str(t.m_Uuid.AsString())
  holes.append(dict(name=name,kind='via',center_mm=xy,drill_mm=(dr,dr),cap=capsule(xy,(dr,dr),0)))
  if diam<dr+.1-1e-6:fail('via diameter >= drill+0.1mm',via=name,diameter_mm=diam,drill_mm=dr)
 for i,h in enumerate(holes):
  for other in holes[i+1:]:
   a,c,r=h['cap'];d,e,s=other['cap'];required=.2 if h['kind']==other['kind']=='via' else .45
   # Broad-phase rejection bounds the expensive exact capsule comparison.
   if math.dist(h['center_mm'],other['center_mm'])>max(h['drill_mm'])/2+max(other['drill_mm'])/2+required:continue
   gap=segment_distance(a,c,d,e)-r-s
   if gap<required-1e-5:fail('drill edge-to-edge separation',a=h['name'],b=other['name'],centers_mm=[h['center_mm'],other['center_mm']],types=[h['kind'],other['kind']],gap_mm=gap,minimum_mm=required)
 return dict(status='PASS' if not issues else 'FAIL',board=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),holes=len(holes),issues=issues,
  source='https://jlcpcb.com/capabilities/pcb-capabilities',verified='2026-11-09',
  coverage=['Component PTH annular width','Round and slotted hole dimensions','All drill-to-drill capsule distances including same-net holes','Via drill/land ratio'],
  limitations=['Via-to-component drill pairs conservatively use 0.45mm; obtain factory disposition if proposing otherwise.','Pad and hole position/size tolerances still require manufacturer engineering review.','Native copper DRC and independent signal/reference/thermal checks remain separate.'])

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('board',type=Path);parser.add_argument('--output',type=Path);args=parser.parse_args()
 report=audit(args.board)
 if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('status','holes')},indent=2));print(json.dumps(report['issues'][:25],indent=2))
 raise SystemExit(report['status']!='PASS')
