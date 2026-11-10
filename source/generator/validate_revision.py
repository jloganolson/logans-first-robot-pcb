"""Independent KiCad schematic-export/PCB-pad regression checks for v0.4.
Run after kicad-cli sch export netlist --format kicadxml.
This reports DRC separately; logical consistency is not a release approval.
"""
import sys, re, json, csv, math, collections, xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew
from bigboard import PARTS
out=Path(sys.argv[1]); b=pcbnew.LoadBoard(str(out/'robot_pdb.kicad_pcb'))
fp={f.GetReference():f for f in b.GetFootprints()}; spec={p['ref']:p for p in PARTS}
def padnet(r,n):
    return next(p.GetNetname() for p in fp[r].Pads() if p.GetNumber()==n)
def check(name,test):
    checks.append({'check':name,'pass':bool(test)})
checks=[]
check('PCB and circuit inventories match',set(fp)==set(spec))
check('removed external-master/spare-USB parts absent',not(set(fp)&{'J309','J409','J11','J12'}))
check('motor pass-through and fuses present',{'F1','F2','J2'}<=set(fp) and padnet('J1','2')=='VBAT' and padnet('F1','2')=='VBAT' and padnet('F1','1')=='VMOT' and padnet('J2','2')=='VMOT' and padnet('F2','2')=='VBAT' and padnet('F2','1')=='VBAT_L')
check('CH334F oscillator pins',padnet('U10','2')=='' and padnet('U10','3')=='H_XO' and padnet('U10','4')=='H_XI')
check('CH334F bus-power strap',padnet('U10','18')=='GND')
check('ILIM RC topology',padnet('C27','1')=='T_ILIM' and padnet('C27','2')=='GND' and fp['R13'].GetValue()=='180' and fp['C27'].GetValue()=='33pF 50V')
check('coherent 3.3V servo IO',all(padnet(r,n)=='V3_IO' for r,n in [('U14','5'),('U15','8'),('U16','8'),('C98','1'),('C99','1'),('R76','1'),('R77','1'),('U17','5'),('C66','1')]))
check('internal CH342 regulator remains separate',padnet('U14','6')=='S_V3' and padnet('U14','7')=='V5_USB')
check('USB codec 100mA bus-powered mode strap',padnet('R70','1')=='GND' and padnet('U12','7')=='')
check('bidirectional TVS and 100V input MOSFET selected',fp['D1'].GetValue()=='SMCJ36CA' and fp['Q1'].GetValue()=='BSC040N10NS5')
check('XL430 feedback values',fp['R401'].GetValue()=='30k' and fp['R402'].GetValue()=='2.4k')
usbt=[t for t in b.GetTracks() if t.GetNetname() in ('USB_DP','USB_DM')]
check('upstream USB pair routed on F.Cu only, no vias',usbt and all(t.GetClass()=='PCB_TRACK' and t.GetLayer()==pcbnew.F_Cu for t in usbt))
# Compare electrical groups independently exported by eeschema with actual pcbnew pads.
boardnets=collections.defaultdict(set)
for r,f in fp.items():
    for p in f.Pads():
        if p.GetNumber() and p.GetNetname():boardnets[p.GetNetname()].add((r,p.GetNumber()))
xml=ET.parse(out/'schematic_netlist.xml').getroot()
schnets={n.attrib['name']:{(e.attrib['ref'],e.attrib['pin']) for e in n.findall('node')} for n in xml.findall('./nets/net')}
# Schematic draws unused/singleton nets as NC; compare every multi-terminal net by
# membership, ignoring leading '/' added to local labels by the schematic exporter.
schnets={k.lstrip('/'):v for k,v in schnets.items() if len(v)>1}
expected={k:v for k,v in boardnets.items() if len(v)>1}
diffs={k:{'pcb':sorted(expected.get(k,set())),'schematic':sorted(schnets.get(k,set()))} for k in expected.keys()|schnets.keys() if expected.get(k,set())!=schnets.get(k,set())}
check('independent schematic/PCB multi-terminal net comparison',not diffs)
# Pin mappings must agree with source too, including no-connects; repeated pads collapse.
errors=[]
for r,f in fp.items():
    for p in f.Pads():
        if p.GetNumber() and p.GetNetname()!=spec[r]['pins'].get(p.GetNumber(),''):errors.append([r,p.GetNumber(),p.GetNetname(),spec[r]['pins'].get(p.GetNumber(),'')])
check('all PCB pad mappings match revised circuit',not errors)
if (out/'jlcpcb/BOM_JLCPCB.csv').exists():
    rows=list(csv.DictReader((out/'jlcpcb/BOM_JLCPCB.csv').open()))
    bom=[r.strip() for row in rows for r in row['Designator'].split(',')]
    cpl=[row['Designator'] for row in csv.DictReader((out/'jlcpcb/CPL_JLCPCB.csv').open())]
    fitted={p['ref'] for p in PARTS if not p['dnp']}
    check('BOM and CPL match fitted parts without duplicates',set(bom)==fitted and set(cpl)==fitted and len(bom)==len(fitted)==len(cpl))
# Rebuild human-readable data directly from the actual board.
(out/'netlist.txt').write_text('# v0.4 pad-net membership; not proof of routed copper\n\n'+''.join(f'{net} ({len(nodes)}): '+ ' '.join(r+'.'+n for r,n in sorted(nodes))+'\n' for net,nodes in sorted(boardnets.items())))
with (out/'placement.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['ref','value','footprint','side','x_mm','y_mm','rot'])
    for r,x in sorted(fp.items()):w.writerow([r,x.GetValue(),str(x.GetFPID().GetLibNickname())+":"+str(x.GetFPID().GetLibItemName()),b.GetLayerName(x.GetLayer()),*pcbnew.ToMM(x.GetPosition()),x.GetOrientationDegrees()])
cnts=collections.Counter((b.GetLayerName(t.GetLayer()),round(pcbnew.ToMM(t.GetWidth()),4)) for t in b.GetTracks() if t.GetClass()!='PCB_VIA')
(out/'copper_stats.txt').write_text('Track segment count by (layer,width mm):\n'+''.join(f'{k}: {v}\n' for k,v in sorted(cnts.items()))+f'Vias: {sum(t.GetClass()=="PCB_VIA" for t in b.GetTracks())}\nZones: {len(b.Zones())}\n')
drc=(out/'drc.rpt').read_text();drc_counts=dict(collections.Counter(re.findall(r'^\[([^]]+)\]',drc,re.M)))
summary={'status':'PASS' if all(x['pass'] for x in checks) else 'FAIL','release_status':'HOLD: engineering review only', 'checks':checks,'net_differences':diffs,'pad_errors':errors,'footprints':len(fp),'fitted_parts':sum(not p['dnp'] for p in PARTS),'multi_terminal_nets_compared':len(expected),'drc_counts':drc_counts,'xl430_nominal_v':.8*(1+30/2.4),'xl430_worst_high_v':.808*(1+30*1.01/(2.4*.99)),'ilim_rc_ns':180*33e-12*1e9,'input_reverse_fet_stress_v':2*33.6,'nominal_two_pack_wh':2*28.8*3}
(out/'revision_validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
raise SystemExit(0 if summary['status']=='PASS' else 1)
