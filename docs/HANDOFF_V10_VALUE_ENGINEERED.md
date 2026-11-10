# v0.10 value-engineered candidate: handoff for independent vetting

> **Superseded by v0.11** (compact 228 x 155 mm layout, plugs on the board edges, corrected part rotations, $307.92). See [HANDOFF_V11_COMPACT_LAYOUT.md](HANDOFF_V11_COMPACT_LAYOUT.md). **Do not order from the v0.10 files: their placement file has wrong part rotations.** This document remains the reference for everything v0.11 did not change.

> **About this document.** It is a working brief written by one AI agent (Claude) for the next reviewing
> agent and for the owner, published as-is for transparency. "I" is that agent; "the owner" is Logan.
> References to cart entries describe the owner's unpaid JLCPCB cart on 10 November 2026. The board is
> on hold and has not been ordered. For the public summary, start at the repository README.

**State on 10 November 2026:** an unpaid JLCPCB cart entry
`Robot_PDB_v10_Gerbers_Y5` holds five boards with two assembled for
**$294.18 before shipping** ($59.65 boards + $234.53 Economic assembly). The
owner's target is $300. Nothing is paid or approved.

Also in the cart:

- `Robot_PDB_v10_Gerbers_Y4` ($294.27) and `Robot_PDB_v10_Gerbers_Y3`
  ($289.41): **superseded v0.10 builds**. Do not order them. They are still
  there only because removing a cart entry needs the owner's say-so.
- `Robot_PDB_v09_Gerbers_Y2` ($535.15): the reviewed v0.9 fallback, untouched.

## HOLD: open issues found after the cart entry was saved

A third independent review (10 November 2026, saved as
`red-team-findings/2026-11-10/reviewer-3-feedback.md`) confirmed that the
board, Gerbers, BOM and placement file match the quoted package, and then
recommended **holding payment**. Its points, with what has been checked since:

1. **Inductor voltage ratings (blocker until resolved).** The reviewer reports
   that Sunlord rates the six regulator inductors (L2-L6, L7002,
   MWSA1004S series) at 30 V. The packs reach 33.6 V, and at start-up or into
   a short the full input voltage appears across a buck inductor. Checking
   the same point on the new Thor inductor: the Cjiang FEXL datasheet states
   "absolute maximum voltage: DC 30V" (note 8), so **L1 has the same problem,
   and it is one this revision introduced**: the v0.9 Coilcraft part was
   chosen as a 60 V part. The Sunlord figure is reviewer-reported; the Sunlord
   PDF could not be opened here to confirm it. The Sunlord parts are
   unchanged from v0.9, so v0.9 shares that half of the issue.
   Options: revert L1 to Coilcraft XAL1510-103 (about +$17, roughly $311);
   replace the six with a higher-voltage family (the reviewer estimates a
   75 V Vishay option at about $307 before the L1 revert); or obtain
   manufacturer confirmation that the start-up waveform is acceptable.
   Nothing has been changed yet.
2. **Electrolytic capacitors in Economic reflow.** The reviewer reports a
   250 C case-temperature limit for the nine Lelon 10 x 10 mm capacitors
   against JLCPCB's fixed 255 +/-5 C Economic profile. Not independently
   checked. Ask JLCPCB, or use Standard assembly (240 +/-5 C, roughly +$35).
3. **Thor inductor overload margin.** The reviewer independently gets about
   26 A peak in overload against a 29 A typical saturation figure at 25 C
   (about 30% inductance loss). Agrees with the estimate below. Dummy-load
   test before connecting the Thor.

Your job is to try to break `Y5` before the owner pays. One agent derived,
audited and quoted it; two Gemini Argon reviews have been worked through (below). The final build
differs from the one Argon last saw only by R13 and one placement rotation.
Payment and production approval belong to the owner.

- This repository is a cleaned public copy of the working tree at the point of the final quote.
- Board: `revisions/v0.10/kicad/robot_pdb.kicad_pcb`, SHA-256 `1b3bcccac46a0f5773c472aa492ede3c1351764b9f63c53f64ded7864630e90c`
- Change record: `revisions/v0.10/derivation.json`
- Package uploaded to the factory: `outputs/v10-order-preparation/package-1b3bcccac46a/`
- Quote record and screenshots: `outputs/v10-order-preparation/factory-quote.json`, `outputs/v10-order-preparation/factory-quote-charge-details.png`, `outputs/v10-order-preparation/factory-placement-preview.png`
- Argon's two reviews and the prompts used: `red-team-findings/2026-11-10/argon/`
- Board heating model and results: `red-team-findings/2026-11-10/thermal/`
- Plain-language walkthrough for the owner: `docs/PROTOTYPE_v0.10_WALKTHROUGH.html`
- Earlier analysis that led here: `red-team-findings/2026-11-10/FINDINGS.md`

## What v0.10 is

v0.10 is **not a new layout**. `source/generator/build_v10.py` loads the
reviewed v0.9 board (hash-checked) and applies a fixed list of changes. Every
copper item keeps its position relative to every other item, and **every
footprint is unchanged**.

| # | Change | Why |
|---|---|---|
| 1 | Whole board moved 17 mm up; outline cut from 228 × 230 to **228 × 195 mm**. Two bottom mounting holes (H7003, H7004) moved to y = 191.5. Two ground stitching vias that fell outside the outline removed. | Board area drives bare-board price. The top 18 mm of v0.9 was empty. |
| 2 | Copper **2 oz / 1 oz → 1 oz / 0.5 oz**; stackup JLC041621-2116 → **JLC04161H-7628** (factory default). | 2 oz outer copper alone costs $45. The thinner-prepreg 3313 stack is free on the bare board, but the order flow states it does not support Economic assembly. |
| 3 | The 70 vias at 0.20 mm drill / 0.40 mm land become **0.30 mm drill / 0.50 mm land**. | 0.30 mm is the factory's standard no-surcharge hole. Keeping 0.20 mm holes costs $45.95 unless a tooltip exception applies; this removes the question. |
| 4 | Upstream High-Speed USB pair (`USB_DP/DM`, `HUB_UP_DP/DM`) widened in place from 0.165 mm to **0.275 mm**; pitch unchanged, so the gap goes 0.300 → 0.19 mm. | Keeps the pair at about 90 Ω over the thicker 0.21 mm prepreg. JLCPCB's own calculator gives 90 Ω at 0.269 mm / 0.175 mm on this stack. |
| 5 | Default net-class clearance 0.20 → **0.15 mm**. | 0.20 mm was the 2 oz rule; JLCPCB's 1 oz minimum is 0.09 mm. Nine enlarged via lands sit 0.16 mm from a track. |
| 6 | **L1** Coilcraft XAL1510-103 ($12.12) → **cjiang FEXL1510A-100M** (C5378597, $3.56, 655 in stock). Original footprint. | A Coilcraft-equivalent: JLCPCB lists 24 A rated / 29 A saturation / 8.6 mΩ against Coilcraft's 22 A / 26.3 A / 9 mΩ. |
| 7 | **U2** LM5146QRGYRQ1 ($8.67) → **LM5146RGYR** (C3188679, $3.93). Same footprint. | Non-automotive grade of the same controller. |
| 8 | **FB2** UPZ1608E601 (Extended) → **GZ1608D601TF** (C1002, Basic). Same footprint. | Removes one $3.09 feeder charge. |
| 9 | Placement file: **J101 and J501 rotated 180°, U9902 rotated 270°**. | The factory preview showed both XT30 connectors reversed and the USB switch 90° off its pads. Fixed and re-checked in the preview (`factory-preview-U9902-corrected.png`). |
| 9a | **R13** 180 Ω → **220 Ω** (C22962, Basic). | Thor current-limit resistor. At 180 Ω the worst tolerance corner could start limiting below 8 A at low battery; at 220 Ω every corner stays above 8 A. |
| 10 | Assembly **Standard → Economic**; finish **ENIG → lead-free HASL**; no purchased impedance control. | Economic charges feeders only for Extended parts and has far lower setup fees. |

Owner decisions recorded: two driven wheels at 5 A each; Thor draws 8 A at
most; bench-test for heat rather than pay for thicker copper; the Pi will be
powered from a 12 V-to-USB-C module on the AUX output, so J101 becomes a
spare 5 V / 5 A output; no connector changes.

Not changed: schematic connectivity, every other part, all connector
positions relative to each other, firmware, the manual-fit list.

## What was checked, and how to re-run it

```sh
export PDB_KICAD_STATE=/tmp/pdb-kicad-red-team
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/generator/build_v10.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/audit_v10.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/audit_factory_drills.py --output outputs/v10-order-preparation/factory-drills.json revisions/v0.10/kicad/robot_pdb.kicad_pcb
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/export_v10.py
```

Re-running `build_v10.py` rewrites the board. Zone refill is not guaranteed
byte-identical, so the hash may change; if it does, the uploaded package no
longer matches and must be re-exported and re-uploaded. `export_v10.py`
re-plots the Gerbers, which carry timestamps.

Results on the saved board:

- **KiCad DRC:** 0 errors, 0 unconnected pads. 13 warnings, the identical
  set v0.9 carries.
- **Delta audit (`audit-v10.json`, PASS):** all 366 footprints at their v0.9
  position plus the translation, same footprint IDs; 1,195 pads identical in
  geometry and net; 3,488 track segments identical once the recorded USB
  widening is normalised; via set identical except the 70 resized and 2
  removed; all 80 zone definitions identical; filled copper area of every
  uncropped zone within −3% / +6% of v0.9; all copper inside the outline;
  at least 1.4 mm of board between any large hole and the edge.
- **Schematic to board:** 366 components; values, footprints and every pin's
  net agree.
- **Factory drill screen:** PASS, 1,150 holes, smallest 0.30 mm.
- **Factory:** the upload was read as a 4-layer 195 × 228 mm board and the
  standard via tier was selected automatically. All 81 BOM rows matched 76
  supplier codes. Economic assembly was offered and priced.

## Argon review of the first build, and what was done

Argon's verdict was "do not order". Each finding was checked against the
files and datasheets rather than accepted as written.

| Argon finding | Checked result | Action |
|---|---|---|
| Thor current limit trips below 8 A with R13 = 180 Ω | **Wrong.** It used the 100 µA shunt-mode sense current. The LM5146 datasheet gives 180 / 200 / 220 µA in RDS(on) mode, with a temperature coefficient that tracks the FET. Typical valley limit is about 12 A. | None needed. See item 1 below for the remaining margin note. |
| Bourns SRP1265A (15.5 A saturation) has no margin | **Right.** In an overload the limit allows about 15–16 A peak typically and up to about 22 A with worst-case tolerances and comparator offset, before hiccup. (FET on-resistance at 7.5 V gate drive is estimated at 2.6–4.0 mΩ.) | L1 changed to FEXL1510A-100M (29 A). |
| Hybrid L1 footprint is an assembly risk | Moot. | Footprint reverted to the original; the custom footprint is deleted. |
| J101 / J501 shown 180° reversed in the factory preview | **Right.** | Rotations corrected; preview re-checked. |
| C20 missing from the preview, J3 rotated, U9902 lacks an offset | Checked at full zoom in the factory viewer. U9902 was 90° off with pin 1 at the wrong corner: **right**. J3's model sits on its pins and peg holes: wrong. C20 is in the BOM and placement file; the preview has no 3D model for it. | U9902 corrected (+270°) and re-checked. |
| 0.20 mm via holes are not in the free tier | Disputed: the factory tooltip says they are free at ≥ 0.45 mm land on multilayer boards, and the tier was auto-selected, not chosen by hand. | Made moot: all vias are now 0.30 mm. |
| Only 0.40 mm of board left at mounting holes H1 / H2 | **Wrong.** The coordinates cited do not exist on this board. The smallest wall is 1.4 mm (H7001, unchanged from v0.9, and H7003). | Audit now checks this. |
| Silkscreen labels collide at top left | Unchanged from v0.9; three labels are within 0.6 mm of the new top edge and may be clipped. | Cosmetic, left as is. |
| Thinner copper runs the Thor corner at 85–105 °C | Not verifiable. Its supporting numbers (36 deleted vias, spoke-only reliefs, 600 kHz regulators) do not match the board. | Still an open bench item, as before. |
| HASL plus Economic assembly risks fine-pitch joints | Fair, and already listed. It quoted via covering as tented; the order is plugged. | Open; see item 4. |
| Audit skipped L1 pads, filled zones, hole walls, placement file | Fair. | L1 skip removed; filled-area and hole-wall checks added. The placement file is still not audited by script. |
| U2 schematic manufacturer field still said LM5146-Q1 | **Right.** | Fixed. |
| USB pair about 85–90 Ω; narrow remnants harmless | Agrees with the factory calculator. | Width retuned to 0.275 mm; only 1.0 mm of one leg remains narrow. |
| FB2 substitution is safe | Agreed. | None. |

## Argon follow-up review of the second build

Verdict: "order with named changes". It agreed it had been wrong on the
sense current and on the mounting holes, agreed with the inductor, via and
USB changes, and named two placement rotations (U9902 right, J3 wrong; see
the table) plus a low-battery current-limit margin note that led to R13 =
220 Ω. It also caught a stale sentence in the exported requirements file
(fixed). Some of its other content does not correspond to this board (for
example parts called Q22, R34, U5 as a TPS54302, and a $51.40 fee) and was
ignored.

## Where to push hardest now

1. **Thor current limit after the R13 change.** Limit valley =
   (I_RDSON × R13 ± comparator offset) / FET on-resistance. Argon and I read
   the offset's sign differently; 220 Ω keeps the lowest corner at about
   8.5 A of load under the less favourable reading. The highest corner puts
   about 26 A peak through L1 against its 29 A saturation rating. FET
   on-resistance at 7.5 V gate drive (2.6–4.0 mΩ) is interpolated, not from
   a datasheet line. Worth one independent recalculation.
2. **FEXL1510A-100M.** The manufacturer datasheet confirms the body
   (16.5 × 15.5 × 9.7 mm) and terminals (13.2 mm wide, 3.2 mm long, 7.0 mm
   gap), which fit the XAL1510 lands (3.18 × 13.2 mm, 7.42 mm gap). The
   body is about 0.1 mm larger than the Coilcraft's in each direction. The
   brand is less proven than Coilcraft; current ratings are from the
   supplier listing and datasheet table, not measured.
3. **USB High-Speed pair.** Geometry now follows the factory calculator, but
   no impedance test is purchased and the v0.9 reference-plane analyser was
   not re-run. Centre lines are unchanged; wider tracks and larger via lands
   change antipads slightly.
4. **Lead-free HASL on fine pitch.** The UQFN-10 USB switch (U9902) carries
   the only USB path. ENIG is +$15.60, which makes $309.78.
5. **Heat with thinner copper.** Now modelled (see the thermal folder) from
   the board's real copper, still air, about 12 W of total loss with Thor at
   8 A and typical rail loads. Board temperature rise above ambient:

   | Location | 2 oz / 1 oz | 1 oz / 0.5 oz (v0.10) | 1 oz / 1 oz |
   |---|---:|---:|---:|
   | AUX 11.7 V regulator at 4 A (hottest spot) | +33 °C | +45 °C | +40 °C |
   | Thor stage (FETs, inductor, controller) | +25 °C | +31–33 °C | +28–30 °C |
   | XL330 regulator at 2 A | +24 °C | +29 °C | +26 °C |
   | Amplifier | +25 °C | +30 °C | +27 °C |

   With a pessimistic air-side figure the v0.10 peak is +59 °C. These are
   board temperatures under the part, not junction temperatures, and the
   model is good to roughly ±30%. The loss figures are estimates in
   `thermal.py`. The AUX rail is hottest because it was loaded with the
   amplifier plus the Pi module plus chargers; it is the one to measure
   first on the bench.
6. **Placement rotations.** v0.9 starting values except J101 / J501 / U9902. Per-part
   pin-1 and polarity review is still owed. Both factory confirmations are
   set to not auto-confirm, and the remarks ask for corrected placement to
   be sent for approval.
7. **Mounting pattern.** The board is 35 mm shorter and two holes moved. The
   owner has not confirmed the robot accepts this.
8. **Edge clearance without rails.** J13 / J14 are 0.5 mm from the right
   edge and C93 / C94 2.2 mm.
9. **Stock.** STM32F072CBT6 showed 30 in stock and SN74AHCT125QPWRQ1 52
   earlier today.

## Remaining savings not taken

Each removes a $3.09 feeder charge plus the part difference, on the same
footprint.

- Y7002 8 MHz → the 12 MHz crystal already used as Y1 (needs a firmware
  clock change and 33 pF load capacitors).
- C20 220 µF 35 V → the 100 µF 63 V type already on the board.
- The four 6.8 µH inductors → the 10 µH type already on the board.
- Green LEDs: no Basic green 0603 exists today; red or white would be Basic.

## Unchanged from v0.9 and still required

Manual fitting of the exact TLV3011BIDBVR (U9903), the three fuses, power
pigtails and harness; programming the PWM microcontroller; the documented
Full-Speed audio and Dynamixel USB layout risks; and all bench qualification
in `docs/V09_BRINGUP_CHECKLIST.md`. This is not a ready-to-run assembly.
