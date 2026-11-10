"""Create the factory's human-readable USB requirements from the exact PCB."""
from pathlib import Path
import hashlib,textwrap
from PIL import Image,ImageDraw,ImageFont

def create(board,output):
 board=Path(board);output=Path(output)
 fonts='/usr/share/fonts/truetype/dejavu/'
 regular=ImageFont.truetype(fonts+'DejaVuSans.ttf',28)
 bold=ImageFont.truetype(fonts+'DejaVuSans-Bold.ttf',30)
 title=ImageFont.truetype(fonts+'DejaVuSans-Bold.ttf',40)
 sections=[
  ('Robot PDB v0.7 - USB impedance / factory review',title),
  ('4 layers | 340 x 260 mm | nominal 0.8 mm | ENIG | 2 oz outer / 1 oz inner',bold),
  ('JLC040821-7628 REQUIRED. Copper: L1/L4 0.070 mm; L2/L3 0.030 mm. Outer dielectric 0.203 mm 7628 each; core 0.200 mm without copper.',regular),
  ('New uniform coupled routing',bold),
  ('Target 90 ohm DIFFERENTIAL, +/-10%. Nominal conductor width 0.204 mm, edge-to-edge pair gap 0.160 mm. Factory calculator: approximately 8.05 mil width / 6.2992 mil gap.',regular),
  ('Top F.Cu / L1 signals reference continuous In1.Cu / L2 GND. Bottom B.Cu / L4 signals reference local continuous In2.Cu / L3 GND. Both surfaces are used.',regular),
  ('Applies to new USB3_UP / CAM / MIC SuperSpeed lanes, HUB_CHILD_DP/DM High-Speed intercell routing and the new P3/P4 paired intercell sections.',regular),
  ('Localized transitions and retained tails',bold),
  ('Connector lands, QFN escapes, DRT ESD pass-through stations, AC capacitors, vias and short length tuning contain intentional local width/spacing changes. Preserve physical pin mapping, polarity and matching.',regular),
  ('Retained internal 12 Mb/s Full-Speed device tails are not uniformly 0.204/0.160 mm. Do not describe a uniform-line coupon as qualification of these complete device channels.',regular),
  ('Review exact same-layer copper and reference-plane geometry in the supplied files. Do not add nearby copper or alter fanouts/vias to impose a uniform rule through component lands.',regular),
  ('Process and production confirmation',bold),
  ('Smallest off-pad through vias: 0.150 mm drill / 0.250 mm copper land. Paid fine-through-via process; no deliberate signal via-in-pad. Confirm mask/plugging process and actual registration capability.',regular),
  ('Standard assembly BOTH sides; 100 micrometre stencil maximum for TI DRT packages. Tooling rails, holes and fiducials ADDED BY JLCPCB on both assembled faces. Side rails must leave USB connector access.',regular),
  ('Confirm exact 340 x 260 x 0.8 mm manufacture and thin-board handling, including rails. Generic 300 x 300 thin-board FAQ conflicts with current capability tables and accepted quote settings; obtain engineering disposition.',regular),
  ('Provide production files plus impedance coupon / TDR report for owner review. Any stackup, geometry or process substitution requires review before fabrication. A geometric routing check is not a USB eye/compliance test.',regular),
  ('Exact PCB SHA256: '+hashlib.sha256(board.read_bytes()).hexdigest(),regular),
 ]
 lines=[]
 for text,font in sections:
  lines.extend((line,font) for line in textwrap.wrap(text,width=104 if font is regular else 85))
  lines.append(('',regular))
 im=Image.new('RGB',(2200,70+len(lines)*43),'white');draw=ImageDraw.Draw(im)
 for index,(text,font) in enumerate(lines):draw.text((40,30+index*43),text,font=font,fill='#16242a')
 output.parent.mkdir(parents=True,exist_ok=True);im.save(output,quality=96)
 return output
