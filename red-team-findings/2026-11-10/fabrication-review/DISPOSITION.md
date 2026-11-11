# Fabrication review of v0.11 build 9e2ac58e2b29: what was done

Review: `V11_COMPACT_LAYOUT_FEEDBACK.md` in the reviewer's own `robot-pdb-review` project
(a second agent, 10 November 2026, against commit `d5d6725`). Its verdict was
to hold the Y8 order. Corrected board: `494e931955b1`.

| Finding | Checked how | Result |
|---|---|---|
| 1. Both XL330 plugs fed through a 0.37 mm copper bridge at (123.48, 138.36) | Filled B.Cu polygon scanned row by row; tracks listed | **Right.** `IO_PWM3_OUT` crossed the whole pour on B.Cu and `IO_SERVO_ARM` half of it. Fixed with a second 5 V plane on In2 under the plugs and 16 vias. `pour_width.py` added to the audit; it fails on the old build and passes on the new one. |
| (same finding) Thor and XL430 added drops match the hand estimates | Not re-modelled | Accepted. The new check also showed the Thor copper squeezing past J3's own ground pins (about 9.4 mm of copper in all over 2 mm); left as is. |
| 2. Lelon 250 C peak against JLCPCB Economic 255 +/-5 C; C20 has no preview model | Not re-examined | **Still open; owner to ask JLCPCB.** Figures added to the walkthrough and handoff. |
| 3. Thor overload peak near 26 A against 26.3 A saturation | R10 = 49.9 k confirmed in the generator; the current figure was not re-derived | Bench test added to the walkthrough's power-up steps. No design change. |
| 4. Heat model held Q1 at 8.3 A in the full-load case | Read `thermal_v11.py` | **Right, and the typical case was low too.** Q1 current now comes from the loads: 10.2 A typical, 13.5 A at full rating. Totals 12.5 W and 25.5 W; hottest spots +45 C and +79 C (were +45 and +78). Conclusions unchanged. |
| 5. Vertical plugs need access from above | Footprints | **Right.** Added to the walkthrough's heat/enclosure notes and risk table. No board change; the owner is deciding whether to move to right-angle plugs in a later revision. |
| 6. Matched-pack instruction missing | Walkthrough text | **Right.** Warning added before the battery step, and a row in the risk table. |

Not done: the corrected package has not been uploaded, so the factory has not
seen it, and nobody independent has reviewed the fix.
