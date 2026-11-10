#!/usr/bin/env python3
"""Create a non-orderable v0.5 fabrication review bundle.

The original sources are read only. A successful run is not an order release.
"""
import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REV = ROOT / 'revisions' / 'v0.5'
PROJECT = REV / 'kicad'
PCB = PROJECT / 'robot_pdb.kicad_pcb'
SCH = PROJECT / 'robot_pdb.kicad_sch'
PARTS = REV / 'review-parts.csv'
EXPECTED = {
    PCB: 'f8b21581a7e25a711ffde62716d4c0b1a8cafae6eabae5d2be4a8d8366df0737',
    SCH: 'fbe1b2ded112e5ee9aa0159eb7456e386530ee8aa343998e4bf1364a2982647a',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    for path in (PCB, SCH, PARTS):
        if not path.is_file():
            raise RuntimeError(f'Missing input: {path}')
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in (PCB, SCH, PARTS)}
    with PARTS.open(newline='', encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    flagged = [{'reference': r['Reference'], 'supplier_code': r['Supplier code (review only)']}
               for r in rows if not r['Supplier code (review only)'].strip()
               or 'HOLD' in r['Supplier code (review only)'].upper()]
    return {
        'disposition': 'HOLD - NOT FOR ORDER',
        'source_sha256': hashes,
        'matches_original_handoff_hashes': all(digest(p) == h for p, h in EXPECTED.items()),
        'review_parts_count': len(rows),
        'missing_or_held_supplier_codes': flagged,
        'known_blockers': [
            'SW1 exact part, DC switching/inrush rating and physical fit are unresolved',
            'L1 startup winding-voltage qualification and land pattern are unresolved',
            'FB1 and FB2 source contains incorrect C1015; replacement not yet qualified',
            'One-pack current path, returns, protection and regeneration require review',
            'Assembly fit/hand-fit list, CPL rotation and JLC preview require review',
        ],
        'note': 'Inventory CSV is a review aid, not an authoritative assembly BOM.',
    }


def run(cmd, log):
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write('$ ' + ' '.join(map(str, cmd)) + '\n' + result.stdout + '\n')
    log.flush()
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}): {cmd[0:4]}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'review-export'])
    parser.add_argument('--output', type=Path, help='New empty output directory for review-export')
    args = parser.parse_args()
    report = audit()
    if args.action == 'audit':
        print(json.dumps(report, indent=2))
        return 0
    cli = shutil.which('kicad-cli')
    if not cli:
        raise RuntimeError('kicad-cli not found. Install KiCad 7.0.11 and retry; see docs/FAB_AUTOMATION.md')
    version = subprocess.run([cli, 'version'], capture_output=True, text=True, check=True).stdout.strip()
    if not version.startswith('7.0.11'):
        raise RuntimeError(f'Expected KiCad 7.0.11, found {version}. Do not silently change tool version.')
    if not args.output:
        raise RuntimeError('Provide --output with a new empty directory.')
    out = args.output.resolve()
    if out == ROOT or ROOT in out.parents and (out == REV or REV in out.parents):
        raise RuntimeError('Do not write inside the source revision; choose a separate output directory.')
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        raise RuntimeError(f'Output directory must be empty: {out}')
    out.mkdir(parents=True, exist_ok=True)
    gerber = out / 'gerbers-review-only'
    gerber.mkdir()
    copy = out / 'working-copy'
    shutil.copytree(PROJECT, copy)
    working_pcb = copy / PCB.name
    report['kicad_version'] = version
    report['generated_utc'] = datetime.now(timezone.utc).isoformat()
    (out / 'DO_NOT_ORDER.txt').write_text('ENGINEERING REVIEW ONLY. All holds in audit.json remain open.\nNo BOM, corrected CPL, or release ZIP is generated.\n')
    (out / 'audit.json').write_text(json.dumps(report, indent=2) + '\n')
    layers = 'F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
    with (out / 'commands.log').open('w') as log:
        run([sys.executable, str(Path(__file__).with_name('refill_drc.py')), str(working_pcb), str(out / 'drc.rpt')], log)
        run([cli, 'pcb', 'export', 'gerbers', '--layers', layers, '--subtract-soldermask', '-o', str(gerber) + '/', str(working_pcb)], log)
        run([cli, 'pcb', 'export', 'drill', '--format', 'excellon', '--excellon-separate-th', '--generate-map', '--map-format', 'gerberx2', '-o', str(gerber) + '/', str(working_pcb)], log)
        run([cli, 'pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--side', 'both', '-o', str(out / 'raw-positions-DO-NOT-ORDER.csv'), str(working_pcb)], log)
        run([cli, 'sch', 'export', 'netlist', '--format', 'kicadxml', '-o', str(out / 'schematic-netlist.xml'), str(copy / SCH.name)], log)
    print(f'Review outputs created in {out}. HOLD remains in force; inspect DRC and plots. ERC is not automated.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(1)
