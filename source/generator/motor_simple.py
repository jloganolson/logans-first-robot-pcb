"""24 V buck + passive CAN development variant. Not qualified for wheel power.

Reuses the screened converter inventory without changing the frozen motor_addon.
The main-board composition must provide source fuse and input reverse protection.
No brake energy sink, thermal permissive or output ideal diode is implemented.
"""
from copy import deepcopy
import motor_addon as previous

TITLE = "DDSM350-CT simple 24 V supply — development only"
REVISION = "0.8 simple motor development"
BOARD_SIZE_MM = previous.BOARD_SIZE_MM
MOUNTING_HOLES_MM = previous.MOUNTING_HOLES_MM
CUSTOM_SYMBOL_PINS = {}
NO_CONNECT_PINS = {}
DATASHEETS = {k: previous.DATASHEETS[k] for k in ('U2', 'L1')}
DATASHEETS.update(wheel='https://docs.waveshare.com/DDSM350-CT',
                 control='https://docs.waveshare.com/DDSM350-CT/Product-Use',
                 divider_R20='https://jlcpcb.com/partdetail/0603WAF750JT5E/C4275')
SCHEMATIC_NOTES = "DEVELOPMENT ONLY: 23.988 V nominal; converter/CAN without braking absorption. Input requires main-board fuse and reverse protection. HOLD powering moving wheels pending measured coast/regen behavior and verified wheel voltage limits. 10 A continuous / 12 A transient are unqualified targets. Bulk capacitance is not a braking energy sink. CAN release must be explicitly configured and verified."
RELEASE_HOLDS = [
    'No energy sink: do not power moving wheels until coast, all deceleration/turn/reversal transitions and fault behavior are qualified with an external energy-absorbing test setup.',
    'Waveshare publishes rated24V only; maximum steady/transient voltage and regenerative behavior remain unverified. Divider tolerance is not a wheel approval.',
    'Input is NOT reverse-protected in this cell: mandatory main source fuse and LM74700/100V MOSFET stage must accompany it, including a standalone implementation.',
    'Ten ampere continuous and twelve ampere transient are design targets. Current-limit corners, Kelvin routing, thermal rise, inrush/SOA and measured loop margins remain unqualified.',
    'No independent motor overvoltage disconnect, dynamic brake or safe-stop hardware is implemented. Shaft release coasts and cannot hold a slope.',
    'Verify actual assembly inventory, hand-fit capacitor polarity, motor harness pinout, strain relief and selective fuse coordination before fabrication release.',
]
EXTERNAL_PARTS = [
    dict(item='source protection', quantity=1, notes='Main-board source fuse and reverse-polarity stage mandatory; no input fuse or reverse MOSFET is present in this cell.'),
    dict(item='CAN controller', quantity=1, notes='Internal Robot I/O USB-CAN bridge; passive CAN pass-through here has no controller or transceiver.'),
]

KEEP = ({'U2', 'Q2', 'Q3', 'L1', 'D1', 'D3', 'JP1', 'JP2', 'R36',
         'C28', 'C40', 'C41', 'TP1', 'TP2', 'TP3', 'TP4', 'TP5', 'TP6',
         'J1', 'J2', 'J3', 'J6', 'J7', 'J8', 'R20', 'R21'} |
        {f'C{i}' for i in range(10, 28)} |
        {f'R{i}' for i in range(10, 18)} | {'R19'} |
        set(MOUNTING_HOLES_MM))
PARTS = [deepcopy(p) for p in previous.PARTS if p['ref'] in KEEP]
assert {p['ref'] for p in PARTS} == KEEP
for part in PARTS:
    part['pins'] = {pin: ('MOTOR_BUS' if net == '+24V' else net)
                    for pin, net in part['pins'].items()}
    part['block'] = ('A. Simple 24 V motor converter (DEVELOPMENT; no energy sink)'
                     if part['block'].startswith('A.') else
                     'B. Passive motor power/CAN connections and mounting')
by_ref = {p['ref']: p for p in PARTS}
by_ref['R20'].update(value='75 1%', lcsc='C4275',
                    mpn='UNI-ROYAL 0603WAF750JT5E',
                    status='supplier-listed; verify live assembly stock; conservative200ppm/C calculation')
by_ref['TP4']['value'] = 'BUCK 24V NOM'
by_ref['TP6']['value'] = 'MOTOR 24V NOM'
by_ref['C23']['status'] = '220nF soft-start; mandatory3.26mF nominal bulk; verify startup'
for ref in ('R16', 'R17', 'C24', 'C25', 'C26'):
    by_ref[ref]['status'] = 'reused compensation; new24V all-bulk averaged screen and measured loop qualification required'
assert len(by_ref) == len(PARTS)
assert not any(any(net.startswith(('DUMP_', 'THERMAL', 'FAULT_', '+5_DUMP', 'Q1_', 'U1_'))
                   for net in part['pins'].values()) for part in PARTS)

if __name__ == '__main__':
    import json
    print(json.dumps(dict(title=TITLE, parts=PARTS, release_holds=RELEASE_HOLDS), indent=2))
