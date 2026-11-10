"""Saved-board USB2 HighSpeed keepout evidence, separate from native DRC.

TI HD3SS3220§9.1.3/Fig9-3 recommends30mil to other signals and50mil to
clocks. Package escapes are clipped explicitly; exceptions are not eye tests.
"""
import argparse,hashlib,json,math,sys
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'source/generator'))
from audit_usb3_signals import load_records,closest,split_at_regions,within
ap=argparse.ArgumentParser();ap.add_argument('board',nargs='?',default=str(ROOT/'revisions/v0.7/kicad/robot_pdb.kicad_pcb'));ap.add_argument('output_dir',nargs='?',default=str(ROOT/'revisions/v0.7'));args=ap.parse_args();board=Path(args.board);b=p.LoadBoard(str(board));output=Path(args.output_dir);output.mkdir(parents=True,exist_ok=True)
own={'HUB_CHILD_DP','HUB_CHILD_DM'};clocks={'H_XI','H_XO','USB3_HUB_XI','USB3_HUB_XO'}
rows=load_records(b);hs=[dict(r,pair='HUB_CHILD') for r in rows if r['net'] in own];foreign=[dict(r,pair=None) for r in rows if r['net'] not in own|{'GND',''} and not r['net'].removeprefix('USB3_').startswith('NC_')]
regions=[]
for f in b.GetFootprints():
 if f.GetReference() not in ('U10','U9500'):continue
 cx,cy=p.ToMM(f.GetPosition());half=5 if f.GetReference()=='U10' else 6.5
 regions.append({'reference':f.GetReference(),'box_mm':[cx-half,cy-half,cx+half,cy+half],'nets':sorted({q.GetNetname() for q in f.Pads()}),'pair_groups':['HUB_CHILD'],'body_expansion_mm':3})
minimum={};exceptions={}
for r in hs:
 for s in foreign:
  if r['layer']!=s['layer']:continue
  target=1.270 if s['net'] in clocks else .762;key=(r['layer'],s['net'])
  xgap=max(0,max(min(r['a'][0],r['b'][0]),min(s['a'][0],s['b'][0]))-min(max(r['a'][0],r['b'][0]),max(s['a'][0],s['b'][0])))
  ygap=max(0,max(min(r['a'][1],r['b'][1]),min(s['a'][1],s['b'][1]))-min(max(r['a'][1],r['b'][1]),max(s['a'][1],s['b'][1])))
  lower=math.hypot(xgap,ygap)-r['width']/2-s['width']/2
  if lower>=target and (lower>target+2 or key in minimum and lower>=minimum[key]['edge_spacing_mm']):continue
  eligible=[e for e in regions if s['net'] in e['nets']]
  rs=split_at_regions(r,eligible) if lower<target and eligible else [dict(r,inside_regions=set())];ss=split_at_regions(s,eligible) if lower<target and eligible else [dict(s,inside_regions=set())]
  for one in rs:
   for two in ss:
    gap,a,c=closest(one,two)
    for pad,point in ((one,c),(two,a)):
     if 'pad_box_mm' in pad and within(point,pad['pad_box_mm']):gap=min(gap,0)
    covering=sorted(one['inside_regions']&two['inside_regions']);row={'layer':r['layer'],'nets':[r['net'],s['net']],'items':[r['id'],s['id']],'edge_spacing_mm':gap,'target_mm':target,'nearest_points_mm':[a,c],'package_exceptions':covering}
    if gap<target-1e-4 and covering:
     if key not in exceptions or gap<exceptions[key]['edge_spacing_mm']:exceptions[key]=row
    elif key not in minimum or gap<minimum[key]['edge_spacing_mm']:minimum[key]=row
#Measure the real filled positive copper, including holes and islands. For an
#inside-package HS segment, subtract the eligible box from foreign copper so
#an exempt near contact cannot hide a nonexempt violation beyond its boundary.
zone_minimum={};zone_shapes={}
def rectangle(box):
 out=p.SHAPE_POLY_SET();out.NewOutline()
 for x,y in [(box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])]:out.Append(p.FromMM(x),p.FromMM(y))
 return out
for zone in b.Zones():
 net=zone.GetNetname();layer=zone.GetLayer()
 if net in own|{'GND',''} or layer not in (p.F_Cu,p.B_Cu):continue
 shape=zone.GetFilledPolysList(layer)
 if not shape.OutlineCount():continue
 eligible=[region for region in regions if net in region['nets']]
 for r in hs:
  if r['layer']!=b.GetLayerName(layer):continue
  for record in split_at_regions(r,eligible) if eligible else [dict(r,inside_regions=set())]:
   key0=(zone.m_Uuid.AsString(),tuple(sorted(record['inside_regions'])))
   if key0 not in zone_shapes:
    clip=p.SHAPE_POLY_SET(shape)
    for region in eligible:
     if region['reference'] in record['inside_regions']:clip.BooleanSubtract(rectangle(region['box_mm']),p.SHAPE_POLY_SET.PM_STRICTLY_SIMPLE)
    zone_shapes[key0]=clip
   clip=zone_shapes[key0]
   if not clip.OutlineCount():continue
   a,c=record['a'],record['b'];near=p.VECTOR2I(0,0);segment=p.SEG(p.VECTOR2I(p.FromMM(a[0]),p.FromMM(a[1])),p.VECTOR2I(p.FromMM(c[0]),p.FromMM(c[1])))
   distance=math.sqrt(clip.SquaredDistance(segment,near))/p.FromMM(1);gap=distance-record['width']/2;key=(r['layer'],net)
   if key in zone_minimum and zone_minimum[key]['edge_spacing_mm']<=gap:continue
   q=tuple(p.ToMM(near));u=(c[0]-a[0],c[1]-a[1]);den=u[0]**2+u[1]**2;t=max(0,min(1,((q[0]-a[0])*u[0]+(q[1]-a[1])*u[1])/den)) if den else 0;one=(a[0]+u[0]*t,a[1]+u[1]*t)
   zone_minimum[key]={'layer':r['layer'],'nets':[r['net'],net],'items':[r['id'],zone.m_Uuid.AsString()],'edge_spacing_mm':gap,'target_mm':.762,'nearest_points_mm':[one,q],'kind':'actual-filled-positive-zone'}
zone_violations=[r for r in zone_minimum.values() if r['edge_spacing_mm']<r['target_mm']-1e-4]
violations=[r for r in minimum.values() if r['edge_spacing_mm']<r['target_mm']-1e-4]
escape_geometry=[]
for region in regions:
 pieces=[];totals={}
 for record in hs:
  if record['kind']!='PCB_TRACK':continue
  for part in split_at_regions(record,[region]):
   if region['reference'] not in part['inside_regions']:continue
   length=math.dist(part['a'],part['b']);key=(record['net'],record['layer']);totals[key]=totals.get(key,0)+length
   pieces.append({'item':record['id'],'net':record['net'],'layer':record['layer'],'from':part['a'],'to':part['b'],'width_mm':record['width'],'length_mm':length})
 escape_geometry.append({'reference':region['reference'],'body_expansion_mm':region['body_expansion_mm'],'exact_track_pieces':pieces,'lengths_by_leg_layer_mm':[{'net':n,'layer':ly,'length_mm':length} for (n,ly),length in totals.items()]})
report={'board':str(board),'board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),'guidance_met_outside_bounded_packages':not violations and not zone_violations,'filled_power_zone_minima':list(zone_minimum.values()),'filled_power_zone_violations':zone_violations,'violations':violations,'bounded_package_exceptions':list(exceptions.values()),'outside_package_minima':list(minimum.values()),'escape_regions':regions,'bounded_escape_copper_geometry':escape_geometry,'guidance_source':'https://www.ti.com/lit/ds/symlink/hd3ss3220.pdf §9.1.3/Fig9-3','limits':'Actual trace/via/pad-bounding-edge and filled positive-power-zone guidance screen. Unlabelled periodic signals, package/solder delays and USB electrical compliance require separate review. No connectivity is implied.'}
(output/'intercell-hs-keepout-audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'guidance_met':not violations and not zone_violations,'violations':violations,'filled_power_zone_violations':zone_violations,'bounded_package_exceptions':len(exceptions)},indent=2));raise SystemExit(0 if not violations and not zone_violations else 1)
