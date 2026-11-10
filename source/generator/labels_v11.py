"""Silkscreen labels for v0.11: written for someone wiring the board while distracted.

Every board-level label is removed and placed again from the table below. Each
label names an anchor (a footprint, one of its pads, or a point) and a
preferred side; the placer takes the nearest spot on that side where the text
touches no pad, hole, part body, other label or board edge. Nothing but
silkscreen changes.
"""
import pcbnew as p
mm=p.ToMM;MM=p.FromMM

LEGEND=[
 'ROBOT POWER BOARD v0.11  2026-11',
 'BATTERY 27-33.6V. FUSE EACH PACK',
 'CHECK POLARITY BEFORE POWER',
 'JUMPER FITTED = THAT SUPPLY OFF',
 'MOTOR OUT = RAW BATTERY VOLTAGE',
 'STOP MOTORS BEFORE MASTER OFF',
 'CAMERA + MIC PLUG INTO JETSON',
]
LEGEND_AT=(157.0,64.0);LEGEND_H=1.1;LEGEND_PITCH=2.6

# (text, anchor, side, height mm).  anchor: 'REF', 'REF.pad', or (x, y).  side: N S E W
LABELS=[
 # battery side
 ('PACK A IN','J1','N',1.4),('+','J1.2','S',2.0),('GND','J1.1','S',1.3),
 ('PACK B IN','J4','N',1.4),('+','J4.2','S',2.0),('GND','J4.1','S',1.3),
 ('A+ TO SWITCH',(17.0,106.9),'N',1.1),('A+ FROM SWITCH',(17.0,71.8),'N',1.1),
 ('B+ TO SWITCH',(33.0,106.9),'N',1.1),('B+ FROM SWITCH',(33.0,71.8),'N',1.1),
 ('GND','J2.1','N',1.2),('BATT+','J2.2','S',1.2),('MOTOR OUT','J2.2','S',1.15),
 ('F1 MOTOR FUSE 30A','F1.1','N',1.1),('F2 ELECTRONICS FUSE 30A','F2.2','N',1.1),
 # outputs
 ('THOR 24V 8A','J3','N',1.4),('EDGE PINS +24V','J3','S',1.0),('INNER PINS GND','J3','S',0.99),
 ('SPARE 5V 5A','J101','N',1.3),('AUX 11.7V 5A','J501','N',1.3),
 ('XL330 A: GND 5V DATA','J301','N',1.0),('XL330 B: GND 5V DATA','J302','N',1.0),
 ('XL430 A: GND 10V8 DATA','J401','N',1.0),('XL430 B: GND 10V8 DATA','J402','N',1.0),
 ('SPEAKER R','J14','W',1.2),('R+','J14.2','W',1.0),('R-','J14.1','W',1.0),
 ('SPEAKER L','J13','W',1.2),('L+','J13.2','W',1.0),('L-','J13.1','W',1.0),
 ('USB-C TO JETSON','J10','W',1.2),
 # hobby servos
 ('SERVO 1','J7004','N',0.9),('SERVO 2','J7005','N',0.9),('SERVO 3','J7006','N',0.9),('GND 5V SIG','J7004','S',0.8),('GND 5V SIG','J7005','S',0.8),('GND 5V SIG','J7006','S',0.8),
 ('PROG: 3V3 GND DIO CLK RST','J7008','S',0.8),
 ('F7000 SERVO FUSE 5A','F7000','N',1.1),
 ('BOOT','JP7003','N',0.9),('RESET','JP7005','S',0.9),
 # off jumpers
 ('THOR OFF','J9921','E',1.0),('SPARE 5V OFF','J9922','S',1.0),('USB 5V OFF','J9923','S',1.0),
 ('XL330 OFF','J9924','N',1.0),('XL430 OFF','J9925','N',1.0),('AUX+AUDIO OFF','J9926','S',1.0),('SERVO OFF','J9928','E',1.0),
 # indicator lights
 ('LED BATTERY','D2','N',0.9),('LED 24V','D3','S',0.9),('LED SPARE 5V','D102','E',0.9),('LED USB 5V','D202','E',0.9),
 ('LED XL330','D302','S',0.9),('LED XL430','D402','S',0.9),('LED AUX','D502','E',0.9),('LED USB HUB','D60','N',0.9),('LED SERVO 5V','D7102','E',0.9),
 # test points
 ('TP BATT','TP1','E',0.9),('TP GND','TP2','E',0.9),('TP 24V','TP4','E',0.9),('TP 5V','TP101','E',0.9),('TP USB5V','TP201','E',0.9),
 ('TP 5V','TP301','E',0.9),('TP 10V8','TP401','E',0.9),('TP 11V7','TP501','E',0.9),('TP 3V3','TP7002','N',0.9),('TP GND','TP7004','E',0.9),('TP 5V','TP7101','E',0.9),
 # hand-fit
 ('FIT U9903 BY HAND','U9903','S',0.9),
]

def apply(b,W,H,drop):
 """Replace the board-level silkscreen texts. `drop(item)` removes an item from the board."""
 fps={f.GetReference():f for f in b.GetFootprints()}
 for d in list(b.GetDrawings()):
  if d.GetClass()=='PCB_TEXT' and d.GetLayer()==p.F_SilkS:drop(d)
 box=lambda bb,g=0:(mm(bb.GetX())-g,mm(bb.GetY())-g,mm(bb.GetRight())+g,mm(bb.GetBottom())+g)
 hard=[];bodies={}
 for f in b.GetFootprints():
  for q in f.Pads():hard.append(box(q.GetBoundingBox(),.25))
  for g in f.GraphicalItems():
   if g.GetLayer()!=p.F_SilkS:continue
   if g.GetClass()=='FP_TEXT':
    if g.IsVisible():hard.append(box(g.GetBoundingBox(),.15))
   else:hard.append(box(g.GetBoundingBox(),.1))
  c=f.GetCourtyard(p.F_Cu)
  if c.OutlineCount():bodies[f.GetReference()]=box(c.BBox())
 hard+=list(bodies.values())
 placed=[];log=[];misses=[]
 def hit(r):
  if r[0]<.8 or r[1]<.8 or r[2]>W-.8 or r[3]>H-.8:return True
  for o in hard:
   if r[0]<o[2] and o[0]<r[2] and r[1]<o[3] and o[1]<r[3]:return True
  for o in placed:
   if r[0]<o[2] and o[0]<r[2] and r[1]<o[3] and o[1]<r[3]:return True
  return False
 def make(text,h,x,y):
  t=p.PCB_TEXT(b);t.SetText(text);t.SetTextSize(p.VECTOR2I(MM(h),MM(h)));t.SetTextThickness(MM(max(.15,h*.15)));t.SetLayer(p.F_SilkS);t.SetPosition(p.VECTOR2I(MM(x),MM(y)));return t
 def put(text,anchor,side,h,reach=14.0):
  if isinstance(anchor,tuple):ax,ay=anchor;span=(0,0)
  else:
   ref,_,pad=anchor.partition('.');f=fps[ref]
   if pad:
    q=next(q for q in f.Pads() if q.GetNumber()==pad);ax,ay=mm(q.GetPosition().x),mm(q.GetPosition().y);span=(mm(q.GetBoundingBox().GetWidth())/2,mm(q.GetBoundingBox().GetHeight())/2)
   else:
    bb=bodies.get(ref) or box(f.GetBoundingBox(False,False));ax,ay=(bb[0]+bb[2])/2,(bb[1]+bb[3])/2;span=((bb[2]-bb[0])/2,(bb[3]-bb[1])/2)
  bb=make(text,h,0,0).GetBoundingBox();w,th=mm(bb.GetWidth()),mm(bb.GetHeight());best=None
  dirs={'N':(0,-1),'S':(0,1),'E':(1,0),'W':(-1,0)}
  if side=='C':cands=[(ax,ay,0)]
  else:
   cands=[]
   for rank,s in enumerate([side]+[s for s in 'NSEW' if s!=side]):
    dx,dy=dirs[s]
    for k in range(int(reach/.25)):
     d=k*.25
     for slide in (0,.5,-.5,1,-1,1.5,-1.5,2.5,-2.5,4,-4,6,-6):
      cands.append((ax+dx*(span[0]+w/2+.4+d)+(slide if dx==0 else 0),ay+dy*(span[1]+th/2+.4+d)+(slide if dy==0 else 0),d+abs(slide)*.6+rank*5))
  for cx,cy,cost in sorted(cands,key=lambda c:c[2]):
   r=(cx-w/2,cy-th/2,cx+w/2,cy+th/2)
   if not hit(r):best=(cx,cy,cost,r);break
  if not best:misses.append(text+' @ '+str(anchor));return
  b.Add(make(text,h,best[0],best[1]))
  placed.append((best[3][0]-.3,best[3][1]-.3,best[3][2]+.3,best[3][3]+.3));log.append(dict(text=text,anchor=str(anchor),height_mm=h,at_mm=[round(best[0],2),round(best[1],2)],search_cost=round(best[2],2)))
 for k,line in enumerate(LEGEND):put(line,(LEGEND_AT[0],LEGEND_AT[1]+k*LEGEND_PITCH),'C',LEGEND_H)
 for text,anchor,side,h in sorted(LABELS,key=lambda l:-l[3]):put(text,anchor,side,h)
 return dict(placed=log,not_placed=misses)
