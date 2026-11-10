"""Compose USB2-only v0.8 source cells. Never exports manufacturing files.

Cell copper is preserved except for explicitly changed base USB and output
interfaces. Intercell links are left open for route_v08.py and native checking.
"""
import os,re,json,math,shutil,subprocess,sys,hashlib
from pathlib import Path
import pcbnew as p
from cells import Board
import usb2_control,service_off_v08
import label_v08
from rev08 import PARTS,CELLS,netmap,refmap,BOARD_SIZE_MM

ROOT=Path(__file__).resolve().parents[2];K=ROOT/'revisions/v0.8/kicad';K.mkdir(parents=True,exist_ok=True)
CUSTOM=K/'Robot_PDB.pretty';CUSTOM.mkdir(exist_ok=True)
FPROOT=Path(os.environ['KICAD7_FOOTPRINT_DIR'])
spec={s['ref']:s for s in PARTS};sources=[];dead=[];source_files={};excluded_landings={}
stage_delta=(4,-51)
def vec(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def remove(item):dead.append(item);b.Remove(item)
def point_segment(q,a,z):
 v=(z[0]-a[0],z[1]-a[1]);den=v[0]**2+v[1]**2
 u=max(0,min(1,((q[0]-a[0])*v[0]+(q[1]-a[1])*v[1])/den)) if den else 0
 return math.dist(q,(a[0]+u*v[0],a[1]+u*v[1]))
def hub_region(q):
 x,y=p.ToMM(q);return 203<=x<=214 and 74<=y<=90
def custom_variant(library,name,new,replacements):
 text=(FPROOT/(library+'.pretty')/(name+'.kicad_mod')).read_text().replace('"'+name+'"','"'+new+'"',1)
 for old,replacement,count in replacements:
  assert text.count(old)==count,(name,old,text.count(old));text=text.replace(old,replacement)
 (CUSTOM/(new+'.kicad_mod')).write_text(text)

# Copy exact source-cell definitions first; source disagreements are errors.
seen={}
for cell,c in CELLS.items():
 lib=(ROOT/c['board']).parent/'Robot_PDB.pretty'
 if lib.exists():
  for file in lib.glob('*.kicad_mod'):
   if file.name in seen:assert seen[file.name]==file.read_bytes(),('conflicting footprint',file.name)
   seen[file.name]=file.read_bytes();shutil.copyfile(file,CUSTOM/file.name)
custom_variant('Connector_AMASS','AMASS_XT30PW-F_1x02_P2.50mm_Horizontal','AMASS_XT30PW_F_2oz',
 [('(size 1.4 1.4)','(size 1.52 1.52)',2)])
custom_variant('Connector_Molex','Molex_Micro-Fit_3.0_43045-0412_2x02_P3.00mm_Vertical','MicroFit_43045_0412_4P_2oz',
 [('(size 1.5 1.5)','(size 1.54 1.54)',4)])
custom_variant('Connector_USB','USB_C_Receptacle_HRO_TYPE-C-31-M-12','USB_C_HRO_31M12_2oz',
 [('(size 1 1.6)','(size 1.12 1.72)',2),('(size 1 2.1)','(size 1.12 2.22)',2)])
usb2_control.write_footprints(CUSTOM)
shutil.copyfile(ROOT/'revisions/v0.7/kicad/Robot_PDB.pretty/Fuse_Schurter_SHF_6.3x32_P40mm.kicad_mod',
 CUSTOM/'Fuse_Schurter_SHF_6.3x32_P40mm.kicad_mod')
b=p.LoadBoard(str(ROOT/CELLS['base']['board']))
g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[]
old_pself=next(q for q in b.FindFootprintByReference('U10').Pads() if q.GetNumber()=='18').GetPosition()
old_pself=p.VECTOR2I(old_pself.x,old_pself.y)

def drop_track(cell,t):
 # Both members of this optional IO termination were deliberately omitted;
 # their private connecting copper has no functional endpoint in v0.8.
 if cell=='io' and t.GetNetname()=='CAN_TERM':return True
 if cell!='base':return False
 n=t.GetNetname()
 # Rebuild these affected connections explicitly, never leave a hidden
 # host-power path or old data path around the VBUS-controlled switch.
 if n in ('USB_DP','USB_DM'):
  # Retain the reviewed connector aliases and ESD pass-through copper. Only
  # hub-side legs are removed for the inserted VBUS-controlled data switch.
  return not all(p.ToMM(q)[0]>=214.36 for q in (t.GetStart(),t.GetEnd()))
 if n=='V5_USB':
  # A real clearance gap, wider than the old0.2mm trace, separates the two
  # supplies at the former shared feed. Merely splitting at one coordinate
  # leaves the copper end caps touching despite different net labels.
  if any(205<=x<=206.3 and 89.35<=y<=90.85 for x,y in (p.ToMM(t.GetStart()),p.ToMM(t.GetEnd()))):return True
  return hub_region(t.GetStart())!=hub_region(t.GetEnd())
 if n in ('USB_RAMPED','USB_SLEW_CT','USB_QOD_NC'):return True
 # Former host load-switch fanout is rebuilt as a sense-only network.
 if n=='VBUS_IN':return True
 # Open self-power selection strap; the ground plane has no assigned pad
 # on the now-open PSELF pin.
 if n=='GND' and t.GetClass()=='PCB_TRACK' and point_segment(p.ToMM(old_pself),p.ToMM(t.GetStart()),p.ToMM(t.GetEnd()))<.5:return True
 if n=='GND' and t.GetClass()=='PCB_VIA':
  xy=p.ToMM(old_pself)
  if math.dist(p.ToMM(t.GetPosition()),xy)<2 and point_segment(p.ToMM(t.GetPosition()),xy,(xy[0]+1.5,xy[1]))<.25:return True
 if n=='GND' and t.GetClass()=='PCB_VIA' and any(math.dist(p.ToMM(t.GetPosition()),q)<.001 for q in ((51.2,64),(52.8,64))):return True
 return False

for cell,c in CELLS.items():
 path=ROOT/c['board'];assert path.exists(),('missing source cell',path)
 source_files[cell]=dict(path=str(path.relative_to(ROOT)),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 src=b if cell=='base' else p.LoadBoard(str(path));sources.append(src);shift=vec(c['position'])
 for original in list(src.GetFootprints()):
  oldref=original.GetReference()
  if oldref in c['exclude']:
   excluded_landings.setdefault(cell,{})[oldref]=[
    dict(pin=q.GetNumber(),net=netmap(cell,q.GetNetname()),
         position_mm=[v+c['position'][i] for i,v in enumerate(p.ToMM(q.GetPosition()))])
    for q in original.Pads() if q.GetNumber()]
   if cell=='base':remove(original)
   continue
  ref=refmap(oldref,c['offset']);assert ref in spec,(cell,ref)
  f=original if cell=='base' else p.Cast_to_FOOTPRINT(original.Duplicate())
  if cell!='base':b.Add(f)
  f.Move(shift);f.SetReference(ref);f.SetValue(spec[ref]['value']);f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
  if ref in ('J101','J501'):
   f.SetFPID(p.LIB_ID('Robot_PDB','AMASS_XT30PW_F_2oz'))
   for pad in f.Pads():
    if not pad.GetNumber() and p.ToMM(pad.GetDrillSize())==(1.,1.):pad.SetSize(vec((1.52,1.52)))
  if ref=='J10':
   f.SetFPID(p.LIB_ID('Robot_PDB','USB_C_HRO_31M12_2oz'))
   for pad in f.Pads():
    if pad.GetNumber()=='S1':
     size=p.ToMM(pad.GetSize());pad.SetSize(vec((size[0]+.12,size[1]+.12)))
  if spec[ref].get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
  for pad in f.Pads():
   n=spec[ref]['pins'].get(pad.GetNumber())
   if not pad.GetNumber() and pad.IsOnLayer(p.F_Cu) and pad.GetNetname():n=netmap(cell,pad.GetNetname())
   pad.SetNet(g.net(n)) if n else pad.SetNetCode(0)
 for original in list(src.GetTracks()):
  if drop_track(cell,original):
   if cell=='base':remove(original)
   continue
  n=original.GetNetname()
  if cell=='base' and n=='V5_USB' and hub_region(original.GetStart()) and hub_region(original.GetEnd()):n='V5_USB_HUB'
  t=original if cell=='base' else original.Duplicate()
  if cell!='base':b.Add(t)
  t.Move(shift);t.SetNet(g.net(netmap(cell,n)))
 for original in list(src.Zones()):
  n=original.GetNetname()
  if original.GetLayer()==p.In1_Cu or cell=='base' and n in ('V5_USB','USB_RAMPED','VBUS_IN'):
   if cell=='base':remove(original)
   continue
  z=original if cell=='base' else p.Cast_to_ZONE(original.Duplicate())
  if cell!='base':b.Add(z)
  z.Move(shift);z.SetNet(g.net(netmap(cell,n)));z.UnFill()
 for d in list(src.GetDrawings()):
  if cell=='base':remove(d)

# Reuse the reviewed ideal-diode gate/VCAP cell in the top service strip.
stage=p.LoadBoard(str(ROOT/CELLS['base']['board']));sources.append(stage)
stage_refs={'U1':'U9910','Q1':'Q9910','C1':'C9910','C2':'C9911'}
stage_nets={'VBAT_L':'MOTOR_FUSED_INPUT','VIN':'MOTOR_VIN','Q1_G':'MOTOR_INPUT_GATE','U1_VCAP':'MOTOR_INPUT_VCAP','GND':'GND'}
for original in stage.GetFootprints():
 if original.GetReference() not in stage_refs:continue
 ref=stage_refs[original.GetReference()];f=p.Cast_to_FOOTPRINT(original.Duplicate());b.Add(f);f.Move(vec(stage_delta));f.SetReference(ref);f.SetValue(spec[ref]['value']);f.Reference().SetLayer(p.F_Fab)
 for pad in f.Pads():
  n=spec[ref]['pins'].get(pad.GetNumber())
  if not pad.GetNumber() and pad.GetNetname():n=stage_nets.get(pad.GetNetname())
  pad.SetNet(g.net(n)) if n else pad.SetNetCode(0)
for original in stage.GetTracks():
 n=original.GetNetname()
 if n not in stage_nets or not all(19<=xy[0]<=34 and 52<=xy[1]<=68 for xy in (p.ToMM(original.GetStart()),p.ToMM(original.GetEnd()))):continue
 t=original.Duplicate();b.Add(t);t.Move(vec(stage_delta));t.SetNet(g.net(stage_nets[n]))
fps={f.GetReference():f for f in b.GetFootprints()};g.fps=fps
# The larger board has room for this support below the source-cell corner.
# Relocating the old NPTH keeps the USB support cell eightmm closer to U10.
fps['H6'].SetPosition(vec((238,150)))
placements={'F7000':(125,145,0),'J3':(48,90,90),'H9910':(58,132,0),'H9911':(86,132,0),'H9912':(64,96,0)}
for ref,(x,y,angle) in placements.items():
 s=spec[ref];lib,name=s['fp'].split(':');directory=CUSTOM if lib=='Robot_PDB' else FPROOT/(lib+'.pretty')
 f=p.FootprintLoad(str(directory),name);assert f,(ref,s['fp']);b.Add(f);fps[ref]=f
 f.SetReference(ref);f.SetValue(s['value']);f.SetFPID(p.LIB_ID(lib,name));f.SetPosition(vec((x,y)));f.SetOrientationDegrees(angle);f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
 if s.get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
 for q in f.Pads():
  n=s['pins'].get(q.GetNumber());q.SetNet(g.net(n)) if n else q.SetNetCode(0)
  if ref in ('J3','F7000'):q.SetZoneConnection(p.ZONE_CONNECTION_FULL)
for layer in ('F','B'):g.zone('+24V',layer,[(44,84.5),(49.2,84.5),(49.2,92),(44,92)],10,.3,minw=.5)
g.outline(*BOARD_SIZE_MM);b.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
w,h=BOARD_SIZE_MM;g.zone('GND','In1',[(.5,.5),(w-.5,.5),(w-.5,h-.5),(.5,h-.5)],0,.25)
g.text('ROBOT PDB v0.8 DEVELOPMENT',220,180,1);g.text('STOP BEFORE MASTER OFF',220,183,1)
g.text('WHEELS22.34V + RESISTOR CLAMP',250,160,1)
g.text('3R3 100W + NC THERMAL REQUIRED',270,163,1)
g.text('CAMERA / MIC: CONNECT TO JETSON',220,187,1)
service_evidence=service_off_v08.add_headers(b)
label_evidence=label_v08.add_labels(b)
fps={f.GetReference():f for f in b.GetFootprints()};assert set(fps)==set(spec),(set(fps)^set(spec))
sheet=(K/'robot_pdb.kicad_sch').read_text();ids={r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(ids)==set(fps)
for ref,f in fps.items():f.SetPath(p.KIID_PATH('/'+ids[ref]))
profile=json.loads((ROOT/'revisions/v0.6/kicad/robot_pdb.kicad_pro').read_text())
rules=profile['board']['design_settings']['rules'];rules['min_through_hole_diameter']=.2;rules['min_via_diameter']=.4
profile_bytes=(json.dumps(profile,indent=2)+'\n').encode();(K/'robot_pdb.kicad_pro').write_bytes(profile_bytes)
libs=sorted({s['fp'].split(':')[0] for s in PARTS})
(K/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{l}")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty' if l=='Robot_PDB' else '${KICAD7_FOOTPRINT_DIR}/'+l+'.pretty')+'")(options "")(descr ""))\n' for l in libs)+')\n')
out=K/'robot_pdb.kicad_pcb';b.SetFileName(str(out));p.SaveBoard(str(out),b);(K/'robot_pdb.kicad_pro').write_bytes(profile_bytes)
subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(out),str(K.parent/'composition-drc.rpt')],check=True)
(K.parent/'composition.json').write_text(json.dumps(dict(status='DEVELOPMENT COMPOSITION; INTERCELL LINKS OPEN; NOT RELEASED',
 source_files=source_files,board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
 generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 inventory_sha256=hashlib.sha256(Path(__file__).with_name('rev08.py').read_bytes()).hexdigest(),
 components=len(fps),service_headers=service_evidence,excluded_landings=excluded_landings,
 functional_labels=label_evidence,label_generator_sha256=hashlib.sha256(Path(label_v08.__file__).read_bytes()).hexdigest(),
 integration_relocated_mounts={'H6':[238,150]}),indent=2)+'\n')
print('Saved v0.8 development composition',len(fps),'parts')
