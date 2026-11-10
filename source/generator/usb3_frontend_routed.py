"""Frozen observed SS pin mapping for the incomplete25/34 engineering PCB. Not a fabrication release."""
from copy import deepcopy
from usb3_frontend import *
from usb3_frontend import PARTS as BASE_PARTS
PARTS=deepcopy(BASE_PARTS)
OVERRIDES={'C552': {'2': 'UP_RX1N'}, 'C553': {'2': 'UP_RX1P'}, 'C541': {'2': 'CAM_TX1P'}, 'C557': {'2': 'CAM_RX1P'}, 'C532': {'2': 'UP_TX1P'}, 'C556': {'2': 'CAM_RX1N'}, 'C540': {'2': 'CAM_TX1N'}, 'U500': {'47': 'UP_TXN', '48': 'UP_TXP'}, 'C531': {'2': 'UP_TX1N'}}
for p in PARTS:
    p["pins"].update(OVERRIDES.get(p["ref"],{}))
