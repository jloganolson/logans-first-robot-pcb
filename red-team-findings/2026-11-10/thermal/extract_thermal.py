"""Dump all copper (every net) and heat-source footprints of the v0.10 board. Run through with_kicad.sh."""
import pcbnew as p, json, sys
b=p.LoadBoard('revisions/v0.10/kicad/robot_pdb.kicad_pcb');mm=p.ToMM
L={p.F_Cu:'F',p.In1_Cu:'In1',p.In2_Cu:'In2',p.B_Cu:'B'}
def polys(ps):
    out=[]
    for i in range(ps.OutlineCount()):
        o=ps.Outline(i);out.append(dict(o=[(mm(o.CPoint(j).x),mm(o.CPoint(j).y)) for j in range(o.PointCount())],
            h=[[(mm(ps.Hole(i,k).CPoint(j).x),mm(ps.Hole(i,k).CPoint(j).y)) for j in range(ps.Hole(i,k).PointCount())] for k in range(ps.HoleCount(i))]))
    return out
d=dict(zones=[],tracks=[],vias=[],pads=[],parts={})
for z in b.Zones():
    for l in z.GetLayerSet().Seq():
        if l in L:d['zones'].append(dict(layer=L[l],polys=polys(z.GetFilledPolysList(l))))
for t in b.GetTracks():
    if t.GetClass()=='PCB_VIA':q=t.GetPosition();d['vias'].append(dict(x=mm(q.x),y=mm(q.y),d=mm(t.GetWidth()),drill=mm(t.GetDrillValue())))
    elif t.GetLayer() in L:s,e=t.GetStart(),t.GetEnd();d['tracks'].append(dict(layer=L[t.GetLayer()],x1=mm(s.x),y1=mm(s.y),x2=mm(e.x),y2=mm(e.y),w=mm(t.GetWidth())))
for f in b.GetFootprints():
    bb=f.GetCourtyard(p.F_Cu).BBox() if f.GetCourtyard(p.F_Cu).OutlineCount() else f.GetBoundingBox(False,False)
    nets=sorted({q.GetNetname() for q in f.Pads() if q.GetNetname()})
    d['parts'][f.GetReference()]=dict(value=f.GetValue(),bbox=[mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom())],nets=nets)
    for q in f.Pads():
        bx=q.GetBoundingBox();d['pads'].append(dict(layers=[L[l] for l in L if q.IsOnLayer(l)],bbox=[mm(bx.GetX()),mm(bx.GetY()),mm(bx.GetRight()),mm(bx.GetBottom())],drill=mm(q.GetDrillSize().x),x=mm(q.GetPosition().x),y=mm(q.GetPosition().y)))
json.dump(d,open(sys.argv[1],'w'));print({k:len(v) for k,v in d.items()})
