#!/usr/bin/env python3
"""Narrowest-neck check for power pours. Run through with_kicad.sh.

KiCad's DRC calls a pour connected if it is one piece, however thin. Signal
tracks routed across a pour can leave a hair-width neck that carries the whole
load (v0.11 build 9e2ac58e2b29 had a 0.37 mm neck feeding both XL330 plugs).

For each listed run this removes every part of the net's filled copper that is
narrower than `width` (a morphological opening), then asks whether the source
pad and each load pad are still joined through what is left, using vias and
through-hole pads to change layer. A PASS means a path at least `width` wide
exists everywhere between them; it says nothing about resistance.

Usage: pour_width.py board.kicad_pcb     (prints one line per run; exit 1 on a failure)
"""
import sys
import pcbnew as p

# net, source part, load parts, minimum width in mm
RUNS=[('+5V_SRV','L4',('J301','J302'),2.0),
      ('+12V_SRV','L5',('J401','J402'),2.0),
      ('+24V','L1',('J3',),1.5),     # past J3's own ground pins and pegs the copper is four gaps of 0.9-4 mm on each of two layers, about 9.4 mm in all
      ('PWM_5V','L7002',('J7004','J7005','J7006'),1.5)]
MM=p.FromMM;mm=p.ToMM
CU=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.B_Cu)

def check_run(b,net,src,loads,width):
 r=MM(width/2);parent={}
 def find(a):
  parent.setdefault(a,a)
  while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
  return a
 def join(a,c):parent[find(a)]=find(c)
 opened={}
 for L in CU:
  u=p.SHAPE_POLY_SET()
  for z in b.Zones():
   if z.GetNetname()==net and z.IsOnLayer(L):u.BooleanAdd(z.GetFilledPolysList(L),p.SHAPE_POLY_SET.PM_FAST)
  if u.OutlineCount()==0:continue
  u.Simplify(p.SHAPE_POLY_SET.PM_FAST);u.Deflate(r,16);u.Inflate(r,16);u.Simplify(p.SHAPE_POLY_SET.PM_FAST);opened[L]=u
 def touch(node,pt,layers,reach):
  for L in layers:
   u=opened.get(L)
   if u is None:continue
   for i in range(u.OutlineCount()):
    if u.Contains(pt,i,reach):join(node,('pour',L,i))
 for t in b.GetTracks():
  if t.GetNetname()!=net:continue
  if t.GetClass()=='PCB_VIA':touch(('via',t.GetPosition().x,t.GetPosition().y),t.GetPosition(),CU,t.GetWidth()//2)
  elif mm(t.GetWidth())>=width:                       # a track at least as wide as the limit counts as a path
   node=('trk',id(t))
   for q in (t.GetStart(),t.GetEnd()):touch(node,q,(t.GetLayer(),),t.GetWidth()//2);join(node,('pt',t.GetLayer(),q.x//1000,q.y//1000))
 pads={}
 for f in b.GetFootprints():
  for q in f.Pads():
   if q.GetNetname()!=net:continue
   node=('pad',f.GetReference(),q.GetNumber(),q.GetPosition().x,q.GetPosition().y);s=q.GetSize()
   touch(node,q.GetPosition(),[L for L in CU if q.IsOnLayer(L)],min(s.x,s.y)//2);pads.setdefault(f.GetReference(),[]).append(node)
 if src not in pads:return dict(net=net,ok=False,why='no pad of %s on this net'%src)
 roots={find(n) for n in pads[src]}
 cut=[ref for ref in loads if not any(find(n) in roots for n in pads.get(ref,[]))]
 return dict(net=net,source=src,loads=list(loads),min_width_mm=width,ok=not cut,not_reached=cut)

def check_board(b):return [check_run(b,*run) for run in RUNS]

if __name__=='__main__':
 res=check_board(p.LoadBoard(sys.argv[1]))
 for r in res:print('PASS' if r['ok'] else 'FAIL',r)
 sys.exit(0 if all(r['ok'] for r in res) else 1)
