#!/usr/bin/env python3
"""Fresh native and independent exported XML/pad audit for resistor motor cell."""
from audit_cells import CELLS,audit
CELLS['motor_resistor']=('motor-resistor','motor_resistor')
raise SystemExit(not audit('motor_resistor'))
