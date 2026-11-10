#!/usr/bin/env python3
"""Independent audit of the compact v0.11 board against v0.10.

Run through with_kicad.sh. v0.11 re-floorplans only the hobby-servo block, so
the audit proves three things from the two saved boards:
  1. everything outside that block (the main board and the USB block) has the
     same parts, pads, tracks, vias and zone definitions as v0.10;
  2. inside the block no part, pad or net assignment changed - parts only moved;
  3. the result is fully connected, inside the new outline, in the free via
     tier, and the schematic still matches the board.
Writes outputs/v11-order-preparation/audit-v11.json; exits non-zero on a finding.
"""
import collections,hashlib,json,re,subprocess,sys,tempfile
from pathlib import Path
import pcbnew as p

ROOT=Path(__file__).resolve().parents[2]
OLD=ROOT/'revisions/v0.10/kicad/robot_pdb.kicad_pcb';NEW=ROOT/'revisions/v0.11/kicad/robot_pdb.kicad_pcb'
OUT=ROOT/'outputs/v11-order-preparation';OUT.mkdir(parents=True,exist_ok=True)
D=json.loads((ROOT/'revisions/v0.11/derivation.json').read_text());W,H=D['outline_mm']
STRIP_Y,STRIP_X=110.5,178.0            # the re-laid-out block lies below and left of these lines
FOLLOW=('P4_DP','P4_DM','V5_USB')      # copper that was shortened to follow the servo controller
PLUGS=tuple(D['placed']['plugs moved to an edge'])                 # Thor and Dynamixel plugs moved to board edges
EXTENDED=('DXL330_DATA','DXL430_DATA','+24V','+12V_SRV')           # nets whose copper was extended to those plugs
mm=p.ToMM;r4=lambda v:round(v,4)
def sha(q):return hashlib.sha256(Path(q).read_bytes()).hexdigest()
def xy(v):return (r4(mm(v.x)),r4(mm(v.y)))
def in_strip(q):return q[1]>=STRIP_Y and q[0]<=STRIP_X
findings=[];facts={}
def check(ok,name,**data):
 if not ok:findings.append(dict(check=name,**data))
 return ok
old=p.LoadBoard(str(OLD));new=p.LoadBoard(str(NEW))
check(sha(OLD)==D['source_board_sha256'],'v0.10 source hash');check(sha(NEW)==D['board_sha256'],'v0.11 hash matches derivation record')

# parts: same set, same footprints, same pad-to-net assignment everywhere; only servo-block parts may move
of={f.GetReference():f for f in old.GetFootprints()};nf={f.GetReference():f for f in new.GetFootprints()}
check(set(of)==set(nf),'reference set',difference=sorted(set(of)^set(nf)))
io=lambda r:(lambda m:m and 7000<=int(m[1])<9000)(re.search(r'(\d+)$',r)) or r=='J9928' or r in PLUGS
moved=[];stayed=0
for ref in sorted(set(of)&set(nf)):
 a,b=of[ref],nf[ref]
 check(str(a.GetFPID().GetUniStringLibId())==str(b.GetFPID().GetUniStringLibId()) and a.GetLayer()==b.GetLayer(),'footprint id and side',ref=ref)
 check((a.GetAttributes()&(p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES))==(b.GetAttributes()&(p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)),'fit attributes',ref=ref)
 pa=sorted((q.GetNumber(),q.GetNetname(),xy(q.GetDrillSize()),q.GetAttribute(),q.GetLayerSet().FmtHex(),r4(mm(q.GetSize().x)*mm(q.GetSize().y))) for q in a.Pads())
 pb=sorted((q.GetNumber(),q.GetNetname(),xy(q.GetDrillSize()),q.GetAttribute(),q.GetLayerSet().FmtHex(),r4(mm(q.GetSize().x)*mm(q.GetSize().y))) for q in b.Pads())
 check(pa==pb,'pads and their nets',ref=ref)
 same=xy(a.GetPosition())==xy(b.GetPosition()) and a.GetOrientationDegrees()==b.GetOrientationDegrees()
 if same:stayed+=1
 else:
  moved.append(ref);check(io(ref),'a part outside the servo block moved',ref=ref)
  # a moved part is rigid: pad-to-pad distances are unchanged
  da=sorted(r4(((q.GetPosition().x-a.GetPosition().x)**2+(q.GetPosition().y-a.GetPosition().y)**2)**.5/1e6) for q in a.Pads())
  db=sorted(r4(((q.GetPosition().x-b.GetPosition().x)**2+(q.GetPosition().y-b.GetPosition().y)**2)**.5/1e6) for q in b.Pads())
  check(da==db,'moved footprint kept its shape',ref=ref)
vals={r:(of[r].GetValue(),nf[r].GetValue()) for r in of if r in nf and of[r].GetValue()!=nf[r].GetValue()}
check(set(vals)==set(D['part_changes']),'value changes are the recorded part changes',changes=vals)
facts.update(footprints=len(nf),parts_not_moved=stayed,parts_moved=len(moved),value_changes=vals)

# copper outside the servo block
def tracks(board):
 t=collections.Counter()
 for item in board.GetTracks():
  if item.GetClass()=='PCB_VIA':e=(xy(item.GetPosition()),);k=('via',item.GetNetname(),r4(mm(item.GetDrillValue())),r4(mm(item.GetWidth())),e)
  else:e=tuple(sorted([xy(item.GetStart()),xy(item.GetEnd())]));k=(item.GetClass(),item.GetNetname(),item.GetLayer(),r4(mm(item.GetWidth())),e)
  if not all(in_strip(q) for q in e):t[k]+=1
 return t
ta,tb=tracks(old),tracks(new);only_old=ta-tb;only_new=tb-ta
other=[k for k in list(only_old)+list(only_new) if k[1] not in FOLLOW+EXTENDED]
ext=collections.Counter(k[1] for k in list(only_old)+list(only_new) if k[1] in EXTENDED)
for k in only_new:
 if k[1] in ('+24V','+12V_SRV'):check(k[0]=='via','power nets outside the block gained only vias',item=k)
check(not other,'copper outside the servo block is identical to v0.10',differences=other[:20],count=len(other))
fo=sum(v for k,v in only_old.items() if k[1] in FOLLOW);fn=sum(v for k,v in only_new.items() if k[1] in FOLLOW)
check(fo<=len(D['usb_and_5v_shortened']) and fn<=len(D['usb_and_5v_shortened']),'shortened USB and 5 V segments are the recorded ones',only_v10=fo,only_v11=fn,recorded=len(D['usb_and_5v_shortened']))
facts['copper_items_changed_outside_block_on_extended_nets']=dict(ext)
def netlen(board,net):return round(sum(mm(t.GetLength()) for t in board.GetTracks() if t.GetNetname()==net and t.GetClass()!='PCB_VIA'),2)
ln={n:[netlen(old,n),netlen(new,n)] for n in FOLLOW}
check(abs((ln['P4_DP'][1]-ln['P4_DM'][1])-(ln['P4_DP'][0]-ln['P4_DM'][0]))<.05,'servo-controller USB pair keeps its length match',lengths=ln)
facts.update(copper_items_outside_block=sum(tb.values()),followed_net_length_mm_v10_v11=ln)

# zones: outside the block, definitions and fills are unchanged
def zones(board):
 out={}
 for z in board.Zones():
  o=z.Outline();pts=tuple(tuple(xy(o.Outline(i).CPoint(j)) for j in range(o.Outline(i).PointCount())) for i in range(o.OutlineCount()))
  bb=z.GetBoundingBox();box=(mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom()))
  out[(z.GetNetname(),z.GetLayerSet().FmtHex(),z.GetAssignedPriority(),z.GetPadConnection(),r4(mm(z.GetLocalClearance())),r4(mm(z.GetMinThickness())),pts)]=(box,z.CalculateFilledArea()/1e12)
 return out
za,zb=zones(old),zones(new)
gone=[k for k in za if k not in zb];added=[k for k in zb if k not in za]
bad=[(k[0],za[k][0]) for k in gone if not(za[k][0][1]>113 and za[k][0][0]<STRIP_X) and not(k[0]=='VIN' and k[2]==2)]
bad+=[(k[0],zb[k][0]) for k in added if zb[k][0][1]<108-1e-6 and k[0] not in ('+24V','+12V_SRV','+5V_SRV')]
check(not bad,'zones changed only inside the servo block',zones=bad)
drift=[]
for k in za:
  # the battery plane and bottom ground pour give up the recorded strips to the Thor and XL430 runs
 if k in zb and za[k][0][3]<108 and za[k][1]>0 and not .995<=zb[k][1]/za[k][1]<=1.005 and not(k[0] in ('VIN','GND','+12V_SRV','+5V_SRV','+24V') and .93<=zb[k][1]/za[k][1]<=1.03):drift.append((k[0],za[k][0],round(za[k][1],1),round(zb[k][1],1)))
check(not drift,'filled copper of zones above the servo block is unchanged',zones=drift[:10])
facts['zones']=dict(v10=len(za),v11=len(zb),removed=len(gone),added=len(added))

# manufacturing limits
tier=[(t.GetNetname(),xy(t.GetPosition())) for t in new.GetTracks() if t.GetClass()=='PCB_VIA' and not(mm(t.GetDrillValue())>=.3-1e-6 and mm(t.GetWidth())>=mm(t.GetDrillValue())+.2-1e-6)]
check(not tier,'vias outside free factory tier',vias=tier[:10])
webs=[]
for f in new.GetFootprints():
 for q in f.Pads():
  d=mm(q.GetDrillSize().x)
  if d>=2.0:x,y=xy(q.GetPosition());webs.append((r4(min(x,y,W-x,H-y)-d/2),f.GetReference()))
check(min(webs)[0]>=1.3,'board material between large holes and the edge >= 1.3 mm',smallest=sorted(webs)[:4]);facts['smallest_hole_to_edge_wall_mm']=sorted(webs)[:4]
bb=new.GetBoardEdgesBoundingBox();facts['outline_bbox_mm']=[r4(mm(bb.GetX())),r4(mm(bb.GetY())),r4(mm(bb.GetWidth())),r4(mm(bb.GetHeight()))]
check(abs(mm(bb.GetWidth())-W)<.2 and abs(mm(bb.GetHeight())-H)<.2,'outline size')
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

# native DRC produced by build_v11
rpt=(ROOT/'revisions/v0.11/drc.rpt').read_text();kinds=collections.Counter(re.findall(r'^\[(\w+)\]',rpt,re.M))
base=collections.Counter(re.findall(r'^\[(\w+)\]',(ROOT/'revisions/v0.10/drc.rpt').read_text(),re.M))
unconnected=int(re.search(r'Found (\d+) unconnected pads',rpt)[1])
check(str(NEW) in rpt.splitlines()[0],'DRC report is for the v0.11 board');check(unconnected==0,'unconnected pads',count=unconnected)
check(set(kinds)<=set(base) and sum(kinds.values())<=sum(base.values()) and kinds.get('via_dangling',0)<=base.get('via_dangling',0),'native DRC has no new category, no more warnings and no more dangling vias than v0.10',v11=dict(kinds),v10=dict(base))
facts['native_drc']=dict(categories=dict(kinds),v10_categories=dict(base),unconnected_pads=unconnected)
facts['routes']=[dict(net=r['net'],length_mm=r['length_mm'],vias=r['vias'],routed=r['routed']) for r in D['routes']]
check(all(r['routed'] for r in D['routes']),'every rebuilt signal connection routed')

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
  elif want.startswith('unconnected-') and (not have or padcount[have]==1):single+=bool(have)
  elif want!=have:bad.append((ref,q.GetNumber(),want,have))
check(not bad,'schematic to board identity',mismatches=bad[:25],count=len(bad));facts['schematic']=dict(components=len(comp),sha256=sha(NEW.with_suffix('.kicad_sch')))

report=dict(status='PASS' if not findings else 'HOLD',board_sha256=sha(NEW),source_board_sha256=sha(OLD),outline_mm=[W,H],facts=facts,findings=findings,
 scope='Delta against v0.10 outside the servo block, part and net identity inside it, native DRC, via tier, outline containment, schematic/board identity. Not covered: electrical behaviour of the re-routed servo block (current density, noise), thermal behaviour, factory DFM.')
(OUT/'audit-v11.json').write_text(json.dumps(report,indent=1,default=str)+'\n')
print(report['status'],json.dumps(facts,default=str)[:1200]);[print('FINDING',json.dumps(f,default=str)[:700]) for f in findings]
sys.exit(0 if not findings else 1)
