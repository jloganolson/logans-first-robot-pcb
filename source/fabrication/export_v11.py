#!/usr/bin/env python3
"""Prepare the v0.11 PROTOTYPE QUOTE package. Never uploads or purchases.

Run through with_kicad.sh. Re-runs audit_v11.py first and stops on any finding.
The BOM is the factory-matched v0.10 BOM with only the part changes in
revisions/v0.11/derivation.json applied. Placements come from a fresh position
export of the v0.11 board and are cross-checked against the v0.10 placement
file: a part that did not move must be identical, and a part that moved must
have turned by exactly the angle its footprint turned.
"""
import collections,csv,hashlib,json,re,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BOARD=ROOT/'revisions/v0.11/kicad/robot_pdb.kicad_pcb';OUT=ROOT/'outputs/v11-order-preparation'
V09=ROOT/json.loads((ROOT/'outputs/v10-order-preparation/current-package.json').read_text())['directory']   # the v0.10 package is the baseline here
LAYERS='F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.SilkS,B.SilkS,F.Mask,B.Mask,Edge.Cuts'
OFFSETS=[(r'^SOT-23',-90),(r'^LQFP-',270),(r'^HTSSOP-',270),(r'^VSSOP-8_',180),(r'^TDSON-8-1',270),(r'^CP_Elec_10x10',180),(r'^(.*?_|V)?QFN-(16|20|24|28|40|56)(-|_|$)',270)]
# Corrections found in the factory placement preview of v0.10 (v0.9 starting values were wrong for these).
# J101/J501 XT30PW bodies rendered 180 degrees from their footprint outline.
# U9902 (UQFN-10, the USB data switch) rendered 90 degrees off its pads with pin 1 at the wrong corner; the
# v0.9 offset table gives QFN packages 270 but its pattern did not match this footprint name.
ROTATION_FIXES={'J101':180,'J501':180,'U9902':270}
# Found by opening every oriented part one at a time in the factory placement viewer for v0.11 (click the part's
# row in the list; the view jumps to it). These were drawn off their pads; the same rows were wrong in the v0.9
# and v0.10 placement files, which had only been spot-checked. Degrees are added to the v0.10 value.
#   90 degrees off: Q7001 (SOT-23), U9900 and U9904 (SOT-23-6), U2 (VQFN-20), U14 (QFN-24), U7007 (TSSOP-14),
#                   U3-U7 and U7003 (SO PowerPAD-8, the six TPS54560 regulators)
#   180 degrees:    J3 (Micro-Fit header; latch side was facing the wrong way)
# Checked and correct: all electrolytics, both crystals, LEDs, SS1060 diodes, FETs, U1, U10, U11, U12, U13, U15,
# U16, U17, U7002, U7006, U7009, U9902, C9902, USB-C, XT30s, JST VH headers.
V11_ROTATION_FIXES={'Q7001':270,'U9900':270,'U9904':270,'U2':270,'U14':90,'U7007':270,'U3':270,'U4':270,'U5':270,'U6':270,'U7':270,'U7003':270,'J3':180}
def sha(q):return hashlib.sha256(Path(q).read_bytes()).hexdigest()
def run(cmd,log):
 r=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
 with open(log,'a') as f:f.write('$ '+' '.join(map(str,cmd))+'\n'+r.stdout+r.stderr+'\n')
 if r.returncode:raise SystemExit('failed: '+' '.join(map(str,cmd))+'\n'+r.stderr)
def rows(path):
 with open(path,newline='') as f:return list(csv.DictReader(f))
def write(path,head,data):
 with open(path,'w',newline='') as f:w=csv.writer(f);w.writerow(head);w.writerows(data)

def main():
 audit=subprocess.run([sys.executable,str(ROOT/'source/fabrication/audit_v11.py')],capture_output=True,text=True)
 if audit.returncode:raise SystemExit('audit_v11 holds the export:\n'+audit.stdout[-2000:])
 D=json.loads((ROOT/'revisions/v0.11/derivation.json').read_text());h=sha(BOARD);assert h==D['board_sha256']
 pkg=OUT/('package-'+h[:12]);shutil.rmtree(pkg,ignore_errors=True);(pkg/'gerbers').mkdir(parents=True);log=pkg/'export.log'
 run(['kicad-cli','pcb','export','gerbers','--layers',LAYERS,'--subtract-soldermask','-o',str(pkg/'gerbers')+'/',BOARD],log)
 run(['kicad-cli','pcb','export','drill','--format','excellon','--excellon-separate-th','-o',str(pkg/'gerbers')+'/',BOARD],log)
 files=sorted((pkg/'gerbers').iterdir());assert len([f for f in files if f.suffix not in('.drl','.gbrjob')])==11 and sum(f.suffix=='.drl' for f in files)==2
 # BOM: v0.9 factory-matched rows with the recorded part changes
 ch=D['part_changes'];bom=[];fitted=set()
 for r in rows(V09/'BOM_JLCPCB.csv'):
  refs=r['Designator'].split(',');fitted|=set(refs);keep=[x for x in refs if x not in ch];new=collections.OrderedDict()
  for x in refs:
   if x in ch:
    c=ch[x];assert r['LCSC Part #']==c['old']['lcsc'],(x,r);new.setdefault((c['value'],c['lcsc'],c.get('footprint',r['Footprint']).split(':',1)[-1]),[]).append(x)
  if keep:bom.append([r['Comment'],','.join(keep),r['Footprint'],r['LCSC Part #']])
  for (value,lcsc,fp_name),group in new.items():bom.append([value,','.join(group),fp_name,lcsc])
 merged=collections.OrderedDict()                       # changed parts from different old lines may now share a part
 for comment,des,fp_name,lcsc in bom:
  k=(comment,fp_name,lcsc)
  if k in merged:merged[k]+=','+des
  else:merged[k]=des
 bom=[[k[0],v,k[1],k[2]] for k,v in merged.items()]
 assert set(ch)<=fitted;write(pkg/'BOM_JLCPCB.csv',['Comment','Designator','Footprint','LCSC Part #'],bom)
 # placement: fresh export, v0.9 starting offsets, cross-checked against v0.9
 run(['kicad-cli','pcb','export','pos','--format','csv','--units','mm','--side','both','-o',pkg/'raw-positions.csv',BOARD],log)
 fp={r[1]:r[2] for r in bom for r in [(None,x,r[2]) for x in r[1].split(',')]}
 old={r['Designator']:r for r in rows(V09/'CPL_JLCPCB.csv')};oldraw={r['Ref']:r for r in rows(V09/'raw-positions.csv')};cpl=[];moved=0
 for r in rows(pkg/'raw-positions.csv'):
  ref=r['Ref']
  if ref not in fitted:continue
  assert r['Side']=='top',ref;off=next((v for pat,v in OFFSETS if re.match(pat,fp[ref])),0)
  x,y,rot=float(r['PosX']),float(r['PosY']),(float(r['Rot'])+off)%360;o=old[ref]
  rot=(rot+ROTATION_FIXES.get(ref,0))%360;q=oldraw[ref];turn=(float(r['Rot'])-float(q['Rot']))%360
  if abs(x-float(o['Mid X']))<1e-4 and abs(y-float(o['Mid Y']))<1e-4:assert abs(rot-float(o['Rotation']))<1e-4,('rotation changed on a part that did not move',ref)
  else:
   moved+=1;assert (re.search(r'(\d+)$',ref) and 7000<=int(re.search(r'(\d+)$',ref)[1])<9000) or ref in D['placed']['plugs moved to an edge'],('a part outside the servo block moved',ref)
   assert abs((rot-float(o['Rotation']))%360-turn)<1e-4,('factory rotation did not follow the footprint',ref,rot,o,turn)
  rot=(rot+V11_ROTATION_FIXES.get(ref,0))%360
  cpl.append([ref,x,y,'Top',rot])
 assert {c[0] for c in cpl}==fitted==set(old);write(pkg/'CPL_JLCPCB.csv',['Designator','Mid X','Mid Y','Layer','Rotation'],cpl)
 req=dict(board_size_mm=D['outline_mm'],layers=4,thickness_mm=1.6,factory_stackup='JLC04161H-7628 (factory default; required for Economic assembly)',specify_stackup='Yes, JLC04161H-7628',impedance_control='No requirement (not purchased)',
  outer_copper_oz=1,inner_copper_oz=.5,min_via='0.3mm/(0.4/0.45mm) tier: every via hole is 0.30 mm or larger',
  usb_pair=dict(high_speed_width_mm=.275,high_speed_gap_mm=.19,reference='inner ground, 0.2104 mm 7628 prepreg',note='upstream pair widened in place from v0.9 0.165/0.300; JLCPCB calculator gives 90 ohm at 0.269/0.175 on this stack; no factory test coupon; Full-Speed pairs unchanged'),
  surface_finish='LeadFree HASL (ENIG acceptable if budget allows)',assembly='Economic preferred, top side, 2 of 5 assembled, confirm parts placement, do not auto-confirm production file')
 (pkg/'manufacturing-requirements.json').write_text(json.dumps(req,indent=1)+'\n')
 (pkg/'STACKUP_REQUIREMENTS.txt').write_text('Robot PDB v0.11. 4 layers, 1.6 mm, stackup JLC04161H-7628, 1 oz outer / 0.5 oz inner copper.\nUSB 2.0 High-Speed pair is 0.275 mm wide / 0.19 mm gap over 0.2104 mm prepreg. Do not substitute a thinner prepreg.\n')
 shutil.copyfile(V09/'hand-fit-and-harness.csv',pkg/'hand-fit-and-harness.csv')
 z=pkg/'Robot_PDB_v11_Gerbers.zip'
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as a:
  for f in files+[pkg/'STACKUP_REQUIREMENTS.txt']:a.write(f,f.name)
 for name,layers in (('board-top.svg','F.Cu,F.SilkS,F.Mask,Edge.Cuts'),('board-bottom.svg','B.Cu,B.SilkS,Edge.Cuts'),('assembly-top.svg','F.Fab,F.SilkS,Edge.Cuts')):
  run(['kicad-cli','pcb','export','svg','--layers',layers,'--page-size-mode','2','--exclude-drawing-sheet','-o',pkg/name,BOARD],log)
 manifest=dict(status='PROTOTYPE QUOTE PACKAGE; NOT A PURCHASE OR PRODUCTION APPROVAL',board_sha256=h,schematic_sha256=D['schematic_sha256'],source_v10_board_sha256=D['source_board_sha256'],
  audit=json.loads((OUT/'audit-v11.json').read_text())['status'],bom_lines=len(bom),fitted_references=len(fitted),supplier_codes=len({r[3] for r in bom}),
  files={f.name:sha(f) for f in sorted(pkg.iterdir()) if f.is_file()},moved_fitted_parts=moved,v11_rotation_fixes=V11_ROTATION_FIXES,placement_rotations='v0.10 values (v0.9 starting values plus '+json.dumps(ROTATION_FIXES)+' found in the factory preview); moved servo-block parts turned with their footprints; factory orientation review still required')
 (pkg/'manifest.json').write_text(json.dumps(manifest,indent=1)+'\n');(OUT/'current-package.json').write_text(json.dumps(dict(directory=str(pkg.relative_to(ROOT)),board_sha256=h,gerber_zip_sha256=sha(z)),indent=1)+'\n')
 print('package',pkg.relative_to(ROOT),'bom lines',len(bom),'fitted',len(fitted),'codes',manifest['supplier_codes'])
if __name__=='__main__':main()
