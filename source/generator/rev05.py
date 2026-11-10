"""v0.5 circuit inventory, based on the reviewed v0.4.1 circuit."""
from copy import deepcopy
from bigboard import PARTS as BASE_PARTS
from blocks import Netlist, FP_XT60M

PARTS = deepcopy([p for p in BASE_PARTS if p['ref'] not in {'J303','J304','J402','J403'}])
parts = {p['ref']:p for p in PARTS}
parts['J1'].update(value='PACK A (XT60 male)', pins={'1':'GND','2':'PACK_A_POS'})
add = Netlist()
block = parts['J1']['block']
add.P('J4','Connector_Generic:Conn_01x02','PACK B (XT60 male)',FP_XT60M,
      {'1':'GND','2':'PACK_B_POS'},block,'C98732','Amass XT60PW-M','verified')
add.P('SW1','Switch:SW_DPST','PACK DISCONNECT DPST','Robot_PDB:Airpax_IPAP_2Pole_S',
      {'1':'PACK_A_POS','2':'VBAT','3':'PACK_B_POS','4':'VBAT'},block,'',
      'Sensata IPAP, two poles, single handle, type S PCB tails (confirm drawing and rating)','confirm')
PARTS.extend(add.parts)
for ref, value in [('J301','XL330 5V CHAIN A'),('J302','XL330 5V CHAIN B'),('J401','XL430 10.8V CHAIN')]:
    parts[ref]['value']=value

for p in PARTS:
    if p['block'].startswith('E.'):
        p['block']='E. XL330 servo power, 5 V, two daisy-chain sockets'
    elif p['block'].startswith('F.'):
        p['block']='F. XL430 servo power, 10.8 V, one daisy-chain socket'

REVISION = "0.5-review"
SCHEMATIC_NOTES = r"""v0.5 ENGINEERING REVIEW ONLY\nJ1 and J4 accept individually protected 8S packs. SW1 opens both positives ahead of VBAT.\nAfter SW1, F1 feeds J2 and F2 feeds the converters. ON directly parallels both packs.\nJ301/J302 supply XL330 at nominal 5 V. J401 supplies XL430 at 10.8 V. Each daisy chain shares its bus current budget.\nSee the v0.5 handoff for switch, thermal and pack qualification."""
