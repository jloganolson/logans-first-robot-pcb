# v0.9: retain the existing motors

The owner chose the original motor passthrough to avoid buying replacement wheels. The replacement-wheel development is archived and is not part of this repository; its unfinished files are not an orderable alternative.

## Selected hardware

- Two individually source-fused battery inputs, external four-wire DPST master switch, common grounds. Stop before OFF.
- **J2: original F1-fused battery-voltage output** to the existing Flipsky controllers. F1 returns to the original30A axial part; this is not a validated continuous output rating. Existing controller control/braking configuration remains external.
- No wheel converter, brake clamp, external brake resistor, thermal-contact port, wheel CAN sockets or USB-CAN MCU/transceiver.
- Corrected Coilcraft Thor regulator, Molex430450412 output and2147551042 factory cable; Pi, two XL330 chains, two XL430 chains, stereo audio/AUX and three MG90S outputs.
- One self-powered USB2 hub serving audio, dual UART and PWM. Hub port3 is unconnected. No configuration EEPROM or guessed descriptor image.
- OAK-D, USB microphone and any later verified Daly adapter use external computer ports/hub. No custom USB3 or onboard Daly interface.
- Seven optional local OFF shunts: Thor, Pi, USB controls, XL330, XL430, audio/AUX and MG90S. Motor passthrough has no regulator OFF shunt.

The external master switch is a separate purchase, not factory assembly. Its
final exact part is still open: the documented80VDC30A Carling candidate was
observed at$83.62 and retains a manufacturer catalog-revision discrepancy to
resolve before wiring it. See switch selection.
This does not prevent current-limited single-input bench testing through the
intended switch/fuse interface, but is a hold before connecting both packs for
robot use. The board interface does not qualify an arbitrary two-wire switch.

The 228×230mm, four-layer board keeps the original USB-C connector at the original228mm board edge. Selected nominal1.6mm JLC041621-2116 is listed by the factory as1.648mm±10%; connector seating and finished impedance need production-file review. It uses2oz outer/1oz inner copper and the reviewed0.2mm via process.

## Qualification boundary

This is a staged engineering prototype. Fresh full-board native/identity/drill and saved-copper USB checks are required before preparing the quote. Actual supplier parts/placement and production-file review remain separate. No source-cell result or older factory draft approves the changed combined board.

Bench work remains: current-limited rail startup, dummy-load voltage/ripple/current-limit/thermal tests; USB attachment/power removal and all functions together; PWM firmware/default-off/timeout and real servo behavior. Thor's8A figure is a connector/design ceiling, not a guaranteed supply rating. Use the proven external PowerStream by unplugging Thor from board J3 and powering it directly; never parallel outputs.

The retained Full-Speed audio/Dynamixel USB geometry has explicit reviewed
reference/return departures. This is a limited prototype risk with external
adapter/rework/spin fallback, not an electrical pass. Read the
[current USB disposition](V09_USB_PROTOTYPE_REVIEW.md) before green-lighting.

Motor regeneration now follows the original direct connection to the battery bus. Verify existing controller/BMS settings, full-battery behavior and pack/harness limits. Master OFF opens the battery positives, but backdriven controllers can energize the board-side bus. Stop before OFF and measure residual voltage; no mechanical holding brake or qualified emergency-stop function is claimed.
