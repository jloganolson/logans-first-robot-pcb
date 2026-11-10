#!/usr/bin/env python3
"""Refill and report DRC for a disposable working-copy board, using KiCad 7."""
import sys,subprocess
from pathlib import Path
import pcbnew

profile=Path(sys.argv[1]).with_suffix('.kicad_pro')
original=profile.read_bytes() if profile.exists() else None
board = pcbnew.LoadBoard(sys.argv[1])
pcbnew.ZONE_FILLER(board).Fill(board.Zones())
try:
    pcbnew.SaveBoard(sys.argv[1], board)
finally:
    #KiCad7's Python SaveBoard can write the process's default project over
    #the adjacent profile. Preserve reviewed rules and reopen in a fresh
    #process: checking against stale/default rules produces false results.
    if original is not None:profile.write_bytes(original)
script="import pcbnew as p; b=p.LoadBoard("+repr(sys.argv[1])+"); p.WriteDRCReport(b,"+repr(sys.argv[2])+",p.EDA_UNITS_MILLIMETRES,True)"
subprocess.run([sys.executable,'-c',script],check=True)
