"""Compose separately audited cells into one physical v0.7 PCB.

Never writes a fabrication archive. Native DRC and final electrical/manufacturer
review are required after integration. Cell reference/net maps live in rev07.py.
"""
import os,re,json,math,shutil,argparse,subprocess,sys,hashlib
from pathlib import Path
import pcbnew as p
from cells import Board
from indexed_fixer import IndexedFixer
from rev07 import PARTS,CELLS,netmap,refmap,BOARD_SIZE_MM,INTEGRATION_PLACEMENTS

ROOT=Path(__file__).resolve().parents[2];K=ROOT/'revisions/v0.7/kicad';K.mkdir(parents=True,exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=K/'robot_pdb.kicad_pcb');parser.add_argument('--usb-board',type=Path);args=parser.parse_args()
# Preserve the manufacturer's hole locations and drill sizes, while providing
# the published 2oz annulus around the XT30's two mechanical solder lugs.
xt30=(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/'Connector_AMASS.pretty/AMASS_XT30PW-F_1x02_P2.50mm_Horizontal.kicad_mod').read_text()
assert xt30.count('(size 1.4 1.4)')==2
xt30=xt30.replace('"AMASS_XT30PW-F_1x02_P2.50mm_Horizontal"','"AMASS_XT30PW_F_2oz"',1).replace('(size 1.4 1.4)','(size 1.52 1.52)')
(K/'Robot_PDB.pretty').mkdir(exist_ok=True);(K/'Robot_PDB.pretty/AMASS_XT30PW_F_2oz.kicad_mod').write_text(xt30)
microfit=(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/'Connector_Molex.pretty/Molex_Micro-Fit_3.0_43045-0412_2x02_P3.00mm_Vertical.kicad_mod').read_text()
assert microfit.count('(size 1.5 1.5)')==4
microfit=microfit.replace('"Molex_Micro-Fit_3.0_43045-0412_2x02_P3.00mm_Vertical"','"MicroFit_43045_0412_4P_2oz"',1).replace('(size 1.5 1.5)','(size 1.54 1.54)')
(K/'Robot_PDB.pretty/MicroFit_43045_0412_4P_2oz.kicad_mod').write_text(microfit)
spec={s['ref']:s for s in PARTS};dead=[];sources=[];custom_sources={};source_files={}
b=p.LoadBoard(str(ROOT/CELLS['base']['board']));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[]
old_pself=next(q for q in b.FindFootprintByReference('U10').Pads() if q.GetNumber()=='18').GetPosition()
old_pself=p.VECTOR2I(old_pself.x,old_pself.y)
def vector(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
def remove(x):dead.append(x);b.Remove(x)
def drop_track(cell,t):
 n=t.GetNetname()
 if cell=='usb' and n in ('HUB_CHILD_DP','HUB_CHILD_DM'):
  # Keep the native-checked package escapes and their fine landing vias.
  # Only the standalone header-side stub is replaced by the inter-cell link.
  # The same bounded package region is used by the integration SI review.
  return not all(58.5<=xy[0]<=71.5 and 50.5<=xy[1]<=63.5
                 for xy in (p.ToMM(t.GetStart()),p.ToMM(t.GetEnd())))
 if cell=='base':
  if n in ('USB_DP','USB_DM','USB_RAMPED','VBUS_IN','USB_CC1','USB_CC2','USB_SLEW_CT','USB_QOD_NC','+5V_OAK') or n.startswith('O_'):return True
  # Open the CH334F self-power strap physically as well as in the netlist.
  if n=='GND' and any(math.dist(p.ToMM(q),p.ToMM(old_pself))<.4 for q in (t.GetStart(),t.GetEnd())):return True
  # The replacement Thor header's locating peg at (51.94,84) occupies
  # these old XT30-area stitching locations after the base's +20mm shift.
  # Both are unanchored GND stitches, not signal/power track transitions.
  if n=='GND' and isinstance(t,p.PCB_VIA) and any(math.dist(p.ToMM(t.GetPosition()),q)<.001 for q in ((51.2,64),(52.8,64))):
   assert not any(not isinstance(q,p.PCB_VIA) and (q.GetStart()==t.GetPosition() or q.GetEnd()==t.GetPosition()) for q in sources[0].GetTracks())
   return True
 return False

for cell,c in CELLS.items():
 path=args.usb_board if cell=='usb' and args.usb_board else ROOT/c['board']
 source_files[cell]=dict(path=str(path.resolve()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 src=b if cell=='base' else p.LoadBoard(str(path));sources.append(src)
 shift=vector(*c['position'])
 # Project-local footprints remain exact manufacturer-specific definitions.
 custom=Path(ROOT/c['board']).parent/'Robot_PDB.pretty'
 if custom.exists():
  (K/'Robot_PDB.pretty').mkdir(exist_ok=True)
  for f in custom.glob('*.kicad_mod'):
   target=K/'Robot_PDB.pretty'/f.name
   if f.name in custom_sources and custom_sources[f.name]!=f.read_bytes():raise AssertionError(('conflicting current cell footprints',f.name,cell))
   custom_sources[f.name]=f.read_bytes()
   if f.name=='Fuse_Schurter_SHF_6.3x32_P40mm.kicad_mod':continue
   shutil.copyfile(f,target)
 for original in list(src.GetFootprints()):
  oldref=original.GetReference()
  if oldref in c['exclude']:
   if cell=='base':remove(original)
   continue
  ref=refmap(oldref,c['offset']);assert ref in spec,(cell,oldref)
  f=original if cell=='base' else p.Cast_to_FOOTPRINT(original.Duplicate())
  if cell!='base':b.Add(f)
  f.Move(shift)
  f.SetReference(ref);f.SetValue(spec[ref]['value']);f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
  if ref in ('J101','J501'):
   f.SetFPID(p.LIB_ID('Robot_PDB','AMASS_XT30PW_F_2oz'))
   for pad in f.Pads():
    if not pad.GetNumber() and p.ToMM(pad.GetDrillSize())==(1.,1.):pad.SetSize(vector(1.52,1.52))
  if spec[ref].get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
  for pad in f.Pads():
   net=spec[ref]['pins'].get(pad.GetNumber())
   # Physically common unnumbered copper lobes inherit their cell's net.
   if not pad.GetNumber() and pad.IsOnLayer(p.F_Cu) and pad.GetNetname():net=netmap(cell,pad.GetNetname())
   pad.SetNet(g.net(net)) if net else pad.SetNetCode(0)
 for original in list(src.GetTracks()):
  if drop_track(cell,original):
   if cell=='base':remove(original)
   continue
  t=original if cell=='base' else original.Duplicate()
  if cell!='base':b.Add(t)
  t.Move(shift)
  t.SetNet(g.net(netmap(cell,original.GetNetname())))
 for original in list(src.Zones()):
  n=original.GetNetname()
  # One continuousL2 return replaces all the per-cell reference planes.
  if original.GetLayer()==p.In1_Cu or cell=='base' and (n=='+5V_OAK' or n.startswith('O_')):
   if cell=='base':remove(original)
   continue
  z=original if cell=='base' else p.Cast_to_ZONE(original.Duplicate())
  if cell!='base':b.Add(z)
  z.Move(shift)
  z.SetNet(g.net(netmap(cell,n)));z.UnFill()
 # Cell edge outlines and connector-interface annotations do not become
 # spurious routed slots or duplicate external-input labels on the mainPCB.
 for d in list(src.GetDrawings()):
  if cell=='base':remove(d)

# Clone only the audited local ideal-diode routes into the vacated camera
# converter area. Broad input/output copper is completed by route_v07.py.
stage=p.LoadBoard(str(ROOT/CELLS['base']['board']));sources.append(stage)
stage_refs={'U1':'U9910','Q1':'Q9910','C1':'C9910','C2':'C9911'}
stage_nets={'VBAT_L':'MOTOR_FUSED_INPUT','VIN':'MOTOR_VIN','Q1_G':'MOTOR_INPUT_GATE','U1_VCAP':'MOTOR_INPUT_VCAP','GND':'GND'}
for original in stage.GetFootprints():
 if original.GetReference() not in stage_refs:continue
 ref=stage_refs[original.GetReference()];f=p.Cast_to_FOOTPRINT(original.Duplicate());b.Add(f);f.Move(vector(4,-51));f.SetReference(ref)
 for pad in f.Pads():
  net=spec[ref]['pins'].get(pad.GetNumber());pad.SetNet(g.net(net)) if net else pad.SetNetCode(0)
for original in stage.GetTracks():
 n=original.GetNetname()
 if n not in stage_nets:continue
 if not all(19<=xy[0]<=34 and 52<=xy[1]<=68 for xy in (p.ToMM(original.GetStart()),p.ToMM(original.GetEnd()))):continue
 t=original.Duplicate();b.Add(t);t.Move(vector(4,-51));t.SetNet(g.net(stage_nets[n]))
fps={f.GetReference():f for f in b.GetFootprints()};g.fps=fps
# The additional low-current branch fuses sit in the inter-cell service strip.
for ref,x,y in [('F7000',90,142),('F8000',165,142)]:
 s=spec[ref];lib,name=s['fp'].split(':');f=p.FootprintLoad(str(K/(lib+'.pretty')),name);assert f is not None
 b.Add(f);f.SetReference(ref);f.SetValue(s['value']);f.SetFPID(p.LIB_ID(lib,name));f.SetPosition(vector(x,y));f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False);fps[ref]=f
 f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
 for q in f.Pads():q.SetNet(g.net(s['pins'][q.GetNumber()]));q.SetZoneConnection(p.ZONE_CONNECTION_FULL)
for ref,x,y,rot in [('J3',48,90,90),('U9900',216,94,0),('R9901',213,99,0),('R9902',216,99,0),('R9905',216,103,0),('C9904',222,103,0),('C9900',212,94,180),('C9901',216,89.5,0),('C9902',224,96,0),('U9901',224,88.5,0),('C9903',228.5,88.5,90)]:
 s=spec[ref];lib,name=s['fp'].split(':');directory=K/(lib+'.pretty') if lib=='Robot_PDB' else Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')
 f=p.FootprintLoad(str(directory),name);assert f is not None,(ref,s['fp']);b.Add(f);fps[ref]=f
 f.SetReference(ref);f.SetValue(s['value']);f.SetFPID(p.LIB_ID(lib,name));f.SetPosition(vector(x,y));f.SetOrientationDegrees(rot);f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
 if s.get('dnp'):f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
 for q in f.Pads():
  net=s['pins'].get(q.GetNumber());q.SetNet(g.net(net)) if net else q.SetNetCode(0)
  if ref=='J3':q.SetZoneConnection(p.ZONE_CONNECTION_FULL)
for ref,connector in [('H9910','J1'),('H9911','J4')]:
 s=spec[ref];lib,name=s['fp'].split(':');f=p.FootprintLoad(str(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/(lib+'.pretty')),name);b.Add(f);fps[ref]=f
 f.SetFPID(p.LIB_ID(lib,name))
 x,y=p.ToMM(fps[connector].GetPosition());f.SetPosition(vector(x,y+18));f.SetReference(ref);f.SetValue(s['value']);f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False)
 f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
f=p.FootprintLoad(str(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/'MountingHole.pretty'),'MountingHole_3.2mm_M3');b.Add(f);fps['H9912']=f
f.SetFPID(p.LIB_ID('MountingHole','MountingHole_3.2mm_M3'))
f.SetReference('H9912');f.SetValue('M3 NYLON SUPPORT');f.SetPosition(vector(64,96));f.Reference().SetLayer(p.F_Fab);f.Value().SetVisible(False);f.SetAttributes(f.GetAttributes()|p.FP_EXCLUDE_FROM_BOM|p.FP_EXCLUDE_FROM_POS_FILES)
assert set(fps)==set(spec),(set(fps)^set(spec))
for ref,(x,y,angle) in INTEGRATION_PLACEMENTS.items():
 fps[ref].SetPosition(vector(x,y));fps[ref].SetOrientationDegrees(angle)
# The Thor header's two positive contacts join the existing output extension.
# Both ground contacts return directly into continuous L2 through their PTHs.
for layer in ('F','B'):g.zone('+24V',layer,[(44,84.5),(49.2,84.5),(49.2,92),(44,92)],10,.3,minw=.5)
g.outline(*BOARD_SIZE_MM)
b.GetDesignSettings().SetBoardThickness(p.FromMM(.8))
w,h=BOARD_SIZE_MM;g.zone('GND','In1',[(.5,.5),(w-.5,.5),(w-.5,h-.5),(.5,h-.5)],0,.25)
g.text('ROBOT PDB v0.7 DEVELOPMENT',220,146,1)
g.text('STOP BEFORE MASTER OFF',220,149,1)
g.text('DALY TELEMETRY INTERFACE RESERVE',248,202,.8,layer=p.F_Fab)
for text,x,y in [('CAN LEFT',312,26),('CAN RIGHT',326,26),('USB TO JETSON',135,253),('OAK-D USB3',165,253),('USB MIC',198,253)]:g.text(text,x,y,1)
sheet=(K/'robot_pdb.kicad_sch').read_text();ids={r:u for u,r in re.findall(r'\(uuid ([^)]*)\)\s+\(property "Reference" "([^"]+)"',sheet)}
assert set(ids)==set(fps),(set(ids)^set(fps))
for ref,f in fps.items():f.SetPath(p.KIID_PATH('/'+ids[ref]))
profile=json.loads((ROOT/'revisions/v0.6/kicad/robot_pdb.kicad_pro').read_text())
rules=profile['board']['design_settings']['rules'];rules['min_through_hole_diameter']=.2;rules['min_via_diameter']=.4
# Preserve the reviewed cell's scoped high-speed rules and remap its nets.
# Native DRC must evaluate the same geometry/rules used for cell approval.
usb_profile=json.loads((ROOT/'revisions/usb3-front-end/kicad/usb3_frontend.kicad_pro').read_text())
for key in ('min_through_hole_diameter','min_via_diameter','min_via_annular_width','min_hole_clearance'):
 rules[key]=min(rules[key],usb_profile['board']['design_settings']['rules'][key])
for nc in usb_profile['net_settings'].get('classes',[]):
 if nc['name']!='Default':
  assert nc['name'] not in {x['name'] for x in profile['net_settings']['classes']}
  profile['net_settings']['classes'].append(nc)
for item in usb_profile['net_settings'].get('netclass_patterns',[]):
 item=dict(item);item['pattern']=netmap('usb',item['pattern']);profile['net_settings'].setdefault('netclass_patterns',[]).append(item)
assign=usb_profile['net_settings'].get('netclass_assignments')
if assign:
 profile['net_settings']['netclass_assignments']={netmap('usb',n):c for n,c in assign.items()}
(K/'robot_pdb.kicad_pro').write_text(json.dumps(profile,indent=2)+'\n')
# Preserve integration-owned pair rules while refreshing the cell-owned native
# geometry rules. These restore the larger-via limits outside tiny escapes.
usb_rules=ROOT/'revisions/usb3-front-end/kicad/usb3_frontend.kicad_dru'
if usb_rules.exists():
 custom=(K/'robot_pdb.kicad_dru');existing=custom.read_text() if custom.exists() else '(version 1)\n'
 begin='# BEGIN v07 USB cell rules';end='# END v07 USB cell rules'
 existing=re.sub(re.escape(begin)+'.*?'+re.escape(end)+'\\s*','',existing,flags=re.S)
 body=re.sub(r'^\s*\(version\s+1\)\s*','',usb_rules.read_text())
 for old in sorted({q.GetNetname() for f in sources[3].GetFootprints() for q in f.Pads()},key=len,reverse=True):
  if old:body=body.replace("'"+old+"'","'"+netmap('usb',old)+"'")
 custom.write_text(existing.rstrip()+'\n'+begin+'\n'+body.rstrip()+'\n'+end+'\n')
libs=sorted({s['fp'].split(':')[0] for s in PARTS})
(K/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{l}")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty' if l=='Robot_PDB' else '${KICAD7_FOOTPRINT_DIR}/'+l+'.pretty')+'")(options "")(descr ""))\n' for l in libs)+')\n')
out=args.output;out.parent.mkdir(parents=True,exist_ok=True);b.SetFileName(str(out))
profile_bytes=(K/'robot_pdb.kicad_pro').read_bytes()
p.SaveBoard(str(out),b)
(K/'robot_pdb.kicad_pro').write_bytes(profile_bytes)
out.with_suffix('.kicad_pro').write_bytes(profile_bytes)
if out.parent!=K:
 shutil.copyfile(K/'robot_pdb.kicad_pro',out.with_suffix('.kicad_pro'))
 if (K/'robot_pdb.kicad_dru').exists():shutil.copyfile(K/'robot_pdb.kicad_dru',out.with_suffix('.kicad_dru'))
# Native cell checks precede integration. This initial composite explicitly
# leaves inter-cell links to the final routing stage rather than inventing
# copper paths or treating matching net names as physical connections.
subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(out),str(out.with_suffix('.composition-drc.rpt'))],check=True)
out.with_suffix('.composition.json').write_text(json.dumps(dict(
 composed_board_sha256=hashlib.sha256(out.read_bytes()).hexdigest(),source_files=source_files,
 generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 inventory_sha256=hashlib.sha256(Path(__file__).with_name('rev07.py').read_bytes()).hexdigest(),
 qualification='Composition provenance only; no routing, DRC or release approval.'),indent=2)+'\n')
print('Saved integrated development PCB',out,'components',len(fps),flush=True)
