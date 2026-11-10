"""Refresh the offline trace reader in the v0.4.1 course from the KiCad exports.
Run from the repository root with Python 3, lxml and Poppler's pdftocairo.
"""
import re,json,math,html,subprocess,tempfile
from pathlib import Path
from collections import defaultdict
from lxml import etree as ET
assets=Path(__file__).resolve().parent
temporary=tempfile.TemporaryDirectory()
out=Path(temporary.name)
subprocess.run(['pdftocairo','-svg','schematic/robot_pdb_schematic.pdf',str(out/'sheet.svg')],check=True)
def parse(file):
    stack=[]
    for tok in re.findall(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+',Path(file).read_text()):
        if tok=='(':
            node=[]
            if stack:stack[-1].append(node)
            stack.append(node)
        elif tok==')':root=stack.pop()
        else:stack[-1].append(json.loads(tok) if tok.startswith('"') else tok)
    return root
def kids(e,k):return [a for a in e if isinstance(a,list) and a[0]==k]
def val(e,k,default=()):return next((a[1:] for a in kids(e,k)),default)
def xy(e,k):return tuple(map(float,val(e,k)[:2]))
def n(x):return f'{float(x):.4f}'.rstrip('0').rstrip('.') or '0'
def coords(pts):return ' '.join(','.join(n(v) for v in point) for point in pts)
def path(d):return f'<path d="{d}"/>'
def esc(s):return html.escape(s,quote=True)
def at(e):
    a=[*map(float,val(e,'at'))]
    return (a+[0])[:3]
def rect(x,y,w,h,rx=0):return f'<rect x="{n(x)}" y="{n(y)}" width="{n(w)}" height="{n(h)}" rx="{n(rx)}"/>'
def circle(x,y,r):return f'<circle cx="{n(x)}" cy="{n(y)}" r="{n(r)}"/>'
pcb=parse('kicad/robot_pdb.kicad_pcb')
sch=parse('kicad/robot_pdb.kicad_sch')
netnames={k[1]:k[2] for k in kids(pcb,'net')}
layers=['F.Cu','In1.Cu','In2.Cu','B.Cu']
def layerOf(p):
    a=val(p,'layers')
    return [l for l in layers if l in a or '*.Cu' in a or 'F&B.Cu' in a and l in ('F.Cu','B.Cu')]
def netnum(o):return val(o,'net',['0'])[0]
zones=defaultdict(list); tracks=defaultdict(list); pads=defaultdict(list); vias=[]; drills=[]; outlines=[];labels=[]; detail={};owners=defaultdict(list)
for zone in kids(pcb,'zone'):
    for poly in kids(zone,'filled_polygon'):
        pt=[p[1:] for p in kids(val(poly,'pts'),'xy')]
        zones[val(poly,'layer')[0]].append(f'<path class="pour" data-n="{netnum(zone)}" d="M{coords(pt)}Z" fill-rule="evenodd"/>')
for s in kids(pcb,'segment'):
    tracks[val(s,'layer')[0]].append(f'<path class="trace" data-n="{netnum(s)}" d="M{coords([xy(s,"start"),xy(s,"end")])}" stroke-width="{val(s,"width")[0]}"/>')
for v in kids(pcb,'via'):
    x,y=xy(v,'at');size=float(val(v,'size')[0]);drill=float(val(v,'drill')[0]);net=netnum(v);vias.append(f'<g class="via" data-n="{net}">{circle(x,y,size/2)}<circle cx="{n(x)}" cy="{n(y)}" r="{n(drill/2)}" class="hole"/></g>')
for f in kids(pcb,'footprint'):
    ref=next(t[2] for t in kids(f,'fp_text') if t[1]=='reference');x,y,a=at(f);angle=math.radians(-a)
    def world(p):
        u,v=p;return x+u*math.cos(angle)-v*math.sin(angle),y+u*math.sin(angle)+v*math.cos(angle)
    geom=''.join(path('M'+coords([world(xy(k,'start')),world(xy(k,'end'))])) for k in kids(f,'fp_line') if val(k,'layer')==['F.Fab'])
    outlines.append(f'<g>{geom}</g>')
    rr=next(t for t in kids(f,'fp_text') if t[1]=='reference');tx,ty=world(xy(rr,'at'));labels.append(f'<text x="{n(tx)}" y="{n(ty)}">{ref}</text>')
    detail[ref]={'board':[x,y],'pins':{}}
    for p in kids(f,'pad'):
        ls=layerOf(p)
        if not ls:continue
        px,py,pr=at(p);cx,cy=world((px,py));w,h=xy(p,'size');nn=netnum(p)
        pin=p[1];key=ref+'.'+pin;shape=p[3]
        radius={'oval':min(w,h)/2,'circle':w/2,'roundrect':min(w,h)*float(val(p,'roundrect_rratio',[0])[0])}.get(shape,0)
        obj=rect(-w/2,-h/2,w,h,radius)
        for g in val(p,'primitives'):
            if g[0]=='gr_circle':
                u,v=xy(g,'center');obj+=circle(u,v,math.dist((u,v),xy(g,'end')))
            if g[0]=='gr_poly':obj+=path('M'+coords([t[1:] for t in kids(val(g,'pts'),'xy')])+'Z')
        title=esc(key+' · '+(netnames[nn] or 'unconnected')) if pin else esc(ref+' mechanical hole')
        transform=f'translate({n(cx)} {n(cy)}) rotate({n(-pr)})'
        pg=f'<g class="pad" data-n="{nn}" data-pin="{esc(key)}" transform="{transform}"><title>{title}</title>{obj}</g>'
        if p[2]!='np_thru_hole':
            for l in ls:pads[l].append(pg)
        if val(p,'drill'):
            dd=[float(i) for i in val(p,'drill') if isinstance(i,str) and i not in ['oval']];w1,h1=dd[0],dd[-1]
            drills.append(f'<g transform="{transform}">{rect(-w1/2,-h1/2,w1,h1,min(w1,h1)/2)}</g>')
        if pin and int(nn):
            d=detail[ref]['pins'].setdefault(pin,{'n':nn,'b':[]});assert d['n']==nn;d['b'].append([round(cx,4),round(cy,4)])
            if key not in owners[nn]:owners[nn].append(key)
layersvg={l:''.join(zones[l]+tracks[l]+pads[l]) for l in layers}
board=''.join(f'<g data-layer="{l}"'+(' hidden=""' if i else '')+'>'+layersvg[l]+'</g>' for i,l in enumerate(layers))+'<g>'+''.join(vias)+'</g><g class="holes">'+''.join(drills)+'</g><g class="outlines">'+''.join(outlines)+'</g><g class="refs">'+''.join(labels)+'</g>'
# Schematic pin and attached wire endpoints are taken from the native sheet.
lib={a[1]:a for a in kids(val(sch,'lib_symbols'),'symbol')};sPins=[]; verified=0
def roundxy(p):return tuple(round(c,3) for c in p)
wires={roundxy(xy(val(w,'pts'),'xy')):roundxy(list(map(float,kids(val(w,'pts'),'xy')[1][1:]))) for w in kids(sch,'wire')}
snames={roundxy(xy(l,'at')):l[1] for l in kids(sch,'label')}
for s in kids(sch,'symbol'):
    props={p[1]:p[2] for p in kids(s,'property')};ref=props['Reference'];sx,sy,a=at(s);assert a==0
    detail[ref]['sheet']=[sx,sy];detail[ref]['value']=props['Value']
    for unit in kids(lib[val(s,'lib_id')[0]],'symbol'):
        for pin in kids(unit,'pin'):
            pn=val(pin,'number')[0];pd=detail[ref]['pins'].get(pn)
            if not pd:continue
            px,py,pa=at(pin);x,y=roundxy((sx+px,sy-py));nn=pd['n'];key=ref+'.'+pn
            end=wires.get((x,y),(x,y)); lab=snames.get(end)
            if lab:assert lab==netnames[nn],(key,lab,netnames[nn]);verified+=1
            pd['s']=[x,y];pd['name']=val(pin,'name')[0];pd['wire']=end!= (x,y)
            # Label text extends away from the pin at the end of its short wire.
            vx,vy=end[0]-x,end[1]-y
            length=math.hypot(vx,vy) or 1
            reach=len(netnames[nn])*1.03 if lab else 0
            tip=(end[0]+vx/length*reach,end[1]+vy/length*reach)
            sPins.append(f'<g data-pin="{esc(key)}" data-n="{nn}" class="sheetpin"><title>{esc(key)} · {esc(netnames[nn])}</title><path d="M{coords([(x,y),end])}" class="stub"/><circle cx="{x}" cy="{y}" r="0.68"/><path d="M{coords([(x,y),tip])}" class="hitstub"/></g>')
assert verified==len(kids(sch,'wire')),(verified,len(kids(sch,'wire')))
# Preserve the KiCad PDF artwork and its placement, group consecutive strokes with identical graphics state.
doc=ET.parse(str(out/'sheet.svg'));root=doc.getroot()
for parent in list(root.iter()):
    if len(parent)<2:continue
    prev=None;attr=None;ds=[]
    def finish():
        if prev is not None:prev.set('d',' '.join(ds))
    for el in list(parent):
        if el.tag.endswith('}path') and el.get('fill')=='none':
            key=tuple((k,v) for k,v in el.attrib.items() if k!='d')
            d=el.get('d')
            if '0.00719857' in el.get('transform',''):
                d=re.sub(r'-?\d+\.\d+',lambda m:str(round(float(m[0]))),d)
            if prev is not None and attr==key and len(ds)<120:
                ds.append(d);parent.remove(el)
            else:
                finish();prev=el;attr=key;ds=[d]
        else:finish();prev=None;ds=[]
    finish()
# Keep native geometry as a single vector image, separate from click targets.
import gzip,base64
sheetBytes=ET.tostring(root)
geometry=json.dumps({'detail':detail,'nets':netnames,'owners':owners,'board':board,'sheetPins':''.join(sPins),'sheetImage':base64.b64encode(gzip.compress(sheetBytes,compresslevel=5,mtime=0)).decode()},separators=(',',':'))
print('pins with schematic wires',verified,'nets',len(owners),'zones',sum(map(len,zones.values())),'tracks',sum(map(len,tracks.values())),'vias',len(vias),'rendered PDF bytes',len(sheetBytes))

guide=Path('docs/BOARD_GUIDE_v0.4.1.html')
document=guide.read_text()
begin='<!-- board-reader:start -->'
end='<!-- board-reader:end -->'
reader=(begin+'<style>'+assets.joinpath('reader.css').read_text()+'</style>'
        +assets.joinpath('section.html').read_text()
        +'<script id="br-data" type="application/json">'+geometry.replace('<','\\u003c')+'</script>'
        +'<script>'+assets.joinpath('reader.js').read_text()+'</script>'+end)
if begin in document:
    start=document.index(begin)
    document=document[:start]+reader+document[document.index(end,start)+len(end):]
else:
    heading=re.search(r'<h3[^>]*>Dive 01 [^<]*</h3>',document)
    if not heading:raise ValueError('Input chapter heading missing')
    document=document[:heading.end()]+reader+document[heading.end():]
guide.write_text(document)
