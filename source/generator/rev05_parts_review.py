"""Proposed parts for the next prototype, based on the frozen v0.5 circuit.

Use CIRCUIT=rev05_parts_review with gen_sch.py in a scratch directory to
inspect the resulting schematic. The power-path layout is still under review.
"""
from copy import deepcopy

from rev05 import PARTS as BASE_PARTS, SCHEMATIC_NOTES as BASE_NOTES

REVISION = "0.5-parts-review"
SCHEMATIC_NOTES = BASE_NOTES + r"\nProposed parts only. F1/F2 holders and SW1 await power-path review."

PARTS = deepcopy(BASE_PARTS)
parts = {part["ref"]: part for part in PARTS}
for reference in ("FB1", "FB2"):
    parts[reference].update(
        lcsc="C133527", mpn="Sunlord UPZ1608E601-1R0TF",
        status="prototype candidate; verify USB drop and noise under load",
    )
parts["L1"].update(
    lcsc="C2045568", mpn="Bourns SRP1770TA-100M",
    status="prototype candidate; verify transient voltage, thermal margin and availability",
)
for reference in ("F1", "F2"):
    parts[reference].update(
        lcsc="", mpn="HOLD: replace blade footprint; evaluate Littelfuse 456 SMD fuse",
        status="hold: new land pattern, interrupt rating and branch coordination required",
    )
