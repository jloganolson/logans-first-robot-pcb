"""Autonomous resistor-clamp motor supply, derived from frozen motor_addon.

Development only. Buck output and motor bus are shared; source-side reverse
protection and fuse are mandatory in the main composition. External resistor
and normally-closed one-shot thermal cutoff must be installed before enabling.
"""
from copy import deepcopy
import motor_addon as previous

TITLE='DDSM350 motor supply: 22.34V buck + autonomous external-resistor clamp'
REVISION='0.8 resistor-clamp development'
BOARD_SIZE_MM=previous.BOARD_SIZE_MM
MOUNTING_HOLES_MM=previous.MOUNTING_HOLES_MM
CUSTOM_SYMBOL_PINS=deepcopy(previous.CUSTOM_SYMBOL_PINS)
NO_CONNECT_PINS=deepcopy(previous.NO_CONNECT_PINS)
DATASHEETS={k:v for k,v in previous.DATASHEETS.items() if k not in ('U1','external_resistor')}
DATASHEETS.update(wheel='https://docs.waveshare.com/DDSM350-CT',
                 external_resistor='https://www.ohmite.com/hs-aluminium-housed-resistors/',
                 resistor_historical_application_guidance='https://us.rs-online.com/m/d/840dcab3450261b61b91e3aa6789a31d.pdf',
                 cutoff='https://media.schott.com/api/public/content/ff224fc379ec4eb09a770a547ac50b04?download=true&v=18465cc0')
SCHEMATIC_NOTES=('DEVELOPMENT ONLY. 22.344V buck and23.xV autonomous clamp share MOTOR_BUS. '
 'Input must have main-board source fuse and reverse protection. External3.3ohm100W chassis resistor '
 'J4.1=DUMP_LOW/J4.2=MOTOR_BUS; never shortJ4. Normally-closed one-shot thermal cutoff J5 grounds '
 'control node while healthy; open/hot inhibitsbuck, leavingdumpconnected. '
 'Wheels24Vnominal only: lower operating and maximum/transient limits unverified. '
 '20J/stop,3mph20lb,10Acontinuous12Atransient are development budgets, not ratings.')
REMOVED_REFS={'U1','Q1','C1','C2'}
PARTS=[deepcopy(s) for s in previous.PARTS if s['ref'] not in REMOVED_REFS]
for s in PARTS:
    s['pins']={k:('MOTOR_BUS' if v=='+24V' else v) for k,v in s['pins'].items()}
    if s['ref']=='R13':
        s.update(lcsc='C245992',mpn='Yageo RC0603FR-07649RL',
                 status='649ohm1%0603; verify assembly reservation/attrition')
    if s['ref'] in ('C28','C40','C41'):
        s['status']='MANDATORY hand-fit1000uF35V afterSMT; allthree shareMOTOR_BUS; verifypolarity/startup'
    if s['ref'] in ('R16','R17','C24','C25','C26'):
        s['status']='reused averaged-screened compensation; sharedbulk topology must pass new screen/bench measurement'
RELEASE_HOLDS=[
    'Waveshare publishes rated24V only. Verify22.34V operation and allowed maximum/transient voltage; clamp23.xV is not an approved motor rating.',
    'Install external3.3ohm100W resistor and one-shot NC cutoff before enabling. Validate actual pulse current/energy/repetition, chassis temperature, inductive overshoot and cutoff thermal lag.',
    'Mandatory main source fuse and LM74700 input reverse-protection stage are absent from this cell. Standalone use must add them.',
    '10Acontinuous/12Atransient and20Jstop are design budgets, not measured ratings. Current limit, loop stability, input headroom, inrush/SOA and fuse/harness coordination remain bench work.',
    'Removing output ideal diode permits motor-bus energy to charge the isolated converter input through the high-side body diode during power removal. Verify switch-off, EN/thermal behavior and restart with actual source protection.',
    'Open/hot cutoff inhibits the buck, not the CAN wheel drive or a mechanical brake. Remaining regeneration is still dissipated, but continuous downhill/external forcing is not bounded by this prototype.',
    'Loss of clamp-control power or a failed-open resistor can remove absorption; no independent second overvoltage shutdown is fitted. Instrumented bring-up and fault tests remain required.',
]
EXTERNAL_PARTS=[
    dict(item='brake resistor',quantity=1,mpn='Ohmite/ARCOL HS100 3R3 F',
         notes='3.3ohm1%100W ordinarywirewound; stockedcandidate. Chassis mount+thermalcompound; freewheelD2fitted. Pulse/inductance/mounting qualification required.'),
    dict(item='thermal cutoff',quantity=1,mpn='SCHOTT SEFUSE SM110A0',
         notes='Normallyconductingone-shot, nominalopening110C; control-loopJ5only, neverresistorcurrent. Thermalclip+crimp/strainrelief; replaceaftertrip.'),
    dict(item='source protection',quantity=1,notes='Main F1 branch fuse and input ideal diode required; neither is included in this cell.'),
]
assert len(PARTS)==len(previous.PARTS)-4
assert len({s['ref'] for s in PARTS})==len(PARTS)
assert not any(v in ('+24V','Q1_G','U1_VCAP') for s in PARTS for v in s['pins'].values())
assert next(s for s in PARTS if s['ref']=='JP1')['pins']=={'1':'T_EN','2':'GND'}

if __name__=='__main__':
    import json
    print(json.dumps(dict(title=TITLE,parts=PARTS,release_holds=RELEASE_HOLDS,external_parts=EXTERNAL_PARTS),indent=2))
