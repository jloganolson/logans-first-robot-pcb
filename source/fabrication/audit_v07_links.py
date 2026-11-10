"""Independent v0.7 intercell connectivity and copper/reference sampling.

Uses native copper adjacency plus each individual filled-zone island, never
matching net names alone. Sampling reports geometry, not qualified ampacity.
"""
import json,sys,math,hashlib
from pathlib import Path
import pcbnew as p

ROOT=Path(__file__).resolve().parents[2];K=ROOT/'revisions/v0.7/kicad'
board=Path(sys.argv[1]) if len(sys.argv)>1 else K/'robot_pdb.kicad_pcb'
b=p.LoadBoard(str(board));cn=b.GetConnectivity();cn.Build(b)
fps={f.GetReference():f for f in b.GetFootprints()}
def uid(x):return x.m_Uuid.AsString()
parent={}
def find(q):
 parent.setdefault(q,q)
 if parent[q]!=q:parent[q]=find(parent[q])
 return parent[q]
def union(a,c):parent[find(a)]=find(c)
def pad(r,n):return next(q for q in fps[r].Pads() if q.GetNumber()==str(n))
links=[('MOTOR_FUSED_INPUT',('F1',1),('Q9910',2)),('MOTOR_VIN',('Q9910',5),('C6014',1)),
 ('VIN',('Q1',5),('F7000',1)),('VIN',('Q1',5),('F8000',1)),('PWM_VIN',('F7000',2),('C7111',1)),
 ('USB_POWER_VIN',('F8000',2),('C8014',1)),('+5_USB_RAW',('L8001',2),('C9546',1)),('+5_USB_RAW',('L8001',2),('U9900',1)),
 ('CHILD_LIMITED_5V',('U9900',6),('FB1',1)),('V5_USB',('FB1',2),('U7005',1)),('V5_USB',('FB1',2),('U7006',1)),
 ('H_V33',('U10',20),('U9901',8)),('H_V33',('U9901',8),('U9901',7)),('CHILD_EE_SCL',('U10',13),('U9901',6)),
 ('CHILD_EE_SDA',('U10',21),('U9901',5)),('CHILD_PRT_CTL',('U9500',36),('U9900',4)),
 ('CHILD_PRT_CTL',('U9900',4),('R9905',1)),('CHILD_SWITCH_EN',('R9905',2),('U9900',3)),('CHILD_SWITCH_EN',('U9900',3),('C9904',1)),
 ('P3_DP',('U10',8),('U7001',33)),('P3_DM',('U10',7),('U7001',32)),('P4_DP',('U10',6),('U7002',33)),('P4_DM',('U10',5),('U7002',32)),
 ('HUB_CHILD_DP',('U10',15),('U9500',1)),('HUB_CHILD_DM',('U10',14),('U9500',2)),
 ('CAN_H',('U7004',7),('J6007',2)),('CAN_L',('U7004',6),('J6007',3)),
 ('H_LED',('U10',22),('D60',1)),('H_XI',('U10',4),('Y1',1)),('V5_USB',('U10',19),('C62',1))]
support_ground_refs={'U9900','U9901','C9900','C9901','C9902','C9903','C9904','R9902','U9910','C9910','C9911'}
nets={x[0] for x in links};items=[q for f in b.GetFootprints() for q in f.Pads() if q.GetNetname() in nets]+[t for t in b.GetTracks() if t.GetNetname() in nets]
#Follow each added ground's real local copper to its plane via. Enumerating
#every unrelated board ground island is unnecessary and prohibitively slow.
pending=[q for ref in support_ground_refs for q in fps[ref].Pads() if q.GetNetname()=='GND']+[pad('J1',1)];ground_seen=set()
while pending:
 q=pending.pop();key=uid(q)
 if key in ground_seen:continue
 ground_seen.add(key);items.append(q)
 for other in list(cn.GetConnectedTracks(q))+list(cn.GetConnectedPads(q)):
  if other.GetNetname()=='GND':union(key,uid(other));pending.append(other)
nets.add('GND')
for q in items:
 for other in list(cn.GetConnectedTracks(q))+list(cn.GetConnectedPads(q)):
  if other.GetNetname()==q.GetNetname():union(uid(q),uid(other))
# Each disconnected filled island is a distinct node, even if its net name
# and parent-zone UUID match. Holes in the fill remain excluded by Contains.
zones=[]
for z in b.Zones():
 if z.GetNetname() not in nets:continue
 ps=z.GetFilledPolysList(z.GetLayer())
 for index in range(ps.OutlineCount()):
  group=[]
  for q in items:
   if q.GetNetname()!=z.GetNetname() or not q.IsOnLayer(z.GetLayer()):continue
   xy=[q.GetPosition()] if q.GetClass() in ('PAD','PCB_VIA') else [q.GetStart(),q.GetEnd(),p.VECTOR2I((q.GetStart().x+q.GetEnd().x)//2,(q.GetStart().y+q.GetEnd().y)//2)]
   if any(ps.Contains(v,index) for v in xy):group.append(uid(q))
  if z.GetNetname()=='GND' and not group:continue
  island_id=f'zone:{uid(z)}:{index}';island=ps.UnitSet(index)
  zones.append((z.GetNetname(),z.GetLayer(),island_id,island))
  for q in group:union(island_id,q)
for i,(net,layer,node,poly) in enumerate(zones):
 for n2,l2,node2,poly2 in zones[i+1:]:
  if n2==net and l2==layer and poly.Collide(poly2):union(node,node2)
results=[]
for n,a,c in links:
 if a[0] not in fps or c[0] not in fps:results.append({'net':n,'from':a,'to':c,'connected':False,'reason':'missing footprint'});continue
 x,y=pad(*a),pad(*c)
 results.append({'net':n,'from':a,'to':c,'connected':x.GetNetname()==n==y.GetNetname() and find(uid(x))==find(uid(y))})
auxiliary=[('MOTOR_FUSED_INPUT',('F1',1),('U9910',3)),('MOTOR_FUSED_INPUT',('F1',1),('U9910',6)),('MOTOR_FUSED_INPUT',('F1',1),('C9910',1)),('MOTOR_FUSED_INPUT',('F1',1),('C9911',2)),('MOTOR_VIN',('Q9910',5),('U9910',4)),('+5_USB_RAW',('U9900',1),('C9900',1)),('+5_USB_RAW',('U9900',1),('C9901',1)),('V5_USB',('FB1',2),('C9902',1))]
aux_results=[]
for n,a,c in auxiliary:
 x,y=pad(*a),pad(*c);aux_results.append({'net':n,'from':a,'to':c,'connected':x.GetNetname()==n==y.GetNetname() and find(uid(x))==find(uid(y))})
ground_anchor=pad('J1',1);ground_results=[]
for ref in sorted(support_ground_refs):
 for q in fps[ref].Pads():
  if q.GetNetname()=='GND':ground_results.append({'reference':ref,'pin':q.GetNumber(),'connected':ground_anchor.GetNetname()=='GND' and find(uid(q))==find(uid(ground_anchor))})
report={'support_ground_links':ground_results,'support_grounds_connected':sum(x['connected'] for x in ground_results),'support_grounds_total':len(ground_results),'auxiliary_support_links':aux_results,'auxiliary_connected':sum(x['connected'] for x in aux_results),'auxiliary_total':len(aux_results),'board':str(board),'board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),'links':results,'connected':sum(x['connected'] for x in results),'total':len(results),
 'method':'Native pad/track adjacency plus individual filled-zone island membership. Matching names alone never create an edge.',
 'limits':'Filled-zone membership samples item anchors; native DRC remains authoritative for all unsampled edge contacts. This does not establish thermal current rating, fuse I-squared-t coordination, or USB eye compliance.'}
output=Path(sys.argv[2]) if len(sys.argv)>2 else K.parent;output.mkdir(parents=True,exist_ok=True)
path=output/'intercell-connectivity-audit.json';path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'connected':report['connected'],'total':report['total'],'missing':[x for x in results if not x['connected']]},indent=2))
