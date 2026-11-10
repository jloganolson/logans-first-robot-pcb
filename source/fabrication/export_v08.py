#!/usr/bin/env python3
"""Prepare an immutable v0.8 PROTOTYPE QUOTE, never a purchase/release.

Run through with_kicad.sh. Every invocation runs both independent audits afresh;
no fabrication files are generated unless both clear the exact current inputs.
--check-only stops before creating a quote directory. Nothing refills/saves the
canonical PCB, changes factory settings, uploads files or purchases anything.
"""
import argparse
import collections
import csv
import datetime
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'source/generator'))
DEFAULT_BOARD = ROOT / 'revisions/v0.8/kicad/robot_pdb.kicad_pcb'
OUTPUT = ROOT / 'outputs/v08-order-preparation'
LAYOUT_OK = 'PROTOTYPE_LAYOUT_SCREEN_COMPLETE_BENCH_QUALIFICATION_REQUIRED'
USB_OK = 'GEOMETRY_SCREEN_COMPLETE_BENCH_QUALIFICATION_REQUIRED'
LAYERS = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
STARTING_OFFSETS = [(r'^SOT-23', -90), (r'^LQFP-', 270),
    (r'^HTSSOP-', 270), (r'^VSSOP-8_', 180), (r'^TDSON-8-1', 270),
    (r'^CP_Elec_10x10', 180), (r'^(.*?_|V)?QFN-(16|20|24|28|40|56)(-|_|$)', 270)]
MANUFACTURING = dict(board_size_mm=[340, 230], thickness_mm=1.6, layers=4,
    factory_stackup='JLC041621-2116', finish='ENIG', outer_copper_oz=2,
    inner_copper_nominal_oz=1, copper_thickness_mm={'F.Cu': .070, 'In1.Cu': .030,
    'In2.Cu': .030, 'B.Cu': .070}, outer_dielectric_mm=.109,
    core_without_copper_mm=1.230, nominal_new_usb_width_mm=.165,
    nominal_new_usb_gap_mm=.300, differential_impedance_target_ohm=90,
    reference_layers={'F.Cu': 'In1.Cu GND', 'B.Cu': 'In2.Cu GND'},
    manufacturer_confirmation_required=True,
    evidence_urls=['https://jlcpcb.com/impedance', 'https://jlcpcb.com/pcb-impedance-calculator'],
    note='Requirements and saved-board geometry; not a factory field-solver acceptance or production approval.')


class Held(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Held(message)


def digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def read_json(path):
    return json.loads(Path(path).read_text())


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def current_hashes(record, label):
    require(bool(record), label + ': missing source hashes')
    for name, expected in record.items():
        path = Path(name)
        if not path.is_absolute():
            path = ROOT / path
        require(digest(path) == expected, label + ': stale/missing ' + str(path))


def execute(command, log, allow_failure=False):
    result = subprocess.run(list(map(str, command)), capture_output=True, text=True)
    with Path(log).open('a') as stream:
        stream.write(json.dumps(list(map(str, command))) + '\n' + result.stdout + result.stderr + '\n')
    if not allow_failure:
        require(result.returncode == 0, 'Command failed; see ' + str(log))
    return result


def watched_inputs(board, cells):
    paths = {Path(__file__).resolve(), board,
        *(board.with_suffix(s) for s in ('.kicad_pro', '.kicad_sch', '.kicad_dru')),
        board.parent.parent / 'composition.json', board.parent.parent / 'integration-routing.json',
        ROOT / 'revisions/v0.8/prototype-usb-fs-exceptions.json',
        ROOT / 'revisions/motor-resistor/calculations.json',
        ROOT / 'outputs/motor-resistor-design/validation.json',
        ROOT / 'docs/MOTOR_RESISTOR_BUILD.md', ROOT / 'docs/USB_VBUS_DETECTOR_REVIEW.md'}
    # Include transitive inventory/calculation dependencies, not just rev08.py.
    paths.update((ROOT / 'source/generator').glob('*.py'))
    paths.update((ROOT / 'source/fabrication').glob('*.py'))
    paths.update(ROOT / cell['board'] for cell in cells.values())
    paths.update(board.parent.glob('*.kicad_sym'))
    paths.update(board.parent / n for n in ('fp-lib-table', 'sym-lib-table'))
    paths.update((board.parent / 'Robot_PDB.pretty').glob('*.kicad_mod'))
    return {str(path.resolve()): digest(path) for path in sorted(paths)}


def profile_gate(board):
    import pcbnew as p
    b = p.LoadBoard(str(board))
    require(b.GetCopperLayerCount() == 4, 'Expected four copper layers')
    require(abs(p.ToMM(b.GetDesignSettings().GetBoardThickness()) - 1.6) < 1e-6,
            'Expected nominal1.6mm PCB')
    box = b.GetBoardEdgesBoundingBox()
    # KiCad's drawing box includes the Edge.Cuts stroke, not just the routed
    # boundary centreline. The uniform0.1mm outline adds0.1mm to both dimensions.
    edge_widths = {d.GetWidth() for d in b.GetDrawings() if d.GetLayer() == p.Edge_Cuts}
    require(len(edge_widths) == 1, 'Nonuniform outline strokes require explicit dimension review')
    stroke = p.ToMM(next(iter(edge_widths)))
    require(abs(p.ToMM(box.GetWidth()) - stroke - 340) < .001 and
            abs(p.ToMM(box.GetHeight()) - stroke - 230) < .001, 'Unexpected board outline dimensions')
    text = board.read_text()
    for layer, thickness in MANUFACTURING['copper_thickness_mm'].items():
        found = re.search(r'\(layer "' + re.escape(layer) + r'" \(type "copper"\) \(thickness ([0-9.]+)\)', text)
        require(found and abs(float(found[1]) - thickness) < 1e-6,
                layer + ': saved stackup differs from selected2oz/1oz profile')
    for number in (1, 3):
        found = re.search(r'\(layer "dielectric ' + str(number) + r'" \(type "prepreg"\) \(thickness ([0-9.]+)\) \(material "([^"]+)"\)', text)
        require(found and abs(float(found[1]) - .109) < 1e-6 and '2116' in found[2],
                'Outer dielectric differs from JLC041621-2116 requirement')
    require('(copper_finish "ENIG")' in text, 'Expected ENIG stackup finish')
    require(re.search(r'\(layer "dielectric 2" \(type "core"\) \(thickness 1\.23\)', text),
            'Unexpected core thickness')
    return b


def resistor_contract(parts):
    import motor_resistor
    from motor_resistor_calculations import calculate
    require('J6090' not in parts, 'Obsolete unprotected plain-bus J6090 must be absent')
    require(parts['J6004']['pins'] == {'1': 'M_DUMP_LOW', '2': 'MOTOR_BUS'}, 'Resistor power port changed')
    require(parts['J6005']['pins'] == {'1': 'M_THERMAL_CONTACT', '2': 'GND'}, 'NC thermal port changed')
    require(parts['JP6001']['pins'] == {'1': 'M_T_EN', '2': 'GND'}, 'Motor service OFF contract changed')
    require(parts['U9903'].get('dnp') and 'TLV3011BIDBVR' in parts['U9903']['value'],
            'Mandatory hand-fit B-version VBUS comparator contract changed')
    require(not parts['U6005'].get('dnp') and 'TLV3201' in parts['U6005']['value'],
            'Autonomous clamp comparator must remain factory fitted')
    for ref in ('C6028', 'C6040', 'C6041'):
        require(parts[ref].get('dnp') and '1000' in parts[ref]['value'],
                ref + ': mandatory bulk manual-fit classification changed')
    require(not any(r in parts for r in ('U6001', 'Q6001')), 'Removed motor output ideal diode returned')
    external = {q['item']: q for q in motor_resistor.EXTERNAL_PARTS}
    require(external['brake resistor']['mpn'] == 'Ohmite/ARCOL HS100 3R3 F', 'Selected resistor changed')
    require(external['thermal cutoff']['mpn'] == 'SCHOTT SEFUSE SM110A0', 'Selected cutoff changed')
    calc = read_json(ROOT / 'revisions/motor-resistor/calculations.json')
    require(json.loads(json.dumps(calculate())) == calc,
            'Motor calculations do not reproduce from current sources')
    require(calc.get('checks') and all(calc['checks'].values()), 'Motor calculation screen held')
    require(calc['resistor']['mpn'] == 'Ohmite/ARCOL HS1003R3F', 'Stale resistor calculation contract')
    require(calc['source_urls']['external_resistor'] ==
            'https://www.ohmite.com/hs-aluminium-housed-resistors/', 'Stale external resistor provenance')
    return dict(external_parts=motor_resistor.EXTERNAL_PARTS, calculation=calc,
                documentation='docs/MOTOR_RESISTOR_BUILD.md', qualification_holds=motor_resistor.RELEASE_HOLDS)


def fresh_audits(board, out):
    log = out / 'audit-commands.log'
    execute([sys.executable, '-B', ROOT / 'source/fabrication/audit_v08_usb.py',
             board, '--output', out / 'usb-channel-audit.json'], log, allow_failure=True)
    execute([sys.executable, '-B', ROOT / 'source/fabrication/audit_v08.py',
             '--board', board, '--output', out], log, allow_failure=True)
    require((out / 'validation.json').exists() and (out / 'usb-channel-audit.json').exists(),
            'Independent audits did not produce both reports; see ' + str(log))
    layout, usb = read_json(out / 'validation.json'), read_json(out / 'usb-channel-audit.json')
    h = digest(board)
    require(layout.get('board_sha256') == usb.get('board_sha256') == h, 'Audit PCB hash mismatch')
    require(layout.get('status') == LAYOUT_OK and layout.get('logical_status') == 'PASS',
            'Independent integrated audit HELD; see ' + str(out / 'validation.json'))
    require(layout.get('checks') and all(q.get('pass_') is True for q in layout['checks']),
            'Integrated audit contains a failed/incomplete check')
    require(layout.get('native_physical_errors') == 0 and layout.get('native_unconnected_items') == 0,
            'Native physical DRC errors or open nets remain')
    require(layout.get('factory_drills', {}).get('status') == 'PASS', 'Factory drill screen held')
    require(not layout.get('live_inputs_changed_during_audit'), 'Inputs changed during integrated audit')
    current_hashes(layout.get('audited_input_sha256'), 'Integrated audit')
    require(layout.get('audit_generator_sha256') == digest(ROOT / 'source/fabrication/audit_v08.py'),
            'Independent audit generator changed')
    require(usb.get('status') == USB_OK and not usb.get('review_holds') and
            not usb.get('inputs_changed_during_run'), 'Independent complete USB audit HELD')
    require(len(usb.get('channels', [])) == 8, 'Incomplete independent USB channel inventory')
    current_hashes(usb.get('source_sha256'), 'USB audit sources')
    current_hashes(usb.get('related_artifact_sha256'), 'USB audit observed artifacts')
    # Require explicit native report evidence as well as JSON count summaries.
    native = (out / 'native-drc.rpt').read_text()
    require('Severity: error' not in native and '** Found 0 unconnected pads **' in native,
            'Fresh native DRC report is not clear')
    return layout, usb


def manual_fit(s):
    return bool(s.get('dnp') or s.get('manual_fit') or
                re.search(r'\b(?:hand[ -]?fit|manual[ -]?fit)\b', s.get('status', ''), re.I))


def write_csv(path, headings, rows):
    with Path(path).open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(headings)
        writer.writerows(rows)


def assembly_files(out, board, parts):
    import pcbnew as p
    loaded = p.LoadBoard(str(board))
    physical = list(loaded.GetFootprints())
    require(len(physical) == len(parts) and {f.GetReference() for f in physical} == set(parts),
            'Export snapshot references differ from imported assembly inventory')
    for footprint in physical:
        ref = footprint.GetReference()
        spec = parts[ref]
        require(footprint.GetValue() == spec['value'] and
                str(footprint.GetFPID().GetUniStringLibId()) == spec['fp'],
                ref + ': export inventory value/footprint differs from actual audited snapshot')
        numbered = {pad.GetNumber(): pad.GetNetname() for pad in footprint.Pads() if pad.GetNumber()}
        require(numbered == spec['pins'], ref + ': export inventory pin map differs from actual snapshot')
    fitted = {ref for ref, spec in parts.items() if not manual_fit(spec)}
    require(fitted and all(parts[r].get('lcsc') for r in fitted), 'Fitted assembly part lacks supplier code')
    require('U9903' not in fitted and 'U6005' in fitted, 'Comparator assembly classification changed')
    groups = collections.defaultdict(list)
    for ref in sorted(fitted):
        s = parts[ref]
        groups[s['value'], s['fp'], s['lcsc']].append(ref)
    write_csv(out / 'BOM_JLCPCB.csv', ['Comment', 'Designator', 'Footprint', 'LCSC Part #'],
        [[v, ','.join(refs), fp.split(':', 1)[-1], code] for (v, fp, code), refs in sorted(groups.items())])
    execute(['kicad-cli', 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
             '--side', 'both', '-o', out / 'raw-positions.csv', board], out / 'export.log')
    placements = []
    with (out / 'raw-positions.csv').open() as stream:
        for row in csv.DictReader(stream):
            ref = row['Ref']
            if ref not in fitted:
                continue
            fp = parts[ref]['fp'].split(':', 1)[-1]
            offset = next((v for pattern, v in STARTING_OFFSETS if re.match(pattern, fp)), 0)
            require(row['Side'] in ('top', 'bottom'), 'Unknown position side for ' + ref)
            values = [float(row[k]) for k in ('PosX', 'PosY', 'Rot')]
            require(all(math.isfinite(v) for v in values), 'Invalid placement coordinates')
            placements.append(dict(ref=ref, x_mm=values[0], y_mm=values[1],
                layer='Top' if row['Side'] == 'top' else 'Bottom', kicad_rotation=values[2],
                offset_deg=offset, quote_rotation=(values[2] + offset) % 360,
                verification='UNVERIFIED; inspect actual supplier preview, underside and pin1/polarity'))
    require(len(placements) == len(fitted) and {q['ref'] for q in placements} == fitted,
            'CPL references do not exactly match fitted BOM (missing/duplicate placements)')
    write_csv(out / 'CPL_JLCPCB.csv', ['Designator', 'Mid X', 'Mid Y', 'Layer', 'Rotation'],
        [[q['ref'], q['x_mm'], q['y_mm'], q['layer'], q['quote_rotation']] for q in placements])
    write_json(out / 'placement-offsets-UNVERIFIED.json', placements)
    write_json(out / 'inventory-and-assembly-classification.json', dict(parts=list(parts.values()),
        fitted=sorted(fitted), excluded_manual_or_DNP=sorted(parts.keys() - fitted),
        warning='DNP means omitted from factory assembly. It does not make mandatory manual components optional.'))
    return dict(fitted_parts=len(fitted), bom_lines=len(groups), placements=len(placements),
                sides=dict(collections.Counter(q['layer'] for q in placements)),
                placement_review_complete=False)


def hand_fit_file(out, parts):
    rows = []
    for ref, s in sorted(parts.items()):
        if not manual_fit(s):
            continue
        optional = ref in ('U9901', 'C9903') or 'optional' in s.get('status', '').lower()
        rows.append([ref, 'OPTIONAL / OMIT BY DEFAULT' if optional else 'MANUAL ITEM; review stated requirement',
            s['value'], s.get('mpn', ''), s.get('lcsc', ''), s.get('status', ''), '', '', ''])
    # Explicit mandatory records prevent a DNP flag being read as permission to omit.
    rows.extend([
        ['U9903', 'MANDATORY HAND FIT before USB use', 'VBUS comparator, B suffix required',
         'TI TLV3011BIDBVR', '296-TLV3011BIDBVRCT-ND', 'Not in fitted factory catalogue total; observed2026-11-09, not reserved/landed quote',
         '2.78', 'USD', 'https://www.digikey.com/en/products/detail/texas-instruments/TLV3011BIDBVR/19236273'],
        ['C6028,C6040,C6041', 'MANDATORY HAND FIT before wheel power', 'Three1000uF35V bulk capacitors',
         'Use exact current inventory MPN; verify polarity', '', 'All three share MOTOR_BUS; not optional DNP', '', '', ''],
        ['J6004 harness', 'MANDATORY before wheel enable', '3.3ohm1%100W chassis brake resistor',
         'Ohmite/ARCOL HS1003R3F', '273-HS1003R3F-ND',
         'J6004.1=DUMP_LOW; .2=MOTOR_BUS. Thermal compound/chassis mounting and measured pulse duty required. Observed2026-11-09 stock22; not reserved.',
         '18.91', 'USD', 'https://www.digikey.com/en/products/detail/ohmite/HS100-3R3-F/21845791'],
        ['J6005 harness', 'MANDATORY before wheel enable', 'Normally closed one-shot thermal cutoff',
         'SCHOTT SEFUSE SM110A0', 'Traceable exact part; procurement pending',
         'J6005.1=THERMAL_CONTACT; .2=GND. Control loop only; thermally couple to resistor; crimp/weld; replace after trip. No verified small-quantity price.',
         '', '', 'https://atcsemitec.co.uk/product/sefuse-sm-a-thermal-fuse/'],
        ['Resistor mounting', 'MANDATORY', 'Qualified aluminum chassis/heatsink, compound, thermal clip, insulated wiring and strain relief',
         'See docs/MOTOR_RESISTOR_BUILD.md', '', '100W assumes specified mounting;20J/stop and10W average are prototype budgets requiring measurement.', '', '', ''],
        ['J3 Thor cable', 'MANDATORY for Thor connection', '300mm18AWG factory crimped four-circuit Micro-Fit cable',
         'Molex2147551042', '900-2147551042-ND', 'Official1↔2,3↔4 preserves power groups. Meter delivered cable before power.', '', '', ''],
        ['Battery disconnect', 'MANDATORY', 'DC-rated mechanical DPST with four heavy wires',
         'External switch, separately mounted', '', 'Stop before OFF; disconnect both pack positive leads before they join. Not a two-wire downstream switch.', '', '', ''],
        ['Power harness', 'MANDATORY', 'Source-end pack fuses, branch fuses, sized conductors, supported connectors',
         'Current inventory F1/F2/F7000 plus pack-source protection', '', 'Verify fuse interruption/overload coordination and complete harness continuity before battery operation.', '', '', ''],
        ['Supports/firmware', 'MANDATORY before robot operation', 'Nylon supports, wire strain relief; flash both STM32 controllers',
         'Current board supports and firmware/robot_io', '', 'Board must not carry heavy cable forces unsupported; firmware is not installed by BOM/CPL export.', '', '', ''],
    ])
    write_csv(out / 'hand-fit-and-harness.csv', ['Reference', 'Requirement', 'Description', 'Manufacturer part',
        'Supplier part', 'Notes', 'Observed unit price', 'Currency', 'Source'], rows)


def impedance_requirements(out, pcb_hash):
    from PIL import Image, ImageDraw, ImageFont
    text = ('Robot PDB v0.8 - USB2 impedance requirements\n\n'
        'PROTOTYPE QUOTE. MANUFACTURER CONFIRMATION REQUIRED BEFORE FABRICATION.\n'
        '340 x230mm; nominal1.6mm; four layers; ENIG; outer2oz, inner nominal1oz.\n'
        'Selected stackup: JLC041621-2116. Saved copper0.070/0.030/0.030/0.070mm; '
        'outer2116 prepreg0.109mm each; core1.230mm without copper.\n\n'
        'Target90ohm DIFFERENTIAL. Nominal NEW uniform USB2 tracks: width0.165mm '
        'each conductor, edge-to-edge pair gap0.300mm. F.Cu signals reference In1.Cu GND; '
        'B.Cu signals reference In2.Cu GND. Preserve continuous adjacent reference.\n'
        'Confirm impedance tolerance with manufacturer, exact production stackup/copper/mask and '
        'field-solver width/spacing; provide coupon/TDR results. No substitution without owner review.\n\n'
        'Localized component lands, connector aliases, via transitions and package escapes have '
        'intentional changes of geometry. Retained FullSpeed audio/Dynamixel tails are not uniformly '
        '0.165/0.300mm, and include inherited inner-layer routing. Review the supplied complete-channel '
        'audit and bounded exceptions. A uniform coupon does not qualify every retained tail or complete USB link.\n'
        'This package has USB2 control circuitry only. Camera/microphone USB3 connect externally. '
        'Do not apply superseded v0.7 USB3/thin-board/fine-via requirements.\n\n'
        'Both-side Standard assembly; verify stencil thickness against actual package datasheets '
        '(100um maximum for populated TI DRT packages). Factory-added rails, tooling holes and '
        'fiducials on both assembled faces; keep connector access clear. Review actual factory matching '
        'and all polarized/custom/underside placements before purchase.\n\nExact PCB SHA256: ' + pcb_hash + '\n'
        'Stackup evidence: https://jlcpcb.com/impedance ; https://jlcpcb.com/pcb-impedance-calculator\n')
    (out / 'USB_IMPEDANCE_REQUIREMENTS.txt').write_text(text)
    regular = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 28)
    lines = [line for paragraph in text.splitlines() for line in (textwrap.wrap(paragraph, 108) or [''])]
    im = Image.new('RGB', (2200, 80 + len(lines) * 43), 'white')
    draw = ImageDraw.Draw(im)
    for i, line in enumerate(lines):
        draw.text((35, 30 + i * 43), line, font=regular, fill='black')
    im.save(out / 'USB_IMPEDANCE_REQUIREMENTS.jpg', quality=96)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--board', type=Path, default=DEFAULT_BOARD)
    ap.add_argument('--check-only', action='store_true', help='Fresh gates only; no fabrication/assembly exports')
    args = ap.parse_args()
    board = args.board.resolve()
    import_inputs = {str(path): digest(path) for folder in ('source/generator', 'source/fabrication')
                     for path in (ROOT / folder).glob('*.py')}
    import rev08
    parts = {s['ref']: s for s in rev08.PARTS}
    current_hashes(import_inputs, 'Inventory sources during import')
    require(len(parts) == len(rev08.PARTS), 'Duplicate inventory references')
    OUTPUT.mkdir(parents=True, exist_ok=True)
    before = watched_inputs(board, rev08.CELLS)
    current_hashes(import_inputs, 'Inventory sources while capturing inputs')
    require(all(v is not None for k, v in before.items() if not k.endswith('.kicad_dru')),
            'Required manufacturing/source input is missing')
    preflight = Path(tempfile.mkdtemp(prefix='preflight-', dir=OUTPUT))
    quote = None
    try:
        layout, usb = fresh_audits(board, preflight)
        profile_gate(board)
        contract = resistor_contract(parts)
        current_hashes(before, 'Input snapshot after independent checks')
        require(layout['inventory_parts'] == len(parts), 'Audit inventory changed')
        bundle = hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
        gate = dict(status='QUOTE_GENERATION_GATES_CLEAR', board_sha256=digest(board),
            source_bundle_sha256=bundle, manufacturing=MANUFACTURING, independent_reports={
            name: digest(preflight / name) for name in ('validation.json', 'usb-channel-audit.json')},
            fabrication_release=False, purchase_approved=False, bench_holds=layout['electrical_release_holds'])
        write_json(preflight / 'quote-generation-gate.json', gate)
        if args.check_only:
            print(json.dumps(dict(gate=gate, reports=str(preflight), exports_generated=False), indent=2))
            return 0
        quote = OUTPUT / ('quote-' + digest(board)[:12] + '-' + bundle[:12])
        require(not quote.exists(), 'This immutable quote directory already exists; old draft preserved: ' + str(quote))
        quote.mkdir()
        shutil.copytree(preflight, quote / 'validation')
        snapshot = quote / 'validation/audit-input' / board.name
        require(digest(snapshot) == digest(board), 'Audited immutable snapshot differs from live PCB')
        snapshot_hashes = {str(snapshot.with_suffix(suffix)): before[str(board.with_suffix(suffix))]
                           for suffix in ('.kicad_pcb', '.kicad_sch', '.kicad_pro', '.kicad_dru')}
        current_hashes(snapshot_hashes, 'Copied manufacturing snapshot')
        profile_gate(snapshot)
        assembly = assembly_files(quote, snapshot, parts)
        hand_fit_file(quote, parts)
        write_json(quote / 'manufacturing-requirements.json', MANUFACTURING)
        write_json(quote / 'motor-resistor-contract.json', contract)
        documentation = quote / 'documentation'
        documentation.mkdir()
        for name in ('MOTOR_RESISTOR_BUILD.md', 'USB_VBUS_DETECTOR_REVIEW.md'):
            shutil.copyfile(ROOT / 'docs' / name, documentation / name)
        impedance_requirements(quote, digest(snapshot))
        gerbers = quote / 'gerbers'
        gerbers.mkdir()
        execute(['kicad-cli', 'pcb', 'export', 'gerbers', '--layers', LAYERS,
                 '--subtract-soldermask', '-o', str(gerbers) + '/', snapshot], quote / 'export.log')
        execute(['kicad-cli', 'pcb', 'export', 'drill', '--format', 'excellon',
                 '--excellon-separate-th', '-o', str(gerbers) + '/', snapshot], quote / 'export.log')
        files = sorted(gerbers.iterdir())
        require(len([f for f in files if f.suffix not in ('.drl', '.gbrjob')]) == 11,
                'Expected eleven plotted manufacturing layers')
        require(any(f.suffix == '.drl' for f in files), 'No drill files generated')
        with zipfile.ZipFile(quote / 'Robot_PDB_v08_Gerbers.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
            for f in files + [quote / 'USB_IMPEDANCE_REQUIREMENTS.jpg', quote / 'USB_IMPEDANCE_REQUIREMENTS.txt']:
                archive.write(f, f.name)
        for side, layers in [('top', 'F.Cu,F.Silkscreen,Edge.Cuts'), ('bottom', 'B.Cu,B.Silkscreen,Edge.Cuts')]:
            execute(['kicad-cli', 'pcb', 'export', 'svg', '--layers', layers, '--page-size-mode', '2',
                     '--exclude-drawing-sheet', '-o', quote / ('board-' + side + '.svg'), snapshot], quote / 'export.log')
        execute(['kicad-cli', 'sch', 'export', 'svg', '--exclude-drawing-sheet',
                 '-o', str(quote / 'schematic-svg') + '/', snapshot.with_suffix('.kicad_sch')], quote / 'export.log')
        current_hashes(before, 'Canonical/source inputs after exports')
        current_hashes(snapshot_hashes, 'Audited snapshot after exports')
        (quote / 'READ_BEFORE_ORDERING.txt').write_text(
            'PROTOTYPE QUOTE ONLY. No purchase or fabrication release is authorized by this package.\n'
            'All CPL rotation offsets are UNVERIFIED starting values. Inspect real supplier BOM matching, '
            'pin1/polarity, custom footprints, underside placements and the required manual fit list.\n'
            'U9903 TLV3011BIDBVR is mandatory hand fit ($2.78 observed, separate from factory fitted total). '
            'U6005 TLV3201 remains factory fitted. Optional EEPROM is not required/programmed by this export.\n'
            'Mandatory Ohmite HS1003R3F external chassis resistor, SM110A0 NC cutoff and three motor bulk capacitors '
            'must be fitted before wheel use. Confirm factory stackup/impedance and production files before purchase.\n'
            'Electrical bench holds remain in validation/validation.json and motor-resistor-contract.json.\n')
        outputs = {str(f.relative_to(quote)): digest(f) for f in sorted(quote.rglob('*')) if f.is_file()}
        manifest = dict(status='PROTOTYPE_QUOTE_ARTIFACTS_GENERATED_REVIEW_REQUIRED',
            timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            board_sha256=gate['board_sha256'], source_bundle_sha256=bundle, source_sha256=before,
            output_sha256=outputs, assembly=assembly, manufacturing=MANUFACTURING,
            gates=gate, fabrication_release=False, purchase_approved=False,
            factory_matching_verified=False, factory_rotations_verified=False,
            manufacturer_impedance_confirmed=False, hardware_tested=False)
        write_json(quote / 'source-manifest.json', manifest)
        print(json.dumps(dict(status=manifest['status'], directory=str(quote), assembly=assembly), indent=2))
        return 0
    except Exception as error:
        failure = dict(status='HELD_NO_VALID_QUOTE', reason=str(error), source_board=str(board),
                       fabrication_release=False, purchase_approved=False)
        write_json(preflight / 'quote-generation-gate.json', failure)
        if quote and quote.exists():
            write_json(quote / 'EXPORT_INCOMPLETE_DO_NOT_UPLOAD.json', failure)
        raise


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Held as error:
        print('HELD: ' + str(error), file=sys.stderr)
        raise SystemExit(1)
