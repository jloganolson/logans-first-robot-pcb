"""PWM-only selection of the reviewed robot-I/O cell; no USB-CAN hardware."""
from copy import deepcopy
import robot_io

TITLE='Three USB-controlled MG90S outputs with a dedicated 5V supply'
PARTS=[deepcopy(s) for s in robot_io.PARTS
       if not s['block'].startswith(('B1.','C.')) and s['ref']!='TP1']
REFS={s['ref'] for s in PARTS}
SOURCE_EXCLUDED_REFS={s['ref'] for s in robot_io.PARTS}-REFS
SOURCE_NETS={n for s in PARTS for n in s['pins'].values() if n}
CUSTOM_SYMBOL_PINS=deepcopy(robot_io.CUSTOM_SYMBOL_PINS)
NO_CONNECT_PINS={r:deepcopy(v) for r,v in robot_io.NO_CONNECT_PINS.items() if r in REFS}
assert 'U2' in REFS and 'U1' not in REFS and 'U4' not in REFS
assert not any('CAN' in n for n in SOURCE_NETS)
