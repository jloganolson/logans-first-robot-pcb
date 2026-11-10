"""Export v0.6 engineering-prototype quote files, with native and independent checks."""
from pathlib import Path
import sys,os,re,csv,json,subprocess,zipfile,hashlib,xml.etree.ElementTree as ET
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'source/generator'))
from rev06 import PARTS
R=ROOT/'revisions/v0.6';K=R/'kicad';O=ROOT/'outputs/v06-order-preparation';O.mkdir(exist_ok=True);G=O/'gerbers';G.mkdir(exist_ok=True)
PCB=K/'robot_pdb.kicad_pcb';SCH=K/'robot_pdb.kicad_sch';b=p.LoadBoard(str(PCB))
def run(args):
 r=subprocess.run(['kicad-cli']+list(map(str,args)),capture_output=True,text=True);(O/'export.log').open('a').write(' '.join(map(str,args))+'\n'+r.stdout+r.stderr+'\n');r.check_returncode()
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(PCB),b);b=p.LoadBoard(str(PCB));p.WriteDRCReport(b,str(R/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
rpt=(R/'drc.rpt').read_text();assert 'Severity: error' not in rpt,rpt
assert '** Found 0 unconnected pads **' in rpt
run(['sch','export','netlist','--format','kicadxml','-o',O/'schematic-netlist.xml',SCH])
x=ET.parse(O/'schematic-netlist.xml');expected={}
for n in x.findall('.//nets/net'):expected[n.attrib['name'].lstrip('/')]={a.attrib['ref']+'.'+a.attrib['pin'] for a in n.findall('node')}
actual={};fps={f.GetReference():f for f in b.GetFootprints()}
for ref,f in fps.items():
 for pad in f.Pads():
  if pad.GetNumber() and pad.GetNetname():actual.setdefault(pad.GetNetname(),set()).add(ref+'.'+pad.GetNumber())
mismatches={n:{'schematic':sorted(e),'board':sorted(actual.get(n,set()))} for n,e in expected.items() if len(e)>1 and actual.get(n,set())!=e}
assert not mismatches,mismatches
parts={q['ref']:q for q in PARTS};assert set(fps)==set(parts)
# Check footprint identities and every numbered pad against the authoritative circuit inventory.
for ref,f in fps.items():
 assert str(f.GetFPID().GetUniStringLibId())==parts[ref]['fp'],ref
 for pad in f.Pads():
  if pad.GetNumber():assert pad.GetNetname()==parts[ref]['pins'].get(pad.GetNumber(),''),(ref,pad.GetNumber(),pad.GetNetname())
# OFF isolation follows the physical conductor graph: neither pack positive has any
# board connection to VBAT. Closing two EXTERNAL contacts adds those two edges.
assert actual['PACK_A_POS']=={'J1.2','J5.1'}
assert actual['PACK_B_POS']=={'J4.2','J5.3'}
assert {'J5.2','J5.4','F1.2','F2.2'}<=actual['VBAT']
assert parts['U18']['pins']=={'1':'VBUS_IN','2':'GND','3':'VBUS_IN','4':'USB_SLEW_CT','5':'USB_QOD_NC','6':'USB_RAMPED'}
assert parts['FB1']['pins']['1']=='USB_RAMPED'
manual={'F1','F2'}
fitted={q['ref'] for q in PARTS if not q['dnp'] and q['ref'] not in manual}
assert all(parts[r]['lcsc'] for r in fitted)
from collections import defaultdict
groups=defaultdict(list)
for ref in sorted(fitted):
 q=parts[ref];groups[(q['value'],q['fp'],q['lcsc'])].append(ref)
with (O/'BOM_JLCPCB.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Comment','Designator','Footprint','LCSC Part #'])
 for (v,fp,lcsc),refs in groups.items():w.writerow([v,','.join(refs),fp.split(':')[1],lcsc])
# Initial CPL corrections reflect known package conventions; every polarized family
# must still be checked against the manufacturer's actual assembly preview.
rotfix=[(r'^SOT-23',-90),(r'^LQFP-',270),(r'^HTSSOP-',270),(r'^VSSOP-8_',180),(r'^TDSON-8-1',270),(r'^CP_Elec_10x10',180),(r'^(.*?_|V)?QFN-(16|20|24|28|40)(-|_|$)',270),(r'^USB_C_Receptacle_HRO_TYPE-C-31-M-12',180)]
# J10/U14 same footprints and orientations as the previously inspected November 6 board.
overrides={'J10':0,'U14':0}
run(['pcb','export','pos','--format','csv','--units','mm','--side','both','-o',O/'raw-positions.csv',PCB])
placements=[]
with (O/'CPL_JLCPCB.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Designator','Mid X','Mid Y','Layer','Rotation'])
 for row in csv.DictReader((O/'raw-positions.csv').open()):
  ref=row['Ref']
  if ref not in fitted:continue
  fp=parts[ref]['fp'].split(':')[1];add=overrides.get(ref,next((v for pat,v in rotfix if re.match(pat,fp)),0));rotation=(float(row['Rot'])+add)%360
  w.writerow([ref,row['PosX'],row['PosY'],'Top' if row['Side']=='top' else 'Bottom',rotation]);placements.append({'ref':ref,'kicad_rotation':row['Rot'],'offset':add,'quote_rotation':rotation})
assert set(q['ref'] for q in placements)==fitted
with (O/'hand-fit-and-harness.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Reference','Description','Supplier part','Status'])
 for q in PARTS:
  if q['ref'] in manual or q['ref'] in {'J1','J2','J4','J5'}:w.writerow([q['ref'],q['mpn'],q['lcsc'],q['status']])
 w.writerow(['External switch','Albright ED252 dual-pole mechanical disconnect; select mounting variant; stop before OFF','Separate procurement','Not included in PCBA'])
 w.writerow(['Harness','Pack-side fuses, strain relief, 12AWG high-current leads, JST VH-to-Dynamixel split harnesses','Separate procurement','Wire length/derating/fault coordination require qualification'])
run(['pcb','export','gerbers','--layers','F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts','--subtract-soldermask','-o',str(G)+'/',PCB])
run(['pcb','export','drill','--format','excellon','--excellon-separate-th','-o',str(G)+'/',PCB])
files=sorted(G.iterdir());assert len([q for q in files if q.suffix not in ('.drl','.gbrjob')])==11
with zipfile.ZipFile(O/'Robot_PDB_v06_Gerbers.zip','w',zipfile.ZIP_DEFLATED) as z:
 for q in files:z.write(q,q.name)
run(['pcb','export','svg','--layers','F.Cu,F.Silkscreen,Edge.Cuts','--page-size-mode','2','--exclude-drawing-sheet','-o',O/'board-top.svg',PCB])
run(['pcb','export','svg','--layers','B.Cu,Edge.Cuts','--page-size-mode','2','--exclude-drawing-sheet','-o',O/'board-bottom.svg',PCB])
run(['pcb','export','svg','--layers','F.Fab,Edge.Cuts','--black-and-white','--page-size-mode','2','--exclude-drawing-sheet','-o',O/'assembly-top.svg',PCB])
run(['sch','export','svg','--exclude-drawing-sheet','-o',str(O/'schematic-svg')+'/',SCH])
hashes={str(q.relative_to(ROOT)):hashlib.sha256(q.read_bytes()).hexdigest() for q in [PCB,SCH,O/'BOM_JLCPCB.csv',O/'CPL_JLCPCB.csv',O/'Robot_PDB_v06_Gerbers.zip']}
report={'disposition':'ENGINEERING PROTOTYPE QUOTE; assembly preview and owner review pending','footprints':len(fps),'compared_multi_terminal_nets':sum(len(e)>1 for e in expected.values()),'net_mismatches':mismatches,'numbered_pad_and_footprint_identity_check':'PASS','off_isolation_net_topology':'PASS; physical external switch/harness still require continuity test','drc_errors':0,'unconnected_pads':0,'drc_warnings':rpt.count('Severity: warning'),'warnings':'C3/C4/J3 silkscreen artwork moved to fabrication layer; pads/holes unchanged','jlc_fitted_parts':len(fitted),'bom_lines':len(groups),'gerber_drill_files':len(files),'sha256':hashes,'limitations':['KiCad 7 has no automated ERC CLI; generated custom passive pin symbols limit ERC coverage. Fresh independent net and per-pad checks performed.','No automated check establishes thermal, fault interruption/coordination, battery paralleling, regenerative braking, USB compliance or functional bring-up.','CPL is initial; validate actual factory preview before purchasing.']}
(O/'validation.json').write_text(json.dumps(report,indent=2)+'\n');(O/'placement-offsets.json').write_text(json.dumps(placements,indent=2)+'\n');print(json.dumps(report,indent=2))
