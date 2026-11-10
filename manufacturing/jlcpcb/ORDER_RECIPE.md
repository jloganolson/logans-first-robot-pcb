# JLCPCB order recipe for v0.11

This is how the quote of **$305.40 before shipping** was produced on
10 November 2026: five boards, two of them assembled. Prices and stock move;
treat the figures as a dated snapshot. The board has **open review questions**
(see the top-level README), so this records how to reproduce the quote, not a
recommendation to order. The v0.10 quote ($294.18, larger board, cheaper Thor
inductor) is recorded in `outputs/v10-order-preparation/`.

## Files

| File | Use |
|---|---|
| `Robot_PDB_v11_Gerbers.zip` | Upload on the quote page |
| `BOM_JLCPCB.csv` | Assembly step, "Add BOM File" |
| `CPL_JLCPCB.csv` | Assembly step, "Add CPL File" |
| `hand-fit-and-harness.csv` | Parts the factory does not fit |
| `quote-2026-11-10.png` | The charge breakdown as quoted |
| `placement-preview.png` | The factory's placement preview of the re-laid-out corner |

The same files, with checksums, are in
`outputs/v11-order-preparation/package-1c351a03d3f0/`.

Known inconsistency: the KiCad board file and the Gerber job file inside the
zip still say ENIG finish and impedance controlled, left over from v0.9.
The order form governs, and this quote is lead-free HASL with no impedance
control.

## Board options

After upload the site should detect a 4-layer board of 155 × 228 mm.

| Option | Setting |
|---|---|
| Layers / quantity | 4 / 5 |
| Thickness | 1.6 mm |
| Material | FR4 TG135 |
| Surface finish | LeadFree HASL |
| Outer / inner copper | 1 oz / 0.5 oz |
| Specify stackup | Yes: **JLC04161H-7628** |
| Impedance control | No requirement |
| Via covering | Plugged |
| Min via hole size | 0.3mm/(0.4/0.45mm), selected automatically |
| Confirm production file | Yes, and tick "Do not confirm automatically" |

## Assembly options

| Option | Setting |
|---|---|
| PCBA type | Economic |
| Side | Top |
| PCBA quantity | 2 |
| Tooling holes | Added by JLCPCB |
| Confirm parts placement | Yes, and tick "Do not confirm automatically" |
| Parts selection | By customer |

On the bill-of-materials page all 81 lines should match. **Eight through-hole
connectors are left unticked by default and must be ticked by hand:** J13,
J14, J101, J501, J301, J302, J401, J402.

Remarks used:

- Assembly: "Engineering prototype v0.11. U9903 is intentionally OMITTED;
  owner fits exact TLV3011BIDBVR. All 304 fitted parts are TOP. Verify IC
  pin1, diode/electrolytic polarity and connector orientations against pads;
  send corrected placement for owner approval. Do not auto-confirm. Firmware
  not included."
- PCB (the form cuts this field at 200 characters): "Engineering prototype
  v0.11. Stackup JLC04161H-7628, 1oz outer / 0.5oz inner. All vias 0.3mm hole
  or larger. USB pair 0.275mm width / 0.19mm gap. Production-file changes
  need owner approval; do not auto-confirm."

## Quote breakdown

| Item | USD |
|---|---:|
| Engineering fee | 25.00 |
| Board | 21.80 |
| Surface finish | 5.90 |
| Confirm production file | 1.05 |
| **Bare boards** | **53.75** |
| Components (76 part numbers) | 130.52 |
| Extended components fee | 101.97 |
| Setup | 8.24 |
| Hand-soldering labor | 3.61 |
| SMT assembly | 3.44 |
| Stencil | 1.55 |
| Manual assembly | 1.01 |
| Nitrogen reflow | 0.86 |
| Confirm parts placement | 0.45 |
| **Assembly** | **251.65** |
| **Total before shipping** | **305.40** |

## Things that cost time to find

- **Economic assembly only accepts the default stack-up.** Choosing the
  thinner-prepreg JLC04161H-3313 costs nothing on the bare board, but the
  stack-up dialog then says it does not support Economic assembly. Design
  controlled-impedance traces for 7628 if you want the cheaper line.
- **Feeder fees differ by service.** Standard assembly charges about $1.53
  per part number, Basic and Extended alike. Economic charges about $3.07
  ($3.09 on this quote), for Extended parts only. On this BOM the feeder bill barely changed; the
  savings came from setup, stencil and fixture fees.
- **Small vias are expensive.** Vias with 0.20 mm holes and 0.40 mm lands put
  the board in a tier that added about $46 (via fee, a required material
  upgrade and a required test). 0.30 mm holes avoid it.
- **Heavy copper and options add up.** At this size: 2 oz outer copper
  +$45, 1 oz inner copper +$18, tested impedance control +$33, ENIG +$16.
- **Check rotations in the placement viewer.** Clicking a part in the list
  zooms to it. Three parts were wrong on the first upload: both XT30
  connectors (180°) and the UQFN-10 USB switch (90°, pin 1 at the wrong
  corner). Rotations for the rest are starting values that have not been
  checked one by one.
- **A missing 3D model is not a missing part.** One electrolytic capacitor
  shows as an empty outline in the preview but is on the BOM.
- **Board area is cheap; parts are not.** Cutting the board from 195 to
  155 mm tall saved $5.90. One inductor choice (60 V Coilcraft instead of a
  30 V alternative) cost $17.12.
- **Low stock.** On the day, STM32F072CBT6 showed 30 in stock and
  SN74AHCT125QPWRQ1 showed 52.

## Not fitted by the factory

See `hand-fit-and-harness.csv`. The main items: the TLV3011BIDBVR comparator
(U9903, out of stock at the factory), three fuses, battery and motor pigtails,
switch wiring, servo headers and the programming header.
