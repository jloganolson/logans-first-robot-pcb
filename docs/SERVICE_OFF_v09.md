# v0.9 local regulator OFF headers

Seven optional two-pin headers provide removable OFF shunts. Pin1 is the local
regulator EN signal; pin2 is GND. **Short=OFF; open=normal startup/UVLO.** The
original solder jumpers remain in parallel; a bridged jumper also keeps it OFF.

| Header | Original jumper | Section |
|---|---|---|
|J9921|JP1|Thor24.33V|
|J9922|JP101|Pi5V|
|J9923|JP201|Local USB control power: hub/audio/UART/PWM logic|
|J9924|JP301|Shared XL3305V|
|J9925|JP401|Shared XL43010.8V|
|J9926|JP501|Audio amplifier/AUX11.7V; the USB codec remains on USB power|
|J9928|JP7101|Shared MG90S5V; PWM logic uses USB power|

The motor passthrough has no regulator or local OFF header. Use the external
master and existing controller behavior. J9927 and the motor converter are absent.

Change shunts unpowered. These headers disable regulation; they do not isolate
a shorted input, discharge capacitors, block external backfeed or provide an
emergency stop. Do not inject external voltage into them. Measure outputs before
connecting loads. Software arming controls PWM signals separately and leaves
servo power present.

The selected hardware is a 2.54mm two-pin header/removable shunt. Header tails,
access and wire forces require normal mechanical inspection. The main composition
records all seven placements and fourteen short local EN/GND links; fresh native
full-board connectivity is the final saved-copper check. Historical eight-header
v0.8 tests do not qualify the new board.
