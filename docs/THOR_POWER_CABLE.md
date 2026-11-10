# Thor power cable and board connector

Current v0.9 retains this same J3/header/cable arrangement and corrected
Coilcraft XAL1510-103MED inductor. The nominal output is24.33V for the selected
27–33.6V battery range. Dummy-load qualification is required;8A is a connector/
design ceiling, not a validated board rating. Earlier revision references below
identify the original research and drawing evidence.

Research checked 2026-11-09. Proposed standard cable: **Molex 2147551042**, 300 mm, 18 AWG, four circuits, Micro-Fit 3.0 receptacle contacts at both ends. Proposed board header: **Molex 430450412**, vertical through-hole, tin contacts. The v0.7 source now replaces the Thor output's XT30 with this header. The official cable drawing verifies the required polarity groups; physical fit and a meter check of the delivered assembly remain part of commissioning.

## Thor connector and polarity

NVIDIA's Thor carrier specification v1.1 §3.4 identifies **J83: Lotes APOWA210-P001A06CC**, 2×2 right-angle, 3 mm pitch. Pins 1/2 are main DC input; 3/4 are ground. The public hardware guide specifies 9–28 V input, up to 8 A. Its official illustration labels an alternate connector **J74, AC2211-0011-035-H0** while showing the same polarity. Do not use that old reference label as proof of the actual installed supplier part. [NVIDIA hardware guide](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/hardware_layout.html), [official pin illustration](https://docs.nvidia.com/jetson/agx-thor-devkit/user-guide/latest/_images/microfit-pin-layout.png)

Looking **into the Thor board connector**, latch feature above:

| Upper left | Upper right |
|---|---|
| 4:GND | 3:GND |
| 2:+DC | 1:+DC |

NVIDIA calls the board connector female; Molex describes the cable as female-female and the 43045 header as male. These labels mix housing/receptacle terminology and contact gender across vendors. Verify keyed cavity shape, latch and contacts against the actual Thor, rather than deciding compatibility from the word female. The electrical pin assignment is independently established by NVIDIA's illustration.

## Cable candidates and availability

| Exact cable | Construction | Supplier listing observed |
|---|---|---|
| **2147551042** | 300 mm, 18 AWG UL1061, four wires, tin contacts | DigiKey 900-2147551042-ND: $4.63 each, 3,804 listed; Mouser 538-214755-1042: $4.51 each, 1,142 listed |
|2147552042 | Same length/gauge/circuit count; gold mating contacts | Mouser 538-214755-2042: $4.47 each, 1,379 listed |

These are observed catalog listings, not reserved inventory or checkout quotations; shipping/tax/tariff may change totals. Prefer 1042 with the tin-plated 0412 board header. 2042 is a separate plating choice and its wiring must not be assumed from 1042. [Molex 1042](https://www.molex.com/en-us/products/part-detail/2147551042), [Molex 2042](https://www.molex.com/en-us/products/part-detail/2147552042), [DigiKey 1042](https://www.digikey.com/en/products/detail/molex/2147551042/12180476), [Mouser 1042](https://www.mouser.com/en/ProductDetail/Molex/214755-1042?qs=vmHwEFxEFR9F03wfn9HHPA%3D%3D), [Mouser 2042](https://www.mouser.com/en/ProductDetail/Molex/214755-2042?qs=vmHwEFxEFR%2F0xQ1%252B7zNtUQ%3D%3D)

## Verified cable wiring

The official Molex product-page **Download Document** control successfully provided the drawing on 2026-11-09. It is **2147551040, revision A**, released 2020-01-18, covering 1041/1042/1043. The downloaded PDF was visually inspected, and a copy is saved at `outputs/v07-order-preparation/datasheets/molex-2147551042-drawing.pdf`. [Manufacturer drawing](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/214/214755/2147551042_sd.pdf)

| Cable end A cavity | Cable end B cavity | Assigned supply |
|---|---|---|
| 1 | 2 | Thor +24V |
| 2 | 1 | Thor +24V |
| 3 | 4 | Ground |
| 4 | 3 | Ground |

This is **not** a 1-to-1 cable: it swaps the two contacts within each row, while preserving the positive pair {1,2} and ground pair {3,4}. That is compatible with NVIDIA's published Thor assignment and v0.7 J3: **pins 1/2 +24V, pins 3/4 GND**. Both cable ends use **430250400** receptacle housings and **430300038** tin 18AWG contacts; the 43045 header drawing explicitly specifies the 43025 mating series. Either end can face Thor without reversing supply polarity.

The intended installation is one factory-crimped 300mm cable directly from J3 to Thor, with no bare-wire adapter. Confirm that the delivered cable latches into the actual Lotes/Wieson Thor connector without force. Before connecting Thor, meter all four cable conductors and verify output polarity at its Thor end. These are physical commissioning checks of the purchased parts, not an unresolved drawing assignment. A generic PC/EPS cable is not a substitute.

## Header and footprint

**430450412 = JLC C277721**, live public detail API at 2026-11-09T19:58:47Z: 55,346 stock; $0.4744 each at 1–9. Evidence: `/tmp/jlc-final-C277721.json`. The API confirms the exact manufacturer part number. Header 430450415 is a different **SMT** part with metal retention clips; do not use it with the 0412 footprint.

The manufacturer-authored drawing **SD-43045-005 G1** was downloaded through a normal distributor attachment and visually inspected. It lists 0412 explicitly and specifies mating receptacle series 43025. The 0412 has straight cylindrical **polarizing pegs**, not a snap-in board-lock clip. One or two pegs may be supplied. [Manufacturer drawing, distributor-hosted copy](https://store.comet.bg/download-file.php?id=29289), [Molex 0412](https://www.molex.com/en-us/products/part-detail/430450412)

Use KiCad `Molex_Micro-Fit_3.0_43045-0412_2x02_P3.00mm_Vertical` as the starting geometry:

- Four electrical PTH holes: Ø1.02 mm,3 × 3 mm grid. Stock pin coordinates: 1=(0,0),2=(3,0),3=(0,3),4=(3,3).
- Two NPTH locating holes: Ø1.02 mm at (−3,3.94) and (6,3.94), relative to pin 1. Include both even if the supplied header has one peg.
- Stock 1.50 mm electrical copper pads give only 0.24 mm nominal annulus. The custom v0.7 footprint enlarges them to 1.54 mm for 0.26 mm nominal annulus, preserving holes and centers. Final combined-board checks still apply.
- Solder-tail length from the seating plane is3.18mm. Current v0.9 nominal1.6mm board leaves1.58mm before solder; the factory-listed1.648mm nominal stack leaves1.532mm. Provide underside clearance and local strain relief/support against cable insertion force. The former0.8mm-board assessment below is historical.

The drawing recommends 1.57 mm PCB, but the mating datum is above the seating plane and the polarizing posts have no thickness-specific snap shoulder. Thus 0.8 mm does not inherently move the mating interface; actual seating, kinked-pin insertion, soldering and mechanical retention still need a physical fit check. This is an engineering assessment, not a manufacturer qualification for 0.8 mm.

## Eight-amp power path

Use **two positive and two return contacts**, with all four 18 AWG conductors connected. At 8 A total, ideal sharing is 4 A per contact. Do not rate the installation by simply doubling a headline current figure.

Molex PS-43045 §4.3 specifies all-circuits-powered reference data: 18 AWG wire-to-board 6-circuit 6.5 A/contact, and even 24-circuit 5 A/contact, based on 30°C maximum rise. These support the 4 A/contact target as an initial selection; the final cable/header/PCB installation must be checked for current sharing, voltage drop and temperature at load. [Molex product specification](https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/productspecificationpdf/430/43045/PS-43045-001.pdf)

The user confirmed approximately **27–33 V intended operation** and accepts step-down conversion; retain the onboard Thor buck at about **24.33V**. Input parts still accommodate **33.6V full charge**. At the 27V minimum there is approximately 2.67V input/output headroom. The fitted49.9kΩ timing resistor selects nominal200kHz; ideal required duty is24.3294/27≈90.1%, leaving about495ns off-time versus the controller’s specified200ns maximum minimum-off-time. This is a nominal topology/headroom check, excluding wiring loss and loaded component drops; low-input regulation and load steps must still be measured before powering Thor. [TI LM5146-Q1 datasheet, §7.5 and Table8-1](https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf) The user's current PowerStream PST-DC2424-8 is a separate 8–40 V input, 24 V/8 A, 200 W buck-boost product. Its successful operation does not validate the project's own Thor buck converter at low battery voltage. [PowerStream product page](https://www.powerstream.com/dc-2424-buck-boost.htm)
