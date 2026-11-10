> **Note for this repository.** This README predates the current board. Only the PWM image applies: the
> published board has one STM32F072 (U7002) and no on-board CAN, so the candleLight/CAN material and
> `can.patch` are historical. The upstream USB stacks are not included here; `build.py --fetch` downloads the
> exact commits listed in `dependencies.json`. Some documents it refers to are not in this repository.

# Robot I/O prototype firmware

Two separate STM32F072CBT6 images match `source/generator/robot_io.py`: U1 provides SocketCAN through candleLight/gs_usb; U2 provides three PWM channels through one USB CDC port. Both use the fitted8 MHz crystal and a48 MHz PLL clock. These images compile; neither has been exercised on physical hardware.

Build with an ARM GNU/newlib toolchain and CMake:

```sh
python3 firmware/robot_io/build.py --fetch
cc -std=c11 -Wall -Wextra -Werror -fsanitize=address,undefined firmware/robot_io/pwm/controller.c firmware/robot_io/pwm/test_controller.c -o /tmp/robot-pwm-test
/tmp/robot-pwm-test
```

Use `TOOLCHAIN_BIN_DIR=/path/to/bin` if required. Exact upstream commits are in `dependencies.json`; `can.patch` is the tracked board-specific modification. Dependencies and build products are ignored rather than vendored. The build creates ELF/BIN files, maps and SHA256 hashes in `build/build_report.json`. It does not flash hardware. Service access is through each MCU's SWD header, or STM32 ROM DFU using its BOOT/reset links after confirming the exact chip bootloader procedure.

CAN uses PB8/PB9 AF4 and PC13 active-high TCAN334 shutdown, with active-low PA0/PA1 status LEDs. The image preserves upstream gs_usb protocol and 150 mA descriptor. An image for another candleLight board is not interchangeable with this target.

PWM uses PA6/PA7/PB0 TIM3 AF1 and PB1 active-high buffer arm. Outputs remain disabled until a valid explicit transaction. The parser accepts ASCII lines terminated by LF, with CR ignored, maximum95 characters, one space between fields and strict unsigned decimal numbers. Other control characters invalidate the complete line. There is no automatic movement on connection, reset or firmware update.

1. Open CDC with DTR asserted. Send `INFO`. It disarms and returns `OK INFO 1 <token> DISARMED`.
2. Send `STAGE <token> 1 1000 1500 2000`. This stages three widths without enabling outputs.
3. Send `ARM <token> 2`. This starts the deliberately staged50 Hz output.
4. Send `SET <token> 3 1100 1500 1900` to update all channels together, or `KEEP <token> 4` to refresh the watchdog without moving. Increase the sequence for every accepted command.
5. Send `DISARM` before closing. It is accepted without a token. It disables output and invalidates the session.

Widths initially must be1000–2000 µs. Sequence numbers are strictly increasing and do not wrap within a session; disarm and use INFO to start another. Only accepted commands refresh the 500 ms deadline. The token prevents accidental buffered commands crossing a connection, not malicious access. INFO always creates a fresh disarmed session. An independent hardware watchdog and the millisecond interrupt also remove output enable if the foreground stops. USB reset/suspend/unplug disables output in the USB event hook; unmount, DTR drop and resume invalidate the session. A new DTR edge/reopen is required after such a fault. The firmware ignores the common1200-baud bootloader trigger.

USB interrupt traffic must not be used as a substitute for valid host commands. On timeout, old staged widths and the token are discarded. Signal disable does not remove servo5 V; servo behavior without pulses must be measured unloaded first. See `docs/ROBOT_IO_FIRMWARE_PLAN.md` for the complete electrical/bring-up contract.

Known qualification holds: USB suspend current is not measured and low-power suspend is not implemented; outputs do disable. The 4,000-period watchdog computes to80–133.4 ms for ST's30–50 kHz LSI range at VDDA3.3 V. Verify actual watchdog timing over LSI tolerance, PWM pulse timing/atomic transitions, crystal startup, USB enumeration/lifecycle, CAN traffic and all reset/brownout behavior before attaching actuators. The PWM image uses TinyUSB's prototype VID with a project PID; obtain an authorized USB identity before distributing a product. The self-powered hub's local supply/protection must cover declared downstream budgets.
