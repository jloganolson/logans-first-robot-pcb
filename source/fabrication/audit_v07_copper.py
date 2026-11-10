"""Independent physical sampling of v0.7 integration copper and references.

This is a geometry inspection report, never an ampacity or USB eye certificate.
It reads the saved/refilled PCB rather than assuming generator polygons filled.
"""
import json,math,sys,hashlib
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'revisions/v0.7'
board=Path(sys.argv[1]) if len(sys.argv)>1 else OUT/'kicad/robot_pdb.kicad_pcb'
routing=Path(sys.argv[2]) if len(sys.argv)>2 else OUT/'integration-routing.json'
OUT=Path(sys.argv[3]) if len(sys.argv)>3 else OUT;OUT.mkdir(parents=True,exist_ok=True)
b=p.LoadBoard(str(board));r=json.loads(routing.read_text());board_hash=hashlib.sha256(board.read_bytes()).hexdigest()
if r.get('routed_board_sha256'):assert r['routed_board_sha256']==board_hash,'Routing evidence belongs to a different PCB; rerun routing or use its matching PCB snapshot.'
def vec(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def norm(q):
 d=math.hypot(*q);return(q[0]/d,q[1]/d)
def distseg(q,a,c):
 v=(c[0]-a[0],c[1]-a[1]);d=v[0]**2+v[1]**2;t=max(0,min(1,((q[0]-a[0])*v[0]+(q[1]-a[1])*v[1])/d)) if d else 0
 return math.dist(q,(a[0]+t*v[0],a[1]+t*v[1]))
polys={}
for z in b.Zones():
 if z.GetIsRuleArea():continue
 for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu):
  if z.IsOnLayer(layer):polys.setdefault((z.GetNetname(),layer),[]).append(z.GetFilledPolysList(layer))
def filled(net,layer,q):return any(poly.Contains(vec(q)) for poly in polys.get((net,layer),[]))
reference_items={layer:[item for item in b.GetTracks() if item.IsOnLayer(layer) and item.GetNetname()!='GND'] for layer in (p.In1_Cu,p.In2_Cu)}
def void_causes(layer,q):
 pt=vec(q);names=set()
 for item in reference_items[layer]:
  hit=math.dist(q,p.ToMM(item.GetPosition()))<p.ToMM(item.GetWidth())/2+.35 if item.GetClass()=='PCB_VIA' else item.HitTest(pt,p.FromMM(.35))
  if hit:names.add(item.GetNetname())
 for (net,ly),shapes in polys.items():
  if ly==layer and net!='GND' and any(poly.OutlineCount() and poly.SquaredDistance(pt)<p.FromMM(.35)**2 for poly in shapes):names.add(net)
 return sorted(names)
def width_at(net,layer,q,normal,half):
 # Uniform0.10mm cross-section bins; report only actual filled copper.
 step=.1;count=round(half*2/step);runs=[];run=0
 for i in range(count):
  d=-half+(i+.5)*step;pt=(q[0]+normal[0]*d,q[1]+normal[1]*d)
  if filled(net,layer,pt):run+=step
  elif run:runs.append(run);run=0
 if run:runs.append(run)
 return {'total_mm':round(sum(runs),3),'largest_interval_mm':round(max(runs,default=0),3)}
power=[]
for item in r.get('power',[]):
 rows=[];width=item['nominal_width_mm_per_outer_layer'];layers=item.get('layers',['F','B']);path=item['centreline']
 for a,c in zip(path,path[1:]):
  distance=math.dist(a,c);tangent=norm((c[0]-a[0],c[1]-a[1]));normal=(-tangent[1],tangent[0]);count=max(1,math.ceil(distance/2))
  for i in range(count):
   f=(i+.5)/count;q=(a[0]+(c[0]-a[0])*f,a[1]+(c[1]-a[1])*f)
   actual={ly:width_at(item['net'],p.F_Cu if ly=='F' else p.B_Cu,q,normal,width*.6) for ly in layers};ratio=sum(v['total_mm'] for v in actual.values())/(width*len(layers))
   rows.append({'point':q,'filled_widths':actual,'nominal_fraction':round(ratio,3)})
 explicit=[]
 for bridge in item.get('explicit_track_segments',[]):
  for a,c in zip(bridge['path'],bridge['path'][1:]):
   ly=p.F_Cu if bridge['layer']=='F' else p.B_Cu
   matches=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==item['net'] and t.GetLayer()==ly and abs(p.ToMM(t.GetWidth())-bridge['width_mm'])<1e-6 and (math.dist(p.ToMM(t.GetStart()),a)<1e-5 and math.dist(p.ToMM(t.GetEnd()),c)<1e-5 or math.dist(p.ToMM(t.GetStart()),c)<1e-5 and math.dist(p.ToMM(t.GetEnd()),a)<1e-5)]
   explicit.append({'layer':bridge['layer'],'from':a,'to':c,'width_mm':bridge['width_mm'],'verified_actual_track':bool(matches),'uuids':[t.m_Uuid.AsString() for t in matches]})
 power.append({'net':item['net'],'layers':layers,'nominal_width_mm_each':width,'sample_count':len(rows),'minimum_nominal_fraction':min(x['nominal_fraction'] for x in rows),'inspection_points':[x for x in rows if x['nominal_fraction']<.65],'explicit_track_geometry':explicit,'bridge_note':item.get('bridge_note'), 'meaning':'Zone-only cross sections: a low fraction identifies geometry to inspect, including component necks and separately verified trace bridges. A high fraction does not establish a continuous conducting path or a current rating.'})
#Match exact KiCad integer-grid coordinates. Decimal rounding can put the
#same1nm-quantized endpoint on opposite sides of a floating halfway tie.
tracks={}
for t in b.GetTracks():
 if t.GetClass()!='PCB_TRACK':continue
 layer=b.GetLayerName(t.GetLayer());a,c=t.GetStart(),t.GetEnd();key=(t.GetNetname(),layer,(a.x,a.y),(c.x,c.y));tracks[key]=p.ToMM(t.GetWidth())
usb=[]
for item in r.get('pairs',[]):
 if not item.get('routed'):usb.append({'pair':item['pair'],'routed':False});continue
 checked=0;missing=[];covered=0;tested=0;gaps=[];lengths={}
 for path in item['paths']:
  net=path['net'];via=[p.ToMM(v.GetPosition()) for v in b.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname() in item['pair']];length=0
  for ly,points in path['segments']:
   ref=p.In1_Cu if ly=='F' else p.In2_Cu
   for a,c in zip(points,points[1:]):
    d=math.dist(a,c);length+=d
    if d<1e-7:continue
    key=(net,ly+'.Cu',tuple(p.FromMM(x) for x in a),tuple(p.FromMM(x) for x in c));rev=(key[0],key[1],key[3],key[2]);checked+=1
    if key not in tracks and rev not in tracks:missing.append({'net':net,'layer':ly,'from':a,'to':c})
    count=max(1,math.ceil(d/.25))
    for i in range(count):
     f=(i+.5)/count;q=(a[0]+(c[0]-a[0])*f,a[1]+(c[1]-a[1])*f)
     if any(math.dist(q,v)<.8 for v in via):continue
     tested+=1
     if filled('GND',ref,q):covered+=1
     else:gaps.append({'net':net,'signal_layer':ly,'reference_layer':b.GetLayerName(ref),'point':q})
  lengths[net]=length
 usb.append({'pair':item['pair'],'routed':True,'recorded_segments':checked,'missing_recorded_segments':missing,'lengths_mm':lengths,'skew_mm':abs(lengths[item['pair'][0]]-lengths[item['pair'][1]]),'reference_samples':tested,'ground_covered_samples':covered,'reference_coverage':covered/tested if tested else None,'reference_inspection_points':gaps,'reference_method':'F.Cu uses saved L2 GND fill; B.Cu uses saved L3 GND fill. Own signal-via antipads within0.8mm are omitted. Other small plane voids remain inspection points, not automatic proof of a broken return path.'})
report={'board':str(board),'board_sha256':board_hash,'power':power,'usb':usb,'release':'Inspection evidence only. Native zero-opens/clearance, factory review, current/thermal tests, and USB electrical/functional tests remain separate requirements.'}
(OUT/'intercell-copper-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'power':[{'net':x['net'],'minimum_fraction':x['minimum_nominal_fraction'],'inspection_points':len(x['inspection_points'])} for x in power],'usb':[{'pair':x['pair'],'routed':x['routed'],'missing_segments':len(x.get('missing_recorded_segments',[])),'reference_coverage':x.get('reference_coverage')} for x in usb]},indent=2))

# Complete channel paths are measured independently of the added-route ledger.
# This includes the inherited MCU/ESD/header tail of both full-speed functions.
import heapq
channels=[('CAN USB FullSpeed12Mb/s','P3_DP','P3_DM',('U10','8','7'),('U7001','33','32')),
 ('PWM USB FullSpeed12Mb/s','P4_DP','P4_DM',('U10','6','5'),('U7002','33','32')),
 ('Child hub HighSpeed480Mb/s','HUB_CHILD_DP','HUB_CHILD_DM',('U10','15','14'),('U9500','1','2'))]
fps={f.GetReference():f for f in b.GetFootprints()};added=set(r.get('added_track_uuids',[]));thickness=p.ToMM(b.GetDesignSettings().GetBoardThickness())
def key(layer,q):return(layer,int(q.x),int(q.y))
def padpoint(ref,pin):return next(x for x in fps[ref].Pads() if x.GetNumber()==pin)
def measure(net,source,target):
 ts=[t for t in b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net and t.GetLayer() in (p.F_Cu,p.B_Cu)]
 vs=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()==net]
 pads=[q for f in b.GetFootprints() for q in f.Pads() if q.GetNetname()==net]
 anchors={p.F_Cu:set(),p.B_Cu:set()};graph={};geometric_edges=[]
 def edge(a,c,length,kind,data=None):
  if a==c:return
  graph.setdefault(a,[]).append((c,length,kind,data));graph.setdefault(c,[]).append((a,length,kind,data))
  if kind=='track':geometric_edges.append((length,data))
 for t in ts:
  anchors[t.GetLayer()].update((key(t.GetLayer(),t.GetStart()),key(t.GetLayer(),t.GetEnd())))
 for v in vs:
  for ly in anchors:anchors[ly].add(key(ly,v.GetPosition()))
 for q in pads:
  for ly in anchors:
   if q.IsOnLayer(ly):anchors[ly].add(key(ly,q.GetPosition()))
 for t in ts:
  ly=t.GetLayer();a,c=p.ToMM(t.GetStart()),p.ToMM(t.GetEnd());length=math.dist(a,c);points=[]
  if length<1e-8:continue
  v=(c[0]-a[0],c[1]-a[1])
  for node in anchors[ly]:
   q=(p.ToMM(node[1]),p.ToMM(node[2]));f=((q[0]-a[0])*v[0]+(q[1]-a[1])*v[1])/(length*length)
   if -1e-8<=f<=1+1e-8 and distseg(q,a,c)<1e-5:points.append((max(0,min(1,f)),node))
  points=sorted(set(points))
  for (fa,na),(fc,nc) in zip(points,points[1:]):
   aa=(p.ToMM(na[1]),p.ToMM(na[2]));cc=(p.ToMM(nc[1]),p.ToMM(nc[2]));edge(na,nc,(fc-fa)*length,'track',{'uuid':t.m_Uuid.AsString(),'layer':ly,'from':aa,'to':cc,'width':p.ToMM(t.GetWidth()),'inherited':t.m_Uuid.AsString() not in added})
 for v in vs:edge(key(p.F_Cu,v.GetPosition()),key(p.B_Cu,v.GetPosition()),thickness,'via',v.m_Uuid.AsString())
 for q in pads:
  for ly in anchors:
   if not q.IsOnLayer(ly):continue
   centre=key(ly,q.GetPosition())
   for node in anchors[ly]:
    if node==centre:continue
    if q.HitTest(p.VECTOR2I(node[1],node[2]),0):edge(centre,node,math.hypot(node[1]-centre[1],node[2]-centre[2])/1e6,'pad_contact')
 start=key(p.F_Cu,padpoint(*source).GetPosition());goal=key(p.F_Cu,padpoint(*target).GetPosition());pq=[(0,start)];cost={start:0};previous={}
 while pq:
  distance,node=heapq.heappop(pq)
  if distance!=cost[node]:continue
  if node==goal:break
  for other,weight,kind,data in graph.get(node,[]):
   candidate=distance+weight
   if candidate<cost.get(other,math.inf):cost[other]=candidate;previous[other]=(node,weight,kind,data);heapq.heappush(pq,(candidate,other))
 if goal not in cost:return {'net':net,'connected_path_found':False,'source':source,'target':target}
 edges=[];node=goal
 while node!=start:
  prev,weight,kind,data=previous[node];edges.append((weight,kind,data));node=prev
 edges.reverse();segments=[(weight,data) for weight,kind,data in edges if kind=='track'];via_count=sum(kind=='via' for _,kind,_ in edges)
 planar=sum(x for x,_ in segments);all_copper=sum(p.ToMM(t.GetLength()) for t in ts);own_vias=[p.ToMM(v.GetPosition()) for v in vs]
 def segment_id(data):return(data['uuid'],tuple(sorted((tuple(data['from']),tuple(data['to'])))))
 used={segment_id(data) for _,data in segments};surplus=[];in_pad_surplus=0
 for distance,data in geometric_edges:
  if segment_id(data) in used:continue
  a0,c0=data['from'],data['to'];inside=True
  for i in range(max(2,math.ceil(distance/.05))+1):
   count=max(2,math.ceil(distance/.05));f=i/count;q=(a0[0]+(c0[0]-a0[0])*f,a0[1]+(c0[1]-a0[1])*f)
   if not any(pad.IsOnLayer(data['layer']) and pad.HitTest(vec(q),0) for pad in pads):inside=False;break
  if inside:in_pad_surplus+=distance
  else:surplus.append({'from':a0,'to':c0,'layer':b.GetLayerName(data['layer']),'length_mm':distance,'uuid':data['uuid']})
 good=total=service_good=service_total=0;missing=[];non_nominal=[]
 for distance,data in segments:
  a,c=data['from'],data['to'];count=max(1,math.ceil(distance/.25));ref=p.In1_Cu if data['layer']==p.F_Cu else p.In2_Cu
  if abs(data['width']-.204)>.001:non_nominal.append({'layer':b.GetLayerName(data['layer']),'from':a,'to':c,'length_mm':distance,'width_mm':data['width'],'inherited':data['inherited']})
  for i in range(count):
   f=(i+.5)/count;q=(a[0]+(c[0]-a[0])*f,a[1]+(c[1]-a[1])*f)
   if any(math.dist(q,v)<.8 for v in own_vias):continue
   total+=1;covered=filled('GND',ref,q);good+=covered
   if 128<=q[1]<=160:service_total+=1;service_good+=covered
   if not covered:missing.append({'point':q,'layer':b.GetLayerName(data['layer']),'reference':b.GetLayerName(ref),'reference_void_causes':void_causes(ref,q)})
 return {'net':net,'source':source,'target':target,'connected_path_found':True,'planar_trace_mm':planar,'barrel_mm':via_count*thickness,'via_transitions':via_count,'pad_centre_contact_mm':sum(w for w,k,d in edges if k=='pad_contact'),'total_centreline_mm':cost[goal],'inherited_trace_mm':sum(w for w,d in segments if d['inherited']),'added_trace_mm':sum(w for w,d in segments if not d['inherited']),'drawn_net_trace_mm':all_copper,'conservative_drawn_trace_plus_barrels_mm':all_copper+via_count*thickness,'off_path_or_parallel_copper_mm':max(0,all_copper-planar),'off_path_inside_pad_mm':in_pad_surplus,'off_path_outside_pad_mm':sum(x['length_mm'] for x in surplus),'off_path_outside_pad_segments':surplus,'non_nominal_width_segments':non_nominal,'reference_samples':total,'ground_covered_samples':good,'reference_coverage':good/total if total else None,'service_gap_reference_samples':service_total,'service_gap_ground_covered_samples':service_good,'service_gap_reference_coverage':service_good/service_total if service_total else None,'reference_inspection_points':missing,'_segments':segments}
def parallel_core(positive,negative):
 total=0;exception=[]
 if not positive.get('connected_path_found') or not negative.get('connected_path_found'):return None,[]
 for length,a in positive['_segments']:
  if length<1e-8:continue
  u=norm((a['to'][0]-a['from'][0],a['to'][1]-a['from'][1]));intervals=[]
  if abs(a['width']-.204)<.001:
   for _,c in negative['_segments']:
    if c['layer']!=a['layer'] or abs(c['width']-.204)>.001:continue
    v=norm((c['to'][0]-c['from'][0],c['to'][1]-c['from'][1]))
    if abs(u[0]*v[1]-u[1]*v[0])>1e-5:continue
    delta=(c['from'][0]-a['from'][0],c['from'][1]-a['from'][1]);separation=abs(delta[0]*u[1]-delta[1]*u[0])
    if abs(separation-.364)>.005:continue
    projection=lambda q:(q[0]-a['from'][0])*u[0]+(q[1]-a['from'][1])*u[1]
    lo,hi=sorted((projection(c['from']),projection(c['to'])));lo=max(0,lo);hi=min(length,hi)
    if hi>lo:intervals.append((lo,hi))
  merged=[]
  for lo,hi in sorted(intervals):
   if merged and lo<=merged[-1][1]+1e-5:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
   else:merged.append((lo,hi))
  matched=sum(hi-lo for lo,hi in merged);total+=matched
  if length-matched>.01:exception.append({'layer':b.GetLayerName(a['layer']),'from':a['from'],'to':a['to'],'unmatched_positive_length_mm':length-matched,'width_mm':a['width'],'inherited':a['inherited'],'meaning':'Package/pad/via taper, corner overlap, or inherited full-speed tail; this portion is not counted as uniform0.204/0.160mm pair core.'})
 return total,exception
complete=[]
for name,pn,nn,a,c in channels:
 positive=measure(pn,(a[0],a[1]),(c[0],c[1]));negative=measure(nn,(a[0],a[2]),(c[0],c[2]));core,exceptions=parallel_core(positive,negative)
 row={'channel':name,'positive':positive,'negative':negative,'nominal_parallel_core_positive_mm':core,'bounded_nonuniform_geometry':exceptions,'measurement_limits':'Pad-centre routing geometry, including actual inherited tracks. Via barrel length uses the PCB thickness; silicon/package internal delays and solder shapes are not modelled. Off-path copper is a stub/loop review hold; finite reference voids require local geometry review.'}
 if positive.get('connected_path_found') and negative.get('connected_path_found'):row['total_skew_mm']=abs(positive['total_centreline_mm']-negative['total_centreline_mm']);row['conservative_drawn_skew_mm']=abs(positive['conservative_drawn_trace_plus_barrels_mm']-negative['conservative_drawn_trace_plus_barrels_mm'])
 positive.pop('_segments',None);negative.pop('_segments',None);complete.append(row)
report['complete_usb2_channels']=complete
(OUT/'intercell-copper-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'complete_usb2_channels':[{'channel':x['channel'],'positive_mm':x['positive'].get('total_centreline_mm'),'negative_mm':x['negative'].get('total_centreline_mm'),'skew_mm':x.get('total_skew_mm'),'P_external_stub_mm':x['positive'].get('off_path_outside_pad_mm'),'N_external_stub_mm':x['negative'].get('off_path_outside_pad_mm'),'P_gap_reference':x['positive'].get('service_gap_reference_coverage'),'N_gap_reference':x['negative'].get('service_gap_reference_coverage')} for x in complete]},indent=2))
