# v0.11 compact, edge-connector layout: handoff for independent vetting

**State on 10 November 2026:** an unpaid JLCPCB cart entry
`Robot_PDB_v11_Gerbers_Y7` holds five boards with two assembled for
**$307.92 before shipping** ($53.75 boards + $254.17 Economic assembly).
The owner's target was $300 and they allowed $10-20 over it for a better Thor
inductor. Nothing is paid or approved. Payment and production approval belong
to the owner.

`Y7` supersedes every other entry in the cart. **Do not order `Y6`, `Y5`,
`Y4`, `Y3` or `Y2`:** their placement files carry part rotations that were
found to be wrong (see "Placement rotations" below).

The v0.10 handoff, `docs/HANDOFF_V10_VALUE_ENGINEERED.md`, still holds for
what v0.11 did not change: the cost-down choices, the Thor current-limit
analysis, the USB pair widths and the heat model.

- Board: `revisions/v0.11/kicad/robot_pdb.kicad_pcb`, SHA-256 `1dabdd8f35dca5d13a01a024d0310674ded7bb68d099827eadc257e1fcf39a4b`
- Generator: `source/generator/build_v11.py` and `labels_v11.py`; change record `revisions/v0.11/derivation.json`
- Audit: `source/fabrication/audit_v11.py`, result `outputs/v11-order-preparation/audit-v11.json` (PASS)
- Package: `outputs/v11-order-preparation/package-1dabdd8f35dc/`
- Quote record: `outputs/v11-order-preparation/factory-quote.json`, `factory-quote-charge-details.png`
- Argon's review of the first v0.11 build and what was done about it: `red-team-findings/2026-11-10/argon/DISPOSITION_v11.md`
- Pictures: `docs/v11-assets/before-after.png`, `board-top.png`, `board-labels.png`

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
- **Factory:** detected 4 layers, 155 x 228 mm; 81 of 81 BOM lines matched;
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
4. **Heat was not re-modelled** for the moved servo buck or the new runs.
5. **Still open from the v0.10 hold:** the six Sunlord MWSA1004S inductors
   (L2-L6, L7002) are reported as 30 V rated against 33.6 V packs, and the
   electrolytic capacitors' reflow limit against the Economic line's profile
   is unconfirmed.
6. **Mechanical:** three holes and seven connectors moved. Nothing has been
   checked against the robot or an enclosure. J3's body is 1.0 mm from the
   left edge.
7. **Space:** the area the Dynamixel plugs vacated (about x 130-178, y 82-112
   mm) is now empty. The strip height is set by the servo buck's 33 mm
   sub-layout, so shrinking further means re-laying that regulator or the
   main board.
8. **Known cosmetic items:** the board file and Gerber job file still say
   ENIG and impedance controlled (left from v0.9; the order form governs).
   The Gerber zip in the package was regenerated after upload; same board,
   different embedded timestamps.

## Cart

| Entry | What | Before shipping |
|---|---|---:|
| `Robot_PDB_v11_Gerbers_Y7` | Final v0.11, this document | $307.92 |
| `Robot_PDB_v11_Gerbers_Y6` | First v0.11 build; superseded | $305.40 |
| `Robot_PDB_v10_Gerbers_Y5`, `_Y4`, `_Y3` | v0.10; superseded | $294.18, $294.27, $289.41 |
| `Robot_PDB_v09_Gerbers_Y2` | v0.9; placement file has the same rotation errors | $535.15 |

Nothing has been removed from the cart; that needs the owner's say-so.
