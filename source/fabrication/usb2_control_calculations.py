#!/usr/bin/env python3
"""Reproduce v0.8 USB-control arithmetic from current inventory and pinned PDFs.

Run through source/fabrication/with_kicad.sh for inventory imports.
No board/inventory writes. This is a DC allocation/corner screen, not an
assembled-board power, USB, thermal or protection qualification. --check compares
all deterministic fields against the saved report; generation time is excluded.
"""
import argparse
import datetime
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'source/generator'))
OUT = ROOT / 'outputs/usb2-control/circuit-screen.json'
DOCS = {
 'TPS2552_TPS2553': dict(path='outputs/usb2-control/tps2552.pdf',
   url='https://www.ti.com/lit/ds/symlink/tps2552.pdf',
   revision='SLVS841G, October2026', section='8.5.1, equations1–3, pages16–17',
   required_text=['SLVS841G', '22980V', '0.94k', '23950V', '0.977k', '25230V', '1.016k']),
 'TPS54560': dict(path='outputs/usb2-control/tps54560.pdf',
   url='https://www.ti.com/lit/ds/symlink/tps54560.pdf',
   revision='SLVSBN0C, March2017', section='6.5 reference limits;8.2.2.9 output divider',
   required_text=['SLVSBN0C', '0.792', '0.808', 'Voltage reference']),
 'TLV3011B': dict(path='outputs/v08-order-preparation/datasheets/tlv3011-revc.pdf',
   url='https://www.ti.com/lit/ds/symlink/tlv3011.pdf',
   revision='SBOS300C, April2023', section='6.9 B-version quiescent current, page9',
   required_text=['TLV3011B', 'SBOS300C', '3.6', 'Quiescent current']),
 'TS3USB221A': dict(path='outputs/usb2-control/ts3usb221a.pdf',
   url='https://www.ti.com/lit/ds/symlink/ts3usb221a.pdf',
   revision='SCDS277C, October2024', section='5.5 supply and control-input current',
   required_text=['SCDS277C', 'Supply Current', '30', '20']),
 'CH334F': dict(path='outputs/usb2-control/ch334-wch-v2.5.pdf',
   url='https://cdn-learn.adafruit.com/assets/assets/000/131/435/original/CH334DS1.PDF?1721660148=',
   revision='WCH CH334/335 V2.5, manufacturer-authored mirror', section='4.2, page20',
   required_text=['V2.5', 'external load', '20', '3.5']),
}


def sha(path):
    p = Path(path)
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None


def ohms(value):
    match = re.fullmatch(r'(\d+(?:\.\d+)?)([kM]?)', value)
    if not match:
        raise ValueError('Unexpected resistor value: ' + value)
    return float(match[1]) * {'': 1, 'k': 1000, 'M': 1e6}[match[2]]


def current_limit(r_ohm, tol, thermal_fraction=0):
    """TI equations use numeric R in kohm and return numeric I in mA."""
    r = r_ohm / 1000
    return dict(minimum_mA=25230 / (r * (1 + tol) * (1 + thermal_fraction)) ** 1.016,
                nominal_mA=23950 / r ** .977,
                maximum_mA=22980 / (r * (1 - tol) * (1 - thermal_fraction)) ** .94)


def output_voltage(top, bottom, tol, thermal_fraction=0):
    low = (1 - tol) * (1 - thermal_fraction)
    high = (1 + tol) * (1 + thermal_fraction)
    return dict(nominal_V=.8 * (1 + top / bottom),
                minimum_V=.792 * (1 + top * low / (bottom * high)),
                maximum_V=.808 * (1 + top * high / (bottom * low)))


def calculate():
    # Capture imports before and after resolving the derived inventory, so a
    # concurrent source edit cannot silently mix a cached module with new hashes.
    import_paths = sorted((ROOT / 'source/generator').glob('*.py'))
    import_before = {str(p): sha(p) for p in import_paths}
    import rev08
    parts = {s['ref']: s for s in rev08.PARTS}
    loaded = {Path(m.__file__).resolve() for m in list(sys.modules.values())
              if getattr(m, '__file__', None) and
              str(Path(m.__file__).resolve()).startswith(str(ROOT / 'source/generator') + '/')}
    paths = loaded | {Path(__file__).resolve()} | {ROOT / d['path'] for d in DOCS.values()}
    before = {str(p.relative_to(ROOT)): sha(p) for p in sorted(paths)}
    checks = {}
    holds = []
    def check(name, passed, detail=None):
        checks[name] = dict(pass_=bool(passed), detail=detail)
        if not passed:
            holds.append(name)
    check('sources stable during inventory import',
          all(sha(p) == old for p, old in import_before.items()))
    evidence = {}
    for name, spec in DOCS.items():
        path = ROOT / spec['path']
        row = dict(spec, sha256=sha(path))
        text = ''
        if path.exists():
            result = subprocess.run(['pdftotext', '-layout', str(path), '-'], capture_output=True, text=True)
            text = result.stdout if result.returncode == 0 else ''
        compact = re.sub(r'\s+', '', text)
        missing = [s for s in spec['required_text'] if re.sub(r'\s+', '', s) not in compact]
        row.update(text_screen_pass=not missing and bool(text), missing_text=missing)
        evidence[name] = row
        check('primary PDF evidence present and recognized: ' + name, row['text_screen_pass'], missing)
    # Actual values and topology: series30k+7.5k at child ILIM;20k upstream.
    resistor_pins = {
      'R9901': {'1':'USB2_ILIM', '2':'USB2_ILIM_MID'},
      'R9902': {'1':'USB2_ILIM_MID', '2':'GND'},
      'R9908': {'1':'USB2_MAIN_ILIM', '2':'GND'},
      'R201': {'1':'USB_CONTROL_5V', '2':'O_FB'},
      'R202': {'1':'O_FB', '2':'GND'},
    }
    check('current-limit and feedback resistor topology matches equations',
          all(parts.get(r, {}).get('pins') == pins for r, pins in resistor_pins.items()))
    check('selected non-latching power switches present',
          parts['U9900']['value'] == 'TPS2552DBVR' and parts['U9904']['value'] == 'TPS2553DBVR')
    check('B-version comparator present and optional EEPROM absent',
          'TLV3011BIDBVR' in parts['U9903']['value'] and
          all(r not in parts for r in ('U9901', 'C9903')) and
          all(pin not in parts['U10']['pins'] for pin in ('13', '21')))
    tcr = 100e-6
    temps = [-40, 85]
    initial = .01
    max_delta = max(abs(t - 25) for t in temps)
    thermal_fraction = tcr * max_delta
    resistance_low = (1 - initial) * (1 - thermal_fraction)
    resistance_high = (1 + initial) * (1 + thermal_fraction)
    upstream_r = ohms(parts['R9908']['value'])
    child_r = sum(ohms(parts[r]['value']) for r in ('R9901', 'R9902'))
    upstream = current_limit(upstream_r, initial)
    upstream_t = current_limit(upstream_r, initial, thermal_fraction)
    child = current_limit(child_r, initial)
    child_t = current_limit(child_r, initial, thermal_fraction)
    equations = dict(Imax_mA='22980 / R_kohm**0.94', Inom_mA='23950 / R_kohm**0.977',
                     Imin_mA='25230 / R_kohm**1.016',
                     source='TI TPS2552/TPS2553 RevG8.5.1 equations1–3; includes chip temperature/process, not resistor variation',
                     external_variation='Imin uses Rmax; Imax uses Rmin. Series resistor corners are correlated conservatively.',
                     valid_R_kohm=[15,232])
    check('actual ILIM values within manufacturer equation range',
          all(15000 <= r * resistance_low <= r * resistance_high <= 232000
              for r in (upstream_r, child_r)))
    top, bottom = (ohms(parts[r]['value']) for r in ('R201','R202'))
    voltage = output_voltage(top, bottom, initial)
    voltage_t = output_voltage(top, bottom, initial, thermal_fraction)
    local = dict(voltage, feedback_resistors_ohm={'R201':top,'R202':bottom}, reference_V=[.792,.8,.808],
                 formula='Vout=Vref*(1+R201/R202)',
                 minimum_V_with_100ppm_TCR_screen=voltage_t['minimum_V'],
                 maximum_V_with_100ppm_TCR_screen=voltage_t['maximum_V'],
                 conditions='DC reference/divider corner arithmetic only; excludes bead/switch/copper drop, ripple, startup/load-step error, capacitor bias and loop dynamics.')
    # Count every current H_V33 terminal; flag a new, unbudgeted load instead of
    # silently continuing with the old schematic's sum.
    terminals = sorted((s['ref'], pin) for s in parts.values()
                       for pin, net in s['pins'].items() if net == 'H_V33')
    known = {'U10','R62','R63','R9900','R9904','U9902','U9903','C63','C64','C9905','C9906'}
    check('all actual H_V33 load references accounted for', {r for r,_ in terminals} == known,
          dict(actual=sorted({r for r,_ in terminals}), expected=sorted(known)))
    vmax = 3.5
    contributors = []
    for ref, description in [('R63','LED current conservatively bounded with zero LED forward drop'),
                             ('R62','OCS pull-up with fault output held at zero'),
                             ('R9900','Active-low downstream enable pull-up, asserted'),
                             ('R9904','Data-switch OE pull-up while comparator output low')]:
        r = ohms(parts[ref]['value'])
        contributors.append(dict(ref=ref, description=description, nominal_resistance_ohm=r,
            initial1pct_upper_mA=1000*vmax/(r*(1-initial)),
            screened_upper_mA=1000*vmax/(r*resistance_low),
            evidence='Ohm law, WCH3.5V maximumLDO and actual resistor value; zero sink/drop is conservative.'))
    for ref, description, microamps, evidence_note in [
      ('U9903','TLV3011B quiescent supply',3.6,'TI6.9: max3.1uA at25C; max3.6uA over−40..125C, output logic high; sinking current separately counted viaR9904.'),
      ('U9902','TS3USB221A static supply',30,'TI5.5:30uA max with rail-level control inputs.'),
      ('U9902','Intermediate-control supply allowance',20,'TI5.5 deltaICC endpoint3.6V, one control at1.8V; conservative engineering allowance during transitions, not a switching-energy bound.'),
      ('U9902','Two control-input leakage allowances',2,'TI5.5 max1uA per control input; conservatively additional, may overlap pull-up allocation.'),
      ('U9900','Enable-input leakage allowance',.5,'TI TPS2552/3 section6.5 IEN ±0.5uA; conservative additional allowance.'),
    ]:
        contributors.append(dict(ref=ref, description=description, initial1pct_upper_mA=microamps/1000,
                                 screened_upper_mA=microamps/1000, evidence=evidence_note))
    subtotal = sum(q['screened_upper_mA'] for q in contributors)
    check('declared DC load screen fits retained8mA allocation', subtotal < 8)
    h33 = dict(LDO_capability_mA=20, conservative_design_allocation_mA=8,
        capability_conditions='WCH4.2 states20mA external load capability in maximum column atTA25C; not a guaranteed minimum over full temperature.',
        initial1pct_contributor_sum_mA=sum(q['initial1pct_upper_mA'] for q in contributors),
        screened_contributor_sum_mA=subtotal, unused_allocation_mA=8-subtotal,
        contributors=contributors, actual_H_V33_terminals=terminals, EEPROM_load_mA=0,
        zero_DC_items=['C63','C64','C9905','C9906'],
        not_H_V33_loads=['RawVBUS10k bleeder and220k/100k sense divider draw from hostVBUS, not H_V33.',
                         'TPS2552/TPS2553 supply currents draw from5V; only downstream enable pull-up/leakage is counted here.'],
        limitations=['Allocation screen is not a guaranteed assembled-board maximum or LDO hot-load qualification.',
            'Bypass/startup charging, output/reference-capacitor leakage, real signal switching and fault behavior require measurement; unused allocation is engineering margin.',
            'The comparator supply-current condition is output high; its asserted-state behavior plus pull-up current must be measured. No artificial guaranteed maximum is inferred.',
            '8mA allocation is retained conservatively despite removed3mA optionalEEPROM; no EEPROM is populated/configured.'])
    check('selected2A bead rating exceeds upstream resistor/IC screen at85C', upstream_t['maximum_mA'] < 2000,
          'MurataBLM18PG121SN1D:2A at85C only,1A at125C. This is static current-setting comparison, not fault selectivity/inrush proof.')
    check('local no-load DC setpoint corners inside hubLDO input range',
          voltage_t['minimum_V'] >= 4.5 and voltage_t['maximum_V'] <= 5.25,
          'WCH4.2:4.5..5.25V for internalLDO. Loaded voltage losses/ripple are excluded.')
    after = {name:sha(ROOT/name) for name in before}
    changed = [name for name in before if before[name] != after[name]]
    check('all calculation inputs stable during run', not changed, changed)
    return dict(status='ARITHMETIC_SCREEN_PASS_BENCH_QUALIFICATION_REQUIRED' if all(q['pass_'] for q in checks.values()) else 'HELD',
        disposition='Current source-derived DC arithmetic only; no support-cell, routing, assembly or electrical-release claim.',
        current_limit=dict(child, R_kohm=child_r/1000, resistor_initial_tolerance=initial,
            min_mA_with_TCR_screen=child_t['minimum_mA'], max_mA_with_TCR_screen=child_t['maximum_mA']),
        upstream_current_limit=dict(R_kohm=upstream_r/1000, resistor_initial_tolerance=initial,
            min_mA_1pct=upstream['minimum_mA'], max_mA_1pct=upstream['maximum_mA'], nominal_mA=upstream['nominal_mA'],
            min_mA_with_TCR_screen=upstream_t['minimum_mA'], max_mA_with_TCR_screen=upstream_t['maximum_mA']),
        current_limit_equations=equations,
        resistor_TCR_engineering_screen=dict(ppm_per_C=100, temperatures_C=temps, reference_C=25,
            maximum_temperature_delta_C=max_delta, resistance_factors=[resistance_low,resistance_high],
            formula='Rmin=Rnom*(1-initial_tolerance)*(1-TCR*max_deltaT); Rmax=Rnom*(1+initial_tolerance)*(1+TCR*max_deltaT)',
            note='Explicit100ppm/C screen for the selected ordinary resistors; not a measured drift bound or an extra chip-temperature error term.'),
        local5V=local, H_V33_external_budget=h33, checks=checks, review_holds=holds,
        source_sha256=before, datasheet_evidence=evidence,
        qualification_holds=['Measure simultaneous active/suspend/reset currents; WCH and codec have no guaranteed operating-current maximum.',
            'Measure loaded voltages, ripple, startup/inrush and temperature; setpoint/current-limit arithmetic does not establish USBport compliance or available load current.',
            'Verify regulator OFF, hub/child faults, hostVBUS isolation/detach, power order and actual descriptor/firmware behavior.',
            'Verify actual resistor TCR/temperature, bead derating, switch losses and circuit-layout current-limit noise; no selective clearing guarantee.'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=OUT)
    ap.add_argument('--check', action='store_true', help='Reproduce deterministic fields without rewriting saved report')
    args = ap.parse_args()
    result = calculate()
    if args.check:
        saved = json.loads(args.output.read_text())
        saved.pop('generated_utc', None)
        same = saved == json.loads(json.dumps(result))
        print(json.dumps(dict(reproduces_saved_report=same,status=result['status']),indent=2))
        return int(not same or bool(result['review_holds']))
    result['generated_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key:result[key] for key in ('status','generated_utc','current_limit','upstream_current_limit','local5V')},indent=2))
    print(json.dumps(dict(H_V33_mA=result['H_V33_external_budget']['screened_contributor_sum_mA'],
                         retained_allocation_mA=8,holds=result['review_holds']),indent=2))
    return int(bool(result['review_holds']))


if __name__ == '__main__':
    raise SystemExit(main())
