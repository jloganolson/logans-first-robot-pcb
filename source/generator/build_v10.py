"""Derive the value-engineered v0.10 candidate from the saved v0.9 board.

Run through source/fabrication/with_kicad.sh. This never touches v0.9. It is a
controlled transformation, not a regeneration: every copper item keeps its
position relative to every other item. Changes, all recorded in
revisions/v0.10/derivation.json:

 1. Whole board translated -17 mm in Y (the top 18 mm of v0.9 was empty) and
    the outline cut to 228 x 195 mm. Two bottom mounting holes move up.
 2. The 70 vias with 0.20 mm drill / 0.40 mm land become 0.30 mm drill /
    0.50 mm land, JLCPCB's standard no-surcharge size. This passes DRC under
    the 1 oz clearance rule below (it did not under the 2 oz rule with
    0.60 mm lands).
 3. Stackup set to the factory default JLC04161H-7628, 1 oz outer / 0.5 oz
    inner. The order flow states JLC04161H-3313 is a special stackup that
    Economic assembly does not accept. To keep the upstream High-Speed USB
    pair near 90 ohm over the thicker 0.2104 mm prepreg, its uniform
    0.165 mm segments are widened in place to 0.275 mm (centre lines and
    pitch unchanged, gap 0.19 mm). JLCPCB's impedance calculator gives
    90 ohm at 0.269 mm / 0.175 mm on this stack. Segments that would break clearance
    stay narrow together with their partner-leg segment, and are listed.
 4. L1 becomes cjiang FEXL1510A-100M (24 A / 29 A, 8.6 mohm), a
    Coilcraft XAL1510 equivalent on the unchanged footprint. The LM5146
    valley limit set by R13 allows up to about 18.7 A peak in an overload,
    so a 15.5 A part (first tried) is not adequate.
 5. U2 becomes LM5146RGYR and FB2 becomes GZ1608D601TF (same footprints).
 6. R13 (Thor current-limit resistor) 180 -> 220 ohm so the limit cannot start below 8 A.
No exports, uploads or purchases happen here.
"""
import collections,hashlib,json,math,re,shutil,subprocess,sys
from pathlib import Path
import pcbnew as p

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'revisions/v0.9/kicad';DST=ROOT/'revisions/v0.10/kicad'
SRC_SHA='ad206a2e675dba909d7661468f507ba976eb8f9994b74af22e48c716b53a18c3'
SHIFT_MM=-17.0;SIZE_MM=(228.0,195.0)
# Ground stitching vias that fall outside the shortened outline (v0.9 coordinates).
OFFBOARD_GND_VIAS=[(78.0,213.0),(108.0,221.0)]
# v0.9 used 0.20 mm for 2 oz copper. JLCPCB's 1 oz multilayer minimum is 0.09 mm;
# 0.15 mm keeps margin and admits the 0.16 mm left beside nine enlarged via lands.
CLEARANCE_MM=.15
# Upstream High-Speed pair (connector -> switch -> hub). Downstream ports are Full-Speed and stay as routed.
HS_NETS=('USB_DP','USB_DM','HUB_UP_DP','HUB_UP_DM');HS_OLD_MM=.165;HS_NEW_MM=.275
PARTNER={'USB_DP':'USB_DM','USB_DM':'USB_DP','HUB_UP_DP':'HUB_UP_DM','HUB_UP_DM':'HUB_UP_DP'}
VIA_DRILL_MM=.30;VIA_LAND_MM=.50
MOVED_HOLES={'H7003':(3.0,191.5),'H7004':(109.0,191.5)}
PART_CHANGES={
 'L1':dict(value='10uH FEXL1510A-100M',lcsc='C5378597',mpn='cjiang FEXL1510A-100M',
  old=dict(value='10uH 22A 60V',lcsc='C3911782',mpn='Coilcraft XAL1510-103MED')),
 'U2':dict(value='LM5146RGYR',lcsc='C3188679',mpn='Texas Instruments LM5146RGYR',
  old=dict(value='LM5146QRGYRQ1',lcsc='C1850329',mpn='TI LM5146-Q1 100V sync buck controller')),
 # LM5146 valley limit = (I_RDSON*R13 +/- comparator offset)/Rds(on). At 180 ohm the worst corner starts limiting
 # near 6.7-7.8 A of load at 27 V in; 220 ohm keeps every corner above 8 A (about 8.5 A) with a worst-case
 # inductor peak near 26 A, inside L1's 29 A saturation rating. 220 ohm is also a Basic part (no feeder fee).
 'R13':dict(value='220',lcsc='C22962',mpn='0603 1% 220',old=dict(value='180',lcsc='C22828',mpn='0603 1% 180')),
 'FB2':dict(value='600R',lcsc='C1002',mpn='Sunlord GZ1608D601TF',
  old=dict(value='600R',lcsc='C133527',mpn='Sunlord UPZ1608E601-1R0TF')),
}
STACK=[('F.Cu','(thickness 0.07)','(thickness 0.035)'),
 ('dielectric 1','(thickness 0.109) (material "2116 RC54%") (epsilon_r 4.16)','(thickness 0.2104) (material "7628 RC49%") (epsilon_r 4.4)'),
 ('In1.Cu','(thickness 0.03)','(thickness 0.0152)'),
 ('dielectric 2','(thickness 1.23)','(thickness 1.065)'),
 ('In2.Cu','(thickness 0.03)','(thickness 0.0152)'),
 ('dielectric 3','(thickness 0.109) (material "2116 RC54%") (epsilon_r 4.16)','(thickness 0.2104) (material "7628 RC49%") (epsilon_r 4.4)'),
 ('B.Cu','(thickness 0.07)','(thickness 0.035)')]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def vec(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))

def main():
 src=SRC/'robot_pdb.kicad_pcb';assert sha(src)==SRC_SHA,'v0.9 board is not the reviewed copy'
 if DST.exists():shutil.rmtree(DST)
 shutil.copytree(SRC,DST)
 out=DST/'robot_pdb.kicad_pcb';b=p.LoadBoard(str(out));log=dict(source_board_sha256=SRC_SHA)
 # 0. drop stitching vias that would land outside the new outline
 gone=[]
 for t in list(b.GetTracks()):
  if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND' and any(abs(p.ToMM(t.GetPosition().x)-x)<1e-3 and abs(p.ToMM(t.GetPosition().y)-y)<1e-3 for x,y in OFFBOARD_GND_VIAS):gone.append(t);b.Remove(t)
 assert len(gone)==len(OFFBOARD_GND_VIAS),gone
 log['removed_offboard_gnd_vias_v09_mm']=OFFBOARD_GND_VIAS
 # 1. translate everything, then cut the outline
 d=vec(0,SHIFT_MM);n=0;dead=[]
 for group in (b.GetFootprints(),b.GetTracks(),b.Zones(),b.GetDrawings()):
  for item in list(group):item.Move(d);n+=1
 for item in list(b.GetDrawings()):
  if item.GetLayer()==p.Edge_Cuts:dead.append(item);b.Remove(item)
 edge=p.PCB_SHAPE(b);edge.SetShape(p.SHAPE_T_RECT);edge.SetStart(vec(0,0));edge.SetEnd(vec(*SIZE_MM));edge.SetLayer(p.Edge_Cuts);edge.SetWidth(p.FromMM(.1));b.Add(edge)
 fps={f.GetReference():f for f in b.GetFootprints()}
 for ref,xy in MOVED_HOLES.items():fps[ref].SetPosition(vec(*xy))
 renamed=0
 for item in b.GetDrawings():
  if item.GetClass()=='PCB_TEXT' and 'v0.9' in item.GetText():item.SetText(item.GetText().replace('v0.9','v0.10'));renamed+=1
 log['translation']=dict(shift_mm=[0,SHIFT_MM],items=n,outline_mm=SIZE_MM,moved_holes=MOVED_HOLES,revision_texts=renamed)
 # 2. free-tier via lands
 changed=[]
 for t in b.GetTracks():
  if t.GetClass()=='PCB_VIA' and p.ToMM(t.GetDrillValue())<.29:
   assert abs(p.ToMM(t.GetWidth())-.4)<1e-6;t.SetDrill(p.FromMM(VIA_DRILL_MM));t.SetWidth(p.FromMM(VIA_LAND_MM))
   changed.append([round(v,4) for v in p.ToMM(t.GetPosition())]+[t.GetNetname()])
 log['via_lands']=dict(count=len(changed),old_drill_mm=.2,new_drill_mm=VIA_DRILL_MM,old_land_mm=.4,new_land_mm=VIA_LAND_MM,vias=sorted(changed))
 # 4. part changes are value/supplier only; every footprint is unchanged
 for ref,c in PART_CHANGES.items():fps[ref].SetValue(c['value'])
 log['part_changes']=PART_CHANGES
 b.GetDesignSettings().SetBoardThickness(p.FromMM(1.6))
 pro=json.loads((SRC/'robot_pdb.kicad_pro').read_text());cls=pro['net_settings']['classes'][0];assert cls['name']=='Default' and cls['clearance']==.2
 cls['clearance']=CLEARANCE_MM;profile=(json.dumps(pro,indent=2)+'\n').encode()
 log['rules']=dict(default_clearance_mm=dict(old=.2,new=CLEARANCE_MM,reason='1 oz copper process; see source comment'))
 b.SetFileName(str(out));p.SaveBoard(str(out),b);(DST/'robot_pdb.kicad_pro').write_bytes(profile)
 # 3. stackup, as text so the saved file states the factory build
 text=out.read_text();start=text.index('(stackup');end=text.index('(copper_finish',start) if '(copper_finish' in text[start:start+3000] else text.index('\n    )',start)
 block=text[start:end]
 for layer,a,z in STACK:
  line=next(l for l in block.splitlines() if '(layer "%s"'%layer in l);assert a in line,(layer,line)
  block=block.replace(line,line.replace(a,z))
 out.write_text(text[:start]+block+text[end:]);(DST/'robot_pdb.kicad_pro').write_bytes(profile)
 log['stackup']=dict(factory_name='JLC04161H-7628',outer_copper_oz=1,inner_copper_oz=.5,outer_dielectric_mm=.2104,core_mm=1.065)
 # schematic fields follow the same part changes
 sch=DST/'robot_pdb.kicad_sch';s=sch.read_text()
 for ref,c in PART_CHANGES.items():
  m=re.search(r'\(property "Reference" "%s"'%ref,s);assert m,ref
  a=s.rfind('(symbol (lib_id',0,m.start());z=s.find('\n  (symbol (lib_id',m.end());z=len(s) if z<0 else z;blk=s[a:z]
  for key,prop in (('value','Value'),('lcsc','LCSC'),('mpn','MPN'),('footprint','Footprint')):
   if key in c and c['old'].get(key,c[key])!=c[key]:
    before='(property "%s" "%s"'%(prop,c['old'][key]);assert blk.count(before)==1,(ref,prop,blk.count(before))
    blk=blk.replace(before,'(property "%s" "%s"'%(prop,c[key]))
  s=s[:a]+blk+s[z:]
 sch.write_text(s.replace('0.9 engineering prototype','0.10 value-engineered candidate'))
 def drc():
  subprocess.run([sys.executable,str(ROOT/'source/fabrication/refill_drc.py'),str(out),str(DST.parent/'drc.rpt')],check=True)
  return (DST.parent/'drc.rpt').read_text()
 def hs(board):return [t for t in board.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname() in HS_NETS]
 def key(t):return (t.GetNetname(),t.GetLayer())+tuple(sorted([(t.GetStart().x,t.GetStart().y),(t.GetEnd().x,t.GetEnd().y)]))
 kept=set();rounds=0
 while True:
  wb=p.LoadBoard(str(out));wide=0
  for t in hs(wb):
   target=HS_OLD_MM if key(t) in kept else HS_NEW_MM
   if abs(p.ToMM(t.GetWidth())-HS_OLD_MM)<1e-6 or abs(p.ToMM(t.GetWidth())-HS_NEW_MM)<1e-6:t.SetWidth(p.FromMM(target));wide+=target==HS_NEW_MM
  p.SaveBoard(str(out),wb);(DST/'robot_pdb.kicad_pro').write_bytes(profile);rpt=drc();rounds+=1
  hits=set()
  for block in re.split(r'\n(?=\[)',rpt):
   if not block.startswith(('[clearance]','[shorting_items]','[tracks_crossing]','[hole_clearance]','[copper_edge_clearance]','[solder_mask_bridge]')):continue
   for m in re.finditer(r'@\(([-\d.]+) mm, ([-\d.]+) mm\): Track \[(\w+)\]',block):
    if m[3] in HS_NETS:hits.add((round(float(m[1]),3),round(float(m[2]),3),m[3]))
  if not hits:
   # keep the two legs matched: a segment left narrow takes its parallel partner segment with it
   wb=p.LoadBoard(str(out));segs=hs(wb);add=set()
   for t in segs:
    if key(t) not in kept:continue
    a=p.ToMM(t.GetStart());z=p.ToMM(t.GetEnd());L=math.dist(a,z)
    if L<1e-6:continue
    u=((z[0]-a[0])/L,(z[1]-a[1])/L);other=PARTNER[t.GetNetname()]
    for o in segs:
     if o.GetNetname()!=other or o.GetLayer()!=t.GetLayer() or key(o) in kept or abs(p.ToMM(o.GetWidth())-HS_NEW_MM)>1e-6:continue
     c=p.ToMM(o.GetStart());d=p.ToMM(o.GetEnd());Lo=math.dist(c,d)
     if Lo<1e-6 or abs(u[0]*(d[1]-c[1])-u[1]*(d[0]-c[0]))/Lo>.05:continue
     m=((c[0]+d[0])/2,(c[1]+d[1])/2);along=(m[0]-a[0])*u[0]+(m[1]-a[1])*u[1];perp=abs((m[0]-a[0])*u[1]-(m[1]-a[1])*u[0])
     if .40<=perp<=.53 and -.3<=along<=L+.3:add.add(key(o))
   if not add:break
   kept|=add;continue
  wb=p.LoadBoard(str(out));before=len(kept)
  for t in hs(wb):
   ends={(round(p.ToMM(q.x),3),round(p.ToMM(q.y),3),t.GetNetname()) for q in (t.GetStart(),t.GetEnd())}
   if ends&hits and abs(p.ToMM(t.GetWidth())-HS_NEW_MM)<1e-6:kept.add(key(t))
  assert len(kept)>before and rounds<16,('HS widening does not converge',sorted(hits)[:5])
 wb=p.LoadBoard(str(out));rows=collections.defaultdict(lambda:[0.,0.])
 for t in hs(wb):
  w=p.ToMM(t.GetWidth())
  if abs(w-HS_NEW_MM)<1e-6:rows[t.GetNetname()][0]+=p.ToMM(t.GetLength())
  elif key(t) in kept:rows[t.GetNetname()][1]+=p.ToMM(t.GetLength())
 log['hs_pair_widening']=dict(nets=HS_NETS,old_width_mm=HS_OLD_MM,new_width_mm=HS_NEW_MM,pitch_mm=.465,new_gap_mm=round(.465-HS_NEW_MM,3),drc_rounds=rounds,
  per_net_mm={n:dict(widened=round(a,3),kept_narrow_for_clearance=round(c,3)) for n,(a,c) in sorted(rows.items())},
  kept_narrow_segments=sorted([k[0],k[1]]+[round(p.ToMM(v),4) for q in k[2:] for v in q] for k in kept))
 log['board_sha256']=sha(out);log['schematic_sha256']=sha(sch);log['generator_sha256']=sha(__file__)
 (DST.parent/'derivation.json').write_text(json.dumps(log,indent=1)+'\n')
 print('v0.10 saved',log['board_sha256'],'vias changed',len(changed))

if __name__=='__main__':main()
