# Argon review of v0.11: what held up

Review: `argon-review-of-v11-1c351a03d3f0.md` (Gemini Argon, read-only, 10 November 2026).
It reviewed the first v0.11 build (board `1c351a03d3f0`). The final v0.11 build
(`1dabdd8f35dc`) includes the fixes below plus the edge-connector move and the
new labels, **which Argon has not seen**: its quota ran out during a second,
unfinished review of layout efficiency and labelling
(`argon-v11-layout-and-labels.md` is only the first line of that run).

Every claim was checked against the board or the factory viewer before acting.

| Argon finding | Checked how | Result |
|---|---|---|
| SOT-23 parts 90 degrees off in the placement file | Each part opened alone in the JLCPCB placement viewer | **Partly right.** Q7001 (3-pin), U9900 and U9904 (6-pin) were wrong. U1, U11, U17, U7006 and U7009 were already correct. |
| SS1060 catch diodes 180 degrees reversed | Viewer at high zoom: cathode stripe and "-" mark are on pad 1 (cathode, switch node) | **Wrong.** Argon read the "+" (anode) mark as the cathode band. No change. |
| LEDs possibly reversed | Viewer: "+" on the anode pad, "-" on the cathode pad | **Wrong.** No change. |
| TPS54560 regulators and U7007 "verified correct" | Viewer | **Wrong the other way.** All six TPS54560 (U3-U7, U7003) and U7007 were 90 degrees off. Fixed. |
| (not raised by Argon) | Viewer, part by part | U2 (Thor controller) and U14 (USB serial) 90 degrees off; J3 (Thor plug) 180 degrees. Fixed. |
| D7001 and C7111 tied to their nets by one 0.3 mm via and a 0.22 mm track | Geometry dump | **Right.** Each of those three pads now has a copper patch and six added vias. |
| No ground vias near the regulator input capacitors' ground pads | Geometry dump | **Right in substance** (inherited from v0.10, not caused by the rotation). One via fitted beside C7103; the other candidate spots were not clear of other copper. |
| Servo 5 V plane lies under the fused battery-voltage copper and the regulator's feedback parts | Zone outlines | **Right.** The plane is now cut back to the regulator output, the bottom edge and the buffer; ground fills the freed area. |
| Two dangling vias allowed through by the audit | DRC report | **Right.** Both pruned; the audit now fails on any increase in dangling vias. |
| J7008 label too close to the board edge | Render | **Right.** All labels were re-placed by `labels_v11.py` with a 0.8 mm edge margin. |
| Staircase segments from the grid router | Geometry dump | Right, cosmetic. Not changed. |
| Thor current limit with R13 = 220 ohm and the Coilcraft inductor | Its own recalculation | Agrees with the handoff: minimum above 8 A, worst-case peak about 21-24 A against 26.3 A saturation. No change. |
| Six Sunlord inductors rated 30 V; electrolytic reflow limit on the Economic line | Not re-examined | **Still open.** Owner decision. |

## The placement-rotation finding matters beyond v0.11

The wrong rotations were in the v0.9 and v0.10 placement files too. Those files
were described as "factory-matched starting values" and only three parts had
been corrected (two XT30s and U9902). The reviewed v0.10 cart entry
`Robot_PDB_v10_Gerbers_Y5`, and the first v0.11 entry `Robot_PDB_v11_Gerbers_Y6`,
both carry the uncorrected rotations and should not be ordered.

The order was set to "confirm parts placement, do not confirm automatically",
so the factory's own review would probably have caught these, but that is a
safety net, not a plan.

Method that worked: on the Component Placements page, choose 2D, then click a
part's row in the list on the right. The view jumps to that part at high
magnification with its pin-1 dot. Rows that group several parts zoom to fit
all of them; for those, use the mouse wheel on one member. One member per
supplier part number is enough, because every member gets the same offset.
