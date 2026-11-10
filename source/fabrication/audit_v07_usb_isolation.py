"""Inspect actual intercell USB2 copper against USB3 copper on the saved board.

Checks TI's0.762mm SS-to-other-signal guidance outside the same bounded hub
package escape used by the USB-cell audit. Connectivity and USB eye compliance
remain independent; this script never edits the PCB or manufacturing rules.
"""
import argparse,hashlib,json,sys
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/generator'))
from audit_usb3_signals import load_records,pair_key,closest,split_at_regions,within

ap=argparse.ArgumentParser();ap.add_argument('board',nargs='?',default=str(ROOT/'revisions/v0.7/kicad/robot_pdb.kicad_pcb'));ap.add_argument('output_dir',nargs='?',default=str(ROOT/'revisions/v0.7'));args=ap.parse_args()
board=Path(args.board);b=p.LoadBoard(str(board));output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
net_pair={net:name for name,nets in [('P3 FullSpeed',('P3_DP','P3_DM')),('P4 FullSpeed',('P4_DP','P4_DM')),('Child HighSpeed',('HUB_CHILD_DP','HUB_CHILD_DM'))] for net in nets}
records=load_records(b);ss=[];usb=[]
for row in records:
 row['pair']=pair_key(row['net'].removeprefix('USB3_'))
 if row['pair']:ss.append(row)
 elif row['net'] in net_pair:usb.append(row)
hub=next(f for f in b.GetFootprints() if f.GetReference()=='U9500');cx,cy=p.ToMM(hub.GetPosition());nets={pad.GetNetname() for pad in hub.Pads()}
regions=[{'reference':'U9500','body_expansion_mm':3,'box_mm':[cx-6.5,cy-6.5,cx+6.5,cy+6.5],'nets':sorted(nets),'pair_groups':sorted({pair_key(n.removeprefix('USB3_')) for n in nets if pair_key(n.removeprefix('USB3_'))})}]
minimum={};exceptions={};violations=[];target=.762
for r in ss:
 for s in usb:
  if r['layer']!=s['layer']:continue
  xgap=max(0,max(min(r['a'][0],r['b'][0]),min(s['a'][0],s['b'][0]))-min(max(r['a'][0],r['b'][0]),max(s['a'][0],s['b'][0])))
  ygap=max(0,max(min(r['a'][1],r['b'][1]),min(s['a'][1],s['b'][1]))-min(max(r['a'][1],r['b'][1]),max(s['a'][1],s['b'][1])))
  lower=(xgap*xgap+ygap*ygap)**.5-r['width']/2-s['width']/2;key=(r['layer'],r['pair'],net_pair[s['net']])
  if lower>=target and key in minimum and lower>=minimum[key]['edge_spacing_mm']:continue
  eligible=[e for e in regions if r['pair'] in e['pair_groups'] and s['net'] in e['nets']]
  rr=split_at_regions(r,eligible) if eligible and lower<target else [dict(r,inside_regions=set())]
  ss0=split_at_regions(s,eligible) if eligible and lower<target else [dict(s,inside_regions=set())]
  for one in rr:
   for two in ss0:
    gap,a,c=closest(one,two)
    for pad,point in ((one,c),(two,a)):
     if 'pad_box_mm' in pad and within(point,pad['pad_box_mm']):gap=min(gap,0)
    covering=sorted(one['inside_regions']&two['inside_regions'])
    row={'layer':r['layer'],'SS_channel':r['pair'],'USB2_channel':net_pair[s['net']],'nets':[r['net'],s['net']],'items':[r['id'],s['id']],'edge_spacing_mm':gap,'target_mm':target,'nearest_points_mm':[a,c],'package_exceptions':covering}
    if gap<target-1e-4 and covering:
     if key not in exceptions or gap<exceptions[key]['edge_spacing_mm']:exceptions[key]=row
    elif key not in minimum or gap<minimum[key]['edge_spacing_mm']:minimum[key]=row
for row in minimum.values():
 if row['edge_spacing_mm']<target-1e-4:violations.append(row)
report={'board':str(board),'board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),'pass':not violations,'target_mm':target,'outside_package_minima':list(minimum.values()),'violations':violations,'bounded_package_exceptions':list(exceptions.values()),'escape_regions':regions,'limits':'Actual saved F/B trace,via and conservative pad-bounding-edge geometry. An isolation PASS is not connectivity, controlled impedance, reference continuity, or USB electrical compliance.'}
(output/'intercell-usb-isolation-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'pass':report['pass'],'violations':violations,'bounded_package_exceptions':len(exceptions)},indent=2))
raise SystemExit(0 if report['pass'] else 1)
