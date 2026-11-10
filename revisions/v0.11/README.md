# Compact prototype v0.11

v0.10 with the hobby-servo block laid out again so the board is
**228 x 155 mm** instead of 228 x 195 mm, and the Thor inductor (L1) back to
the 60 V Coilcraft XAL1510-103MED. Same circuit, same parts list otherwise.
Everything above the servo block, and the USB block, is copper-identical to
v0.10.

- Start here as the owner: [walkthrough](../../docs/PROTOTYPE_v0.11_WALKTHROUGH.html)
- Start here as a reviewer: [handoff](../../docs/HANDOFF_V11_COMPACT_LAYOUT.md)
- Every change, machine-readable: [derivation.json](derivation.json)

Board SHA-256 `1c351a03d3f0b3f11d9e3ada8f00d47ceda0ed84d05fd2d542ebe165c876a0f5`.
Unpaid cart entry `Robot_PDB_v11_Gerbers_Y6`, $305.40 before shipping. No
purchase made; no hardware built or measured.

```sh
export PDB_KICAD_STATE=/tmp/pdb-kicad-red-team
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/generator/build_v11.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/audit_v11.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/export_v11.py
```

Rebuilding can change the board hash (zone refill), which invalidates the
uploaded package and the cart entry.
