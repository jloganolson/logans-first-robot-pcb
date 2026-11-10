# Compact, edge-connector prototype v0.11

v0.10 with the hobby-servo block laid out again (228 x 155 mm instead of
228 x 195 mm), every plug moved to a board edge, a full set of silkscreen
labels, the Thor inductor (L1) back to the 60 V Coilcraft XAL1510-103MED, and
the six TPS54560 regulator inductors changed to 75 V Vishay IHLP-4040DZ-01.
Same circuit and parts list otherwise.

- Start here as the owner: [walkthrough](../../docs/PROTOTYPE_v0.11_WALKTHROUGH.html)
- Start here as a reviewer: [handoff](../../docs/HANDOFF_V11_COMPACT_LAYOUT.md)
- Every change, machine-readable: [derivation.json](derivation.json)

Board SHA-256 `9e2ac58e2b295c252fd9d9d2044a3d4543f521787b17a18788caf1f443d97d41`.
Unpaid cart entry `Robot_PDB_v11_Gerbers_Y8`, $321.20 before shipping. No
purchase made; no hardware built or measured; the final build has not been
independently reviewed.

```sh
export PDB_KICAD_STATE=/tmp/pdb-kicad-red-team
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/generator/build_v11.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/audit_v11.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/export_v11.py
```

Rebuilding can change the board hash (zone refill), which invalidates the
uploaded package and the cart entry.
