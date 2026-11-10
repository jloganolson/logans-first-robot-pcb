"""Build the separate USB3 engineering layout; never modifies the main PDB.

Run through source/fabrication/with_kicad.sh.  This writes an explicit placement,
routes and audit evidence.  RELEASE_HOLDS remain binding: layout generation is
not an assertion of USB3 electrical compliance or fabrication readiness.
"""
import os, math, json, shutil, heapq,hashlib,re,collections
from pathlib import Path
#KiCad7 caches the first project settings in a process. Build in a worker,
#then write scopednetclasses and run DRC in a genuinely fresh process.
if __name__=='__main__' and os.environ.get('USB3_LAYOUT_WORKER')!='1':
    import sys,subprocess
    worker_env=dict(os.environ,USB3_LAYOUT_WORKER='1')
    worker=subprocess.run([sys.executable,str(Path(__file__).resolve())],env=worker_env)
    import usb3_frontend as schema
    folder=Path(__file__).resolve().parents[2]/'revisions/usb3-front-end/kicad'
    project=folder/'usb3_frontend.kicad_pro'
    settings=json.loads(project.read_text()) if project.exists() else {'net_settings':{'classes':[{'name':'Default','clearance':.2,'track_width':.2,'via_diameter':.6,'via_drill':.15}]}}
    default=next(c for c in settings['net_settings']['classes'] if c['name']=='Default')
    ss=dict(default,name='USB3_SS',clearance=.160,diff_pair_width=.204,diff_pair_gap=.160,track_width=.204,via_diameter=.25,via_drill=.15)
    settings.setdefault('board',{}).setdefault('design_settings',{}).setdefault('rules',{}).update(min_via_diameter=.25,min_through_hole_diameter=.15,min_via_annular_width=.05,min_hole_clearance=.20)
    settings['net_settings']['classes']=[c for c in settings['net_settings']['classes'] if c['name']!='USB3_SS']+[ss]
    names=sorted({n for pair in schema.SUPERSPEED_PAIRS+schema.USB2_PAIRS for n in pair})
    settings['net_settings']['netclass_patterns']=[{'netclass':'USB3_SS','pattern':n} for n in names]
    project.write_text(json.dumps(settings,indent=2)+'\n')
    (folder/'usb3_frontend.kicad_dru').write_text('''(version 1)
(rule "Larger through vias retain annulus"
 (condition "A.Type == 'Via' && A.Diameter > 0.251mm")
 (constraint annular_width (min 0.10mm)))
(rule "Larger through vias retain hole clearance"
 (condition "(A.Type == 'Via' && A.Diameter > 0.251mm) || (B.Type == 'Via' && B.Diameter > 0.251mm)")
 (constraint hole_clearance (min 0.25mm)))
''')
    #SaveBoard resets adjacent project defaults even when a later route stage
    #fails. Restore the reviewed manufacturing profile on every worker exit.
    worker.check_returncode()
    script="import pcbnew as p; b=p.LoadBoard("+repr(str(folder/'usb3_frontend.kicad_pcb'))+"); assert b.FindNet('UP_TXP').GetNetClassName()=='USB3_SS'; p.WriteDRCReport(b,"+repr(str(folder.parent/'drc.rpt'))+",p.EDA_UNITS_MILLIMETRES,True)"
    subprocess.run([sys.executable,'-c',script],check=True)
    raise SystemExit(0)
import pcbnew as pcb
import usb3_frontend as circuit
from cells import Board
import fixer
from indexed_fixer import IndexedFixer

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'revisions/usb3-front-end/kicad'
LIB=DEST/'Robot_PDB.pretty'
W,H=140,100
WIDTH,GAP=.204,.160
CHILD_RESERVATION_PATH=ROOT/'source/generator/usb_child_arrival_reservation.json'
CHILD_RESERVATION=json.loads(CHILD_RESERVATION_PATH.read_text())
CHILD_SEGMENTS=[(leg['net'],leg['width_mm'],a,b) for leg in CHILD_RESERVATION['legs'] for a,b in zip(leg['points_mm'],leg['points_mm'][1:])]
SS_EXIT_RESERVATIONS={
    'MIC_RX':('F', [[(64.60,52.64),(64.60,51.9),(64.25,50.4)]]),
    'CAM_RX':('B', [[(69.36,54.55),(72.0,54.25)],[(69.0,71.89),(68.75,69.3)]]),
}
def child_corridor_nearest(q):
    best=(1e9,None)
    for net,width,a,b in CHILD_SEGMENTS:
        d=tuple(b[i]-a[i] for i in (0,1));t=max(0,min(1,sum((q[i]-a[i])*d[i] for i in (0,1))/sum(z*z for z in d)));near=tuple(a[i]+t*d[i] for i in (0,1));best=min(best,(math.dist(q,near)-width/2,near))
    return best
def child_corridor_distance(q):return child_corridor_nearest(q)[0]
def canonical_preboard(text):
    """Keep hierarchy/geometry while ignoring record order and UUID identity.
    Net codes are editor-local IDs; preserve the actual named pad assignments.
    """
    stack=[];root=None
    for token in re.findall(r'"(?:\\.|[^"\\])*"|[^\s()]+|[()]',text):
        if token=='(':
            node=[]
            if stack:stack[-1].append(node)
            else:root=node
            stack.append(node)
        elif token==')':stack.pop()
        else:stack[-1].append(token)
    net_names={node[1]:node[2] for node in root if isinstance(node,list) and len(node)==3 and node[0]=='net'}
    def clean(node):
        if not isinstance(node,list):return node
        if node and node[0] in ('tstamp','uuid','tedit'):return None
        if node and node[0]=='net' and len(node)==3:return ['net',node[2]]
        if node and node[0]=='net' and len(node)==2:return ['net',net_names.get(node[1],node[1])]
        out=[v for item in node if (v:=clean(item)) is not None]
        if out and out[0] in ('kicad_pcb','footprint','pad','segment','via'):
            out=[v for v in out if not isinstance(v,list)]+sorted((v for v in out if isinstance(v,list)),key=lambda v:json.dumps(v,separators=(',',':')))
        return out
    return json.dumps(clean(root),separators=(',',':'))
DATA_NETS={n for pair in circuit.SUPERSPEED_PAIRS+circuit.USB2_PAIRS for n in pair}
fixer.CLR=.16
fixer.VIA_D=.56
fixer.VIA_DR=.30

class USB3Fixer(IndexedFixer):
    def add_track(self,net,pts,w,layer):
        for a,b in zip(pts,pts[1:]):
            if math.dist(a,b)<1e-8:continue
            duplicate=any(t.m_Uuid.AsString() not in getattr(self,'temporary_stub_ids',set()) and t.GetClass()=='PCB_TRACK' and t.GetLayer()==layer and t.GetNetname()==net and abs(pcb.ToMM(t.GetWidth())-w)<1e-6 and ((math.dist(tuple(pcb.ToMM(t.GetStart())),a)<1e-6 and math.dist(tuple(pcb.ToMM(t.GetEnd())),b)<1e-6) or (math.dist(tuple(pcb.ToMM(t.GetStart())),b)<1e-6 and math.dist(tuple(pcb.ToMM(t.GetEnd())),a)<1e-6)) for t in self.b.GetTracks())
            if not duplicate:super().add_track(net,[a,b],w,layer)
    def free(self,layer,net,x,y,r):
        #Exact circular copper clearance to tracks/vias avoids KiCadHitTest's
        #inclusive tangent rejection of already-reserved opposite pair legs.
        #PAD geometry remains KiCad's ownshape test, with its explicitlocalrule.
        if not (pcb.ToMM(self.edge.GetLeft())+r+.5<x<pcb.ToMM(self.edge.GetRight())-r-.5 and pcb.ToMM(self.edge.GetTop())+r+.5<y<pcb.ToMM(self.edge.GetBottom())-r-.5):return False
        if layer==pcb.F_Cu and any(cx-3.5-r<x<cx+3.5+r and 95.6-1.305-r<y<95.6+4.325+r for cx in (20,70)):return False
        pt=pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))
        for it in self._items(layer,net,x,y,r+3):
            if it.m_Uuid.AsString() in getattr(self,'temporary_stub_ids',set()) and it.GetNetname() in getattr(self,'temporary_stub_pairs',{}).get(net,()):continue
            clearance=max(fixer.CLR,(pcb.ToMM(it.GetLocalClearance()) or (.16 if it.GetNetname() in DATA_NETS else .20)) if isinstance(it,pcb.PAD) else (.16 if it.GetNetname() in DATA_NETS else .20))
            if isinstance(it,pcb.PAD):
                if it.HitTest(pt,pcb.FromMM(r+clearance)):return False
            elif it.GetClass()=='PCB_VIA':
                if math.dist((x,y),tuple(pcb.ToMM(it.GetPosition())))<r+pcb.ToMM(it.GetWidth())/2+clearance-1e-6:return False
            else:
                a,b=tuple(pcb.ToMM(it.GetStart())),tuple(pcb.ToMM(it.GetEnd()));dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy;t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/den)) if den else 0
                if math.dist((x,y),(a[0]+t*dx,a[1]+t*dy))<r+pcb.ToMM(it.GetWidth())/2+clearance-1e-6:return False
        for zone in self.b.Zones():
            if zone.GetLayer()==layer and zone.GetNetname() not in (net,'GND') and zone.Outline().Collide(pt,pcb.FromMM(r+fixer.CLR)):return False
        return not getattr(self,'si_guard',None) or self.si_guard((x,y),net,layer,r)
    def via_ok(self,net,x,y):
        for t in self.b.GetTracks():
            if t.GetClass()!='PCB_VIA':continue
            dist=math.dist((x,y),tuple(pcb.ToMM(t.GetPosition())))
            if t.GetNetname()==net and dist<1e-6:return True
            if dist<(fixer.VIA_DR+pcb.ToMM(t.GetDrillValue()))/2+.25-1e-6:return False
        return super().via_ok(net,x,y)
    def add_via(self,net,x,y):
        if any(t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist((x,y),tuple(pcb.ToMM(t.GetPosition())))<1e-6 for t in self.b.GetTracks()):return
        return super().add_via(net,x,y)

def footprint(name,body,pads,description):
    """pads: number,x,y,width,height[,drillx,drilly,type]."""
    lines=[f'(footprint "{name}" (version 20221018) (generator pcbnew) (layer "F.Cu")',f' (descr "{description}")',
           ' (attr smd)',' (fp_text reference "REF**" (at 0 -5) (layer "F.Fab") (effects (font (size .8 .8) (thickness .12))))',
           f' (fp_text value "{name}" (at 0 5) (layer "F.Fab") hide (effects (font (size .8 .8) (thickness .12))))']
    x,y=body
    lines.append(f' (fp_rect (start {-x/2} {-y/2}) (end {x/2} {y/2}) (stroke (width .1) (type default)) (fill none) (layer "F.Fab"))')
    for q in pads:
        num,px,py,sx,sy=q[:5]
        if len(q)>5:
            dx,dy,kind=q[5:]
            shape='oval' if sx!=sy else 'circle'
            drill=f'(drill {dx})' if dx==dy else f'(drill oval {dx} {dy})'
            layer='"*.Cu" "*.Mask"' if kind=='thru_hole' else '"*.Cu" "*.Mask"'
            lines.append(f' (pad "{num}" {kind} {shape} (at {px} {py}) (size {sx} {sy}) {drill} (layers {layer}))')
        else:
            lines.append(f' (pad "{num}" smd rect (at {px} {py}) (size {sx} {sy}) (layers "F.Cu" "F.Paste" "F.Mask") (solder_mask_margin .025))')
    lines.append(')')
    (LIB/(name+'.kicad_mod')).write_text('\n'.join(lines)+'\n')

def quad(name,body,left,bottom,right,top,pitch,span,padsize,ep,description):
    pads=[];i=1;px,py=span;length,width=padsize
    for j in range(left):pads.append((str(i),-px/2,(j-(left-1)/2)*pitch,length,width));i+=1
    for j in range(bottom):pads.append((str(i),(j-(bottom-1)/2)*pitch,py/2,width,length));i+=1
    for j in range(right):pads.append((str(i),px/2,((right-1)/2-j)*pitch,length,width));i+=1
    for j in range(top):pads.append((str(i),((top-1)/2-j)*pitch,-py/2,width,length));i+=1
    pads.append((str(i),0,0,*ep));footprint(name,body,pads,description)

def make_footprints():
    LIB.mkdir(parents=True,exist_ok=True)
    quad('USB5744_56VQFN_7x7_P0.4',(7,7),14,14,14,14,.4,(6.8,6.8),(.75,.200),(4.6,4.6),'MicrochipDS00001855M Fig11-3; manufacturerallowedminimum.200mm padwidth for2ozspacing;EP4.6square')
    quad('TI_RNH0030A_WQFN_2.5x4.5_P0.4',(2.5,4.5),10,5,10,5,.4,(2.4,4.4),(.5,.2),(1.2,3.2),'TI RNH0030A manufacturer example land pattern')
    #Manufacturer's corner chamfers preserve.2mm diagonalclearance.
    rnh=LIB/'TI_RNH0030A_WQFN_2.5x4.5_P0.4.kicad_mod'
    s=rnh.read_text()
    for number,corner in {1:'top_right',10:'bottom_right',11:'top_left',15:'top_right',16:'bottom_left',25:'top_left',26:'bottom_right',30:'bottom_left'}.items():
        lines=s.splitlines()
        for i,line in enumerate(lines):
            if line.startswith(f' (pad "{number}" '):lines[i]=line.replace('smd rect','smd roundrect').replace('(layers ',f'(roundrect_rratio 0) (chamfer_ratio .5) (chamfer {corner}) (layers ')
        s='\n'.join(lines)+'\n'
    rnh.write_text(s)
    quad('TI_RKS0020A_VQFN_2.5x4.5_P0.5',(2.5,4.5),8,2,8,2,.5,(2.3,4.3),(.6,.25),(1.25,3),'TI RKS0020A; pin1 upper left corner top land')
    #RKS numbering begins on top, thenleft2..9,bottom10/11,right12..19,top20.
    f=pcb.FootprintLoad(str(LIB),'TI_RKS0020A_VQFN_2.5x4.5_P0.5')
    ps=sorted(f.Pads(),key=lambda p:int(p.GetNumber()))
    for pad in ps:
        num=int(pad.GetNumber())
        if num<=20:pad.SetNumber(str(num+1 if num<20 else 1))
    pcb.FootprintSave(str(LIB),f)
    quad('TI_RVC0020A_WQFN_3x4_P0.5',(3,4),6,4,6,4,.5,(2.8,3.8),(.6,.2),(1.6,2.6),'TI RVC0020A manufacturer example land pattern')
    pads=[]
    for i in range(1,6):pads.append((str(i),-.385,(i-3)*.5,.55,.3))
    for i in range(6,11):pads.append((str(i),.385,(8-i)*.5,.55,.3))
    footprint('TI_DQA0010A_USON_2.5x1_P0.5',(1,2.5),pads,'TI DQA0010A; rotate body drawing90deg; verify terminal land sizing')
    #USB4056 origin is the PCB edge at connector centre. The footprint's
    #unrotated mating direction is+Y. All dimensions from manufacturer Fig2.
    pads=[]
    for i in range(1,13):pads.append((f'A{i}',-2.75+(i-1)*.5,-7.75,.3,.9))
    for i,x in ((12,-2.8),(9,-1.2),(7,-.4),(6,.4),(4,1.2),(1,2.8)):
        pads.append((f'B{i}',x,-6.49,.6,.6,.4,.4,'thru_hole'))
    for i,x in ((11,-2.4),(10,-1.6),(8,-.8),(5,.8),(3,1.6),(2,2.4)):
        pads.append((f'B{i}',x,-5.84,.6,.6,.4,.4,'thru_hole'))
    for x,y in ((-4.13,-5.95),(4.13,-5.95),(-4.49,-1.55),(4.49,-1.55)):
        pads.append(('S1',x,y,.8,1.4,.5,1.1,'thru_hole'))
    pads.extend([('',-3.6,-7.19,.65,.65,.65,.65,'np_thru_hole'),('',3.6,-7.19,.95,.65,.95,.65,'np_thru_hole')])
    footprint('USB_C_GCT_USB4056-03-A',(9.85,9.87),pads,'GCTUSB4056 drawingA2 sheet2;1.00–1.20mmPCB; mating edge atY=0')
    cfile=LIB/'USB_C_GCT_USB4056-03-A.kicad_mod'
    cfile.write_text(cfile.read_text().replace('(start -4.925 -4.935) (end 4.925 4.935)','(start -4.925 -8.89) (end 4.925 .98)'))
    footprint('L_Bourns_SRP4020TA',(4.5,4.1),[('1',-1.85,0,1.5,2.4),('2',1.85,0,1.5,2.4)],'BournsSRP4020TA recommendedlandpattern:5.2mmouterspan,2.2mmgap,2.4mmheight')
    footprint('Panasonic_POSCAP_D3L',(7.3,4.3),[('1',-3.05,0,2.4,2.9),('2',3.05,0,2.4,2.9)],'Panasonicast-ind-13950730-Sep-26D3L:a2.4,b2.9,c3.7mm;positivepin1')
    #Molex1054500101:24SMT contacts and four platedshieldslots; noNPTH
    #locating pegs. Stocklands compared to the manufacturer's A9drawing.
    f=pcb.FootprintLoad(str(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/'Connector_USB.pretty'),'USB_C_Receptacle_Molex_105450-0101')
    f.SetFPID(pcb.LIB_ID('Robot_PDB','USB_C_Molex_1054500101'))
    f.SetValue('Molex1054500101')
    f.SetDescription('Manufacturer24SMTpattern;shieldslots.60x1.60/.60x2.10;lands1.12x2.12/1.12x2.62=.26annulus;PCBedgeatlocalY+4.40;.8mmPCB')
    for pad in f.Pads():
        if pad.GetNumber()=='S1':pad.SetSize(pcb.VECTOR2I(pcb.FromMM(1.12),pad.GetDrillSize().y+pcb.FromMM(.52)))
    pcb.FootprintSave(str(LIB),f)
    f=pcb.FootprintLoad(str(Path(os.environ['KICAD7_FOOTPRINT_DIR'])/'Package_TO_SOT_SMD.pretty'),'Texas_DRT-3')
    f.SetFPID(pcb.LIB_ID('Robot_PDB','TI_DRT0003A_1x0.8_P0.7'))
    f.SetValue('TPD2EUSB30ADRTR')
    f.SetDescription('TI4211172/A07/10:3x.30squarepads;IO±.35,+.425/GND0,-.425;mask.05;stencil<=.1016mm')
    for pad in f.Pads():pad.SetLocalSolderMaskMargin(pcb.FromMM(.05))
    pcb.FootprintSave(str(LIB),f)
    old=ROOT/'revisions/v0.6/kicad/Robot_PDB.pretty/Power_WirePort_P7.2mm.kicad_mod'
    shutil.copyfile(old,LIB/old.name)

def init_board():
    make_footprints()
    g=Board.__new__(Board);g.b=pcb.BOARD();g.b.SetCopperLayerCount(4)
    g.b.GetDesignSettings().SetBoardThickness(pcb.FromMM(.8))
    g.nets={};g.fps={};g.parts={p['ref']:p for p in circuit.PARTS};g.zones=[];g.fixed_nets=set()
    fproot=Path(os.environ['KICAD7_FOOTPRINT_DIR'])
    for p in circuit.PARTS:
        lib,name=p['fp'].split(':');folder=LIB if lib=='Robot_PDB' else fproot/(lib+'.pretty')
        f=pcb.FootprintLoad(str(folder),name);assert f,(p['ref'],p['fp'])
        f.SetReference(p['ref']);f.SetValue(p['value']);f.SetFPID(pcb.LIB_ID(lib,name));f.Value().SetVisible(False)
        f.Reference().SetLayer(pcb.F_Fab)
        f.Reference().SetTextSize(pcb.VECTOR2I(pcb.FromMM(.7),pcb.FromMM(.7)))
        for pad in f.Pads():
            net=p['pins'].get(pad.GetNumber())
            if net:pad.SetNet(g.net(net))
            pad.SetLocalClearance(pcb.FromMM(.16 if p['ref'] in ('U500','U501','U503','J500','J501','U520','U521','U522','U523','U524','U530','U531','U532','U533','U534','U525','U527','U529') else .20))
        if p['ref']=='J502':
            for pad in f.Pads():
                if pad.GetNumber()!='10' and pad.GetDrillSize().x>0:pad.SetSize(pcb.VECTOR2I(pcb.FromMM(1.22),pcb.FromMM(1.22)))
        if p['dnp']:f.SetAttributes(f.GetAttributes()|pcb.FP_EXCLUDE_FROM_BOM|pcb.FP_EXCLUDE_FROM_POS_FILES)
        g.b.Add(f);g.fps[p['ref']]=f
    g.outline(W,H,r=2)
    return g

def ss_fine_escape(ps):
    """Short matched translated launch around a reserved supply landing.
    The .05mm transverse translation is shared by both legs. It starts .4mm
    beyond the pad centre and completes at .65mm; no terminal pitch changes.
    """
    points=[tuple(pcb.ToMM(p.GetPosition())) for p in ps];centre=tuple(sum(q[i] for q in points)/2 for i in (0,1));origin=tuple(pcb.ToMM(ps[0].GetParent().GetPosition()));delta=tuple(points[0][i]-points[1][i] for i in (0,1));dl=math.hypot(*delta);direction=(-delta[1]/dl,delta[0]/dl)
    if sum(direction[i]*(centre[i]-origin[i]) for i in (0,1))<0:direction=(-direction[0],-direction[1])
    ref=ps[0].GetParent().GetReference();nets={p.GetNetname() for p in ps};shift=(0,0)
    for pin,offset in ({'U500':{'CAM_TXP':(0,.05),'CAM_RXP':(0,-.05),'MIC_TXP':(.05,0),'MIC_RXP':(-.05,0),'UP_TXP':(-.05,0),'UP_RXP':(.05,0),'UP_DP':(-.05,0),'CAM_DP':(0,.05),'MIC_DP':(.05,0),'BMS_USB_DP':(-.05,0)},'U501':{'UP_TXP':(.05,0),'UP_RXP':(-.05,0)}}.get(ref,{})).items():
        if pin in nets:shift=offset;break
    first=min(int(p.GetNumber()) for p in ps);vias=[];paths=[]
    for pad,q in zip(ps,points):
        distance=(1.35 if int(pad.GetNumber())==first else 1.47) if any(n in nets for n in ('UP_DP','CAM_DP','MIC_DP','HUB_CHILD_DP','BMS_USB_DP')) else (.9 if int(pad.GetNumber())==first else 1.02);v=tuple(q[i]+direction[i]*distance+shift[i] for i in (0,1));path=[q]
        if shift!=(0,0):path.extend([tuple(q[i]+direction[i]*.4 for i in (0,1)),tuple(q[i]+direction[i]*.65+shift[i] for i in (0,1))])
        path.append(v);vias.append(v);paths.append(path)
    return vias,paths,tuple(sum(v[i] for v in vias)/2 for i in (0,1)),False

def placement(g):
    major={'U500':(45,57,180),'U501':(20,74,270),'U502':(62,84,0),'U503':(50,74,270),'U504':(90,79,0),
           'U510':(76,21,0),'U511':(76,34,0),'U512':(85,18,0),'U513':(85,28,0),'U514':(85,38,0),'U515':(57,27,0),'Q500':(57,21,0),
           'U520':(17.75,87.5,0),'U521':(26,86.5,180),'U522':(47.75,87.5,0),'U523':(56,86.5,180),'U524':(80.5,79,0),'U530':(22.25,87.5,0),'U531':(14,86.5,180),'U532':(52.25,87.5,0),'U533':(44,86.5,180),'U534':(86.5,79,0),
           'U525':(20,89.5,0),'U526':(27,92,0),'U527':(50,89.5,0),'U528':(57,92,0),'U529':(73,91.5,0),'U505':(28,22,0),
           'J500':(20,95.6,0),'J501':(50,95.6,0),'J502':(80,88.25,0),'H500':(6,6,0),'H501':(94,6,0),'H502':(6,94,0),'H503':(94,94,0),'J503':(15,18,0),'J504':(90,64,90),'J505':(35,18,0),'Y500':(51,64,180)}
    for ref in ('U521','U523','U531','U533','U525','U527','U529'):g.fps[ref].Flip(g.fps[ref].GetPosition(),False)
    for ref,pos in major.items():g.place(ref,*pos)
    #Block-specific compact passive fields; specialized power/filter groups are
    #placed first, remaining low-speed passives occupy a separate quiet field.
    occupied=[]
    for ref in major:
        bb=g.fps[ref].GetBoundingBox();occupied.append((ref,bb))
    perblock={}
    for p in circuit.PARTS:
        ref=p['ref']
        if ref in major:continue
        block=p['block'];j=perblock.get(block,0);perblock[block]=j+1
        if block.startswith('USB3 A'):x,y=65+(j%8)*3.7,10+(j//8)*4.8
        elif block.startswith('USB3 B'):x,y=34+(j%7)*3.5,49+(j//7)*4.3
        elif block.startswith('USB3 C'):x,y=30+(j%8)*3.5,6+(j//8)*4.5
        elif block.startswith('USB3 D'):x,y=5+(j%7)*3.6,61+(j//7)*4.5
        else:x,y=35+(j%6)*4,87+(j//6)*4
        g.place(ref,x,y,90 if ref.startswith('C') else 0)
    #Hub local bypasses surround the associated edge instead of the passive grid.
    caps=[p for p in circuit.PARTS if p['block'].startswith('USB3 B') and p['value']=='100nF 50V']
    positions=[(51.8,58,0),(51.8,55.2,0),(47.6,49.4,90),(45.2,49.4,90),(42.4,49.4,90),(38.2,56.4,180),(38.2,65.5,270),(55.8,66,270),(51.8,51.4,0),(38.2,52.8,180),(38.2,62.4,180),(55.8,63,0)]
    for p,pos in zip(caps,positions):g.place(p['ref'],*pos)
    #AC coupling components in matched pairs, immediately between mux andESD.
    pairs=[]
    for prefix,xbase in [('UP',20),('CAM',50),('MIC',80)]:
        cs=[p for p in circuit.PARTS if p['sym']=='Device:C' and any(net.startswith(prefix+'_') and ('TX' in net or 'RX' in net) for net in p['pins'].values())]
        for j,p in enumerate(cs):
            if prefix=='MIC':x,y=xbase+1.4+(j%2)*1.5+(3.5 if any(n.startswith('MIC_RX') for n in p['pins'].values()) else 0),74
            else:
                net=list(p['pins'].values())[0];rx='_RX' in net;lane2='2' in net
                group=(-6 if rx else -2)+(8 if lane2 else 0)
                x=xbase+group+(.75 if j%2==0 else -.75);y=82.5
                if prefix=='CAM' and any('_TX2' in n for n in p['pins'].values()):x-=.10
            g.place(p['ref'],x,y,270)
    #Keepbuck input/inductor/output filter physically together.
    for l,x,y in [('L501',70.5,22),('L502',70.5,35)]:g.place(l,x,y,180)
    buck_placement={'C501':(79,24.5,0),'C502':(79.7,22,0),'C503':(66,20.5,180),'C504':(66,23.5,180),'R501':(78.8,18,0),'R502':(79.7,20,0),'C505':(79,37.5,0),'C506':(79.7,35,0),'C507':(66,33.5,180),'C508':(66,36.5,180),'R503':(79.5,29,0),'R504':(79.5,31,0),'R505':(79.7,33,180),'R506':(77,30.5,90)}
    for ref,pos in buck_placement.items():g.place(ref,*pos)
    for p in circuit.PARTS:
        if 'POSCAP' in p['value']:g.place(p['ref'],95 if 'MIC_VBUS' in p['pins'].values() else 63,86 if 'MIC_VBUS' in p['pins'].values() else 90,270 if 'MIC_VBUS' in p['pins'].values() else 0)
    #Place bypasses outside the hub body and keep all ordinary passives clear
    #of fixed USB escape components. No copper clearance is relaxed.
    for ref,x,y in [('C525',50.7,60.7),('C526',53.5,60.1),('C527',56,55),('C528',56,60)]:
        if ref in g.fps:g.place(ref,x,y,0 if ref=='C525' else 90)
    for ref,pos in {'R528':(31.5,24.5,0),'C551':(28,18,0),'R527':(94.5,79,0),'C547':(89,75.5,180),'C544':(66.5,84,0),'C545':(66.5,87,0)}.items():g.place(ref,*pos)
    timing_positions={'CAM':((66.5,77.5,0),(66.5,80.5,0)),'MIC':((94,74,0),(95.5,77,0)),'BMS':((21,28,0),(28,27,0))}
    for prefix,meta in circuit.PORT_EN_FILTER.items():
        for key,pos in zip(('resistor','capacitor'),timing_positions[prefix]):g.place(meta[key],*pos)
    ss_refs={p['ref'] for p in circuit.PARTS if p['sym']=='Device:C' and any('TX' in n or 'RX' in n for n in p['pins'].values())}
    fixed=set(major)|{'R528','C551','R527','C547','C544','C545'}|set(buck_placement)|{m[k] for m in circuit.PORT_EN_FILTER.values() for k in ('resistor','capacitor')}|ss_refs|{p['ref'] for p in caps}|{'L501','L502','C525','C526','C527','C528'}|{p['ref'] for p in circuit.PARTS if 'POSCAP' in p['value']}
    def box(f):
        bs=[p.GetBoundingBox() for p in f.Pads()]
        return (min(pcb.ToMM(b.GetLeft()) for b in bs),min(pcb.ToMM(b.GetTop()) for b in bs),max(pcb.ToMM(b.GetRight()) for b in bs),max(pcb.ToMM(b.GetBottom()) for b in bs))
    occupied=[box(g.fps[r]) for r in fixed if g.fps[r].GetLayer()==pcb.F_Cu]+[(2.75,2.75,9.25,9.25),(90.75,2.75,97.25,9.25),(2.75,90.75,9.25,97.25),(90.75,90.75,97.25,97.25),(49,51.8,55,54.4),(42.8,46,48.2,53),(42,61.0,48,67.8)]
    def fits(bb):
        if not(1<bb[0]<bb[2]<99 and 1<bb[1]<bb[3]<98):return False
        return all(bb[2]+.5<ob[0] or ob[2]+.5<bb[0] or bb[3]+.5<ob[1] or ob[3]+.5<bb[1] for ob in occupied)
    for ref,f in g.fps.items():
        if ref in fixed:continue
        x,y=pcb.ToMM(f.GetPosition());orientation=f.GetOrientationDegrees()
        candidates=sorted(((i*.8,j*.8) for i in range(-24,25) for j in range(-24,25)),key=lambda a:a[0]**2+a[1]**2)
        for dx,dy in candidates:
            g.place(ref,x+dx,y+dy,orientation);bb=box(f)
            if fits(bb):occupied.append(bb);break
        else:raise RuntimeError('No collision-free passive position for '+ref)
    #Deliberate140mm cell placement: preserve each functional cluster,
    #spread camera/hub20mm and microphone/rail converters40mm from upstream.
    for ref,f in g.fps.items():
        x,y=pcb.ToMM(f.GetPosition());part=g.parts[ref];block=part['block']
        if ref.startswith('H'):
            g.place(ref,5 if ref in ('H500','H502') else W-5,6 if ref in ('H500','H501') else H-6,0);continue
        if ref=='U500':dx=20
        elif any(n.startswith('UP_') and ('TX' in n or 'RX' in n) for n in part['pins'].values()):dx=0
        elif any(n.startswith('CAM_') and ('TX' in n or 'RX' in n) for n in part['pins'].values()):dx=20
        elif any(n.startswith('MIC_') and ('TX' in n or 'RX' in n) for n in part['pins'].values()):dx=40
        elif ref in ('U505','R528','C551','J505','R531','C564'):dx=20
        elif block.startswith('USB3 A'):dx=40
        elif block.startswith('USB3 B') or block.startswith('USB3 D'):dx=20
        elif block.startswith('USB3 C'):dx=0
        elif ref in ('J503','J505','U505') or any(n.startswith('BMS_') for n in part['pins'].values()):dx=20
        elif ref in ('U525',):dx=0
        elif ref in ('U527',):dx=20
        elif block.startswith('USB3 F'):dx=20 if 'CAM' in part['pins'].values().__str__() else 40
        else:dx=40
        g.place(ref,x+dx,y,f.GetOrientationDegrees())
    g.place('R510',127.2,20.7,0)
    g.place('C526',67.2,65.8,180)
    for f in g.b.GetFootprints():
        for drawing in f.GraphicalItems():
            if drawing.GetLayer()==pcb.F_SilkS:drawing.SetLayer(pcb.F_Fab)
    g.text('USB3 FRONTEND / DEVELOPMENT',72,5,1)
    g.text('5V1 INPUT >=6A / LOCAL POWER ONLY',76,70,.8)

def make_si_guard(fx,board):
    from audit_usb3_signals import package_regions,pair_key,hs_key,within
    si_regions=package_regions(board)
    def si_free(q,net,layer,radius):
        """TI9.1.3 isolation envelope outside bounded package escapes.
        This complements native copper clearance; the independent saved-board
        audit clips boundaries and remains the release authority.
        """
        si_free.last_collision=None
        channel=pair_key(net);high=hs_key(net);ownpair=next((pair for pair in circuit.SUPERSPEED_PAIRS+circuit.USB2_PAIRS if net in pair),(net,))
        if layer==pcb.B_Cu and net not in ('HUB_CHILD_DP','HUB_CHILD_DM','GND'):
            for legnet,width,a,b in CHILD_SEGMENTS:
                limit=radius+width/2+.767
                if q[0]<min(a[0],b[0])-limit or q[0]>max(a[0],b[0])+limit or q[1]<min(a[1],b[1])-limit or q[1]>max(a[1],b[1])+limit:continue
                d=tuple(b[i]-a[i] for i in (0,1));t=max(0,min(1,sum((q[i]-a[i])*d[i] for i in (0,1))/sum(z*z for z in d)));near=tuple(a[i]+t*d[i] for i in (0,1))
                local=any(r['reference']=='U500' and within(q,r['box_mm']) and within(near,r['box_mm']) and net in r['nets'] for r in si_regions)
                clearance=.205 if local else .767
                if math.dist(q,near)<radius+width/2+clearance:si_free.last_collision=dict(kind='child_actual_leg',net=net,point=q,nearest=near,package_exception=local);return False
        if high:
            for reserved,(side,guides) in SS_EXIT_RESERVATIONS.items():
                if channel==reserved or layer!=(pcb.F_Cu if side=='F' else pcb.B_Cu):continue
                for a,b in [(a,b) for guide in guides for a,b in zip(guide,guide[1:])]:
                    d=tuple(b[i]-a[i] for i in (0,1));t=max(0,min(1,sum((q[i]-a[i])*d[i] for i in (0,1))/sum(z*z for z in d)));near=tuple(a[i]+t*d[i] for i in (0,1))
                    local=any(within(q,r['box_mm']) and within(near,r['box_mm']) and high in r['pair_groups'] and reserved in r['pair_groups'] for r in si_regions)
                    if math.dist(q,near)<radius+.284+(.16 if local else 1.020 if channel else .762):si_free.last_collision=dict(kind='reserved_package_exit',net=net,reserved=reserved,point=q,nearest=near);return False
        pt=pcb.VECTOR2I(pcb.FromMM(q[0]),pcb.FromMM(q[1]))
        for it in fx._items(layer,'',*q,3):
            other=it.GetNetname();other_channel=pair_key(other);other_high=hs_key(other)
            if other in ownpair or (high and high==other_high) or not other or other=='GND' or other.startswith('NC_') or (not high and not other_high):continue
            target=1.020 if channel and other_channel else 1.270 if net in ('HUB_XI','HUB_XO') or other in ('HUB_XI','HUB_XO') else .762
            if not it.HitTest(pt,pcb.FromMM(radius+target-1e-6)):continue
            if isinstance(it,pcb.PAD):
                box=it.GetBoundingBox();near=(max(pcb.ToMM(box.GetLeft()),min(q[0],pcb.ToMM(box.GetRight()))),max(pcb.ToMM(box.GetTop()),min(q[1],pcb.ToMM(box.GetBottom()))))
            else:
                a,b=[tuple(pcb.ToMM(v)) for v in (it.GetStart(),it.GetEnd())];d=tuple(b[i]-a[i] for i in (0,1));den=sum(z*z for z in d);t=max(0,min(1,sum((q[i]-a[i])*d[i] for i in (0,1))/den)) if den else 0;near=tuple(a[i]+t*d[i] for i in (0,1))
            if any(within(q,r['box_mm']) and within(near,r['box_mm']) and (high in r['pair_groups'] if high else net in r['nets']) and (other_high in r['pair_groups'] if other_high else other in r['nets']) for r in si_regions):continue
            si_free.last_collision=dict(net=net,other=other,point=q,nearest=near,target=target)
            return False
        return True
    return si_free

def route_board(g):
    """Explicit coupled signal spines; low-speed completion is separate.

    A route failure is recorded and leaves an open net. Never silently replace
    a failed high-speed coupled path with independently autorouted traces.
    """
    fixer.CLR=.16;fixer.VIA_D=.56;fixer.VIA_DR=.30
    fx=USB3Fixer(g.b);evidence=[];overrides={};maze_probe=[]
    fx.temporary_stub_ids={row['item'].m_Uuid.AsString() for row in getattr(g,'data_stub_items',[])}
    fx.temporary_stub_pairs={net:set(pair) for pair in circuit.SUPERSPEED_PAIRS+circuit.USB2_PAIRS for net in pair}
    si_free=make_si_guard(fx,g.b)
    #Map bothpolarities to component-pad endpoints. Opposite NC lands on the
    #flow-through ESD packages are deliberate external routing terminals.
    ss_virtual=[]
    def pads(net):return [p for f in g.b.GetFootprints() if g.parts[f.GetReference()]['sym']!='pdb:TPD2EUSB30A_DRT' for p in f.Pads() if p.GetNetname()==net and not net.startswith('NC_')]+[p for p in ss_virtual if p.GetNetname()==net]
    def point(p):return tuple(pcb.ToMM(p.GetPosition()))
    def fine_escape(ps):
        return ss_fine_escape(ps)
    def direct(net,a,b,w=.17,layer='F'):
        if math.dist(a,b)<.0001:return True
        return fx.route(net,a,b,w=w,step=.08,win=2,layers=(layer,))
    #The shortest coupled connection is first; every branch is kept as a
    #paired connection. Longchannel routing uses a shared centreline below.
    def centre_route(a,b,layer,pair,start_dir,end_dir,aroot,broot,end_approach=2,search_margin=.016):
        """Shared spine with <=45degree turns and1mm between trunk turns.
        Within2.5mm of terminal roots, allow.5mm SS/.25mm USB2 straights;
        these explicit package escapes still receive exact native/SI checks.
        Actual terminal coordinates are preserved; the final grid correction is
        spread over a 1mm straight approach, never a sub-grid hairpin.
        """
        step=.25;approach=min(end_approach,math.dist(a,b)/4);minrun=max(1,min(3 if math.dist(a,b)<10 else 4,int(math.dist(a,b)/(2*step))))
        dest=(b[0]+end_dir[0]*approach,b[1]+end_dir[1]*approach)
        x0=a[0]-math.ceil((a[0]-min(a[0],dest[0])+10)/step)*step
        y0=a[1]-math.ceil((a[1]-min(a[1],dest[1])+10)/step)*step
        nx=math.ceil((max(a[0],dest[0])+10-x0)/step)+1;ny=math.ceil((max(a[1],dest[1])+10-y0)/step)+1
        dirs=((1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1),(0,-1),(1,-1))
        hd=lambda d:max(range(8),key=lambda i:(d[0]*dirs[i][0]+d[1]*dirs[i][1])/math.hypot(*dirs[i]))
        ah=hd(start_dir);bh=hd((-end_dir[0],-end_dir[1]))
        s=(round((a[0]-x0)/step),round((a[1]-y0)/step),ah,0)
        target=(round((dest[0]-x0)/step),round((dest[1]-y0)/step))
        xy=lambda q:(x0+q[0]*step,y0+q[1]*step)
        cache={};turn_cache={};sep=(WIDTH+GAP)/2
        normals=[(-d[1]/math.hypot(*d),d[0]/math.hypot(*d)) for d in dirs]
        def conductor_clear(q,offsets):
            x,y=xy(q)
            if point_segment((x,y),broot,dest)<.75 and (x-dest[0])*end_dir[0]+(y-dest[1])*end_dir[1]<-.2:return False
            if point_segment((x,y),aroot,a)<.75 and (x-a[0])*start_dir[0]+(y-a[1])*start_dir[1]<-.2:return False
            items=[it for it in fx._items(layer,'',x,y,3) if (it.GetNetname() not in pair or not isinstance(it,pcb.PAD)) and not(it.GetNetname() in pair and min(math.dist((x,y),aroot),math.dist((x,y),broot))<1.3)]
            for ox,oy in offsets:
                pos=(x+ox,y+oy);radius=WIDTH/2+search_margin
                if not(.5+radius<pos[0]<W-.5-radius and .5+radius<pos[1]<H-.5-radius):return False
                if layer==pcb.F_Cu and any(cx-3.5-radius<pos[0]<cx+3.5+radius and 95.6-1.305-radius<pos[1]<95.6+4.325+radius for cx in (20,70)):return False
                pt=pcb.VECTOR2I(pcb.FromMM(pos[0]),pcb.FromMM(pos[1]))
                for it in items:
                    clearance=max(fixer.CLR,(pcb.ToMM(it.GetLocalClearance()) or (.16 if it.GetNetname() in DATA_NETS else .20)) if isinstance(it,pcb.PAD) else (.16 if it.GetNetname() in DATA_NETS else .20))
                    if isinstance(it,pcb.PAD):
                        if it.HitTest(pt,pcb.FromMM(radius+clearance)):return False
                    elif point_segment(pos,tuple(pcb.ToMM(it.GetStart())),tuple(pcb.ToMM(it.GetEnd())))<radius+pcb.ToMM(it.GetWidth())/2+clearance-1e-6:return False
                if not si_free(pos,pair[0],layer,radius):return False
            return True
        def clear(q):
            if len(q)<3:return any(clear((*q[:2],h)) for h in range(8))
            key=q[:3]
            if key not in cache:
                nx,ny=normals[q[2]];cache[key]=conductor_clear(q,[(sep*nx,sep*ny),(-sep*nx,-sep*ny)])
            return cache[key]
        def clear_turn(q,heading):
            key=(*q[:3],heading)
            if key not in turn_cache:
                n1,n2=normals[q[2]],normals[heading];den=1+sum(n1[i]*n2[i] for i in (0,1));m=tuple((n1[i]+n2[i])/den for i in (0,1))
                turn_cache[key]=conductor_clear(q,[(sep*m[0],sep*m[1]),(-sep*m[0],-sep*m[1])])
            return turn_cache[key]
        if not clear(s) or not clear((*target,bh,4)):
            maze_probe.append(dict(pair=pair,layer=g.b.GetLayerName(layer),start=xy(s),goal=xy((*target,bh,4)),start_free=clear(s),goal_free=clear((*target,bh,4))))
            if os.environ.get('USB3_DEBUG'):
                for label,q0 in (('start',s),('end',(*target,bh,4))):
                    if not clear(q0):
                        x,y=xy(q0);pt=pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y));acc=pcb.FromMM(.5)
                        si=si_free((x,y),pair[0],layer,(WIDTH+WIDTH+GAP)/2)
                        print('    Pair endpoint',pair,label,(x,y),'SI',si,si_free.last_collision,[(it.GetNetname(),it.GetParent().GetReference() if isinstance(it,pcb.PAD) else 'track',tuple(pcb.ToMM(it.GetPosition()))) for it in fx._items(layer,'',x,y,3) if it.HitTest(pt,acc)],flush=True)
            return None
        if os.environ.get('USB3_MAZE_PROBE')=='1':
            queue=collections.deque([s[:2]]);seen={s[:2]};reached=False
            while queue:
                q=queue.popleft()
                if q==target:reached=True;break
                for dx,dy in dirs:
                    m=(q[0]+dx,q[1]+dy)
                    if m in seen or not(0<=m[0]<nx and 0<=m[1]<ny):continue
                    if clear(m) and clear(((q[0]+m[0])/2,(q[1]+m[1])/2)):seen.add(m);queue.append(m)
            row=dict(pair=pair,layer=g.b.GetLayerName(layer),start=xy(s),goal=xy((*target,bh,4)),start_free=True,goal_free=True,reachable_without_heading=reached,cells_visited=len(seen),search_margin=search_margin)
            maze_probe.append(row);print('MAZE PROBE',json.dumps(row),flush=True);return None
        incoming=tuple(v/math.hypot(*dirs[bh]) for v in dirs[bh])
        def directed_heuristic(q):
            delta=sum((q[i]-target[i])*incoming[i] for i in (0,1))
            if q[2]==bh and delta<=.01:return math.dist(q[:2],target)
            pre=tuple(target[i]-6*incoming[i] for i in (0,1))
            return math.dist(q[:2],pre)+6
        pq=[(1.35*directed_heuristic(s),0,s)];cost={s:0};prev={s:None};count=0
        while pq and count<750000:
            _,c,q=heapq.heappop(pq);count+=1
            if q[:2]==target and q[2]==bh and q[3]>=(1 if math.dist(xy(q),broot)<2.5 else minrun):
                path=[]
                while q is not None:path.append(xy(q));q=prev[q]
                path.reverse();path[0]=a;path[-1]=dest
                #Remove exactly collinear grid vertices only.
                out=[path[0]]
                for i in range(1,len(path)-1):
                    v1=(path[i][0]-out[-1][0],path[i][1]-out[-1][1]);v2=(path[i+1][0]-path[i][0],path[i+1][1]-path[i][1])
                    if abs(v1[0]*v2[1]-v1[1]*v2[0])>1e-8:out.append(path[i])
                out.extend((path[-1],(b[0]+end_dir[0]*approach/2,b[1]+end_dir[1]*approach/2),b))
                return out
            if c>cost.get(q,1e30):continue
            near_package=min(math.dist(xy(q),aroot),math.dist(xy(q),broot))<2.5
            required=1 if near_package else minrun
            headings=(q[2],) if q[3]<required else ((q[2]-1)%8,q[2],(q[2]+1)%8)
            for nh in headings:
                dx,dy=dirs[nh];m=(q[0]+dx,q[1]+dy,nh,min(4,q[3]+1) if nh==q[2] else 1)
                if not (0<=m[0]<nx and 0<=m[1]<ny) or not clear(m) or not clear_turn(q,nh):continue
                mid=((q[0]+m[0])/2,(q[1]+m[1])/2)
                if not clear((*mid,nh)):continue
                new=c+math.hypot(dx,dy)+(1 if nh!=q[2] else 0)
                if new<cost.get(m,1e30):cost[m]=new;prev[m]=q;heapq.heappush(pq,(new+1.35*directed_heuristic(m),new,m))
        if os.environ.get('USB3_DEBUG'):print('    Pair maze exhausted',pair,count,len(pq),'heads',ah,bh,'roots',aroot,broot,'grid',s,target,'free',sum(cache.values()),'blocked',len(cache)-sum(cache.values()),flush=True)
        return None
    def offset(path,d):
        normals=[]
        for a,b in zip(path,path[1:]):
            length=math.dist(a,b)
            if length<1e-9:return None
            normals.append((-(b[1]-a[1])/length,(b[0]-a[0])/length))
        out=[]
        for i,(x,y) in enumerate(path):
            if i==0:nx,ny=normals[0]
            elif i==len(path)-1:nx,ny=normals[-1]
            else:
                n1,n2=normals[i-1],normals[i];den=1+n1[0]*n2[0]+n1[1]*n2[1]
                if den<.15:return None
                nx,ny=(n1[0]+n2[0])/den,(n1[1]+n2[1])/den
            out.append((x+d*nx,y+d*ny))
        return out
    small_vias=set()
    def vsize(v):return (.25,.15) if tuple(round(z,5) for z in v) in small_vias else (.56,.30)
    def vok(net,v):
        old=(fixer.VIA_D,fixer.VIA_DR);fixer.VIA_D,fixer.VIA_DR=vsize(v)
        try:return fx.via_ok(net,*v)
        finally:fixer.VIA_D,fixer.VIA_DR=old
    def vadd(net,v):
        if any(t.GetClass()=='PCB_VIA' and t.GetNetname()==net and math.dist(tuple(pcb.ToMM(t.GetPosition())),v)<1e-6 for t in g.b.GetTracks()):return
        old=(fixer.VIA_D,fixer.VIA_DR);fixer.VIA_D,fixer.VIA_DR=vsize(v)
        try:fx.add_via(net,*v)
        finally:fixer.VIA_D,fixer.VIA_DR=old
    collision_seen=set()
    def clear_line(net,path,layer):
        for start,end in zip(path,path[1:]):
            count=max(1,math.ceil(math.dist(start,end)/.06))
            for j in range(count+1):
                x=start[0]+(end[0]-start[0])*j/count;y=start[1]+(end[1]-start[1])*j/count
                if not fx.free(layer,net,x,y,WIDTH/2) or not si_free((x,y),net,layer,WIDTH/2):
                    reason=si_free.last_collision
                    if os.environ.get('USB3_DEBUG') and (net,layer) not in collision_seen:
                        collision_seen.add((net,layer))
                        pt=pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y));acc=pcb.FromMM(WIDTH/2+fixer.CLR)
                        print('      Launch obstructed',net,(x,y),'native',fx.free(layer,net,x,y,WIDTH/2),'SIreason',reason,[(it.GetNetname(),it.GetParent().GetReference() if isinstance(it,pcb.PAD) else it.GetClass(),tuple(pcb.ToMM(it.GetPosition()))) for it in fx._items(layer,net,x,y,2) if it.HitTest(pt,acc)],flush=True)
                    return False
        return True
    def point_segment(q,a,b):
        dx,dy=b[0]-a[0],b[1]-a[1];den=dx*dx+dy*dy
        t=max(0,min(1,((q[0]-a[0])*dx+(q[1]-a[1])*dy)/den)) if den else 0
        return math.dist(q,(a[0]+t*dx,a[1]+t*dy))
    def segment_distance(a,b,c,d):
        cross=lambda x,y,z:(y[0]-x[0])*(z[1]-x[1])-(y[1]-x[1])*(z[0]-x[0])
        if cross(a,b,c)*cross(a,b,d)<-1e-12 and cross(c,d,a)*cross(c,d,b)<-1e-12:return 0
        return min(point_segment(q,x,y) for q,x,y in ((a,c,d),(b,c,d),(c,a,b),(d,a,b)))
    last_commit={}
    def path_length(path):return sum(math.dist(a,b) for a,b in zip(path,path[1:]))
    def commit_pair(items):
        """Atomic coupled route, exact P/N separation and local length tuning.
        Short package pitch changes and deliberately uncoupled tuning sections
        are reported separately; neither is represented as90ohm uniformline.
        """
        last_commit.clear()
        #Drop zero-length vertices; detect geometric self-crossing beforecommit.
        for net,segments,vias in items:
            for layer,path in segments:
                path[:]=[q for i,q in enumerate(path) if i==0 or math.dist(q,path[i-1])>1e-7]
        invalid=[]
        def valid(candidate):
            invalid.clear()
            for net,segments,vias in candidate:
                if not all(clear_line(net,path,layer) for layer,path in segments):invalid.append(('external',net));return False
                if not all(vok(net,v) for v in vias):invalid.append(('via',net));return False
                for layer,path in segments:
                    for i,(a,b) in enumerate(zip(path,path[1:])):
                        for j in range(i+2,len(path)-1):
                            c,d=path[j:j+2]
                            if segment_distance(a,b,c,d)<1e-7:invalid.append(('self',net,a,b,c,d));return False
            one,two=candidate
            for la,pa in one[1]:
                for lb,pb in two[1]:
                    if la==lb and any(segment_distance(a,b,c,d)<WIDTH+GAP-1e-6 for a,b in zip(pa,pa[1:]) for c,d in zip(pb,pb[1:])):invalid.append(('mutual',la));return False
            if any(math.dist(a,b)<(vsize(a)[0]+vsize(b)[0])/2+GAP-1e-6 for a in one[2] for b in two[2]):return False
            for vias,other in ((one[2],two[1]),(two[2],one[1])):
                if any(point_segment(v,a,b)<vsize(v)[0]/2+WIDTH/2+GAP-1e-6 for v in vias for layer,path in other for a,b in zip(path,path[1:])):return False
            return True
        if not valid(items):
            if os.environ.get('USB3_DEBUG') and (items[0][0].endswith('_DP') or items[0][0] in ('UP_TX1P','UP_TX2P')):print('    USB2 invalid',items[0][0],invalid,flush=True)
            return False
        lengths=[sum(path_length(path) for layer,path in it[1]) for it in items]
        delta=abs(lengths[0]-lengths[1]);tuning=None
        if delta>.015:
            which=0 if lengths[0]<lengths[1] else 1
            net,segments,vias=items[which]
            #Equal45degree teeth add exactly2h(sqrt2-1) per tooth.
            #Limit excursion to.5mm and place on one existingstraightsection.
            teeth=max(1,math.ceil(delta/(2*.5*(math.sqrt(2)-1))))
            height=delta/(teeth*2*(math.sqrt(2)-1));base=2*height*teeth
            choices=sorted(((math.dist(a,b),si,i,a,b) for si,(ly,path) in enumerate(segments) for i,(a,b) in enumerate(zip(path,path[1:])) if math.dist(a,b)>base+.4),reverse=True)
            for _,si,i,a,b in choices:
                layer,path=segments[si];length=math.dist(a,b);ux=(b[0]-a[0])/length;uy=(b[1]-a[1])/length
                for fraction in (.1,.5,.9):
                    start=.2+(length-base-.4)*fraction
                    for side in (1,-1):
                        bump=[(a[0]+start*ux,a[1]+start*uy)]
                        for k in range(teeth):
                            t=start+(2*k+1)*height
                            bump.append((a[0]+t*ux-side*height*uy,a[1]+t*uy+side*height*ux))
                            t=start+(2*k+2)*height;bump.append((a[0]+t*ux,a[1]+t*uy))
                        original=path[:];path[i+1:i+1]=bump
                        if valid(items):
                            tuning={'net':net,'layer':g.b.GetLayerName(layer),'added_length_mm':delta,'excursion_mm':height,'straight_footprint_mm':base,'teeth':teeth,'note':'Local uncoupled length-compensation section; reviewed separately from uniform90ohm pair.'};break
                        path[:]=original
                    if tuning:break
                if tuning:break
        lengths=[sum(path_length(path) for layer,path in it[1]) for it in items]
        last_commit.update(length_mm=lengths,skew_mm=abs(lengths[0]-lengths[1]),length_tuning=tuning)
        for net,segments,vias in items:
            for layer,path in segments:fx.add_track(net,path,WIDTH,layer)
            for v in vias:vadd(net,v)
        return True
    def coupled(pnet,nnet,ap,an,bp,bn):
        allpads=(ap,an,bp,bn)
        layer=pcb.F_Cu if all(p.IsOnLayer(pcb.F_Cu) for p in allpads) else pcb.B_Cu if all(p.IsOnLayer(pcb.B_Cu) for p in allpads) else None
        if layer is None:return None
        a=[point(ap),point(an)];b=[point(bp),point(bn)]
        if ap.GetParent().GetReference()==bp.GetParent().GetReference() and ap.GetParent().GetReference().startswith('U52') and math.dist(a[0],b[0])<1.2:
            if commit_pair([(pnet,[(layer,[a[0],b[0]])],[]),(nnet,[(layer,[a[1],b[1]])],[])]):return {**last_commit,'layer':g.b.GetLayerName(layer),'width_mm':WIDTH,'gap_mm':GAP,'topology':'short external flow-through link under ESDpackage'}

        ac=tuple((a[0][i]+a[1][i])/2 for i in range(2));bc=tuple((b[0][i]+b[1][i])/2 for i in range(2))
        vx,vy=bc[0]-ac[0],bc[1]-ac[1];length=math.hypot(vx,vy)
        if length<.05:return False
        #Normal pad escapes prevent diagonal tracks cutting across adjacent
        #rectangular lands. Between escapes, both legs share the same shape.
        if length<100:
            def normal(pts,pad):
                if pad.GetParent().GetReference()=='J502' and (pnet,nnet) in circuit.USB2_PAIRS:return (0,1)
                if pad.GetParent().GetReference() in ('J500','J501') and pad.GetNumber() in ('B2','B3','B6','B7','B10','B11'):return (0,-1)
                centre=tuple((pts[0][i]+pts[1][i])/2 for i in range(2));fp=pcb.ToMM(pad.GetParent().GetPosition())
                dx,dy=pts[0][0]-pts[1][0],pts[0][1]-pts[1][1];dl=math.hypot(dx,dy)
                if dl<.05:return None
                d=(-dy/dl,dx/dl)
                return (-d[0],-d[1]) if d[0]*(centre[0]-fp[0])+d[1]*(centre[1]-fp[1])<0 else d
            na,nb=normal(a,ap),normal(b,bp)
            if na and nb:
                #The preferred transition has a shared constant-gap spine.
                #Only the terminal launches change from land pitch to .394mm.
                def launch(pad):
                    ref=pad.GetParent().GetReference()
                    return .8 if ref.startswith('C') else .7 if ref in ('U500','U501','U503') else .6
                la,lb=launch(ap),launch(bp)
                def splay(pts,pad):
                    if True:return 0
                    fp=pcb.ToMM(pad.GetParent().GetPosition());mid=sum(q[0] for q in pts)/2
                    return -.8 if mid<fp[0] else .8
                asplay,bsplay=splay(a,ap),splay(b,bp)
                for extra in (.6,1.0,1.5,2.0):
                    ca=(ac[0]+na[0]*(la+extra)+asplay,ac[1]+na[1]*(la+extra))
                    cb=(bc[0]+nb[0]*(lb+extra)+bsplay,bc[1]+nb[1]*(lb+extra))
                    core=[ca,(ca[0]+na[0]*.4,ca[1]+na[1]*.4),(cb[0]+nb[0]*.4,cb[1]+nb[1]*.4),cb]
                    pv=(a[0][0]-ac[0],a[0][1]-ac[1]);sign=1 if pv[0]*(-na[1])+pv[1]*na[0]>=0 else -1
                    ep=(b[0][0]-bc[0],b[0][1]-bc[1])
                    if (ep[0]*nb[1]-ep[1]*nb[0])*sign<0:continue
                    po,no=offset(core,(WIDTH+GAP)/2*sign),offset(core,-(WIDTH+GAP)/2*sign)
                    if po is None or no is None:continue
                    candidates=[]
                    for net,start,end,inside in ((pnet,a[0],b[0],po),(nnet,a[1],b[1],no)):
                        path=[start,(start[0]+na[0]*la,start[1]+na[1]*la),*inside,(end[0]+nb[0]*lb,end[1]+nb[1]*lb),end]
                        candidates.append((net,path))
                    if commit_pair([(net,[(layer,path)],[]) for net,path in candidates]):
                        lengths=[sum(math.dist(x,y) for x,y in zip(path,path[1:])) for _,path in candidates]
                        return {'length_mm':lengths,**last_commit,'layer':g.b.GetLayerName(layer),'width_mm':WIDTH,'gap_mm':GAP,'topology':'shared normal spine with terminal pitch transitions'}
                #Independent terminal pitch transitions are package escapes,
                #never an alternative to a controlled long differential spine.
                for fan in ((.2,.3,.4,.5,.7,.8,1.0) if length<3.5 else ()):
                    candidates=[]
                    for net,start,end in ((pnet,a[0],b[0]),(nnet,a[1],b[1])):
                        path=[start,(start[0]+na[0]*fan,start[1]+na[1]*fan),(end[0]+nb[0]*fan,end[1]+nb[1]*fan),end]
                        candidates.append((net,path))
                    if all(clear_line(net,path,layer) for net,path in candidates):
                        if not commit_pair([(net,[(layer,path)],[]) for net,path in candidates]):continue
                        lengths=[sum(math.dist(x,y) for x,y in zip(path,path[1:])) for _,path in candidates]
                        return {'length_mm':lengths,**last_commit,'layer':g.b.GetLayerName(layer),'width_mm':WIDTH,'short_package_transition':True,'fanout_mm':fan}
        #A straight common centreline is fully controlled; symmetrical escapes
        #are limitedto1.2mm. Bends require explicit placement/channel refinement.
        ux,uy=vx/length,vy/length;nx,ny=-uy,ux
        sign=1 if (a[0][0]-ac[0])*nx+(a[0][1]-ac[1])*ny>=0 else -1
        if ((b[0][0]-bc[0])*nx+(b[0][1]-bc[1])*ny)*sign<-.02:return False
        if length<2.0 and math.dist(a[0],a[1])<1.4 and math.dist(b[0],b[1])<1.4:
            paths=[(pnet,[a[0],b[0]]),(nnet,[a[1],b[1]])]
            if all(clear_line(net,path,layer) for net,path in paths):
                if not commit_pair([(net,[(layer,path)],[]) for net,path in paths]):return False
                lengths=[math.dist(*path) for _,path in paths]
                return {'length_mm':lengths,**last_commit,'layer':g.b.GetLayerName(layer),'width_mm':WIDTH,'short_package_transition':True}
        inset=min(1.2,length/3);sep=(WIDTH+GAP)/2
        centre=[(ac[0]+ux*inset,ac[1]+uy*inset),(bc[0]-ux*inset,bc[1]-uy*inset)]
        paths=[]
        for side,net,ends in ((sign,pnet,(a[0],b[0])),(-sign,nnet,(a[1],b[1]))):
            mid=[(x+nx*sep*side,y+ny*sep*side) for x,y in centre]
            path=[ends[0],*mid,ends[1]]
            if not clear_line(net,path,layer):return False
            paths.append((net,path))
        if not commit_pair([(net,[(layer,path)],[]) for net,path in paths]):return False
        lengths=[sum(math.dist(s,t) for s,t in zip(path,path[1:])) for _,path in paths]
        return {'length_mm':lengths,**last_commit,'width_mm':WIDTH,'gap_mm':GAP,'layer':g.b.GetLayerName(layer),'topology':'shared straight centreline with short fanouts'}
    def paired_channel(pnet,nnet,ap,an,bp,bn):
        def connected(a,b):
            cn=g.b.GetConnectivity();cn.Build(g.b);target=b.m_Uuid.AsString();seen=set();todo=[a]
            while todo:
                q=todo.pop();key=q.m_Uuid.AsString()
                if key==target:return True
                if key in seen:continue
                seen.add(key);todo.extend(z for z in list(cn.GetConnectedTracks(q))+list(cn.GetConnectedPads(q)) if z.GetNetname()==a.GetNetname())
            return False
        if not ap.GetNumber().startswith('V') and not bp.GetNumber().startswith('V') and connected(ap,bp) and connected(an,bn):
            lengths=[sum(pcb.ToMM(t.GetLength()) for t in g.b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net) for net in (pnet,nnet)]
            layers=sorted({g.b.GetLayerName(t.GetLayer()) for t in g.b.GetTracks() if t.GetClass()=='PCB_TRACK' and t.GetNetname() in (pnet,nnet)})
            return {'length_mm':lengths,'skew_mm':abs(lengths[0]-lengths[1]),'topology':'retained complete coupledchannel;connectivityrechecked','width_mm':WIDTH,'gap_mm':GAP,'layers':layers}
        #First try the shortest no-via coupledpath.
        buspair=pnet in ('UP_TXP','UP_RXP','CAM_TXP','CAM_RXP','MIC_TXP','MIC_RXP')
        result=coupled(pnet,nnet,ap,an,bp,bn)
        if result:return result
        a=[point(ap),point(an)];b=[point(bp),point(bn)]
        def exit_direction(ps,pad):
            centre=tuple((ps[0][i]+ps[1][i])/2 for i in range(2));fp=pcb.ToMM(pad.GetParent().GetPosition())
            if pad.GetParent().GetReference()=='J502' and (pnet,nnet) in circuit.USB2_PAIRS:return centre,(0,1)
            if pad.GetParent().GetReference() in ('J500','J501') and pad.GetNumber() in ('B2','B3','B6','B7','B10','B11'):return centre,(0,-1)
            delta=(ps[0][0]-ps[1][0],ps[0][1]-ps[1][1]);dl=math.hypot(*delta)
            if dl<.05:return None
            d=(-delta[1]/dl,delta[0]/dl)
            if d[0]*(centre[0]-fp[0])+d[1]*(centre[1]-fp[1])<0:d=(-d[0],-d[1])
            return centre,d
        ea=exit_direction(a,ap);eb=exit_direction(b,bp)
        if not ea or not eb:return None
        ac,ad=ea;bc,bd=eb;sep=(WIDTH+GAP)/2
        def shift(pad):
            if not buspair:return (0,0)
            ref=pad.GetParent().GetReference()
            if ref=='U500' and pnet.startswith('CAM_'):return (0,.6 if pnet=='CAM_TXP' else -.6)
            if ref=='U500' and pnet.startswith('UP_'):return (-1 if pnet=='UP_TXP' else 1,0)
            if ref=='U500' and pnet.startswith('MIC_'):return (.6 if pnet=='MIC_TXP' else -.8,0)
            if ref in ('U500','U501','U503'):return (1 if '_TX' in pnet else -1,0)
            return (0,0)
        ash,bsh=shift(ap),shift(bp)
        def fanout(ps,pad,centre,direction,sh):
            if pad.GetParent().GetReference() in ('U500','U501','U503') and (pnet,nnet) in circuit.SUPERSPEED_PAIRS:
                result=fine_escape(ps);small_vias.update(tuple(round(z,5) for z in v) for v in result[0]);return result
            if pad.GetParent().GetReference()=='U500' and (pnet,nnet) in circuit.USB2_PAIRS:
                result=ss_fine_escape(ps);small_vias.update(tuple(round(z,5) for z in v) for v in result[0]);return result
            if pad.GetNumber().startswith('VS'):
                points=[point(p) for p in ps];return points,[[v] for v in points],centre,not pad.IsOnLayer(pcb.F_Cu)
            if pad.GetNumber().startswith('V'):
                points=[point(p) for p in ps];small_vias.update(tuple(round(z,5) for z in v) for v in points)
                return points,[[v] for v in points],centre,True
            if pad.GetParent().GetReference() in ('J500','J501') and pad.GetNumber() in ('B2','B3','B6','B7','B10','B11'):
                #Molex inter-row pad-edge channel is.60mm. Paid-option
                #.25/.15 THROUGHvias at its centre leave.175mm copper gap
                #to the Bpad and >=.175mm to the Arow. No pad overlap or
                #manufacturer bodykeepout entry; nominalrulemargin15um.
                points=[point(p) for p in ps]
                vias=[(q[0],q[1]-.65) for q in points]
                small_vias.update(tuple(round(z,5) for z in v) for v in vias)
                paths=[[q,v] for q,v in zip(points,vias)]
                return vias,paths,(sum(v[0] for v in vias)/2,vias[0][1]),False
            if pad.GetParent().GetReference() in ('J500','J501') and pad.GetNumber() in ('A6','A7'):
                points=[point(p) for p in ps];vc=(centre[0],centre[1]-1.2)
                sign=1 if points[0][0]>points[1][0] else -1
                vias=[(vc[0]+sign*.41,vc[1]),(vc[0]-sign*.41,vc[1])]
                paths=[[q,(q[0],q[1]-.7),v] for q,v in zip(points,vias)]
                return vias,paths,vc,False
            if pad.GetParent().GetReference().startswith('C'):
                points=[point(p) for p in ps];pv=(points[0][0]-centre[0],points[0][1]-centre[1]);dl=math.hypot(*pv)
                vc=(centre[0]+direction[0]*1.2,centre[1]+direction[1]*1.2)
                vias=[(vc[0]+side*.41*pv[0]/dl,vc[1]+side*.41*pv[1]/dl) for side in (1,-1)]
                paths=[[q,(q[0]+direction[0]*.7,q[1]+direction[1]*.7),v] for q,v in zip(points,vias)]
                return vias,paths,vc,False
            through=all(p.GetDrillSize().x>0 or not p.IsOnLayer(pcb.F_Cu) for p in ps)
            if through:return [point(p) for p in ps],[[point(p)] for p in ps],centre,True
            length=math.hypot(*sh)
            centres=[(centre[0]+direction[0]*1.2,centre[1]+direction[1]*1.2),
                     (centre[0]+direction[0]*1.5,centre[1]+direction[1]*1.5)]
            if length:
                centres.append((centre[0]+direction[0]*(1.5+length)+sh[0],centre[1]+direction[1]*(1.5+length)+sh[1]))
            base=1.7 if (pnet,nnet) in circuit.USB2_PAIRS else 5.0 if pad.GetParent().GetReference()=='U500' and pnet.startswith('MIC_') else 4.0
            core_end=(centre[0]+direction[0]*(base+length)+sh[0],centre[1]+direction[1]*(base+length)+sh[1])
            centres.append(core_end)
            via_c=(core_end[0]+direction[0]*.8,core_end[1]+direction[1]*.8)
            pv=(point(ps[0])[0]-centre[0],point(ps[0])[1]-centre[1])
            sign=1 if pv[0]*(-direction[1])+pv[1]*direction[0]>=0 else -1
            pairpaths=[];vias=[]
            for side,pad0 in zip((sign,-sign),ps):
                oo=offset(centres,(WIDTH+GAP)/2*side)
                if oo is None:return None
                q=point(pad0);axis=(-direction[1],direction[0]);v=(via_c[0]+axis[0]*.41*side,via_c[1]+axis[1]*.41*side)
                pairpaths.append([q,(q[0]+direction[0]*.7,q[1]+direction[1]*.7),*oo,v]);vias.append(v)
            return vias,pairpaths,via_c,False
        af=fanout((ap,an),ap,ac,ad,ash);bf=fanout((bp,bn),bp,bc,bd,bsh)
        if af is None or bf is None:return None
        #Adjacent Bstation/Fcapacitor:short matched package transition.
        #Use the actualcapfanout vias; do not force a gridhairpin between
        #nearby on-layer endpoints. This is explicitly not a long90ohmspine.
        if math.dist(af[2],bf[2])<3.5 and (af[3] or bf[3]):
            items=[]
            for i,net in enumerate((pnet,nnet)):
                segments=[(pcb.B_Cu,[af[0][i],bf[0][i]])];vias=[]
                for f0 in (af,bf):
                    if not f0[3]:segments.append((pcb.F_Cu,f0[1][i]));vias.append(f0[0][i])
                items.append((net,segments,vias))
            if commit_pair(items):return {**last_commit,'width_mm':WIDTH,'layer':'F/B','short_package_transition':True,'topology':'short paired package transition to matchedcapacitorvias'}
        layers=((pcb.B_Cu,) if buspair and pnet not in ('UP_TXP','CAM_RXP','MIC_TXP','MIC_RXP') else (pcb.F_Cu,pcb.B_Cu))
        for layer,search_margin in [(layer,margin) for layer in layers for margin in (0,.016,.040)]:
            if layer==pcb.F_Cu and any(not p.IsOnLayer(pcb.F_Cu) for p in (ap,an,bp,bn)):continue
            short_brow=bp.GetParent().GetReference() in ('J500','J501') and bp.GetNumber() in ('B2','B3','B10','B11')
            fine=lambda pad:pad.GetParent().GetReference() in ('U500','U501','U503') and (pnet,nnet) in circuit.SUPERSPEED_PAIRS
            limit=math.dist(af[2],bf[2])/4
            ia=min(.35 if fine(ap) else .25 if (pnet,nnet) in circuit.USB2_PAIRS and ap.GetParent().GetReference()=='U500' else 1,limit)
            ib=min(.25 if short_brow or ((pnet,nnet) in circuit.USB2_PAIRS and bp.GetParent().GetReference()=='U500') else .35 if fine(bp) else 1,limit)
            sa=(af[2][0]+ad[0]*ia,af[2][1]+ad[1]*ia);sb=(bf[2][0]+bd[0]*ib,bf[2][1]+bd[1]*ib)
            path=centre_route(sa,sb,layer,(pnet,nnet),ad,bd,af[2],bf[2],.25 if short_brow else .2 if (pnet,nnet) in circuit.USB2_PAIRS and bp.GetParent().GetReference()=='U500' else .50 if fine(bp) and pnet in ('MIC_TXP','MIC_RXP') else .10 if fine(bp) else .6 if (pnet,nnet) in circuit.USB2_PAIRS and bp.GetParent().GetReference() in ('J500','J501') else 2,search_margin)
            if not path:
                if os.environ.get('USB3_DEBUG') and (buspair or (pnet,nnet) in circuit.USB2_PAIRS):print('  debug center blocked',sa,sb,flush=True)
                continue
            #Includeescape headings so offset bends retainconstant separation.
            
            first=(path[1][0]-path[0][0],path[1][1]-path[0][1]);normal=(-first[1],first[0]);dl=math.hypot(*normal)
            sign=1 if (a[0][0]-ac[0])*normal[0]+(a[0][1]-ac[1])*normal[1]>=0 else -1
            positive=offset(path,sep*sign);negative=offset(path,-sep*sign)
            if positive is None or negative is None:
                if os.environ.get('USB3_DEBUG') and (buspair or (pnet,nnet) in circuit.USB2_PAIRS):print('  debug offset invalid',flush=True)
                continue
            #No polarity swap silently introduced. Report incompatiblemapping.
            lastvec=(path[-1][0]-path[-2][0],path[-1][1]-path[-2][1]);lastnorm=(-lastvec[1],lastvec[0])
            if ((b[0][0]-bc[0])*lastnorm[0]+(b[0][1]-bc[1])*lastnorm[1])*sign<0:
                if os.environ.get('USB3_DEBUG') and (buspair or (pnet,nnet) in circuit.USB2_PAIRS):print('  debug polarity',flush=True)
                continue
            paths=[positive,negative];nets=[pnet,nnet];ends=[(a[0],b[0]),(a[1],b[1])]
            via_points=[];ok=True;lengths=[]
            for net,pp,(start,end) in zip(nets,paths,ends):
                if layer==pcb.F_Cu:
                    i=0 if net==pnet else 1
                    full=[*af[1][i],*pp,*reversed(bf[1][i])]
                    if not clear_line(net,full,layer):ok=False;break
                    lengths.append(sum(math.dist(s,t) for s,t in zip(full,full[1:])))
                else:
                    i=0 if net==pnet else 1
                    va,vb=af[0][i],bf[0][i];ath,bth=af[3],bf[3]
                    a_path,b_path=af[1][i],list(reversed(bf[1][i]))
                    if (not ath and not vok(net,va)) or (not bth and not vok(net,vb)) or (not ath and not clear_line(net,a_path,pcb.F_Cu)) or (not bth and not clear_line(net,b_path,pcb.F_Cu)) or not clear_line(net,[va,*pp,vb],pcb.B_Cu):ok=False;break
                    via_points.append((net,va,vb,ath,bth,a_path,b_path));lengths.append(sum(math.dist(s,t) for pp0 in (a_path,[va,*pp,vb],b_path) for s,t in zip(pp0,pp0[1:])))
            if not ok:
                if os.environ.get('USB3_DEBUG') and (buspair or (pnet,nnet) in circuit.USB2_PAIRS or pnet in ('UP_TX2P','UP_RX1P')) and layer==pcb.B_Cu:
                    print('  debug candidate',net,'via',va,vb,vok(net,va),vok(net,vb),'F',clear_line(net,a_path,pcb.F_Cu),clear_line(net,b_path,pcb.F_Cu),'B',clear_line(net,[va,*pp,vb],pcb.B_Cu),flush=True)
                continue
            items=[]
            for net,pp,(start,end) in zip(nets,paths,ends):
                if layer==pcb.F_Cu:
                    i=0 if net==pnet else 1
                    items.append((net,[(layer,[*af[1][i],*pp,*reversed(bf[1][i])])],[]))
                else:
                    _,va,vb,ath,bth,a_path,b_path=next(x for x in via_points if x[0]==net)
                    segments=[(pcb.B_Cu,[va,*pp,vb])];vias=[]
                    if not ath:segments.append((pcb.F_Cu,a_path));vias.append(va)
                    if not bth:segments.append((pcb.F_Cu,b_path));vias.append(vb)
                    items.append((net,segments,vias))
            if not commit_pair(items):continue
            return {'length_mm':lengths,**last_commit,'width_mm':WIDTH,'gap_mm':GAP,'layer':g.b.GetLayerName(layer),'topology':'shared offset channel; matchedvia count' if via_points else 'shared offset channel','signal_vias_per_line':2 if via_points else 0}
        return None
    def route_ss(pairs):
        seen=set()
        priority=['UP_RXP','CAM_TXP','CAM_RXP','MIC_TXP','MIC_RXP','UP_TXP']
        ordered=sorted(pairs,key=lambda pair:len(priority)+priority.index(pair[0]) if pair[0] in priority else 0)
        for pnet,nnet in ordered:
            if (pnet,nnet) in seen:continue
            seen.add((pnet,nnet));pp=pads(pnet);nn=pads(nnet)
            print('SS',pnet,nnet,flush=True)
            endpoints=[]
            for pf in pp:
                choices=[nf for nf in nn if nf.GetParent().GetReference()==pf.GetParent().GetReference()]
                if not choices and pf.GetParent().GetReference().startswith('C'):
                    choices=[nf for nf in nn if nf.GetParent().GetReference().startswith('C') and nf.GetNumber()==pf.GetNumber()]
                if choices:endpoints.append((pf,min(choices,key=lambda nf:math.dist(point(pf),point(nf)))))
            if len(endpoints)<2:
                evidence.append({'pair':[pnet,nnet],'routed':False,'reason':'missing pair endpoint'});continue
            rank=lambda ep:0 if ep[0].GetParent().GetReference().startswith('U52') else 1 if ep[0].GetParent().GetReference().startswith('J') else 2
            preferred={'UP':'U501','CAM':'U503'}.get(pnet.split('_')[0]) if pnet in ('UP_TXP','UP_RXP','CAM_TXP','CAM_RXP') else None
            endpoints.sort(key=lambda ep:(rank(ep),0 if preferred and ep[0].GetParent().GetReference()==preferred else 1,ep[0].GetParent().GetReference(),ep[0].GetNumber()))
            faces=[ep for ep in endpoints if ep[0].GetNumber().startswith('VS')]
            done=list(faces) if faces else [endpoints.pop(0)]
            if faces:endpoints=[ep for ep in endpoints if ep not in faces]
            while endpoints:
                _,_,i,anchor=min((rank(b),math.dist(point(a[0]),point(b[0])),i,a) for i,b in enumerate(endpoints) for a in (faces if faces else done))
                target=endpoints.pop(i);result=paired_channel(pnet,nnet,*anchor,*target)
                swapped=False
                if not result:
                    #MicrochipDS00002970B explicitly permitsSS polarity inversion.
                    #Swaponly the target physical terminals and export the identical
                    #netlist override for schematic generation; never swapUSB2.
                    old=[p.GetNetname() for p in target]
                    for pad,net in zip(target,(nnet,pnet)):
                        pad.SetNet(g.net(net))
                        for item in getattr(g,'fine_escape_items',{}).get((pad.GetParent().GetReference(),pad.GetNumber()),[]):item.SetNet(g.net(net))
                    fx._index=None
                    result=paired_channel(pnet,nnet,*anchor,*reversed(target))
                    if result:
                        for pad,net in zip(target,(nnet,pnet)):
                            rref=pad.GetParent().GetReference();number=pad.GetNumber()
                            overrides.setdefault(rref,{})[number]=net
                        target=tuple(reversed(target));swapped=True
                    else:
                        for pad,net in zip(target,old):
                            pad.SetNet(g.net(net))
                            for item in getattr(g,'fine_escape_items',{}).get((pad.GetParent().GetReference(),pad.GetNumber()),[]):item.SetNet(g.net(net))
                        fx._index=None
                evidence.append({'pair':[pnet,nnet],'from':anchor[0].GetParent().GetReference()+'.'+anchor[0].GetNumber(),'to':target[0].GetParent().GetReference()+'.'+target[0].GetNumber(),'routed':bool(result),'target_polarity_inverted':swapped,'geometry':result or None})
                print('  ',evidence[-1]['from'],evidence[-1]['to'],bool(result),flush=True)
                done.append(target)
        if os.environ.get('USB3_MAZE_PROBE')=='1':return
        pcb.SaveBoard(str(DEST/'usb3_frontend.kicad_pcb'),g.b)
        (DEST.parent/'layout-net-overrides.json').write_text(json.dumps(overrides,indent=2)+'\n')
        #Importthis derived inventory for a schematic that matches the physical
        #polarity choices. All reversals are limited toUSB3 SuperSpeed pairs.
        derived=ROOT/'source/generator/usb3_frontend_routed.py'
        derived.write_text('"""Generated physicalSS polarity mapping; see layout-net-overrides.json."""\nfrom copy import deepcopy\nfrom usb3_frontend import *\nfrom usb3_frontend import PARTS as BASE_PARTS\nPARTS=deepcopy(BASE_PARTS)\nOVERRIDES='+repr(overrides)+'\nfor p in PARTS:\n    p["pins"].update(OVERRIDES.get(p["ref"],{}))\n')
    #TI Fig10-1:one protection device perpair, external mainline through
    #theIOlands, no electrical stub. Broad short packagepitch is explicit.
    drt_evidence=[]
    for part in circuit.PARTS:
        if part['sym']!='pdb:TPD2EUSB30A_DRT':continue
        f=g.fps[part['ref']];cx,cy=pcb.ToMM(f.GetPosition());layer=f.GetLayer()
        positive=next(p for p in f.Pads() if p.GetNumber()=='1');negative=next(p for p in f.Pads() if p.GetNumber()=='2')
        items=[]
        for pad in (positive,negative):
            q=point(pad);side=1 if q[0]>cx else -1
            path=[(cx+side*.41,cy-1.3),(cx+side*.43,cy-.7),(cx+side*.43,cy+.2),q,(cx+side*.41,cy+1.3)]
            items.append((pad.GetNetname(),[(layer,path)],[]))
        if not commit_pair(items):raise RuntimeError('DRT protectedstation blocked '+part['ref'])
        for end in (-1,1):
            for pad,label in ((positive,'P'),(negative,'N')):
                side=1 if point(pad)[0]>cx else -1
                proxy=pcb.PAD(f);proxy.SetNumber('VS'+str(end)+label);proxy.SetPosition(pcb.VECTOR2I(pcb.FromMM(cx+side*.41),pcb.FromMM(cy+end*1.3)));proxy.SetSize(pcb.VECTOR2I(pcb.FromMM(.01),pcb.FromMM(.01)));proxy.SetLayerSet(pcb.LSET(layer));proxy.SetNet(g.net(pad.GetNetname()));ss_virtual.append(proxy)
        drt_evidence.append({'reference':part['ref'],'layer':g.b.GetLayerName(layer),'io_pad_centres_mm':[point(positive),point(negative)],'ground_pad_centre_mm':point(next(p for p in f.Pads() if p.GetNumber()=='3')),'ground_via_mm':[cx,cy],'signal_width_mm':WIDTH,'underbody_half_pitch_mm':.43,'ground_via_diameter_drill_mm':[.25,.15],'nominal_ground_via_copper_gap_mm':.43-.125-WIDTH/2,'station_length_mm':last_commit['length_mm'],'station_skew_mm':last_commit['skew_mm'],'land_source':'TI4211172/A07/10;100umstencil;notvia-in-pad'})
    (DEST.parent/'drt-breakout-evidence.json').write_text(json.dumps(drt_evidence,indent=2)+'\n')
    #Reserve all five USB2 hub escapes before SuperSpeed long channels.
    #The shortstaggered.25/.15throughvias avoid adjacentSS/bypass fanouts.
    for pnet,nnet in circuit.USB2_PAIRS:
        ps=[next(p for p in g.fps['U500'].Pads() if p.GetNetname()==net) for net in (pnet,nnet)]
        a,b=map(point,ps);centre=tuple((a[i]+b[i])/2 for i in (0,1));fp=tuple(pcb.ToMM(g.fps['U500'].GetPosition()))
        delta=(a[0]-b[0],a[1]-b[1]);dl=math.hypot(*delta);d=(-delta[1]/dl,delta[0]/dl)
        if d[0]*(centre[0]-fp[0])+d[1]*(centre[1]-fp[1])<0:d=(-d[0],-d[1])
        vs,paths,_,_=ss_fine_escape(ps)
        small_vias.update(tuple(round(z,5) for z in v) for v in vs)
        #These exact short launches already exist from pre-power allocation.
        #Do not retune a copied path while leaving its original copper behind;
        #the complete channel is tuned when its long connection is committed.
        if not all(clear_line(net,path,pcb.F_Cu) and vok(net,v) for net,path,v in zip((pnet,nnet),paths,vs)):raise RuntimeError('USB2 hub escapeblocked '+pnet)
    mainpairs={'UP_TXP','UP_RXP','CAM_TXP','CAM_RXP','MIC_TXP','MIC_RXP'}
    route_ss([p for p in circuit.SUPERSPEED_PAIRS if p[0] in mainpairs])
    if os.environ.get('USB3_MAZE_PROBE')=='1':return {'maze_probe':maze_probe}
    #Keep physicalFpackageescapes and pairedBvia-endtap ers as reservations,
    #but reopen the longBtrunks whileUSB2 isrouted. Rebuild those trunksafter
    #USB2; temporary Breservations are removed, so no dead-end stubsremain.
    staged_nets={'UP_RXP','UP_RXN','CAM_TXP','CAM_TXN','CAM_RXP','CAM_RXN','MIC_TXP','MIC_TXN'} if os.environ.get('USB3_STAGE_B')=='1' else set()
    staged_vias=[t for t in g.b.GetTracks() if t.GetClass()=='PCB_VIA' and t.GetNetname() in staged_nets]
    b_reservations=[]
    for track in list(g.b.GetTracks()):
        if track.GetClass()!='PCB_TRACK' or track.GetLayer()!=pcb.B_Cu or track.GetNetname() not in staged_nets:continue
        a,b=tuple(pcb.ToMM(track.GetStart())),tuple(pcb.ToMM(track.GetEnd()))
        if any(math.dist(a,tuple(pcb.ToMM(v.GetPosition())))<1.5 and math.dist(b,tuple(pcb.ToMM(v.GetPosition())))<1.5 for v in staged_vias):b_reservations.append(track)
        else:g.b.Remove(track)
    fx._index=None;evidence.clear()
    usb2=[]
    virtual_pads=[]
    if os.environ.get('USB3_SKIP_LOW')!='1':
        for pnet,nnet in sorted(circuit.USB2_PAIRS,key=lambda pair:0 if pair[0]=='BMS_USB_DP' else 1):
            pp=[p for p in pads(pnet) if not(p.GetParent().GetReference() in ('J500','J501') and p.GetNumber()=='B6')];nn=[p for p in pads(nnet) if not(p.GetParent().GetReference() in ('J500','J501') and p.GetNumber()=='B7')];endpoints=[];stations=[]
            esdref={'UP_DP':'U525','CAM_DP':'U527','MIC_DP':'U529'}.get(pnet)
            if esdref:
                f=g.fps[esdref];cx,cy=pcb.ToMM(f.GetPosition());station_layer=f.GetLayer();sign=1 if point(next(p for p in f.Pads() if p.GetNumber()=='3'))[0]>cx else -1
                #Straight paired through-station with.518mm ESD branches.
                #The diagonal SOT553 protection terminals are not fabricated
                #as a diagonallyuncoupled main transmissionline.
                station_top=-3.0 if pnet in ('UP_DP','CAM_DP') else -.9
                station_items=[]
                for net,side,number in ((pnet,sign,'3'),(nnet,-sign,'5')):
                    x=cx+side*(WIDTH+GAP)/2;pad=next(p for p in f.Pads() if p.GetNumber()==number)
                    q=point(pad);stub=[q,(x,q[1])];spine=[(cx+side*.225,cy+station_top),(x,cy+station_top+.3),(x,cy+.6),(cx+side*.225,cy+.9)]
                    station_items.append((net,[(station_layer,stub),(station_layer,spine)],[]))
                if not commit_pair(station_items):raise RuntimeError('USB2 ESD station blocked '+esdref)
                for net,side in ((pnet,sign),(nnet,-sign)):
                    for end in (-1,1):
                        v=(cx+side*.225,cy+(station_top if end==-1 else .9));small_vias.add(tuple(round(z,5) for z in v));vadd(net,v)
                for end in (-1,1):
                    station=[]
                    for net,side,label in ((pnet,sign,'P'),(nnet,-sign,'N')):
                        pad=pcb.PAD(f);pad.SetNumber('V'+str(end)+label);pad.SetPosition(pcb.VECTOR2I(pcb.FromMM(cx+side*.225),pcb.FromMM(cy+(station_top if end==-1 else .9))));pad.SetSize(pcb.VECTOR2I(pcb.FromMM(.01),pcb.FromMM(.01)));pad.SetLayerSet(pcb.LSET.AllCuMask());pad.SetAttribute(pcb.PAD_ATTRIB_PTH);pad.SetNet(g.net(net));virtual_pads.append(pad);station.append(pad)
                    stations.append(tuple(station))
                pp=[p for p in pp if p.GetParent().GetReference()!=esdref];nn=[p for p in nn if p.GetParent().GetReference()!=esdref]

            for pf in pp:
                choices=[nf for nf in nn if nf.GetParent().GetReference()==pf.GetParent().GetReference()]
                if choices:endpoints.append((pf,min(choices,key=lambda nf:math.dist(point(pf),point(nf)))))
            endpoints.sort(key=lambda ep:0 if ep[0].GetParent().GetReference().startswith('U52') else 1 if ep[0].GetParent().GetReference()=='U500' else 2)
            if not endpoints:continue
            done=list(stations) if stations else [endpoints.pop(0)]
            while endpoints:
                _,i,anchor=min((math.dist(point(a[0]),point(b[0])),i,a) for i,b in enumerate(endpoints) for a in ([stations[0] if b[0].GetParent().GetReference()=='U500' else stations[1]] if stations else done))
                target=endpoints.pop(i);result=paired_channel(pnet,nnet,*anchor,*target)
                usb2.append({'pair':[pnet,nnet],'from':anchor[0].GetParent().GetReference()+'.'+anchor[0].GetNumber(),'to':target[0].GetParent().GetReference()+'.'+target[0].GetNumber(),'routed':bool(result),'geometry':result})
                print('USB2',pnet,usb2[-1]['from'],usb2[-1]['to'],bool(result),flush=True)
                if result and not stations:done.append(target)
        #Reserve legal SS inner-row via lands before pin-merge routing.
        for jref in ('J500','J501'):
            for pad in g.fps[jref].Pads():
                if pad.GetNumber() in ('B2','B3','B10','B11'):
                    q=point(pad);v=(q[0],q[1]-.65);small_vias.add(tuple(round(z,5) for z in v));vadd(pad.GetNetname(),v)
        #USB-C duplicates require a local layer crossover without changing
        #D+/D- assignments. Keep this explicit package pin-merge separate from
        #the controlled long USB2 channel; no generic long-pair fallback.
        for jref,prefix in (('J500','UP'),('J501','CAM')):
            merges=[]
            for letter,number in (('P','6'),('M','7')):
                net=prefix+'_D'+letter;f=g.fps[jref]
                a=next(p for p in f.Pads() if p.GetNumber()=='A'+number);b=next(p for p in f.Pads() if p.GetNumber()=='B'+number)
                bp=point(b);v=(bp[0],bp[1]-.65);small_vias.add(tuple(round(z,5) for z in v));merges.append((net,a,b,bp,v))
            #Reserve both starts before either single-net local crossover.
            launchok=commit_pair([(net,[(pcb.F_Cu,[bp,v])],[v]) for net,a,b,bp,v in merges])
            for net,a,b,bp,v in merges:
                old=(fixer.VIA_D,fixer.VIA_DR);fixer.VIA_D,fixer.VIA_DR=.25,.15
                ok=launchok and fx.route(net,v,point(a),w=.17,step=.06,win=4,layers=('F','B'))
                fixer.VIA_D,fixer.VIA_DR=old
                usb2.append({'net':net,'from':jref+'.'+b.GetNumber(),'to':jref+'.'+a.GetNumber(),'routed':ok,'topology':'local duplicatedUSB2 contact merge with layer crossover; no polarity inversion','package_breakout_width_mm':.17})
                print('USB2 merge',net,ok,flush=True)
    for track in b_reservations:g.b.Remove(track)
    fx._index=None
    route_ss([p for p in circuit.SUPERSPEED_PAIRS if p[0] in mainpairs])
    route_ss([p for p in circuit.SUPERSPEED_PAIRS if p[0] not in mainpairs])
    #No automatic completion ofSS nets. ExternalNC nets deliberately remainNC.
    highspeed={net for pair in circuit.SUPERSPEED_PAIRS for net in pair}
    #IncludeAC side pair names not yet present in manifest.
    highspeed.update(net for net in g.nets if any(s in net for s in ('TX','RX')) and not net.startswith('NC_'))
    highspeed.update(net for pair in circuit.USB2_PAIRS for net in pair)
    low=[]
    fixer.CLR=.20
    if os.environ.get('USB3_SKIP_LOW')=='1' or os.environ.get('USB3_SKIP_SIGNALS')=='1':return {'superspeed':evidence,'usb2':usb2,'low_speed':low,'holds':circuit.RELEASE_HOLDS}
    fx.si_guard=si_free
    for net in sorted(g.nets,key=lambda n:(n not in ('HUB_XI','HUB_XO'),n)):
        if net in highspeed or net.startswith('NC_') or net in ('GND','+5_USB_RAW','+1V2_USB','+3V3_USB','CAM_VBUS','MIC_VBUS','BMS_USB_VBUS','U510_SW','U511_SW'):continue
        ps=pads(net)
        if len(ps)<2:continue
        done=[ps.pop(0)]
        while ps:
            _,i,a=min((math.dist(point(a),point(b)),i,a) for i,b in enumerate(ps) for a in done)
            b=ps.pop(i);print('low',net,flush=True);ok=fx.route(net,point(a),point(b),w=.17,step=.08 if net in ('HUB_XI','HUB_XO') else .12,win=3,layers=('F',) if net in ('HUB_XI','HUB_XO') else ('F','B'))
            low.append({'net':net,'routed':ok});done.append(b)
    return {'superspeed':evidence,'usb2':usb2,'low_speed':low,'holds':circuit.RELEASE_HOLDS}

def main():
    g=init_board();placement(g)
    for part in circuit.PARTS:
        if part['sym']=='pdb:TPD2EUSB30A_DRT':
            f=g.fps[part['ref']];x,y=pcb.ToMM(f.GetPosition());g.via('GND',x,y,.25,.15)
            pad=next(p for p in f.Pads() if p.GetNumber()=='3');g.track('GND',[tuple(pcb.ToMM(pad.GetPosition())),(x,y)],.17,'F' if f.GetLayer()==pcb.F_Cu else 'B')
            for pad in f.Pads():
                if pad.GetNumber() not in ('1','2'):continue
                q=tuple(pcb.ToMM(pad.GetPosition()));side=1 if q[0]>x else -1
                path=[(x+side*.41,y-1.3),(x+side*.43,y-.7),(x+side*.43,y+.2),q,(x+side*.41,y+1.3)]
                g.track(pad.GetNetname(),path,WIDTH,'F' if f.GetLayer()==pcb.F_Cu else 'B')
    #Thermal ground vias are obstacles before signal routing, not copper
    #inserted afterwards through an already accepted B-side data channel.
    for ref in ('U500','U501','U502','U503'):
        for pad in g.fps[ref].Pads():
            if pad.GetNetname()=='GND' and pad.GetSize().x>pcb.FromMM(1):
                x,y=pcb.ToMM(pad.GetPosition())
                for dx in (-.3,.3):g.via('GND',x+dx,y,.6,.3)
    #Reserve the known USB2 finepitchhub exits before localpoweranchors.
    #The powerpreparer must see these real shorttracks/vias, not justICpads.
    for pnet,nnet in circuit.USB2_PAIRS:
        pairpads=[next(p for p in g.fps['U500'].Pads() if p.GetNetname()==net) for net in (pnet,nnet)]
        a,b=[tuple(pcb.ToMM(p.GetPosition())) for p in pairpads];centre=tuple((a[i]+b[i])/2 for i in (0,1));origin=tuple(pcb.ToMM(g.fps['U500'].GetPosition()));delta=(a[0]-b[0],a[1]-b[1]);length=math.hypot(*delta);direction=(-delta[1]/length,delta[0]/length)
        if sum(direction[i]*(centre[i]-origin[i]) for i in (0,1))<0:direction=(-direction[0],-direction[1])
        vs,paths,_,_=ss_fine_escape(pairpads)
        for net,path,v in zip((pnet,nnet),paths,vs):g.track(net,path,WIDTH,'F');g.via(net,*v,.25,.15)
    #Allocate SS fine-pitch exits jointly with power, before either long data
    #channels or local bypass feeds can occupy the adjacent package perimeter.
    #Geometry is tied to physical terminal numbers so a permitted polarity
    #inversion updates the whole short escape without moving its copper.
    from route_usb3_power import reserve_critical_power_anchors
    critical=reserve_critical_power_anchors(g.b)
    assert critical['complete'],'Critical local power reservations failed'
    fixer.CLR=.16;fixer.VIA_D=.56;fixer.VIA_DR=.30
    g.fine_escape_items={}
    for ref in ('U500','U501','U503'):
        f=g.fps[ref]
        for pnet,nnet in dict.fromkeys(circuit.SUPERSPEED_PAIRS):
            ps=[next((p for p in f.Pads() if p.GetNetname()==net),None) for net in (pnet,nnet)]
            if any(p is None for p in ps):continue
            vias,paths,_,_=ss_fine_escape(ps)
            for pad,v,path in zip(ps,vias,paths):
                before={t.m_Uuid.AsString() for t in g.b.GetTracks()};g.track(pad.GetNetname(),path,WIDTH,'F');g.via(pad.GetNetname(),*v,.25,.15)
                g.fine_escape_items[(ref,pad.GetNumber())]=[t for t in g.b.GetTracks() if t.m_Uuid.AsString() not in before]
    #Reserve the actual two-conductor via-to-spine transition before power
    #distribution. A supply must not cut between a legal fine via and the
    #short paired heading exit needed to use it. Unused layer stubs are
    #removed after long routing, based on real endpoint connectivity.
    g.data_stub_items=[]
    for ref in ('U500','U501','U503'):
        f=g.fps[ref];pairs=list(dict.fromkeys(circuit.SUPERSPEED_PAIRS))+(circuit.USB2_PAIRS if ref=='U500' else [])
        for pair in pairs:
            if pair[0]=='HUB_CHILD_DP':continue
            ps=[next((pad for pad in f.Pads() if pad.GetNetname()==net),None) for net in pair]
            if any(pad is None for pad in ps):continue
            vias,_,centre,_=ss_fine_escape(ps);pts=[tuple(pcb.ToMM(pad.GetPosition())) for pad in ps];delta=tuple(pts[0][i]-pts[1][i] for i in (0,1));dl=math.hypot(*delta);direction=(-delta[1]/dl,delta[0]/dl);origin=tuple(pcb.ToMM(f.GetPosition()));mid=tuple(sum(q[i] for q in pts)/2 for i in (0,1))
            if sum(direction[i]*(mid[i]-origin[i]) for i in (0,1))<0:direction=(-direction[0],-direction[1])
            normal=(-direction[1],direction[0]);inset=1.10 if pair[0] in ('MIC_TXP','MIC_RXP') else .70;end=tuple(centre[i]+direction[i]*inset for i in (0,1));sign=1 if sum((pts[0][i]-mid[i])*normal[i] for i in (0,1))>=0 else -1
            for pad,via,side in zip(ps,vias,(sign,-sign)):
                goal=tuple(end[i]+side*(WIDTH+GAP)/2*normal[i] for i in (0,1));before={t.m_Uuid.AsString() for t in g.b.GetTracks()}
                for layer in ('F','B'):g.track(pad.GetNetname(),[via,goal],WIDTH,layer)
                added=[t for t in g.b.GetTracks() if t.m_Uuid.AsString() not in before]
                for t in added:g.data_stub_items.append(dict(item=t,endpoint=goal,layer=t.GetLayer()))
                if (ref,pad.GetNumber()) in g.fine_escape_items:g.fine_escape_items[(ref,pad.GetNumber())].extend(added)
    pcb.SaveBoard('/tmp/usb3-prepower-reserved.kicad_pcb',g.b)
    from route_usb3_power import prepare_local_bypasses
    #UUIDs/editor timestamps, local net IDs and unordered record order are
    #normalized. All named assignments, hierarchy, geometry and keepouts stay.
    reserved=Path('/tmp/usb3-prepower-reserved.kicad_pcb').read_text()
    normalized=canonical_preboard(reserved)
    helper_source=ROOT/'source/generator/route_usb3_power.py'
    helper_bytes=helper_source.read_bytes();child_bytes=CHILD_RESERVATION_PATH.read_bytes()
    cache_key=hashlib.sha256(normalized.encode()+helper_bytes+child_bytes).hexdigest()
    cache_dir=Path('/tmp/usb3-power-cache');cache_dir.mkdir(exist_ok=True)
    cache_board=cache_dir/(cache_key+'.kicad_pcb');cache_meta=cache_dir/(cache_key+'.json')
    if cache_board.exists() and cache_meta.exists():
        cached=json.loads(cache_meta.read_text());g.b=pcb.LoadBoard(str(cache_board));g.fps={f.GetReference():f for f in g.b.GetFootprints()};g.nets={name:g.b.FindNet(name) for name in g.nets}
        by_uuid={t.m_Uuid.AsString():t for t in g.b.GetTracks()}
        g.fine_escape_items={tuple(key.split('.')):[by_uuid[u] for u in uuids] for key,uuids in cached['fine_escape_item_uuids'].items()}
        g.data_stub_items=[dict(item=by_uuid[row['uuid']],endpoint=row['endpoint'],layer=row['layer']) for row in cached['data_stub_items']]
        prep=cached['report'];prep['cache_hit']=True;print('Reused identical verified prepower geometry',flush=True)
    else:
        prep=prepare_local_bypasses(g.b)
        if prep['complete']:
            pcb.SaveBoard(str(cache_board),g.b)
            cache_meta.write_text(json.dumps({'report':prep,'fine_escape_item_uuids':{'.'.join(key):[t.m_Uuid.AsString() for t in items] for key,items in g.fine_escape_items.items()},'data_stub_items':[dict(uuid=row['item'].m_Uuid.AsString(),endpoint=row['endpoint'],layer=row['layer']) for row in g.data_stub_items]},indent=2)+'\n')
    prep['cache_key']=cache_key
    prep['helper_sha256']=hashlib.sha256(helper_bytes).hexdigest();prep['child_reservation_sha256']=hashlib.sha256(child_bytes).hexdigest();prep['input_geometry_sha256']=hashlib.sha256(normalized.encode()).hexdigest()
    (DEST.parent/'pre-power-escapes.json').write_text(json.dumps(prep,indent=2)+'\n')
    assert prep['complete'],'Local power/bypass escape preparation failed; data replay must not hide it'
    if os.environ.get('USB3_PREP_ONLY')=='1':
        pcb.SaveBoard('/tmp/usb3-prepared-data-launches.kicad_pcb',g.b);return
    #Clock copper is a real obstacle before long data, rather than a late
    #periodic signal squeezed into an already-filled SuperSpeed corridor.
    fixer.CLR=.20;clock_routes=[]
    def clockpoint(pad):
        x,y=pcb.ToMM(pad.GetPosition());return (x,y+.7) if pad.GetParent().GetReference()=='U500' else (x,y)
    for pad in g.fps['U500'].Pads():
        if pad.GetNetname() in ('HUB_XI','HUB_XO'):g.track(pad.GetNetname(),[tuple(pcb.ToMM(pad.GetPosition())),clockpoint(pad)],.17,'F')
    clockfx=USB3Fixer(g.b);clockfx.si_guard=make_si_guard(clockfx,g.b)
    for net in ('HUB_XI','HUB_XO'):
        ps=[p for f in g.b.GetFootprints() for p in f.Pads() if p.GetNetname()==net];done=[ps.pop(0)]
        while ps:
            distance,i,a=min((math.dist(clockpoint(a),clockpoint(b)),i,a) for i,b in enumerate(ps) for a in done);b=ps.pop(i)
            ok=clockfx.route(net,clockpoint(a),clockpoint(b),w=.17,step=.06,win=6,layers=('F',));clock_routes.append(dict(net=net,source=a.GetParent().GetReference()+'.'+a.GetNumber(),target=b.GetParent().GetReference()+'.'+b.GetNumber(),routed=ok));done.append(b)
    (DEST.parent/'pre-clock-routes.json').write_text(json.dumps(clock_routes,indent=2)+'\n')
    pcb.SaveBoard('/tmp/usb3-predata-clocks.kicad_pcb',g.b)
    assert all(q['routed'] for q in clock_routes),'Short F-only clock routing failed before data'
    if os.environ.get('USB3_MAZE_PROBE')!='1':pcb.SaveBoard(str(DEST/'usb3_frontend.kicad_pcb'),g.b)
    report=route_board(g)
    if os.environ.get('USB3_MAZE_PROBE')=='1':
        Path('/tmp/usb3-maze-probe.json').write_text(json.dumps(report,indent=2)+'\n');return
    report['search_reservations']={'child_arrival_actual_legs_source':str(CHILD_RESERVATION_PATH),'child_arrival_source_sha256':hashlib.sha256(CHILD_RESERVATION_PATH.read_bytes()).hexdigest(),'child_arrival_legs':CHILD_RESERVATION['legs'],'future_SS_exit_guides':SS_EXIT_RESERVATIONS,'note':'Search-only allocations; final independent audit measures saved copper, not these guide envelopes.'}
    #Accepted routes are emitted independently of these temporary physical
    #obstacles (add_track ignores them for deduplication). Remove every
    #reservation now, retaining only actual validated route copper.
    stub_ids={row['item'].m_Uuid.AsString() for row in g.data_stub_items};removed_stubs=[]
    for row in g.data_stub_items:
        item=row['item'];goal=row['endpoint'];net=item.GetNetname()
        continuation=any(t.GetClass()=='PCB_TRACK' and t.GetLayer()==row['layer'] and t.GetNetname()==net and t.m_Uuid.AsString() not in stub_ids and min(math.dist(tuple(pcb.ToMM(t.GetStart())),goal),math.dist(tuple(pcb.ToMM(t.GetEnd())),goal))<1e-5 for t in g.b.GetTracks())
        g.b.Remove(item);removed_stubs.append(dict(net=net,layer=g.b.GetLayerName(row['layer']),endpoint=goal,had_actual_route_at_endpoint=continuation))
    report['unused_layer_launch_stubs_removed']=removed_stubs
    #A successful F-only route can make an earlier through-via reservation
    #unnecessary. Remove that unused plated stub; remove its short reserved
    #launch as well only when all actual component pads remain connected.
    from audit_usb3_signals import pointseg,pair_key,net_connectivity
    removed=[]
    for via in list(g.b.GetTracks()):
        if via.GetClass()!='PCB_VIA' or not pair_key(via.GetNetname()):continue
        q=tuple(pcb.ToMM(via.GetPosition()));net=via.GetNetname();layers=set()
        for t in g.b.GetTracks():
            if t.GetClass()=='PCB_TRACK' and t.GetNetname()==net and pointseg(q,tuple(pcb.ToMM(t.GetStart())),tuple(pcb.ToMM(t.GetEnd())))[0]<=(pcb.ToMM(t.GetWidth())+pcb.ToMM(via.GetWidth()))/2+1e-6:layers.add(t.GetLayer())
        if pcb.F_Cu in layers and pcb.B_Cu in layers:continue
        g.b.Remove(via);deleted=[]
        for items in g.fine_escape_items.values():
            if any(it.m_Uuid.AsString()==via.m_Uuid.AsString() for it in items):
                present={t.m_Uuid.AsString() for t in g.b.GetTracks()};deleted=[it for it in items if it.GetClass()=='PCB_TRACK' and it.m_Uuid.AsString() in present];break
        baseline=all(r['connected'] for r in net_connectivity(g.b,{net}))
        if baseline:
            for t in deleted:g.b.Remove(t)
            if not all(r['connected'] for r in net_connectivity(g.b,{net})):
                for t in deleted:g.b.Add(t)
                deleted=[]
        else:deleted=[]
        removed.append(dict(net=net,via_mm=q,retained_layers=[g.b.GetLayerName(L) for L in layers],removed_short_launch=bool(deleted)))
    report['unused_reserved_signal_vias_removed']=removed
    #Continuous inner ground planes; no power/signal routing onL2/L3.
    for layer in ('In1','In2'):g.zone('GND',layer,[(.5,.5),(W-.5,.5),(W-.5,H-.5),(.5,H-.5)],1,.15,minw=.15)
    fx=USB3Fixer(g.b)
    holes=[p for f in g.b.GetFootprints() for p in f.Pads() if p.GetDrillSize().x>0]
    for f in g.b.GetFootprints():
        for p in f.Pads():
            if g.parts[f.GetReference()]['sym']=='pdb:TPD2EUSB30A_DRT':continue
            if f.GetReference() in ('U500','U501','U502','U503') and p.GetSize().x>pcb.FromMM(1):continue
            if p.GetNetname()!='GND' or p.GetDrillSize().x>0:continue
            x,y=pcb.ToMM(p.GetPosition())
            for dx,dy in ((0,.8),(0,-.8),(.8,0),(-.8,0),(1.2,0),(-1.2,0)):
                if child_corridor_distance((x+dx,y+dy))<.50:continue
                if not any(q.GetAttribute()==pcb.PAD_ATTRIB_SMD and q.HitTest(pcb.VECTOR2I(pcb.FromMM(x+dx),pcb.FromMM(y+dy)),pcb.FromMM(.4)) for f2 in g.b.GetFootprints() for q in f2.Pads()) and all(fx.free(ly,'GND',x+dx,y+dy,.3) for ly in (pcb.F_Cu,pcb.B_Cu)) and all(math.dist((x+dx,y+dy),tuple(pcb.ToMM(h.GetPosition())))>.56+max(pcb.ToMM(h.GetDrillSize().x),pcb.ToMM(h.GetDrillSize().y))/2 for h in holes) and not any(math.dist((x+dx,y+dy),tuple(pcb.ToMM(t.GetPosition())))<.60 for t in g.b.GetTracks() if isinstance(t,pcb.PCB_VIA)):
                    g.via('GND',x+dx,y+dy,.6,.3);fx._index=None
                    fx.route('GND',(x,y),(x+dx,y+dy),w=.17,step=.08,win=1,layers=('F' if p.IsOnLayer(pcb.F_Cu) else 'B',));break
    for ref in ('U500','U501','U502','U503'):
        f=g.fps[ref]
        for p in f.Pads():
            if p.GetNetname()=='GND' and p.GetSize().x>pcb.FromMM(1):
                x,y=pcb.ToMM(p.GetPosition())
                for dx in (-.3,.3):
                    if not any(math.dist((x+dx,y),tuple(pcb.ToMM(t.GetPosition())))<.60 for t in g.b.GetTracks() if isinstance(t,pcb.PCB_VIA)):g.via('GND',x+dx,y,.6,.3)
    #Every actualSSlayertransition gets a nearbygroundreturn. Avoid all
    #SMTsolderlands and componentdrills; the returns join both innerplanes.
    ss_nets={net for pair in circuit.SUPERSPEED_PAIRS for net in pair};returns=[]
    signal_vias=[v for v in g.b.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname() in ss_nets]
    old_via=fixer.VIA_D,fixer.VIA_DR;fixer.VIA_D,fixer.VIA_DR=.6,.3
    for via in signal_vias:
        q=tuple(pcb.ToMM(via.GetPosition()));ground=[v for v in g.b.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname()=='GND']
        distance=min((math.dist(q,tuple(pcb.ToMM(v.GetPosition()))) for v in ground),default=1e9)
        added=None
        if distance>1.5:
            for radius in (1.0,1.2,1.5,1.8):
                for angle in range(0,360,45):
                    t=math.radians(angle);v=(q[0]+radius*math.cos(t),q[1]+radius*math.sin(t));pt=pcb.VECTOR2I(pcb.FromMM(v[0]),pcb.FromMM(v[1]))
                    if child_corridor_distance(v)<.50:continue
                    if not fx.via_ok('GND',*v):continue
                    if any(pad.GetAttribute()==pcb.PAD_ATTRIB_SMD and pad.HitTest(pt,pcb.FromMM(.4)) for f in g.b.GetFootprints() for pad in f.Pads()):continue
                    if any(math.dist(v,tuple(pcb.ToMM(h.GetPosition())))<.15+max(pcb.ToMM(h.GetDrillSize().x),pcb.ToMM(h.GetDrillSize().y))/2+.45 for h in holes):continue
                    fx.add_via('GND',*v);added=v;break
                if added:break
        ground=[v for v in g.b.GetTracks() if v.GetClass()=='PCB_VIA' and v.GetNetname()=='GND'];distance=min((math.dist(q,tuple(pcb.ToMM(v.GetPosition()))) for v in ground),default=1e9)
        returns.append({'signal_net':via.GetNetname(),'signal_via_mm':q,'added_ground_via_mm':added,'nearest_ground_via_mm':distance,'target_maximum_mm':2.0})
    fixer.VIA_D,fixer.VIA_DR=old_via;report['ground_returns']=returns
    board=DEST/'usb3_frontend.kicad_pcb';pcb.SaveBoard(str(board),g.b)
    #KiCad7's filler needs a freshly loaded board/project for this new design.
    g.b=pcb.LoadBoard(str(board));pcb.ZONE_FILLER(g.b).Fill(g.b.Zones())
    pcb.SaveBoard(str(board),g.b)
    pcb.WriteDRCReport(g.b,str(DEST.parent/'drc.rpt'),pcb.EDA_UNITS_MILLIMETRES,True)
    report['pcb_sha256']=hashlib.sha256(board.read_bytes()).hexdigest()
    (DEST.parent/'routing-evidence.json').write_text(json.dumps(report,indent=2)+'\n')
    libs=sorted({p['fp'].split(':')[0] for p in circuit.PARTS})
    (DEST/'fp-lib-table').write_text('(fp_lib_table\n'+''.join(f' (lib (name "{lib}")(type "KiCad")(uri "'+('${KIPRJMOD}/Robot_PDB.pretty' if lib=='Robot_PDB' else '${KICAD7_FOOTPRINT_DIR}/'+lib+'.pretty')+'")(options "")(descr ""))\n' for lib in libs)+')\n')
    (DEST.parent/'layout-status.json').write_text(json.dumps({'released':False,'board_mm':[W,H],'thickness_mm':.8,'copper':'4layer2ozouter1ozinner;L2/L3continuousGND;JLC040821-7628','differential_target_ohm':90,'factory_calculator_geometry_mm':{'width':WIDTH,'gap':GAP,'minimum_clearance':.16,'dielectric_to_reference':.203},'superspeed_connections_routed':sum(e['routed'] for e in report['superspeed']),'superspeed_connections_total':len(report['superspeed']),'release_holds':circuit.RELEASE_HOLDS},indent=2)+'\n')
    print('Saved',board,'SS routed',sum(e['routed'] for e in report['superspeed']),'/',len(report['superspeed']),flush=True)

if __name__=='__main__':main()
