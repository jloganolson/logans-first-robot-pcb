#!/usr/bin/env python3
"""Independent XML/pad and fresh-process native checks for the held simple cell."""
from audit_cells import CELLS, audit
CELLS['motor_simple']=('motor-simple','motor_simple')
raise SystemExit(not audit('motor_simple'))
