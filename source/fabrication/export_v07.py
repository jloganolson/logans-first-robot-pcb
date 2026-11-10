"""Gate v0.7 quote artifacts on current native and independent evidence.

This prepares a reviewable prototype quote. Factory matching/placement and
hardware commissioning remain required; running an export never purchases.
"""
from pathlib import Path
import sys,re,csv,json,subprocess,zipfile,hashlib,collections
import xml.etree.ElementTree as ET
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'source/generator'))
from rev07 import PARTS,CELLS
from audit_factory_drills import audit as audit_drills
from gate_v07_intercell import evaluate as intercell_gate
from impedance_image_v07 import create as impedance_image
R=ROOT/'revisions/v0.7';K=R/'kicad';O=ROOT/'outputs/v07-order-preparation';O.mkdir(exist_ok=True)
PCB=K/'robot_pdb.kicad_pcb';SCH=K/'robot_pdb.kicad_sch'
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(args):
 r=subprocess.run(['kicad-cli']+list(map(str,args)),capture_output=True,text=True)
 with (O/'export.log').open('a') as log:log.write(' '.join(map(str,args))+'\n'+r.stdout+r.stderr+'\n')
 r.check_returncode()
for folder in ('motor-addon','usb-power','robot-io','usb3-front-end'):
 report=json.loads((ROOT/'outputs'/f'{folder}-design/validation.json').read_text())
 assert report['status']=='PASS',(folder,'cell audit failed')
 assert all(digest(ROOT/name)==value for name,value in report['sha256'].items()),(folder,'cell audit stale')
subprocess.run([sys.executable,'-B',str(ROOT/'source/fabrication/audit_usb3_lanes.py')],check=True)
si=json.loads((ROOT/'outputs/usb3-design/signal-integrity-audit.json').read_text())
assert si['status']=='PASS','USB geometry/reference/channel audit failed'
assert si.get('sha256') and all(digest(ROOT/name)==value for name,value in si['sha256'].items()),'USB geometry/reference/channel audit stale'
subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(PCB),str(R/'drc.rpt')],check=True)
b=p.LoadBoard(str(PCB))
rpt=(R/'drc.rpt').read_text()
assert 'Severity: error' not in rpt,'Combined native DRC failed; see revisions/v0.7/drc.rpt'
assert '** Found 0 unconnected pads **' in rpt,'Combined PCB has open nets'
for script,args in [
 ('audit_v07_links.py',[PCB,R]),
 ('audit_v07_copper.py',[PCB,R/'integration-routing.json',R]),
 ('audit_v07_usb_isolation.py',[PCB,R]),
 ('audit_v07_hs_keepout.py',[PCB,R]),
]:
 subprocess.run([sys.executable,str(ROOT/'source/fabrication'/script),*map(str,args)],check=True)
links=intercell_gate(PCB,R)
(O/'intercell-release-gate.json').write_text(json.dumps(links,indent=2)+'\n')
assert links['pass'],'Inter-cell connectivity, channel or isolation gate failed'
composition=json.loads(PCB.with_suffix('.composition.json').read_text())
routing=json.loads((R/'integration-routing.json').read_text())
assert routing['source_sha256']==composition['composed_board_sha256'],'Routing did not use the recorded labeled composition'
assert composition['generator_sha256']==digest(ROOT/'source/generator/build_v07.py'),'Composition builder changed'
assert composition['inventory_sha256']==digest(ROOT/'source/generator/rev07.py'),'Composition inventory changed'
assert composition.get('label_generator_sha256')==digest(ROOT/'source/generator/label_v07.py'),'Functional legends missing or stale'
assert set(composition['source_files'])==set(CELLS),'Composition source inventory incomplete'
for cell,item in composition['source_files'].items():
 assert item['sha256']==digest(ROOT/CELLS[cell]['board']),(cell,'Composed copper differs from current audited cell')
drills=audit_drills(PCB);(O/'factory-drill-audit.json').write_text(json.dumps(drills,indent=2)+'\n')
assert drills['status']=='PASS','Manufacturer drill geometry failed'
run(['sch','export','netlist','--format','kicadxml','-o',O/'schematic-netlist.xml',SCH])
expected={n.attrib['name'].lstrip('/'):{(a.attrib['ref'],a.attrib['pin']) for a in n.findall('node')} for n in ET.parse(O/'schematic-netlist.xml').findall('.//nets/net')}
actual=collections.defaultdict(set);parts={q['ref']:q for q in PARTS};fps={f.GetReference():f for f in b.GetFootprints()}
assert set(fps)==set(parts),(set(fps)^set(parts))
for ref,f in fps.items():
 assert str(f.GetFPID().GetUniStringLibId())==parts[ref]['fp'],(ref,'footprint mismatch')
 for pad in f.Pads():
  if not pad.GetNumber():continue
  assert pad.GetNetname()==parts[ref]['pins'].get(pad.GetNumber(),''),(ref,pad.GetNumber(),'pad/net mismatch')
  if pad.GetNetname():actual[pad.GetNetname()].add((ref,pad.GetNumber()))
expected={n:s for n,s in expected.items() if len(s)>1};actual={n:s for n,s in actual.items() if len(s)>1}
mismatches={n:dict(schematic=sorted(expected.get(n,set())),PCB=sorted(actual.get(n,set()))) for n in expected.keys()|actual.keys() if expected.get(n,set())!=actual.get(n,set())}
assert not mismatches,mismatches
assert actual['PACK_A_POS']=={('J1','2'),('J5','1')}
assert actual['PACK_B_POS']=={('J4','2'),('J5','3')}
assert {('J5','2'),('J5','4'),('F1','2'),('F2','2')}<=actual['VBAT']
assert parts['F1']['pins']['1']=='MOTOR_FUSED_INPUT'
assert {parts['Q9910']['pins'][i] for i in ('1','2','3')}=={'MOTOR_FUSED_INPUT'}
assert parts['Q9910']['pins']['5']=='MOTOR_VIN'
assert parts['U10']['pins']['18']=='NC_HUB_PSELF'
assert parts['U9901']['pins']['7']=='H_V33'
assert parts['FB1']['pins']['1']=='CHILD_LIMITED_5V'
assert parts['J3']['fp']=='Robot_PDB:MicroFit_43045_0412_4P_2oz'
assert parts['J3']['pins']=={'1':'+24V','2':'+24V','3':'GND','4':'GND'}
# Official2147551040 revA cable continuity swaps only within polarity groups.
thor_cable={1:2,2:1,3:4,4:3}
assert all(parts['J3']['pins'][str(a)]==parts['J3']['pins'][str(z)] for a,z in thor_cable.items())
assert abs(p.ToMM(b.GetDesignSettings().GetBoardThickness())-.8)<1e-6
fitted={s['ref'] for s in PARTS if not s.get('dnp')};assert all(parts[r].get('lcsc') for r in fitted)
groups=collections.defaultdict(list)
for ref in sorted(fitted):
 q=parts[ref];groups[(q['value'],q['fp'],q['lcsc'])].append(ref)
with (O/'BOM_JLCPCB.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Comment','Designator','Footprint','LCSC Part #'])
 for (v,fp,lcsc),refs in groups.items():w.writerow([v,','.join(refs),fp.split(':')[1],lcsc])
# These starting offsets inherit already-inspected package conventions. Every
# new polarized footprint still needs its real supplier placement reviewed.
rotfix=[(r'^SOT-23',-90),(r'^LQFP-',270),(r'^HTSSOP-',270),(r'^VSSOP-8_',180),(r'^TDSON-8-1',270),(r'^CP_Elec_10x10',180),(r'^(.*?_|V)?QFN-(16|20|24|28|40|56)(-|_|$)',270)]
overrides_path=O/'factory-placement-overrides.json'
overrides=json.loads(overrides_path.read_text()) if overrides_path.exists() else {'U14':0}
run(['pcb','export','pos','--format','csv','--units','mm','--side','both','-o',O/'raw-positions.csv',PCB])
placements=[]
with (O/'CPL_JLCPCB.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Designator','Mid X','Mid Y','Layer','Rotation'])
 for row in csv.DictReader((O/'raw-positions.csv').open()):
  ref=row['Ref']
  if ref not in fitted:continue
  fp=parts[ref]['fp'].split(':')[1];add=overrides.get(ref,next((v for pat,v in rotfix if re.match(pat,fp)),0));rotation=(float(row['Rot'])+add)%360
  side='Top' if row['Side']=='top' else 'Bottom'
  w.writerow([ref,row['PosX'],row['PosY'],side,rotation]);placements.append(dict(ref=ref,layer=side,kicad_rotation=row['Rot'],offset=add,quote_rotation=rotation))
assert {q['ref'] for q in placements}==fitted
with (O/'hand-fit-and-harness.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Reference','Description','Supplier part','Status'])
 for q in PARTS:
  if q.get('dnp'):w.writerow([q['ref'],q.get('mpn','') or q['value'],q.get('lcsc',''),q.get('status','')])
 w.writerow(['Thor power cable','Molex2147551042,300mm18AWG four circuits, factory crimped','900-2147551042-ND','Official drawing verifies1↔2 and3↔4; check fit and meter delivered cable polarity before connecting Thor'])
 w.writerow(['Board supports','Insulating M3 supports, underside clearance for3.18mm header tails, separate cable strain relief','Separate procurement','0.8mm board must not carry heavy cable insertion forces unsupported'])
 w.writerow(['External switch','DC-rated DPST, four heavy wires; stop before OFF','Separate procurement','Do not substitute a two-wire switch after packs join'])
 w.writerow(['Brake resistor','Vishay NH1003R300FE01, 3.3 ohm 100W chassis, verified thermal mounting required','Separate procurement','Supplier availability and mounted pulse qualification required'])
 w.writerow(['Thermal cutoff','SCHOTT SEFUSE SM110A0, normally closed one shot','Separate procurement','Crimp/weld; thermal mounting and overshoot qualification required'])
 w.writerow(['Harness','Pack-source fuses, heavy conductors, strain relief, Dynamixel cables, wheel power/CAN','Separate procurement','Qualify full assembled harness before battery operation'])
G=O/'gerbers';G.mkdir(exist_ok=True)
assert not any(G.iterdir()),'Export directory must be empty; move the previous frozen quote files first'
run(['pcb','export','gerbers','--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts','--subtract-soldermask','-o',str(G)+'/',PCB])
run(['pcb','export','drill','--format','excellon','--excellon-separate-th','-o',str(G)+'/',PCB])
files=sorted(G.iterdir());assert len([q for q in files if q.suffix not in ('.drl','.gbrjob')])==11
archive=O/'Robot_PDB_v07_Gerbers.zip'
requirements=impedance_image(PCB,O/'USB_IMPEDANCE_REQUIREMENTS.jpg')
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
 for q in files:z.write(q,q.name)
 z.write(requirements,requirements.name)
for side,layers in [('top','F.Cu,F.Silkscreen,Edge.Cuts'),('bottom','B.Cu,B.Silkscreen,Edge.Cuts')]:
 run(['pcb','export','svg','--layers',layers,'--page-size-mode','2','--exclude-drawing-sheet','-o',O/f'board-{side}.svg',PCB])
 run(['pcb','export','svg','--layers',('F' if side=='top' else 'B')+'.Fab,Edge.Cuts','--black-and-white','--page-size-mode','2','--exclude-drawing-sheet','-o',O/f'assembly-{side}.svg',PCB])
run(['sch','export','svg','--exclude-drawing-sheet','-o',str(O/'schematic-svg')+'/',SCH])
hashes={str(q.relative_to(ROOT)):digest(q) for q in [PCB,SCH,PCB.with_suffix('.kicad_pro'),PCB.with_suffix('.kicad_dru'),PCB.with_suffix('.composition.json'),O/'BOM_JLCPCB.csv',O/'CPL_JLCPCB.csv',archive,requirements,O/'intercell-release-gate.json',ROOT/'outputs/usb3-design/lane-orientation-audit.json',ROOT/'outputs/usb3-design/signal-integrity-audit.json']}
report=dict(status='PASS',disposition='ENGINEERING PROTOTYPE QUOTE; actual factory matching, placement and owner purchase review still required',footprints=len(fps),multi_terminal_nets=len(actual),numbered_pad_and_footprint_identity_check='PASS',off_isolation_net_topology='PASS; physical external switch/harness still require continuity test',drc_errors=0,unconnected_pads=0,drc_warnings=rpt.count('Severity: warning'),jlc_fitted_parts=len(fitted),bom_lines=len(groups),placement_sides=dict(collections.Counter(q['layer'] for q in placements)),sha256=hashes,
 limitations=['Custom passive schematic symbols limit ERC coverage; fresh exported netlist and every numbered physical pad were compared.','Native DRC and these checks do not qualify current capacity, fuse coordination, battery sharing, braking, USB performance, firmware safety or thermal behavior.','Starting CPL offsets require actual factory preview validation, including underside parts and new custom footprints.'])
(O/'validation.json').write_text(json.dumps(report,indent=2)+'\n');(O/'placement-offsets.json').write_text(json.dumps(placements,indent=2)+'\n');print(json.dumps(report,indent=2))
