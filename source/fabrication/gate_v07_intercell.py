"""Bind the intercell engineering checks to one exact saved PCB.

Native DRC/ERC, component/pin/DFM checks, USB-cell checks and manufacturing
review remain separate exporter gates. This gate never creates fabrication data.
"""
import argparse,ast,hashlib,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REPORTS={'routing':'integration-routing.json','links':'intercell-connectivity-audit.json','copper':'intercell-copper-audit.json','isolation':'intercell-usb-isolation-audit.json','keepout':'intercell-hs-keepout-audit.json'}
FS_WINDOWS={'CAN USB FullSpeed12Mb/s':[(201.8,116.5,203.2,117.3),(198.2,118.8,200.6,119.7),(195.2,121.8,196.6,122.7)],'PWM USB FullSpeed12Mb/s':[(205.8,102.85,207.8,104.9)]}
FS_CAUSES={'CAN USB FullSpeed12Mb/s':{'DXL0_TNOW','DXL1_TX','DXL1_RX'},'PWM USB FullSpeed12Mb/s':{'P1_DM'}}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def numeric(value,default=math.inf):
 try:return float(value) if value is not None else default
 except (TypeError,ValueError):return default
def _evaluate(board,report_dir):
 board=Path(board);directory=Path(report_dir);errors=[];reports={};hashes={};accepted=[];hs_summary=None
 def check(good,message):
  if not good:errors.append(message)
 try:board_hash=sha(board)
 except OSError as error:return {'pass':False,'errors':[str(error)]}
 for key,name in REPORTS.items():
  path=directory/name
  try:hashes[name]=sha(path);reports[key]=json.loads(path.read_text())
  except (OSError,ValueError) as error:errors.append(f'{name}: {error}');continue
  field='routed_board_sha256' if key=='routing' else 'board_sha256';check(reports[key].get(field)==board_hash,f'{name}: stale or missing PCB hash')
 if len(reports)==len(REPORTS):
  links=reports['links'];check(links.get('connected')==links.get('total')==30,'Required intercell links are not30/30');check(links.get('auxiliary_connected')==links.get('auxiliary_total')==8,'Auxiliary links are not8/8')
  check(links.get('support_grounds_connected')==links.get('support_grounds_total')==13,'Added support-ground connections are not13/13')
  tree=ast.parse((ROOT/'source/generator/rev07.py').read_text());assignment=next(x for x in tree.body if isinstance(x,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='INTEGRATION_PLACEMENTS' for t in x.targets));placements=ast.literal_eval(assignment.value);placement_hash=hashlib.sha256(json.dumps(placements,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  routing=reports['routing'];check(routing.get('integration_placements_sha256')==placement_hash,'Shared integration placements changed after routing evidence');check(routing.get('child_arrival_reservation_sha256')==sha(ROOT/'source/generator/usb_child_arrival_reservation.json'),'Exact child arrival reservation changed after routing evidence')
  escapes=[x for x in routing.get('ordinary_routes',[]) if x.get('action')=='HS arrival uses preserved USB-cell package escapes'];check(len(escapes)==1 and escapes[0].get('preserved') and len(escapes[0].get('via_uuids',[]))==2,'HS did not use the two preserved USB-cell package fine vias')
  check(not routing.get('stale_USB_inventory_references') and not routing.get('obsolete_USB_inventory_references'),'Routing used stale USB inventory')
  check(routing.get('generator_sha256')==sha(ROOT/'source/generator/route_v07.py'),'Routing generator changed after the saved routing evidence')
  profile=board.with_suffix('.kicad_pro');check(profile.exists() and routing.get('profile_sha256')==sha(profile),'PCB profile changed after routing evidence')
  pairs=routing.get('pairs',[]);check(all(x.get('routed') and not x.get('rolled_back') for x in pairs),'A paired route failed or rolled back');check({tuple(x['pair']) for x in pairs}=={('P3_DP','P3_DM'),('P4_DP','P4_DM'),('HUB_CHILD_DP','HUB_CHILD_DM')},'Expected USB2 pair records are incomplete')
  copper=reports['copper'];check(all(x.get('routed') and not x.get('missing_recorded_segments') for x in copper.get('usb',[])),'Actual PCB does not contain all recorded USB2 segments')
  for item in copper.get('power',[]):
   check(all(x.get('verified_actual_track') for x in item.get('explicit_track_geometry',[])),f"Missing explicit power bridge:{item.get('net')}")
  channels=copper.get('complete_usb2_channels',[]);check(len(channels)==3,'Expected three complete USB2 channels')
  for channel in channels:
   name=channel.get('channel','');highspeed='HighSpeed' in name
   check(highspeed or name in FS_WINDOWS,f'Unrecognized USB2 channel:{name}')
   for polarity in ('positive','negative'):
    leg=channel.get(polarity,{});label=f'{name} {polarity}';check(leg.get('connected_path_found'),f'{label}: no physical end-to-end path')
    check(numeric(leg.get('off_path_outside_pad_mm'))<=1e-5,f'{label}: external stub/parallel copper remains')
    check(math.isclose(leg.get('service_gap_reference_coverage') or 0,1,abs_tol=1e-9),f'{label}: service-gap ground reference incomplete')
    gaps=leg.get('reference_inspection_points',[])
    samples=leg.get('reference_samples',0);covered=leg.get('ground_covered_samples',-1)
    check(isinstance(samples,int) and samples>0 and isinstance(covered,int) and covered>=0 and samples-covered==len(gaps),f'{label}: reference sample accounting is incomplete')
    check(samples>0 and math.isclose(numeric(leg.get('reference_coverage'),0),covered/samples if samples else 0,abs_tol=1e-9),f'{label}: inconsistent reference coverage')
    check(leg.get('service_gap_reference_samples',0)>0,f'{label}: no service-gap reference samples')
    if highspeed:
     check(math.isclose(leg.get('reference_coverage') or 0,1,abs_tol=1e-9) and not gaps,f'{label}: HS full-channel reference incomplete')
     check(0<numeric(leg.get('conservative_drawn_trace_plus_barrels_mm'))<=150,f'{label}: HS drawn trace plus barrels exceeds150mm or is missing')
    elif name in FS_WINDOWS:
     for gap in gaps:
      q=gap.get('point',[]);causes=set(gap.get('reference_void_causes',[]));known=len(q)==2 and gap.get('layer')=='B.Cu' and gap.get('reference')=='In2.Cu' and any(a<=q[0]<=c and bb<=q[1]<=d for a,bb,c,d in FS_WINDOWS[name]) and bool(causes) and causes<=FS_CAUSES[name]
      check(known,f'{label}: new/unattributed reference gap:{gap}')
     if gaps:accepted.append({'channel':name,'polarity':polarity,'reference_coverage':leg.get('reference_coverage'),'explicit_inherited_reference_gaps':gaps,'qualification':'Previously accepted bounded12Mb/s source-layout SI/EMI bench exception; not100% full-channel reference.'})
   if highspeed:
    check(numeric(channel.get('conservative_drawn_skew_mm'))<=1.25 and numeric(channel.get('total_skew_mm'))<=1.25,'HS total or conservative drawn skew exceeds1.25mm')
    hs_summary={key:channel.get(key) for key in ('channel','total_skew_mm','conservative_drawn_skew_mm')};hs_summary['drawn_lengths_mm']=[channel.get(p,{}).get('conservative_drawn_trace_plus_barrels_mm') for p in ('positive','negative')]
  check(hs_summary is not None,'No HighSpeed channel measurement')
  check(reports['isolation'].get('pass') is True and not reports['isolation'].get('violations'),'Intercell USB2-to-SS isolation screen failed')
  keepout=reports['keepout'];check(keepout.get('guidance_met_outside_bounded_packages') is True and not keepout.get('violations') and not keepout.get('filled_power_zone_violations'),'HS signal/positive-pour keepout screen failed')
  regions={x['reference']:x for x in keepout.get('escape_regions',[])};check(set(regions)=={'U10','U9500'},'Unexpected HS package exception inventory')
  for ref,width in (('U10',10),('U9500',13)):
   region=regions.get(ref,{});box=region.get('box_mm',[]);check(region.get('body_expansion_mm')==3 and len(box)==4 and abs(box[2]-box[0]-width)<1e-6 and abs(box[3]-box[1]-width)<1e-6,f'{ref}: package exception exceeded the approved physical bounds')
 return {'pass':not errors,'board':str(board),'board_sha256':board_hash,'errors':errors,'highspeed':hs_summary,'accepted_bounded_inherited_fs_reference_exceptions':accepted,'audit_files_sha256':hashes,'limits':'Intercell gate only. Native zero-errors/opens, pin/DFM/cell checks, manufacturer review and prototype electrical/thermal/USB bench qualification remain separate.'}
def evaluate(board,report_dir):
 try:return _evaluate(board,report_dir)
 except Exception as error:return {'pass':False,'board':str(board),'errors':['Intercell evidence is incomplete or invalid:'+str(error)]}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('board',nargs='?',default=str(ROOT/'revisions/v0.7/kicad/robot_pdb.kicad_pcb'));ap.add_argument('report_dir',nargs='?',default=str(ROOT/'revisions/v0.7'));args=ap.parse_args();result=evaluate(args.board,args.report_dir);out=Path(args.report_dir);out.mkdir(parents=True,exist_ok=True);(out/'intercell-release-gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));raise SystemExit(0 if result['pass'] else 1)
if __name__=='__main__':main()
