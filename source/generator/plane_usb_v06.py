from pathlib import Path
import math,json
import pcbnew as p
from cells import Board
from indexed_fixer import IndexedFixer
root=Path(__file__).resolve().parents[2];path=root/'revisions/v0.6/kicad/robot_pdb.kicad_pcb';b=p.LoadBoard(str(path));g=Board.__new__(Board);g.b=b;g.nets={};g.zones=[];dead=[]
# Finish the global top ground island stitching, using filled copper, not nominal outlines.
fx=IndexedFixer(b);added=[]
for z in list(b.Zones()):
 if z.GetNetname()!='GND' or z.GetLayer()!=p.F_Cu or z.GetAssignedPriority()!=0:continue
 poly=z.GetFilledPolysList(p.F_Cu)
 for i in range(poly.OutlineCount()):
  line=poly.COutline(i);bb=line.BBox();x0,y0=p.ToMM(bb.GetOrigin());w,h=p.ToMM(bb.GetSize())
  if max(w,h)>50:continue
  old=[t for t in b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname()=='GND' and line.PointInside(t.GetPosition())]
  if old:continue
  points=[(x0+w/2+dx*.3,y0+h/2+dy*.3) for dx in range(-int(w/.6),int(w/.6)+1) for dy in range(-int(h/.6),int(h/.6)+1)]
  points.sort(key=lambda q:math.dist(q,(x0+w/2,y0+h/2)))
  for q in points:
   pt=p.VECTOR2I(*[p.FromMM(v) for v in q])
   if line.PointInside(pt) and all(fx.free(L,'GND',*q,.3) for L in (p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)):
    g.via('GND',*q,.6,.3);fx._index=None;added.append(q);print('ground stitch',i,q,flush=True);break
  else:print('narrow island',i,x0,y0,w,h,flush=True)
# The long USB upstream traces are effectively uncoupled over the 0.109mm dielectric.
# JLC calculator: JLC041621-2116, 2oz outer / 1oz inner, 45 ohm single-ended
# width = 7.69 mil = 0.195326mm. Use that width; connector/IC pads remain unchanged.
for t in b.GetTracks():
 if t.GetClass()=='PCB_TRACK' and t.GetNetname() in ('USB_DP','USB_DM'):t.SetWidth(p.FromMM(.2))
# Keep coplanar pours away so the specified non-coplanar model applies. L2 is GND.
z=p.ZONE(b);z.SetLayer(p.F_Cu);z.SetIsRuleArea(True);z.SetDoNotAllowCopperPour(True);z.SetDoNotAllowTracks(False);z.SetDoNotAllowVias(False);z.SetDoNotAllowPads(False);z.SetDoNotAllowFootprints(False)
ol=z.Outline();ol.NewOutline()
for x,y in [(208.3,80.3),(221.8,80.3),(221.8,83.7),(208.3,83.7)]:ol.Append(p.FromMM(x),p.FromMM(y))
b.Add(z)
# Record actual factory stackup in the source board as well as order documentation.
# KiCad7 exposes stackup through the board's S-expression after this save.
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b)
s=path.read_text();s=s.replace('(thickness 0.035)', '(thickness 0.07)')
# Replace the existing stackup block with a measured manufacturer construction.
a=s.find('    (stackup');depth=0;end=None
if a<0:a=s.index('  (setup')+len('  (setup');end=a
for i in range(a,len(s)) if end is None else []:
 if s[i]=='(':depth+=1
 elif s[i]==')':
  depth-=1
  if depth==0:end=i+1;break
stack='''    (stackup
      (layer "F.SilkS" (type "Top Silk Screen"))
      (layer "F.Paste" (type "Top Solder Paste"))
      (layer "F.Mask" (type "Top Solder Mask") (thickness 0.01))
      (layer "F.Cu" (type "copper") (thickness 0.07))
      (layer "dielectric 1" (type "prepreg") (thickness 0.109) (material "2116 RC54%") (epsilon_r 4.16) (loss_tangent 0.02))
      (layer "In1.Cu" (type "copper") (thickness 0.03))
      (layer "dielectric 2" (type "core") (thickness 1.23) (material "FR4") (epsilon_r 4.6) (loss_tangent 0.02))
      (layer "In2.Cu" (type "copper") (thickness 0.03))
      (layer "dielectric 3" (type "prepreg") (thickness 0.109) (material "2116 RC54%") (epsilon_r 4.16) (loss_tangent 0.02))
      (layer "B.Cu" (type "copper") (thickness 0.07))
      (layer "B.Mask" (type "Bottom Solder Mask") (thickness 0.01))
      (layer "B.Paste" (type "Bottom Solder Paste"))
      (layer "B.SilkS" (type "Bottom Silk Screen"))
      (copper_finish "ENIG") (dielectric_constraints yes)
    )'''
s=s[:a]+stack+s[end:];path.write_text(s)
b=p.LoadBoard(str(path));g.b=b;g.nets={};g.track('GND',[(14.1,54.5),(14.7,56.7)],.6);p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(path),b);p.WriteDRCReport(b,str(path.parent.parent/'drc.rpt'),p.EDA_UNITS_MILLIMETRES,True)
(path.parent.parent/'stackup.json').write_text(json.dumps({'factory_stackup':'JLC041621-2116','outer_copper_mm':.07,'inner_copper_mm':.03,'outer_dielectric_mm':.109,'core_mm':1.23,'usb_width_mm':.2,'factory_calculator_ohms_single_ended':45,'top_ground_stitches_added':added},indent=2))
