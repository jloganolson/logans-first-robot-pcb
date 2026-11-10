"""Route v0.9 integration copper; no manufacturing exports or purchase actions.

The reusable geometry search is inherited read-only from the frozen v0.7
router. This module owns its inventory, endpoints, geometry and output paths.
Any failed search remains an explicit open connection, never a clearance waiver.
"""
import argparse,hashlib,json,math,signal,subprocess,sys
from pathlib import Path
import pcbnew as p
import fixer
from cells import Board
from robot_io_router import RobotIOFixer
import route_v07 as geometry
from rev09 import PARTS,CELLS

ROOT=Path(__file__).resolve().parents[2];K=ROOT/'revisions/v0.9/kicad'
# Actual JLC nominal calculation, JLC041621-2116,2oz outer/.109mm prepreg.
# Factory production confirmation and finished-board USB testing remain open.
geometry.W=.165;geometry.GAP=.300

class V09Fixer(RobotIOFixer):
 def free(self,layer,net,x,y,half):
  if not super().free(layer,net,x,y,half):return False
  pt=p.VECTOR2I(p.FromMM(x),p.FromMM(y))
  for item in self._items(layer,net,x,y,half+2.3):
   if item.GetClass()=='PCB_VIA':
    gap=.225
    if hasattr(self,'integration'):gap=max(gap,self.integration.external_spacing(item,(x,y),gap,net))
    if math.dist((x,y),p.ToMM(item.GetPosition()))<p.ToMM(item.GetWidth())/2+half+gap:return False
   else:
    gap=.255 if item.GetClass()=='PAD' and item.GetAttribute()==p.PAD_ATTRIB_NPTH else .225
    if hasattr(self,'integration'):gap=max(gap,self.integration.external_spacing(item,(x,y),gap,net))
    if item.HitTest(pt,p.FromMM(half+gap)):return False
  return True

class Integration(geometry.Integration):
 def __init__(self,path):
  self.path=Path(path);self.output=K/'robot_pdb.kicad_pcb';self.b=p.LoadBoard(str(path));self.dead=[]
  self.g=Board.__new__(Board);self.g.b=self.b;self.g.nets={};self.g.zones=[]
  self.fps={f.GetReference():f for f in self.b.GetFootprints()};self.g.fps=self.fps
  assert set(self.fps)=={s['ref'] for s in PARTS},'Regenerate v0.9 composition'
  self.zones=list(self.b.Zones())
  for z in self.zones:self.b.Remove(z)
  fixer.VIA_D=.4;fixer.VIA_DR=.2
  self.fx=V09Fixer(self.b);self.fx.integration=self;self.fx.via_ok=lambda n,x,y:self.stitch(n,(x,y),.4,.2,dry=True)
  self.initial_ids={t.m_Uuid.AsString() for t in self.b.GetTracks()}
  self.original_copper={t.m_Uuid.AsString():dict(net=t.GetNetname(),layer=int(t.GetLayer()),start=p.ToMM(t.GetStart()),end=p.ToMM(t.GetEnd()),width_mm=p.ToMM(t.GetWidth()),drill_mm=p.ToMM(t.GetDrillValue()) if t.GetClass()=='PCB_VIA' else None) for t in self.b.GetTracks()}
  self.landings=json.loads((K.parent/'composition.json').read_text())['excluded_landings']
  self.evidence=[];self.pairs=[];self.power=[];self.routing_attempts=[];self.source_hash=hashlib.sha256(self.path.read_bytes()).hexdigest()
  self.route_code_hashes={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in
   [Path(__file__),Path(geometry.__file__),ROOT/'source/generator/route_v09_usb.py',ROOT/'source/generator/rev09.py',ROOT/'source/generator/usb2_control.py',ROOT/'source/generator/robot_pwm.py']}
 def external_spacing(self,item,q,ordinary=.205,ownnet=None):return ordinary
 def landing(self,cell,ref,net):
  return tuple(next(q['position_mm'] for q in self.landings[cell][ref] if q['net']==net))
 def local(self):
  ox,oy=CELLS['usb2']['position'];local=lambda q:(q[0]+ox-183,q[1]+oy-128)
  # VBUS is connector/ESD/bypass/sense only. No path to any local5V rail.
  for r,pin in [('J10','A4'),('J10','A9'),('C67','1'),('R9909','1')]:
   self.route('VBUS_IN',self.pad('U11','5'),self.pad(r,pin),.2,win=8)
  # Rebuild removed base supply branches explicitly. The two current-limit
  # stages and ferrite remain physically in series, never only renamed pads.
  # Explicit layer handoffs: a zone on B alone cannot energize an F SMD pad.
  for layer in ('F','B'):
   self.g.zone('USB_CONTROL_5V',layer,[(132.5,44),(139.5,44),(139.5,50),(132.5,50)],3,.3,minw=.4)
   self.g.zone('USB_CONTROL_5V',layer,[local(q) for q in ((184.5,138.5),(187.1,138.5),(187.1,142.5),(184.5,142.5))],3,.3,minw=.3)
  handoffs=[(134.2,46),(135.3,46),(134.2,47.1),(135.3,47.1)]+[local(q) for q in ((185.5,139.5),(186.5,139.5),(185.5,140.5),(186.5,140.5))]
  for q in handoffs:
   ok=self.stitch('USB_CONTROL_5V',q,.8,.4);self.evidence.append(dict(action='USB control handoff via candidate',net='USB_CONTROL_5V',at=q,placed=ok))
  self.route('USB_CONTROL_5V',(133.5,48),local((185.5,140.5)),.8,win=20)
  self.route('USB2_LIMITED_5V',self.pad('U9904','6'),self.pad('FB1','1'),.6,win=10)
  for r,pin in [('U9900','1')]:
   self.route('V5_USB_HUB',self.pad('FB1','2'),self.pad(r,pin),.4,win=8)
  for r,pin in [('U14','7'),('C7021','1')]:
   self.route('V5_USB',self.pad('U9900','6'),self.pad(r,pin),.4,win=10)
  for net,a,c in [
   ('H_V33',('U10','20'),('C9905','1')),
   ('H_PWREN_N',('U10','24'),('U9900','3')),
   ('H_OVCUR',('U10','1'),('U9900','4')),
   ]:
   self.route(net,self.pad(*a),self.pad(*c),.18,win=10)
  # R74/R75 share a filled F ground pocket with no original plane anchor.
  # Connect that actual resistor island to the continuous inner ground.
  for q in ((205.30,119.85),):
   ok=self.stitch('GND',q,.6,.3)
   self.evidence.append(dict(action='R74/R75 ground pocket plane anchor',net='GND',at=q,placed=ok))
   assert ok,('R74/R75 ground anchor obstructed',q)
  self.local_links_built=True
 def power_links(self):
  self.g.zone('VIN','In2',[(35,115),(175,115),(175,149),(115,149),(115,128),(35,128)],2,.5,minw=.6)
  self.power_spine('PWM_VIN',[self.pad('F7000','2'),(170,150),(170,188),(7.5,188),(5,186)],4,'5A-fused PWM input branch',layers=('B',))
  for q in ((169.5,151.5),(170.5,151.5),(169.5,152.5),(170.5,152.5)):
   ok=self.stitch('PWM_VIN',q,.8,.4);self.evidence.append(dict(action='PWM fuse power crossing via candidate',net='PWM_VIN',at=q,placed=ok))
  self.route('PWM_VIN',self.pad('F7000','2'),(169.5,151.5),.8,win=6,layers=('F',))
  array=[(169.5,151.5),(170.5,151.5),(170.5,152.5),(169.5,152.5)]
  for a,b in zip(array,array[1:]):
   assert all(self.fx.free(p.F_Cu,'PWM_VIN',*q,.4) for q in geometry.samples([a,b],.05)),('PWM handoff array link obstructed',a,b)
   self.g.track('PWM_VIN',[a,b],.8,'F');self.fx._index=None
  self.evidence.append(dict(action='Join four PWM input handoff vias on F to existing B spine',path_mm=array,width_mm=.8,qualification='Connectivity only; no continuous5A thermal rating claimed'))
  for q in ((4.5,185),(4.5,186.2),(5.5,185),(5.5,186.2)):
   ok=self.stitch('PWM_VIN',q,.8,.4);self.evidence.append(dict(action='PWM input layer handoff via candidate',net='PWM_VIN',at=q,placed=ok))
 def usb_pairs(self):
  from route_v09_usb import apply
  apply(self)
 def repair_vbus_reference_clearance(self):
  # The independent filled-copper audit found this foreign VBUS antipad
  # clipping the inherited connector DM edge. Move only this DC handoff;
  # the USB signal geometry and both inner ground outlines stay unchanged.
  old=(218.087499,102.4);new=(218.187499,102.35)
  vias=[t for t in self.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='VBUS_IN' and math.dist(p.ToMM(t.GetPosition()),old)<.001]
  assert len(vias)==1,('Expected raw VBUS reference repair via',len(vias))
  via=vias[0];before_uuid=via.m_Uuid.AsString();self.remove(via);self.fx._index=None
  assert self.stitch('VBUS_IN',new,.4,.2),('VBUS reference repair blocked',new)
  endpoints=[]
  for t in self.b.GetTracks():
   if t.GetClass()!='PCB_TRACK' or t.GetNetname()!='VBUS_IN':continue
   for label,getter,setter in [('start',t.GetStart,t.SetStart),('end',t.GetEnd,t.SetEnd)]:
    if math.dist(p.ToMM(getter()),old)<.001:
     setter(p.VECTOR2I(p.FromMM(new[0]),p.FromMM(new[1])));endpoints.append(dict(uuid=t.m_Uuid.AsString(),endpoint=label,layer=self.b.GetLayerName(t.GetLayer())))
  assert len(endpoints)==2,('Expected both raw VBUS handoff leads',endpoints)
  self.fx._index=None
  self.evidence.append(dict(action='Move raw VBUS handoff away from USB DM ground reference',removed_via_uuid=before_uuid,before_mm=old,after_mm=new,diameter_mm=.4,drill_mm=.2,updated_leads=endpoints,required_independent_screen='Native DRC and actual filled In1 reference; no foreign-antipad waiver'))
 def repair_audio_reference_clearance(self):
  # A new low-speed overcurrent handoff must not punch a new reference hole
  # under the retained P1 audio pair. Preserve the data copper verbatim.
  old=(204.9625,98.85);new=(204.85,99.0);net='H_OVCUR'
  vias=[t for t in self.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist(p.ToMM(t.GetPosition()),old)<.001]
  assert len(vias)==1,('Expected overcurrent reference repair via',len(vias))
  via=vias[0];before_uuid=via.m_Uuid.AsString();self.remove(via);self.fx._index=None
  assert self.stitch(net,new,.4,.2),('Overcurrent reference repair blocked',new)
  endpoints=[]
  for t in self.b.GetTracks():
   if t.GetClass()!='PCB_TRACK' or t.GetNetname()!=net:continue
   for label,getter,setter in [('start',t.GetStart,t.SetStart),('end',t.GetEnd,t.SetEnd)]:
    if math.dist(p.ToMM(getter()),old)<.001:
     setter(p.VECTOR2I(p.FromMM(new[0]),p.FromMM(new[1])));endpoints.append(dict(uuid=t.m_Uuid.AsString(),endpoint=label,layer=self.b.GetLayerName(t.GetLayer())))
  assert len(endpoints)==2,('Expected both overcurrent handoff leads',endpoints)
  self.fx._index=None
  self.evidence.append(dict(action='Move overcurrent handoff away from inherited audio ground reference',net=net,removed_via_uuid=before_uuid,before_mm=old,after_mm=new,diameter_mm=.4,drill_mm=.2,updated_leads=endpoints,required_independent_screen='Native DRC and saved In1 reference; every remaining audio reference gap must be proven present in frozen source'))
 def protect_usb_from_outer_pours(self):
  """Keep the new microstrip corridors free of coplanar copper pours.

  The nominal factory calculation assumes an adjacent inner GND plane, not
  coplanar copper. Do not cut either inner reference plane. Package escapes
  use the same explicit, bounded exceptions as the routing-spacing screen.
  Final filled-copper coverage/spacing is independently audited after refill.
  """
  names={'USB_DP','USB_DM','HUB_UP_DP','HUB_UP_DM','P4_DP','P4_DM'}
  tracks=[t for t in self.b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname() in names and t.m_Uuid.AsString() not in self.initial_ids]
  def polygon(points):
   poly=p.SHAPE_POLY_SET();poly.NewOutline()
   for x,y in points:poly.Append(p.FromMM(x),p.FromMM(y))
   return poly
  def signature(poly):
   return tuple(tuple(tuple((line.CPoint(k).x,line.CPoint(k).y) for k in range(line.PointCount())) for line in [poly.COutline(n)]+[poly.CHole(n,h) for h in range(poly.HoleCount(n))]) for n in range(poly.OutlineCount()))
  cache={};changed=[]
  for zone in self.zones+list(self.b.Zones()):
   layer=zone.GetLayer();net=zone.GetNetname()
   if layer not in (p.F_Cu,p.B_Cu) or zone.GetIsRuleArea():continue
   key=(layer,net)
   if key not in cache:
    guard=p.SHAPE_POLY_SET()
    for track in tracks:
     if not track.IsOnLayer(layer) or track.GetNetname()==net:continue
     aa,bb=p.ToMM(track.GetStart()),p.ToMM(track.GetEnd());radius=p.ToMM(track.GetWidth())/2+.770
     if math.dist(aa,bb)<1e-8:continue
     u=geometry.norm((bb[0]-aa[0],bb[1]-aa[1]));n=(-u[1],u[0]);a=geometry.add(aa,geometry.mul(u,-radius));b=geometry.add(bb,geometry.mul(u,radius))
     part=polygon([geometry.add(a,geometry.mul(n,radius)),geometry.add(b,geometry.mul(n,radius)),geometry.add(b,geometry.mul(n,-radius)),geometry.add(a,geometry.mul(n,-radius))])
     for region in getattr(self,'usb_regions',[]):
      if track.GetNetname() not in region['nets'] or net not in region['nets']:continue
      x0,y0,x1,y1=region['box_mm']
      part.BooleanSubtract(polygon([(x0,y0),(x1,y0),(x1,y1),(x0,y1)]),p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
     guard.BooleanAdd(part,p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
    cache[key]=guard
   guard=cache[key]
   if not guard.OutlineCount() or not zone.Outline().Collide(guard):continue
   before=signature(zone.Outline());zone.Outline().BooleanSubtract(guard,p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE);after=signature(zone.Outline())
   if before!=after:changed.append(dict(uuid=zone.m_Uuid.AsString(),net=net,layer=self.b.GetLayerName(layer),before_geometry_sha256=hashlib.sha256(repr(before).encode()).hexdigest(),after_geometry_sha256=hashlib.sha256(repr(after).encode()).hexdigest()))
  self.usb_outer_pour_exclusions=changed
 def finish(self):
  assert all(hashlib.sha256((ROOT/q).read_bytes()).hexdigest()==h for q,h in self.route_code_hashes.items()),'Routing source changed during this run; regenerate from a frozen source snapshot'
  if getattr(self,'local_links_built',False):
   self.repair_vbus_reference_clearance();self.repair_audio_reference_clearance()
  self.protect_usb_from_outer_pours()
  for z in self.zones:self.b.Add(z)
  profile=self.output.with_suffix('.kicad_pro');profile_bytes=profile.read_bytes()
  p.SaveBoard(str(self.output),self.b);profile.write_bytes(profile_bytes)
  subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(self.output),str(K.parent/'drc.rpt')],check=True)
  current_ids={t.m_Uuid.AsString() for t in self.b.GetTracks()}
  current_copper={t.m_Uuid.AsString():dict(net=t.GetNetname(),layer=int(t.GetLayer()),start=p.ToMM(t.GetStart()),end=p.ToMM(t.GetEnd()),width_mm=p.ToMM(t.GetWidth()),drill_mm=p.ToMM(t.GetDrillValue()) if t.GetClass()=='PCB_VIA' else None) for t in self.b.GetTracks()}
  (K.parent/'integration-routing.json').write_text(json.dumps(dict(status='DEVELOPMENT; NOT RELEASED',source_sha256=self.source_hash,
   board_sha256=hashlib.sha256(self.output.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   geometry_library_sha256=hashlib.sha256(Path(geometry.__file__).read_bytes()).hexdigest(),power=self.power,pairs=self.pairs,ordinary_routes=self.evidence,routing_attempts=self.routing_attempts,
   route_input_code_sha256=self.route_code_hashes,
   usb_outer_pour_exclusions=self.usb_outer_pour_exclusions,usb_package_escape_regions=[dict(reference=q['reference'],box_mm=q['box_mm']) for q in getattr(self,'usb_regions',[])],
   original_copper_removed=[dict(uuid=q,**row) for q,row in self.original_copper.items() if q not in current_ids],
   original_copper_modified=[dict(uuid=q,before=row,after=current_copper[q]) for q,row in self.original_copper.items() if q in current_copper and row!=current_copper[q]],
   bench_hold='Original battery-voltage passthrough only. Verify existing controller regeneration, pack/BMS limits and harness; qualify all new rails/USB/PWM on the bench.'),indent=2)+'\n')

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,default=K/'robot_pdb.kicad_pcb');ap.add_argument('--stage',choices=['local','power','usb','nonusb','all'],default='all');args=ap.parse_args()
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('route budget')))
 route=Integration(args.input)
 # Pair geometry gets first choice of free corridors before added controls.
 if args.stage in ('usb','all'):route.usb_pairs()
 if args.stage in ('local','nonusb','all'):route.local()
 if args.stage in ('power','nonusb','all'):route.power_links()
 route.finish()
