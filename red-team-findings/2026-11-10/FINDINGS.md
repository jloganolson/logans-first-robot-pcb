# Independent review of the $300 prototype plan

> **Superseded in two places.** A candidate was built and quoted later the
> same day: see `docs/HANDOFF_V10_VALUE_ENGINEERED.md` ($294.18 final quote).
> (1) The JLC04161H-3313 stack is free on the bare board, but the factory
> order flow says it does not support Economic assembly; v0.10 uses the 7628
> stack and widens the USB pair. (2) Pouring the pack feeds on both outer
> layers is not free: the two feeds cross in plan view.

Reviewed 10 November 2026 against the locked v0.9 board
(`ad206a2e…53a18c3`, hash re-checked) and the saved factory evidence.
Nothing in the reviewed board, package or cart was changed. No cart entry was
made; all live prices came from JLCPCB's public pages and the signed-out
calculator.

## Verdict

**$300 is reachable, but not with the v0.9 parts list as it stands.** With the
unchanged BOM on Economic assembly and the $54.45 bare board, my estimate is
about **$327**, roughly $27 over. Two Thor-supply part swaps close that gap on
their own (about −$30), and a handful of low-risk feeder eliminations add
$10–20 of margin. None of this is a factory quote: it is the published fee
schedule applied to the saved BOM. The matched quote from real files is still
the deciding number.

Three assumptions in the handoff need correcting before a candidate is routed:

1. The saved $111.60 feeder charge is **not** 36 Extended feeders. It is 72
   surface-mount feeders at $1.55, because Standard assembly charges Basic
   parts too. Economic charges only Extended parts, but at $3.07. For this
   BOM the feeder bill barely moves (about $108).
2. The $54.45 price evidence was taken with "Specify Stackup: No". That
   default stack would put the existing High-Speed USB pair roughly 30% above
   its v0.9 impedance. A thin-prepreg stack that keeps the existing geometry
   costs nothing extra, but it must be selected.
3. At 1 oz outer / 0.5 oz inner copper, board heating in the motor loop
   doubles. The two pack-positive feeds are single-layer pours and become the
   hot spots.

## 1. Budget and feeders

### What the fee schedule says (JLCPCB, page dated 22 Oct 2026)

| Fee | Economic | Standard |
|---|---:|---:|
| Setup | $8.18 | $25.56 |
| Stencil | $1.53 | $8.21 |
| Feeder loading | $3.07 per Extended part | $1.53 per part, Basic and Extended |
| SMT joints | $0.0016 | $0.0016 |
| Hand-soldering labor | $3.58 per order | $3.58 per order |
| Manual joints | $0.0164 | $0.0164 |
| Fixture, packing, handling | none | charged |

The saved quote reconciles with this: 76 supplier codes − 4 through-hole
types = 72 feeders × $1.55 = $111.60 exactly.

### BOM classification (saved catalog data, re-checked live)

- 76 supplier codes: 37 Basic, 39 Extended. None is "Preferred" (fee-exempt).
- 4 of the Extended codes are through-hole connectors (hand-soldered, no
  feeder). That leaves **35 chargeable Extended feeders** under Economic.
- Every one of the 55 distinct fitted part pages I fetched lists
  "PCBA Type: Economic and Standard". No part forces Standard assembly.
- Economic accepts 4-layer, 1.6 mm, green, lead-free HASL or ENIG, 2–50 pcs.

### Estimate for the unchanged v0.9 BOM on Economic

| Item | USD |
|---|---:|
| Five bare boards, 228 × 160, 1 oz / 0.5 oz, lead-free HASL (live: $54.45) | 54.45 |
| Components, two boards (saved quote) | 144.66 |
| Extended feeders, 35 × ~$3.09 | ~108 |
| Setup + stencil | ~9.8 |
| SMT joints (~970 per board), hand-solder labor, manual joints, nitrogen, placement confirmation | ~10 |
| **Estimated merchandise** | **~$327** |

The per-feeder rate and the small fees are taken from the old-design Economic
quote screenshot ($80.34 for 26 feeders = $3.09 each; setup $8.24; stencil
$1.55), which matches the published schedule within cents.

### Savings I could support

| Change | Saves (2 boards) | Confidence / what must be checked |
|---|---:|---|
| U2 LM5146QRGYRQ1 → LM5146RGYR (C3188679, $3.93, 6,000 in stock). Same package, non-automotive grade. | $9.48 | High. Same footprint and pinout; confirm datasheet limits are identical for this use. |
| L1 XAL1510-103 ($12.12) → Sunlord MWSA1707S-100MT (C5240401, $1.70, 357 in stock; 10 µH, 9.9 mΩ, 10.5 A rated, 16.5 A saturation). | $20.85 | Medium. Same DCR, lower saturation (16.5 A vs 26.3 A). At 8 A output and ~3.4 A ripple the peak is ~9.7 A. Needs a new 17.2 mm footprint and a check of the current-limit peak against saturation when hot. Bourns SRP1265A-100M ($1.13, 1,943 in stock, 15.5 A saturation, 16.5 mΩ) is a smaller fallback with more loss. |
| Y7002 8 MHz (Extended) → second 12 MHz C9002 (Basic, already on the board as Y1), or run the STM32F072 crystal-less. | ~$3.9 | High for hardware. Needs a firmware clock change and 20 pF-load capacitors. |
| Nine green LEDs KT-0603G (Extended) → a Basic 0603 green. | $3.07 | High. Indicator only. |
| FB2 600 Ω bead (Extended) → a Basic 0603 bead. | $3.07 | Medium. Audio analog supply filter; check impedance and current. |
| C20 220 µF 35 V (single, on +24 V) → the 100 µF 63 V type already used four times. | ~$3.8 | Medium. Check Thor output ripple and loop stability. |
| L2/L3/L4/L7002 6.8 µH → the 10 µH type already used (same Sunlord family). | $3.07 | Medium-low. Four 5 V regulators change ripple, saturation margin and compensation. |
| Q2/Q3 BSC034N06NS → BSC040N10NS5 (already used as Q1). | ~$5.6 | Low until analysed. R13 (180 Ω, Extended) sets the Thor current limit from the low-side FET's on-resistance, so the limit shifts; R13 would move to ~200 Ω (Basic), saving another $3.07. |

First two rows: **−$30.33 → about $297.** Adding the three high/medium
feeder rows: **about $287.** I did not credit anything I could not tie to a
stocked part number.

Not creditable: TPS2552 and TPS2553 cannot share a feeder (opposite enable
polarity). The 100 nF 100 V and 2.2 µF 100 V capacitors sit on battery-voltage
nets behind a TVS that clamps near 58 V, so 50 V Basic parts are not a safe
swap.

### Things that push the other way

| Option | Adds | Live calculator, 228 × 160 |
|---|---:|---|
| ENIG instead of lead-free HASL | $14.90 | $69.35 |
| 1 oz inner copper | $18.05 | $72.50 |
| 2 oz outer copper | $45.20 | $99.65 |
| Impedance control (±10%, tested) | $33.08 | $87.53 |
| Specified stack JLC04161H-3313, no impedance test | $0.00 | $54.45 |

### Stock exposure

At the saved observation: STM32F072CBT6 had **30** in stock,
SN74AHCT125QPWRQ1 **52**, XAL1510-103 191. The first two can disappear
between quote and payment. A non-automotive SN74AHCT125PWR would remove one
of those risks.

### Shifted work, shown separately

Leaving the eight through-hole connectors off the factory order would save
about $8–9 (labor fee, joints, parts) and hand the owner eight connectors to
solder on each board. I did not count this toward the target.

## 2. Thinner copper and power return

Method: the filled copper of each power net was rasterised at 0.1 mm from the
saved board, layers joined at vias and through-hole pads, and the resistance
between the real terminals solved numerically. Copper at 20 °C; hot copper is
about 20% worse. Fuses, connectors, switch and wiring are excluded.

### Motor loop at 30 A, one pack carrying everything

| Segment | 2 oz / 1 oz (v0.9) | 1 oz / 0.5 oz | 1 oz / 1 oz |
|---|---:|---:|---:|
| Pack B positive, J4 → switch (top layer only) | 1.10 mΩ | 2.19 mΩ | 2.19 mΩ |
| Switch pole B → motor fuse | 0.47 mΩ | 0.94 mΩ | 0.94 mΩ |
| Fuse → J2 | 0.17 mΩ | 0.33 mΩ | 0.33 mΩ |
| Ground return, J2 → J4 | 0.85 mΩ | 1.69 mΩ | 1.06 mΩ |
| **Loop** | **2.58 mΩ** | **5.14 mΩ** | **4.51 mΩ** |
| Board heat at 30 A | 2.3 W | 4.6 W | 4.1 W |
| Drop at 30 A | 78 mV | 154 mV | 135 mV |

Pack A alone is lower: 1.82 mΩ today, 3.63 mΩ at 1 oz / 0.5 oz.

- **Voltage drop is not the issue.** 154 mV on a 27–33 V bus is negligible.
- **Heat is.** Pack B's positive feed is a single top-layer pour of about
  530 mm² and would dissipate ~2.0 W at 30 A in 1 oz copper (1.0 W today).
  Pack A's feed is bottom-layer only: 1.3 W. Peak density reaches 8.4 A per mm
  of width (about 240 A/mm² in 1 oz) at a neck near (58.4, 117.8).
- **The fix is free in a reroute.** Both ends of each pack feed are
  through-hole pads. Pouring PACK_A and PACK_B on both outer layers restores
  today's resistance in 1 oz copper. With that, the 1 oz / 0.5 oz loop is
  about 4.0 mΩ (3.6 W at 30 A), dominated by ground return.
- Ground return: at 0.5 oz the inner ground plane carries most of the return
  and loses the most (0.95 W of 1.5 W). Paying $18.05 for 1 oz inner copper
  buys back 0.6 mΩ. More outer-layer ground pour along the left edge between
  J2 and the pack connectors does the same for nothing.
- All high-current through-hole pads use solid zone connections, not thermal
  spokes. Good.

Heating scales with current squared: at 15 A continuous the whole 1 oz loop
is about 1.2 W.

**Owner input, 10 November 2026:** the robot moved fast enough with each wheel
limited to 5 A. A controller's motor-current limit caps battery current at or
below that figure per wheel, so J2 carries at most about 10 A with two wheels
or 20 A with four. In 1 oz / 0.5 oz copper, one pack carrying everything:

| J2 current | Motor loop heat | Pack B feed alone |
|---:|---:|---:|
| 10 A (two wheels) | 0.5 W | 0.2 W |
| 20 A (four wheels) | 2.1 W | 0.9 W |

The pack feeds also carry the electronics load (Thor about 7–8 A at the
battery, plus the smaller rails), so a pack feed can see roughly 10 A more
than J2. Even at 30 A total in one pack feed that is the 2.0 W case above,
and it is halved by pouring the feed on both layers. **1 oz / 0.5 oz copper is
acceptable for the motor path at these currents.** The owner confirmed two driven wheels, so the 10 A row applies. Whether
the 5 A setting is a motor or battery limit is still an assumption. The
open copper question is now regulator heat spreading, not the motor loop.

### Thor and electronics paths

| Path | Current | 2 oz / 1 oz | 1 oz / 0.5 oz |
|---|---:|---:|---:|
| Switch → electronics fuse | 15 A | 0.73 mΩ, 0.16 W | 1.45 mΩ, 0.33 W |
| Fuse → ideal-diode FET | 15 A | 0.21 mΩ | 0.41 mΩ |
| Input plane → Thor buck | 8 A | 0.95 mΩ | 1.77 mΩ, 0.11 W |
| Thor inductor → J3 | 8 A | 0.93 mΩ | 1.86 mΩ, 0.12 W |
| Thor ground return J3 → J1 | 8 A | 0.17 mΩ | 0.33 mΩ |

No concern here at either copper weight. What this does not cover: copper as
a heatsink. Halving outer copper also halves heat spreading under the six
TPS54560 regulators, the Thor FETs and the amplifier. That needs bench
measurement or a thermal estimate per regulator; I did not model it.

## 3. USB stack and routing

The upstream High-Speed pair is routed 0.165 mm wide with a 0.300 mm gap over
0.109 mm of prepreg in 2 oz copper. I solved the pair cross-section
numerically on each candidate stack. My solver reads the v0.9 geometry at
98 Ω where the design intent was 90 Ω, so treat absolute values as ~9% high
and use the comparison.

| Stack (1 oz outer) | Prepreg | Existing 0.165 / 0.300 pair | Relative to v0.9 | Width for the v0.9-equivalent impedance |
|---|---:|---:|---:|---|
| v0.9, JLC041621-2116, 2 oz | 0.109 mm | 98.5 Ω | — | — |
| Default JLC04161H-7628 | 0.210 mm | 129.5 Ω | **+31%** | far wider; ~0.27 mm at a 0.127 mm gap for 90 Ω on my solver |
| JLC04161H-3313 | 0.099 mm | 100.8 Ω | +2% | unchanged |

- Leaving the stack unspecified means the default 7628 build. The existing
  pair would land near 120 Ω against a 90 Ω ±15% requirement. The saved
  $54.45 evidence has "Specify Stackup: No".
- Selecting JLC04161H-3313 with impedance control set to "No requirement"
  stayed at **$54.45** in the live calculator. The existing pair geometry
  carries over within 2%.
- Buying tested impedance control adds $33.08. On this budget, specify the
  stack and skip the test coupon; accept that impedance is by design, not
  measured.
- The Full-Speed pairs (0.25 mm, some on the inner layer) are not
  impedance-critical; their documented reference-plane departures are
  unchanged by any of this.
- **Open item:** Economic assembly lists "standard stack-up only". I could
  not confirm from public pages whether a specified 3313 stack counts as
  standard. This only shows in the assembly quote flow with real files. If it
  does not, the choice is Standard assembly (roughly +$35–45 in fees) or
  re-routing the pair for 7628.
- The 70 vias at 0.20 mm drill still force the reroute the handoff describes.
  I did not re-test that count's 125-error result.

## 4. Assembly fit

- **Area is fine.** Footprints occupy about 13,000 mm² of a 36,480 mm²
  (228 × 160) outline, 36%. The top 18 mm is empty. Everything below y = 178
  totals 750 mm² (three servo headers, SWD header, level shifter, a TVS, one
  electrolytic, passives), and the band above it is 83% empty.
- **Mounting holes move.** Two holes sit at y ≈ 227, and others at y ≈ 133
  and 156. A 160 mm board changes the mounting pattern. The handoff lists
  electrical interfaces to preserve but says nothing about the mechanical
  one. The owner should confirm the robot can take a new hole pattern.
- **Edge clearance.** J13/J14 screw terminals are 0.5 mm from the right edge
  and the USB-C overhangs it by design; both are fine without rails only if
  the factory agrees. C93/C94 are surface-mount parts 2.2 mm from the edge.
  Economic says rails are "not necessary", but the saved Standard order
  needed them. Expect either 238 mm with rails or a factory query.
- **HASL versus fine pitch.** The board has 0.5 mm-pitch leadless parts: two
  QFN-24s, the VQFN-20 buck controller and the UQFN-10 USB switch
  (1.5 × 2 mm), plus two LQFP-48s and the USB-C. HASL is within the
  factory's stated limits, but uneven solder height on the UQFN-10 is the
  realistic failure, and that part carries the only USB path. ENIG is $14.90.
  With the two Thor swaps there is room for it under $300; without them
  there is not.
- Economic reflow is fixed at 255 °C with no solder-paste inspection.
  Nothing on the BOM is excluded by that, but the saved order's per-part
  orientation review is still required.

## What I did not verify

- No Economic assembly quote exists for this BOM. Every fee above is the
  published schedule times a count.
- No candidate layout exists, so drill rules, USB geometry on the new stack
  and the 160 mm placement are untested.
- Inductor and FET substitutions were checked against catalog ratings only,
  not against datasheet curves or the compensation network.
- Copper results are DC resistance at 20 °C from the saved fills. No thermal
  simulation, no measurement.
- The impedance solver is uncalibrated against the factory's own calculator.

## Decisions for the owner

1. Answered: 5 A per wheel is enough, so 1 oz copper is acceptable for the
   motor path (see section 2). Two driven wheels, so about 10 A at J2.
2. Is a changed mounting-hole pattern acceptable for a 160 mm board?
3. HASL at the lowest price, or ENIG for $14.90?
4. Accept the two Thor part substitutions pending a designer check?

## Evidence

`evidence/` holds the scripts and raw results: `extract.py` and `solve.py`
(copper resistance; `res1.json`, `res2.json`), `zdiff.py` (USB pair
impedance), `fit.py` (occupancy and edge distances), `roles.py` (net roles
and joint counts). Run the KiCad-dependent ones through
`source/fabrication/with_kicad.sh` with `PDB_KICAD_STATE=/tmp/pdb-kicad-red-team`.
