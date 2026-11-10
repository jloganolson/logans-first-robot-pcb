"""Dedicated USB 5.1 V / 8 A target LM5146 cell; engineering candidate.

Reuses the reviewed converter topology, not the previous 5 A camera rail.
All current/thermal/loop ratings remain qualification targets until measured.
"""
from blocks import Netlist, FP_R, FP_TDSON

REVISION='USB power development'
TITLE='Dedicated USB5V supply, 8A continuous design target'
SCHEMATIC_NOTES='5.10V nominal; eight ampere design target is unqualified. Separate source-fused protected8S supply. Shunt valley current limit is not an8A output ceiling. Qualify loop response, startup, thermal and port-voltage limits before attaching camera.'
RELEASE_HOLDS=[
 'Native routing, pin/net comparison and manufacturer placement checks required before fabrication.',
 'Verify5V tolerance including resistor temperature, FB accuracy, load/wiring drop and startup overshoot. USB port voltage must remain within applicable USB limits.',
 'Averaged loop model is a screen only; measure actual loop margin and simultaneous camera/mic/internal USB load steps.',
 '8A continuous is a design target, not a demonstrated board rating. Verify capacitor bias/ESR, MOSFET and inductor temperatures and local input fuse coordination.',
]

def build_parts():
 n=Netlist();n.thor_block(out_conn=False)
 by={s['ref']:s for s in n.parts}
 by['JP1']['value']='USB 5V OFF'
 for s in n.parts:s['block']='USB power. Dedicated5.1V buck'
 by['L1'].update(value='10uH XAL1510-103MED',fp='Inductor_SMD:L_Coilcraft_XAL1510-103',lcsc='C3911782',mpn='Coilcraft XAL1510-103MED')
 for r in ('Q2','Q3'):by[r].update(value='BSC040N10NS5',lcsc='C534334',mpn='Infineon BSC040N10NS5ATMA1')
 by['R14'].update(value='100k0.1%',lcsc='C122538',mpn='Yageo RT0603BRD07100KL')
 by['R14']['pins']['2']='USB_FB_TOP'
 n.P('R20','Device:R','8.2k1%',FP_R,{'1':'USB_FB_TOP','2':'T_FB'},'USB power.5.128V feedback trim','C25981','UNI-ROYAL0603WAF8201T5E','1%100ppm; verify final supplier stock')
 by['R15'].update(value='10k0.1%',lcsc='C95204',mpn='Yageo RT0603BRD0710KL')
 by['R15']['pins']['2']='USB_FB_BOTTOM'
 n.P('R22','Device:R','10k0.1%',FP_R,{'1':'USB_FB_BOTTOM','2':'GND'},'USB power. Precision feedback bottom','C95204','Yageo RT0603BRD0710KL','0.1%25ppm required')
 by['R13'].update(value='470',lcsc='C23179',mpn='UNI-ROYAL0603WAF4700T5E')
 by['R13']['pins']['2']='USB_SENSE'
 for pin in ('1','2','3'):by['Q3']['pins'][pin]='USB_SENSE'
 n.P('R21','Device:R','5m1%3W','Resistor_SMD:R_2512_6332Metric',{'1':'USB_SENSE','2':'GND'},'USB power. Kelvin valley sense','C2994643','Milliohm HoLLR2512-3W-5mR-1%','verify JLC stock and Kelvin layout')
 for r,value,code,mpn in (
  ('R16','10k','C25804','UNI-ROYAL0603WAF1002T5E'),
  ('R17','3.3k','C22978','UNI-ROYAL0603WAF3301T5E'),
  ('C24','47nF50V','C1622','0603X7R47nF50V'),
  ('C25','100pF50V','C14858','SamsungCL10C101JB8NNNC C0G5%'),
  ('C23','220nF25V','C21120','0603X7R220nF25V')):
  by[r].update(value=value,lcsc=code,mpn=mpn,status='analytical compensation screen and bench qualification required')
 n.P('C28','Device:C_Polarized','1000uF35V FR','Capacitor_THT:CP_Radial_D12.5mm_P5.00mm',{'1':'+24V','2':'GND'},'USB power. Permanent bulk','C128518','PanasonicEEUFR1V102','mandatory hand-fit after SMT',dnp=True)
 n.P('J1','Connector_Generic:Conn_01x02','FUSED PROTECTED8S IN','Robot_PDB:Power_WirePort_P7.2mm',{'1':'GND','2':'VIN'},'USB power. Input',dnp=True)
 n.P('J2','Connector_Generic:Conn_01x02','USB5V1 OUTPUT','Robot_PDB:Power_WirePort_P7.2mm',{'1':'GND','2':'+24V'},'USB power. Output',dnp=True)
 n.P('D1','Device:D_TVS','SMCJ36CA','Diode_SMD:D_SMC',{'1':'VIN','2':'GND'},'USB power. Local input protection','C151283','LittelfuseSMCJ36CA','verify source transient envelope')
 # No legacy24V identity escapes this module; T_* is local switching-cell naming.
 for s in n.parts:
  s['pins']={k:('+5_USB_RAW' if v=='+24V' else v) for k,v in s['pins'].items()}
  if s['ref']=='TP4':s['value']='USB5V1'
 return n.parts

PARTS=build_parts()
