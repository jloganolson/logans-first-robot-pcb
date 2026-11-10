import pcbnew, json, sys
b=pcbnew.LoadBoard('revisions/v0.9/kicad/robot_pdb.kicad_pcb')
mm=pcbnew.ToMM
NETS=set(sys.argv[2].split(','))
L={pcbnew.F_Cu:'F',pcbnew.In1_Cu:'In1',pcbnew.In2_Cu:'In2',pcbnew.B_Cu:'B'}
def polyset(ps):
    out=[]
    for i in range(ps.OutlineCount()):
        o=ps.Outline(i); pts=[(mm(o.CPoint(j).x),mm(o.CPoint(j).y)) for j in range(o.PointCount())]
        holes=[]
        for k in range(ps.HoleCount(i)):
            h=ps.Hole(i,k); holes.append([(mm(h.CPoint(j).x),mm(h.CPoint(j).y)) for j in range(h.PointCount())])
        out.append({'o':pts,'h':holes})
    return out
d={'zones':[],'tracks':[],'vias':[],'pads':[]}
for z in b.Zones():
    if z.GetNetname() not in NETS: continue
    for l in z.GetLayerSet().Seq():
        if l in L:
            d['zones'].append({'net':z.GetNetname(),'layer':L[l],'polys':polyset(z.GetFilledPolysList(l)),'conn':z.GetPadConnection(),'spoke':mm(z.GetThermalReliefSpokeWidth()),'gap':mm(z.GetThermalReliefGap())})
for t in b.GetTracks():
    n=t.GetNetname()
    if n not in NETS: continue
    if t.GetClass()=='PCB_VIA':
        p=t.GetPosition(); d['vias'].append({'net':n,'x':mm(p.x),'y':mm(p.y),'drill':mm(t.GetDrillValue()),'d':mm(t.GetWidth())})
    elif t.GetLayer() in L:
        s,e=t.GetStart(),t.GetEnd(); d['tracks'].append({'net':n,'layer':L[t.GetLayer()],'x1':mm(s.x),'y1':mm(s.y),'x2':mm(e.x),'y2':mm(e.y),'w':mm(t.GetWidth()),'arc':t.GetClass()=='PCB_ARC'})
for fp in b.GetFootprints():
    for p in fp.Pads():
        n=p.GetNetname()
        if n not in NETS: continue
        ps=pcbnew.SHAPE_POLY_SET()
        p.TransformShapeToPolygon(ps, pcbnew.F_Cu if p.IsOnLayer(pcbnew.F_Cu) else pcbnew.B_Cu, 0, 20000)
        pos=p.GetPosition()
        d['pads'].append({'ref':fp.GetReference(),'num':p.GetNumber(),'net':n,'x':mm(pos.x),'y':mm(pos.y),'tht':p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH,'drill':mm(p.GetDrillSize().x),'layers':[L[l] for l in L if p.IsOnLayer(l)],'poly':polyset(ps),'zc':p.GetZoneConnection() if hasattr(p,'GetZoneConnection') else None,'sx':mm(p.GetSize().x),'sy':mm(p.GetSize().y)})
json.dump(d,open(sys.argv[1],'w'))
print({k:len(v) for k,v in d.items()})
for p in d['pads']:
    if p['ref'] in('J1','J2','J4','J5','F1','F2','J3','Q1','L1','Q2','Q3'): print(p['ref'],p['num'],p['net'],p['x'],p['y'],'tht' if p['tht'] else 'smd',p['drill'],p['sx'],p['sy'],p['layers'],'zc',p['zc'])
print(set((z['net'],z['layer'],z['conn'],z['spoke'],z['gap']) for z in d['zones']))
