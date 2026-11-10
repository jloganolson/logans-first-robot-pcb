#!/usr/bin/env python3
"""Independent read-only v0.9 saved-board USB2 channel geometry audit.

Native copper adjacency and individual filled islands establish physical links.
A separate split centreline graph measures routing; neither proves a USB eye.
No generator route ledger is accepted as proof of saved copper.
"""
import argparse,collections,datetime,hashlib,heapq,importlib,json,math,sys
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/generator'))
from audit_usb3_signals import load_records,closest,split_at_regions,within
LAYERS=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)
SPECS=[('upstream_A','USB_DP','USB_DM',('J10','A6','A7'),('U9902','8','7'),'HS'),
 ('upstream_B','USB_DP','USB_DM',('J10','B6','B7'),('U9902','8','7'),'HS'),
 ('host_package','USB_DP','USB_DM',('U11','1','3'),('U9902','8','7'),'HS'),
 ('upstream_hub','HUB_UP_DP','HUB_UP_DM',('U9902','1','2'),('U10','15','14'),'HS'),
 ('audio','P1_DP','P1_DM',('U10','12','11'),('U12','41','42'),'FS'),
 ('dynamixel','P2_DP','P2_DM',('U10','10','9'),('U14','3','4'),'FS'),
 ('PWM','P4_DP','P4_DM',('U10','6','5'),('U7002','33','32'),'FS')]
NETS={n for row in SPECS for n in row[1:3]}
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def uid(x):return x.m_Uuid.AsString()
def xy(q):return tuple(p.ToMM(q))
def vec(q):return p.VECTOR2I(p.FromMM(q[0]),p.FromMM(q[1]))
def pointseg(q,a,b):
 v=(b[0]-a[0],b[1]-a[1]);d=sum(z*z for z in v);t=max(0,min(1,sum((q[k]-a[k])*v[k] for k in (0,1))/d)) if d else 0
 return math.dist(q,tuple(a[k]+t*v[k] for k in (0,1)))
def channel(net):return 'UPSTREAM' if net in ('USB_DP','USB_DM','HUB_UP_DP','HUB_UP_DM') else net[:2] if net in NETS else None
class Audit:
 def __init__(self,path):
  self.path=Path(path);self.hash=digest(path);self.b=p.LoadBoard(str(path));self.cn=self.b.GetConnectivity();self.cn.Build(self.b)
  self.fps={f.GetReference():f for f in self.b.GetFootprints()};self.thick=p.ToMM(self.b.GetDesignSettings().GetBoardThickness());self.parent={}
  self.items=[q for f in self.b.GetFootprints() for q in f.Pads() if q.GetNetname() in NETS|{'GND'}]+[t for t in self.b.GetTracks() if t.GetNetname() in NETS|{'GND'}]
  for q in self.items:
   if q.GetNetname()=='GND':continue
   others=list(self.cn.GetConnectedTracks(q))
   # Ground pads query their tracks; querying all ground pads again for each
   # track can expand through the full plane and is redundant here.
   if q.GetNetname()!='GND':others+=list(self.cn.GetConnectedPads(q))
   for other in others:
    if other.GetNetname()==q.GetNetname():self.union(uid(q),uid(other))
  # Ground copper uses exact anchor adjacency and native-shaped pad contacts;
  # filled islands below provide plane connectivity. Never union by net name.
  anchors=collections.defaultdict(list);ground=[q for q in self.items if q.GetNetname()=='GND']
  for q in ground:
   for ly in LAYERS:
    if not q.IsOnLayer(ly):continue
    pts=[q.GetPosition()] if q.GetClass() in ('PAD','PCB_VIA') else [q.GetStart(),q.GetEnd()]
    for pt in pts:anchors[(ly,pt.x,pt.y)].append(q)
  for group in anchors.values():
   for q in group[1:]:self.union(uid(group[0]),uid(q))
  padgrid=collections.defaultdict(list)
  for q in ground:
   if q.GetClass()!='PAD':continue
   bb=q.GetBoundingBox()
   for x in range(bb.GetLeft()//2000000,bb.GetRight()//2000000+1):
    for y in range(bb.GetTop()//2000000,bb.GetBottom()//2000000+1):padgrid[x,y].append(q)
  for (ly,x,y),group in anchors.items():
   for q in padgrid.get((x//2000000,y//2000000),[]):
    if q.IsOnLayer(ly) and q.HitTest(p.VECTOR2I(x,y),0):self.union(uid(q),uid(group[0]))
  self.zones=[];self.signal_islands=[]
  for z in self.b.Zones():
   if z.GetIsRuleArea():continue
   for layer in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu):
    if not z.IsOnLayer(layer):continue
    ps=z.GetFilledPolysList(layer)
    for ix in range(ps.OutlineCount()):
     island=ps.UnitSet(ix);node=f'zone:{uid(z)}:{layer}:{ix}';self.zones.append((z.GetNetname(),layer,node,island))
     if z.GetNetname() not in NETS|{'GND'}:continue
     if z.GetNetname() in NETS:self.signal_islands.append(node)
     for q in self.items:
      if q.GetNetname()!=z.GetNetname() or not q.IsOnLayer(layer):continue
      anchors=[q.GetPosition()] if q.GetClass() in ('PAD','PCB_VIA') else [q.GetStart(),q.GetEnd()]
      if any(island.BBox().Contains(v) and island.Contains(v) for v in anchors):self.union(node,uid(q))
  # Separate island nodes are unioned only by a real same-net/layer overlap.
  sz=[z for z in self.zones if z[0] in NETS|{'GND'}]
  for i,(n,l,k,poly) in enumerate(sz):
   for nn,ll,kk,pp in sz[i+1:]:
    if n==nn and l==ll and k.split(':')[1]!=kk.split(':')[1] and poly.BBox().Intersects(pp.BBox()) and poly.Collide(pp):self.union(k,kk)
  self.ground_anchor=self.pad('J1','1');self.ground_islands=[dict(node=k,layer=self.b.GetLayerName(l),connected_to_J1_GND=self.find(k)==self.find(uid(self.ground_anchor))) for n,l,k,poly in self.zones if n=='GND']
  self.regions=[]
  for ref,hx,hy in [('U10',5,5),('U11',3.8,4.45),('U9902',3.75,4),('J10',5.2,2.5),('U12',5,5),('U14',4,4),('U7002',6.5,6.5),('U7009',2.5,3)]:
   f=self.fps[ref];x,y=xy(f.GetPosition());self.regions.append(dict(reference=ref,box_mm=[x-hx-(.5 if ref=='J10' else 0),y-hy,x+hx+(.5 if ref=='U10' else .4 if ref=='U7009' else 0),y+hy],nets=sorted({q.GetNetname() for q in f.Pads()}),rationale='J10 left edge only218.7→218.2; reviewed unchanged connector-side0.282843mm DM bend plus following horizontal/CC1 static5.1kRd; excludes post-ESD source x214.3625/newhost x213.3; all actual minima remain reported' if ref=='J10' else 'U10 right-side only0.5mm expansion for preserved power-via/source-escape field; all actual minima remain reported' if ref=='U10' else 'U7009 right-side only0.4mm expansion for own P4 flare around centrepin5; native clearance and remote isolation unchanged' if ref=='U7009' else 'Bounded package/source-cell escape'))
 def find(self,k):
  self.parent.setdefault(k,k);trail=[];node=k
  while self.parent[node]!=node:trail.append(node);node=self.parent[node]
  for item in trail:self.parent[item]=node
  return node
 def union(self,a,b):self.parent[self.find(a)]=self.find(b)
 def pad(self,r,pin):return next(q for q in self.fps[r].Pads() if q.GetNumber()==str(pin))
 def fill(self,net,layer,q):return any(n==net and l==layer and (net!='GND' or self.find(k)==self.find(uid(self.ground_anchor))) and poly.BBox().Contains(vec(q)) and poly.Contains(vec(q)) for n,l,k,poly in self.zones)
 def package_box(self,ref,margin=.0):
  f=self.fps[ref];pads=list(f.Pads());boxes=[q.GetBoundingBox() for q in pads]
  return [min(p.ToMM(bb.GetLeft()) for bb in boxes)-margin,min(p.ToMM(bb.GetTop()) for bb in boxes)-margin,max(p.ToMM(bb.GetRight()) for bb in boxes)+margin,max(p.ToMM(bb.GetBottom()) for bb in boxes)+margin]
 def measure(self,net,source,target,native_contacts=True):
  pads=[q for f in self.b.GetFootprints() for q in f.Pads() if q.GetNetname()==net];ts=[q for q in self.b.GetTracks() if q.GetNetname()==net and q.GetClass()=='PCB_TRACK' and q.GetLayer() in LAYERS];vs=[q for q in self.b.GetTracks() if q.GetNetname()==net and q.GetClass()=='PCB_VIA']
  a0,c0=self.pad(*source),self.pad(*target);native=a0.GetNetname()==net==c0.GetNetname() and self.find(uid(a0))==self.find(uid(c0))
  out=dict(net=net,source=list(source),target=list(target),native_connected=native,drawn_track_mm=sum(p.ToMM(t.GetLength()) for t in ts),drawn_vias=len(vs))
  key=lambda ly,q:(int(ly),int(q.x),int(q.y));anchors={ly:set() for ly in LAYERS};graph=collections.defaultdict(list);edges=[]
  def edge(a,c,w,kind,data=None):
   if a==c:return
   eid=len(edges);edges.append((a,c,w,kind,data));graph[a].append((c,w,eid));graph[c].append((a,w,eid))
  for t in ts:anchors[t.GetLayer()].update([key(t.GetLayer(),t.GetStart()),key(t.GetLayer(),t.GetEnd())])
  for q in vs+pads:
   for ly in LAYERS:
    if q.IsOnLayer(ly):anchors[ly].add(key(ly,q.GetPosition()))
  contacts=[];byuid={uid(t):t for t in ts};seen_contacts=set()
  for t in ts:
   for other in self.cn.GetConnectedTracks(t):
    if uid(other) not in byuid or other.GetLayer()!=t.GetLayer():continue
    pair=tuple(sorted((uid(t),uid(other))))
    if pair in seen_contacts:continue
    seen_contacts.add(pair)
    def rec(v):return dict(a=xy(v.GetStart()),b=xy(v.GetEnd()),width=p.ToMM(v.GetWidth()))
    gap,aa,cc=closest(rec(t),rec(other))
    if gap>.000002:continue
    na=key(t.GetLayer(),vec(aa));nc=key(t.GetLayer(),vec(cc));anchors[t.GetLayer()].update((na,nc));contacts.append((na,nc,math.dist(aa,cc),'native_track_contact',dict(track_uuids=list(pair))))
  for q in pads+vs:
   for t in self.cn.GetConnectedTracks(q):
    if uid(t) not in byuid or not q.IsOnLayer(t.GetLayer()):continue
    a,c=xy(t.GetStart()),xy(t.GetEnd());v=tuple(c[j]-a[j] for j in (0,1));den=sum(z*z for z in v);centre=xy(q.GetPosition());f=max(0,min(1,sum((centre[j]-a[j])*v[j] for j in (0,1))/den)) if den else 0;pt=tuple(a[j]+f*v[j] for j in (0,1));node=key(t.GetLayer(),vec(pt))
    if q.HitTest(vec(pt),t.GetWidth()//2):anchors[t.GetLayer()].add(node);contacts.append((key(t.GetLayer(),q.GetPosition()),node,math.dist(centre,pt),'pad_contact' if q.GetClass()=='PAD' else 'native_via_contact',dict(uuid=uid(q),method='Native physical copper contact, nearest centreline projection')))
  for t in ts:
   ly=t.GetLayer();a,c=xy(t.GetStart()),xy(t.GetEnd());d=math.dist(a,c)
   if d<1e-9:continue
   points=[]
   for node in anchors[ly]:
    q=(node[1]/1e6,node[2]/1e6)
    if pointseg(q,a,c)<.000002:
     v=(c[0]-a[0],c[1]-a[1]);fraction=sum((q[k]-a[k])*v[k] for k in (0,1))/(d*d)
     if -.000001<=fraction<=1.000001:points.append((max(0,min(1,fraction)),node))
   points=sorted(set(points))
   for (fa,na),(fc,nc) in zip(points,points[1:]):edge(na,nc,(fc-fa)*d,'track',dict(uuid=uid(t),layer=int(ly),a=[na[1]/1e6,na[2]/1e6],b=[nc[1]/1e6,nc[2]/1e6],width_mm=p.ToMM(t.GetWidth())))
  for contact in contacts:
   if native_contacts:edge(*contact)
  for q in vs:
   for i,ly in enumerate(LAYERS):
    for other in LAYERS[i+1:]:
     if not q.IsOnLayer(ly) or not q.IsOnLayer(other):continue
     edge(key(ly,q.GetPosition()),key(other,q.GetPosition()),self.thick,'via',dict(uuid=uid(q),position_mm=xy(q.GetPosition()),drill_mm=p.ToMM(q.GetDrillValue()),land_mm=p.ToMM(q.GetWidth()),from_layer=self.b.GetLayerName(ly),to_layer=self.b.GetLayerName(other),model='Conservative full1.6mm through-barrel per traversed via, including legacy inner-layer connections'))
  for q in pads:
   for ly in LAYERS:
    if not q.IsOnLayer(ly):continue
    centre=key(ly,q.GetPosition())
    for node in anchors[ly]:
     if node!=centre and q.HitTest(p.VECTOR2I(node[1],node[2]),0):edge(centre,node,math.hypot(node[1]-centre[1],node[2]-centre[2])/1e6,'pad_contact',dict(reference=q.GetParent().GetReference(),pin=q.GetNumber()))
  start=key(p.F_Cu,a0.GetPosition());goal=key(p.F_Cu,c0.GetPosition());cost={start:0};prev={};queue=[(0,start)]
  while queue:
   d,node=heapq.heappop(queue)
   if d!=cost[node]:continue
   if node==goal:break
   for other,w,eid in graph[node]:
    if d+w<cost.get(other,math.inf):cost[other]=d+w;prev[other]=(node,eid);heapq.heappush(queue,(d+w,other))
  out['centreline_path_found']=goal in cost
  if goal not in cost:return out
  selected=[];node=goal
  while node!=start:node,eid=prev[node];selected.append(eid)
  selected.reverse();chosen=set(selected);path=[edges[eid] for eid in selected];segments=[(w,data) for a,c,w,k,data in path if k=='track'];via_records=[data for a,c,w,k,data in path if k=='via']
  out.update(total_length_mm=cost[goal],planar_track_mm=sum(w for w,d in segments),via_barrel_mm=sum(w for a,c,w,k,d in path if k=='via'),via_transitions=len(via_records),vias=via_records,pad_centre_contact_mm=sum(w for a,c,w,k,d in path if k=='pad_contact'),native_track_contact_mm=sum(w for a,c,w,k,d in path if k=='native_track_contact'),path_segments=[d for w,d in segments])
  allowed=['J10','U11'] if net.startswith('USB_') else ['U7009'] if net.startswith('P4_') else []
  off=[]
  for eid,(a,c,w,k,data) in enumerate(edges):
   if eid in chosen or k!='track' or w<.00001:continue
   count=max(1,math.ceil(w/.05));pts=[tuple(data['a'][j]+f*(data['b'][j]-data['a'][j]) for j in (0,1)) for f in [i/count for i in range(count+1)]]
   inpad=all(any(q.IsOnLayer(data['layer']) and q.HitTest(vec(pt),0) for q in pads) for pt in pts)
   bounded=[ref for ref in allowed if all(within(pt,([218.7,100.95,221.0,103.05] if ref=='J10' else self.package_box(ref,.05))) for pt in pts)]
   off.append(dict(**data,length_mm=w,inside_same_net_pad=inpad,documented_package_aliases=bounded,unbounded_stub=not(inpad or bounded)))
  out['off_path_segments']=off;out['unbounded_off_path_mm']=sum(r['length_mm'] for r in off if r['unbounded_stub']);out['bounded_off_path_mm']=sum(r['length_mm'] for r in off if not r['unbounded_stub'])
  good=total=0;gaps=[];via_void=[];hist=collections.defaultdict(float)
  traversed_via_ids={v['uuid'] for v in via_records}
  reference_intruders=[q for q in self.b.GetTracks() if q.GetNetname() not in ('','GND') and uid(q) not in traversed_via_ids]+[q for f in self.b.GetFootprints() for q in f.Pads() if q.GetNetname() not in ('','GND')]
  for d,data in segments:
   hist[f"{data['width_mm']:.6f}"]+=d;ref=p.In2_Cu if data['layer'] in (p.B_Cu,p.In1_Cu) else p.In1_Cu;a,c=data['a'],data['b'];count=max(1,math.ceil(d/.10));u=((c[0]-a[0])/d,(c[1]-a[1])/d) if d else (0,0);normal=(-u[1],u[0])
   for i in range(count):
    f=(i+.5)/count;mid=tuple(a[j]+f*(c[j]-a[j]) for j in (0,1))
    for side in (-.5,0,.5):
     q=tuple(mid[j]+normal[j]*data['width_mm']*side for j in (0,1));total+=1;covered=self.fill('GND',ref,q);good+=covered
     if covered:continue
     causes=sorted({n for n,l,k,poly in self.zones if l==ref and n!='GND' and poly.Contains(vec(q))})
     trace_causes=sorted({t.GetNetname() for t in self.b.GetTracks() if t.GetNetname() not in ('GND','') and t.IsOnLayer(ref) and t.HitTest(vec(q),p.FromMM(.35))})
     row=dict(reference_nearby_copper_nets=trace_causes,point_mm=q,signal_layer=self.b.GetLayerName(data['layer']),reference_layer=self.b.GetLayerName(ref),positive_zone_nets=causes)
     # Keep via antipads visible as measured exceptions rather than silently omitting them.
     near=[v for v in via_records if math.dist(q,v['position_mm'])<=v['land_mm']/2+.25]
     intruders=[dict(uuid=uid(t),net=t.GetNetname(),kind=t.GetClass()) for t in reference_intruders if near and t.IsOnLayer(ref) and t.HitTest(vec(q),p.FromMM(.25))]
     if intruders:row['other_reference_copper_in_own_via_field']=intruders
     (via_void if near and not causes and not intruders else gaps).append(row)
  out['legacy_inner_layer_segments']=[data for length,data in segments if data['layer'] in (p.In1_Cu,p.In2_Cu)]
  out.update(width_length_histogram_mm=dict(hist),non_antipad_reference_coverage=good/(total-len(via_void)) if total>len(via_void) else None,reference_samples=total,ground_covered_samples=good,reference_coverage=good/total if total else None,reference_gaps=gaps,own_via_antipad_samples=via_void)
  return out
 def pair_geometry(self,positive,negative):
  if not positive.get('centreline_path_found') or not negative.get('centreline_path_found'):return None
  core=0;exceptions=[];observed=collections.defaultdict(float)
  for a in positive['path_segments']:
   length=math.dist(a['a'],a['b']);u=tuple((a['b'][j]-a['a'][j])/length for j in (0,1)) if length else (0,0);runs=[]
   for c in negative['path_segments']:
    if a['layer']!=c['layer']:continue
    d=math.dist(c['a'],c['b']);v=tuple((c['b'][j]-c['a'][j])/d for j in (0,1)) if d else (0,0)
    if abs(u[0]*v[1]-u[1]*v[0])>1e-5:continue
    sep=abs((c['a'][0]-a['a'][0])*u[1]-(c['a'][1]-a['a'][1])*u[0]);gap=sep-(a['width_mm']+c['width_mm'])/2
    projection=lambda q:sum((q[j]-a['a'][j])*u[j] for j in (0,1))
    lo,hi=sorted([projection(c['a']),projection(c['b'])]);lo=max(0,lo);hi=min(length,hi)
    if hi<=lo or gap<-.001 or gap>1:continue
    observed[f"P{a['width_mm']:.3f}/N{c['width_mm']:.3f}/gap{gap:.3f}"]+=hi-lo
    if abs(a['width_mm']-.165)<.001 and abs(c['width_mm']-.165)<.001 and abs(gap-.300)<.005:runs.append((lo,hi))
   merged=[]
   for lo,hi in sorted(runs):
    if merged and lo<=merged[-1][1]+1e-6:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
    else:merged.append((lo,hi))
   matched=sum(hi-lo for lo,hi in merged);core+=matched
   if length-matched>.01:exceptions.append(dict(**a,nonuniform_positive_length_mm=length-matched))
  return dict(uniform_0165_0300_positive_length_mm=core,parallel_geometry_histogram_mm=dict(observed),nonuniform_segments=exceptions,meaning='Parallel interval geometry only; bends, package tapers and inherited FS copper are reported, never silently counted as uniform impedance.')
 def own_transfer_fields(self,channels):
  """Bound only matched P/N transfer antipads, using real copper/ground."""
  ground=[q for q in self.b.GetTracks() if q.GetClass()=='PCB_VIA' and q.GetNetname()=='GND']
  signal_items=[q for q in self.b.GetTracks() if q.GetNetname() not in ('','GND')]
  pads=[q for f in self.b.GetFootprints() for q in f.Pads() if q.GetNetname() not in ('','GND')]
  reference=lambda name:'In2.Cu' if name in ('B.Cu','In1.Cu') else 'In1.Cu'
  def foreign(q,layer,allowed):
   pt=vec(q)
   return any(t.IsOnLayer(layer) and uid(t) not in allowed and t.HitTest(pt,p.FromMM(.25)) for t in signal_items) or any(t.IsOnLayer(layer) and t.HitTest(pt,p.FromMM(.25)) for t in pads) or any(n not in ('','GND') and ly==layer and poly.Contains(pt) for n,ly,k,poly in self.zones)
  def stitch(one,two):
   out=[]
   for v in ground:
    pos=xy(v.GetPosition());ds=[math.dist(pos,s['position_mm']) for s in (one,two)]
    if max(ds)>2 or self.find(uid(v))!=self.find(uid(self.ground_anchor)):continue
    if not v.IsOnLayer(p.F_Cu) or not v.IsOnLayer(p.B_Cu):continue
    if not all(self.fill('GND',ly,pos) for ly in (p.In1_Cu,p.In2_Cu)):continue
    out.append(dict(uuid=uid(v),position_mm=pos,distances_to_signal_vias_mm=ds))
   return min(out,key=lambda r:max(r['distances_to_signal_vias_mm'])) if out else None
  radius_cache={}
  def field_radius(via,layer,name):
   nominal=via['land_mm']/2+.25;key=(via['uuid'],layer,name)
   if key in radius_cache:return radius_cache[key]
   radius_cache[key]=(nominal,None)
   # Explicitly reviewed PWM source field only.  Saved polygon inflation is
   # not a licence to absorb another signal's antipad or a remote aperture.
   if name!='PWM' or layer!=p.In2_Cu or math.dist(via['position_mm'],(204.2,103.55))>1e-7 or abs(via['land_mm']-.4)>1e-7:return radius_cache[key]
   max_error=p.ToMM(self.b.GetDesignSettings().m_MaxError)
   if abs(max_error-.005)>1e-9:return radius_cache[key]
   expected=(203.744867,103.55)
   for n,ly,node,poly in self.zones:
    if n!='GND' or ly!=layer or self.find(node)!=self.find(uid(self.ground_anchor)):continue
    for ix in range(poly.OutlineCount()):
     for ring in [poly.COutline(ix)]+[poly.CHole(ix,h) for h in range(poly.HoleCount(ix))]:
      for i in range(ring.PointCount()):
       vertex=xy(ring.CPoint(i))
       if math.dist(vertex,expected)>1e-7:continue
       radius=math.dist(vertex,via['position_mm'])
       if not nominal<radius<=nominal+1.1*max_error:return radius_cache[key]
       basis=dict(classification='reviewed_polygonized_PWM_source_antipad',source_via_uuid=via['uuid'],source_via_mm=via['position_mm'],actual_saved_GND_vertex_mm=vertex,actual_radial_bound_mm=radius,nominal_circle_bound_mm=nominal,board_polygon_max_error_mm=max_error,anchored_GND_island=node,reviewed_by='/root',scope='Only this measured PWM source-via field; foreign copper/positive-zone rejection and matched-pair grounded-stitch requirements still apply.')
       radius_cache[key]=(radius,basis);return radius_cache[key]
   return radius_cache[key]
  def exact_intervals(segment,side,ref,station):
   a,b=segment['a'],segment['b'];d=math.dist(a,b)
   if d<1e-10:return []
   normal=(-(b[1]-a[1])/d,(b[0]-a[0])/d);a=tuple(a[j]+normal[j]*segment['width_mm']*side for j in (0,1));b=tuple(b[j]+normal[j]*segment['width_mm']*side for j in (0,1));v=tuple(b[j]-a[j] for j in (0,1));cuts={0.,1.}
   # Local field limits are circles around exactly these two measured vias.
   for via in station['signal_vias']:
    c=via['position_mm'];radius=station['field_radii_mm'].get(via['uuid'],via['land_mm']/2+.25);delta=tuple(a[j]-c[j] for j in (0,1));aa=sum(t*t for t in v);bb=2*sum(delta[j]*v[j] for j in (0,1));cc=sum(t*t for t in delta)-radius*radius;disc=bb*bb-4*aa*cc
    if disc>=0:
     for f in ((-bb-math.sqrt(disc))/(2*aa),(-bb+math.sqrt(disc))/(2*aa)):
      if 0<f<1:cuts.add(f)
   x0,x1=sorted((a[0],b[0]));y0,y1=sorted((a[1],b[1]))
   # Intersections with actual anchored GND fill outlines AND their holes.
   for n,ly,k,poly in self.zones:
    if n!='GND' or ly!=ref or self.find(k)!=self.find(uid(self.ground_anchor)):continue
    box=poly.BBox()
    if p.ToMM(box.GetRight())<x0 or p.ToMM(box.GetLeft())>x1 or p.ToMM(box.GetBottom())<y0 or p.ToMM(box.GetTop())>y1:continue
    for ix in range(poly.OutlineCount()):
     rings=[poly.COutline(ix)]+[poly.CHole(ix,h) for h in range(poly.HoleCount(ix))]
     for ring in rings:
      points=[xy(ring.CPoint(i)) for i in range(ring.PointCount())]
      for c,e in zip(points,points[1:]+points[:1]):
       if max(c[0],e[0])<x0 or min(c[0],e[0])>x1 or max(c[1],e[1])<y0 or min(c[1],e[1])>y1:continue
       w=tuple(e[j]-c[j] for j in (0,1));den=v[0]*w[1]-v[1]*w[0]
       if abs(den)<1e-14:continue
       delta=tuple(c[j]-a[j] for j in (0,1));f=(delta[0]*w[1]-delta[1]*w[0])/den;u=(delta[0]*v[1]-delta[1]*v[0])/den
       if 0<f<1 and -1e-9<=u<=1+1e-9:cuts.add(f)
   out=[];cuts=sorted(cuts);allowed={q['uuid'] for q in station['signal_vias']}
   for lo,hi in zip(cuts,cuts[1:]):
    mid=tuple(a[j]+v[j]*(lo+hi)/2 for j in (0,1))
    if not any(math.dist(mid,q['position_mm'])<=station['field_radii_mm'].get(q['uuid'],q['land_mm']/2+.25)+1e-8 for q in station['signal_vias']):continue
    if self.fill('GND',ref,mid) or foreign(mid,ref,allowed):continue
    out.append(dict(from_mm=tuple(a[j]+v[j]*lo for j in (0,1)),to_mm=tuple(a[j]+v[j]*hi for j in (0,1)),length_mm=d*(hi-lo),signal_layer=self.b.GetLayerName(segment['layer']),reference_layer=self.b.GetLayerName(ref),copper_width_lane_fraction=side,track_uuid=segment['uuid']))
   return out
  summaries=[]
  for row in channels:
   for leg,other in (('positive','negative'),('negative','positive')):
    measured=row[leg];counter=row[other];fields=[];paired=[];active=[];retained_own=list(measured.get('own_via_antipad_samples',[]))
    for gap in measured.get('reference_gaps',[]):
     q=gap['point_mm'];ref=p.In1_Cu if gap['reference_layer']=='In1.Cu' else p.In2_Cu;match=None
     for own in measured.get('vias',[]):
      if math.dist(q,own['position_mm'])>1.2:continue
      for opposite in counter.get('vias',[]):
       if {own['from_layer'],own['to_layer']}!={opposite['from_layer'],opposite['to_layer']} or math.dist(own['position_mm'],opposite['position_mm'])>1.2:continue
       bounds={v['uuid']:field_radius(v,ref,row['name']) for v in (own,opposite)}
       if not any(math.dist(q,v['position_mm'])<=bounds[v['uuid']][0]+1e-8 for v in (own,opposite)):continue
       allowed={own['uuid'],opposite['uuid']}
       if gap.get('positive_zone_nets') or foreign(q,ref,allowed):continue
       actual=stitch(own,opposite)
       if not actual:continue
       match=dict(signal_vias=[own,opposite],anchored_GND_stitch=actual,antipad_field_radial_clearance_mm=.25,field_radii_mm={k:v[0] for k,v in bounds.items()},polygonized_field_basis=[v[1] for v in bounds.values() if v[1]]);break
      if match:break
     if match:
      gap=dict(gap,classification='intrinsic_matched_PN_transfer_antipad',transfer=match);paired.append(gap)
      if not any({v['uuid'] for v in f['signal_vias']}=={v['uuid'] for v in match['signal_vias']} for f in fields):fields.append(match)
     else:active.append(gap)
    exact=[]
    for field in fields:
     for segment in measured.get('path_segments',[]):
      if not any(pointseg(v['position_mm'],segment['a'],segment['b'])<v['land_mm']/2+.5 for v in field['signal_vias']):continue
      ref=p.In2_Cu if segment['layer'] in (p.B_Cu,p.In1_Cu) else p.In1_Cu
      for side in (-.5,0,.5):exact.extend(exact_intervals(segment,side,ref,field))
    measured['reference_gaps']=active;measured['intrinsic_paired_transfer_antipad_samples']=paired;measured['intrinsic_paired_transfer_fields']=fields;measured['exact_paired_field_void_intervals']=exact
    measured['non_antipad_reference_coverage']=measured.get('ground_covered_samples',0)/(measured.get('reference_samples',0)-len(retained_own)-len(paired)) if measured.get('reference_samples',0)>len(retained_own)+len(paired) else None
    if paired:summaries.append(dict(channel=row['name'],leg=leg,classified_samples=len(paired),transfer_fields=fields,exact_lane_void_intervals=exact,exact_affected_length_mm_by_lane={str(side):sum(q['length_mm'] for q in exact if q['copper_width_lane_fraction']==side) for side in (-.5,0,.5)}))
  return dict(fields=summaries,meaning='Only intrinsic matched P/N transfer antipads with same physical transition,<=1.2mm station pitch,no other reference copper/positive zone,and one anchored two-plane GND stitch within2mm ofboth legs. Exact lane intervals clip saved filled polygons (including holes) inside the tightly bounded field. Raw void samples and coverage remain; unrelated/remote vias never qualify.')

 def transition_stitches(self,channels):
  vias=[q for q in self.b.GetTracks() if q.GetClass()=='PCB_VIA' and q.GetNetname()=='GND']
  reference=lambda name:'In2.Cu' if name in ('B.Cu','In1.Cu') else 'In1.Cu'
  rows=[]
  for row in channels:
   for leg in ('positive','negative'):
    for signal in row[leg].get('vias',[]):
     refs=[reference(signal[k]) for k in ('from_layer','to_layer')];required=refs[0]!=refs[1];candidates=[]
     for q in vias:
      position=xy(q.GetPosition());distance=math.dist(position,signal['position_mm'])
      if distance>5:continue
      connected=self.find(uid(q))==self.find(uid(self.ground_anchor));planes={self.b.GetLayerName(ly):self.fill('GND',ly,position) for ly in (p.In1_Cu,p.In2_Cu)}
      candidates.append(dict(uuid=uid(q),position_mm=position,distance_mm=distance,through_via=bool(q.IsOnLayer(p.F_Cu) and q.IsOnLayer(p.B_Cu)),connected_to_J1_GND=connected,plane_contacts=planes,valid=connected and all(planes.values()) and q.IsOnLayer(p.F_Cu) and q.IsOnLayer(p.B_Cu)))
     candidates.sort(key=lambda x:x['distance_mm']);valid=[q for q in candidates if q['valid']];nearest=valid[0] if valid else None
     rows.append(dict(channel=row['name'],leg=leg,signal_via=signal,reference_layers=refs,changes_reference_plane=required,nearest_physical_GND_via=candidates[0] if candidates else None,nearest_valid_return_stitch=nearest,engineering_distance_target_mm=2.0,return_transition_screen_met=not required or bool(nearest and nearest['distance_mm']<=2.0)))
  return dict(transitions=rows,meaning='Independent saved copper/vias and anchored individual filled GND islands. F/In1 andB/In2 reference changes require a through-GND stitch contacting both planes.2mm is an explicit engineering screen, not a universal USB specification. Legacy F-to-In2 retains In1 reference; all actual nearest distances remain visible.')

 def detector_contract(self):
  expected={'U9903':{'1':'USB2_UP_OE_N','2':'GND','3':'USB2_VREF','4':'USB2_VBUS_SENSE','5':'USB2_VREF','6':'H_V33'},
   'R9909':{'1':'VBUS_IN','2':'USB2_VBUS_SENSE'},'R9910':{'1':'USB2_VBUS_SENSE','2':'GND'},
   'R9903':{'1':'VBUS_IN','2':'GND'},'R9904':{'1':'USB2_UP_OE_N','2':'H_V33'},
   'C67':{'1':'VBUS_IN','2':'GND'},'C9906':{'1':'H_V33','2':'GND'},'C9909':{'1':'USB2_VREF','2':'GND'},'U11':{'5':'VBUS_IN'}}
  checks=[]
  for ref,pins in expected.items():
   for pin,net in pins.items():
    actual=next((q.GetNetname() for q in self.fps[ref].Pads() if q.GetNumber()==pin),None) if ref in self.fps else None;checks.append(dict(reference=ref,pin=pin,expected_net=net,actual_net=actual,matches=actual==net))
  values={ref:self.fps[ref].GetValue() if ref in self.fps else None for ref in ('U9903','R9909','R9910','R9903','R9904','C67','C9909')}
  value_checks={'B_comparator':'TLV3011BIDBVR' in (values['U9903'] or ''),'top220k':values['R9909']=='220k','bottom100k':values['R9910']=='100k','raw_bleeder10k':values['R9903']=='10k','OE_pullup100k':values['R9904']=='100k','raw100nF':(values['C67'] or '').startswith('100nF'),'REF1nF':(values['C9909'] or '').startswith('1nF')}
  raw_allowed={('J10',pin) for pin in ('A4','A9','B4','B9')}|{('U11','5'),('C67','1'),('R9903','1'),('R9909','1')}
  raw_actual={(f.GetReference(),q.GetNumber()) for f in self.b.GetFootprints() for q in f.Pads() if q.GetNetname()=='VBUS_IN'}
  def connected(source,target):
   try:a,c=self.pad(*source),self.pad(*target)
   except (KeyError,StopIteration):return False
   if a.GetNetname()!=c.GetNetname():return False
   if a.GetNetname()=='GND':return self.find(uid(a))==self.find(uid(c))
   pending=[a];seen=set()
   while pending:
    q=pending.pop();key=uid(q)
    if key in seen:continue
    seen.add(key)
    if key==uid(c):return True
    pending.extend(t for t in list(self.cn.GetConnectedTracks(q))+list(self.cn.GetConnectedPads(q)) if t.GetNetname()==a.GetNetname())
   return False
  links=[(('U9903','1'),('U9902','6')),(('U9903','1'),('R9904','1')),(('U9903','3'),('U9903','5')),(('U9903','5'),('C9909','1')),
   (('U9903','4'),('R9909','2')),(('U9903','4'),('R9910','1')),(('U9903','6'),('U10','20')),(('U9903','2'),('J1','1')),
   (('R9904','2'),('U9903','6')),(('C9906','1'),('U9903','6')),(('C9906','2'),('J1','1')),(('C9909','2'),('J1','1')),
   (('C67','2'),('J1','1')),(('R9903','2'),('J1','1')),(('R9910','2'),('J1','1')),(('R9909','1'),('J10','A4')),(('R9903','1'),('J10','A4')),(('C67','1'),('J10','A4'))]
  physical=[dict(source=s,target=t,connected=connected(s,t)) for s,t in links] if all(ref in self.fps for ref in expected) else []
  passed=all(x['matches'] for x in checks) and all(value_checks.values()) and raw_actual==raw_allowed and len(physical)==len(links) and all(x['connected'] for x in physical)
  return dict(contract_met=passed,pin_net_checks=checks,values=values,value_checks=value_checks,raw_VBUS_pads=sorted(raw_actual),unexpected_raw_VBUS_pads=sorted(raw_actual-raw_allowed),missing_raw_VBUS_pads=sorted(raw_allowed-raw_actual),native_copper_links=physical,meaning='Literal host-VBUS divider/bleeder/ESD and local-H33 gate separation; no direct rawVBUS/local5V net join is permitted. NativeDRC remains authoritative for accidental cross-net copper shorts. Comparator/ESD silicon is not copper-unioned. Manual fitting and analogue detach waveforms remain bench holds.')

 def spacing(self):
  records=load_records(self.b)
  for net,layer,node,poly in self.zones:
   if net in ('','GND') or layer not in LAYERS:continue
   for ix in range(poly.OutlineCount()):
    rings=[poly.COutline(ix)]+[poly.CHole(ix,h) for h in range(poly.HoleCount(ix))]
    for h,ring in enumerate(rings):
     pts=[xy(ring.CPoint(k)) for k in range(ring.PointCount())]
     for k,(a,c) in enumerate(zip(pts,pts[1:]+pts[:1])):records.append(dict(id=f'{node}:ring{h}:edge{k}',net=net,pair=channel(net),layer=self.b.GetLayerName(layer),a=a,b=c,width=0,kind='filled-zone-boundary'))
  for t in self.b.GetTracks():
   if t.GetClass()=='PCB_TRACK' and t.GetLayer() in (p.In1_Cu,p.In2_Cu):records.append(dict(id=uid(t),net=t.GetNetname(),pair=None,layer=self.b.GetLayerName(t.GetLayer()),a=xy(t.GetStart()),b=xy(t.GetEnd()),width=p.ToMM(t.GetWidth()),kind=t.GetClass()))
  for r in records:r['pair']=channel(r['net'])
  # Spatial candidates avoid quadratic examination of remote power fields.
  grid=collections.defaultdict(list);pitch=4
  for ix,r in enumerate(records):
   x0=min(r['a'][0],r['b'][0])-r['width']/2;x1=max(r['a'][0],r['b'][0])+r['width']/2;y0=min(r['a'][1],r['b'][1])-r['width']/2;y1=max(r['a'][1],r['b'][1])+r['width']/2
   for x in range(math.floor(x0/pitch),math.floor(x1/pitch)+1):
    for y in range(math.floor(y0/pitch),math.floor(y1/pitch)+1):grid[x,y].append(ix)
  minima={};bounded={};seen=set()
  for ix,r in enumerate(records):
   if not r['pair']:continue
   x0=min(r['a'][0],r['b'][0])-1.6;x1=max(r['a'][0],r['b'][0])+1.6;y0=min(r['a'][1],r['b'][1])-1.6;y1=max(r['a'][1],r['b'][1])+1.6
   candidates={j for x in range(math.floor(x0/pitch),math.floor(x1/pitch)+1) for y in range(math.floor(y0/pitch),math.floor(y1/pitch)+1) for j in grid.get((x,y),[])}
   for j in candidates:
    s=records[j]
    if s['layer']!=r['layer'] or s['net'] in ('','GND') or channel(s['net'])==r['pair'] or s['net'].endswith('_NC') or s['net'].startswith(('NC_','IO_NC_')):continue
    key0=tuple(sorted((ix,j)))
    if key0 in seen:continue
    seen.add(key0);target=1.270 if s['net'] in ('H_XI','H_XO') else .762
    applicable=[e for e in self.regions if r['net'] in e['nets'] and s['net'] in e['nets']]
    for one in split_at_regions(r,applicable):
     for two in split_at_regions(s,applicable):
      gap,a,c=closest(one,two);cover=sorted(one['inside_regions']&two['inside_regions']);key=(r['pair'],s['pair'] or ('clock' if target>1 else 'ordinary'),r['layer']);row=dict(channel=r['pair'],other_channel=s['pair'],nets=[r['net'],s['net']],items=[r['id'],s['id']],layer=r['layer'],edge_spacing_mm=gap,target_mm=target,nearest_points_mm=[a,c],package_exceptions=cover)
      dest=bounded if cover and gap<target else minima
      if key not in dest or gap<dest[key]['edge_spacing_mm']:dest[key]=row
  violations=[r for r in minima.values() if r['edge_spacing_mm']<r['target_mm']-.0001]
  return dict(outside_package_minima=list(minima.values()),violations=violations,bounded_package_exceptions=list(bounded.values()),regions=self.regions,meaning='TI engineering spacing screen:0.762mm USB2-to-unrelated signal/power,1.270mm to hubclock. Explicit legacy FS deviations remain reported. Closest conservative pad edges may require exact native geometry review.')

def apply_fs_exceptions(problems,channels,board_hash,source_hashes,path):
 if not path:return problems,dict(applied=[],supplied=False)
 try:
  payload=path.read_bytes();artifact_hash=hashlib.sha256(payload).hexdigest();data=json.loads(payload);assert data.get('schema')=='v09-fs-numeric-exceptions-1','Unexpected schema'
  assert data.get('approved') is True and data.get('approved_by'),'Explicit reviewer approval required'
  assert data.get('board_sha256')==board_hash,'Saved-board hash mismatch'
  assert data.get('auditor_sha256')==digest(__file__),'Auditor hash mismatch'
  assert data.get('source_sha256')==source_hashes,'Source snapshot mismatch'
  applied=[];remaining=list(problems)
  for name,approval in data.get('channels',{}).items():
   row=next(q for q in channels if q['name']==name);assert row['speed']=='FS','HS exceptions are forbidden'
   assert set(approval)<={'primary_applicability','bench_disposition','maximum_skew_mm','maximum_length_mm'},'Unsupported exception field'
   assert 'https://' in str(approval.get('primary_applicability','')) and approval.get('bench_disposition') and not str(approval['bench_disposition']).startswith('REVIEW REQUIRED'),'Actual primary URLs and bench disposition required'
   numeric=[]
   for metric,messages in [('maximum_skew_mm',['literal centreline skew target exceeded','skew target exceeded']),('maximum_length_mm',['length recommendation exceeded'])]:
    if metric not in approval:continue
    if metric=='maximum_skew_mm':values=[row.get('skew_mm'),row['literal_centreline_model'].get('skew_mm')]
    else:values=[q.get('total_length_mm') for q in (row['positive'],row['negative'])]+[row['literal_centreline_model'].get(k) for k in ('positive_mm','negative_mm')]
    assert all(q is not None for q in values),'Cannot except an unmeasured/open channel'
    actual=max(values);assert math.isfinite(float(approval[metric])) and actual<=float(approval[metric])+1e-8,'Reviewed numeric bound exceeded'
    for suffix in messages:
     message=name+':'+suffix
     if message in remaining:remaining.remove(message);numeric.append(dict(metric=metric,actual=actual,reviewed_bound=approval[metric],original_hold=message))
   applied.append(dict(channel=name,approved_by=data['approved_by'],numeric_comparisons=numeric,primary_applicability=approval['primary_applicability'],bench_disposition=approval['bench_disposition']))
  assert digest(path)==artifact_hash,'Exception artifact changed during read'
  return remaining,dict(supplied=True,source=str(path),sha256=artifact_hash,applied=applied,limits='Only explicitly reviewed FS numeric comparisons are disposed. HS, reference/stub/native/polarity/analogue-detector and changed-input holds remain active.')
 except Exception as exc:return problems+['Invalid FS numeric-exception file:'+str(exc)],dict(supplied=True,source=str(path),error=str(exc),applied=[])

def normalized(value):return json.loads(json.dumps(value,sort_keys=True))
def value_digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def connector_escape_identity(a,cells):
 cell=cells['base'];source_path=ROOT/cell['board'];source=p.LoadBoard(str(source_path));dx,dy=[p.FromMM(v) for v in cell['position_mm']]
 expected='567650a0-6924-455d-8657-45598002d8bb';track=next((t for t in a.b.GetTracks() if uid(t)==expected),None)
 def signature(t,shift):return(t.GetNetname(),int(t.GetLayer()),t.GetWidth(),*sorted([(t.GetStart().x-shift[0],t.GetStart().y-shift[1]),(t.GetEnd().x-shift[0],t.GetEnd().y-shift[1])]))
 horizontal=next((t for t in a.b.GetTracks() if uid(t)=='03fcc21a-416a-4e36-9f6c-8d5efa7e6dac'),None)
 def preserved_part(item):return bool(item and item.GetClass()=='PCB_TRACK' and any(t.GetClass()=='PCB_TRACK' and signature(t,(0,0))==signature(item,(dx,dy)) for t in source.GetTracks()))
 preserved=preserved_part(track) and preserved_part(horizontal)
 return dict(source_board=str(source_path.relative_to(ROOT)),source_board_sha256=digest(source_path),saved_source_track_uuid=expected,preserved_source_geometry=preserved,track_start_mm=xy(track.GetStart()) if track else None,track_end_mm=xy(track.GetEnd()) if track else None,track_length_mm=p.ToMM(track.GetLength()) if track else None,track_width_mm=p.ToMM(track.GetWidth()) if track else None,following_horizontal=dict(uuid=uid(horizontal),start_mm=xy(horizontal.GetStart()),end_mm=xy(horizontal.GetEnd()),length_mm=p.ToMM(horizontal.GetLength()),preserved_source_geometry=preserved_part(horizontal)) if horizontal else None,reviewed_left_edge_mm=218.2,previous_218p7_clipped_edge_minimum_mm=.3973932046178168,previous_clipped_nearest_points_mm=[[218.7,102.85],[219.13,103.1]],static_CC1_Rd_reference='R60',static_CC1_Rd_ohm=5100,CC1_Rd_contract_met=a.fps['R60'].GetValue()=='5.1k' and a.pad('R60','1').GetNetname()=='USB_CC1' and a.pad('R60','2').GetNetname()=='GND',scope='Reviewed J10 connector-side own-net escape only; unchanged other box edges. New post-ESD routes near x214.3625/x213.3 remain outside. All actual spacing minima remain in the spacing report.')
def legacy_review_evidence(a,channels,stitches,spacing,cells):
 """Prove the named source copper and report the exact reviewable findings."""
 cell=cells['base'];source_path=ROOT/cell['board'];source=p.LoadBoard(str(source_path));dx,dy=[p.FromMM(v) for v in cell['position_mm']]
 mapping=cell['net_mapping'];proof={};findings=[]
 def copper(board,nets,shift):
  out=[]
  for t in board.GetTracks():
   if t.GetNetname() not in nets:continue
   pts=sorted([(t.GetStart().x-shift[0],t.GetStart().y-shift[1]),(t.GetEnd().x-shift[0],t.GetEnd().y-shift[1])]);out.append((t.GetClass(),t.GetNetname(),int(t.GetLayer()),t.GetWidth(),t.GetDrillValue() if t.GetClass()=='PCB_VIA' else None,*pts))
  return sorted(out,key=repr)
 for name,prefix in [('audio','P1'),('dynamixel','P2')]:
  nets={prefix+'_DP',prefix+'_DM'};assert not any(mapping.get(n,n)!=n for n in nets),'Unexpected legacy source net mapping'
  baseline=copper(source,nets,(0,0));saved=copper(a.b,nets,(dx,dy));unchanged=baseline==saved
  row=next(r for r in channels if r['name']==name);samples=[]
  for leg in ('positive','negative'):
   for gap in row[leg].get('reference_gaps',[]):
    ref=source.GetLayerID(gap['reference_layer']);q=gap['point_mm'];v=p.VECTOR2I(p.FromMM(q[0])-dx,p.FromMM(q[1])-dy);fills=[]
    for z in source.Zones():
     if z.GetIsRuleArea() or not z.IsOnLayer(ref):continue
     ps=z.GetFilledPolysList(ref)
     if any(ps.UnitSet(i).Contains(v) for i in range(ps.OutlineCount())):fills.append(z.GetNetname())
    samples.append(dict(leg=leg,current_point_mm=q,source_point_mm=xy(v),reference_layer=gap['reference_layer'],source_filled_nets=sorted(set(fills)),source_GND_present='GND' in fills))
  proof[name]=dict(source_copper_unchanged=unchanged,source_tracks=sum(r[0]=='PCB_TRACK' for r in baseline),source_vias=sum(r[0]=='PCB_VIA' for r in baseline),saved_tracks=sum(r[0]=='PCB_TRACK' for r in saved),saved_vias=sum(r[0]=='PCB_VIA' for r in saved),source_copper_signature_sha256=value_digest(baseline),saved_copper_signature_sha256=value_digest(saved),gap_samples=samples,all_active_gap_samples_also_lack_source_GND=all(not r['source_GND_present'] for r in samples))
  if not unchanged:continue
  for leg in ('positive','negative'):
   gaps=row[leg].get('reference_gaps',[]);matching=[s for s in samples if s['leg']==leg]
   if gaps and all(not s['source_GND_present'] for s in matching):findings.append(dict(kind='reference',channel=name,leg=leg,hold=name+':'+leg+':reference gaps',actual=dict(gap_samples=gaps,source_reference_samples=matching,reference_coverage=row[leg].get('reference_coverage'))))
  for item in stitches['transitions']:
   if item['channel']==name and not item['return_transition_screen_met']:findings.append(dict(kind='return',channel=name,leg=item['leg'],hold=name+':'+item['leg']+':reference-transition ground stitch missing/distant',actual=item))
 for item in spacing['violations']:
  channel_name={'P1':'audio','P2':'dynamixel'}.get(item['channel'])
  if channel_name and item['other_channel'] in (None,'P1','P2') and proof[channel_name]['source_copper_unchanged']:
   findings.append(dict(kind='spacing',channel=channel_name,actual=item))
 evidence=normalized(dict(source_board=str(source_path.relative_to(ROOT)),source_board_sha256=digest(source_path),base_offset_mm=cell['position_mm'],channels=proof,total_source_tracks=sum(r['source_tracks'] for r in proof.values()),all_named_source_copper_unchanged=all(r['source_copper_unchanged'] for r in proof.values()),limits='Source identity proves preserved geometry, not bench validation. Source gap samples test actual saved source fill; absent GND is not an electrical PASS.'))
 return evidence,normalized(findings)

def apply_legacy_review(problems,board_hash,source_hashes,identity,findings,spacing,path):
 if not path:return problems,dict(supplied=False,applied=[],unreviewed_spacing_violations=spacing['violations'])
 try:
  payload=path.read_bytes();artifact_hash=hashlib.sha256(payload).hexdigest();data=json.loads(payload)
  assert data.get('schema')=='v09-legacy-source-prototype-review-1','Unexpected legacy review schema'
  assert data.get('approved') is True and data.get('approved_by'),'Explicit reviewer approval required'
  assert data.get('board_sha256')==board_hash,'Saved-board hash mismatch'
  assert data.get('auditor_sha256')==digest(__file__),'Auditor hash mismatch'
  assert data.get('source_sha256')==source_hashes,'Source snapshot mismatch'
  assert identity['all_named_source_copper_unchanged'] and identity['total_source_tracks']==34,'Named34-track source identity not proven'
  assert data.get('source_identity_sha256')==value_digest(identity),'Source-copper/reference evidence mismatch'
  assert data.get('reviewed_findings')==normalized(findings),'Exact reviewed findings mismatch'
  assert all(r['kind'] in ('reference','return','spacing') and r['channel'] in ('audio','dynamixel') for r in findings),'Unpermitted legacy finding'
  assert 'https://' in str(data.get('primary_applicability','')) and data.get('bench_disposition') and not str(data['bench_disposition']).startswith('REVIEW REQUIRED'),'Actual primary applicability and prototype/bench disposition required'
  remaining=list(problems);applied=[]
  for r in findings:
   if r['kind']=='spacing':continue
   hold=r['hold']
   if hold in remaining:remaining.remove(hold);applied.append(r)
  reviewed_spacing=[r['actual'] for r in findings if r['kind']=='spacing'];unreviewed=[r for r in spacing['violations'] if normalized(r) not in reviewed_spacing]
  applied.extend(r for r in findings if r['kind']=='spacing')
  if not unreviewed and 'Outside-package engineering spacing deviations' in remaining:remaining.remove('Outside-package engineering spacing deviations')
  assert digest(path)==artifact_hash,'Legacy review artifact changed during read'
  return remaining,dict(supplied=True,source=str(path),sha256=artifact_hash,approved_by=data['approved_by'],applied=applied,primary_applicability=data['primary_applicability'],bench_disposition=data['bench_disposition'],unreviewed_spacing_violations=unreviewed,limits='Reviewed named source-identical audio/Dynamixel prototype deviations only; not measured USB compliance. HS/PWM/native/opens/detector/stubs and FS numeric comparisons are not disposed here. External adapter/rework/board spin may be needed.')
 except Exception as exc:return problems+['Invalid legacy prototype-review file:'+str(exc)],dict(supplied=True,source=str(path),error=str(exc),applied=[],unreviewed_spacing_violations=spacing['violations'])

def selected_provenance():
 """Bind actual selected CELLS/dependencies rather than an obsolete motor cell."""
 generator=ROOT/'source/generator'
 before={q.resolve():digest(q) for q in generator.glob('*.py')}
 module=importlib.import_module('rev09')
 assert isinstance(module.CELLS,dict) and module.CELLS,'Selected revision has no CELLS'
 assert isinstance(module.PARTS,list),'Selected revision has no inventory'
 sources={Path(__file__).resolve()}
 for name in ('build_v09.py','label_v09.py','route_v09.py','route_v09_usb.py'):
  q=(generator/name).resolve();assert q.exists(),f'Missing selected source:{q}';sources.add(q)
 for loaded in tuple(sys.modules.values()):
  file=getattr(loaded,'__file__',None)
  if file:
   q=Path(file).resolve()
   if q.parent==generator.resolve() and q.suffix=='.py':sources.add(q)
 cells={}
 for name,cell in sorted(module.CELLS.items()):
  q=(ROOT/cell['board']).resolve();assert q.exists(),f'Missing selected cell PCB:{q}';sources.add(q)
  file=getattr(cell['module'],'__file__',None)
  if file:sources.add(Path(file).resolve())
  cells[name]=dict(board=str(q.relative_to(ROOT)),offset=cell['offset'],prefix=cell['prefix'],position_mm=list(cell['position']),excluded_refs=sorted(cell.get('exclude',())),net_mapping=cell.get('nets',{}),selected_source_part_refs=sorted(v['ref'] for v in cell['module'].PARTS if v['ref'] not in cell.get('exclude',())))
 hashes={str(q.relative_to(ROOT)):digest(q) for q in sorted(sources)}
 changed=[str(q) for q in sources if q.parent==generator.resolve() and before.get(q)!=digest(q)]
 assert not changed,'Selected source changed during import:'+str(changed)
 inventory_hash=hashlib.sha256(json.dumps(module.PARTS,sort_keys=True,separators=(',',':')).encode()).hexdigest()
 return hashes,cells,inventory_hash

def main():
 ap=argparse.ArgumentParser();ap.add_argument('board',nargs='?',type=Path,default=ROOT/'revisions/v0.9/kicad/robot_pdb.kicad_pcb');ap.add_argument('--fs-exceptions',type=Path);ap.add_argument('--legacy-review',type=Path);ap.add_argument('--output',type=Path,default=ROOT/'outputs/v09-order-preparation/usb-channel-audit.json');args=ap.parse_args();selected_exceptions=args.fs_exceptions
 if selected_exceptions is None:
  default_exceptions=ROOT/'revisions/v0.9/prototype-usb-fs-exceptions.json';selected_exceptions=default_exceptions if default_exceptions.exists() else None
 selected_legacy=args.legacy_review
 if selected_legacy is None:
  default_legacy=ROOT/'revisions/v0.9/prototype-usb-legacy-review.json';selected_legacy=default_legacy if default_legacy.exists() else None
 a=Audit(args.board)
 hashes,selected_cells,inventory_hash=selected_provenance();evidence_paths=[args.board.with_suffix('.kicad_pro'),args.board.parent.parent/'composition.json',args.board.parent.parent/'integration-routing.json',args.board.parent.parent/'drc.rpt'];artifact_hashes={str(q.resolve()):digest(q) for q in evidence_paths if q.exists()};channels=[]
 for name,pn,nn,source,target,speed in SPECS:
  pos=a.measure(pn,(source[0],source[1]),(target[0],target[1]));neg=a.measure(nn,(source[0],source[2]),(target[0],target[2]));row=dict(name=name,speed=speed,target_applicability='Manufacturer HighSpeed layout recommendations' if speed=='HS' else 'Conservative engineering comparison; these HS numeric targets are not asserted as universal12Mbps FullSpeed PCB limits',positive=pos,negative=neg,pair_geometry=a.pair_geometry(pos,neg))
  if pos.get('centreline_path_found') and neg.get('centreline_path_found'):row.update(skew_mm=abs(pos['total_length_mm']-neg['total_length_mm']),engineering_skew_target_mm=1.25,skew_target_met=abs(pos['total_length_mm']-neg['total_length_mm'])<=1.25,package_to_package_150mm_met=max(pos['total_length_mm'],neg['total_length_mm'])<=150)
  nomp=a.measure(pn,(source[0],source[1]),(target[0],target[1]),False);nomn=a.measure(nn,(source[0],source[2]),(target[0],target[2]),False)
  row['literal_centreline_model']={k:v for k,v in [('positive_mm',nomp.get('total_length_mm')),('negative_mm',nomn.get('total_length_mm')),('skew_mm',abs(nomp['total_length_mm']-nomn['total_length_mm']) if nomp.get('centreline_path_found') and nomn.get('centreline_path_found') else None)]}
  row['partial_HS_disposition']='Passive analogue-switch leg; skew/length recorded but complete J10-to-U10 channel is the HS acceptance boundary. Opposite signed leg errors may intentionally compensate.' if speed=='HS' else 'Legacy/new FullSpeed comparison remains explicitly reported.'
  row['length_model_note']='Contact graph includes actual touching same-net copper; literal centreline is also reported. Different answers indicate pad shortcuts/overlap that must be reviewed before declaring skew.'
  channels.append(row)
 # A partial U11-to-switch measurement has an intentional connector-side
 # continuation. Classify only pieces actually used by complete A/B paths;
 # never turn an unused physical loop into a continuation by net name alone.
 host_partial=next(q for q in channels if q['name']=='host_package')
 for leg in ('positive','negative'):
  full=[q[leg] for q in channels if q['name'] in ('upstream_A','upstream_B')]
  identity=lambda d:(d['uuid'],tuple(sorted((tuple(d.get('a',())),tuple(d.get('b',()))))))
  used={identity(d) for q in full for d in q.get('path_segments',[])}
  partial=host_partial[leg];continued=0
  for d in partial.get('off_path_segments',[]):
   if d['unbounded_stub'] and identity(d) in used:d['connector_side_continuation_outside_partial_measurement']=True;d['unbounded_stub']=False;continued+=d['length_mm']
  partial['connector_side_continuation_mm']=continued
  if 'unbounded_off_path_mm' in partial:partial['unbounded_off_path_mm']=sum(d['length_mm'] for d in partial['off_path_segments'] if d['unbounded_stub'])
 # Analogue switch continuity is a declared silicon boundary, not fabricated copper.
 chain=[];hub=next(r for r in channels if r['name']=='upstream_hub')
 for orientation in ('A','B'):
  host=next(r for r in channels if r['name']=='upstream_'+orientation);row=dict(orientation=orientation,declared_analogue_switch=dict(reference='U9902',positive=['8','1'],negative=['7','2'],select_pin9='GND selects1D',enable_pin6='active low hostVBUS gate'),physical_legs=[host['name'],hub['name']])
  if all(q.get('centreline_path_found') for r in (host,hub) for q in (r['positive'],r['negative'])):
   pp=sum(r['positive']['total_length_mm'] for r in (host,hub));nn=sum(r['negative']['total_length_mm'] for r in (host,hub));row.update(positive_copper_mm=pp,negative_copper_mm=nn,skew_mm=abs(pp-nn),skew_125mm_met=abs(pp-nn)<=1.25,complete_connector_to_hub_150mm_met=max(pp,nn)<=150,meaning='Sum of real external copper legs only; silicon/package delay is not assigned zero or claimed measured.')
  package=next(r for r in channels if r['name']=='host_package')
  if all(q.get('centreline_path_found') for r in (package,hub) for q in (r['positive'],r['negative'])):
   pp=sum(r['positive']['total_length_mm'] for r in (package,hub));nn=sum(r['negative']['total_length_mm'] for r in (package,hub));row.update(ESD_to_hub_positive_mm=pp,ESD_to_hub_negative_mm=nn,ESD_to_hub_150mm_met=max(pp,nn)<=150,connector_alias_additional_positive_mm=host['positive'].get('total_length_mm',0)-package['positive']['total_length_mm'],connector_alias_additional_negative_mm=host['negative'].get('total_length_mm',0)-package['negative']['total_length_mm'])
  if all(r['literal_centreline_model'].get(k) is not None for r in (host,hub) for k in ('positive_mm','negative_mm')):
   lp=sum(r['literal_centreline_model']['positive_mm'] for r in (host,hub));ln=sum(r['literal_centreline_model']['negative_mm'] for r in (host,hub));row.update(literal_signed_P_minus_N_mm=lp-ln,literal_skew_125mm_met=abs(lp-ln)<=1.25,literal_complete_150mm_met=max(lp,ln)<=150)
  chain.append(row)
 switch_expected={'1':'HUB_UP_DP','2':'HUB_UP_DM','6':'USB2_UP_OE_N','7':'USB_DM','8':'USB_DP','9':'GND'};switch_contract={pin:dict(expected_net=net,actual_net=a.pad('U9902',pin).GetNetname(),matches=a.pad('U9902',pin).GetNetname()==net) for pin,net in switch_expected.items()}
 detector=a.detector_contract();transfer_fields=a.own_transfer_fields(channels);stitches=a.transition_stitches(channels);spacing=a.spacing();legacy_identity,legacy_findings=legacy_review_evidence(a,channels,stitches,spacing,selected_cells);connector_identity=connector_escape_identity(a,selected_cells);changed=[k for k,v in hashes.items() if digest(ROOT/k)!=v];changed+=['PCB'] if digest(args.board)!=a.hash else []
 report=dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),board=str(args.board.resolve()),board_sha256=a.hash,source_sha256=hashes,selected_source_cells=selected_cells,selected_inventory_sha256=inventory_hash,related_artifact_sha256=artifact_hashes,related_artifact_note='Hashes bind observed files only; a DRC/ledger file is not asserted to match this board without its own matching PCB hash.',inputs_changed_during_run=changed,board_thickness_mm=a.thick,channels=channels,upstream_orientations=chain,analogue_switch_pin_contract=switch_contract,VBUS_detector=detector,return_transition_stitches=stitches,connector_escape_source_identity=connector_identity,legacy_source_identity=legacy_identity,reviewable_legacy_findings=legacy_findings,intrinsic_transfer_field_review=transfer_fields,spacing=spacing,signal_zone_islands=a.signal_islands,ground_reference_islands=a.ground_islands,criteria=dict(length_mm=150,skew_mm=1.25,nominal_new_width_mm=.165,nominal_new_gap_mm=.300,reference='Saved F→In1 and B→In2 actual GND filled islands, including fill holes and positive zones;0.10mm longitudinal samples across both copper edges/centre. Own via antipads reported separately.'),primary_references={'length_skew':'https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ApplicationNotes/ApplicationNotes/AN26.2-Application-Note-DS00001876C.pdf','TI_USB2_layout':'https://www.ti.com/lit/ds/symlink/ts3usb221a.pdf','hub':'https://cdn-learn.adafruit.com/assets/assets/000/131/435/original/CH334DS1.PDF?1721660148='},connector_alias_bounds_mm={'J10_short_signal_fanout':[218.7,100.95,221.0,103.05]},legacy_scope={'audio_and_DXL':'Preserved source-cell traces include innerIn2 signals. Inner routing is measured/reported as legacy geometry; adjacent-reference and controlled-impedance qualification differ from new F/In1 and B/In2 corridors. No waiver of measured skew/spacing deviations is automatic.','reference_box_policy':'Explicit saved-placement boxes listed in spacing.regions. Source-package/connector boxes only bound local escape exceptions; remote long traces remain subject to actual minima.'},limits=['Native copper contact shortest-path geometry may differ from literal drawn centreline around overlapping bends/pads; both models are reported and neither is a field solution.', 'No automatic fabrication release. Native DRC remains authoritative for copper clearance, via-in-pad, drill floor and annulus.','Every FS source-cell geometry exception remains visible;12Mbps does not make an omitted check a PASS.','Trace endpoints/contact centres and full board thickness model geometry, not package delays/actual field-solver impedance/USB eye.','Ground reference requires an actual individual island connection to J1GND by saved copper anchors/pad contacts and island overlap; a shared GND name alone is insufficient.', 'Reference sampling can miss sub0.10mm voids; positive zones, NPTH/antipads and real fill holes are not replaced by nominal GND zone outlines.','Off-path copper inside documented short USB-C aliases/ESD package bounds is reported separately; any unbounded stub is a review hold.'])
 problems=[]
 if not connector_identity['preserved_source_geometry'] or not connector_identity['CC1_Rd_contract_met']:problems.append('Reviewed connector-escape source geometry/Rd contract changed')
 if not detector['contract_met']:problems.append('VBUS detector literal contract/physical connection mismatch')
 if not all(q['matches'] for q in switch_contract.values()):problems.append('Unexpected analogue switch pin/net assignment')
 for r in channels:
  if not all(q.get('native_connected') and q.get('centreline_path_found') for q in (r['positive'],r['negative'])):problems.append(r['name']+':open/unmodelled physical path')
  if r['speed']!='HS' and r.get('literal_centreline_model',{}).get('skew_mm') is not None and r['literal_centreline_model']['skew_mm']>1.25:problems.append(r['name']+':literal centreline skew target exceeded')
  if r['speed']!='HS' and r.get('skew_target_met') is False:problems.append(r['name']+':skew target exceeded')
  if r['speed']!='HS' and r.get('package_to_package_150mm_met') is False:problems.append(r['name']+':length recommendation exceeded')
  for leg in ('positive','negative'):
   q=r[leg]
   if r['name']=='host_package':continue # This partial measurement intentionally omits connector-side copper; full orientations audit its stubs.
   if q.get('unbounded_off_path_mm',0)>.001:problems.append(r['name']+':'+leg+':unbounded off-path copper')
   if q.get('reference_gaps'):problems.append(r['name']+':'+leg+':reference gaps')
 for row in chain:
  if row.get('literal_skew_125mm_met') is False:problems.append('Upstream'+row['orientation']+':complete literal skew target exceeded')
  if row.get('complete_connector_to_hub_150mm_met') is False or row.get('literal_complete_150mm_met') is False:problems.append('Upstream'+row['orientation']+':complete connector-to-hub length recommendation exceeded')
  if row.get('skew_125mm_met') is False:problems.append('Upstream'+row['orientation']+':combined physical-contact skew target exceeded')
  if row.get('ESD_to_hub_150mm_met') is False:problems.append('Upstream'+row['orientation']+':combined ESD-to-hub length recommendation exceeded')
 for row in stitches['transitions']:
  if not row['return_transition_screen_met']:problems.append(row['channel']+':'+row['leg']+':reference-transition ground stitch missing/distant')
 if spacing['violations']:problems.append('Outside-package engineering spacing deviations')
 if a.signal_islands:problems.append('Signal-filled zones: centreline length model incomplete')
 problems+=['Input changed:'+q for q in changed];report['raw_review_holds']=list(problems);problems,disposition=apply_fs_exceptions(problems,channels,a.hash,hashes,selected_exceptions);report['FS_numeric_disposition']=disposition;problems,legacy_disposition=apply_legacy_review(problems,a.hash,hashes,legacy_identity,legacy_findings,spacing,selected_legacy);report['legacy_prototype_disposition']=legacy_disposition;report['review_holds']=problems;report['status']='REVIEW_HOLDS' if problems else 'GEOMETRY_SCREEN_COMPLETE_WITH_REVIEWED_LEGACY_PROTOTYPE_DEVIATIONS' if legacy_disposition.get('applied') else 'GEOMETRY_SCREEN_COMPLETE_BENCH_QUALIFICATION_REQUIRED';args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,indent=2)+'\n');candidate=dict(schema='v09-fs-numeric-exceptions-1',approved=False,approved_by=None,board_sha256=a.hash,auditor_sha256=digest(__file__),source_sha256=hashes,channels={})
 for row in channels:
  if row['speed']!='FS' or row.get('skew_mm') is None:continue
  skew=max(row['skew_mm'],row['literal_centreline_model'].get('skew_mm') or 0);length=max(row['positive']['total_length_mm'],row['negative']['total_length_mm'],row['literal_centreline_model'].get('positive_mm') or 0,row['literal_centreline_model'].get('negative_mm') or 0)
  if skew<=1.25 and length<=150:continue
  approval=dict(primary_applicability='REVIEW REQUIRED: cite actual FS primary applicability',bench_disposition='REVIEW REQUIRED: explicit bounded engineering disposition')
  if skew>1.25:approval['maximum_skew_mm']=math.ceil(skew*1e6)/1e6
  if length>150:approval['maximum_length_mm']=math.ceil(length*1e6)/1e6
  candidate['channels'][row['name']]=approval
 args.output.with_name('usb-fs-numeric-exception-candidate.json').write_text(json.dumps(candidate,indent=2)+'\n')
 legacy_candidate=dict(schema='v09-legacy-source-prototype-review-1',approved=False,approved_by=None,board_sha256=a.hash,auditor_sha256=digest(__file__),source_sha256=hashes,source_identity_sha256=value_digest(legacy_identity),primary_applicability='REVIEW REQUIRED: cite actual manufacturer guidance and applicability',bench_disposition='REVIEW REQUIRED: explicit bounded prototype risk and bench/fallback disposition',reviewed_findings=legacy_findings)
 args.output.with_name('usb-legacy-prototype-review-candidate.json').write_text(json.dumps(legacy_candidate,indent=2)+'\n')
 print(json.dumps(dict(status=report['status'],board_sha256=a.hash,channels=[dict(name=r['name'],connected=all(q.get('native_connected') and q.get('centreline_path_found') for q in (r['positive'],r['negative'])),P_mm=r['positive'].get('total_length_mm'),N_mm=r['negative'].get('total_length_mm'),skew_mm=r.get('skew_mm')) for r in channels],spacing_deviations=len(spacing['violations']),holds=problems,output=str(args.output)),indent=2));return 1 if problems else 0
if __name__=='__main__':raise SystemExit(main())
