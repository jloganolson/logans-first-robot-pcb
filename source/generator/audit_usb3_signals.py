"""Independent saved-copper USB3/USB2 high-speed screen; never changes a PCB.

Run with KiCadPython after power/ordinary completion. Reports FAIL until all
checks pass; native clearance alone cannot produce a signal-integrity PASS.
"""
import argparse,collections,datetime,hashlib,json,math,re,sys
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
xy=lambda v:tuple(p.ToMM(v.GetPosition() if hasattr(v,'GetPosition') else v))
def pair_key(net):
 s=net.replace('_AC','').replace('_CONN','')
 return s[:-1] if re.fullmatch(r'(UP|CAM|MIC)_(TX|RX)[12]?[PN]',s) else None

def hs_key(net):
 """Spacing channel identity; pair_key deliberately remains SS-only.

 USB2 DP/DM channels need the TI high-speed isolation screen too, without
 inheriting USB3-only path/skew/reference rules elsewhere in this auditor.
 """
 ss=pair_key(net)
 if ss:return ss
 return 'USB2_'+net[:-3] if re.fullmatch(r'(UP|CAM|MIC|HUB_CHILD|BMS_USB)_D[PM]',net) else None

def spacing_rule(r,s):
 """TI high-speed layout targets, in millimetres, outside package escapes."""
 ss_r=bool(pair_key(r['net']));ss_s=bool(pair_key(s['net']))
 if s['pair']:
  if ss_r and ss_s:return 1.020,'SS_pair_to_pair'
  return .762,'USB2_to_SS' if ss_r or ss_s else 'USB2_pair_to_pair'
 prefix='SS' if ss_r else 'USB2'
 return (1.270,prefix+'_to_clock') if s['net'] in ('HUB_XI','HUB_XO') else (.762,prefix+'_to_other_signal_or_power')

def pointseg(q,a,b):
 d=(b[0]-a[0],b[1]-a[1]);den=sum(v*v for v in d);t=max(0,min(1,sum((q[i]-a[i])*d[i] for i in (0,1))/den)) if den else 0
 out=tuple(a[i]+t*d[i] for i in (0,1));return math.dist(q,out),q,out

def closest(r,s):
 a,b=r['a'],r['b'];c,d=s['a'],s['b'];u=(b[0]-a[0],b[1]-a[1]);v=(d[0]-c[0],d[1]-c[1]);den=u[0]*v[1]-u[1]*v[0]
 if abs(den)>1e-12:
  t=((c[0]-a[0])*v[1]-(c[1]-a[1])*v[0])/den;z=((c[0]-a[0])*u[1]-(c[1]-a[1])*u[0])/den
  if 0<=t<=1 and 0<=z<=1:
   q=tuple(a[i]+t*u[i] for i in (0,1));return -r['width']/2-s['width']/2,q,q
 vals=[pointseg(a,c,d),pointseg(b,c,d)]+[(q[0],q[2],q[1]) for q in (pointseg(c,a,b),pointseg(d,a,b))]
 gap,one,two=min(vals,key=lambda q:q[0]);return gap-r['width']/2-s['width']/2,one,two

def within(q,box):return box[0]-1e-9<=q[0]<=box[2]+1e-9 and box[1]-1e-9<=q[1]<=box[3]+1e-9

def region_covers(region,one,two,r,s):
 #An escape region applies only to signals actually belonging to that package.
 groups=region['pair_groups'];nets=region['nets']
 return within(one,region['box_mm']) and within(two,region['box_mm']) and r['pair'] in groups and (s['pair'] in groups if s['pair'] else s['net'] in nets)

def split_at_regions(record,regions):
 """Clip at every escape boundary so an exempt minimum cannot mask a
 second, nonexempt violation farther along the same copper segment.
 """
 a,b=record['a'],record['b'];cuts={0.,1.}
 for region in regions:
  box=region['box_mm']
  for axis,limits in ((0,(box[0],box[2])),(1,(box[1],box[3]))):
   delta=b[axis]-a[axis]
   if abs(delta)<1e-12:continue
   for edge in limits:
    t=(edge-a[axis])/delta
    if 0<t<1:cuts.add(t)
 out=[];cuts=sorted(cuts)
 for lo,hi in zip(cuts,cuts[1:]):
  q=dict(record);q['a']=tuple(a[k]+lo*(b[k]-a[k]) for k in (0,1));q['b']=tuple(a[k]+hi*(b[k]-a[k]) for k in (0,1))
  mid=tuple((q['a'][k]+q['b'][k])/2 for k in (0,1));q['inside_regions']={r['reference'] for r in regions if within(mid,r['box_mm'])};out.append(q)
 return out

def load_records(board):
 records=[]
 for t in board.GetTracks():
  net=t.GetNetname();layers=[t.GetLayer()] if t.GetClass()!='PCB_VIA' else [p.F_Cu,p.B_Cu]
  for layer in layers:
   if layer not in (p.F_Cu,p.B_Cu):continue
   records.append(dict(id=t.m_Uuid.AsString(),net=net,pair=hs_key(net),layer=board.GetLayerName(layer),a=xy(t.GetStart()),b=xy(t.GetEnd()),width=p.ToMM(t.GetWidth()),kind=t.GetClass()))
 #Axis-aligned pad edges are conservative for rounded/chamfered corners.
 #All cell placement rotations are multiples of90degrees.
 for f in board.GetFootprints():
  for pad in f.Pads():
   net=pad.GetNetname()
   if not net or net.startswith('NC_'):continue
   bb=pad.GetBoundingBox();x0,y0,x1,y1=[p.ToMM(v) for v in (bb.GetLeft(),bb.GetTop(),bb.GetRight(),bb.GetBottom())]
   edges=[((x0,y0),(x1,y0)),((x1,y0),(x1,y1)),((x1,y1),(x0,y1)),((x0,y1),(x0,y0))]
   for layer in (p.F_Cu,p.B_Cu):
    if not pad.IsOnLayer(layer):continue
    for i,(a,b) in enumerate(edges):records.append(dict(id=f.GetReference()+'.'+pad.GetNumber()+f':edge{i}',net=net,pair=hs_key(net),layer=board.GetLayerName(layer),a=a,b=b,width=0,kind='pad-bounding-edge',pad_box_mm=[x0,y0,x1,y1]))
 return records

def package_regions(board):
 out=[]
 for f in board.GetFootprints():
  ref=f.GetReference();cx,cy=xy(f.GetPosition());angle=math.radians(f.GetOrientationDegrees());w=h=margin=None
  #The staggered USB2 via field reaches1.47mm from pad centres, and the
  #fine SS launch needs a further matched pitch/heading transition before
  #the isolated uniform spine. A2mm body box cut through that real launch
  #field.3mm bounds this package escape; it never covers the AC-cap rows.
  if ref=='U500':w=h=7;margin=3
  elif ref in ('U501','U503'):w,h=2.5,4.5;margin=3
  elif ref in [f'U{x}' for x in list(range(520,525))+list(range(530,535))]:w,h=1,.8;margin=1.5
  if w:
   ex=abs(math.cos(angle))*w/2+abs(math.sin(angle))*h/2;ey=abs(math.sin(angle))*w/2+abs(math.cos(angle))*h/2;box=[cx-ex-margin,cy-ey-margin,cx+ex+margin,cy+ey+margin]
  elif ref in ('J500','J501','J502'):
   pads=[pad for pad in f.Pads() if pad.GetNumber() not in ('S1','10')];pts=[xy(pad.GetPosition()) for pad in pads];box=[min(q[0] for q in pts)-2,min(q[1] for q in pts)-2,max(q[0] for q in pts)+2,max(q[1] for q in pts)+2];margin=2
  else:continue
  nets=sorted({pad.GetNetname() for pad in f.Pads() if pad.GetNetname()});groups=sorted({hs_key(n) for n in nets if hs_key(n)})
  out.append(dict(reference=ref,box_mm=box,body_expansion_mm=margin,nets=nets,pair_groups=groups,reason='Bounded actual-package escape: pad pitch/connector geometry prevents full inter-channel isolation locally. Exact manufacturing clearance and actual subtarget distance remain separately reported.'))
 return out

def spacing(records,regions):
 minima={};exceptions={}
 for i,r in enumerate(records):
  if not r['pair']:continue
  for j,s in enumerate(records):
   if r['layer']!=s['layer'] or r['net']==s['net'] or r['pair']==s['pair'] or (s['pair'] and i>=j):continue
   if not s['pair'] and (not s['net'] or s['net']=='GND' or s['net'].startswith('NC_')):continue
   target,category=spacing_rule(r,s)
   names=tuple(sorted((r['pair'],s['pair']))) if s['pair'] else (r['pair'],s['net']);key=(r['layer'],category,*names)
   xgap=max(0,max(min(r['a'][0],r['b'][0]),min(s['a'][0],s['b'][0]))-min(max(r['a'][0],r['b'][0]),max(s['a'][0],s['b'][0])))
   ygap=max(0,max(min(r['a'][1],r['b'][1]),min(s['a'][1],s['b'][1]))-min(max(r['a'][1],r['b'][1]),max(s['a'][1],s['b'][1])))
   lower=math.hypot(xgap,ygap)-r['width']/2-s['width']/2
   if lower>=target and key in minima and lower>=minima[key]['edge_spacing_mm']:continue
   eligible=[e for e in regions if r['pair'] in e['pair_groups'] and (s['pair'] in e['pair_groups'] if s['pair'] else s['net'] in e['nets'])]
   #Only pairs capable of approaching their target need boundary splitting.
   parts_r=split_at_regions(r,eligible) if lower<target and eligible else [dict(r,inside_regions=set())]
   parts_s=split_at_regions(s,eligible) if lower<target and eligible else [dict(s,inside_regions=set())]
   for rr in parts_r:
    for ss in parts_s:
     gap,a,b=closest(rr,ss)
     #A segment through a rectangular pad has negative/colliding clearance,
     #not the distance to its boundary on the opposite side of the pad.
     for pad,point in ((rr,b),(ss,a)):
      if 'pad_box_mm' in pad and within(point,pad['pad_box_mm']):gap=min(gap,0)
     covering=sorted(rr['inside_regions'] & ss['inside_regions'])
     row=dict(layer=r['layer'],category=category,channels=names,nets=[r['net'],s['net']],edge_spacing_mm=gap,target_mm=target,nearest_centerline_points_mm=[a,b],items=[r['id'],s['id']],package_exceptions=covering)
     if gap<target-1e-4 and covering:
      ek=(*key,tuple(covering))
      if ek not in exceptions or gap<exceptions[ek]['edge_spacing_mm']:exceptions[ek]=row
     elif key not in minima or gap<minima[key]['edge_spacing_mm']:minima[key]=row
 return list(minima.values()),list(exceptions.values())

def net_connectivity(board,nets):
 cn=board.GetConnectivity();cn.Build(board);out=[]
 for net in sorted(nets):
  pads=[pad for f in board.GetFootprints() for pad in f.Pads() if pad.GetNetname()==net]
  if len(pads)<2:continue
  todo=[pads[0]];seen=set()
  while todo:
   item=todo.pop();key=item.m_Uuid.AsString()
   if key in seen:continue
   seen.add(key);todo.extend(q for q in list(cn.GetConnectedPads(item))+list(cn.GetConnectedTracks(item)) if q.GetNetname()==net)
  missing=[pad.GetParent().GetReference()+'.'+pad.GetNumber() for pad in pads if pad.m_Uuid.AsString() not in seen]
  out.append(dict(net=net,connected=not missing,missing_pads=missing))
 return out

def reference_audit(board):
 zones={L:[z for z in board.Zones() if z.GetNetname()=='GND' and z.IsOnLayer(L) and z.HasFilledPolysForLayer(L)] for L in (p.In1_Cu,p.In2_Cu)}
 vias=[t for t in board.GetTracks() if t.GetClass()=='PCB_VIA' and pair_key(t.GetNetname())];signal_holes=[q for f in board.GetFootprints() for q in f.Pads() if q.GetDrillSize().x and pair_key(q.GetNetname())];ground=[t for t in board.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND'];fail=[];samples=0;excluded=0
 for t in board.GetTracks():
  if t.GetClass()!='PCB_TRACK' or not pair_key(t.GetNetname()):continue
  L=p.In1_Cu if t.GetLayer()==p.F_Cu else p.In2_Cu if t.GetLayer()==p.B_Cu else None
  if L is None:fail.append(dict(net=t.GetNetname(),reason='SS routed on unexpected inner layer'));continue
  a,b=xy(t.GetStart()),xy(t.GetEnd());count=max(1,math.ceil(math.dist(a,b)/.25))
  for i in range(count+1):
   q=tuple(a[k]+(b[k]-a[k])*i/count for k in (0,1))
   if any(math.dist(q,xy(v))<p.ToMM(v.GetWidth())/2+.25 for v in vias) or any(math.dist(q,xy(h))<max(p.ToMM(h.GetSize().x),p.ToMM(h.GetSize().y))/2+.25 for h in signal_holes):excluded+=1;continue
   samples+=1;pt=p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
   if not any(z.GetFilledPolysList(L).Contains(pt) for z in zones[L]):fail.append(dict(net=t.GetNetname(),layer=board.GetLayerName(t.GetLayer()),reference=board.GetLayerName(L),point_mm=q))
 returns=[]
 for v in vias:
  d=min((math.dist(xy(v),xy(g)) for g in ground),default=1e9);returns.append(dict(net=v.GetNetname(),via_mm=xy(v),nearest_ground_via_mm=d,target_maximum_mm=2.0))
 return dict(reference_samples=samples,local_via_antipad_samples_excluded=excluded,missing_reference_samples=fail,signal_via_ground_returns=returns,ground_return_target_is_design_rule_not_manufacturer_guarantee=True)

def via_transition_audit(board):
 """A retained signal via must carry its net between both routed layers.
 Same-net proximity alone does not justify an unused plated-hole stub.
 """
 tracks=[t for t in board.GetTracks() if t.GetClass()=='PCB_TRACK' and pair_key(t.GetNetname())];out=[]
 for via in board.GetTracks():
  if via.GetClass()!='PCB_VIA' or not pair_key(via.GetNetname()):continue
  q=xy(via);layers=set()
  for track in tracks:
   if track.GetNetname()!=via.GetNetname():continue
   distance=pointseg(q,xy(track.GetStart()),xy(track.GetEnd()))[0]
   if distance<=(p.ToMM(track.GetWidth())+p.ToMM(via.GetWidth()))/2+1e-6:layers.add(track.GetLayer())
  out.append(dict(net=via.GetNetname(),via_mm=q,connected_outer_layers=[board.GetLayerName(L) for L in sorted(layers)],has_two_layer_signal_path=p.F_Cu in layers and p.B_Cu in layers))
 return out

def total_paths(board,lane):
 lengths=collections.defaultdict(float);counts=collections.Counter()
 for t in board.GetTracks():
  if t.GetClass()=='PCB_TRACK':lengths[t.GetNetname()]+=p.ToMM(t.GetLength())
  elif t.GetClass()=='PCB_VIA':counts[t.GetNetname()]+=1
 rows=[]
 paths=lane.get('variants',{}).get('routed_overrides',{}).get('orientation_paths',[])
 for item in paths:
  legs=item['paths_from_physical_hub_p_n'];result=[]
  for leg in legs:
   chain=leg['net_chain'];result.append(dict(hub_pin=leg['hub_pin'],connector_pin=leg['connector_pin'],net_chain=chain,copper_length_mm=sum(lengths[n] for n in chain),signal_via_count=sum(counts[n] for n in chain)))
  rows.append(dict(port=item['port'],orientation=item['detected_cc'],direction=item['direction_relative_to_hub'],legs=result,copper_skew_mm=abs(result[0]['copper_length_mm']-result[1]['copper_length_mm']),via_count_matched=result[0]['signal_via_count']==result[1]['signal_via_count']))
 for direction,pins,chains in [('TX',['19','20'],[['MIC_TXP','MIC_TX_CONNP'],['MIC_TXN','MIC_TX_CONNN']]),('RX',['22','23'],[['MIC_RXP','MIC_RX_CONNP'],['MIC_RXN','MIC_RX_CONNN']])]:
  vals=[sum(lengths[n] for n in chain) for chain in chains];vs=[sum(counts[n] for n in chain) for chain in chains]
  rows.append(dict(port='MIC',orientation='USB-A fixed',direction=direction,net_chains=chains,copper_length_mm=vals,copper_skew_mm=abs(vals[0]-vals[1]),signal_via_counts=vs,via_count_matched=vs[0]==vs[1]))
 return rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('pcb',type=Path);ap.add_argument('--routing',type=Path,default=ROOT/'revisions/usb3-front-end/routing-evidence.json');ap.add_argument('--power-report',type=Path);ap.add_argument('--output',type=Path,default=ROOT/'outputs/usb3-design/signal-integrity-audit.json');a=ap.parse_args()
 board=p.LoadBoard(str(a.pcb));records=load_records(board);regions=package_regions(board);mins,exceptions=spacing(records,regions)
 lane_path=ROOT/'outputs/usb3-design/lane-orientation-audit.json';lane=json.loads(lane_path.read_text());route=json.loads(a.routing.read_text())
 sys.path.insert(0,str(ROOT/'source/generator'));import usb3_frontend as schema
 connected=net_connectivity(board,{n for pair in schema.SUPERSPEED_PAIRS+schema.USB2_PAIRS for n in pair}|{'HUB_XI','HUB_XO'})
 power_connected=net_connectivity(board,{'+5_USB_RAW','+1V2_USB','+3V3_USB','CAM_VBUS','MIC_VBUS','BMS_USB_VBUS','U510_SW','U511_SW'})
 reference=reference_audit(board);totals=total_paths(board,lane);transitions=via_transition_audit(board)
 inputs=[a.pcb,a.routing,lane_path,Path(__file__),ROOT/'source/generator/build_usb3_frontend.py',ROOT/'source/generator/usb3_frontend.py',ROOT/'source/generator/usb3_frontend_routed.py',ROOT/'source/generator/route_usb3_power.py',ROOT/'source/generator/usb_child_arrival_reservation.json',ROOT/'revisions/usb3-front-end/pre-power-escapes.json',ROOT/'revisions/usb3-front-end/drt-breakout-evidence.json']
 if a.power_report:inputs.append(a.power_report)
 hashes={str(q):hashlib.sha256(q.read_bytes()).hexdigest() for q in inputs if q.exists()}
 stale=[path for path,h in lane.get('source_sha256',{}).items() if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=h]
 problems=[]
 if len(route.get('superspeed',[]))!=34 or len(route.get('usb2',[]))!=12 or len(totals)!=10:problems.append('Differential routing/channel evidence incomplete')
 if any(not q['connected'] for q in connected):problems.append('Unconnected highspeed/clock pads')
 if any(not q['connected'] for q in power_connected):problems.append('Unconnected power pads')
 if any(q['edge_spacing_mm']<q['target_mm']-1e-4 for q in mins):problems.append('Outside-package spacing targets not met')
 if any(q['copper_skew_mm']>.050+1e-5 or not q['via_count_matched'] for q in totals):problems.append('Whole-channel copper skew/via count not met')
 if reference['missing_reference_samples']:problems.append('Missing continuous adjacent ground reference')
 if any(q['nearest_ground_via_mm']>2.0 for q in reference['signal_via_ground_returns']):problems.append('Signal transitions need closer ground returns')
 if any(not q['has_two_layer_signal_path'] for q in transitions):problems.append('Unused or single-layer signal via stubs')
 if stale:problems.append('Independent logical lane audit stale')
 if not a.power_report:problems.append('Power-stage input/report not provided')
 else:
  power_report=json.loads(a.power_report.read_text())
  if power_report.get('status')!='POWER_CONNECTED':problems.append('Power-stage report incomplete')
  if not route.get('pcb_sha256') or power_report.get('input_sha256')!=route['pcb_sha256']:problems.append('Power-stage input does not match differential/ordinary routing snapshot')
 if any(not q['routed'] for q in route.get('superspeed',[])+route.get('usb2',[])):problems.append('Routing evidence contains failed differential links')
 report=dict(status='FAIL' if problems else 'PASS',time_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),reviewed_pcb=str(a.pcb),sha256=hashes,problems=problems,targets_mm={'SS_pair_to_pair':1.020,'USB2_to_SS_or_USB2':.762,'HS_to_other_signal_or_power':.762,'HS_to_clock':1.27,'maximum_SS_total_copper_skew':.050},spacing_minima=sorted(mins,key=lambda q:q['edge_spacing_mm']),bounded_package_exceptions=sorted(exceptions,key=lambda q:q['edge_spacing_mm']),package_regions=regions,highspeed_and_clock_connectivity=connected,power_connectivity=power_connected,total_active_channel_copper_paths=totals,ground_reference=reference,signal_via_transitions=transitions,stale_lane_source_files=stale,limitations=['Geometric saved-copper screen; no eye-diagram/EMC/insertion-loss simulation or real streaming certification.','Pad rectangle bounds conservatively cover rounded/chamfered corners.','Intra-chip delay and capacitor internal paths are not reconstructed; matched-component qualification remains per manufacturer.','90ohm geometry applies to coupled uniform sections; explicit DRT/package pitch expansions and length tuning are local discontinuities.','Native DRC, factory drill/assembly checks, electrical startup/thermal tests and actualUSB3enumeration remain separate release gates.'])
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'status':report['status'],'problems':problems,'spacing_minima':len(mins),'package_exceptions':len(exceptions),'output':str(a.output)},indent=2))
if __name__=='__main__':main()
