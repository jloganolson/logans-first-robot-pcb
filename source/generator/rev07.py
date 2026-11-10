"""Authoritative single-PCB integration inventory for replacement-wheel v0.7.

Development: physical cell checks do not imply the combined PCB is released.
Reference offsets preserve traceability to separately audited cell work products.
"""
import copy,re
import rev06, motor_addon, robot_io, usb_power, usb3_frontend_routed as usb3_frontend
from blocks import Netlist, FP_SOT236

REVISION='0.7 development'
TITLE='Robot PDB: DDSM350, USB3 camera/mic, internal CAN and three PWM servos'
BOARD_SIZE_MM=(340,260)
INTEGRATION_PLACEMENTS={
 'H9910':(58,132,0),'H9911':(79,132,0),'U9900':(240,140,0),
 'C9900':(236,140,180),'C9901':(240,135.5,0),'C9902':(252,140,0),
 'R9901':(240,145,0),'R9902':(244,145,0),'R9905':(233,146,0),
 'C9904':(235,142.5,0),'F7000':(90,142,0),'F8000':(264,121,-90),
 'U9901':(221,114,0),'C9903':(227,114,90),
}
SCHEMATIC_NOTES='Development integration, not fabrication released. External mechanical DPST disconnect; stop before OFF. Two protected8S packs,33.6V full, source-end fuses required. F1 is now15A motor branch, F2 remains30A logic branch; new5A USB and PWM branch fuses. Single self-poweredUSB3 upstream; upstreamVBUS is sense only. CH334F PSELF is open/high. TwoXL330 chains share5V and twoXL430 chains share10.8V. ThreeMG90S outputs have separate5V power and default-disabled PWM. Motor buck22.34V, autonomous motor-side brake dump; external resistor and one-shot thermal cutoff required. FourthUSB3hub port reserved for isolated two-pack Daly telemetry; no unverified BMS connector pinout is implemented. Current, voltage, USB, thermal and braking qualification remain open.'

BASE_REMOVED={'J2','J3','J10','R60','R61','U11','U18','C67','C68'}
BASE_REMOVED|={s['ref'] for s in rev06.PARTS if s['block'].startswith('D.')}

def refmap(ref,offset):
 m=re.fullmatch(r'([A-Za-z]+)(\d+)',ref);assert m,ref
 return m[1]+str(int(m[2])+offset)

CELLS={
 'base':dict(module=rev06,offset=0,prefix='',position=(0,20),
  board='revisions/v0.6/kicad/robot_pdb.kicad_pcb',exclude=BASE_REMOVED,
  nets={'VMOT':'MOTOR_FUSED_INPUT','USB_DP':'HUB_CHILD_DP','USB_DM':'HUB_CHILD_DM','USB_RAMPED':'+5_USB_RAW'}),
 'motor':dict(module=motor_addon,offset=6000,prefix='M_',position=(228,20),
  board='revisions/motor-addon/kicad/motor_supply.kicad_pcb',exclude={'J1','J6'},
  nets={'VIN':'MOTOR_VIN','+24V':'MOTOR_BUCK_22V34','MOTOR_BUS':'MOTOR_BUS','CAN_H':'CAN_H','CAN_L':'CAN_L'}),
 'io':dict(module=robot_io,offset=7000,prefix='IO_',position=(0,160),
  board='revisions/robot-io/kicad/robot_io.kicad_pcb',exclude={'J1','J2','J3','J9','R43','JP1'},
  nets={'VIN':'PWM_VIN','USB_CAN_VBUS':'V5_USB','USB_PWM_VBUS':'V5_USB',
        'USB_CAN_DP':'P3_DP','USB_CAN_DM':'P3_DM','USB_PWM_DP':'P4_DP','USB_PWM_DM':'P4_DM',
        'CAN_H':'CAN_H','CAN_L':'CAN_L','V5_SERVO':'PWM_5V'}),
 'usb':dict(module=usb3_frontend,offset=9000,prefix='USB3_',position=(115,160),
  board='revisions/usb3-front-end/kicad/usb3_frontend.kicad_pcb',exclude={'J503','J504'},
  nets={'+5_USB_RAW':'+5_USB_RAW','HUB_CHILD_DP':'HUB_CHILD_DP','HUB_CHILD_DM':'HUB_CHILD_DM'}),
 'usb_power':dict(module=usb_power,offset=8000,prefix='UP_',position=(280,160),
  board='revisions/usb-power/kicad/usb_power.kicad_pcb',exclude={'J1','J2'},
  nets={'VIN':'USB_POWER_VIN','+5_USB_RAW':'+5_USB_RAW'}),
}

def netmap(cell,net):
 if not net or net=='GND':return net
 c=CELLS[cell]
 return c['nets'].get(net,c['prefix']+net)

CUSTOM_SYMBOL_PINS={}
NO_CONNECT_PINS={}
for cell,c in CELLS.items():
 CUSTOM_SYMBOL_PINS.update(getattr(c['module'],'CUSTOM_SYMBOL_PINS',{}))
 for r,pins in getattr(c['module'],'NO_CONNECT_PINS',{}).items():
  if r not in c['exclude']:NO_CONNECT_PINS[refmap(r,c['offset'])]=list(pins)
if 'U9500' in NO_CONNECT_PINS and '36' in NO_CONNECT_PINS['U9500']:NO_CONNECT_PINS['U9500'].remove('36')
CUSTOM_SYMBOL_PINS['pdb:AT24C02C']={'1':'A0','2':'A1','3':'A2','4':'GND','5':'SDA','6':'SCL','7':'WP','8':'VCC'}

def build_parts():
 result=[]
 for cell,c in CELLS.items():
  for original in c['module'].PARTS:
   if original['ref'] in c['exclude']:continue
   s=copy.deepcopy(original);s['source_cell']=cell;s['source_ref']=s['ref'];s['ref']=refmap(s['ref'],c['offset'])
   s['pins']={k:netmap(cell,v) for k,v in s['pins'].items()};s['block']=cell.upper()+'. '+s['block']
   if s['ref']=='U10':s['pins']['18']='NC_HUB_PSELF'
   if s['ref']=='U10':s['pins'].update({'13':'CHILD_EE_SCL','21':'CHILD_EE_SDA'})
   if s['ref']=='FB1':s['pins']['1']='CHILD_LIMITED_5V'
   if s['ref'] in ('J101','J501'):s['fp']='Robot_PDB:AMASS_XT30PW_F_2oz'
   if s['ref']=='U9500':s['pins']['36']='CHILD_PRT_CTL'
   if s['ref']=='F1':s.update(value='15A500VDC',mpn='Littelfuse0505015.MXEP',lcsc='',status='hand-fit axial; source-fuse and branch coordination qualification required',dnp=True)
   if s['ref']=='F2':s['dnp']=True
   result.append(s)
 # Separate current protection for the new logic-supplied converter branches.
 # These are DC interrupt ratings at63V, not an invented500V rating.
 for ref,out in (('F7000','PWM_VIN'),('F8000','USB_POWER_VIN')):
  result.append(dict(ref=ref,sym='Device:Fuse',value='5A63VDC20kA',fp='Robot_PDB:Fuse_Schurter_SHF_6.3x32_P40mm',
   pins={'1':'VIN','2':out},block='BRANCH. Additional converter input fuses',lcsc='',mpn='SCHURTER8020.5075.PT',
   status='hand-fit; verify physical dimensions and overload coordination',dnp=True,source_cell='branch',source_ref=ref))
 # The self-powered child hub distributes this ganged downstreamVBUS rail.
 # Current limiting protects its1A bead and the permanently attached functions.
 n=Netlist();block='CHILD. Ganged internal USB power protection'
 n.P('U9900','pdb:TPS2553','TPS2553DBVR',FP_SOT236,
  {'1':'+5_USB_RAW','2':'GND','3':'CHILD_SWITCH_EN','4':'CHILD_PRT_CTL','5':'CHILD_ILIM','6':'CHILD_LIMITED_5V'},
  block,'C55266','TI TPS2553DBVR','verify combined enable/overcurrent signaling with hub')
 # USB5744 supplies its own controlled weak pull-up. Its design checklist
 # explicitly prohibits an external pull-up on the combinedPRT_CTL line.
 n.R('R9901','30k','CHILD_ILIM','CHILD_ILIM_MID',block)
 n.R('R9902','7.5k','CHILD_ILIM_MID','GND',block)
 n.R('R9905','220k','CHILD_PRT_CTL','CHILD_SWITCH_EN',block)
 n.P('C9904','Device:C','100nF 50V C0G 5%','Capacitor_SMD:C_1206_3216Metric',{'1':'CHILD_SWITCH_EN','2':'GND'},
  block,'C97946','Murata GRM31C5C1H104JA01L','EN hold separates FAULT reporting from power disable; verify bench OCS recovery')
 n.C('C9900','100nF 50V','+5_USB_RAW','GND',block)
 n.C('C9901','10uF 25V','+5_USB_RAW','GND',block)
 n.P('C9902','Device:C_Polarized','150uF 10V POSCAP','Robot_PDB:Panasonic_POSCAP_D3L',{'1':'V5_USB','2':'GND'},block,
  'C347559','Panasonic10TPF150ML','120uF minimum at20% tolerance; verify actual stock')
 # Optional configuration memory is programmed OFFBOARD before fitting. The
 # hub multiplexes these pins as LED outputs; no live-programming header exists.
 n.P('U9901','pdb:AT24C02C','OPTIONAL AT24C02C-SSHM-T','Package_SO:SOIC-8_3.9x4.9mm_P1.27mm',
  {'1':'GND','2':'GND','3':'GND','4':'GND','5':'CHILD_EE_SDA','6':'CHILD_EE_SCL','7':'H_V33','8':'H_V33'},
  block,'C6203','MicrochipAT24C02C-SSHM-T','DNP; verified full baseline required; preprogram offboard before hand-fitting',dnp=True)
 # WCH drives SCL push-pull and supplies the SDA pull-up internally.
 # Permanent write protection suits the offboard-only programming workflow.
 n.C('C9903','100nF 50V','H_V33','GND',block)
 for s in n.parts:
  if s['ref']=='C9903':s.update(dnp=True,status='optional EEPROM support; hand-fit only with preprogrammed memory')
 for s in n.parts:s.update(source_cell='child',source_ref=s['ref']);result.append(s)
 result.append(dict(ref='J3',sym='Connector_Generic:Conn_02x02_Odd_Even',value='THOR 24V MICRO-FIT',fp='Robot_PDB:MicroFit_43045_0412_4P_2oz',pins={'1':'+24V','2':'+24V','3':'GND','4':'GND'},block='THOR OUTPUT. Standard four-contact power cable',lcsc='C277721',mpn='Molex 430450412',status='0.8mm board: straight locating pegs; 2.38mm tail protrusion, local insulating support and cable strain relief; verify cable group continuity before use',dnp=False,source_cell='thor_output',source_ref='J3'))
 # The original motor connector bypassed the logic ideal diode. Its new
 # onboard converter needs its own input reverse-polarity stage after F1.
 stage_refs={'U1':'U9910','Q1':'Q9910','C1':'C9910','C2':'C9911'}
 stage_nets={'VBAT_L':'MOTOR_FUSED_INPUT','VIN':'MOTOR_VIN','Q1_G':'MOTOR_INPUT_GATE','U1_VCAP':'MOTOR_INPUT_VCAP','GND':'GND'}
 for original in rev06.PARTS:
  if original['ref'] not in stage_refs:continue
  s=copy.deepcopy(original);s['ref']=stage_refs[original['ref']]
  s['pins']={k:stage_nets[v] for k,v in s['pins'].items()}
  s.update(block='MOTOR INPUT. Independent reverse-polarity protection',source_cell='motor_input',source_ref=original['ref'])
  result.append(s)
 for ref,connector in (('H9910','J1'),('H9911','J4'),('H9912','J3')):
  result.append(dict(ref=ref,sym='Mechanical:MountingHole',value='M3 NYLON SUPPORT',fp='MountingHole:MountingHole_3.2mm_M3',pins={},block='MOUNT. Battery harness support',lcsc='',mpn='M3 nylon/insulating standoff',status='Mandatory nearby harness support on 0.8mm board',dnp=True,source_cell='mount',source_ref=connector))
 return result

PARTS=build_parts()
assert len({s['ref'] for s in PARTS})==len(PARTS)
