"""Place functional legends on the final combined board, with body/mask checks.

Run on the composition before final routing. Never alters any copper, footprint or drill. A missing label
is a failed preparation step, not permission to silently omit a connection.
"""
import argparse,json,math,subprocess,sys,hashlib
from pathlib import Path
import pcbnew as p
from cells import Board
ROOT=Path(__file__).resolve().parents[2];K=ROOT/'revisions/v0.7/kicad'
parser=argparse.ArgumentParser();parser.add_argument('--board',type=Path,default=K/'robot_pdb.kicad_pcb');args=parser.parse_args()
composition=args.board.with_suffix('.composition.json')
provenance=json.loads(composition.read_text()) if composition.exists() else None
before_hash=hashlib.sha256(args.board.read_bytes()).hexdigest()
if provenance:assert provenance['composed_board_sha256']==before_hash,'Composition provenance stale before labeling'
b=p.LoadBoard(str(args.board));g=Board.__new__(Board);g.b=b
dead=[]
for d in list(b.GetDrawings()):
 if isinstance(d,p.PCB_TEXT):dead.append(d);b.Remove(d)
fps={f.GetReference():f for f in b.GetFootprints()}
def rect(bb):return tuple(p.ToMM(v) for v in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()))
def overlap(a,c,margin=.2):return not(a[2]+margin<c[0] or c[2]+margin<a[0] or a[3]+margin<c[1] or c[3]+margin<a[1])
bodies=[(f.GetReference(),rect(f.GetBoundingBox(False,False))) for f in fps.values() if not f.GetReference().startswith(('TP','JP')) and 'WirePort' not in str(f.GetFPID().GetUniStringLibId())]
mask=[rect(q.GetBoundingBox()) for f in fps.values() for q in f.Pads() if q.IsOnLayer(p.F_Mask)]
edge=rect(b.GetBoardEdgesBoundingBox());placed=[];failed=[]
def label(text,xy,ref='',size=1):
 offsets=sorted([(x,y) for x in (0,-1,1,-2,2,-3,3,-5,5,-8,8,-12,12,-16,16) for y in (0,-1,1,-2,2,-3,3,-5,5,-8,8,-12,12,-16,16)],key=lambda q:q[0]**2+q[1]**2)
 tx=p.PCB_TEXT(b);tx.SetText(text);tx.SetLayer(p.F_SilkS);tx.SetTextSize(p.VECTOR2I(p.FromMM(size),p.FromMM(size)));tx.SetTextThickness(p.FromMM(.15));b.Add(tx)
 for dx,dy in offsets:
  tx.SetPosition(p.VECTOR2I(p.FromMM(xy[0]+dx),p.FromMM(xy[1]+dy)));box=rect(tx.GetBoundingBox())
  if not(edge[0]+.5<box[0] and box[2]<edge[2]-.5 and edge[1]+.5<box[1] and box[3]<edge[3]-.5):continue
  if any(overlap(box,c,.15) for c in mask):continue
  if any(overlap(box,c,.2) for r,c in bodies):continue
  if any(overlap(box,c['bbox_mm'],.4) for c in placed):continue
  placed.append(dict(text=text,reference=ref,xy_mm=[xy[0]+dx,xy[1]+dy],bbox_mm=box,size_mm=size));return
 dead.append(tx);b.Remove(tx);failed.append(dict(text=text,reference=ref,requested_xy_mm=xy))
for text,xy,ref in [
 ('PACK A',(61.6,107),'J1'),('PACK B',(82.6,107),'J4'),
 ('A IN',(17,129),'J5.1'),('A OUT',(17,94),'J5.2'),('B IN',(33,129),'J5.3'),('B OUT',(33,94),'J5.4'),
 ('THOR 24V',(50,98),'J3'),('PI 5V',(100.5,18),'J101'),('AUX 11V7',(168.5,18),'J501'),
 ('MOTOR 15A',(14,20),'F1'),('LOGIC 30A',(29,20),'F2'),
 ('PWM 5A',(110,148),'F7000'),('USB 5A',(272,141),'F8000'),
 ('XL330 A 5V',(95.56,131),'J301'),('XL330 B 5V',(113.96,131),'J302'),
 ('XL430 A 10V8',(140.56,131),'J401'),('XL430 B 10V8',(158.46,131),'J402'),
 ('SPEAKER L',(218,60),'J13'),('SPEAKER R',(218,38),'J14'),
 ('MOTOR L 22V3',(289.6,121),'J6002'),('MOTOR R 22V3',(310.6,121),'J6003'),
 ('BRAKE 3R3',(328.6,116),'J6004'),('THERMAL NC',(284.27,42),'J6005'),
 ('CAN LEFT',(312,24),'J6007'),('CAN RIGHT',(326,24),'J6008'),
 ('SERVO 1',(26,225),'J7004'),('SERVO 2',(37,225),'J7005'),('SERVO 3',(48,225),'J7006'),
 ('CAN SWD',(45,212),'J7007'),('PWM SWD',(80,212),'J7008')]:label(text,xy,ref)
for ref,title in [('J9500','USB TO JETSON'),('J9501','OAK-D USB3'),('J9502','USB MIC'),('J9505','BMS USB RESERVE')]:
 f=fps[ref];bb=rect(f.GetBoundingBox(False,False));label(title,((bb[0]+bb[2])/2,bb[1]-2),ref)
for ref,title in [('JP1','THOR OFF'),('JP101','PI OFF'),('JP301','XL330 OFF'),('JP401','XL430 OFF'),('JP501','AUDIO OFF'),('JP6001','MOTOR OFF'),('JP7101','PWM 5V OFF'),('JP8001','USB 5V OFF')]:
 f=fps[ref];x,y=p.ToMM(f.GetPosition());label(ref+' '+title,(x,y-2),ref)
for r in ('J1','J4','J6002','J6003','J6004'):
 for q in fps[r].Pads():
  if not q.GetNumber():continue
  xy=p.ToMM(q.GetPosition());text='GND' if q.GetNetname()=='GND' else ('R-' if q.GetNetname()=='M_DUMP_LOW' else '+')
  label(text,(xy[0],xy[1]+5.5),r+'.'+q.GetNumber())
for r in ('J7004','J7005','J7006'):
 for q in fps[r].Pads():
  if not q.GetNumber():continue
  xy=p.ToMM(q.GetPosition());label({'1':'G','2':'+','3':'S'}[q.GetNumber()],(xy[0]-3,xy[1]),r+'.'+q.GetNumber())
for text,xy in [('ROBOT PDB v0.7',(310,145)),('STOP BEFORE MASTER OFF',(310,149)),('OFF JUMPERS: CLOSE = OFF',(310,153))]:label(text,xy,size=1.2)
evidence=dict(status='PASS' if not failed else 'FAIL',placed=placed,failed=failed,limitations=['Body bounds and nominal mask openings are conservative placement screens. Inspect actual final plots and native silk warnings.','Artwork does not establish wiring correctness; verify every external cable and polarity before applying power.'])
(K.parent/'label-audit.json').write_text(json.dumps(evidence,indent=2)+'\n')
assert not failed,failed
profile=args.board.with_suffix('.kicad_pro');profile_bytes=profile.read_bytes() if profile.exists() else None
try:p.SaveBoard(str(args.board),b)
finally:
 if profile_bytes is not None:profile.write_bytes(profile_bytes)
subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(args.board),str(args.board.with_suffix('.label-drc.rpt'))],check=True)
if provenance:
 provenance.update(pre_label_board_sha256=before_hash,composed_board_sha256=hashlib.sha256(args.board.read_bytes()).hexdigest(),label_generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
 composition.write_text(json.dumps(provenance,indent=2)+'\n')
print('Placed',len(placed),'functional legends')
