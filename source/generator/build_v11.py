"""Derive the compact v0.11 board from the saved v0.10 board.

Run through source/fabrication/with_kicad.sh. v0.10 is not modified.

v0.10 kept the hobby-servo block where the old cell composition put it, which
left the lower-right quarter of the board empty. v0.11 re-floorplans that block
only. The main board (everything above y = 112 mm, and the USB block on the
right) is not touched. Inside the servo block each sub-circuit keeps its own
proven copper and is moved as a rigid piece:

  A   servo 5 V buck converter      rotated 90 degrees into the bottom-left corner
  IN  its input bulk capacitor/TVS  beside the buck input
  F   its 5 A fuse                  beside the buck instead of 150 mm away
  C   PWM output buffer             next to the servo power
  J   three servo headers           on the bottom edge
  B   servo controller MCU + USB    moved right, next to the USB hub
  S   SWD programming header        bottom edge beside the MCU

Connections between those pieces are removed and rebuilt: power on planes,
signals with the project's grid maze router. The USB pair and 5 V feed to the
MCU keep their existing copper and are simply shortened.

Also in this revision: L1 returns to the 60 V Coilcraft XAL1510-103.
Every step is recorded in revisions/v0.11/derivation.json.
"""
import collections,hashlib,heapq,json,math,re,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p
sys.path.insert(0,str(Path(__file__).resolve().parent))
from robot_io_router import RobotIOFixer

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'revisions/v0.10/kicad';DST=ROOT/'revisions/v0.11/kicad'
SRC_SHA='1b3bcccac46a0f5773c472aa492ede3c1351764b9f63c53f64ded7864630e90c'
W,H=228.0,155.0
mm=p.ToMM;MM=p.FromMM
def V(x,y):return p.VECTOR2I(MM(x),MM(y))
def xy(v):return (mm(v.x),mm(v.y))
def sha(q):return hashlib.sha256(Path(q).read_bytes()).hexdigest()

# ---- sub-circuits, as boxes in v0.10 coordinates -------------------------------------------------
BOX=dict(
 A =(4.5,116.8,42.8,162.6),      # servo buck
 IN=(2.5,162.7,19.6,175.0),      # C7111 with its PWM_VIN vias
 TV=(12.5,175.0,21.5,186.0),     # D7001
 C =(52.0,164.4,78.2,192.6),     # output buffer
 B =(76.4,126.8,107.2,164.3),    # MCU
)
B_SHIFT=(51.0,-12.0)             # MCU block: pure translation; P4 and V5_USB copper is shortened to match
SIGNAL_NETS=('IO_PWM1_MCU','IO_PWM2_MCU','IO_PWM3_MCU','IO_SERVO_ARM','IO_PWM1_OUT','IO_PWM2_OUT','IO_PWM3_OUT',
             'IO_PWM_SWDIO','IO_PWM_SWCLK','IO_PWM_NRST','IO_V3_PWM')
POWER_NETS=('PWM_VIN','PWM_5V')
PART_CHANGES={'L1':dict(value='10uH 22A 60V',lcsc='C3911782',mpn='Coilcraft XAL1510-103MED',
  old=dict(value='10uH FEXL1510A-100M',lcsc='C5378597',mpn='cjiang FEXL1510A-100M'))}

class Router(RobotIOFixer):
 """The project's maze router, generalised to start and end on either outer layer."""
 LAYERS=(p.F_Cu,p.B_Cu)
 def path(self,net,a,la,b,lb,w=.2,step=.1,win=8.0,budget=900000,via=(.6,.3)):
  (ax,ay),(bx,by)=a,b
  x0,y0=min(ax,bx)-win,min(ay,by)-win
  nx,ny=int((abs(ax-bx)+2*win)/step)+1,int((abs(ay-by)+2*win)/step)+1
  g=lambda i,j:(x0+i*step,y0+j*step)
  si,sj=round((ax-x0)/step),round((ay-y0)/step);ti,tj=round((bx-x0)/step),round((by-y0)/step)
  cache={};vcache={}
  def ok(i,j,L):
   k=(i,j,L)
   if k not in cache:
    x,y=g(i,j)
    # the first and last few steps sit on the net's own pad or track end
    cache[k]=(abs(i-si)+abs(j-sj)<=2 and L in la) or (abs(i-ti)+abs(j-tj)<=2 and L in lb) or self.free(self.LAYERS[L],net,x,y,w/2)
   return cache[k]
  def vok(i,j):
   if (i,j) not in vcache:
    x,y=g(i,j);vcache[(i,j)]=all(self.free(L,net,x,y,via[0]/2) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)) and self.hole_ok(x,y,via[1])
   return vcache[(i,j)]
  h=lambda n:math.hypot(n[0]-ti,n[1]-tj)
  openq=[];came={};cost={}
  for L in la:
   s=(si,sj,L);came[s]=None;cost[s]=0;heapq.heappush(openq,(h(s),0,s))
  found=None;it=0
  while openq and it<budget:
   it+=1;_,c,n=heapq.heappop(openq)
   if n[0]==ti and n[1]==tj and n[2] in lb:found=n;break
   if c>cost.get(n,1e18):continue
   i,j,L=n
   for di,dj in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
    m=(i+di,j+dj,L)
    if 0<=m[0]<nx and 0<=m[1]<ny and ok(*m):
     nc=c+math.hypot(di,dj)
     if nc<cost.get(m,1e18):cost[m]=nc;came[m]=n;heapq.heappush(openq,(nc+h(m),nc,m))
   if vok(i,j):
    m=(i,j,1-L);nc=c+25
    if nc<cost.get(m,1e18):cost[m]=nc;came[m]=n;heapq.heappush(openq,(nc+h(m),nc,m))
  if not found:return None
  nodes=[];n=found
  while n:nodes.append(n);n=came[n]
  nodes.reverse();runs=[];cur=[nodes[0]]
  for q in nodes[1:]:
   if q[2]!=cur[-1][2]:runs.append(cur);cur=[q]
   else:cur.append(q)
  runs.append(cur);out=[]
  for k,r in enumerate(runs):
   pts=[g(i,j) for i,j,_ in r];simp=[pts[0]]
   for q in range(1,len(pts)-1):
    d1=(pts[q][0]-simp[-1][0],pts[q][1]-simp[-1][1]);d2=(pts[q+1][0]-pts[q][0],pts[q+1][1]-pts[q][1])
    if abs(d1[0]*d2[1]-d1[1]*d2[0])>1e-9:simp.append(pts[q])
   simp.append(pts[-1])
   if k==0:simp[0]=(ax,ay)
   if k==len(runs)-1:simp[-1]=(bx,by)
   out.append((r[0][2],simp))
  return out
 def hole_ok(self,x,y,drill):
  for t in self._items(p.F_Cu,'',x,y,2.5):
   if t.GetClass()=='PCB_VIA':
    if math.dist((x,y),xy(t.GetPosition()))<(drill+mm(t.GetDrillValue()))/2+.46:return False
   elif t.GetClass()=='PAD':
    hole=max(mm(t.GetDrillSize().x),mm(t.GetDrillSize().y))
    if hole and math.dist((x,y),xy(t.GetPosition()))<(drill+hole)/2+.46:return False
  return True
 def lay(self,net,runs,w,via=(.6,.3)):
  ni=self.b.FindNet(net);n=0
  for k,(L,pts) in enumerate(runs):
   for a,c in zip(pts,pts[1:]):
    if math.dist(a,c)<1e-6:continue
    t=p.PCB_TRACK(self.b);t.SetStart(V(*a));t.SetEnd(V(*c));t.SetWidth(MM(w));t.SetLayer(self.LAYERS[L]);t.SetNet(ni);self.b.Add(t);n+=math.dist(a,c)
   if k<len(runs)-1:
    v=p.PCB_VIA(self.b);v.SetPosition(V(*pts[-1]));v.SetWidth(MM(via[0]));v.SetDrill(MM(via[1]));v.SetNet(ni);self.b.Add(v)
  self._index=None;return n

def main(stage='all'):
 src=SRC/'robot_pdb.kicad_pcb';assert sha(src)==SRC_SHA,'v0.10 board is not the reviewed copy'
 if DST.exists():shutil.rmtree(DST)
 shutil.copytree(SRC,DST);out=DST/'robot_pdb.kicad_pcb';b=p.LoadBoard(str(out));dead=[];log=dict(source_board_sha256=SRC_SHA,outline_mm=[W,H])
 profile=(SRC/'robot_pdb.kicad_pro').read_bytes()
 fps={f.GetReference():f for f in b.GetFootprints()}
 def rm(item):dead.append(item);b.Remove(item)
 def inbox(q,box,pad=0):return box[0]-pad<=q[0]<=box[2]+pad and box[1]-pad<=q[1]<=box[3]+pad
 def ends(t):return [xy(t.GetPosition())] if t.GetClass()=='PCB_VIA' else [xy(t.GetStart()),xy(t.GetEnd())]
 def home(t):
  for name,box in BOX.items():
   if all(inbox(q,box) for q in ends(t)):return name
  return None
 io_ref=lambda r:(lambda m:m and 7000<=int(m[1])<9000)(re.search(r'(\d+)$',r))
 ionets={q.GetNetname() for r,f in fps.items() if io_ref(r) for q in f.Pads() if q.GetNetname()}-{'GND','VIN','V5_USB','P4_DP','P4_DM'}

 # ---- 1. sort every item of the servo block into its sub-circuit, drop what joined them ----
 member=collections.defaultdict(list)
 for r,f in fps.items():
  if not io_ref(r):continue
  q=xy(f.GetPosition());k=next((n for n,box in BOX.items() if inbox(q,box)),None)
  if r in ('C7111',):k='IN'
  if r=='D7001':k='TV'
  member[k].append(f)
 loose=sorted(f.GetReference() for f in member.pop(None,[]))
 removed=collections.Counter();tails={'P4_DP':[],'P4_DM':[],'V5_USB':[]}
 for t in list(b.GetTracks()):
  n=t.GetNetname();e=ends(t)
  if n in ('P4_DP','P4_DM','V5_USB'):
   if all(q[1]>117.0 and q[0]<115.5 for q in e):tails[n].append(t);member['B'].append(t)     # copper that travels with the MCU
   continue
  if n in ionets or (n=='GND' and all(q[1]>113.5 and q[0]<178 for q in e)):
   k=home(t)
   if k:
    member[k].append(t)
   elif n=='GND' and not k:
    if all(q[1]>119 for q in e):rm(t);removed['GND stitching outside sub-circuits']+=1
   else:rm(t);removed[n]+=1
 for z in list(b.Zones()):
  n=z.GetNetname();bb=z.GetBoundingBox();box=(mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom()))
  if n in ionets or (n=='GND' and box[1]>113 and box[0]<178):
   k=next((name for name,c in BOX.items() if inbox(box[:2],c,.6) and inbox(box[2:],c,.6)),None)
   if k and z.GetLayer()==p.F_Cu:member[k].append(z)
   else:rm(z);removed['zone '+n+' '+b.GetLayerName(z.GetLayer())]+=1
  elif n=='VIN' and z.GetLayer()==p.In2_Cu and z.GetAssignedPriority()==2:rm(z);removed['zone VIN In2 feed to old fuse position']+=1
 texts={d.GetText():d for d in b.GetDrawings() if d.GetClass()=='PCB_TEXT'}
 log['removed']=dict(removed);log['loose_parts']=loose

 # ---- 2. place the pieces ----
 def bbox(items):
  x0=y0=1e9;x1=y1=-1e9
  for it in items:
   if isinstance(it,p.PCB_TEXT):continue
   boxes=[it.GetBoundingBox()] if not isinstance(it,p.FOOTPRINT) else [q.GetBoundingBox() for q in it.Pads()]+([it.GetCourtyard(p.F_Cu).BBox()] if it.GetCourtyard(p.F_Cu).OutlineCount() else [])
   for bb in boxes:x0=min(x0,mm(bb.GetX()));y0=min(y0,mm(bb.GetY()));x1=max(x1,mm(bb.GetRight()));y1=max(y1,mm(bb.GetBottom()))
  return x0,y0,x1,y1
 def move(items,dx,dy):
  for it in items:it.Move(V(dx,dy))
 def rotate(items,centre,deg):
  for it in items:it.Rotate(V(*centre),p.EDA_ANGLE(deg,p.DEGREES_T))
 placed={}
 def put(name,items,corner=None,deg=0,shift=None):
  before=bbox(items)
  if deg:rotate(items,((before[0]+before[2])/2,(before[1]+before[3])/2),deg)
  now=bbox(items);d=shift if shift else (corner[0]-now[0],corner[1]-now[1]);move(items,*d)
  placed[name]=dict(from_bbox=[round(v,2) for v in before],rotated_deg=deg,to_bbox=[round(v,2) for v in bbox(items)])
 # A: rotate so the input side faces right (towards the fuse) and tuck into the corner
 a_items=member['A']+[texts['J9928 SERVO OFF'],fps['J9928']]     # the servo-off jumper belongs to the buck's enable pin
 put('A servo buck',a_items,corner=(8.3,114.3),deg=90)
 cin=fps['C7101'].GetPosition();cout=fps['C7112'].GetPosition()
 if mm(cin.x)<mm(cout.x):                       # wrong way round: turn it over
  rotate(a_items,((placed['A servo buck']['to_bbox'][0]+placed['A servo buck']['to_bbox'][2])/2,(placed['A servo buck']['to_bbox'][1]+placed['A servo buck']['to_bbox'][3])/2),180)
  now=bbox(a_items);move(a_items,8.3-now[0],114.3-now[1]);placed['A servo buck'].update(rotated_deg=270,to_bbox=[round(v,2) for v in bbox(a_items)])
 texts['J9928 SERVO OFF'].SetTextAngleDegrees(0);_a=bbox(a_items);texts['J9928 SERVO OFF'].SetPosition(V((_a[0]+_a[2])/2,_a[3]+1.6))
 ax1=placed['A servo buck']['to_bbox'][2]
 put('F fuse',[fps['F7000']],deg=180,corner=(ax1+2.4,121.6))
 put('IN input capacitor',member['IN'],corner=(ax1+2.0,131.4))
 put('TV input TVS',member['TV'],corner=(ax1+2.0+18.0,131.6))
 put('B servo controller',member['B'],shift=B_SHIFT)
 bx0=placed['B servo controller']['to_bbox'][0]
 put('C output buffer',member['C'],corner=(bx0-26.6,118.4))
 conn=[fps['J7004'],fps['J7005'],fps['J7006']]
 for k,f in enumerate(conn):f.SetPosition(V(ax1+9.0+15.0*k,150.6))
 placed['J servo headers']=dict(pin1_mm=[[round(v,2) for v in xy(f.GetPosition())] for f in conn])
 fps['J7008'].SetPosition(V(bx0-15.5,151.0));placed['S SWD header']=dict(pin1_mm=[round(v,2) for v in xy(fps['J7008'].GetPosition())])
 holes={'H7002':(bx0-22.5,151.3),'H7003':(3.5,151.5),'H7004':(176.0,151.5)}
 for r,q in holes.items():fps[r].SetPosition(V(*q))
 placed['mounting holes']=holes
 # labels
 for old in [t for t in texts if re.match(r'J700[456] ',t)]:rm(texts[old])
 def label(s,x,y,size=.9):
  t=p.PCB_TEXT(b);t.SetText(s);t.SetPosition(V(x,y));t.SetTextSize(p.VECTOR2I(MM(size),MM(size)));t.SetTextThickness(MM(.14));t.SetLayer(p.F_SilkS);b.Add(t)
 for k,f in enumerate(conn):
  q=xy(f.GetPosition());label('SERVO %d  1G 2+ 3S'%(k+1),q[0]+2.54,q[1]+2.9,.8)
 q=xy(fps['J7008'].GetPosition());texts['J7008 PWM SWD'].SetPosition(V(q[0]+5.1,q[1]+3.0))
 q=xy(fps['F7000'].GetPosition());texts['F7000 PWM 5A'].SetPosition(V(q[0]-20.0,q[1]-5.2))
 for k,(old,new) in enumerate([('ROBOT PDB v0.10 PASSTHROUGH','ROBOT PDB v0.11 PASSTHROUGH'),('STOP BEFORE MASTER OFF',None),('MOTOR OUTPUT: BATTERY VOLTAGE',None),('CAMERA / MIC: JETSON USB3',None)]):
  t=texts[old];t.SetPosition(V(199.0,139.0+3.0*k))
  if new:t.SetText(new)
 log['placed']=placed

 # ---- 3. shorten the copper that follows the MCU ----
 dx,dy=B_SHIFT;stretch=[]
 for t in b.GetTracks():
  n=t.GetNetname()
  if n not in ('P4_DP','P4_DM','V5_USB') or t.GetClass()=='PCB_VIA' or any(t is q for q in member['B']):continue
  a,c=xy(t.GetStart()),xy(t.GetEnd())
  if n!='V5_USB':
   # corner piece and the two long runs: slide the corner, keep the far ends
   if max(a[1],c[1])<117.0 and min(a[0],c[0])<115.5:
    na=(a[0]+dx,a[1]) if a[0]<115.5 else a;nc=(c[0]+dx,c[1]) if c[0]<115.5 else c
    if abs(a[0]-c[0])<1e-6 and a[0]<115.5:                      # vertical run: lower end follows the MCU
     lo=max(a[1],c[1]);na=(a[0]+dx,a[1]+(dy if a[1]==lo and lo>116.9 else 0));nc=(c[0]+dx,c[1]+(dy if c[1]==lo and lo>116.9 else 0))
    t.SetStart(V(*na));t.SetEnd(V(*nc));stretch.append([n,[round(v,3) for v in a+c],[round(v,3) for v in na+nc]])
   elif abs(a[0]-c[0])<1e-6 and a[0]<115.5:
    lo=max(a[1],c[1]);na=(a[0]+dx,a[1]+(dy if abs(a[1]-lo)<1e-6 else 0));nc=(c[0]+dx,c[1]+(dy if abs(c[1]-lo)<1e-6 else 0))
    t.SetStart(V(*na));t.SetEnd(V(*nc));stretch.append([n,[round(v,3) for v in a+c],[round(v,3) for v in na+nc]])
  elif abs(a[1]-130.75)<1e-3 and abs(c[1]-130.75)<1e-3 and min(a[0],c[0])<115:
   west=min(a[0],c[0]);na=(a[0]+dx,a[1]) if a[0]==west else a;nc=(c[0]+dx,c[1]) if c[0]==west else c
   t.SetStart(V(*na));t.SetEnd(V(*nc));stretch.append([n,[round(v,3) for v in a+c],[round(v,3) for v in na+nc]])
   jog=p.PCB_TRACK(b);jog.SetStart(V(west+dx,130.75));jog.SetEnd(V(west+dx,130.75+dy));jog.SetWidth(t.GetWidth());jog.SetLayer(p.F_Cu);jog.SetNet(t.GetNet());b.Add(jog)
   stretch.append([n,'new jog',[round(west+dx,3),130.75,round(west+dx,3),round(130.75+dy,3)]])
 log['usb_and_5v_shortened']=stretch

 # ---- 4. outline ----
 for d in list(b.GetDrawings()):
  if d.GetLayer()==p.Edge_Cuts:rm(d)
 e=p.PCB_SHAPE(b);e.SetShape(p.SHAPE_T_RECT);e.SetStart(V(0,0));e.SetEnd(V(W,H));e.SetLayer(p.Edge_Cuts);e.SetWidth(MM(.1));b.Add(e)
 def save():
  b.SetFileName(str(out));p.SaveBoard(str(out),b);(DST/'robot_pdb.kicad_pro').write_bytes(profile)
 if stage=='place':
  save();print(json.dumps(log,indent=1)[:6000]);return

 # ---- 5. signals between the pieces ----
 rt=Router(b);routes=[]
 def padxy(ref,net):
  q=next(q for q in fps[ref].Pads() if q.GetNetname()==net);return xy(q.GetPosition()),((0,1) if q.GetAttribute()==p.PAD_ATTRIB_PTH else (0,))
 def loose_ends(net,near):
  """track ends of `net` that touch nothing else of that net; nearest to `near` first"""
  pts=collections.Counter();tracks=[t for t in b.GetTracks() if t.GetNetname()==net]
  for t in tracks:
   for q in ends(t):pts[(round(q[0],3),round(q[1],3))]+=1 if t.GetClass()!='PCB_VIA' else 2
  pads=[(xy(q.GetPosition()),q) for f in b.GetFootprints() for q in f.Pads() if q.GetNetname()==net]
  out=[]
  for t in tracks:
   if t.GetClass()=='PCB_VIA':continue
   for q in ends(t):
    if pts[(round(q[0],3),round(q[1],3))]==1 and not any(pad.HitTest(V(*q)) for _,pad in pads):out.append((math.dist(q,near),q,(0,) if t.GetLayer()==p.F_Cu else (1,)))
  return sorted(out)
 def connect(net,a,la,c,lc,w=.2,win=8.0,what=''):
  r=rt.path(net,a,la,c,lc,w=w,win=win)
  if r is None:r=rt.path(net,a,la,c,lc,w=w,win=win+10,step=.1)
  ok=r is not None;length=rt.lay(net,r,w) if ok else 0
  routes.append(dict(net=net,what=what,frm=[round(v,3) for v in a],to=[round(v,3) for v in c],width_mm=w,routed=ok,length_mm=round(length,2),vias=(len(r)-1 if ok else 0)));print(' route',net,what,'OK %.1f mm'%length if ok else 'FAILED',flush=True)
  return ok
 # MCU -> buffer inputs and arm signal: from where the kept MCU-side copper ends
 for net,ref in (('IO_PWM1_MCU','R7051'),('IO_PWM2_MCU','R7052'),('IO_PWM3_MCU','R7053'),('IO_SERVO_ARM','R7047')):
  tgt,lt=padxy(ref,net);cand=[e for e in loose_ends(net,tgt) if inbox(e[1],placed['B servo controller']['to_bbox'],1.0)]
  if cand:_,a,la=cand[0]
  else:a,la=padxy('U7002',net)
  connect(net,a,la,tgt,lt,what='MCU to buffer')
 for k,(net,ref) in enumerate((('IO_PWM1_OUT','J7004'),('IO_PWM2_OUT','J7005'),('IO_PWM3_OUT','J7006'))):
  tgt,lt=padxy(ref,net);src_ref='R705%d'%(4+k);a,la=padxy(src_ref,net);connect(net,a,la,tgt,lt,w=.25,win=10,what='buffer to servo header')
 for net in ('IO_PWM_SWDIO','IO_PWM_SWCLK','IO_PWM_NRST','IO_V3_PWM'):
  tgt,lt=padxy('J7008',net);cand=[e for e in loose_ends(net,tgt) if inbox(e[1],placed['B servo controller']['to_bbox'],1.0)]
  if cand:_,a,la=cand[0]
  else:a,la=padxy('TP7002' if net=='IO_V3_PWM' else 'U7002',net)
  connect(net,a,la,tgt,lt,what='MCU to SWD header')
 log['routes']=routes
 # leftover ends of the old inter-block tracks: remove anything on these nets that leads nowhere
 pruned=collections.Counter()
 for net in SIGNAL_NETS[:-1]+('IO_PWM_EN',):
  pads=[q for f in b.GetFootprints() for q in f.Pads() if q.GetNetname()==net]
  while True:
   items=[t for t in b.GetTracks() if t.GetNetname()==net];gone=0
   for t in items:
    others=[o for o in items if o is not t]
    def held(q):
     if any(pad.HitTest(V(*q)) for pad in pads):return True
     for o in others:
      if o.GetClass()=='PCB_VIA':
       if math.dist(q,xy(o.GetPosition()))<.05:return True
      elif o.HitTest(V(*q)) and (t.GetClass()=='PCB_VIA' or o.GetLayer()==t.GetLayer()):return True
     return False
    n_held=[held(q) for q in ends(t)]
    if (t.GetClass()=='PCB_VIA' and len({o.GetLayer() for o in others if o.GetClass()!='PCB_VIA' and o.HitTest(t.GetPosition())})<2 and not any(pad.HitTest(t.GetPosition()) for pad in pads)) or (t.GetClass()!='PCB_VIA' and not all(n_held)):
     rm(t);pruned[net]+=1;gone+=1;break
   if not gone:break
 log['pruned_stubs']=dict(pruned);rt._index=None

 # ---- 6. power planes for the servo block ----
 def zone(net,layer,poly,prio,clear=.3,minw=.3):
  z=p.ZONE(b);z.SetLayer(layer);z.SetNet(b.FindNet(net));o=z.Outline();o.NewOutline()
  for x,y in poly:o.Append(MM(x),MM(y))
  z.SetAssignedPriority(prio);z.SetLocalClearance(MM(clear));z.SetMinThickness(MM(minw));z.SetPadConnection(p.ZONE_CONNECTION_FULL)
  z.SetIslandRemovalMode(p.ISLAND_REMOVAL_MODE_ALWAYS);b.Add(z);return z
 A=placed['A servo buck']['to_bbox'];Bb=placed['B servo controller']['to_bbox'];fuse=[xy(q.GetPosition()) for q in fps['F7000'].Pads()]
 vin_pin=next(xy(q.GetPosition()) for q in fps['F7000'].Pads() if q.GetNetname()=='VIN')
 planes=[]
 z5=[(6.0,112.6),(Bb[0]-1.2,112.6),(Bb[0]-1.2,H-.6),(6.0,H-.6)]
 zone('PWM_5V',p.In2_Cu,z5,3);planes.append(dict(net='PWM_5V',layer='In2.Cu',outline=z5,purpose='servo 5 V from the buck to the buffer and the three headers'))
 zv=[(vin_pin[0]-4.0,108.0),(vin_pin[0]+3.0,108.0),(vin_pin[0]+3.0,vin_pin[1]+3.0),(vin_pin[0]-4.0,vin_pin[1]+3.0)]
 zone('VIN',p.In2_Cu,zv,5);planes.append(dict(net='VIN',layer='In2.Cu',outline=zv,purpose='battery bus down to the fuse'))
 zi=[(A[2]-17.5,120.0),(A[2]+32.0,120.0),(A[2]+32.0,145.5),(A[2]-7.0,145.5),(A[2]-7.0,148.2),(A[2]-17.5,148.2)]
 zone('PWM_VIN',p.B_Cu,zi,2);planes.append(dict(net='PWM_VIN',layer='B.Cu',outline=zi,purpose='fused input: fuse, bulk capacitor, TVS and buck input'))
 c1=next(xy(q.GetPosition()) for q in fps['C7111'].Pads() if q.GetNetname()=='PWM_VIN')
 zc=[(c1[0]-4.1,c1[1]-1.7),(c1[0]+1.6,c1[1]-1.7),(c1[0]+1.6,c1[1]+1.7),(c1[0]-4.1,c1[1]+1.7)]
 zone('PWM_VIN',p.F_Cu,zc,3);planes.append(dict(net='PWM_VIN',layer='F.Cu',outline=zc,purpose='ties the bulk capacitor pad to its three vias'))
 z3=[(Bb[0]-.6,112.6),(Bb[2]+2.0,112.6),(Bb[2]+2.0,H-.6),(Bb[0]-.6,H-.6)]
 zone('IO_V3_PWM',p.In2_Cu,z3,3);planes.append(dict(net='IO_V3_PWM',layer='In2.Cu',outline=z3,purpose='3.3 V under the servo controller'))
 zg=[(.5,110.5),(178.0,110.5),(178.0,112.3),(W-.5,112.3),(W-.5,H-.5),(.5,H-.5)]   # meets the main pour; the USB block keeps its old edge
 for layer in (p.F_Cu,p.B_Cu):zone('GND',layer,zg,0,clear=.25,minw=.25)
 planes.append(dict(net='GND',layer='F.Cu and B.Cu',outline=zg,purpose='ground pour across the whole lower strip, including the corner v0.10 left bare'))
 log['planes']=planes

 # ---- 7. part change, save, fill, check ----
 for ref,c in PART_CHANGES.items():fps[ref].SetValue(c['value'])
 log['part_changes']=PART_CHANGES
 save()
 sch=DST/'robot_pdb.kicad_sch';s=sch.read_text()
 for ref,c in PART_CHANGES.items():
  m=re.search(r'\(property "Reference" "%s"'%ref,s);a=s.rfind('(symbol (lib_id',0,m.start());z=s.find('\n  (symbol (lib_id',m.end());z=len(s) if z<0 else z;blk=s[a:z]
  for key,prop in (('value','Value'),('lcsc','LCSC'),('mpn','MPN')):
   before='(property "%s" "%s"'%(prop,c['old'][key]);assert blk.count(before)==1,(ref,prop);blk=blk.replace(before,'(property "%s" "%s"'%(prop,c[key]))
  s=s[:a]+blk+s[z:]
 sch.write_text(s.replace('0.10 value-engineered candidate','0.11 compact layout'))
 subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(out),str(DST.parent/'drc.rpt')],check=True)
 log['board_sha256']=sha(out);log['schematic_sha256']=sha(sch);log['generator_sha256']=sha(__file__)
 (DST.parent/'derivation.json').write_text(json.dumps(log,indent=1)+'\n')
 print('v0.11 saved',log['board_sha256'],'routes ok',sum(r['routed'] for r in routes),'of',len(routes))

if __name__=='__main__':main(sys.argv[1] if len(sys.argv)>1 else 'all')
