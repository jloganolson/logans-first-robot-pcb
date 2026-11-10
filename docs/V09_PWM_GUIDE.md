# v0.9 three-servo control

Only **U7002**, the PWM STM32F072CBT6, is fitted in the selected board. There is
no CAN MCU. The archived two-controller firmware documentation describes the
source cell; use only its **PWM** image for v0.9. J7008 is the PWM service header.
The three outputs are J7004–J7006, with a separate shared nominal4.992V supply.
Check each actual servo's plug order before connection: the pictured MG90S uses
brown ground, red power and yellow signal.

The current PWM source is in `firmware/robot_io/pwm/`. Its pinned build produces
`firmware/robot_io/build/robot_io_pwm.elf` and `.bin`; exact compiler, dependencies
and artifact hashes are recorded in `firmware/robot_io/build/build_report.json`.
Use SWD with the actual chip's voltage/pinout verified. Firmware has compiled,
but has not been flashed or exercised on physical hardware. Do not flash the
CAN image or an unrelated board image.

## Host sequence

Open the enumerated PWM USB CDC port with DTR asserted. Device identity/port
number must be verified on the real Jetson rather than assumed.

1. Send `INFO` followed by LF. It disarms and replies
   `OK INFO 1 <token> DISARMED`.
2. Send `STAGE <token> 1 1500 1500 1500` to stage three pulse widths.
3. Send `ARM <token> 2` only when the mechanism is ready.
4. Use `SET <token> 3 1400 1500 1600` or `KEEP <token> 4`, increasing the
   sequence for every accepted command. Refresh comfortably before500ms.
5. Send `DISARM` before closing. It requires no token.

These values illustrate the protocol;1500µs is not a verified safe position for
an attached mechanism. Begin unloaded. Initial bounds are1000–2000µs at50Hz;
the image's advertised wider servo travel is not enabled automatically.

Reset, USB disconnect/suspend, DTR drop and command timeout remove signal enable.
Resume does not re-arm. A fresh disarmed session is required after a fault.
Tokens prevent accidental stale commands, not unauthorized access. An
independent watchdog also removes enable if foreground execution stops.

**Disarming leaves servo power present.** Servo behavior without pulses must
be measured. The MG90S OFF shunt disables the shared supply and is not an
isolating switch. Keep mechanisms disconnected until reset/brownout/USB-event
behavior, actual pulse timing and the servo's endpoints have been measured.

The current native controller test passed the valid transaction, atomic range
rejection, stale-token/sequence, timer-rollover, disconnect and100,000 malformed
line cases under address/undefined-behavior sanitizers. Leak checking was disabled
because this execution environment cannot support LeakSanitizer; these tests do
not demonstrate electrical behavior. USB low-power suspend current is still
unimplemented/unmeasured and the prototype USB identity is not a production
identity. See [commissioning](V09_BRINGUP_CHECKLIST.md).
