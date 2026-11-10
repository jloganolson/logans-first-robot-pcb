# v0.11 compact, edge-connector layout: handoff for independent vetting

**State on 10 November 2026:** an unpaid JLCPCB cart entry
`Robot_PDB_v11_Gerbers_Y8` holds five boards with two assembled for
**$321.20 before shipping** ($53.75 boards + $267.45 Economic assembly).
The owner's target was $300. They allowed $10-20 over it for a better Thor
inductor (+$17.12) and then asked for the six regulator inductors to be
swapped to higher-voltage parts as well (+$13.28). Nothing is paid or approved. Payment and production approval belong
to the owner.

`Y8` is the only entry in the cart. The earlier entries `Y2` to `Y7` were
removed on 10 November 2026 at the owner's request; all of them except `Y7`
carried part rotations that were found to be wrong (see "Placement rotations"
below), and `Y7` had the old 30 V regulator inductors.

The v0.10 handoff, `docs/HANDOFF_V10_VALUE_ENGINEERED.md`, still holds for
what v0.11 did not change: the cost-down choices, the Thor current-limit
analysis, the USB pair widths and the heat model.

- Board: `revisions/v0.11/kicad/robot_pdb.kicad_pcb`, SHA-256 `9e2ac58e2b295c252fd9d9d2044a3d4543f521787b17a18788caf1f443d97d41`
- Generator: `source/generator/build_v11.py` and `labels_v11.py`; change record `revisions/v0.11/derivation.json`
- Audit: `source/fabrication/audit_v11.py`, result `outputs/v11-order-preparation/audit-v11.json` (PASS)
- Package: `outputs/v11-order-preparation/package-9e2ac58e2b29/`
- Quote record: `outputs/v11-order-preparation/factory-quote.json`, `factory-quote-charge-details.png`
- Argon's review of the first v0.11 build and what was done about it: `red-team-findings/2026-11-10/argon/DISPOSITION_v11.md`
- Heat model for v0.11: `red-team-findings/2026-11-10/thermal/thermal_v11.py`, results in `thermal/v11/`
- Pictures: `docs/v11-assets/before-after.png`, `board-top.png`, `board-labels.png`, `thermal-map.png`

## What changed from v0.10

1. **Outline 228 x 195 mm became 228 x 155 mm.** The hobby-servo block
   (reference numbers 7000-8999 plus jumper J9928) was laid out again. Each
   sub-circuit moved as a rigid piece with its own copper: the servo 5 V buck
   rotated into the bottom-left corner with fuse F7000, bulk capacitor C7111
   and TVS D7001 beside it; the output buffer next to it; the STM32 servo
   controller translated next to the USB hub.
2. **Every plug is at a board edge.** The owner asked for this for an
   enclosure, with compact use of space taking priority over a single edge.
   - J3 (Thor, Micro-Fit) moved from the middle of the board to the left edge.
   - J301, J302 (XL330) and J401, J402 (XL430) moved to the bottom edge.
   - J7004-J7006 (hobby servos) and J7008 (programming) are on the bottom edge.
   - Unchanged and already on edges: J2 (motor wires, left), J101 and J501
     (top), J13, J14 and J10 (right).
   - Still inside the board: the soldered wire pads for the packs (J1, J4)
     and the master switch (J5). They are not plugs.
3. **New power copper for the moved plugs** (hand estimates, not a field solve):

   | Run | Copper | Length | Estimated resistance | At full load |
   |---|---|---|---|---|
   | Thor +24 V to J3 | In2 strip about 10 mm wide and B.Cu strip about 7 mm wide in parallel, 20 vias at the old plug position | about 45 mm | about 2 milliohm | 16 mV, 0.13 W at 8 A |
   | XL430 10.8 V to J401/J402 | In2, about 14 mm wide, one 4.5 mm neck; 9 vias from the existing B.Cu pour | about 78 mm | about 6.5 milliohm | 33 mV, 0.17 W at 5 A |
   | XL330 5 V to J301/J302 | B.Cu, about 24 mm wide | about 45 mm | about 1 milliohm | 5 mV at 5 A |

   The Thor strip on In2 is notched around the three vias of bulk capacitor
   C3 so that C3 stays on the battery plane. Ground returns use the solid In1
   plane.
4. **Fifteen signal links were rebuilt** by the project's grid maze router:
   the eleven servo-block links, plus `DXL330_DATA` and `DXL430_DATA` from
   where the old copper ended to the moved plugs (about 53 and 56 mm, then
   14.5 mm plug to plug). The old branches to the vacated pad positions were
   pruned.
5. **Changes made after Argon's review:** copper patches with six vias each
   on both pads of D7001 and on the ground pad of C7111; the servo 5 V plane
   cut back so it no longer lies under the fused-input copper or the
   regulator's feedback parts; one ground via beside C7103; two leftover vias
   removed.
6. **Silkscreen replaced.** 76 labels are placed by `labels_v11.py`, clear of
   pads, holes, part bodies and each other: connector names with ratings,
   polarity at every power pad, pin order at every multi-pin plug, names for
   the nine LEDs and eleven test points, jumper functions, fuse ratings and a
   seven-line legend. Reference designators remain hidden.
7. **Mounting holes:** H7002 at (95.2, 151.3), H7003 at (3.5, 151.5), H7004
   at (214.5, 151.3) mm. The other twelve are where v0.10 had them.
8. **L1 is the Coilcraft XAL1510-103MED again** (LCSC C3911782, 60 V).
9. **The six battery-fed TPS54560 regulators have 75 V inductors.** Sunlord
   MWSA1004S (reported 30 V) became Vishay IHLP-4040DZ-01: `IHLP4040DZER6R8M01`
   (C845080) at L2, L3, L4 and L7002, `IHLP4040DZER100M01` (C845065) at L5 and
   L6. Read from Vishay datasheet 34193 (revision 02-Oct-2026): rated operating
   voltage across the inductor 75 V; 6.8 uH is 21.2 milliohm typical, 13.5 A
   saturation, 8.0 A heat rating; 10 uH is 33.2 milliohm, 12.0 A, 6.8 A. Same
   inductance values, so the regulators are electrically unchanged apart from
   resistance. Vishay's land pattern (12.07 mm over the pads, 5.82 mm between
   them, 3.25 mm wide) lies inside the existing pads (13.6 / 5.4 / 4.1 mm), so
   the footprint was not changed. The sister series IHLP-4040DZ-11 is only
   50 V; do not substitute it. The four amplifier output inductors L70-L73
   stay Sunlord: they never see more than 11.7 V.

## Placement rotations

Opening each oriented part alone in the factory's 2D placement viewer showed
that thirteen rows of the placement file put the part off its pads. The same
rows were wrong in the v0.9 and v0.10 files, which had only been spot-checked.

- 90 degrees off: Q7001, U9900, U9904, U2, U14, U7007, and all six TPS54560
  regulators (U3-U7, U7003).
- 180 degrees: J3.

All thirteen are corrected in `export_v11.py` (`V11_ROTATION_FIXES`) and were
looked at again after re-upload. Checked and already correct: every
electrolytic with a factory model, both crystals, the LEDs, the SS1060 diodes,
the FETs, U1, U10, U11, U12, U13, U15, U16, U17, U7002, U7006, U7009, U9902,
C9902, the USB-C socket, both XT30s and the JST VH headers. C20 has no factory
model and could not be checked by eye.

## What was checked

- **Native DRC:** 0 errors, 0 unconnected pads, 11 warnings (2 library
  mismatches, 9 dangling track ends, all inherited). v0.10 had 13.
- **`audit_v11.py` (PASS):** same 366 references, footprints and pad-to-net
  assignments; 286 parts did not move; the 80 that did are servo-block parts
  or the five recorded plugs, and each kept its shape; outside the servo block
  the only copper differences are on `P4_DP`, `P4_DM`, `V5_USB` (shortened),
  the two Dynamixel data nets (re-routed) and added vias on `+24V` and
  `+12V_SRV`; no new zone outside the block except on `+24V`, `+12V_SRV` and
  `+5V_SRV`; all vias 0.30 mm or larger; all copper inside the outline;
  schematic netlist matches the board.
- **Factory:** detected 4 layers, 155 x 228 mm; 82 of 82 BOM lines matched;
  same options as before (JLC04161H-7628, 1 oz / 0.5 oz, lead-free HASL,
  plugged vias, Economic, top side, manual confirmation of production file and
  placement).

## Where to push hardest

1. **Nothing in the final build has had an independent review.** Argon saw
   only the first v0.11 build. The edge-connector move, the new power runs,
   the labels and the rotation corrections were all made afterwards.
2. **The new power runs are sized by hand estimate.** Check the Thor strip in
   particular: its width past the J5 pads, the notch around C3, the 20-via
   field, and whether carving it out of the battery plane on In2 hurts the
   feed to anything. The LM5146 senses its output at the regulator, so the
   drop along the strip is not corrected.
3. **Dynamixel data lines are now about 55 mm longer** and were auto-routed
   with staircase segments. They are half-duplex TTL at up to a few Mbit/s.
4. **Heat (re-modelled on v0.11, same simple model, about +/-30%).** With
   Thor at 8 A and typical rail loads (12.3 W of loss) the hottest spot is
   still the AUX regulator U7 at about +45 C above ambient on the ordered
   copper; the moved servo buck is about +14 C and the new Thor strip region
   about +18 C. A new case with every output at its rated current (24.8 W)
   gives about +78 C at the spare 5 V and XL430 regulators, which is not
   sustainable in still air. Inside an enclosure add the enclosure's own air
   temperature rise. Not measured.
5. **Still open from the v0.10 hold:** the electrolytic capacitors' reflow
   limit against the Economic line's profile is unconfirmed. (The inductor
   voltage question is closed by item 9 above.) The new inductors' heat
   rating for the 10 uH part (6.8 A for a 40 C rise) is closer to the 5 A
   rated load than the Sunlord part's was; their saturation current is higher.
6. **Mechanical:** three holes and seven connectors moved. Nothing has been
   checked against the robot or an enclosure. J3's body is 1.0 mm from the
   left edge.
7. **Space:** the area the Dynamixel plugs vacated (about x 130-178, y 82-112
   mm) is now empty. The strip height is set by the servo buck's 33 mm
   sub-layout, so shrinking further means re-laying that regulator or the
   main board.
8. **Known cosmetic items:** the board file and Gerber job file still say
   ENIG and impedance controlled (left from v0.9; the order form governs).
   The inductor footprints are still named `L_Sunlord_MWSA1004S`.

## Cart

| Entry | What | Before shipping |
|---|---|---:|
| `Robot_PDB_v11_Gerbers_Y8` | Final v0.11 with 75 V regulator inductors, this document | $321.20 |

Removed on 10 November 2026 at the owner's request: `Y7` ($307.92, same board
with the 30 V inductors), `Y6` ($305.40, first v0.11 build), `Y5`, `Y4`, `Y3`
(v0.10) and `Y2` (v0.9). Nothing in the cart is selected for checkout.
