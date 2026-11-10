import pcbnew, collections
b=pcbnew.LoadBoard('revisions/v0.9/kicad/robot_pdb.kicad_pcb'); mm=pcbnew.ToMM
rows=[]
for fp in b.GetFootprints():
    cy=fp.GetCourtyard(pcbnew.F_Cu) if fp.GetLayer()==pcbnew.F_Cu else fp.GetCourtyard(pcbnew.B_Cu)
    bb=cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False,False)
    rows.append((fp.GetReference(),fp.GetValue()[:26],mm(bb.GetX()),mm(bb.GetY()),mm(bb.GetRight()),mm(bb.GetBottom()),fp.GetLayerName(), any(p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH for p in fp.Pads()), cy.OutlineCount()>0))
tot=sum((r[4]-r[2])*(r[5]-r[3]) for r in rows)
print('footprints',len(rows),'bbox area sum mm2',round(tot), 'layers',collections.Counter(r[6] for r in rows),'no courtyard',sum(not r[8] for r in rows))
xs=[r[2] for r in rows]+[r[4] for r in rows]; ys=[r[3] for r in rows]+[r[5] for r in rows]
print('extent x',min(xs),max(xs),'y',min(ys),max(ys))
# occupancy raster 1mm
import math
occ=[[0]*229 for _ in range(231)]
for r in rows:
    for y in range(max(0,int(r[3])),min(230,int(math.ceil(r[5])))):
        for x in range(max(0,int(r[2])),min(228,int(math.ceil(r[4])))): occ[y][x]=1
def area(x0,x1,y0,y1): return sum(occ[y][x] for y in range(y0,y1) for x in range(x0,x1))
print('occupied total',area(0,228,0,230))
for band in [(0,18),(18,60),(60,100),(100,130),(130,178),(178,230)]:
    print('y band',band,'occupied',area(0,228,*band),'of',228*(band[1]-band[0]), 'left half',area(0,114,*band),'right half',area(114,228,*band))
print('lower-right free block x>113,y 160..230 occ',area(113,228,160,230))
print('items with y_max>178:')
for r in sorted(rows,key=lambda r:-r[5]):
    if r[5]>178: print('  ',r[0],r[1],[round(v,1) for v in r[2:6]],'THT' if r[7] else '')
print('edge-near (<3mm) parts:')
for r in rows:
    d=min(r[2],r[3],228-r[4],230-r[5])
    if d<3: print('  ',r[0],r[1],[round(v,1) for v in r[2:6]],'edge dist',round(d,2),'THT' if r[7] else 'SMD')
# tallest y span items
print('largest parts:')
for r in sorted(rows,key=lambda r:-(r[4]-r[2])*(r[5]-r[3]))[:14]: print('  ',r[0],r[1],[round(v,1) for v in r[2:6]])
