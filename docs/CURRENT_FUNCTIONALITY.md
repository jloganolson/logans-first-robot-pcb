# Current robot board functionality — v0.9 passthrough

> Written for v0.9. The connections and limits below are unchanged in v0.10; cost and status figures are superseded by the README. An earlier replacement-wheel design mentioned here is archived and is not part of this repository.

| Connection | Quantity | Function and limits |
|---|---:|---|
| Battery inputs J1/J4 |2|Protected8S packs,27–33V intended/33.6V full; individual source-end fuses|
| Mechanical master J5 |1 four-wire interface|DPST opens both positive feeds before joining; grounds common; stop before OFF|
| Motor output J2 |1|Original fused **battery-voltage passthrough** to existing Flipsky controllers; no conversion or onboard control/braking hardware|
| Thor J3 |1|24.33V nominal, corrected Coilcraft inductor, four-contact Micro-Fit and Molex2147551042 factory cable; meter delivered polarity first|
| Pi J101 |1|Separate5V supply|
| XL330 J301/J302 |2|Chains2+2; shared5V supply/data bus, aggregate current/torque restrictions|
| XL430 J401/J402 |2|Chains2+1; shared10.8V supply/data bus|
| MG90S J7004–J7006 |3|Three PWM signals; dedicated shared5V servo supply; signal disarm leaves power present|
| Speakers J13/J14 |2|USB audio and bridge amplifier outputs; neither speaker lead is ground|
| Audio/AUX J501 |1|11.7V nominal, shared with amplifier|
| USB-C J10 |1|USB2 to Jetson for audio, Dynamixel and PWM; local power, raw host VBUS sensing only|
| PWM service J7008 |1|Program/recover the one PWM MCU; blank device cannot operate servos|
| Regulator OFF controls |7|Optional shunt headers, existing solder jumpers retained; short=OFF, open=normal regulation/UVLO|

There are no replacement-wheel24V sockets, brake-resistor/thermal ports, onboard CAN, camera/microphone USB sockets or onboard Daly interface. Existing motor controllers retain their prior control connection. OAK-D and microphone use Jetson/external USB3.

## Hardware and software

The mechanical battery master requires no software permission. Stop the robot before OFF. Local shunts disable individual regulators; they do not isolate/discharge outputs or stop a shorted input. Motor passthrough is controlled by the master and its fuse, with the existing controllers responsible for motor behavior. Backdriven controllers can energize the board-side bus after the battery switch opens.

PWM requires explicit arming and disables its signal buffer on reset, disconnect, suspend and command timeout. Servo power remains present when its supply is enabled. Verify the actual servos' response and endpoints on the bench. Only the PWM MCU needs programming in this revision.

## Risk, dependencies and descope

| Section | Relative complexity / risk | Practical staged use |
|---|---|---|
| Switch, fuses and motor passthrough |Low circuit complexity; wiring/polarity/contact ratings have high consequence|Preserves existing motor/controller arrangement. Inspect and continuity-test before packs; qualify current/regen/full-battery behavior.|
| Pi, XL330, XL430 and audio/AUX supplies |Moderate; startup, current limits, ripple and heat require measurement|Enable/load one supply at a time; leave unused outputs disconnected.|
| Thor supply |Higher power and consequence|Dummy-load qualify first. For PowerStream fallback, unplug Thor from J3 and power it directly while this section stays disabled; never parallel outputs.|
| USB2 hub, audio and UART |Higher retained layout risk for inherited UART USB; shared fault domain|P1/P2 retain documented reference/return departures. Bench qualification may require an external data adapter, rework or another spin. A shared child-rail/hub fault can remove audio, UART and PWM together.|
| MG90S supply/PWM MCU |Moderate power plus firmware|Test one servo before three; verify arming/watchdog/timeouts. Servo-supply OFF affects all three; signal disarm does not cut power.|

These are separately inspectable source cells and separately enabled supply sections, **not fully fault-isolated boards**. Batteries, grounds and the main electronics fuse remain shared. An input short can affect other sections; an EN shunt cannot isolate it. A cheaper omitted-section assembly needs a reviewed BOM variant rather than arbitrary DNP choices.

Read the [current USB prototype disposition](V09_USB_PROTOTYPE_REVIEW.md) before purchase. The retained audio/Dynamixel geometry is disclosed engineering risk, not a measured USB pass. A data-adapter fallback requires a reviewed harness with the board's data contact disconnected.

Mandatory manual items include the exact TLV3011B detector, fuses, power pigtails/harness and required connectors/programming. Optional OFF headers/test pads are different. No motor clamp parts or three motor bulk capacitors remain in the selected BOM.

## Checks and cost

The current inventory has 366 references, including 304 factory-fitted components plus manual/PCB features. The live catalog snapshot is **$67.98 per board at two-board tiers**, excluding bare PCB, assembly/setup/attrition, manual/external parts, programming, shipping and tax. It is not the assembled-order quote or reserved stock. The mandatory manual USB comparator was separately observed at$2.78 each. Use the current walkthrough for the actual factory quote and final check status.

Before fabrication: final layout/labels, schematic/pad/footprint identity, zero native physical errors/opens, manufacturer drill rules, complete upstream USB and selected FS geometry dispositions, actual assembly matching/placement. Before equipment/motion: rail/load/thermal and USB/PWM tests plus existing motor-controller/BMS/harness qualification. See [scope](V09_SCOPE.md), [commissioning](V09_BRINGUP_CHECKLIST.md), [USB design](USB2_CONTROL_v09.md), [OFF controls](SERVICE_OFF_v09.md) and [Thor cable](THOR_POWER_CABLE.md).
