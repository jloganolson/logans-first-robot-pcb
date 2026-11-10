"""Authoritative USB2-only v0.8 integration inventory. DEVELOPMENT, not released.

Source cells remain separately inspectable. Shared VIN/GND and USB logic are
shared failure domains: regulator OFF shunts are not fault isolation switches.
"""
from copy import deepcopy
from types import SimpleNamespace
import re
import rev06, motor_resistor, robot_io, usb2_control, service_off_v08

REVISION='0.8 development'
TITLE='Robot PDB: USB2 controls, CAN wheels with resistor clamp and three PWM servos'
BOARD_SIZE_MM=(340,230)
SCHEMATIC_NOTES=('DEVELOPMENT ONLY; no fabrication release. External mechanical DPST disconnect: STOP BEFORE OFF. '
 '27–33V intended battery operation,33.6V full charge. Source-end fuses required. '
 'USB2 host VBUS is sense only; local control5V powers hub and current-limited embedded devices. '
 'OAK-D and USB microphone connect externally to Jetson USB3. No onboard Daly telemetry interface. '
 'Motor buck22.34V nominal plus autonomous23.xV clamp: external3.3ohm100W chassis resistor and NC thermal cutoff required. '
 'Wheel low-voltage operation and braking waveforms require bench qualification before motion. '
 'Local service shunts shortENtoGND=OFF; no isolation/discharge. Both controller MCUs require firmware. '
 'TwoXL330 chains share5V/data; twoXL430 chains share10.8V/data; threeMG90S share independent5V power.')

def refmap(ref,offset):
 m=re.fullmatch(r'([A-Za-z]+)(\d+)',ref);assert m,ref
 return m[1]+str(int(m[2])+offset)

BASE_REMOVED={'J2','J3','J201'}|usb2_control.BASE_REMOVED
BASE=SimpleNamespace(PARTS=usb2_control.apply_base_parts(rev06.PARTS),
 CUSTOM_SYMBOL_PINS=getattr(rev06,'CUSTOM_SYMBOL_PINS',{}),
 NO_CONNECT_PINS={**getattr(rev06,'NO_CONNECT_PINS',{}),**usb2_control.NO_CONNECT_PINS})
CELLS={
 'base':dict(module=BASE,offset=0,prefix='',position=(0,20),board='revisions/v0.6/kicad/robot_pdb.kicad_pcb',exclude=BASE_REMOVED,
  nets={'VMOT':'MOTOR_FUSED_INPUT',**usb2_control.BASE_NET_RENAMES}),
 'motor':dict(module=motor_resistor,offset=6000,prefix='M_',position=(228,20),board='revisions/motor-resistor/kicad/motor_resistor.kicad_pcb',exclude={'J1','J6'},
  nets={'VIN':'MOTOR_VIN','MOTOR_BUS':'MOTOR_BUS','CAN_H':'CAN_H','CAN_L':'CAN_L'}),
 'io':dict(module=robot_io,offset=7000,prefix='IO_',position=(0,130),board='revisions/robot-io/kicad/robot_io.kicad_pcb',exclude={'J1','J2','J3','J9','R43','JP1'},
  nets={'VIN':'PWM_VIN','USB_CAN_VBUS':'V5_USB','USB_PWM_VBUS':'V5_USB','USB_CAN_DP':'P3_DP','USB_CAN_DM':'P3_DM',
        'USB_PWM_DP':'P4_DP','USB_PWM_DM':'P4_DM','CAN_H':'CAN_H','CAN_L':'CAN_L','V5_SERVO':'PWM_5V'}),
 'usb2':dict(module=usb2_control,offset=0,prefix='',position=(183,121),board='revisions/usb2-control/kicad/usb2_control.kicad_pcb',
  exclude=set(getattr(usb2_control,'PORT_REFS',())),nets={}),
}
def netmap(cell,net):
 if not net or net=='GND':return net
 c=CELLS[cell];return c['nets'].get(net,c['prefix']+net)

CUSTOM_SYMBOL_PINS={};NO_CONNECT_PINS={}
for cell,c in CELLS.items():
 CUSTOM_SYMBOL_PINS.update(getattr(c['module'],'CUSTOM_SYMBOL_PINS',{}))
 for r,pins in getattr(c['module'],'NO_CONNECT_PINS',{}).items():
  if r not in c['exclude']:NO_CONNECT_PINS[refmap(r,c['offset'])]=list(pins)

def build_parts():
 parts=[]
 for cell,c in CELLS.items():
  for original in c['module'].PARTS:
   if original['ref'] in c['exclude']:continue
   s=deepcopy(original);s.update(source_cell=cell,source_ref=s['ref'],ref=refmap(s['ref'],c['offset']))
   s['pins']={k:netmap(cell,v) for k,v in s['pins'].items()};s['block']=cell.upper()+'. '+s['block']
   if s['ref'] in ('J101','J501'):s['fp']='Robot_PDB:AMASS_XT30PW_F_2oz'
   if s['ref']=='J10':s['fp']='Robot_PDB:USB_C_HRO_31M12_2oz'
   if s['ref']=='F1':s.update(value='15A500VDC',mpn='Littelfuse0505015.MXEP',lcsc='',dnp=True,status='mandatory hand-fit source branch fuse; overload coordination unqualified')
   if s['ref']=='F2':s['dnp']=True
   if s['ref']=='R6013':s.update(lcsc='C245992',mpn='Yageo RC0603FR-07649RL',status='649ohm1%0603 drop-in; scarce stock; assembly reservation/attrition confirmation required')
   if s['ref']=='U7007':s.update(value='SN74AHCT125QPWRQ1',lcsc='C507215',mpn='Texas Instruments SN74AHCT125QPWRQ1',status='TI PW14 drop-in; documented VCC=0 input leakage; verify delivered marking and disabled-rail behavior')
   parts.append(s)
 parts.append(dict(ref='F7000',sym='Device:Fuse',value='5A63VDC20kA',fp='Robot_PDB:Fuse_Schurter_SHF_6.3x32_P40mm',
  pins={'1':'VIN','2':'PWM_VIN'},block='BRANCH. PWM converter input fuse',lcsc='',mpn='SCHURTER8020.5075.PT',
  status='mandatory hand-fit; verify overload coordination',dnp=True,source_cell='branch',source_ref='F7000'))
 parts.append(dict(ref='J3',sym='Connector_Generic:Conn_02x02_Odd_Even',value='THOR 24V MICRO-FIT',fp='Robot_PDB:MicroFit_43045_0412_4P_2oz',
  pins={'1':'+24V','2':'+24V','3':'GND','4':'GND'},block='THOR OUTPUT. Standard four-contact power cable',lcsc='C277721',mpn='Molex430450412',
  status='1.6mm PCB; verify mating/strain relief and delivered cable continuity before power',dnp=False,source_cell='thor_output',source_ref='J3'))
 stage_refs={'U1':'U9910','Q1':'Q9910','C1':'C9910','C2':'C9911'}
 stage_nets={'VBAT_L':'MOTOR_FUSED_INPUT','VIN':'MOTOR_VIN','Q1_G':'MOTOR_INPUT_GATE','U1_VCAP':'MOTOR_INPUT_VCAP','GND':'GND'}
 for original in rev06.PARTS:
  if original['ref'] not in stage_refs:continue
  s=deepcopy(original);s['ref']=stage_refs[original['ref']];s['pins']={k:stage_nets[v] for k,v in s['pins'].items()}
  s.update(block='MOTOR INPUT. Reverse-polarity protection',source_cell='motor_input',source_ref=original['ref']);parts.append(s)
 parts.extend(deepcopy(service_off_v08.PARTS))
 for ref,connector in (('H9910','J1'),('H9911','J4'),('H9912','J3')):
  parts.append(dict(ref=ref,sym='Mechanical:MountingHole',value='M3 NYLON SUPPORT',fp='MountingHole:MountingHole_3.2mm_M3',pins={},
   block='MOUNT. Harness support',lcsc='',mpn='M3 nylon/insulating standoff',status='harness strain relief',dnp=True,source_cell='mount',source_ref=connector))
 return parts
PARTS=build_parts()
assert len({s['ref'] for s in PARTS})==len(PARTS)
assert not any(s.get('source_cell') in ('usb','usb_power') for s in PARTS)
