"""Functional silkscreen for the v0.9 composition; never changes copper."""
import math
import pcbnew as p

def add_labels(board):
 fps={f.GetReference():f for f in board.GetFootprints()}
 def rect(bb):return tuple(p.ToMM(v) for v in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom()))
 def overlap(a,b,gap):return not(a[2]+gap<b[0] or b[2]+gap<a[0] or a[3]+gap<b[1] or b[3]+gap<a[1])
 bodies=[rect(f.GetBoundingBox(False,False)) for r,f in fps.items() if not r.startswith(('TP','JP')) and 'WirePort' not in str(f.GetFPID().GetUniStringLibId())]
 mask=[rect(q.GetBoundingBox()) for f in fps.values() for q in f.Pads() if q.IsOnLayer(p.F_Mask)]
 edge=rect(board.GetBoardEdgesBoundingBox());placed=[];dead=[]
 existing=[rect(d.GetBoundingBox()) for d in board.GetDrawings() if isinstance(d,p.PCB_TEXT) and d.GetLayer()==p.F_SilkS]
 def label(text,where,ref,size=1.0):
  tx=p.PCB_TEXT(board);tx.SetText(text);tx.SetLayer(p.F_SilkS);tx.SetTextSize(p.VECTOR2I(p.FromMM(size),p.FromMM(size)));tx.SetTextThickness(p.FromMM(.15));board.Add(tx)
  offsets=sorted([(x,y) for x in (0,-1,1,-2,2,-3,3,-5,5,-8,8,-12,12,-16,16,-24,24,-32,32) for y in (0,-1,1,-2,2,-3,3,-5,5,-8,8,-12,12,-16,16,-24,24,-32,32)],key=lambda q:q[0]**2+q[1]**2)
  for dx,dy in offsets:
   tx.SetPosition(p.VECTOR2I(p.FromMM(where[0]+dx),p.FromMM(where[1]+dy)));box=rect(tx.GetBoundingBox())
   if not(edge[0]+.5<box[0] and box[2]<edge[2]-.5 and edge[1]+.5<box[1] and box[3]<edge[3]-.5):continue
   if any(overlap(box,c,.15) for c in mask) or any(overlap(box,c,.2) for c in bodies):continue
   if any(overlap(box,c,.35) for c in existing) or any(overlap(box,c['bbox_mm'],.35) for c in placed):continue
   placed.append(dict(text=text,reference=ref,xy_mm=p.ToMM(tx.GetPosition()),bbox_mm=box,size_mm=size));return
  dead.append(tx);board.Remove(tx);raise RuntimeError(('No clear functional legend position',ref,text))
 def near(ref,text):
  f=fps[ref];bb=rect(f.GetBoundingBox(False,False));label(ref+' '+text,((bb[0]+bb[2])/2,bb[1]-2),ref)
 for ref,title in [
  ('J1','PACK A'),('J4','PACK B'),('J2','BATTERY MOTOR OUT'),('J3','THOR 24V'),('J101','PI 5V'),('J501','AUX 11V7'),
  ('J301','XL330 A 5V'),('J302','XL330 B 5V'),('J401','XL430 A 10V8'),('J402','XL430 B 10V8'),
  ('J10','USB2 TO JETSON'),('J13','SPKR L'),('J14','SPKR R'),
  ('J7004','SERVO 1'),('J7005','SERVO 2'),('J7006','SERVO 3'),
  ('J7008','PWM SWD'),('F1','MOTOR 30A'),('F2','LOGIC 30A'),('F7000','PWM 5A'),
  ('J9921','THOR OFF'),('J9922','PI OFF'),('J9923','USB OFF'),('J9924','XL330 OFF'),('J9925','XL430 OFF'),
  ('J9926','AUDIO OFF'),('J9928','SERVO OFF')]:near(ref,title)
 for pin,title,net in [('1','A IN','PACK_A_POS'),('2','A OUT','VBAT'),('3','B IN','PACK_B_POS'),('4','B OUT','VBAT')]:
  pad=next(q for q in fps['J5'].Pads() if q.GetNumber()==pin);assert pad.GetNetname()==net
  x,y=p.ToMM(pad.GetPosition());label('J5.'+pin+' '+title,(x,y-5),'J5.'+pin)
 for ref in ('J1','J4','J2'):
  for pad in fps[ref].Pads():
   if not pad.GetNumber():continue
   x,y=p.ToMM(pad.GetPosition());text='GND' if pad.GetNetname()=='GND' else ('R-' if pad.GetNetname()=='M_DUMP_LOW' else '+')
   label(ref+'.'+pad.GetNumber()+' '+text,(x,y+5.5),ref+'.'+pad.GetNumber(),1.0)
 for ref in ('J7004','J7005','J7006'):
  near(ref,'1G 2+ 3S')
 return dict(status='PASS',placed=placed,limitations=['Conservative body/mask/legend bounds, not physical cable access qualification. Inspect final plots and delivered board.','Every label includes its connector reference when placement shifts away from the first candidate position.'])
