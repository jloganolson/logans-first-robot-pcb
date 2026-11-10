"""Verify the actual v0.5 schematic export, PCB and DRC. Writes review evidence."""
import collections
import csv
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET

import pcbnew as pcb
from rev05 import PARTS

out=Path(__file__).resolve().parents[2]/'revisions/v0.5'
base=out/'kicad/robot_pdb'
with tempfile.TemporaryDirectory() as tmp:
    xml=Path(tmp)/'schematic.xml'
    subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),str(base.with_suffix('.kicad_sch'))],check=True)
    sheet=ET.parse(xml)
b=pcb.LoadBoard(str(base.with_suffix('.kicad_pcb')))
parts={p['ref']:p for p in PARTS}
footprints={f.GetReference():f for f in b.GetFootprints()}
assert parts.keys()==footprints.keys()
boardnets=collections.defaultdict(set)
for ref,f in footprints.items():
    for p in f.Pads():
        num=p.GetNumber()
        if num:
            assert p.GetNetname()==parts[ref]['pins'].get(num,''),(ref,num)
            if p.GetNetname():
                boardnets[p.GetNetname()].add(ref+'.'+num)
schnets={n.get('name').lstrip('/'):{p.get('ref')+'.'+p.get('pin') for p in n.findall('node')} for n in sheet.findall('./nets/net')}
multi={k:v for k,v in boardnets.items() if len(v)>1}
assert multi=={k:v for k,v in schnets.items() if len(v)>1}
for component in sheet.findall('./components/comp'):
    f=footprints[component.get('ref')]
    assert str(f.GetPath().AsString()).strip('/')==component.findtext('tstamps').strip()
assert boardnets['PACK_A_POS']=={'J1.2','SW1.1'}
assert boardnets['PACK_B_POS']=={'J4.2','SW1.3'}
assert boardnets['VBAT']=={'SW1.2','SW1.4','F1.2','F2.2'}
assert {ref for ref in footprints if ref.startswith(('J30','J40'))}=={'J301','J302','J401'}
for ref,rail,signal in [('J301','+5V_SRV','DXL330_DATA'),('J302','+5V_SRV','DXL330_DATA'),('J401','+12V_SRV','DXL430_DATA')]:
    for num,net in enumerate(('GND',rail,signal),1):
        assert f'{ref}.{num}' in boardnets[net]
assert [footprints[r].GetValue() for r in ('R301','R302','R401','R402')]==['39k','7.5k','30k','2.4k']
drc=(out/'drc.rpt').read_text()
assert 'Severity: error' not in drc and '** Found 0 unconnected pads **' in drc
rows=collections.Counter(re.findall(r'^\[([^]]+)\]',drc,re.M))
summary={'revision':'0.5 engineering review','footprints':len(parts),'compared_multi_pin_nets':len(multi),
         'input_nets':{n:sorted(boardnets[n]) for n in ('PACK_A_POS','PACK_B_POS','VBAT')},
         'physical_DRC_errors':0,'unconnected_pads':0,'DRC_warnings':rows}
(out/'validation.json').write_text(json.dumps(summary,indent=2)+'\n')
with (out/'review-parts.csv').open('w',newline='') as stream:
    w=csv.writer(stream)
    w.writerow(['Reference','Value','Footprint','Part description','Supplier code (review only)'])
    for ref,p in sorted(parts.items()):
        if not p['dnp']:
            w.writerow([ref,p['value'],p['fp'],p['mpn'],p['lcsc'] if ref not in ('FB1','FB2') else 'HOLD - old order code is incorrect'])
print(json.dumps(summary))
