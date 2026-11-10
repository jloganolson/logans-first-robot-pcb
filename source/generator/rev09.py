"""Active original-motor passthrough revision; replacement wheels archived."""
from copy import deepcopy
from types import SimpleNamespace
import re
import rev06,robot_pwm,usb2_control,service_off_v09

REVISION='0.9 engineering prototype'
TITLE='Robot PDB: original motor passthrough, USB2 audio/UART and three PWM servos'
BOARD_SIZE_MM=(228,230)
SCHEMATIC_NOTES=('ENGINEERING PROTOTYPE; final layout/assembly review and bench qualification required. '
 'External mechanical DPST disconnect: STOP ROBOT BEFORE OFF. '
 '27–33V intended battery operation,33.6V full; individual pack-source fuses required. '
 'J2 is original fused BATTERY-VOLTAGE motor passthrough to existing Flipsky controllers. '
 'No motor converter, brake clamp, external brake resistor, thermal contact or onboard CAN. '
 'Existing motor controllers retain their previous control connection and braking configuration. '
 'USB2 VBUS is sense only; local5V powers audio/UART/PWM through the CH334 hub. '
 'Hub port3 unused; no configuration EEPROM. OAK-D/microphone connect externally to Jetson USB3. '
 'Seven local shunts shortENtoGND=OFF; they do not isolate/discharge outputs. '
 'One PWM MCU requires firmware; signal disarm leaves servo5V powered. '
 'TwoXL330 chains share5V/data; twoXL430 chains share10.8V/data; threeMG90S share separate5V.')

def refmap(ref,offset):
 m=re.fullmatch(r'([A-Za-z]+)(\d+)',ref);assert m,ref
 return m[1]+str(int(m[2])+offset)

base_parts=usb2_control.apply_base_parts(rev06.PARTS)
for s in base_parts:
 if s['ref']=='U10':s['pins'].update({'7':'NC_HUB_P3_DM','8':'NC_HUB_P3_DP'})
base_nc={**getattr(rev06,'NO_CONNECT_PINS',{}),**usb2_control.NO_CONNECT_PINS}
base_nc['U10']=sorted(set(base_nc['U10'])|{'7','8'},key=int)
BASE=SimpleNamespace(PARTS=base_parts,CUSTOM_SYMBOL_PINS=getattr(rev06,'CUSTOM_SYMBOL_PINS',{}),NO_CONNECT_PINS=base_nc)
CELLS={
 'base':dict(module=BASE,offset=0,prefix='',position=(0,20),board='revisions/v0.6/kicad/robot_pdb.kicad_pcb',
  exclude={'J3','J201'}|usb2_control.BASE_REMOVED,nets=usb2_control.BASE_NET_RENAMES),
 'io':dict(module=robot_pwm,offset=7000,prefix='IO_',position=(0,130),board='revisions/robot-io/kicad/robot_io.kicad_pcb',
  exclude=robot_pwm.SOURCE_EXCLUDED_REFS|{'J2','J9'},
  nets={'VIN':'PWM_VIN','USB_PWM_VBUS':'V5_USB','USB_PWM_DP':'P4_DP','USB_PWM_DM':'P4_DM','V5_SERVO':'PWM_5V'}),
 'usb2':dict(module=usb2_control,offset=0,prefix='',position=(183,121),board='revisions/usb2-control/kicad/usb2_control.kicad_pcb',
  exclude=set(usb2_control.PORT_REFS),nets={}),
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
   if s['ref'] in ('F1','F2'):s['dnp']=True
   if s['ref']=='J2':s['value']='FUSED BATTERY MOTOR PASSTHROUGH'
   if s['ref']=='U7007':s.update(value='SN74AHCT125QPWRQ1',lcsc='C507215',mpn='Texas Instruments SN74AHCT125QPWRQ1',
    status='TI PW14 drop-in; documented VCC=0 input leakage; verify marking and disabled-rail behavior')
   parts.append(s)
 parts.append(dict(ref='F7000',sym='Device:Fuse',value='5A63VDC20kA',fp='Robot_PDB:Fuse_Schurter_SHF_6.3x32_P40mm',
  pins={'1':'VIN','2':'PWM_VIN'},block='BRANCH. PWM converter input fuse',lcsc='',mpn='SCHURTER8020.5075.PT',
  status='mandatory hand-fit; verify overload coordination',dnp=True,source_cell='branch',source_ref='F7000'))
 parts.append(dict(ref='J3',sym='Connector_Generic:Conn_02x02_Odd_Even',value='THOR 24V MICRO-FIT',fp='Robot_PDB:MicroFit_43045_0412_4P_2oz',
  pins={'1':'+24V','2':'+24V','3':'GND','4':'GND'},block='THOR OUTPUT. Standard four-contact power cable',lcsc='C277721',mpn='Molex430450412',
  status='nominal1.6mm PCB; meter delivered cable continuity/polarity before power',dnp=False,source_cell='thor_output',source_ref='J3'))
 parts.extend(deepcopy(service_off_v09.PARTS))
 for ref,connector in (('H9910','J1'),('H9911','J4'),('H9912','J3')):
  parts.append(dict(ref=ref,sym='Mechanical:MountingHole',value='M3 NYLON SUPPORT',fp='MountingHole:MountingHole_3.2mm_M3',pins={},
   block='MOUNT. Harness support',lcsc='',mpn='M3 nylon/insulating standoff',status='harness strain relief',dnp=True,source_cell='mount',source_ref=connector))
 return parts
PARTS=build_parts()
assert len({s['ref'] for s in PARTS})==len(PARTS)
assert next(s for s in PARTS if s['ref']=='J2')['pins']=={'1':'GND','2':'VMOT'}
assert not any(r.startswith('M_') or 'CAN' in r for s in PARTS for r in s['pins'].values())
