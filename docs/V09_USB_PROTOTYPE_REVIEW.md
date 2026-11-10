# v0.9 USB prototype risk and acceptance

This is a **limited prototype disposition**, not a measured USB pass. The new
upstream route and PWM route have independent saved-copper checks. Two inherited
Full-Speed audio/Dynamixel routes retain documented reference-plane and return
path departures. They may require an external adapter, rework or another board
revision. Do not buy this prototype assuming every USB function is qualified.

## What was checked

The independent analyzer reads the actual filled PCB, finds physical signal
paths, measures lengths and off-path copper, examines the adjacent copper
reference, and checks ground transitions and engineering spacing. Native KiCad
clearance/connectivity, literal schematic/PCB/inventory identity and manufacturer
drill rules are separate checks. None substitutes for electrical measurements.

Both USB-C orientations are evaluated through the passive switch to the hub as
one complete High-Speed channel. New intercell USB transitions have real nearby
ground stitches. The PWM path is Full-Speed; its approximately180mm length is a
documented departure from the conservative150mm High-Speed comparison, with
approximately0.56mm mismatch. Final exact values and PCB/source hashes are in the
current independent report linked from the walkthrough.

## Retained source copper

All34 P1/P2 signal-track segments and their signal vias were compared with the
frozen v0.6 source after its placement translation. The active reference gaps
also exist in that source's filled copper. This proves their origin; it does
**not** prove that the original layout worked on hardware.

| Channel | Actual concern | Consequence |
|---|---|---|
| Audio P1 | Short reference interruptions at an LED via and signal-via fields | Enumeration, noise or traffic errors remain possible |
| Dynamixel P2 | Portions face VIN instead of ground, cross UART routing on the adjacent layer, and have distant ground-return transitions | Higher retained USB risk; USB-to-Dynamixel operation needs deliberate qualification |
| Dynamixel P2 numeric comparison | Approximately1.72mm mismatch versus the conservative1.25mm HS comparison | Retained Full-Speed prototype exception; not a universal FS-limit claim |

The Dynamixel negative leg has about6.41mm and1.84mm of adjacent VIN reference;
other reported gaps and ground distances remain visible in the raw report.
A bounded attempt to move this route onto ground-referenced outer copper could
not clear the existing component field without wider redesign. The present
prototype retains it explicitly rather than hiding the finding.

## Manufacturer guidance and applicability

[WCH's CH342 datasheet](https://datasheet.lcsc.com/datasheet/pdf/7f27ff9550bdd2b424d8351b0108d136.pdf?productCode=C2841530)
identifies Full-Speed operation and recommends close, parallel USB routing with
ground nearby. It does not establish these reference interruptions as acceptable.
[C-Media's CM108B v1.41 datasheet](https://www.cmedia.com.tw/storage/upload/sync_file/E02-0045%20CM108B_Datasheet_v1.41.pdf)
identifies Full-Speed operation. The retrieved document gives no numeric PCB
pair-length/mismatch allowance.
[Microchip AN26.2](https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ApplicationNotes/ApplicationNotes/AN26.2-Application-Note-DS00001876C.pdf)
provides the conservative150mm/1.25mm **High-Speed** comparison used by the screen.
Its numeric values are not represented as universal12Mbps Full-Speed limits.
[ST's STM32F072 datasheet §3.21](https://www.st.com/resource/en/datasheet/stm32f072cb.pdf)
also identifies the PWM MCU's USB interface as12Mbit/s Full-Speed; this does not
qualify the long PCB route by itself.
The longer PWM route's acceptance is engineering judgment for a prototype and
still requires actual operation and signal checks.

Two separate exact-board review records preserve this distinction: the numeric
FS record can address only named length/mismatch comparisons; the legacy-source
record can address only the reported unchanged P1/P2 reference/return/spacing
findings. Neither can clear new HS/PWM reference faults, stubs, detector faults,
native shorts/opens or changed source copper. Stale records hold the export.
The report uses a distinct reviewed-legacy-deviations status.

## Bench and fallback

Test both USB-C orientations, both power-up orders, board-off/host-on,
host-off/board-on, unplug/replug, suspend/resume and fault recovery. Run audio,
both UART channels and PWM together with sustained traffic and error recording.
One successful enumeration is insufficient. Inspect suspect signals and power
with suitable instrumentation if errors occur.

If the internal Dynamixel USB path fails, use a suitable external USB-to-Dynamixel
adapter for data. A board-powered fallback harness must **leave the board's data
contact disconnected** and correctly join the adapter/data ground; never parallel
two data drivers. Do not parallel an adapter's power output with the board rail;
use only its compatible data/ground connection in this arrangement. Verify the
exact actuator pinout and shared power limits first.
External USB audio can similarly replace the codec if needed. These workarounds
cost another host connection and harness work; they are not guaranteed plug-in
repairs.

The other supply outputs remain usable after their own bench checks even if
internal USB is unsuccessful. A shared hub/child-power fault can affect audio,
UART and PWM together. An OFF header disables a regulator; it does not isolate
an input short or backfeed. A failed section may need physical feed disconnection.

## Ordering judgment

I would order only a small, two assembled board **engineering prototype**, with
the factory matching/placement review complete and budget for the manual fitting,
PWM programming and staged bench work. I would not treat it as a ready-to-run
robot controller or buy a production batch. If dependable integrated USB on the
first spin is a purchase requirement, resolve the inherited layout before buying.
