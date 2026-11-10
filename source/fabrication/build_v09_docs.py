"""Render the current saved v0.9 review package; does not change design files."""
import hashlib, html, json, os
from pathlib import Path
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / 'docs'
O = ROOT / 'outputs/v09-order-preparation'
MD = MarkdownIt('commonmark', {'html': False}).enable('table')
def read(name):
    p = O / name
    return json.loads(p.read_text()) if p.exists() else {}
def esc(value): return html.escape(str(value))
def href(path): return esc(os.path.relpath(path, D))
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def hashes_match(record):
    if not record: return False
    for name, expected in record.items():
        path = Path(name)
        if not path.is_absolute(): path = ROOT / path
        if expected is None:
            if path.exists(): return False
        elif not path.is_file() or digest(path) != expected: return False
    return True
cost = read('section-cost-screen.json')
audit = read('validation.json')
usb = read('usb-channel-audit.json')
quote = read('factory-quote.json')
package = read('current-package.json')
board = ROOT / 'revisions/v0.9/kicad/robot_pdb.kicad_pcb'
current = bool(audit and usb and board.exists() and
               digest(board) == audit.get('board_sha256') == usb.get('board_sha256') and
               hashes_match(audit.get('audited_input_sha256')) and
               hashes_match(usb.get('source_sha256')))
body = '''<h1>Robot PDB v0.9 — purchase review</h1>
<div class="notice"><strong>Engineering prototype; purchase awaits your green light.</strong>
The new-wheel design is archived. This version keeps the existing controllers
and fused battery-voltage motor passthrough. No payment has been made.
<p><strong>Principal retained risk:</strong> inherited audio/Dynamixel USB routing
has reviewed reference/return departures. External adapters, rework or another
spin may be needed. All rails and PWM still need staged bench qualification.</p></div>
<nav><a href="#decision">Decision</a><a href="#quote">Factory quote</a>
<a href="#functions">Connections</a><a href="#cost">Section costs</a>
<a href="#layout">Final layout</a><a href="#checks">Checks</a>
<a href="#review-SERVICE_OFF_v09">OFF controls</a><a href="#details">Guides</a></nav>
<section id="decision"><h2>Ordering judgment</h2><p>I would order a small,
two assembled board engineering prototype after factory matching and placement
review, with time for manual fitting, one PWM MCU programming step and the
commissioning checklist. This is not a ready-to-run robot controller. If
dependable internal USB on the first spin is essential, resolve the inherited
layout before buying.</p><p>The board is 228 ×230mm, four layers,2oz outer/1oz
inner copper, selected nominal1.6mm JLC041621-2116 stackup. The factory lists
finished thickness1.648mm ±10%. Production files/impedance remain subject to
manufacturer engineering confirmation.</p><p>Replacement-wheel work is preserved on
<a href="#">codex/replacement-wheels-v08-archive</a>
at f135c36. Current review work is on codex/passthrough-v09.</p></section>'''
body += '<section id="quote"><h2>Factory quote and manual work</h2>'
if quote:
    body += MD.render(quote.get('summary_markdown', 'Factory quote record has no summary.'))
    body += '<p><a href="'+href(O/'factory-quote.json')+'">Saved quote evidence</a></p>'
else:
    body += '<p><strong>Factory quote not yet recorded. Do not use an older draft or catalog allocation as the total.</strong></p>'
body += '''<p>Factory-fitted parts do not include every physical item. The exact
TLV3011BIDBVR USB detector is mandatory manual fit ($2.78 separately observed);
fuses, harness/connector work, PWM programming, bench work and external cables
are additional. Follow the selected package’s hand-fit list. Optional OFF
headers/test points are distinguished from mandatory items.</p></section>'''
body += '<section id="functions">'+MD.render((D/'CURRENT_FUNCTIONALITY.md').read_text())+'</section>'
body += '<section id="cost"><h2>Section component allocations</h2>'
if cost:
    body += f'<p><strong>${cost["catalog_component_total_per_board_usd"]:.2f}/board</strong> at saved two-board tiers; component catalog allocation only. Factory setup/attrition, PCB, assembly, manual/external items, shipping and tax are separate.</p><table><tr><th>Section</th><th>Fitted parts</th><th>Catalog allocation/board</th></tr>'
    for label, row in cost['functional_groups'].items():
        body += f'<tr><td>{esc(label)}</td><td>{row["parts_per_board"]}</td><td>${row["catalog_component_cost_per_board_usd"]:.2f}</td></tr>'
    body += f'</table><p class="small">Observed {esc(cost["completed_at_utc"])}; stock is unreserved. Omitting a function changes shared tiers and requires a reviewed assembly variant. The listed allocation is not a guaranteed saving.</p>'
body += '</section><section id="layout"><h2>Final saved layout</h2>'
if package.get('directory'):
    folder = ROOT / package['directory']
    body += '<p>Views are exported from the same audited manufacturing snapshot as the BOM, placement and Gerbers. Click a view for full size.</p>'
    for name, title in [('assembly-top.svg','Top assembly and references'),('board-top.svg','Top copper and connector labels'),('board-bottom.svg','Bottom copper')]:
        target = folder / name
        if target.exists():
            body += f'<details><summary>{title}</summary><a href="{href(target)}"><img alt="{title}" src="{href(target)}"></a></details>'
    body += f'<p><a href="{href(folder/"READ_BEFORE_ORDERING.txt")}">Package instructions</a> · <a href="{href(folder/"source-manifest.json")}">Exact source and output hashes</a></p>'
else:
    body += '<p>Final gated export not yet recorded.</p>'
body += '</section><section id="checks"><h2>Automated checks and limits</h2>'
body += '<p><strong>'+('The independent reports match the current PCB.' if current else 'HOLD: reports are missing or do not match the current PCB.')+'</strong></p>'
body += '<table><tr><th>Check</th><th>Recorded result</th></tr>'
for label, value in [('Overall layout disposition',audit.get('status','PENDING')),('Schematic / inventory / PCB identity',audit.get('logical_status','PENDING')),('Component references',audit.get('physical_parts','PENDING')),('Native physical errors',audit.get('native_physical_errors','PENDING')),('Unconnected items',audit.get('native_unconnected_items','PENDING')),('Warnings (classified separately)',audit.get('native_warnings','PENDING')),('Factory drill screen',audit.get('factory_drills',{}).get('status','PENDING')),('Independent USB disposition',usb.get('status','PENDING')),('Unreviewed USB holds',len(usb.get('review_holds',[])) if usb else 'PENDING')]:
    body += f'<tr><td>{esc(label)}</td><td>{esc(value)}</td></tr>'
body += '</table><p>Reviewed legacy deviations remain in the report’s raw findings; their disposition is not a measured electrical pass. Native checks do not prove regulator stability, temperature, current capability, USB eye quality or servo behavior.</p><ul>'
for hold in audit.get('electrical_release_holds',[]): body += '<li>'+esc(hold)+'</li>'
body += '</ul><p>'
for name, title in [('validation.json','Integrated audit'),('usb-channel-audit.json','Actual saved-copper USB report'),('native-warning-review.json','Native warning classification'),('pwm-controller-test.txt','PWM controller test')]:
    body += '<a href="'+href(O/name)+'">'+title+'</a> · '
body += '</p></section><section id="details"><h2>Review and commissioning guides</h2>'
names = ['V09_REPORT','V09_SCOPE','V09_USB_PROTOTYPE_REVIEW','V09_BRINGUP_CHECKLIST','V09_PWM_GUIDE','SERVICE_OFF_v09','USB2_CONTROL_v09','USB2_POWER_BUDGET_v09','USB_VBUS_DETECTOR_REVIEW','THOR_POWER_CABLE','MASTER_DISCONNECT_SELECTION','DALY_USB_v09','V09_FACTORY_PREFLIGHT']
for name in names:
    path = D / (name+'.md')
    if not path.exists(): continue
    text = path.read_text()
    body += f'<details id="review-{name}"><summary>{esc(text.splitlines()[0].lstrip("# "))}</summary>'+MD.render(text)+'</details>'
body += '</section>'
for name in names: body = body.replace('href="'+name+'.md"', 'href="#review-'+name+'"')
body += '''<script>function reveal(){const d=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(d&&d.tagName==='DETAILS')d.open=true;}addEventListener('hashchange',reveal);document.addEventListener('click',e=>{const a=e.target.closest('a[href^="#review-"]');if(a){const d=document.getElementById(a.hash.slice(1));if(d)d.open=true;}});reveal();</script>'''
style = '''body{max-width:1160px;margin:24px auto;padding:0 20px 60px;font:16px/1.5 system-ui,sans-serif;color:#202b30}h1{font-size:29px}h2{font-size:23px;border-top:1px solid #bdc6ca;padding-top:18px;margin-top:30px}a{color:#135a7b}nav{display:flex;gap:14px;flex-wrap:wrap;padding:12px 0;border-bottom:1px solid #bdc6ca}table{width:100%;border-collapse:collapse;font-size:14px}td,th{text-align:left;vertical-align:top;padding:8px;border-bottom:1px solid #d1d7da}th{background:#eef2f4}.notice{border:2px solid #926326;padding:12px 16px;background:#fffaf0}summary{cursor:pointer;padding:10px;background:#eef2f4}details{margin:12px 0}img{max-width:100%;height:auto}.small{font-size:13px;color:#48575e}section,details{scroll-margin-top:18px}code{overflow-wrap:anywhere}li{margin:6px 0}@media print{nav{display:none}tr{break-inside:avoid}}'''
target = D / 'PROTOTYPE_v0.9_WALKTHROUGH.html'
target.write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Robot PDB v0.9 purchase review</title><style>'+style+'</style><main>'+body+'</main></html>')
print(target)
