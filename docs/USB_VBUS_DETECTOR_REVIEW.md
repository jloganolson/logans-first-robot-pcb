# v0.8 host-VBUS detector correction

Reviewed2026-11-09. **Use mandatory hand-fitted TI TLV3011BIDBVR**, replacing the original Schmitt inverter. The B suffix matters. This note records the selected correction and its remaining hardware qualification, not a USB compliance certificate.

## Failure mechanism

U11 is ST USBLC6-2SC6. Its pin5 is raw host VBUS, and the manufacturer's rail-to-rail protector topology includes upper data-line steering diodes. With the locally powered hub's pull-up connected through enabled U9902, current can flow from D+ into raw VBUS after unplug/power removal. The former100k bleeder requires only tens of microamps; it cannot guarantee collapse of that phantom supply. The old Schmitt inverter's falling threshold is around1V at this supply, allowing an enabled state to sustain itself. These are circuit inferences from the actual pin connections and primary diagrams, not a measured latch event. [ST DS4260 Rev7 front diagram/§2.1](https://www.st.com/resource/en/datasheet/usblc6-2.pdf), [TI SN74LVC1G14 SCES218AA §5.5](https://www.ti.com/lit/ds/symlink/sn74lvc1g14.pdf)

## Exact selected connections

| U9903 pin | TLV3011B function | Connection |
| --- | --- | --- |
|1|OUT, open drain|USB2_UP_OE_N; existing100k R9904 pull-up to H_V33|
|2|V−|GND|
|3|IN+|REF node|
|4|IN−|VBUS divider sense|
|5|REF|Same node as pin3;1nF C9909 to GND|
|6|V+|H_V33; retain adjacent100nF C9906 bypass|

R9909 is220k from raw VBUS to sense; R9910 is100k from sense to GND. Both use the existing0603±1%/100ppm resistor families. R9903 becomes10k from raw VBUS to GND. C67 becomes Yageo CC0603KRX7R9BB104/C14663,100nF50V±10% X7R. C9909 is Samsung CL10B102KB8NNNC/C1588,1nF50V±10% X7R0603. Keep sense/reference traces short; place the reference capacitor beside pins3/5 and groundpin2. No additional sense capacitor is assumed in the timing below.

When real VBUS is good, IN− exceeds REF, so OUT sinks and enables the USB data switch. Without valid VBUS, OUT releases and R9904 disables it. The B device explicitly permits inputs up to5.5V independently of V+, including V+=0, and specifies a high-impedance open-drain output during power-on reset. Its reference is stable with capacitive loading up to10nF; selected1nF remains comfortably below that limit including tolerance/temperature. The non-B TLV3011 does not provide the same input/POR provisions. [TI SBOS300C §§5,6.2,6.9,9.4.3–9.4.5](https://www.ti.com/lit/ds/symlink/tlv3011.pdf), [Samsung exact capacitor](https://product.samsungsem.com/mlcc/CL10B102KB8NNN.do), [Yageo exact raw bypass](https://www.yageogroup.com/download/specsheet/CC0603KRX7R9BB104)

## Threshold and discharge screen

Nominal trip is1.242×(1+220k/100k)=**3.9744V**. Enumerating resistor±1% and100ppm/°C over a100°C departure, reference initial range1.223–1.260V plus100ppm/°C, offset±9mV and a conservative full±8mV hysteresis allowance gives **3.717–4.243V**. Adding a separate8mV engineering allowance for common-mode/supply/line effects expands the screen to **3.692–4.269V**. This extra allowance is not a new manufacturer guarantee; some underlying table conditions are25°C. Measure actual trip/release over the intended operating range.

The lower screen exceeds CH334's specified H_V33 maximum3.5V, so normal local D+ pull-up power cannot sustain the detector above threshold. The upper screen is below USB2's4.35V low-power-function input allowance. This is a phantom-power rejection design; it does not claim the precise4.35/4.75V valid/invalid window used in some vendor implementations. [WCH CH334DS1 §4.2](https://cdn-learn.adafruit.com/assets/assets/000/131/435/original/CH334DS1.PDF?1721660148=), [TI USB power-distribution discussion SLVA049](https://www.ti.com/lit/an/slva049/slva049.pdf)

For raw VBUS discharge, use10.201k maximum bleeder and126.5nF capacitor screen (100nF×1.10×1.15). Ignoring the parallel divider conservatively, discharge from5.5V to3.69V takes **0.515ms**. At those voltages the local3.5V data rail cannot forward-bias U11's upper diode, so that feedback does not delay the threshold crossing. This leaves substantial margin within a3ms disconnect engineering target, but comparator response, capacitance outside C67 and real waveforms still require measurement. The earlier1µF/100k combination did not have this margin. [Espressif primary self-powered-device guidance](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32s2/api-reference/peripherals/usb_device.html#self-powered-device)

The two resistive VBUS loads draw at most approximately **0.579mA at5.5V** under the same resistor corners. This fits the2.5mA USB suspend-current budget with margin; it is not a measured complete-board suspend result. The [USB-IF April2008 suspend-current ECN](https://compliance.usb.org/index.asp?UpdateFile=Electrical) applies2.5mA to all ordinary USB peripherals regardless of low/high-power classification or remote-wakeup setting. Include protector leakage and actual powered/unpowered host current in the bench record. The ST protector datasheet states no external VBUS bypass-capacitance minimum;100nF therefore does not contradict a stated protector requirement.

## Procurement and fitting

Official JLC detail responses observed **zero stock** for TLV3011BIDBVR/C20345920 and TLV3011BIDCKR/C20345921. Cached search listings showing stock are not current assembly evidence. DigiKey's ordinary product page showed **974 units**, **USD2.78 each** in cut tape, exact part296-TLV3011BIDBVRCT-ND. This is an observation, not a reservation, landed quote or purchase. [DigiKey listing](https://www.digikey.com/en/products/detail/texas-instruments/TLV3011BIDBVR/19236273)

U9903 is excluded from the factory fitted catalog total and must appear in the mandatory hand-fit list. Fit the B comparator before expecting the USB connection to work. An omitted comparator must leave the switch disabled through R9904; DNP is manufacturing metadata, not permission to omit the final functional part. No old5-pin inverter or non-B comparator is an approved substitute.

TPS3700DDCR/C33002 and TLV6700DDCR/C2868382 had live factory stock, but their electrical-table footnotes and POR prose disagree about outputs below the POR voltage, and they lack the same explicit VDD=0 input-leakage provision. They were not selected merely to avoid manual fitting.

Reproducible numeric inputs, timestamped stock responses and manufacturer PDF hashes are in vbus-detector-review.json (not included in this repository). Before connection to the robot, verify host absent/present, unplug, host power removal, local board off with host on, and both power-up orders. Capture raw VBUS, H_V33, divider, OE_N and D+ together. The saved-board auditor separately checks the literal pin/net contract; it cannot prove diode leakage, comparator delay or USB electrical compliance.
