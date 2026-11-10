"""Export component drawings only when the cell's independent audit is current."""
import sys,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
CELLS={'motor_addon':('motor-addon','motor_supply'),'usb_power':('usb-power','usb_power'),
       'robot_io':('robot-io','robot_io'),'usb3_frontend':('usb3-front-end','usb3_frontend')}
for name in sys.argv[1:]:
 folder,project=CELLS[name];pcb=ROOT/'revisions'/folder/'kicad'/f'{project}.kicad_pcb';out=ROOT/'outputs'/f'{folder}-design'
 report=json.loads((out/'validation.json').read_text())
 assert report['status']=='PASS',f'{name}: independent audit has not passed'
 assert report['sha256'][str(pcb.relative_to(ROOT))]==hashlib.sha256(pcb.read_bytes()).hexdigest(),f'{name}: audit predates this PCB'
 subprocess.run(['kicad-cli','pcb','export','svg','--layers','F.Fab,Edge.Cuts','--black-and-white','--page-size-mode','2','--exclude-drawing-sheet','-o',str(out/'assembly-top.svg'),str(pcb)],check=True)
 print('Exported',folder)
