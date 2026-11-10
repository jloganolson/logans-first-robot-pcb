#!/usr/bin/env python3
"""Read-only, snapshot-bound v0.9 integration audit; NEVER fabrication release.

Run with with_kicad.sh. Only this audit's output directory is written. Native
DRC runs in a fresh process against copied reviewed project settings; no board
refill/save or project mutation occurs. A live edit during sampling holds the
result. Logical agreement and native DRC do not qualify USB or electrical behavior.
"""
import argparse, collections, hashlib, importlib, json, re, shutil, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p
from audit_factory_drills import audit as drill_audit

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/generator'))
HOST_VBUS_ALLOWED={('J10',n) for n in ('A4','A9','B4','B9')} | {
    ('U11','5'),('C67','1'),('R9909','1'),('R9903','1')}
REQUIRED_PAIRS={('USB_DP','USB_DM'),('HUB_UP_DP','HUB_UP_DM'),
                ('P4_DP','P4_DM')}
ELECTRICAL_HOLDS=[
    'Original fused battery-voltage passthrough: verify existing controller/BMS regeneration settings, harness, pack matching and stop-before-OFF behavior.',
    'Qualify Thor and other regulator startup, loaded voltage/ripple, current limits, loop behavior and temperature with dummy loads before connecting equipment.',
    'Verify actual USB host-off/board-off behavior, both connector orientations, all three functions and power/fault recovery on hardware.',
    'Program the PWM MCU; verify explicit arming, reset/disconnect/watchdog/timeout and actual servo response before connecting a mechanism.',
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None

def json_read(path):
    try:return json.loads(path.read_text())
    except (OSError,ValueError):return None

def netmap_rows(rows):
    result=collections.defaultdict(set)
    for ref,pins in rows:
        for pin,net in pins.items():
            if net:result[net].add((ref,pin))
    return dict(result)

def differences(a,b):
    return {net:{'expected':sorted(a.get(net,set())),'actual':sorted(b.get(net,set()))}
            for net in sorted(a.keys()|b.keys()) if a.get(net,set())!=b.get(net,set())}

def nontrivial(nets):return {k:v for k,v in nets.items() if len(v)>1}

def run(board,out):
    out.mkdir(parents=True,exist_ok=True)
    watched=[board,board.with_suffix('.kicad_sch'),board.with_suffix('.kicad_pro'),
             board.with_suffix('.kicad_dru'),board.parent.parent/'composition.json',
             board.parent.parent/'integration-routing.json',
             Path(__file__),ROOT/'source/generator/rev09.py',
             ROOT/'source/generator/build_v09.py',ROOT/'source/generator/route_v09.py',
             ROOT/'source/generator/label_v09.py',
             ROOT/'source/generator/route_v07.py',ROOT/'source/generator/route_v09_usb.py',ROOT/'source/generator/usb2_control.py',
             ROOT/'source/generator/robot_pwm.py',ROOT/'source/generator/robot_io.py',
             ROOT/'source/fabrication/audit_v09_usb.py',out/'usb-channel-audit.json',
             ROOT/'revisions/v0.9/prototype-usb-fs-exceptions.json',
             ROOT/'revisions/v0.9/prototype-usb-legacy-review.json',
             ROOT/'source/generator/service_off_v09.py',ROOT/'source/generator/rev06.py']
    before={str(f):sha(f) for f in watched}
    rev=importlib.import_module('rev09')
    inventory=rev.PARTS;spec={s['ref']:s for s in inventory}
    checks=[]
    def check(label,passed,detail=None):
        row=dict(check=label,pass_=bool(passed))
        if detail is not None:row['detail']=detail
        checks.append(row)
    snapshot=out/'audit-input';snapshot.mkdir(exist_ok=True)
    for suffix in ('.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_dru'):
        src=board.with_suffix(suffix);dst=snapshot/src.name
        if src.exists():shutil.copyfile(src,dst)
        elif dst.exists():dst.unlink()
    for name in ('fp-lib-table','sym-lib-table','pdb.kicad_sym'):
        src=board.parent/name
        if src.exists():shutil.copyfile(src,snapshot/name)
    local=board.parent/'Robot_PDB.pretty'
    if local.exists():shutil.copytree(local,snapshot/local.name,dirs_exist_ok=True)
    copied=snapshot/board.name
    expected=netmap_rows((s['ref'],s['pins']) for s in inventory)
    b=p.LoadBoard(str(copied));footprints=list(b.GetFootprints());fps={f.GetReference():f for f in footprints}
    check('inventory reference uniqueness',len(spec)==len(inventory))
    check('PCB reference uniqueness',len(fps)==len(footprints))
    check('PCB references exactly match inventory',set(fps)==set(spec),
          dict(missing=sorted(set(spec)-set(fps)),extra=sorted(set(fps)-set(spec))))
    errors=[];physical_rows=[]
    for ref,f in fps.items():
        if ref not in spec:
            physical_rows.append((ref,{q.GetNumber():q.GetNetname() for q in f.Pads() if q.GetNumber()}))
            continue
        s=spec[ref];actualfp=f.GetFPID().GetUniStringLibId()
        if str(actualfp)!=s['fp']:errors.append([ref,'footprint',str(actualfp),s['fp']])
        if f.GetValue()!=s['value']:errors.append([ref,'value',f.GetValue(),s['value']])
        pads={}
        for pad in f.Pads():
            num=pad.GetNumber()
            if not num:continue
            actual=pad.GetNetname();wanted=s['pins'].get(num,'')
            if actual!=wanted:errors.append([ref,'pad',num,actual,wanted])
            if num in pads and pads[num]!=actual:errors.append([ref,'inconsistent duplicated pad',num])
            pads[num]=actual
        for absent in s['pins'].keys()-pads.keys():errors.append([ref,'missing numbered pad',absent])
        physical_rows.append((ref,pads))
    physical=netmap_rows(physical_rows)
    check('exact PCB values, footprints and all numbered pad nets match inventory',not errors)
    pcb_net_errors=differences(nontrivial(expected),nontrivial(physical))
    check('nontrivial PCB nets match inventory',not pcb_net_errors)
    xml=out/'schematic-netlist.xml'
    export=subprocess.run(['kicad-cli','sch','export','netlist','--format','kicadxml','-o',str(xml),
                           str(copied.with_suffix('.kicad_sch'))],capture_output=True,text=True)
    (out/'schematic-export.log').write_text(export.stdout+export.stderr)
    check('actual schematic XML export succeeds',export.returncode==0)
    schematic={};sch_errors=[];sch_net_errors={}
    if export.returncode==0:
        tree=ET.parse(xml)
        component_rows=tree.findall('.//components/comp')
        comps={q.attrib['ref']:q for q in component_rows}
        check('schematic reference uniqueness',len(comps)==len(component_rows))
        check('schematic references exactly match inventory',set(comps)==set(spec),
              dict(missing=sorted(set(spec)-set(comps)),extra=sorted(set(comps)-set(spec))))
        for ref,q in comps.items():
            if ref not in spec:continue
            for field in ('value','footprint'):
                actual=q.findtext(field) or '';wanted=spec[ref]['fp' if field=='footprint' else field]
                if actual!=wanted:sch_errors.append([ref,field,actual,wanted])
        check('exact schematic values and footprint identifiers match inventory',not sch_errors)
        schematic={q.attrib['name'].lstrip('/'):{(n.attrib['ref'],n.attrib['pin']) for n in q.findall('node')}
                   for q in tree.findall('.//nets/net')}
        sch_net_errors=differences(nontrivial(expected),nontrivial(schematic))
        check('independently exported nontrivial schematic nets match inventory and PCB',
              not sch_net_errors and not differences(nontrivial(schematic),nontrivial(physical)))
    report_path=out/'native-drc.rpt'
    if report_path.exists():report_path.unlink()
    script=('import pcbnew as p; b=p.LoadBoard('+repr(str(copied))+'); '
            'p.WriteDRCReport(b,'+repr(str(report_path))+',p.EDA_UNITS_MILLIMETRES,True)')
    drc=subprocess.run([sys.executable,'-c',script],capture_output=True,text=True)
    (out/'native-drc.log').write_text(drc.stdout+drc.stderr)
    check('native DRC runs in a fresh process',drc.returncode==0 and report_path.exists())
    text=report_path.read_text() if report_path.exists() else ''
    entries=[]
    for match in re.finditer(r'^\[([^]]+)\]: (.*?)(?=^\[|^\*\*|\Z)',text,re.M|re.S):
        block=match.group(0).strip();severity=re.search(r'Severity: (\w+)',block)
        entries.append(dict(rule=match.group(1),severity=severity.group(1) if severity else 'unknown',text=block))
    opened=[q for q in entries if q['rule']=='unconnected_items']
    physical_errors=[q for q in entries if q['severity']=='error' and q['rule']!='unconnected_items']
    check('native physical DRC errors are zero',not physical_errors)
    check('native unconnected items are zero',not opened and '** Found 0 unconnected pads **' in text)
    profile=json_read(copied.with_suffix('.kicad_pro')) or {}
    settings=profile.get('board',{}).get('design_settings',{})
    severities=settings.get('rule_severities',{})
    required_rules=('clearance','copper_edge_clearance','hole_clearance','unconnected_items')
    check('critical native rules remain errors and no exclusions hide results',
          all(severities.get(k)=='error' for k in required_rules) and not settings.get('drc_exclusions'),
          {k:severities.get(k) for k in required_rules})
    drill=drill_audit(copied)
    (out/'factory-drills.json').write_text(json.dumps(drill,indent=2)+'\n')
    check('independent nominal factory drill screen passes',drill['status']=='PASS')
    vbus=dict(expected=sorted(HOST_VBUS_ALLOWED),physical=sorted(physical.get('VBUS_IN',set())),
              schematic=sorted(schematic.get('VBUS_IN',set())))
    check('host VBUS connects only to connector, ESD, bypass, sense input and pulldown',
          expected.get('VBUS_IN',set())==physical.get('VBUS_IN',set())==schematic.get('VBUS_IN',set())==HOST_VBUS_ALLOWED)
    obsolete_values=[(r,f.GetValue()) for r,f in fps.items() if re.search(r'USB5744|HD3SS3220|TPS25810',f.GetValue(),re.I)]
    usednets={q.GetNetname() for f in b.GetFootprints() for q in f.Pads()} | {q.GetNetname() for q in b.GetTracks()} | {q.GetNetname() for q in b.Zones()}
    obsolete_nets=sorted(n for n in usednets if n.startswith('USB3_') or n in ('+5_USB_RAW','USB_POWER_VIN','HUB_CHILD_DP','HUB_CHILD_DM'))
    obsolete_sources=sorted({s.get('source_cell') for s in inventory if s.get('source_cell') in ('usb','usb_power')})
    check('obsolete USB3 parts, nets and source cells are absent',not obsolete_values and not obsolete_nets and not obsolete_sources)
    comp=json_read(board.parent.parent/'composition.json');routing=json_read(board.parent.parent/'integration-routing.json')
    provenance=[]
    def provenance_check(label,ok):provenance.append(dict(check=label,pass_=bool(ok)))
    provenance_check('composition manifest exists',comp is not None)
    if comp:
        provenance_check('composition uses current integration inventory',comp.get('inventory_sha256')==sha(ROOT/'source/generator/rev09.py'))
        provenance_check('composition uses current builder',comp.get('generator_sha256')==sha(ROOT/'source/generator/build_v09.py'))
        provenance_check('functional legends are present and current',comp.get('functional_labels',{}).get('status')=='PASS'
                         and bool(comp.get('functional_labels',{}).get('placed'))
                         and comp.get('label_generator_sha256')==sha(ROOT/'source/generator/label_v09.py'))
        provenance_check('composition part count matches',comp.get('components')==len(spec))
        provenance_check('composition includes every expected source cell',set(comp.get('source_files',{}))==set(rev.CELLS))
        for cell,c in rev.CELLS.items():
            source=comp.get('source_files',{}).get(cell,{})
            path=ROOT/c['board'];watched.append(path);before[str(path)]=sha(path)
            provenance_check(cell+' source hash and canonical path match',source.get('path')==c['board'] and source.get('sha256')==sha(path))
    boardhash=sha(copied)
    provenance_check('snapshot PCB matches captured live input',boardhash==before[str(board)])
    if comp and boardhash==comp.get('board_sha256'):
        provenance_check('current board is the composed input',True)
    else:
        provenance_check('routing manifest exists for changed composition',routing is not None)
    if comp and routing:
        provenance_check('router consumed exactly the composition',routing.get('source_sha256')==comp.get('board_sha256'))
        provenance_check('router report binds this PCB',routing.get('board_sha256')==boardhash)
        provenance_check('router report matches current router source',routing.get('generator_sha256')==sha(ROOT/'source/generator/route_v09.py'))
        provenance_check('router geometry library hash matches',routing.get('geometry_library_sha256')==sha(ROOT/'source/generator/route_v07.py'))
        route_code=routing.get('route_input_code_sha256',{})
        provenance_check('router code snapshot remains current',bool(route_code) and all(sha(ROOT/k)==v for k,v in route_code.items()))
    check('source composition and route provenance are current',all(q['pass_'] for q in provenance))
    pairs=routing.get('pairs',[]) if routing else []
    reported_pairs={tuple(q.get('pair',())) for q in pairs if q.get('routed') and not q.get('rolled_back')}
    check('router reports all three required pair channels complete',REQUIRED_PAIRS<=reported_pairs)
    failed_routes=[q for q in routing.get('ordinary_routes',[]) if q.get('routed') is False] if routing else []
    check('router reports no failed ordinary routes',routing is not None and not failed_routes)
    # Consume the separate saved-copper analyser only when its PCB and complete
    # source hashes still match. Router success is not independent validation.
    usb=json_read(out/'usb-channel-audit.json') or {}
    usb_sources=usb.get('source_sha256',{})
    usb_current=bool(usb_sources) and all(sha(ROOT/k)==v for k,v in usb_sources.items())
    usb_ok=(usb.get('board_sha256')==boardhash and usb_current
            and not usb.get('inputs_changed_during_run') and not usb.get('review_holds')
            and usb.get('status') in ('GEOMETRY_SCREEN_COMPLETE_BENCH_QUALIFICATION_REQUIRED','GEOMETRY_SCREEN_COMPLETE_WITH_REVIEWED_LEGACY_PROTOTYPE_DEVIATIONS'))
    check('independent USB screen is current with no unreviewed holds; any legacy prototype deviations remain explicit',usb_ok,
          dict(report_status=usb.get('status','MISSING'),board_matches=usb.get('board_sha256')==boardhash,
               sources_current=usb_current,review_holds=usb.get('review_holds',[])))
    # Literal original passthrough contract; no wheel-specific power or CAN.
    pass_contract={('F1','1'):'VMOT',('F1','2'):'VBAT',('J2','1'):'GND',('J2','2'):'VMOT',
                   ('J5','1'):'PACK_A_POS',('J5','2'):'VBAT',('J5','3'):'PACK_B_POS',('J5','4'):'VBAT',
                   ('U10','7'):'NC_HUB_P3_DM',('U10','8'):'NC_HUB_P3_DP'}
    pass_errors=[dict(ref=ref,pin=pin,expected_net=net) for (ref,pin),net in pass_contract.items()
                 if (ref,pin) not in physical.get(net,set())]
    removed_nets=sorted(n for n in usednets if n in ('P3_DP','P3_DM','CAN_H','CAN_L','MOTOR_BUS','MOTOR_VIN','MOTOR_FUSED_INPUT') or n.startswith('M_') or 'CAN' in n)
    removed_parts=sorted(r for r in fps if r in ('U7001','U7004','U7005','U7008','J7007','J9927','U9910','Q9910','C9910','C9911') or re.match(r'^[A-Za-z]+6[0-9]{3}$',r))
    check('original fused battery-voltage motor passthrough is restored and replacement-wheel circuitry absent',
          not pass_errors and physical.get('VMOT')=={('F1','1'),('J2','2')} and not removed_nets and not removed_parts,
          dict(pin_contract_errors=pass_errors,removed_wheel_nets_present=removed_nets,removed_wheel_parts_present=removed_parts,
               note='Fused passthrough only; existing external controllers retain control/braking responsibilities.'))
    after={str(f):sha(f) for f in watched}
    changed=[name for name,value in before.items() if after.get(name)!=value]
    check('audited inputs remain unchanged during audit',not changed,changed)
    logical_labels={
        'inventory reference uniqueness','PCB reference uniqueness','PCB references exactly match inventory',
        'exact PCB values, footprints and all numbered pad nets match inventory',
        'nontrivial PCB nets match inventory','actual schematic XML export succeeds',
        'schematic reference uniqueness','schematic references exactly match inventory','exact schematic values and footprint identifiers match inventory',
        'independently exported nontrivial schematic nets match inventory and PCB'}
    screen_ok=all(q['pass_'] for q in checks)
    legacy_reviewed=bool(usb.get('legacy_prototype_disposition',{}).get('applied'))
    screen_status='PROTOTYPE_LAYOUT_SCREEN_COMPLETE_WITH_REVIEWED_LEGACY_USB_DEVIATIONS' if legacy_reviewed else 'PROTOTYPE_LAYOUT_SCREEN_COMPLETE_BENCH_QUALIFICATION_REQUIRED'
    result=dict(status=screen_status if screen_ok else 'HELD',
        disposition='Prototype layout screen only; review assembly/manufacturing before purchase and qualify hardware before robot operation.',
        logical_status='PASS' if all(q['pass_'] for q in checks if q['check'] in logical_labels) else 'FAIL',
        board=str(board),board_sha256=boardhash,inventory_parts=len(inventory),physical_parts=len(fps),
        nontrivial_nets=len(nontrivial(physical)),native_physical_errors=len(physical_errors),
        native_unconnected_items=len(opened),native_warnings=sum(q['severity']=='warning' for q in entries),
        checks=checks,pad_value_footprint_errors=errors,schematic_component_errors=sch_errors,
        pcb_net_mismatches=pcb_net_errors,schematic_net_mismatches=sch_net_errors,
        native_physical_error_details=physical_errors,native_open_details=opened,
        native_rule_counts=dict(collections.Counter(q['rule'] for q in entries)),
        factory_drills=dict(status=drill['status'],holes=drill['holes'],issues=drill['issues']),
        host_vbus=vbus,obsolete_usb3=dict(parts=obsolete_values,nets=obsolete_nets,sources=obsolete_sources),
        provenance=provenance,routing_screen=dict(reported_successful_pairs=sorted(reported_pairs),
          required_pairs=sorted(REQUIRED_PAIRS),failed_ordinary_routes=failed_routes,
          independent_channel_validation=usb.get('status','MISSING')),
        reviewed_legacy_USB_deviations=usb.get('legacy_prototype_disposition',{}),
        electrical_release_holds=ELECTRICAL_HOLDS+(['Retained source FullSpeed audio/Dynamixel reference/return/spacing departures require bench qualification; external data adapter, rework or board spin may be needed. This is not a measured USB pass.'] if legacy_reviewed else []),live_inputs_changed_during_audit=changed,
        audited_input_sha256=before,audit_generator_sha256=sha(Path(__file__)),
        limitations=['This audit does not refill/save the board; fill currency requires upstream provenance and final regeneration.',
                    'Passive custom schematic symbols do not provide comprehensive ERC.',
                    'Host VBUS whitelist is logical; physical short clearance is checked separately by native DRC.',
                    'Cell checks alone do not qualify the integrated board. A clear layout screen is not a completed manufacturing/assembly review or electrical bench qualification.'])
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','logical_status','inventory_parts','physical_parts','native_physical_errors','native_unconnected_items','native_warnings')},indent=2))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--board',type=Path,default=ROOT/'revisions/v0.9/kicad/robot_pdb.kicad_pcb')
    ap.add_argument('--output',type=Path,default=ROOT/'outputs/v09-order-preparation')
    args=ap.parse_args();result=run(args.board.resolve(),args.output.resolve())
    raise SystemExit(result['status']=='HELD')
