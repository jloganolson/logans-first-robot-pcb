"""v0.6 engineering prototype: external mechanical DPST; no supervisor."""
from copy import deepcopy
from rev05_parts_review import PARTS as BASE_PARTS
from blocks import Netlist, FP_XT60M
PARTS=deepcopy(BASE_PARTS)
parts={p['ref']:p for p in PARTS}
# Stocked alternate with explicit 60V winding rating; exact Coilcraft land pattern.
parts['L1'].update(value='10uH 22A 60V',fp='Inductor_SMD:L_Coilcraft_XAL1510-103',lcsc='C3911782',mpn='Coilcraft XAL1510-103MED',status='prototype; 60V rated; verify startup, loop stability, thermal behavior and 10mm height')
REVISION='0.6 engineering prototype'
SCHEMATIC_NOTES=r'''v0.6 ENGINEERING PROTOTYPE\nJ1/J4: soldered 12AWG battery pigtails with external XT60 mating ends. Source-end fuses required.\nJ5.1->external DPST pole A->J5.2; J5.3->pole B->J5.4. STOP BEFORE OFF. No software sequencer.\nJ5.2/J5.4 share VBAT; the two pack positives remain separate with the external switch OFF.\nBring-up: current-limited supply first. Initial traction limit 4A battery current per ESC channel.\nNo live pack paralleling until equal-voltage/reconnect, fault and thermal qualification.\nJ301/J302: 5V XL330 chains 2+2, torque/current restricted; J401/J402: 10.8V XL430 chains 2+1.\nServo and wheel regeneration require instrumented qualification. Branch fuses do not protect every output harness.''' 
for ref in ('F1','F2'):
 parts[ref].update(value=('MOTOR' if ref=='F1' else 'ELECTRONICS')+' 30A 500VDC',fp='Robot_PDB:Fuse_505_Axial_P40mm',lcsc='C187656',mpn='Littelfuse 0505030.MXEP 30A 500VDC 20kA interrupt, axial lead',status='hand-solder after SMT; verify pulse/fault/thermal coordination')
old=parts['SW1'];old.update(ref='J5',sym='Connector_Generic:Conn_01x04',value='EXTERNAL DPST POWER WIRES',fp='Robot_PDB:Disconnect_WirePort_4Circuit',lcsc='',mpn='Four hand-soldered 12AWG wires to external mechanical DPST, no fitted PCB switch',status='wire interface; strain relief required',dnp=True)
for ref in ('J1','J4','J2'):
 parts[ref].update(fp='Robot_PDB:Power_WirePort_P7.2mm',lcsc='',mpn='Hand-soldered 12AWG power pigtail; external XT60 mating end; strain relief required',status='hand-wire after SMT',dnp=True)
for ref in ('J301','J302','J401'):
 parts[ref].update(fp='Connector_JST:JST_VH_B3P-VH_1x03_P3.96mm_Vertical',lcsc='C160316',mpn='JST B3P-VH(LF)(SN), use VHR-3N mating harness',status='confirm assembly preview and mating harness')
new=deepcopy(parts['J401']);new.update(ref='J402',value='XL430 10.8V CHAIN B');PARTS.append(new)
# USB controlled attachment ramp, before ferrite FB1 and all existing bulk.
parts['FB1']['pins']['1']='USB_RAMPED'
n=Netlist();B='I. USB attachment slew control'
n.P('U18','pdb:TPS22918','TPS22918DBVR','Package_TO_SOT_SMD:SOT-23-6',{'1':'VBUS_IN','2':'GND','3':'VBUS_IN','4':'USB_SLEW_CT','5':'USB_QOD_NC','6':'USB_RAMPED'},B,'C131941','TI TPS22918DBVR 2A load switch; not a current limiter','confirm')
n.C('C67','1uF 25V','VBUS_IN','GND',B)
n.C('C68','2.2nF','USB_SLEW_CT','GND',B)
PARTS.extend(n.parts)
