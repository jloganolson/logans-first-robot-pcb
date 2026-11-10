"""v0.8 USB2 control-only changes; no USB3 dependencies or physical board writes.

Apply ``apply_base_parts`` to a cloned v06 inventory before integration net
mapping, then append PARTS. Existing base routes on the changed nets must be
reviewed/re-routed by the parent PCB builder. Camera/microphone are external.
"""
from copy import deepcopy
from pathlib import Path
import os
from blocks import Netlist, FP_R

TITLE = "Self-powered USB2 audio, Dynamixel, CAN and PWM controls"
REVISION = "0.8 development"
BASE_REMOVED = {"U18", "C68"}
BASE_NET_RENAMES = {"+5V_OAK": "USB_CONTROL_5V"}
CUSTOM_SYMBOL_PINS = {
    "pdb:TPS2552": {"1":"IN", "2":"GND", "3":"EN_N", "4":"FAULT_N", "5":"ILIM", "6":"OUT"},
    "pdb:TPS2553": {"1":"IN", "2":"GND", "3":"EN", "4":"FAULT_N", "5":"ILIM", "6":"OUT"},
    "pdb:TS3USB30E_DGS": {"1":"S", "2":"D1+", "3":"D2+", "4":"D+", "5":"GND", "6":"D-", "7":"D2-", "8":"D1-", "9":"OE_N", "10":"VCC"},
    "pdb:TS3USB221A": {"1":"1D+", "2":"1D-", "3":"2D+", "4":"2D-", "5":"GND", "6":"OE_N", "7":"D-", "8":"D+", "9":"S", "10":"VCC"},
    "pdb:TLV3011B": {"1":"OUT", "2":"GND", "3":"IN+", "4":"IN-", "5":"REF", "6":"V+"},
    "pdb:AT24C02C": {"1":"A0", "2":"A1", "3":"A2", "4":"GND", "5":"SDA", "6":"SCL", "7":"WP", "8":"VCC"},
}
# Supersedes the bus-powered U10 NC list: EEPROM omitted; pin24 drives ganged power.
NO_CONNECT_PINS = {"U10":["2","13","16","17","18","21","23"], "U9904":["4"]}

def write_footprints(directory):
    """Create exact TI DGS0010A example lands in the caller's local library."""
    out = Path(directory); out.mkdir(parents=True,exist_ok=True)
    source = Path(os.environ['KICAD7_FOOTPRINT_DIR'])/'Package_SO.pretty/MSOP-10_3x3mm_P0.5mm.kicad_mod'
    text = source.read_text()
    assert text.count('(size 1.4 0.3)')==10
    text = text.replace('"MSOP-10_3x3mm_P0.5mm"','"TI_DGS0010A_VSSOP_3x3_P0.5mm"')
    text = text.replace('(size 1.4 0.3)','(size 1.45 0.3)')
    text = text.replace('(descr "10-Lead Plastic Micro Small Outline Package (MS) [MSOP] (see Microchip Packaging Specification 00000049BS.pdf)")',
                        '(descr "TI DGS0010A VSSOP10; TS3USB30E RevG drawing4221984/A: 1.45x0.30 lands, 4.4mm column spacing, 0.50mm pitch")')
    target = out/'TI_DGS0010A_VSSOP_3x3_P0.5mm.kicad_mod'
    target.write_text(text)
    (out/'USB2_Inline_Pair_Landing.kicad_mod').write_text('''(footprint "USB2_Inline_Pair_Landing" (version 20221018) (generator robot_pdb)
 (layer "F.Cu") (attr smd exclude_from_pos_files exclude_from_bom)
 (descr "Internal PCB integration pair landing, not a fitted connector; pin1 D+, pin2 D-")
 (fp_text reference "REF**" (at 0 -1.3) (layer "F.Fab") (effects (font (size .6 .6) (thickness .1))))
 (fp_text value "USB2 LINK" (at 0 1.3) (layer "F.Fab") (effects (font (size .6 .6) (thickness .1))))
 (pad "1" smd rect (at 0 -.25) (size .6 .3) (layers "F.Cu" "F.Mask"))
 (pad "2" smd rect (at 0 .25) (size .6 .3) (layers "F.Cu" "F.Mask")))\n''')
    return target

def apply_base_parts(original):
    """Return a patched copy; never mutate v06 or a caller-owned inventory."""
    result = [deepcopy(p) for p in original if p['ref'] not in BASE_REMOVED]
    by = {p['ref']:p for p in result}
    for p in result:
        p['pins'] = {pin:BASE_NET_RENAMES.get(net,net) for pin,net in p['pins'].items()}
    by['FB1']['pins'] = {'1':'USB2_LIMITED_5V','2':'V5_USB_HUB'}
    by['FB1'].update(value='120R 2A',lcsc='C14709',mpn='Murata BLM18PG121SN1D',
        status='Same0603 package;2A@85C,1A@125C;.05ohm max;lower filter impedance requires noise/EMI bench review')
    for ref in ('C60','C61','C62'):
        by[ref]['pins'] = {k:('V5_USB_HUB' if v=='V5_USB' else v) for k,v in by[ref]['pins'].items()}
    by['U10']['pins'].update({'14':'HUB_UP_DM','15':'HUB_UP_DP','18':'HUB_PSELF_NC',
                            '19':'V5_USB_HUB','24':'H_PWREN_N'})
    for pin in ('13','21'):by['U10']['pins'].pop(pin,None)
    by['U10']['status'] = 'Self-powered PSELF open/high; direct ganged EN/OCS; inspect descriptors before operation'
    by['TP201'].update(value='USB CONTROL 5V')
    by['D202']['status'] = 'Local USB controls supply indicator; camera/microphone powered externally'
    by['C67'].update(value='100nF 50V',lcsc='C14663',mpn='Yageo CC0603KRX7R9BB104',status='Host VBUS sense bypass only; 100nF avoids excessive host-detach delay')
    assert by['J10']['pins']['A4']=='VBUS_IN'
    assert by['U10']['pins']['19']!='V5_USB'
    assert not any(p['ref']=='U18' for p in result)
    return result

n=Netlist(); B='USB2 CONTROL. Local supply and host-controlled data attachment'
n.P('U9900','pdb:TPS2552','TPS2552DBVR','Package_TO_SOT_SMD:SOT-23-6',
    {'1':'V5_USB_HUB','2':'GND','3':'H_PWREN_N','4':'H_OVCUR','5':'USB2_ILIM','6':'V5_USB'},
    B,'C46506','Texas Instruments TPS2552DBVR','Active-low auto-retry, not -1 latch-off; ganged embedded-device current limit')
n.R('R9900','100k','H_PWREN_N','H_V33',B)
n.R('R9901','30k','USB2_ILIM','USB2_ILIM_MID',B)
n.R('R9902','7.5k','USB2_ILIM_MID','GND',B)
n.C('C9900','100nF 50V','V5_USB_HUB','GND',B)
n.C('C9901','10uF 25V','V5_USB_HUB','GND',B)
n.P('C9902','Device:C_Polarized','150uF 10V POSCAP','Robot_PDB:Panasonic_POSCAP_D3L',
    {'1':'V5_USB','2':'GND'},B,'C347559','Panasonic 10TPF150ML',
    '120uF minimum at -20% nameplate tolerance; local downstream VBUS bulk')
n.P('U9902','pdb:TS3USB221A','TS3USB221ARSER','Package_DFN_QFN:Texas_UQFN-10_1.5x2mm_P0.5mm',
    {'1':'HUB_UP_DP','2':'HUB_UP_DM','3':'USB2_UNUSED_DP','4':'USB2_UNUSED_DM','5':'GND',
     '6':'USB2_UP_OE_N','7':'USB_DM','8':'USB_DP','9':'GND','10':'H_V33'},
    B,'C128396','Texas Instruments TS3USB221ARSER',
    'RSE10 exact pinout; 0.5mm pitch/noEP; power-off leakage specified; selected D1 path')
n.C('C9905','100nF 50V','H_V33','GND',B)
for ref,net in [('R9906','USB2_UNUSED_DP'),('R9907','USB2_UNUSED_DM')]:
    n.P(ref,'Device:R','49.9',FP_R,{'1':net,'2':'GND'},B,'C23185',
        'UNI-ROYAL 0603WAF499JT5E','TI recommendation: terminate unused alternate signal paths near switch')
n.P('U9903','pdb:TLV3011B','TLV3011BIDBVR MANUAL FIT','Package_TO_SOT_SMD:SOT-23-6',
    {'1':'USB2_UP_OE_N','2':'GND','3':'USB2_VREF','4':'USB2_VBUS_SENSE','5':'USB2_VREF','6':'H_V33'},
    B,'C20345920','Texas Instruments TLV3011BIDBVR',
    'MANDATORY MANUAL FIT; JLC stock0; B version VDD0 fail-safe input/POR high-Z; rawVBUS valid comparator',dnp=True)
n.P('R9903','Device:R','10k',FP_R,{'1':'VBUS_IN','2':'GND'},B,'C25804','UNI-ROYAL 0603WAF1002T5E','RawVBUS bleeder for bounded detach timing')
n.P('R9909','Device:R','220k',FP_R,{'1':'VBUS_IN','2':'USB2_VBUS_SENSE'},B,'C22961','UNI-ROYAL 0603WAF2203T5E','1%100ppm divider upper')
n.P('R9910','Device:R','100k',FP_R,{'1':'USB2_VBUS_SENSE','2':'GND'},B,'C25803','UNI-ROYAL 0603WAF1003T5E','1%100ppm divider lower')
n.P('C9909','Device:C','1nF 50V', 'Capacitor_SMD:C_0603_1608Metric',{'1':'USB2_VREF','2':'GND'},B,'C1588','Samsung CL10B102KB8NNNC','1nF reference bypass below10nF stable-load limit')
n.R('R9904','100k','USB2_UP_OE_N','H_V33',B)
n.C('C9906','100nF 50V','H_V33','GND',B)
n.P('U9904','pdb:TPS2553','TPS2553DBVR','Package_TO_SOT_SMD:SOT-23-6',
    {'1':'USB_CONTROL_5V','2':'GND','3':'USB_CONTROL_5V','4':'USB2_MAIN_FAULT_NC','5':'USB2_MAIN_ILIM','6':'USB2_LIMITED_5V'},
    B,'C55266','Texas Instruments TPS2553DBVR',
    'Always enabled upstream limiter protects 2A FB1 and hub supply; not active-low TPS2552')
n.R('R9908','20k','USB2_MAIN_ILIM','GND',B)
n.C('C9907','1uF 25V','USB2_LIMITED_5V','GND',B)
n.C('C9908','100nF 50V','USB_CONTROL_5V','GND',B)

# Board-only integration landings remain useful probe points. No external cable
# or fitted connector is implied. Parent can join these exact endpoints and
# retain the short local routes without leaving an open-ended signal stub.
PORT_REFS={
 'J9900':{'1':'USB_DP','2':'USB_DM'},
 'J9901':{'1':'HUB_UP_DP','2':'HUB_UP_DM'},
}
for ref,pins in PORT_REFS.items():
    n.P(ref,'Connector_Generic:Conn_01x02','USB2 INLINE LINK','Robot_PDB:USB2_Inline_Pair_Landing',
        pins,B,'','Bare PCB landing, no fitted connector','Internal integration endpoint; preserve pair polarity',dnp=True)
for i,net in enumerate(['USB_CONTROL_5V','USB2_LIMITED_5V','V5_USB_HUB','V5_USB','H_V33',
                         'H_PWREN_N','H_OVCUR','HUB_EE_SCL','HUB_EE_SDA','VBUS_IN','GND']):
    if net in ('HUB_EE_SCL','HUB_EE_SDA'):continue
    ref='TP'+str(9900+i);n.TP(ref,net,net,B);PORT_REFS[ref]={'1':net}
PARTS=n.parts
assert len({p['ref'] for p in PARTS})==len(PARTS)

DATASHEETS={
 'CH334F':'https://cdn-learn.adafruit.com/assets/assets/000/131/435/original/CH334DS1.PDF?1721660148=',
 'TPS2552':'https://www.ti.com/lit/ds/symlink/tps2552.pdf',
 'TS3USB30E':'https://www.ti.com/lit/ds/symlink/ts3usb30e.pdf',
 'TS3USB221A':'https://www.ti.com/lit/ds/symlink/ts3usb221a.pdf',
 'TLV3011B':'https://www.ti.com/lit/ds/symlink/tlv3011.pdf',
}
