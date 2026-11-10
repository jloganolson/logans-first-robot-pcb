# v0.9 prototype commissioning checklist

These are staged prototype checks, not completed measurements or achieved
ratings. Keep a record of the actual board revision, firmware hashes, supply,
loads, oscilloscope captures and temperatures. Read the section-specific guides
before each powered test.

## Before purchase

- Confirm that the Gerber, BOM and placement files belong to the same current
  v0.9 hash-bound package. Review fresh native/independent results, documented
  prototype exceptions and the actual supplier placement preview.
- Review the **total assembled quote**, not just catalog component allocations.
  Confirm stock/attrition and the exact selected parts; no automatic substitutes.
- Plan the manual fitting, one PWM MCU programming step, harness and bench work.
  This prototype is not delivered as a fully commissioned robot controller.
- Read the [retained USB risk and fallback](V09_USB_PROTOTYPE_REVIEW.md). The
  inherited audio/Dynamixel reference/return departures may need external
  adapters, rework or another spin; their reviewed status is not a bench pass.

## Before applying power

- Fit and inspect all mandatory hand-fit items: branch fuses, exact **TLV3011BIDBVR**, connectors and harness parts.
  Optional OFF headers and test pads have different requirements from these.
- Inspect source-end battery fuses, four-wire DPST wiring and strain relief.
  Leave packs and all loads disconnected for initial supply tests. Do not
  connect unequal packs together to perform an initial bench test.
- Fit all seven OFF shunts with the board unpowered. Inspect for shorts and
  confirm each shunt's EN/GND identity. An OFF shunt does not isolate a fault,
  discharge a capacitor or block an externally powered output.

## Rails, one at a time

Use a current-limited bench source through one intended battery input and the
proper switch/fuse path; leave the other pack input empty. Begin with no Jetson,
Pi, actuators, wheels or speakers attached. Work within27–33.6V. Choose current
limits for the particular test rather than enabling every supply at once.

| Section | Nominal target | Record before connecting equipment |
|---|---:|---|
| Pi |5V|Startup/loaded voltage, ripple, current limit, temperature|
| USB control source |4.96V|Source and hub/child endpoint voltage, startup/inrush, overload reporting|
| XL330 |5V|Dummy-load behavior and shared-chain current limit|
| XL430 |10.8V|Dummy-load behavior and shared-chain current limit|
| Audio/AUX |11.7V|Rail behavior, amplifier startup and output behavior|
| MG90S |4.992V|Pulse load/stall behavior and recovery, then one servo before three|
| Thor |24.329V|Dummy-load regulation, actual current limit, ripple/overshoot and heat;8A is not a validated rating|

Enable a section by removing its OFF shunt while unpowered, then test it.
Measure what happens when disabled again, including residual voltage and any
backfeed. Keep other sections disabled until individually checked. For an
input-side fault, an EN shunt is insufficient: disconnect/repair the actual
feed before continuing.

## USB, firmware and signals

- Fit U9903 before expecting USB attachment. Check board-off/host-on,
  board-on/host-off, unplug, both startup orders and both USB-C orientations.
  Measure raw VBUS, H_V33 and OE_N to verify the detector and power separation.
- Program the PWM controller with the reviewed images; capture actual
  USB descriptors. Verify audio, both UARTs and PWM together, including
  disconnect/reconnect, suspend/resume and error behavior.
- Verify PWM default-off, explicit arming, command timeout, reset, watchdog and
  disconnect behavior before attaching a mechanism. Disarming signals leaves
  the servo5V rail powered. Check each actual servo's wire order and endpoints.
## Existing motor controllers

J2 restores the original F1-fused battery-voltage feed. Retain the existing motor
controllers and their external control connection. There is no onboard motor
conversion, CAN adapter or braking clamp. Check harness polarity/current limits,
existing controller configuration, battery/BMS regenerative-current limits and
full-battery behavior before reconnecting traction. The board fuse does not
establish controller or wiring current ratings.

Stop before master OFF. Backdriven controllers can energize the board-side bus
with the battery positives disconnected; measure residual voltage and do not
interpret OFF as a mechanical brake or immediate discharge.

## Connecting Thor

Only after dummy-load qualification, continuity-test the delivered Molex cable
and verify the Thor-end voltage/polarity before mating. Board J3 pins1/2 are
positive and3/4 ground; use the exact [verified cable drawing](THOR_POWER_CABLE.md).
For the known-working PowerStream fallback, unplug Thor from J3 and power it
directly from that supply while the board section is disabled. Never parallel
the two supply outputs.
