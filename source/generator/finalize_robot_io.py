"""I/O native-rule configuration and local geometric cleanup, no other revision.

Small0.4/0.2mm through vias are explicitly represented in the project rules.
All other electrical/clearance rules remain enabled. Fix sampled-route corner
errors by rerouting the actual offending segments, then rerun native KiCad.
"""
import json,re,math,subprocess,signal
from pathlib import Path
import pcbnew as p
from cells import Board
from robot_io_router import RobotIOFixer

def finalize(root=None):
 root=Path(root or Path(__file__).resolve().parents[2]);dest=root/'revisions/robot-io/kicad';out=dest/'robot_io.kicad_pcb';report=dest.parent/'drc.rpt'
 pro=dest/'robot_io.kicad_pro'
 config=json.loads(pro.read_text())
 config['board']['design_settings']['rules'].update(min_through_hole_diameter=.2,min_via_diameter=.4,min_via_annular_width=.1)
 pro.write_text(json.dumps(config,indent=2)+'\n')
 b=p.LoadBoard(str(out));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[];g.fps={f.GetReference():f for f in b.GetFootprints()}
 d=b.GetDesignSettings();d.m_MinThroughDrill=p.FromMM(.2);d.m_ViasMinSize=p.FromMM(.4);d.m_ViasMinAnnularWidth=p.FromMM(.1)
 dead=[];evidence=[]
 def strip_zones():
  zs=list(b.Zones())
  for z in zs:b.Remove(z)
  return zs
 def save_refill(zs):
  for z in zs:b.Add(z)
  p.SaveBoard(str(out),b)
  subprocess.run(['python3',str(root/'source/fabrication/refill_drc.py'),str(out),str(report)],check=True)
 def timeout(a,c):raise TimeoutError('local route time budget')
 signal.signal(signal.SIGALRM,timeout)
 zs=strip_zones();fx=RobotIOFixer(b)
 # R21's original left-hand power via fell outside its own supply region.
 # Move this one-ended spur upward into the PWM supply plane.
 a=g.pad('R21','1');q=(a[0],a[1]-.9)
 old=(a[0]-.8,a[1])
 for t in list(b.GetTracks()):
  if t.GetNetname()!='V3_PWM':continue
  if t.GetClass()=='PCB_VIA' and math.dist(p.ToMM(t.GetPosition()),old)<.01:
   dead.append(t);b.Remove(t)
  elif t.GetClass()=='PCB_TRACK' and any(math.dist(p.ToMM(v),old)<.01 for v in (t.GetStart(),t.GetEnd())):
   dead.append(t);b.Remove(t)
 fx._index=None
 if not any(t.GetClass()=='PCB_VIA' and t.GetNetname()=='V3_PWM' and math.dist(p.ToMM(t.GetPosition()),q)<.01 for t in b.GetTracks()):
  assert all(fx.free(L,'V3_PWM',*q,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)),q
  g.via('V3_PWM',*q);g.track('V3_PWM',[a,q],.22);fx._index=None
 # Remove the fully overlapped original CAN-TX escape stub. Its longer escape
 # is already connected; retaining both creates a misleading dangling warning.
 for t in list(b.GetTracks()):
  if t.GetClass()=='PCB_TRACK' and t.GetNetname()=='CAN_TXD' and abs(p.ToMM(t.GetLength())-1.2)<.001 and math.dist(p.ToMM(t.GetStart()),g.pad('U1','46'))<.001:
   dead.append(t);b.Remove(t)
 for drawing in b.GetDrawings():
  if drawing.GetClass()!='PCB_TEXT':continue
  name=drawing.GetText()
  if name=='CAN USB':drawing.SetPosition(p.VECTOR2I(p.FromMM(79),p.FromMM(21)))
  if name=='PWM USB':drawing.SetPosition(p.VECTOR2I(p.FromMM(106),p.FromMM(21)))
  if name=='BATTERY IN':drawing.SetPosition(p.VECTOR2I(p.FromMM(14),p.FromMM(86)))
  drawing.SetTextSize(p.VECTOR2I(p.FromMM(1),p.FromMM(1)))
 # Polarity follows the actual rotated power-port pads, not assumed axes.
 j9=g.fps['J9'];pins={q.GetNumber():p.ToMM(q.GetPosition()) for q in j9.Pads()}
 existing={q.GetText():q for q in b.GetDrawings() if q.GetClass()=='PCB_TEXT'}
 for label,(x,y) in [('GND',(pins['1'][0],pins['1'][1]+5)),('BAT+',(pins['2'][0],pins['2'][1]-4.5))]:
  if label in existing:existing[label].SetPosition(p.VECTOR2I(p.FromMM(x),p.FromMM(y)))
  else:g.text(label,x,y,1)
 save_refill(zs)
 for iteration in range(4):
  txt=report.read_text();blocks=[q for q in txt.split('\n[') if q.startswith('clearance]')]
  if not blocks:break
  b=p.LoadBoard(str(out));g.b=b;g.nets={};zs=strip_zones();fx=RobotIOFixer(b)
  for block in blocks:
   m=re.search(r'@\(([-\d.]+) mm, ([-\d.]+) mm\): Track \[([^\]]+)\] on ([FB])\.Cu, length ([\d.]+) mm',block)
   if not m:continue
   x,y,net,layer,length=m.groups();xy=(float(x),float(y));length=float(length)
   match=next((t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net and t.GetLayer()==(p.F_Cu if layer=='F' else p.B_Cu) and math.dist(p.ToMM(t.GetStart()),xy)<.001 and abs(p.ToMM(t.GetLength())-length)<.001),None)
   if not match:continue
   a=p.ToMM(match.GetStart());c=p.ToMM(match.GetEnd());width=p.ToMM(match.GetWidth());removed=[match];b.Remove(match);fx._index=None
   # Expand to the next junction if the original endpoint itself violates the
   # other net's clearance; every replacement keeps the same electrical ends.
   for side in range(2):
    for _ in range(5):
     tip=a if side==0 else c
     if fx.free(p.F_Cu if layer=='F' else p.B_Cu,net,*tip,width/2):break
     neighbor=next((t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net and t.GetLayer()==match.GetLayer() and any(math.dist(p.ToMM(v),tip)<.001 for v in (t.GetStart(),t.GetEnd()))),None)
     if not neighbor:break
     u,v=p.ToMM(neighbor.GetStart()),p.ToMM(neighbor.GetEnd());other=v if math.dist(u,tip)<.001 else u
     if side==0:a=other
     else:c=other
     removed.append(neighbor);b.Remove(neighbor);fx._index=None
   signal.alarm(15)
   try:ok=fx.route(net,a,c,w=width,step=.05,win=2,layers=(layer,'B' if layer=='F' else 'F'))
   except TimeoutError:ok=False
   finally:signal.alarm(0)
   if ok:dead.extend(removed)
   else:
    for t in removed:b.Add(t)
    fx._index=None
   evidence.append({'iteration':iteration,'net':net,'start':a,'end':c,'rerouted':bool(ok)})
   print('native-corner cleanup',net,ok,flush=True)
  save_refill(zs)
 (dest.parent/'native-cleanup-evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
 txt=report.read_text();print('Final native report:',[q for q in txt.splitlines() if q.startswith('** Found')],flush=True)
if __name__=='__main__':finalize()
