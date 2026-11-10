"""Independent exported-netlist and physical-pad audits for development cells.

Run under with_kicad.sh. These are cell checks, not a combined-board release.
"""
import argparse,importlib,sys,re,json,hashlib,subprocess,collections
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'source/generator'))
CELLS={'motor_addon':('motor-addon','motor_supply'),'usb_power':('usb-power','usb_power'),
       'robot_io':('robot-io','robot_io'),'usb3_frontend':('usb3-front-end','usb3_frontend')}

def audit(name):
 folder,project=CELLS[name]
 module=importlib.import_module('usb3_frontend_routed' if name=='usb3_frontend' else name)
 k=ROOT/'revisions'/folder/'kicad';out=ROOT/'outputs'/f'{folder}-design';out.mkdir(parents=True,exist_ok=True)
 pcb=k/f'{project}.kicad_pcb';sch=k/f'{project}.kicad_sch';xml=out/'schematic-netlist.xml'
 #Each cell's native rules must load in a fresh process. KiCad7 otherwise
 #caches the first project's settings when auditing several cells together.
 drc_script="import pcbnew as p; b=p.LoadBoard("+repr(str(pcb))+"); p.WriteDRCReport(b,"+repr(str(k.parent/'drc.rpt'))+",p.EDA_UNITS_MILLIMETRES,True)"
 subprocess.run([sys.executable,'-c',drc_script],check=True)
 b=p.LoadBoard(str(pcb))
 r=subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(sch)],capture_output=True,text=True)
 (out/'export.log').write_text(r.stdout+r.stderr);r.check_returncode()
 spec={s['ref']:s for s in module.PARTS};fps={f.GetReference():f for f in b.GetFootprints()}
 checks=[];errors=[]
 def check(label,ok):checks.append({'check':label,'pass':bool(ok)})
 check('all references match circuit inventory',set(fps)==set(spec))
 physical=collections.defaultdict(set)
 for ref,f in fps.items():
  if ref not in spec:continue
  if str(f.GetFPID().GetUniStringLibId())!=spec[ref]['fp']:errors.append([ref,'footprint',str(f.GetFPID().GetUniStringLibId()),spec[ref]['fp']])
  for pad in f.Pads():
   num=pad.GetNumber()
   if not num:continue
   net=pad.GetNetname();expected=spec[ref]['pins'].get(num,'')
   if net!=expected:errors.append([ref,num,net,expected])
   if net:physical[net].add((ref,num))
 check('every numbered pad and footprint matches inventory',not errors)
 schematic={n.attrib['name'].lstrip('/'):{(a.attrib['ref'],a.attrib['pin']) for a in n.findall('node')} for n in ET.parse(xml).findall('.//nets/net')}
 schematic={n:s for n,s in schematic.items() if len(s)>1};physical={n:s for n,s in physical.items() if len(s)>1}
 mismatches={n:{'schematic':sorted(schematic.get(n,set())),'PCB':sorted(physical.get(n,set()))} for n in schematic.keys()|physical.keys() if schematic.get(n,set())!=physical.get(n,set())}
 check('independently exported schematic and PCB nets agree',not mismatches)
 rpt=(k.parent/'drc.rpt').read_text();drc_errors=rpt.count('Severity: error')
 check('native DRC has no errors',drc_errors==0)
 check('native DRC has no unconnected pads','** Found 0 unconnected pads **' in rpt)
 missing=[s['ref'] for s in module.PARTS if not s.get('dnp') and not s.get('lcsc')]
 check('every assembly part has supplier identifier',not missing)
 report={'cell':name,'inventory_module':module.__name__,'status':'PASS' if all(c['pass'] for c in checks) else 'FAIL',
  'disposition':'DEVELOPMENT CELL ONLY; final combined board, assembly preview and qualification remain open',
  'checks':checks,'footprints':len(fps),'multi_terminal_nets':len(physical),'drc_errors':drc_errors,'drc_warnings':rpt.count('Severity: warning'),
  'pad_errors':errors,'net_mismatches':mismatches,'missing_supplier_ids':missing,
  'sha256':{str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (pcb,sch,pcb.with_suffix('.kicad_pro'),pcb.with_suffix('.kicad_dru')) if f.exists()},
  'limitations':['Custom passive symbols do not provide comprehensive ERC coverage.','Logical agreement and DRC do not establish electrical, thermal, protection, USB or firmware qualification.']}
 (out/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('cell','status','footprints','multi_terminal_nets','drc_errors','drc_warnings','pad_errors','missing_supplier_ids')}))
 return report['status']=='PASS'

if __name__=='__main__':
 args=argparse.ArgumentParser();args.add_argument('cells',nargs='+',choices=list(CELLS));ns=args.parse_args()
 results=[audit(n) for n in ns.cells];raise SystemExit(0 if all(results) else 1)
