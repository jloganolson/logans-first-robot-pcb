#!/usr/bin/env python3
"""Timestamped JLC catalog component allocation; never places an order.

Run under with_kicad.sh when the inventory module imports pcbnew. Only fitted
parts with supplier codes are priced. Manual/external work and assembly fees
remain outside this catalog screen. Quantity tiers use the complete shared SKU
quantity for all requested boards before allocating costs to functions.
"""
import argparse,collections,concurrent.futures,datetime,hashlib,importlib,json,re,sys,time,urllib.request
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
API='https://cart.jlcpcb.com/shoppingCart/smtGood/getComponentDetail?componentCode='
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()

def functional_section(part):
 cell=part.get('source_cell','');block=part.get('block','');ref=part['ref']
 if cell=='base':
  letter=re.match(r'BASE\. ([A-Z])\.',block)
  key=letter[1] if letter else ''
  return {'A':'Shared battery input/protection','B':'Thor supply and board header',
   'C':'Raspberry Pi 5V supply','D':'USB control 5V supply','E':'XL330 5V power',
   'F':'XL430 10.8V power','G':'Audio/AUX power and codec/amplifier',
   'I':'USB2 hub, host attachment and shared power protection',
   'J':'Audio/AUX power and codec/amplifier','K':'Dynamixel dual UART and buffers'}.get(key,'Other base: '+block)
 if cell=='thor_output':return 'Thor supply and board header'
 if cell=='usb2':return 'USB2 hub, host attachment and shared power protection'
 if cell=='motor_input':return 'Motor input reverse-polarity protection'
 if cell=='motor':
  local=block.removeprefix('MOTOR. ')
  if local.startswith(('C.','D.')):return 'Motor autonomous resistor-clamp control'
  return 'Motor 22.34V supply and bus support'
 if cell=='io':
  local=block.removeprefix('IO. ')
  if local.startswith(('B1.','C.')):return 'Wheel CAN USB MCU and transceiver'
  if local.startswith(('A.','B2.','D.')):return 'MG90S power and USB PWM control'
  return 'Other I/O: '+local
 return 'Other: '+(cell or block or ref)

def load_inventory(args):
 if args.inventory:
  src=args.inventory.resolve();data=json.loads(src.read_text())
  parts=data['inventory'] if isinstance(data,dict) else data
  sources={str(src):digest(src)}
 else:
  if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*',args.module):raise ValueError('Invalid inventory module')
  sys.path.insert(0,str(ROOT/'source/generator'))
  before={str(q.resolve()):digest(q) for q in (ROOT/'source/generator').glob('*.py')}
  module=importlib.import_module(args.module);parts=module.PARTS
  loaded={Path(m.__file__).resolve() for m in tuple(sys.modules.values()) if getattr(m,'__file__',None)
          and str(Path(m.__file__).resolve()).startswith(str(ROOT/'source/generator')+'/')}
  sources={str(q):digest(q) for q in loaded if q.suffix=='.py'}
  changed=[q for q,h in sources.items() if before.get(q)!=h]
  if changed:raise RuntimeError('Inventory sources changed during import: '+str(changed))
 if not isinstance(parts,list) or len({q['ref'] for q in parts})!=len(parts):raise ValueError('Inventory must have unique references')
 # Freeze data before network work; a later source change is explicitly stale.
 return json.loads(json.dumps(parts)),sources

def fetch(code):
 url=API+code
 for attempt in range(2):
  try:
   with urllib.request.urlopen(url,timeout=25) as stream:data=json.load(stream)
   if data.get('code')!=200 or not isinstance(data.get('data'),dict):raise ValueError('Unexpected API response')
   if data['data'].get('componentCode')!=code:raise ValueError('API supplier code mismatch')
   return code,dict(retrieved_at_utc=now(),source_url=url,response=data)
  except Exception as exc:
   if attempt:return code,dict(retrieved_at_utc=now(),source_url=url,error=str(exc))
   time.sleep(.3)

def select_tier(tiers,quantity):
 candidates=[t for t in tiers if int(t['startNumber'])<=quantity and
             (t.get('endNumber') in (None,-1) or quantity<=int(t['endNumber']))]
 return max(candidates,key=lambda t:int(t['startNumber'])) if candidates else None

def manual_comparator_observation(parts,boards):
 evidence=ROOT/'outputs/v08-order-preparation/vbus-detector-review.json'
 selected=[q for q in parts if q.get('dnp') and 'TLV3011BIDBVR' in q.get('mpn','')]
 if not selected or not evidence.exists():return []
 data=json.loads(evidence.read_text());v=data['selected']
 return [dict(refs=[q['ref'] for q in selected],model=v['model'],mandatory_manual_fit=True,
  quantity_all_boards=len(selected)*boards,observed_unit_price_usd=v['external_observed_unit_price_usd'],
  observed_cost_per_board_usd=len(selected)*v['external_observed_unit_price_usd'],
  supplier=v['external_supplier'],supplier_part=v['external_supplier_part'],source_url=v['external_source'],
  observation_recorded_utc=data['recorded_utc'],observed_stock=v['external_observed_stock'],
  evidence_sha256=digest(evidence),excluded_from_factory_catalog_total=True,
  limits='Observed comparator only; shipping/tax and all other manual/external hardware remain unquoted. Stock not reserved.')]

def build_screen(parts,sources,raw,boards,raw_path,started):
 fitted=[q for q in parts if not q.get('dnp',False) and q.get('lcsc')]
 counts=collections.Counter(q['lcsc'] for q in fitted);rows=[];unit={}
 for code,count in sorted(counts.items()):
  item=raw.get(code,{});data=item.get('response',{}).get('data',{});quantity=count*boards
  tier=select_tier(data.get('prices') or [],quantity)
  price=Decimal(str(tier['productPrice'])) if tier else None
  if price is not None:unit[code]=price
  stock=data.get('stockCount')
  rows.append(dict(code=code,model=data.get('componentModelEn'),quantity_per_board=count,
   purchase_quantity_all_boards=quantity,unit_catalog_price_usd=float(price) if price is not None else None,
   stock=stock,observed_least_patch_number=data.get('leastPatchNumber'),observed_loss_number=data.get('lossNumber'),observed_min_purchase_number=data.get('minPurchaseNum'),stock_below_board_quantity=(stock<quantity if isinstance(stock,(int,float)) else None),
   tier=tier,refs=[q['ref'] for q in fitted if q['lcsc']==code],
   retrieved_at_utc=item.get('retrieved_at_utc'),source_url=item.get('source_url',API+code),
   error=item.get('error') or ('No matching price tier' if tier is None else None)))
 groups={};blocks={}
 for part in fitted:
  for target,name in ((groups,functional_section(part)),(blocks,part.get('block','Unspecified'))):
   g=target.setdefault(name,dict(parts_per_board=0,priced_parts_per_board=0,refs=[],unpriced_refs=[],_cost=Decimal(0)))
   g['parts_per_board']+=1;g['refs'].append(part['ref'])
   if part['lcsc'] in unit:g['_cost']+=unit[part['lcsc']];g['priced_parts_per_board']+=1
   else:g['unpriced_refs'].append(part['ref'])
 for collection in (groups,blocks):
  for g in collection.values():
   value=g.pop('_cost');g['catalog_component_cost_per_board_usd']=float(value)
   g['catalog_component_cost_all_boards_usd']=float(value*boards)
 total=sum((unit[q['lcsc']] for q in fitted if q['lcsc'] in unit),Decimal(0))
 stale=[q for q,h in sources.items() if not Path(q).exists() or digest(q)!=h]
 encoded=json.dumps(parts,sort_keys=True,separators=(',',':')).encode()
 return dict(status='STALE_INVENTORY' if stale else 'COMPLETE_CATALOG_SCREEN' if len(unit)==len(counts) else 'PARTIAL_CATALOG_SCREEN',
  started_at_utc=started,completed_at_utc=now(),assembled_board_quantity=boards,catalog_script_sha256=digest(__file__),
  inventory_total_refs=len(parts),priced_eligible_refs=len(fitted),supplier_sku_count=len(counts),
  inventory=parts,inventory_sha256=hashlib.sha256(encoded).hexdigest(),inventory_source_sha256=sources,
  sources_changed_during_run=stale,sku_prices=rows,functional_groups=groups,source_blocks=blocks,
  procurement_stock_status=('SHORTFALL' if any(q['stock_below_board_quantity'] for q in rows) else
                            'UNVERIFIED' if any(q['stock_below_board_quantity'] is None for q in rows) else 'SUFFICIENT_AT_OBSERVATION'),
  stock_shortfalls=[dict(code=q['code'],model=q['model'],refs=q['refs'],observed_stock=q['stock'],required_quantity=q['purchase_quantity_all_boards'])
                    for q in rows if q['stock_below_board_quantity']],
  raw_responses_file=str(raw_path),raw_responses_sha256=digest(raw_path),
  catalog_component_total_per_board_usd=float(total),catalog_component_total_all_boards_usd=float(total*boards),
  excluded_dnp_refs=[q['ref'] for q in parts if q.get('dnp',False)],
  separately_observed_manual_components=manual_comparator_observation(parts,boards),
  fitted_refs_without_supplier_code=[q['ref'] for q in parts if not q.get('dnp',False) and not q.get('lcsc')],
  limitations=['Catalog components only: excludes PCB, setup, assembly, attrition, hand-fit and external components, programming, shipping and tax.',
   'DNP metadata also marks mandatory manual fuses, wiring, bulk and supports; exclusion from this total does not authorize omitting them.',
   'Shared SKU tiers use the entire eligible inventory for the requested board count before functional allocation; section cost is not guaranteed deletion savings.',
   'Supplier stock and prices are timestamped observations, not reserved inventory or a matched manufacturing quote.',
   'Actual supplied manufacturer models, footprints and assembly substitutions still require matching review.'])

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 src=ap.add_mutually_exclusive_group();src.add_argument('--module',default='rev08');src.add_argument('--inventory',type=Path)
 ap.add_argument('--boards',type=int,default=2);ap.add_argument('--output-dir',type=Path,default=ROOT/'outputs/v08-order-preparation')
 ap.add_argument('--workers',type=int,default=4);ap.add_argument('--responses-file',type=Path,help='Explicitly reuse timestamped responses; default fetches fresh')
 args=ap.parse_args()
 if args.boards<1 or not 1<=args.workers<=8:ap.error('boards must be positive; workers must be1..8')
 started=now();parts,sources=load_inventory(args);codes=sorted({q['lcsc'] for q in parts if not q.get('dnp',False) and q.get('lcsc')})
 args.output_dir.mkdir(parents=True,exist_ok=True);raw={}
 if args.responses_file:raw=json.loads(args.responses_file.read_text())
 else:
  with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
   for future in concurrent.futures.as_completed([pool.submit(fetch,c) for c in codes]):
    code,item=future.result();raw[code]=item
    if len(raw)%20==0 or len(raw)==len(codes):print('Catalog rows',len(raw),'of',len(codes),flush=True)
 raw_path=args.output_dir/'section-cost-catalog-responses.json';raw_path.write_text(json.dumps(raw,indent=2)+'\n')
 screen=build_screen(parts,sources,raw,args.boards,raw_path,started)
 target=args.output_dir/'section-cost-screen.json';target.write_text(json.dumps(screen,indent=2)+'\n')
 print(json.dumps({k:screen[k] for k in ('status','inventory_total_refs','priced_eligible_refs','supplier_sku_count','catalog_component_total_per_board_usd','catalog_component_total_all_boards_usd','procurement_stock_status','stock_shortfalls','sources_changed_during_run')},indent=2))
 print('Screen:',target,flush=True)
 return 0 if screen['status']=='COMPLETE_CATALOG_SCREEN' else 2

if __name__=='__main__':raise SystemExit(main())
