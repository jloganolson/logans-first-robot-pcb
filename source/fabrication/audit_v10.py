#!/usr/bin/env python3
"""Independent delta and identity audit of the v0.10 candidate.

Run through with_kicad.sh. Proves, from the two saved boards, that v0.10 is
v0.9 translated plus exactly the changes listed in derivation.json, and that
the v0.10 schematic netlist matches the v0.10 board. Writes
outputs/v10-order-preparation/audit-v10.json and exits non-zero on any finding.
It does not re-run the v0.9 USB reference-plane analysis; relative copper
identity is what carries those results over.
"""
import collections,hashlib,json,re,subprocess,sys,tempfile
from pathlib import Path
import pcbnew as p

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'revisions/v0.9/kicad/robot_pdb.kicad_pcb';NEW=ROOT/'revisions/v0.10/kicad/robot_pdb.kicad_pcb'
OUT=ROOT/'outputs/v10-order-preparation';OUT.mkdir(parents=True,exist_ok=True)
D=json.loads((ROOT/'revisions/v0.10/derivation.json').read_text())
DX,DY=D['translation']['shift_mm'];W,H=D['translation']['outline_mm']
mm=p.ToMM;r4=lambda v:round(v,4)
def sha(q):return hashlib.sha256(Path(q).read_bytes()).hexdigest()
def xy(v,shift=False):return (r4(mm(v.x)+(DX if shift else 0)),r4(mm(v.y)+(DY if shift else 0)))
findings=[];facts={}
def check(ok,name,**data):
 if not ok:findings.append(dict(check=name,**data))
 return ok

old=p.LoadBoard(str(OLD));new=p.LoadBoard(str(NEW))
check(sha(OLD)==D['source_board_sha256'],'v0.9 source hash');check(sha(NEW)==D['board_sha256'],'v0.10 hash matches derivation record')

# footprints, pads, nets
of={f.GetReference():f for f in old.GetFootprints()};nf={f.GetReference():f for f in new.GetFootprints()}
check(set(of)==set(nf),'reference set',difference=sorted(set(of)^set(nf)))
moved=D['translation']['moved_holes'];changed_fp=set();pad_rows=0
for ref in sorted(set(of)&set(nf)):
 a,b=of[ref],nf[ref]
 if ref in moved:check(list(xy(b.GetPosition()))==[r4(v) for v in moved[ref]],'moved hole position',ref=ref);continue
 check(xy(a.GetPosition(),True)==xy(b.GetPosition()) and a.GetOrientationDegrees()==b.GetOrientationDegrees() and a.GetLayer()==b.GetLayer(),'footprint placement',ref=ref)
 check((a.GetAttributes()&(p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES))==(b.GetAttributes()&(p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)),'fit attributes',ref=ref)
 if ref in changed_fp:
  check({q.GetNumber():q.GetNetname() for q in a.Pads()}=={q.GetNumber():q.GetNetname() for q in b.Pads() if q.GetNumber()},'changed footprint pad nets',ref=ref);continue
 check(str(a.GetFPID().GetUniStringLibId())==str(b.GetFPID().GetUniStringLibId()),'footprint id',ref=ref)
 pa=sorted((q.GetNumber(),q.GetNetname(),xy(q.GetPosition(),True),xy(q.GetSize()),xy(q.GetDrillSize()),q.GetAttribute(),q.GetLayerSet().FmtHex()) for q in a.Pads())
 pb=sorted((q.GetNumber(),q.GetNetname(),xy(q.GetPosition()),xy(q.GetSize()),xy(q.GetDrillSize()),q.GetAttribute(),q.GetLayerSet().FmtHex()) for q in b.Pads())
 check(pa==pb,'pad geometry and nets',ref=ref);pad_rows+=len(pa)
vals={r:(of[r].GetValue(),nf[r].GetValue()) for r in of if r in nf and of[r].GetValue()!=nf[r].GetValue()}
check(set(vals)<={r for r,c in D['part_changes'].items() if c['value']!=c['old']['value']},'unexpected value changes',changes=vals)
facts.update(footprints=len(nf),unchanged_pads_compared=pad_rows,value_changes=vals)

# tracks and vias. The only permitted track difference is the recorded in-place widening of the High-Speed pair.
HS=D['hs_pair_widening'];widened=collections.Counter()
def tracks(board,shift):
 t=collections.Counter();v={}
 for item in board.GetTracks():
  if item.GetClass()=='PCB_VIA':v[(item.GetNetname(),)+xy(item.GetPosition(),shift)]=(r4(mm(item.GetDrillValue())),r4(mm(item.GetWidth())),item.GetLayerSet().FmtHex())
  else:
   ends=tuple(sorted([xy(item.GetStart(),shift),xy(item.GetEnd(),shift)]))
   mid=xy(item.GetMid(),shift) if item.GetClass()=='PCB_ARC' else None
   w=r4(mm(item.GetWidth()))
   if not shift and item.GetNetname() in HS['nets'] and w==HS['new_width_mm']:w=HS['old_width_mm'];widened[item.GetNetname()]+=mm(item.GetLength())
   t[(item.GetClass(),item.GetNetname(),item.GetLayer(),w,ends,mid)]+=1
 return t,v
ta,va=tracks(old,True);tb,vb=tracks(new,False)
check(ta==tb,'track multiset identical after translation (High-Speed widths normalised)',only_v09=len(ta-tb),only_v10=len(tb-ta))
for n,v in HS['per_net_mm'].items():check(abs(widened[n]-v['widened'])<.01,'recorded High-Speed widening length',net=n,measured=widened[n],recorded=v)
check(set(widened)<=set(HS['nets']),'widening confined to High-Speed nets')
facts['hs_pair_widening']=dict(width_mm=[HS['old_width_mm'],HS['new_width_mm']],gap_mm=HS['new_gap_mm'],per_net_mm=HS['per_net_mm'],note='centre lines unchanged; segments kept narrow are short clearance-limited necks')
removed={('GND',r4(x+DX),r4(y+DY)) for x,y in D['removed_offboard_gnd_vias_v09_mm']}
check(set(va)-set(vb)==removed and not set(vb)-set(va),'via set',missing=sorted(set(va)-set(vb)-removed),extra=sorted(set(vb)-set(va)))
relanded=0;tier=[]
for k in vb:
 a,b=va[k],vb[k]
 if a==b:continue
 ok=a[0]==.2 and a[1]==.4 and b[0]==D['via_lands']['new_drill_mm'] and b[1]==D['via_lands']['new_land_mm'] and a[2]==b[2];check(ok,'via change is the documented land growth',via=k,old=a,new=b);relanded+=ok
 # factory standard tier: every via hole >=0.30 mm with at least a 0.10 mm annular ring
for k,(drill,land,_) in vb.items():
 if not(drill>=.3-1e-6 and land>=drill+.2-1e-6):tier.append((k,drill,land))
check(relanded==D['via_lands']['count'],'re-landed via count',count=relanded);check(not tier,'vias outside free factory tier',vias=tier)
facts.update(track_segments=sum(tb.values()),vias=len(vb),relanded_vias=relanded,removed_offboard_vias=len(removed),via_sizes=dict(collections.Counter('%.2f/%.2f'%(d,l) for d,l,_ in vb.values())))

# zones
def zones(board,shift):
 rows=[]
 for z in board.Zones():
  o=z.Outline();pts=[]
  for i in range(o.OutlineCount()):
   c=o.Outline(i);pts.append(tuple(xy(c.CPoint(j),shift) for j in range(c.PointCount())))
  rows.append((z.GetNetname(),z.GetLayerSet().FmtHex(),z.GetAssignedPriority(),z.GetPadConnection(),r4(mm(z.GetLocalClearance())),r4(mm(z.GetMinThickness())),tuple(pts)))
 return sorted(rows)
check(zones(old,True)==zones(new,False),'zone definitions identical after translation');facts['zones']=len(new.Zones())

# filled copper: same zone, same fill, unless the outline crop or the listed changes touch it
def fills(board,shift):
 out={}
 for z in board.Zones():
  bb=z.GetBoundingBox();y0=mm(bb.GetTop())+(DY if shift else 0);y1=mm(bb.GetBottom())+(DY if shift else 0);x=xy(bb.GetPosition(),shift)
  out[(z.GetNetname(),z.GetLayerSet().FmtHex(),z.GetAssignedPriority(),x)]=(z.CalculateFilledArea()/1e12,y0>=0 and y1<=H)
 return out
fa,fb=fills(old,True),fills(new,False);ratios={};worst=[]
check(set(fa)==set(fb),'zone identity for fill comparison')
for k in sorted(set(fa)&set(fb)):
 a,inside=fa[k];b=fb[k][0]
 if a<=0:continue
 r=b/a;ratios['%s|%s|%s'%(k[0],k[1][-9:],k[3])]=[round(a,1),round(b,1),round(r,4)]
 if inside and not .97<=r<=1.06:worst.append((k,round(a,1),round(b,1),round(r,3)))
check(not worst,'filled area of uncropped zones within -3%/+6% of v0.9',zones=worst[:12])
facts['filled_zone_area']=dict(zones_compared=len(ratios),total_v09_mm2=round(sum(v[0] for v in fa.values()),0),total_v10_mm2=round(sum(v[0] for v in fb.values()),0),note='cropped zones lose the off-board strip; thinner clearance adds a little copper',per_zone=ratios)

# mounting-hole wall to the board edge
webs=[]
for f in new.GetFootprints():
 for q in f.Pads():
  d=mm(q.GetDrillSize().x)
  if d>=2.0:
   x,y=xy(q.GetPosition());webs.append((r4(min(x,y,W-x,H-y)-d/2),f.GetReference()))
check(min(webs)[0]>=1.3,'board material between large holes and the edge >= 1.3 mm',smallest=sorted(webs)[:4]);facts['smallest_hole_to_edge_wall_mm']=sorted(webs)[:4]

# outline and everything inside it
bb=new.GetBoardEdgesBoundingBox();facts['outline_bbox_mm']=[r4(mm(bb.GetX())),r4(mm(bb.GetY())),r4(mm(bb.GetWidth())),r4(mm(bb.GetHeight()))]
outside=[]
for item in new.GetTracks():
 for q in ([item.GetPosition()] if item.GetClass()=='PCB_VIA' else [item.GetStart(),item.GetEnd()]):
  x,y=xy(q);half=mm(item.GetWidth())/2
  if not(.5+half<=x<=W-.5-half and .5+half<=y<=H-.5-half):outside.append((item.GetNetname(),x,y))
for f in new.GetFootprints():
 for q in f.Pads():
  if q.IsOnLayer(p.F_Cu) or q.IsOnLayer(p.B_Cu):
   b=q.GetBoundingBox()
   if q.GetAttribute()!=p.PAD_ATTRIB_NPTH and f.GetReference()!='J10' and not(mm(b.GetLeft())>=.2 and mm(b.GetTop())>=.2 and mm(b.GetRight())<=W-.2 and mm(b.GetBottom())<=H-.2):outside.append((f.GetReference(),q.GetNumber()))
check(not outside,'copper inside outline',items=outside[:20])

# native DRC report produced by build_v10
rpt=(ROOT/'revisions/v0.10/drc.rpt').read_text();kinds=collections.Counter(re.findall(r'^\[(\w+)\]',rpt,re.M))
base=collections.Counter(re.findall(r'^\[(\w+)\]',(ROOT/'revisions/v0.9/drc.rpt').read_text(),re.M))
unconnected=int(re.search(r'Found (\d+) unconnected pads',rpt)[1])
check(str(NEW) in rpt.splitlines()[0],'DRC report is for the v0.10 board');check(unconnected==0,'unconnected pads',count=unconnected)
check(kinds==base,'native DRC categories equal the reviewed v0.9 warnings',v10=dict(kinds),v09=dict(base))
facts['native_drc']=dict(categories=dict(kinds),unconnected_pads=unconnected,note='all are warnings carried unchanged from v0.9')

# schematic netlist against the board
with tempfile.TemporaryDirectory() as tmp:
 net=Path(tmp)/'n.xml'
 subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(net),str(NEW.with_suffix('.kicad_sch'))],check=True,capture_output=True)
 x=net.read_text()
comp={m[1]:dict(value=m[2],footprint=m[3]) for m in re.finditer(r'<comp ref="([^"]+)">\s*<value>([^<]*)</value>\s*<footprint>([^<]*)</footprint>',x)}
pins=collections.defaultdict(dict)
for m in re.finditer(r'<net code="\d+" name="([^"]*)">(.*?)</net>',x,re.S):
 for n in re.finditer(r'<node ref="([^"]+)" pin="([^"]+)"',m[2]):pins[n[1]][n[2]]=m[1].lstrip('/')
check(set(comp)==set(nf),'schematic and board references',difference=sorted(set(comp)^set(nf))[:20])
bad=[];padcount=collections.Counter(q.GetNetname() for f in nf.values() for q in f.Pads() if q.GetNumber());single=0
for ref,f in nf.items():
 c=comp.get(ref)
 if not c:continue
 if c['value'].replace('&amp;','&')!=f.GetValue() or c['footprint']!=str(f.GetFPID().GetUniStringLibId()):bad.append((ref,c,f.GetValue(),str(f.GetFPID().GetUniStringLibId())))
 for q in f.Pads():
  if not q.GetNumber():continue
  want=pins.get(ref,{}).get(q.GetNumber());have=q.GetNetname()
  if want is None:
   if have and not have.startswith('unconnected-') and not have.startswith('NC_'):bad.append((ref,q.GetNumber(),'board net without schematic pin',have))
  elif want.startswith('unconnected-') and (not have or padcount[have]==1):single+=bool(have)  # v0.9 convention: one-pad placeholder net on a no-connect pin
  elif want!=have:bad.append((ref,q.GetNumber(),want,have))
check(not bad,'schematic to board identity',mismatches=bad[:25],count=len(bad));facts['schematic']=dict(components=len(comp),no_connect_pins_with_single_pad_board_net=single,sha256=sha(NEW.with_suffix('.kicad_sch')))

report=dict(status='PASS' if not findings else 'HOLD',board_sha256=sha(NEW),source_board_sha256=sha(OLD),derivation=D['translation'],facts=facts,findings=findings,
 scope='Delta against reviewed v0.9 copper, native DRC parity, via tier, outline containment and schematic/board identity. Not covered: USB signal measurement or reference-plane re-analysis, thermal behaviour, factory DFM.')
(OUT/'audit-v10.json').write_text(json.dumps(report,indent=1,default=str)+'\n')
print(report['status'],json.dumps(facts,default=str)[:900]);[print('FINDING',json.dumps(f,default=str)[:500]) for f in findings]
sys.exit(0 if not findings else 1)
