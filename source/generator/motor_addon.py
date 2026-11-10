"""Companion motor supply circuit inventory; engineering prototype, NOT qualified.

The legacy +24V net is intentionally retained for reuse of the routed Thor cell;
its setpoint here is 22.344 V. No existing PDB circuit inventory is modified.
Run motor_addon_calculations.py for margins, assumptions and release holds.
"""

from blocks import Netlist, FP_R, FP_TDSON, FP_SOT236, FP_HOLE

TITLE = "DDSM350-CT companion supply: 22.34 V / 10 A target / autonomous brake dump"
REVISION = "0.1 motor prototype"
SCHEMATIC_NOTES = "22.344V engineering prototype. Ten ampere continuous design target is unqualified. External 3.3ohm100W brake resistor and normally closed one-shot thermal loop required. Default open thermal loop inhibits buck. Source-fused input; no unrestricted battery or motor use before bench qualification."
BOARD_SIZE_MM = (112, 100)
MOUNTING_HOLES_MM = {"H1": (3, 3), "H2": (109, 3), "H3": (3, 97), "H4": (109, 97)}
FP_WIRE = "Robot_PDB:Power_WirePort_P7.2mm"
FP_HDR2 = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
FP_HDR3 = "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
FP_DUMP_FET = "Package_TO_SOT_SMD:TDSON-8-1"
FP_LDO = "Package_SO:MSOP-8-1EP_3x3mm_P0.65mm_EP1.5x1.8mm"

# Datasheet pin names, not the main board's passive symbol approximation.
# The schematic builder may create project-local symbols from this mapping.
CUSTOM_SYMBOL_PINS = {
    "pdb:TPS7A1650": {"1": "OUT", "2": "DNC", "3": "PG", "4": "GND", "5": "EN", "6": "NC", "7": "DELAY", "8": "IN", "9": "GND_EP"},
    "pdb:REF3333": {"1": "IN", "2": "OUT", "3": "GND"},
    "pdb:TLV3201": {"1": "OUT", "2": "GND", "3": "IN+", "4": "IN-", "5": "VCC"},
    "pdb:UCC27511": {"1": "VDD", "2": "OUTH", "3": "OUTL", "4": "GND", "5": "IN-", "6": "IN+"},
    # KiCad TDSON footprint numbers the common drain land 5; right-hand
    # physical drain leads are continuous with that land, as in its stock symbol.
    "pdb:CSD18534Q5A": {"1": "S", "2": "S", "3": "S", "4": "G", "5": "D"},
}
NO_CONNECT_PINS = {"U3": ["2", "7"]}
DATASHEETS = {
    "U2": "https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf",
    "U1": "https://www.ti.com/lit/ds/symlink/lm74700-q1.pdf",
    "U3": "https://www.ti.com/lit/ds/symlink/tps7a16.pdf",
    "U4": "https://www.ti.com/lit/ds/symlink/ref33.pdf",
    "U5": "https://www.ti.com/lit/ds/symlink/tlv3201.pdf",
    "U6": "https://www.ti.com/lit/ds/symlink/ucc27511.pdf",
    "Q4": "https://www.ti.com/lit/ds/symlink/csd18534q5a.pdf",
    "L1": "https://www.coilcraft.com/en-us/products/power/shielded-inductors/molded-inductor/xal/xal1510/xal1510-103/",
    "C40/C41": "https://industrial.panasonic.com/ww/products/pt/aluminum-cap-lead/models/EEUFR1V102",
    "external_resistor": "https://www.vishay.com/docs/30201/rhnh.pdf",
}

RELEASE_HOLDS = [
    "DDSM350-CT manufacturer publishes nominal 24 V but no verified permitted operating/regen maximum; confirm 22.34 V operation and allowable transients before connecting wheels.",
    "10 A continuous and 12 A transient are design targets, not ratings. Verify LM5146 5mR shunt/649R valley-limit corners, temperature, Kelvin routing and input headroom. Limit is not a precise output ceiling.",
    "Revised compensation passes only the declared averaged-model screen. C28 provides permanent buck-side bulk; verify actual capacitor ESR, diode transitions, motor input impedance and measured loop margin/startup/load steps.",
    "Verify footprint land patterns against TI DGN and Q3A drawings, and all new parts against actual JLC assembly inventory/rotation preview.",
    "Clamp corner model is a design estimate; validate threshold/overshoot, wiring inductance, resistor pulse temperature and all fault cases on a current-limited bench supply.",
    "Fit the selected SCHOTT SM110A0 one-shot thermal cutoff to the resistor using manufacturer installation guidance; confirmDCapplication and thermal coupling/overshoot. An auto-reset bimetal alone is not acceptable.",
    "Input harness must have a local DC-rated fuse sized to the wire/PCB and source fault current. Existing main 30 A fuse does not establish companion-board protection.",
    "No independent clamp-control-power failure backup is fitted; loss of U3/U4/U5/U6 can remove braking absorption. Bound prototype tests and add independent OVP if required by the final hazard review.",
]
EXTERNAL_PARTS = [
    {"item": "brake resistor", "quantity": 1, "mpn": "Vishay NH1003R300FE01 (3.3 ohm 1%, non-inductive)", "notes": "External metal mounting plate; nominal 100 W requires datasheet heatsink. Wire directly J4, never through thermal contact. Pulse/recurrence qualification required."},
    {"item": "thermal cutoff", "quantity": 1, "mpn": "SCHOTT SEFUSE SM110A0 (Tf115C; nominal opening110C)", "notes": "Thermally bond to resistor body/plate; J5 shorts FAULT_BASE to GND while healthy. Opens permanently on overtemperature; replace only after fault inspection. No automatic restart."},
    {"item": "input protection", "quantity": 1, "mpn": "HOLD: local fuse and holder >=58 VDC", "notes": "Install near source; select interrupt rating, wire gauge, inrush/pulse and continuous rating by measured load. Main F1 is not sufficient evidence."},
    {"item": "CAN interface", "quantity": 1, "mpn": "Internal USB CAN bridge on Robot I/O board", "notes": "J6/J7/J8 connect to the internal TCAN334 bridge and two addressed wheels. The motor supply and braking hardware do not depend on host software."},
]


def build_parts():
    n = Netlist()
    n.thor_block(out_conn=False)
    by_ref = {p["ref"]: p for p in n.parts}
    for p in n.parts:
        p["block"] = "A. Motor buck 22.5 V (10 A continuous / 12 A transient targets; unqualified)"
    by_ref["L1"].update(value="10uH XAL1510-103MED", fp="Inductor_SMD:L_Coilcraft_XAL1510-103", lcsc="C3911782", mpn="Coilcraft XAL1510-103MED", status="supplier-listed; verify JLC stock")
    by_ref["R14"].update(value="150k 0.1%", lcsc="C326734", mpn="Yageo RT0603BRD07150KL", status="precision required; verify JLC stock")
    by_ref["R15"].update(value="5.1k 0.1%", lcsc="C328432", mpn="RESI PTFR0603B5K10P9", status="precision required; verify JLC stock")
    by_ref["R15"]["pins"]["2"] = "T_FB_BOTTOM"
    # 470 R provides extra margin below the clamp-off tolerance corner.
    n.P("R20", "Device:R", "470 1%", FP_R, {"1": "T_FB_BOTTOM", "2": "GND"}, "A. Motor buck 22.34 V (10 A continuous / 12 A transient targets; unqualified)", "C23179", "UNI-ROYAL 0603WAF4700T5E", "supplier-listed; verify JLC stock")
    by_ref["R13"].update(value="649", lcsc="C2101770", mpn="Yageo AA0603FR-07649RL", status="verify JLC stock; shunt valley limit")
    by_ref["R13"]["pins"]["2"] = "M_SENSE"
    for pin in ("1", "2", "3"):
        by_ref["Q3"]["pins"][pin] = "M_SENSE"
    n.P("R21", "Device:R", "5m 1% 3W", "Resistor_SMD:R_2512_6332Metric", {"1": "M_SENSE", "2": "GND"}, "A. Motor buck 22.5 V (10 A continuous / 12 A transient targets; unqualified)", "C2994643", "Milliohm HoLLR2512-3W-5mR-1%", "Kelvin ILIM sense at pads; verify JLC stock/land pattern")
    by_ref["R16"].update(value="10k", lcsc="C25804", mpn="UNI-ROYAL 0603WAF1002T5E")
    by_ref["R17"].update(value="3.3k", lcsc="C22978", mpn="UNI-ROYAL 0603WAF3301T5E")
    by_ref["C23"].update(value="220nF 25V", lcsc="C21120", mpn="0603 X7R 220nF 25V", status="longer soft start for mandatory 3.26mF bulk; verify startup")
    by_ref["C24"].update(value="47nF 50V", lcsc="C1622", mpn="0603 X7R 47nF 50V")
    by_ref["C25"].update(value="100pF 50V", lcsc="C14858", mpn="Samsung CL10C101JB8NNNC C0G 5%")
    for ref in ("R16", "R17", "C24", "C25", "C26"):
        by_ref[ref]["status"] = "averaged-model screened; bench loop qualification required"
    n.P("C28", "Device:C_Polarized", "1000uF 35V FR", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", {"1": "+24V", "2": "GND"}, "A. Permanent buck-side bulk", "C128518", "Panasonic EEUFR1V102", "mandatory hand-fit THT after SMT; verify polarity/dimensions", dnp=True)
    by_ref["TP4"]["value"] = "BUCK 22V34"
    by_ref["TP3"]["value"] = "SW MOTOR"
    by_ref["JP1"]["value"] = "MOTOR BUCK OFF (OPEN)"

    B = "B. Reverse blocking from motor bus"
    n.P("Q1", "pdb:NMOS_TDSON8", "BSC040N10NS5", FP_TDSON,
        {"1": "+24V", "2": "+24V", "3": "+24V", "4": "Q1_G", "5": "MOTOR_BUS"}, B,
        "C534334", "Infineon BSC040N10NS5ATMA1", "verify thermal performance")
    n.P("U1", "pdb:LM74700", "LM74700QDBVRQ1", FP_SOT236,
        {"1": "U1_VCAP", "2": "GND", "3": "+24V", "4": "MOTOR_BUS", "5": "Q1_G", "6": "+24V"}, B,
        "C2941042", "TI LM74700QDBVRQ1", "supplier-listed")
    n.C("C1", "100nF 100V", "+24V", "GND", B)
    n.C("C2", "100nF 50V", "U1_VCAP", "+24V", B)

    B = "C. Autonomous voltage-triggered dump; powered from MOTOR_BUS"
    n.P("U3", "pdb:TPS7A1650", "TPS7A1650DGNR", FP_LDO,
        {"1": "+5_DUMP", "2": "NC_U3_DNC", "3": "GND", "4": "GND", "5": "MOTOR_BUS", "6": "GND", "7": "NC_U3_DELAY", "8": "MOTOR_BUS", "9": "GND"}, B,
        "C468238", "TI TPS7A1650DGNR", "verify JLC stock and DGN land pattern")
    n.C("C30", "10uF 50V", "MOTOR_BUS", "GND", B)
    n.C("C31", "10uF 25V", "+5_DUMP", "GND", B)
    n.P("U4", "pdb:REF3333", "REF3333AIDBZR", "Package_TO_SOT_SMD:SOT-23",
        {"1": "+5_DUMP", "2": "DUMP_REF3V3", "3": "GND"}, B, "C130016", "TI REF3333AIDBZR", "verify JLC stock")
    n.C("C32", "1uF 25V", "+5_DUMP", "GND", B)
    n.C("C33", "1uF 25V", "DUMP_REF3V3", "GND", B)
    n.P("U5", "pdb:TLV3201", "TLV3201AIDBVR", "Package_TO_SOT_SMD:SOT-23-5",
        {"1": "DUMP_CMD", "2": "GND", "3": "DUMP_SENSE", "4": "DUMP_REF3V3", "5": "+5_DUMP"}, B, "C105188", "TI TLV3201AIDBVR", "verify JLC stock")
    n.C("C34", "100nF 50V", "+5_DUMP", "GND", B)
    n.P("R30", "Device:R", "60.4k 0.1%", FP_R, {"1": "MOTOR_BUS", "2": "DUMP_SENSE"}, B, "C2989235", "UNI-ROYAL TC0325B6042T5F", "precision required; verify JLC stock")
    n.P("R31", "Device:R", "10k 0.1%", FP_R, {"1": "DUMP_SENSE", "2": "GND"}, B, "C95204", "Yageo RT0603BRD0710KL", "precision required; verify JLC stock")
    n.P("R32", "Device:R", "1M 0.1%", FP_R, {"1": "DUMP_CMD", "2": "DUMP_SENSE"}, B, "C326730", "Yageo RT0603BRD071ML", "verify JLC stock")
    n.P("U6", "pdb:UCC27511", "UCC27511DBVR", FP_SOT236,
        {"1": "+5_DUMP", "2": "DUMP_DRV", "3": "DUMP_DRV", "4": "GND", "5": "GND", "6": "DUMP_CMD"}, B, "C191027", "TI UCC27511DBVR", "verify JLC stock")
    n.C("C35", "100nF 50V", "+5_DUMP", "GND", B)
    n.C("C36", "1uF 25V", "+5_DUMP", "GND", B)
    n.P("R33", "Device:R", "10", FP_R, {"1": "DUMP_DRV", "2": "DUMP_GATE"}, B, "C22859", "UNI-ROYAL 0603WAF100JT5E", "supplier-listed")
    n.R("R34", "100k", "DUMP_GATE", "GND", B)
    n.P("Q4", "pdb:CSD18534Q5A", "CSD18534Q5A", FP_DUMP_FET,
        {"1": "GND", "2": "GND", "3": "GND", "4": "DUMP_GATE", "5": "DUMP_LOW"}, B,
        "C115943", "TI CSD18534Q5A", "verify Q5A land pattern; 4.5 V Rds specified")
    # Resistor and harness inductance must recirculate when Q4 turns OFF.
    # This is not the main braking-energy sink: current decays in the resistor.
    n.P("D2", "Device:D_Schottky", "SS1060", "Diode_SMD:D_SMC",
        {"1": "MOTOR_BUS", "2": "DUMP_LOW"}, B,
        "C2922189", "SS1060 60V 10A SMC", "dump resistor/harness freewheel; verify reverse recovery and overshoot")
    for ref in ("C40", "C41"):
        n.P(ref, "Device:C_Polarized", "1000uF 35V FR", "Capacitor_THT:CP_Radial_D12.5mm_P5.00mm", {"1": "MOTOR_BUS", "2": "GND"}, B, "C128518", "Panasonic EEUFR1V102", "hand-fit THT after SMT; verify polarity/dimensions", dnp=True)

    B = "D. Thermal permissive (one-shot NC external contact required)"
    n.R("R35", "100k", "VIN", "THERMAL_CONTACT", B)
    n.R("R37", "10k", "THERMAL_CONTACT", "FAULT_BASE", B)
    n.C("C42", "100nF 50V", "FAULT_BASE", "GND", B)
    n.P("D4", "Device:D", "1N4148W", "Diode_SMD:D_SOD-123",
        {"1": "FAULT_BASE", "2": "GND"}, B, "C81598", "ST(Semtech) 1N4148W", "base-emitter reverse clamp; harness EMI qualification required")
    n.P("Q5", "Transistor_BJT:MMBT3904", "MMBT3904", "Package_TO_SOT_SMD:SOT-23", {"1": "FAULT_BASE", "2": "GND", "3": "T_EN"}, B, "C20526", "JSCJ MMBT3904(RANGE:100-300)", "supplier-listed")
    n.P("J5", "Connector_Generic:Conn_01x02", "NC ONE-SHOT THERMAL LOOP", FP_HDR2, {"1": "THERMAL_CONTACT", "2": "GND"}, B, "", "external thermal-loop harness; hand-fit", "mandatory external part", dnp=True)

    B = "E. Hand-wired power and CAN pass-through"
    for ref, value, pins in (
        ("J1", "FUSED 8S INPUT", {"1": "GND", "2": "VIN"}),
        ("J2", "MOTOR LEFT", {"1": "GND", "2": "MOTOR_BUS"}),
        ("J3", "MOTOR RIGHT", {"1": "GND", "2": "MOTOR_BUS"}),
        ("J4", "EXTERNAL 3R3 BRAKE RESISTOR", {"1": "DUMP_LOW", "2": "MOTOR_BUS"}),
    ):
        n.P(ref, "Connector_Generic:Conn_01x02", value, FP_WIRE, pins, B, "", "3 mm plated wire ports; strain-relieved external pigtails", "hand-fit", dnp=True)
    for ref, label in (("J6", "USB-CAN INPUT"), ("J7", "CAN LEFT"), ("J8", "CAN RIGHT")):
        n.P(ref, "Connector_Generic:Conn_01x03", label, FP_HDR3, {"1": "GND", "2": "CAN_H", "3": "CAN_L"}, B, "", "hand-fit 2.54 mm signal header; verify external motor connector pinout", "hand-fit", dnp=True)
    n.P("R36", "Device:R", "120", FP_R, {"1": "CAN_H", "2": "CAN_TERM"}, B, "C22787", "UNI-ROYAL 0603WAF1200T5E", "supplier-listed")
    n.JP("JP2", "CAN_TERM", "CAN_L", "CAN 120R TERM (OPEN DEFAULT)", B)
    for ref, net, label in (("TP1", "VIN", "RAW IN"), ("TP2", "GND", "GND"), ("TP6", "MOTOR_BUS", "MOTOR BUS"), ("TP7", "+5_DUMP", "DUMP 5V"), ("TP8", "DUMP_CMD", "DUMP ON"), ("TP9", "DUMP_SENSE", "CLAMP SENSE")):
        n.TP(ref, net, label, B)
    for ref in MOUNTING_HOLES_MM:
        n.P(ref, "Mechanical:MountingHole", "M3 NPTH", FP_HOLE, {}, "F. Mounting", "", "M3 NPTH", "", dnp=True)
    # Local raw-input surge protection: this feed bypasses the main logic TVS.
    for ref in ("Q2", "Q3"):
        by_ref[ref].update(value="BSC040N10NS5", lcsc="C534334", mpn="Infineon BSC040N10NS5ATMA1 100V", status="100V margin; shunt current sense; verify switching/thermal behavior")
    n.P("D1", "Device:D_TVS", "SMCJ36CA", "Diode_SMD:D_SMC", {"1": "VIN", "2": "GND"}, "A. Local raw input surge protection", "C151283", "SMCJ36CA 36V stand-off, bidirectional", "local short ground return required; verify transient envelope")
    return n.parts


PARTS = build_parts()
assert len({p["ref"] for p in PARTS}) == len(PARTS), "duplicate motor-board reference"
assert all(p["fp"] for p in PARTS)

if __name__ == "__main__":
    import json
    print(json.dumps({"title": TITLE, "parts": PARTS, "release_holds": RELEASE_HOLDS, "external_parts": EXTERNAL_PARTS}, indent=2))
