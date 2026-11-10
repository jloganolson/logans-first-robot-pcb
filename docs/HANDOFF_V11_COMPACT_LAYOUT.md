# v0.11 compact layout: handoff for independent vetting

**State on 10 November 2026:** an unpaid JLCPCB cart entry
`Robot_PDB_v11_Gerbers_Y6` holds five boards with two assembled for
**$305.40 before shipping** ($53.75 boards + $251.65 Economic assembly).
The owner's target was $300 and they allowed $10-20 over it for a better Thor
inductor. Nothing is paid or approved. Payment and production approval belong
to the owner.

v0.11 supersedes v0.10 (`Robot_PDB_v10_Gerbers_Y5`, $294.18, on hold). The
v0.10 handoff, `docs/HANDOFF_V10_VALUE_ENGINEERED.md`, still holds for
everything this document does not mention: the cost-down changes, the Thor
current-limit analysis, the USB pair widths, the heat model and the two Argon
reviews.

- Board: `revisions/v0.11/kicad/robot_pdb.kicad_pcb`, SHA-256 `1c351a03d3f0b3f11d9e3ada8f00d47ceda0ed84d05fd2d542ebe165c876a0f5`
- Generator: `source/generator/build_v11.py`; change record `revisions/v0.11/derivation.json`
- Audit: `source/fabrication/audit_v11.py`, result `outputs/v11-order-preparation/audit-v11.json` (PASS)
- Uploaded package: `outputs/v11-order-preparation/package-1c351a03d3f0/`
- Quote record and screenshots: `outputs/v11-order-preparation/factory-quote.json`, `factory-quote-charge-details.png`, `factory-cart.png`, `factory-placement-preview-servo-block.png`
- Before/after picture: `docs/v11-assets/before-after.png`

## What changed from v0.10

1. **Outline 228 x 195 mm became 228 x 155 mm.** Only the hobby-servo block
   (reference numbers 7000-8999 plus jumper J9928) was laid out again. v0.10
   had inherited its position from an older cell arrangement, which left the
   lower-right quarter of the board bare.
2. **Each sub-circuit moved as a rigid piece with its own copper:**
   - servo 5 V buck (U7101 area): rotated 90 degrees into the bottom-left corner;
   - its 5 A fuse F7000, bulk capacitor C7111 and TVS D7001: beside the buck
     input (the fuse used to be about 150 mm of plane away);
   - PWM output buffer: next to the servo 5 V;
   - servo headers J7004-J7006: bottom edge, 15 mm pitch, silkscreen
     `SERVO n  1G 2+ 3S`;
   - servo controller (STM32F072) with its USB tail: translated 51 mm right
     and 12 mm up, next to the hub. Its USB pair went from 173 mm to 110 mm
     per line with the same 0.57 mm length difference;
   - SWD header J7008: bottom edge beside the controller.
3. **Connections between the pieces were rebuilt.** Eleven signal links were
   routed by the project's grid maze router (18-56 mm each, lengths and via
   counts in `derivation.json`). Power is on planes: `PWM_5V` on In2 under the
   whole servo strip, `PWM_VIN` on B.Cu between fuse, bulk capacitor, TVS and
   buck input, `IO_V3_PWM` on In2 under the controller, a `VIN` finger on In2
   down to the fuse, and ground pours on F.Cu and B.Cu across the strip
   (v0.10 left much of it bare).
4. **Three mounting holes moved:** H7002 to (105.17, 151.3), H7003 to
   (3.5, 151.5), H7004 to (176.0, 151.5) mm. The other twelve are where
   v0.10 had them.
5. **L1 is the Coilcraft XAL1510-103MED again** (LCSC C3911782, 60 V rated),
   reversing v0.10's swap to the 30 V Cjiang FEXL1510A. Same footprint.
   This closes the L1 half of the v0.10 hold.

## What was checked

- **Native DRC:** 0 errors, 0 unconnected pads, 13 warnings (2 library
  mismatches, 9 dangling track ends, 2 dangling vias). v0.10 also had 13.
  The two dangling vias are leftover `IO_PWM2_OUT`/`IO_PWM3_OUT` vias inside
  the buffer block that now have copper on one layer only; harmless.
- **`audit_v11.py` (PASS):** same 366 references, footprints and pad-to-net
  assignments; 291 parts did not move and the 75 that did are all servo-block
  parts and kept their shape; every track and via outside the servo block is
  identical to v0.10 except the recorded shortening of `P4_DP`, `P4_DM` and
  `V5_USB`; zone definitions changed only inside the block and the filled
  area of every zone above it is unchanged; all vias 0.30 mm or larger; all
  copper inside the outline; smallest hole-to-edge wall 1.4 mm; schematic
  netlist matches the board.
- **`export_v11.py`:** BOM is the v0.10 BOM with the L1 line changed.
  Placement rows for parts that did not move equal v0.10's; rows for moved
  parts turned by exactly the angle their footprint turned.
- **Factory:** detected 4 layers, 155 x 228 mm; 81 of 81 BOM lines matched;
  same options as Y5 (JLC04161H-7628, 1 oz / 0.5 oz, lead-free HASL, plugged
  vias, Economic, top side, manual confirmation of production file and
  placement). Moved parts were looked at in the 2D placement preview and sit
  on their pads with matching polarity marks.

## Where to push hardest

1. **The re-laid servo block was auto-routed and has had no second pair of
   eyes.** Look at it on all four layers. In particular: the `PWM_VIN` B.Cu
   island under the buck (does it sit under the switch node or inductor in a
   way that matters, given the In1 ground plane between); current paths from
   F7000 through the `VIN` finger and into the buck; return paths for the
   three PWM outputs, which run 34-56 mm on F.Cu over solid In1 ground.
2. **Heat for the servo buck was not re-modelled.** The model in
   `red-team-findings/2026-11-10/thermal/` was run on v0.10. The servo buck
   was not the hot spot there and now has more ground pour around it, but
   that is an argument, not a result.
3. **Still open from the v0.10 hold:** the six Sunlord MWSA1004S inductors
   (L2-L6, L7002) are reported as 30 V rated against 33.6 V packs, and the
   electrolytic capacitors' reflow limit against the Economic line's profile
   has not been confirmed. Neither was changed here.
4. **Rotation review is still not part-by-part.**
5. **Mechanical:** three holes moved and the servo, SWD and jumper positions
   changed; nothing has been checked against the robot's mounting.
6. **Cosmetic, known:** the board file and Gerber job file still say ENIG and
   impedance controlled (left from v0.9; the order form governs). The PCB
   remark on the order was cut at 200 characters mid-word.

## Cart

| Entry | What | Before shipping |
|---|---|---:|
| `Robot_PDB_v11_Gerbers_Y6` | v0.11, this document | $305.40 |
| `Robot_PDB_v10_Gerbers_Y5` | v0.10 final, on hold | $294.18 |
| `Robot_PDB_v10_Gerbers_Y4`, `_Y3` | superseded v0.10 builds | $294.27, $289.41 |
| `Robot_PDB_v09_Gerbers_Y2` | reviewed v0.9 fallback | $535.15 |

Nothing has been removed from the cart; that needs the owner's say-so.
