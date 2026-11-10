# Value-engineered prototype v0.10

Derived by script from the reviewed v0.9 board to bring the JLCPCB order (five
boards, two assembled) under $300. Same circuit and layout; thinner copper,
shorter outline (228 x 195 mm), factory-standard stack and via sizes, Economic
assembly, and four part changes (L1, U2, R13, FB2).

- Start here as the owner: [walkthrough](../../docs/PROTOTYPE_v0.10_WALKTHROUGH.html)
- Start here as a reviewer: [handoff](../../docs/HANDOFF_V10_VALUE_ENGINEERED.md)
- Every change, machine-readable: [derivation.json](derivation.json)

Board SHA-256 `1b3bcccac46a0f5773c472aa492ede3c1351764b9f63c53f64ded7864630e90c`.
Unpaid cart entry `Robot_PDB_v10_Gerbers_Y5`, $294.18 before shipping. No
purchase made; no hardware built or measured.

```sh
export PDB_KICAD_STATE=/tmp/pdb-kicad-red-team
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/generator/build_v10.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/audit_v10.py
bash source/fabrication/with_kicad.sh /usr/bin/python3 source/fabrication/export_v10.py
```

Rebuilding can change the board hash (zone refill), which invalidates the
uploaded package and the cart entry.
