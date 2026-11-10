"""Internal two-port USB CAN + three-channel PWM companion circuit inventory.

Engineering prototype. Two independent STM32F072CBT6 devices preserve stock
gs_usb operation and avoid a custom composite USB stack. No cost estimate is
embedded: obtain actual assembly quotes for this exact inventory.
"""
from blocks import Netlist, FP_R, FP_C0603, FP_LQFP48, FP_XTAL, FP_HOLE

REVISION = "robot-io-prototype-1"
TITLE = "Robot I/O: internal USB CAN + USB PWM, dedicated servo 5 V"
SCHEMATIC_NOTES = ("ROBOT I/O ENGINEERING PROTOTYPE\\n"
    "- U1 USB-CAN and U2 USB-CDC PWM are separate STM32F072CBT6 devices on independent internal USB ports.\\n"
    "- VBUS domains must not be joined. Separate fused/protected8S input powers dedicated4.992V servo buck.\\n"
    "- PWM headers: pin1GND, pin2+5V, pin3signal. Buffer defaults disabled; signal-off is not supply-off.\\n"
    "- CAN header: GND/H/L. Exactly two120R terminators at physical bus ends; JP1 defaults open.\\n"
    "- Firmware builds at firmware/robot_io; no hardware tests performed. Blank MCUs cannot operate actuators.\\n"
    "- Check crystal startup, USB power/suspend, converter compensation/stall current and all fail-safe transitions.\\n"
    "- Read docs/ROBOT_IO_FIRMWARE_PLAN.md before assembly or actuator connection.")
BOARD_SIZE_MM = (112, 100)
MOUNTING_HOLES_MM = {"H1": (3, 3), "H2": (109, 3), "H3": (3, 97), "H4": (109, 97)}
FP_HDR3 = "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
FP_HDR4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
FP_HDR5 = "Connector_PinHeader_2.54mm:PinHeader_1x05_P2.54mm_Vertical"
FP_SOT235 = "Package_TO_SOT_SMD:SOT-23-5"

STM32_PINS = {
    "1":"VBAT", "2":"PC13", "3":"PC14", "4":"PC15", "5":"PF0_OSC_IN", "6":"PF1_OSC_OUT", "7":"NRST", "8":"VSSA", "9":"VDDA",
    "10":"PA0", "11":"PA1", "12":"PA2", "13":"PA3", "14":"PA4", "15":"PA5", "16":"PA6", "17":"PA7", "18":"PB0", "19":"PB1",
    "20":"PB2", "21":"PB10", "22":"PB11", "23":"VSS", "24":"VDD", "25":"PB12", "26":"PB13", "27":"PB14", "28":"PB15", "29":"PA8",
    "30":"PA9", "31":"PA10", "32":"PA11_USB_DM", "33":"PA12_USB_DP", "34":"PA13_SWDIO", "35":"VSS", "36":"VDDIO2", "37":"PA14_SWCLK",
    "38":"PA15", "39":"PB3", "40":"PB4", "41":"PB5", "42":"PB6", "43":"PB7", "44":"BOOT0", "45":"PB8_CAN_RX", "46":"PB9_CAN_TX", "47":"VSS", "48":"VDD",
}
CUSTOM_SYMBOL_PINS = {
    "pdb:STM32F072CBT6": STM32_PINS,
    "pdb:TCAN334": {"1":"TXD","2":"GND","3":"VCC","4":"RXD","5":"SHDN","6":"CANL","7":"CANH","8":"STB"},
    "pdb:SN74AHCT125": {"1":"1OE_N","2":"1A","3":"1Y","4":"2OE_N","5":"2A","6":"2Y","7":"GND","8":"3Y","9":"3A","10":"3OE_N","11":"4Y","12":"4A","13":"4OE_N","14":"VCC"},
}
PIN_MAPPING = [
    {"device":"U1 CAN MCU","pins":"45/PB8 AF4;46/PB9 AF4","function":"CAN_RX;CAN_TX to U4"},
    {"device":"U1 CAN MCU","pins":"2/PC13","function":"TCAN334 SHDN; HIGH disables; external pull-up defaults disabled"},
    {"device":"U1 CAN MCU","pins":"10/PA0;11/PA1","function":"candleLight active-low RX/TX LEDs"},
    {"device":"U2 PWM MCU","pins":"16/PA6 AF1;17/PA7 AF1;18/PB0 AF1","function":"TIM3 CH1/CH2/CH3, 50 Hz, initially1000–2000us permitted"},
    {"device":"U2 PWM MCU","pins":"19/PB1","function":"SERVO_ARM, HIGH enables Q1/OE; hardware pulldown defaults disabled"},
    {"device":"both MCUs","pins":"32/PA11;33/PA12","function":"USB D−;D+, independent hub ports, internal pull-up and impedance matching"},
    {"device":"both MCUs","pins":"34/PA13;37/PA14;7/NRST","function":"SWDIO;SWCLK;reset service header"},
    {"device":"both MCUs","pins":"5/PF0;6/PF1","function":"8MHz HSE crystal, PLL×6=48MHz"},
    {"device":"both MCUs","pins":"1/24/36/48;9;8/23/35/47","function":"3.3V including VDDIO2/VBAT;filtered VDDA;ground"},
]
SOURCE_URLS = {
    "STM32F072": "https://www.st.com/resource/en/datasheet/stm32f072c8.pdf",
    "STM32_USB_layout": "https://www.st.com/resource/en/application_note/dm00296349-usb-hardware-and-pcb-guidelines-using-stm32-mcus-stmicroelectronics.pdf",
    "TCAN334": "https://www.ti.com/lit/ds/symlink/tcan334.pdf",
    "AHCT125": "https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf",
    "TPS54560": "https://www.ti.com/lit/ds/symlink/tps54560.pdf",
    "AP2112": "https://www.diodes.com/datasheet/download/AP2112.pdf",
    "crystal": "https://www.lcsc.com/product-detail/C2682775.html",
    "candleLight": "https://github.com/candle-usb/candleLight_fw",
    "CAN_board_hook": "https://github.com/candle-usb/candleLight_fw/blob/master/src/boards/legacy.c",
    "CAN_GPIO_init": "https://github.com/candle-usb/candleLight_fw/blob/master/src/gpio.c",
    "CAN_enable_disable": "https://github.com/candle-usb/candleLight_fw/blob/master/src/can_common.c",
    "CAN_timer": "https://github.com/candle-usb/candleLight_fw/blob/master/src/timer.c",
    "TinyUSB": "https://github.com/hathach/tinyusb",
}
RELEASE_HOLDS = [
    "Both firmware images compile from firmware/robot_io; neither is hardware-tested. Verify enumeration, CAN traffic, USB suspend current and all PWM fail-safe transitions before using actuators.",
    "I/O input must be a separately fused protected8S logic feed with a verified transient envelope below TPS54560 absolute maximum. Main motor output and USB VBUS are not substitutes for this feed.",
    "TPS54560 5A is an IC capability, not a qualified board rating. Verify voltage drop, stall/restart current of the actual three MG90S clones, thermal rise and compensation under pulse loads.",
    "OE disables PWM signals only; servo5V remains present unless the hardware disconnect is OFF. Missing PWM is not a demonstrated mechanical safe state for the actual servos.",
    "18pF crystal loading assumes≈3pF equivalent stray capacitance and12pF specified CL. Verify oscillator startup margin, amplitude, load and frequency with the final PCB.",
    "USB uses internal short paired interconnects to two separate CH334F downstream ports. Host VBUS sources must never be joined; no external series termination or external D+ pull-up is fitted.",
    "Set exactly two120R CAN terminations at physical bus ends; this board's termination jumper defaults open. TCAN334 bus-fault rating does not tolerate accidental24V motor-power connection.",
    "All part codes identify real listings; verify actual JLC stock, footprint land patterns, rotations and assembly quotation before ordering. No cost estimate is provided.",
]


def build_parts():
    n=Netlist()
    # Existing 5V TPS54560 circuit cell, kept as a separate dedicated rail.
    n.tps_block(0,"PWM","V5_SERVO","A. Dedicated MG90S servo5V (5A target unqualified)","6.8uH","39k","7.5k","12k","2.2k")
    by={p["ref"]:p for p in n.parts}
    by["R101"]["pins"]["2"]="PWM_FB_TOP"
    n.R("R108","300","PWM_FB_TOP","PWM_FB","A. Servo5V trim to4.992V nominal")
    for ref in ("R106","C109","C110"):
        by[ref]["status"]="inherited buck compensation; qualify actual servo pulse loads"
    n.CP("C111","100uF 63V","10x10","VIN","GND","A. Input bulk")
    n.P("D1","Device:D_TVS","SMCJ36CA","Diode_SMD:D_SMC",{"1":"VIN","2":"GND"},"A. Local input surge footprint","C151283","Littelfuse SMCJ36CA","surge envelope/60V buck margin unqualified")
    n.P("J9","Connector_Generic:Conn_01x02","FUSED PROTECTED8S LOGIC IN","Robot_PDB:Power_WirePort_P7.2mm",{"1":"GND","2":"VIN"},"A. I/O power",mpn="hand-soldered strain-relieved input pigtail",status="separate fuse and protected feed required",dnp=True)
    n.P("C112","Device:C_Polarized","470uF 25V","Capacitor_SMD:CP_Elec_10x10",{"1":"V5_SERVO","2":"GND"},"A. Servo pulse bulk","C249933","Lelon VZH471M1ETR-1010","qualify ripple and pulse-load control loop")

    for idx,prefix,mcu,reg,esd,usb,debug,cbase,rbase,yref,bootjp,resetjp in (
        (0,"CAN","U1","U5","U8","J1","J7",1,1,"Y1","JP2","JP4"),
        (1,"PWM","U2","U6","U9","J2","J8",21,21,"Y2","JP3","JP5"),
    ):
        B=f"B{idx+1}. {prefix} USB MCU and independent USB logic supply"
        vbus=f"USB_{prefix}_VBUS";v3=f"V3_{prefix}";avdd=f"V3_{prefix}_A"
        n.P(usb,"Connector_Generic:Conn_01x04",f"INTERNAL USB {prefix}:VBUS/D-/D+/GND",FP_HDR4,{"1":vbus,"2":f"USB_{prefix}_DM","3":f"USB_{prefix}_DP","4":"GND"},B,mpn="short paired internal USB interconnect; hand-fit",status="must be independent hub port",dnp=True)
        n.P(reg,"pdb:AP2112K","AP2112K-3.3TRG1",FP_SOT235,{"1":vbus,"2":"GND","3":vbus,"5":v3},B,"C51118","Diodes AP2112K-3.3TRG1","verify JLC stock; independent VBUS")
        n.C(f"C{cbase}","1uF 25V",vbus,"GND",B)
        n.C(f"C{cbase+1}","4.7uF 16V",v3,"GND",B)
        n.P(esd,"pdb:USBLC6","USBLC6-2SC6","Package_TO_SOT_SMD:SOT-23-6",{"1":f"USB_{prefix}_DP","6":f"USB_{prefix}_DP","3":f"USB_{prefix}_DM","4":f"USB_{prefix}_DM","5":vbus,"2":"GND"},B,"C7519","ST USBLC6-2SC6","flow-through ESD placement required")
        # All48 pins represented. NC_ nets each contain only their unused pin.
        pins={pin:f"NC_{prefix}_{pin}" for pin in STM32_PINS}
        for pin in ("1","24","36","48"):pins[pin]=v3
        for pin in ("8","23","35","47"):pins[pin]="GND"
        pins.update({"5":f"{prefix}_HSE_IN","6":f"{prefix}_HSE_OUT","7":f"{prefix}_NRST","9":avdd,"32":f"USB_{prefix}_DM","33":f"USB_{prefix}_DP","34":f"{prefix}_SWDIO","37":f"{prefix}_SWCLK","44":f"{prefix}_BOOT0"})
        if prefix=="CAN":
            pins.update({"2":"CAN_SHDN","10":"CAN_LED_RX","11":"CAN_LED_TX","45":"CAN_RXD","46":"CAN_TXD"})
        else:
            pins.update({"16":"PWM1_MCU","17":"PWM2_MCU","18":"PWM3_MCU","19":"SERVO_ARM"})
        n.P(mcu,"pdb:STM32F072CBT6","STM32F072CBT6",FP_LQFP48,pins,B,"C81720","ST STM32F072CBT6 128KB flash","blank MCU: firmware required")
        for offset in (2,3,4):n.C(f"C{cbase+offset}","100nF 50V",v3,"GND",B)
        # A dedicated100nF at each of VDD24,VDD48,VDDIO2; local analog RC.
        n.R(f"R{rbase}","10",v3,avdd,B)
        # 10R is not in the shared dictionary; use verified listing explicitly.
        n.parts[-1].update(lcsc="C22859",mpn="UNI-ROYAL 0603WAF100JT5E",status="supplier-listed")
        n.C(f"C{cbase+5}","100nF 50V",avdd,"GND",B)
        n.C(f"C{cbase+6}","1uF 25V",avdd,"GND",B)
        n.C(f"C{cbase+7}","100nF 50V",f"{prefix}_NRST","GND",B)
        n.R(f"R{rbase+1}","10k",v3,f"{prefix}_NRST",B)
        n.R(f"R{rbase+2}","10k",f"{prefix}_BOOT0","GND",B)
        n.P(yref,"pdb:XTAL4","8MHz CL12pF",FP_XTAL,{"1":f"{prefix}_HSE_IN","2":"GND","3":f"{prefix}_HSE_OUT","4":"GND"},B,"C2682775","YXC X32258MOB4SI","CL and oscillator gain-margin/startup qualification required")
        for off,net in ((8,f"{prefix}_HSE_IN"),(9,f"{prefix}_HSE_OUT")):
            n.P(f"C{cbase+off}","Device:C","18pF 50V",FP_C0603,{"1":net,"2":"GND"},B,"C1647","Samsung CL10C180JB8NNNC C0G5%","load tuning may be required")
        n.JP(bootjp,v3,f"{prefix}_BOOT0",f"{prefix} DFU BOOT (OPEN)",B)
        n.JP(resetjp,f"{prefix}_NRST","GND",f"{prefix} RESET (OPEN)",B)
        n.P(debug,"Connector_Generic:Conn_01x05",f"{prefix} SWD:VREF/GND/DIO/CLK/RESET",FP_HDR5,{"1":v3,"2":"GND","3":f"{prefix}_SWDIO","4":f"{prefix}_SWCLK","5":f"{prefix}_NRST"},B,mpn="hand-fit SWD service header; pin1 is target-reference sense",status="do not inject debugger power",dnp=True)

    B="C. Classic CAN physical interface"
    n.P("U4","pdb:TCAN334","TCAN334DR","Package_SO:SOIC-8_3.9x4.9mm_P1.27mm",{"1":"CAN_TXD","2":"GND","3":"V3_CAN","4":"CAN_RXD","5":"CAN_SHDN","6":"CAN_L","7":"CAN_H","8":"GND"},B,"C2871143","TI TCAN334DR 3.3V","1Mbps classic CAN; default shutdown")
    n.C("C41","100nF 50V","V3_CAN","GND",B)
    n.C("C42","1uF 25V","V3_CAN","GND",B)
    n.R("R41","10k","V3_CAN","CAN_SHDN",B)
    n.R("R42","10k","V3_CAN","CAN_TXD",B)
    n.P("J3","Connector_Generic:Conn_01x03","CAN:GND/H/L",FP_HDR3,{"1":"GND","2":"CAN_H","3":"CAN_L"},B,mpn="hand-fit keyed/labelled internal CAN harness",status="do not connect motor power",dnp=True)
    n.P("R43","Device:R","120",FP_R,{"1":"CAN_H","2":"CAN_TERM"},B,"C22787","UNI-ROYAL 0603WAF1200T5E","termination optional")
    n.JP("JP1","CAN_TERM","CAN_L","CAN120R (OPEN DEFAULT)",B)
    for dref,rref,cathode in (("D3","R44","CAN_LED_RX"),("D4","R45","CAN_LED_TX")):
        n.P(dref,"Device:LED","Green","LED_SMD:LED_0603_1608Metric",{"1":cathode,"2":dref+"_A"},B,"C12624","KT-0603G","active-low stock candleLight LEDs")
        n.R(rref,"1k","V3_CAN",dref+"_A",B)

    B="D. Three5V PWM outputs, default disabled"
    n.P("U7","pdb:SN74AHCT125","SN74AHCT125PWR","Package_SO:TSSOP-14_4.4x5mm_P0.65mm",{"1":"SERVO_OE_N","2":"PWM1_MCU","3":"PWM1_BUF","4":"SERVO_OE_N","5":"PWM2_MCU","6":"PWM2_BUF","7":"GND","8":"PWM3_BUF","9":"PWM3_MCU","10":"SERVO_OE_N","11":"NC_PWM_BUFFER4","12":"GND","13":"V5_SERVO","14":"V5_SERVO"},B,"C36365","TI SN74AHCT125PWR","TTL input thresholds accept3.3V; VCC4.5–5.5V")
    n.C("C43","100nF 50V","V5_SERVO","GND",B)
    n.R("R46","2.2k","V5_SERVO","SERVO_OE_N",B)
    n.P("Q1","Transistor_BJT:MMBT3904","MMBT3904","Package_TO_SOT_SMD:SOT-23",{"1":"SERVO_OE_BASE","2":"GND","3":"SERVO_OE_N"},B,"C20526","JSCJ MMBT3904(RANGE:100-300)","default off enables/OE only when ARM high")
    n.R("R47","10k","SERVO_ARM","SERVO_OE_BASE",B)
    n.R("R48","100k","SERVO_OE_BASE","GND",B)
    n.R("R49","100k","SERVO_ARM","GND",B)
    for i,jref in enumerate(("J4","J5","J6"),1):
        n.R(f"R{50+i}","10k",f"PWM{i}_MCU","GND",B)
        n.P(f"R{53+i}","Device:R","100",FP_R,{"1":f"PWM{i}_BUF","2":f"PWM{i}_OUT"},B,"C22775","UNI-ROYAL 0603WAF1000T5E","output series damping")
        n.R(f"R{56+i}","100k",f"PWM{i}_OUT","GND",B)
        n.P(jref,"Connector_Generic:Conn_01x03",f"MG90S{i}:GND/+5V/PWM",FP_HDR3,{"1":"GND","2":"V5_SERVO","3":f"PWM{i}_OUT"},B,mpn="hand-fit three-pin servo header; center pin+5V",status="verify actual cable polarity before plugging in",dnp=True)
    for ref,net,label in (("TP1","V3_CAN","CAN3V3"),("TP2","V3_PWM","PWM3V3"),("TP3","SERVO_OE_N","PWM OE_N"),("TP4","GND","GND")):
        n.TP(ref,net,label,"E. Service")
    for ref in MOUNTING_HOLES_MM:n.P(ref,"Mechanical:MountingHole","M3 NPTH",FP_HOLE,{},"E. Mounting",mpn="M3 NPTH",status="",dnp=True)
    return n.parts


PARTS=build_parts()
NO_CONNECT_PINS={p["ref"]:[pin for pin,net in p["pins"].items() if net.startswith("NC_")] for p in PARTS}


def validate_inventory():
    """Critical wiring checks supplement passive-symbol schematic ERC."""
    by={p["ref"]:p for p in PARTS}
    checks={"unique_references":len(by)==len(PARTS),"all_fitted_supplier_codes":all(p["lcsc"] for p in PARTS if not p["dnp"])}
    checks["USB_VBUS_not_joined"]=by["J1"]["pins"]["1"]!=by["J2"]["pins"]["1"]
    checks["independent_USB_regulators"]=by["U5"]["pins"]["1"]=="USB_CAN_VBUS" and by["U6"]["pins"]["1"]=="USB_PWM_VBUS"
    checks["CAN_separate_from_USB_pins"]=by["U1"]["pins"]["45"]=="CAN_RXD" and by["U1"]["pins"]["46"]=="CAN_TXD" and by["U1"]["pins"]["32"]=="USB_CAN_DM" and by["U1"]["pins"]["33"]=="USB_CAN_DP"
    checks["VDDIO2_powered"]=by["U1"]["pins"]["36"]=="V3_CAN" and by["U2"]["pins"]["36"]=="V3_PWM"
    checks["CAN_default_shutdown_pullup"]=by["R41"]["pins"]=={"1":"V3_CAN","2":"CAN_SHDN"}
    checks["servo_OE_default_disabled"]=by["R46"]["pins"]=={"1":"V5_SERVO","2":"SERVO_OE_N"} and by["Q1"]["pins"]=={"1":"SERVO_OE_BASE","2":"GND","3":"SERVO_OE_N"}
    checks["servo_headers_center_positive"]=all(by[r]["pins"]["1"]=="GND" and by[r]["pins"]["2"]=="V5_SERVO" for r in ("J4","J5","J6"))
    checks["both_MCUs_all48pins"]=all(set(by[r]["pins"])==set(STM32_PINS) for r in ("U1","U2"))
    return checks


assert all(validate_inventory().values()),validate_inventory()
if __name__=="__main__":
    import json
    print(json.dumps({"title":TITLE,"parts":PARTS,"critical_checks":validate_inventory(),"pin_mapping":PIN_MAPPING,"release_holds":RELEASE_HOLDS,"sources":SOURCE_URLS},indent=2))
