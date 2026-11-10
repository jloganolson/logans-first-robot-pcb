from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import zipfile
root=Path(__file__).resolve().parents[2];o=root/'outputs/v06-order-preparation'
im=Image.new('RGB',(1900,1230),'white');d=ImageDraw.Draw(im)
font='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';reg=ImageFont.truetype(font,28);small=ImageFont.truetype(font,24);title=ImageFont.truetype(font,40)
lines=[
'Robot PDB v0.6 — USB upstream impedance requirements',
'4 layers | nominal 1.6mm | ENIG | JLC041621-2116 REQUIRED',
'Outer Cu 0.070mm; inner Cu 0.030mm; L1-L2 dielectric 0.109mm (2116).',
'Core 1.230mm; bottom prepreg 0.109mm. Actual construction about 1.648mm.',
'',
'Signals: USB_DP and USB_DM on L1 (top). Reference: continuous L2 GND.',
'Coordinates below are millimetres from the top-left board-outline corner.',
'Trace width: 0.200mm. Top copper-pour keepout surrounds the upstream traces.',
'',
'A. Long separated sections, including U11 ESD pass-through:',
'   approximately x=212.9 to 218.6; DP y=81.05, DM y=82.95.',
'   Edge-to-edge separation approximately 1.70mm; effectively uncoupled.',
'   Target 45 ohm SINGLE-ENDED each (approximately 90 ohm differential).',
'   JLC calculator result: 45 ohm non-coplanar L1/L2 => width 7.69mil / 0.1953mm.',
'   Production width 0.200mm is within the requested 45 ohm +/-5 ohm tolerance.',
'',
'B. Short hub-side paired fanout near x=208.94 to 211.7:',
'   DP y=82.25, DM y=82.75; nominal width 0.200mm, edge gap 0.300mm.',
'   Target 90 ohm DIFFERENTIAL +/-10%, reference L2 GND.',
'',
'C. USB-C and IC/ESD fanouts contain short pads/stubs and changing spacing.',
'   Preserve pin mapping, matched path lengths and DRC clearance around these pads.',
'   Do not apply a uniform pair-spacing change through the connector or ESD device.',
'',
'Please confirm this construction and achievable impedance before manufacture.',
'Provide production files and impedance coupon/report for owner confirmation.',
'Any proposed geometry/stackup substitution requires review before fabrication.',
]
y=35
for i,s in enumerate(lines):
 d.text((35,y),s,font=title if i==0 else (reg if i in (1,5,9,16,20,24) else small),fill='#172a32');y+=55 if i==0 else 40
im.save(o/'USB_IMPEDANCE_REQUIREMENTS.jpg',quality=96)
with zipfile.ZipFile(o/'Robot_PDB_v06_Gerbers.zip','a',zipfile.ZIP_DEFLATED) as z:z.write(o/'USB_IMPEDANCE_REQUIREMENTS.jpg','USB_IMPEDANCE_REQUIREMENTS.jpg')
print(o/'USB_IMPEDANCE_REQUIREMENTS.jpg')

# The requirements image is part of the final upload archive identity.
import hashlib,json
manifest=o/'validation.json'
if manifest.exists():
 report=json.loads(manifest.read_text());report['sha256'][str((o/'Robot_PDB_v06_Gerbers.zip').relative_to(root))]=hashlib.sha256((o/'Robot_PDB_v06_Gerbers.zip').read_bytes()).hexdigest();report['impedance_requirements_in_zip']=True;manifest.write_text(json.dumps(report,indent=2)+'\n')
