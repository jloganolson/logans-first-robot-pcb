"""Self-powered USB3 companion frontend circuit inventory, engineering prototype.

This module does not mutate the main PDB or create fabrication files.  +5_USB_RAW
is a separately regulated 5.1 V / >=6 A input target, NOT Jetson upstream VBUS.
Port 1 is the permanent CH334F child; port 2 OAK-D; port 3 USB-A microphone;
port 4 is a protected internal USB2 expansion for an isolated BMS interface.
The child's four USB2 devices are defined in the IO module.
All new footprints and supplier stock require the release checks below.
"""
from blocks import Netlist, FP_R, FP_C0603, FP_C0805, FP_SOT236, FP_XTAL

TITLE = "USB5744 self-powered USB3 frontend, camera 3A + microphone 900mA"
REVISION = "0.7 development; not fabrication released"
POWER_INPUT = {"net": "+5_USB_RAW", "target_v": 5.1, "minimum_design_a": 6.0,
               "recommended_design_a": 8.0, "maximum_allowed_v": 5.5,
               "notes": "Dedicated regulated supply; input fused/harness qualified by parent design. Never connect upstream USB VBUS."}
CHILD_INTERFACE = {"D+": "HUB_CHILD_DP", "D-": "HUB_CHILD_DM", "power": "+5_USB_RAW", "GND": "GND"}
CHILD_REQUIRED_CHANGES = [
    "CH334F pin18 PSELF must be open/high (self-powered), replacing the existing GND connection.",
    "CH334F V5, CM108B and UART/MCU power come from local regulated power; no connection to upstream connector VBUS.",
    "CH334F upstream pin14 DMU -> HUB_CHILD_DM and pin15 DPU -> HUB_CHILD_DP; preserve polarity.",
    "All four child ports are internal: audio, dual UART, CAN MCU and PWM MCU. Check descriptors/enumeration together.",
]
FP = {
    "hub": "Robot_PDB:USB5744_56VQFN_7x7_P0.4",  # exact Microchip land pattern required
    "up_mux": "Robot_PDB:TI_RNH0030A_WQFN_2.5x4.5_P0.4",
    "cam_mux": "Robot_PDB:TI_RKS0020A_VQFN_2.5x4.5_P0.5",
    "camera_power": "Robot_PDB:TI_RVC0020A_WQFN_3x4_P0.5",
    "ss_esd": "Robot_PDB:TI_DQA0010A_USON_2.5x1_P0.5",
    "usb2_esd": "Package_TO_SOT_SMD:SOT-553",
    "usbc": "Robot_PDB:USB_C_Molex_1054500101",
    "usba": "Connector_USB:USB3_A_Molex_48393-001",
    "buck": "Package_TO_SOT_SMD:SOT-23-5",
    "inductor": "Robot_PDB:L_Bourns_SRP4020TA",
}
DATASHEETS = {
    "USB5744": "https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/USB5744-Data-Sheet-DS00001855.pdf",
    "USB5744_reference": "https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/BoardDesignFiles/EVB-USB5744_A1-sch.pdf",
    "USB5744_checklist_2024": "https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DesignChecklist/USB5744-Hardware-Design-Checklist-DS000029701.pdf",
    "HD3SS3220": "https://www.ti.com/lit/ds/symlink/hd3ss3220.pdf",
    "HD3SS3212": "https://www.ti.com/lit/ds/symlink/hd3ss3212.pdf",
    "TPS25810": "https://www.ti.com/lit/ds/symlink/tps25810.pdf",
    "TPS2553": "https://www.ti.com/lit/ds/symlink/tps2553.pdf",
    "TLV62569": "https://www.ti.com/lit/ds/symlink/tlv62569.pdf",
    "TPS3808": "https://www.ti.com/lit/ds/symlink/tps3808.pdf",
    "SN74LVC1G97": "https://www.ti.com/lit/ds/symlink/sn74lvc1g97.pdf",
    "TPD4E02B04": "https://www.ti.com/lit/ds/symlink/tpd4e02b04.pdf",
    "TPD2EUSB30A": "https://www.ti.com/lit/ds/symlink/tpd2eusb30a.pdf",
    "TPD2E2U06": "https://www.ti.com/lit/ds/symlink/tpd2e2u06.pdf",
    "USB_C": "https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/105/105450/1054500101_sd.pdf",
    "USB_A": "https://www.molex.com/content/dam/molex/molex-dot-com/products/automated/en-us/salesdrawingpdf/483/48393/483930003_sd.pdf",
    "inductor": "https://www.bourns.com/docs/product-datasheets/srp4020ta.pdf",
    "CH334F": "https://www.wch.cn/downloads/CH334DS1_PDF.html",
}
CUSTOM_SYMBOL_PINS = {
    "pdb:USB_C_24": {"A1":"GND","A2":"SSTX1+","A3":"SSTX1-","A4":"VBUS","A5":"CC1","A6":"D+","A7":"D-","A8":"SBU1","A9":"VBUS","A10":"SSRX2-","A11":"SSRX2+","A12":"GND","B1":"GND","B2":"SSTX2+","B3":"SSTX2-","B4":"VBUS","B5":"CC2","B6":"D+","B7":"D-","B8":"SBU2","B9":"VBUS","B10":"SSRX1-","B11":"SSRX1+","B12":"GND","S1":"SHIELD"},
    "pdb:USB_A_3": {"1":"VBUS","2":"D-","3":"D+","4":"GND","5":"SSRX-","6":"SSRX+","7":"GND_DRAIN","8":"SSTX-","9":"SSTX+","10":"SHIELD"},
    "pdb:USB5744": {},
    "pdb:HD3SS3220": {"1":"CC2","2":"CC1","3":"CURRENT_MODE","4":"PORT","5":"VBUS_DET","6":"TXp","7":"TXn","8":"VCC33","9":"RXp","10":"RXn","11":"DIR","12":"ENn_MUX","13":"GND","14":"RX1n","15":"RX1p","16":"TX1n","17":"TX1p","18":"RX2n","19":"RX2p","20":"TX2n","21":"TX2p","22":"ADDR","23":"INT_N/OUT3","24":"VCONN_FAULT_N","25":"SDA/OUT1","26":"SCL/OUT2","27":"ID","28":"GND","29":"ENn_CC","30":"VDD5","31":"GND_EP"},
    "pdb:HD3SS3212": {"1":"RSVD1","2":"OEn","3":"A0p","4":"A0n","5":"GND","6":"VCC","7":"A1p","8":"A1n","9":"SEL","10":"RSVD2","11":"GND","12":"C1n","13":"C1p","14":"C0n","15":"C0p","16":"B1n","17":"B1p","18":"B0n","19":"B0p","20":"GND","21":"GND_EP"},
    "pdb:TPS25810": {"1":"FAULT#","2":"IN1","3":"IN1","4":"IN2","5":"AUX","6":"EN","7":"CHG","8":"CHG_HI","9":"REF_RTN","10":"REF","11":"CC1","12":"GND","13":"CC2","14":"OUT","15":"OUT","16":"DEBUG#","17":"AUDIO#","18":"POL#","19":"UFP#","20":"LD_DET#","21":"GND_EP"},
    "pdb:TPS2553": {"1":"IN","2":"GND","3":"EN","4":"FAULT#","5":"ILIM","6":"OUT"},
    "pdb:TLV62569_DBV": {"1":"EN","2":"GND","3":"SW","4":"VIN","5":"FB"},
    "pdb:TPS3808_DBV": {"1":"RESET#","2":"GND","3":"MR#","4":"CT","5":"SENSE","6":"VDD"},
    "pdb:SN74LVC1G97": {"1":"In1","2":"GND","3":"In0","4":"Y","5":"VCC","6":"In2"},
    "pdb:TPD2EUSB30A_DRT": {"1":"D+","2":"D-","3":"GND"},
    "pdb:TPD4E02B04": {"1":"IO1","2":"IO2","3":"GND","4":"IO3","5":"IO4","6":"NC_IO4_ROUTE","7":"NC_IO3_ROUTE","8":"GND","9":"NC_IO2_ROUTE","10":"NC_IO1_ROUTE"},
    "pdb:TPD2E2U06_DRL": {"1":"NC","2":"NC","3":"IO1","4":"GND","5":"IO2"},
}
_hub_names = ["USB2DN_DP1/PRT_DIS_P1","USB2DN_DM1/PRT_DIS_M1","USB3DN_TXDP1","USB3DN_TXDM1","VDD12","USB3DN_RXDP1","USB3DN_RXDM1","USB2DN_DP2/PRT_DIS_P2","USB2DN_DM2/PRT_DIS_M2","USB3DN_TXDP2","USB3DN_TXDM2","VDD12","USB3DN_RXDP2","USB3DN_RXDM2","VDD12","VDD33","USB2DN_DP3/PRT_DIS_P3","USB2DN_DM3/PRT_DIS_M3","USB3DN_TXDP3","USB3DN_TXDM3","VDD12","USB3DN_RXDP3","USB3DN_RXDM3","USB2DN_DP4/PRT_DIS_P4","USB2DN_DM4/PRT_DIS_M4","USB3DN_TXDP4","USB3DN_TXDM4","VDD12","USB3DN_RXDP4","USB3DN_RXDM4","VDD33","PRT_CTL4/GANG_PWR","VDD12","PRT_CTL3","PRT_CTL2","PRT_CTL1","VBUS_DET","SPI_CLK/SMCLK","SPI_DO/SMDAT","SPI_DI/CFG_BC_EN","SPI_CE_N/CFG_NON_REM","RESET_N","VDD12","VDD33","USB2UP_DP","USB2UP_DM","USB3UP_TXDP","USB3UP_TXDM","VDD12","USB3UP_RXDP","USB3UP_RXDM","ATEST","XTALO","XTALI/CLK_IN","VDD33","RBIAS","VSS_EP"]
CUSTOM_SYMBOL_PINS["pdb:USB5744"] = {str(i): name for i, name in enumerate(_hub_names, 1)}
NO_CONNECT_PINS = {}
USB2_PAIRS = [("UP_DP", "UP_DM"), ("CAM_DP", "CAM_DM"), ("MIC_DP", "MIC_DM"), ("HUB_CHILD_DP", "HUB_CHILD_DM"), ("BMS_USB_DP", "BMS_USB_DM")]
SUPERSPEED_PAIRS = []
PORT_EN_FILTER = {}

RELEASE_HOLDS = [
    "Engineering inventory and layout are unreleased: finish routing, native checks, manufacturer matching and physical qualification before ordering.",
    "Validate all custom footprints against manufacturer drawings and actual JLC placement/rotation. USBA connector is a hand-fit Molex fallback, not assumed stocked JLC assembly.",
    "Dedicated +5_USB_RAW supply and wiring must deliver >=6A at port voltage; target8A. Do not use upstream VBUS or assume existing5A camera rail suffices.",
    "5Gbps routing requires approved4-layer2ozouter/1ozinner JLC040821-7628 stackup with continuous L2/L3 grounds;90ohm pairs(.204mm width/.160mm gap;.203mm outer-to-ground dielectric), no plane splits, coupled escapes and measured skew/loss audit. Generic router/DRC is insufficient.",
    "Validate oscillator startup/frequency/load capacitance, rail startup/fall/reset order, USB suspend behavior and both Type-C plug orientations.",
    "Validate USB5744 vendor-tool configuration disabling only the unused SuperSpeed halves of ports1/4 while preserving their USB2 paths. Existing USB supports internalOTP access; validate the image before irreversible programming, read back and cold-boot-check descriptors. Normal port-power commands do not establish this configuration.",
    "TPD2EUSB30A DRT lands require100um stencil (TI maximum101.6um), .05mm mask clearance and factory engineering review of the short under-body routing/central non-pad ground via. Paid .25/.15 through-via escapes need exact final factory approval.",
    "USB3 upstream TX/RX lane assignment and camera POL mapping must be reviewed against TI figures and cable convention before fabrication.",
    "Verify OAK-D full requested resolution/frame rate and microphone streaming simultaneously with all four internal USB devices on real hardware; no USB2-only upstream cable.",
    "Mic900mA is an available port budget, not its measured consumption. Standard USB enumeration still governs device allocation.",
    "Supervisor thresholds ensure staged startup, not a guaranteed fail-safe undervoltage boundary for every chip. Verify brownout/recovery corners and improve if required.",
    "J505 is an internal USB2 expansion only,500mA enumeration budget. No Daly UART electrical levels or isolation circuitry are assumed; never join either BMS ground toUSBground through an unisolated UART.",
]

def build_parts():
    NO_CONNECT_PINS.clear()
    SUPERSPEED_PAIRS.clear()
    PORT_EN_FILTER.clear()
    n = Netlist()
    seq = {"R":500,"C":500,"L":500,"D":500}
    def ref(k):
        seq[k] += 1
        return f"{k}{seq[k]}"
    def r(value, a, b, block, lcsc=None, mpn=None):
        q=ref("R"); n.R(q,value,a,b,block)
        if lcsc: n.parts[-1].update(lcsc=lcsc,mpn=mpn or f"0603 1% {value}",status="supplier-listed; confirm actual assembly stock")
        return q
    def c(value,a,b,block):
        q=ref("C"); n.C(q,value,a,b,block); return q
    def nc(uref,pins):
        NO_CONNECT_PINS[uref]=list(map(str,pins))
    def p(uref,sym,value,fp,pins,block,code,mpn):
        n.P(uref,sym,value,fp,pins,block,code,mpn,"manufacturer pinchecked; footprint/stock/bench verification pending")
    def ss_esd(uref,signals,block):
        # Opposite-side NC lands are deliberately assigned the same nets for
        # physical straight-through routing; they are NOT internally connected.
        pins={"3":"GND","8":"GND"}
        for (a,b),net in zip((("1","10"),("2","9"),("4","7"),("5","6")),signals): pins[a]=pins[b]=net
        p(uref,"pdb:TPD4E02B04","TPD4E02B04DQAR",FP["ss_esd"],pins,block,"C106794","TI TPD4E02B04DQAR")
    def two_esd(uref,a,b,block):
        p(uref,"pdb:TPD2E2U06_DRL","TPD2E2U06DRLR",FP["usb2_esd"],{"1":f"NC_{uref}_1","2":f"NC_{uref}_2","3":a,"4":"GND","5":b},block,"C1972959","TI TPD2E2U06DRLR")
        nc(uref,(1,2))
    def usb_c(jref,prefix,vbus,block):
        pins={"A1":"GND","A12":"GND","B1":"GND","B12":"GND","A2":prefix+"_TX1P","A3":prefix+"_TX1N","B2":prefix+"_TX2P","B3":prefix+"_TX2N","A10":prefix+"_RX2N","A11":prefix+"_RX2P","B10":prefix+"_RX1N","B11":prefix+"_RX1P","A4":vbus,"A9":vbus,"B4":vbus,"B9":vbus,"A5":prefix+"_CC1","B5":prefix+"_CC2","A6":prefix+"_DP","B6":prefix+"_DP","A7":prefix+"_DM","B7":prefix+"_DM","A8":f"NC_{jref}_SBU1","B8":f"NC_{jref}_SBU2","S1":"GND"}
        p(jref,"pdb:USB_C_24",prefix+" USB3 TYPE-C",FP["usbc"],pins,block,"C134092","Molex1054500101")
        nc(jref,("A8","B8"))
    def tx_caps(a,b,block):
        for lane in ("P","N"):
            c("100nF 50V",a+lane,b+lane,block)
        SUPERSPEED_PAIRS.extend([(a+"P",a+"N"),(b+"P",b+"N")])

    B="USB3 A. Dedicated low-voltage rails and staged hardware reset"
    # 1.2V starts with the input;3.3V is enabled only after delayed1.2V good.
    for uref,out,enable,top in (("U510","+1V2_USB","+5_USB_RAW",["105k"]),("U511","+3V3_USB","USB_1V2_GOOD",["150k","150k","160k"])):
        sw=uref+"_SW"; fb=uref+"_FB"
        p(uref,"pdb:TLV62569_DBV","TLV62569DBVR",FP["buck"],{"1":enable,"2":"GND","3":sw,"4":"+5_USB_RAW","5":fb},B,"C141836","TI TLV62569DBVR")
        c("10uF 25V","+5_USB_RAW","GND",B);c("100nF 50V","+5_USB_RAW","GND",B)
        p(ref("L"),"Device:L","2.2uH 4A",FP["inductor"],{"1":sw,"2":out},B,"C719179","Bourns SRP4020TA-2R2M")
        for _ in range(2):c("22uF 25V",out,"GND",B)
        prev=out
        for i,val in enumerate(top):
            dest=fb if i==len(top)-1 else uref+f"_DIV{i}"
            r(val,prev,dest,B,*({"105k":("C16840","UNI-ROYAL0603WAF1053T5E"),"160k":("C22813","UNI-ROYAL0603WAF1603T5E")}.get(val,(None,None))));prev=dest
        r("100k",fb,"GND",B,"C122538","Yageo RT0603BRD07100KL")
    #Fixed-threshold supervisors avoid uncertain external divider/hysteresis
    #overlap. G12minfall1.103V>hub1.08V;G33minfall3.024V>hub3.0V.
    #3.3V supervisor stays powered by3.3V during raw5V collapse.
    for uref,supply,sense_rail,mr,good,pull,mpn,code in (
        ('U512','+5_USB_RAW','+5_USB_RAW','+5_USB_RAW','USB_5V_GOOD','+5_USB_RAW','TPS3808G50DBVR','C134123'),
        ('U513','+5_USB_RAW','+1V2_USB','USB_5V_GOOD','USB_1V2_GOOD','+5_USB_RAW','TPS3808G12DBVR','C130063'),
        ('U514','+3V3_USB','+3V3_USB','USB_1V2_GOOD','USB_RESET_N','+3V3_USB','TPS3808G33DBVR','C43698')):
        r('10k',pull,good,B)
        p(uref,'pdb:TPS3808_DBV',mpn,FP_SOT236,{'1':good,'2':'GND','3':mr,'4':uref+'_CT_NC','5':sense_rail,'6':supply},B,code,'TI '+mpn)
        nc(uref,(4,));c('100nF 50V',supply,'GND',B)
    # NPN inversion makesCC disabled until rail-good delay has expired.
    r("100k","USB_RESET_N","USB_CC_ENABLE_BASE",B);r("100k","USB_CC_ENABLE_BASE","GND",B)
    p("Q500","Transistor_BJT:MMBT3904","MMBT3904","Package_TO_SOT_SMD:SOT-23",{"1":"USB_CC_ENABLE_BASE","2":"GND","3":"UP_CC_EN_N"},B,"C20526","JSCJ MMBT3904")
    r("10k","+5_USB_RAW","UP_CC_EN_N",B)
    r("49.9k","UP_VBUS","UP_VBUS_SENSE",B);r("100k","UP_VBUS_SENSE","GND",B)
    p("U515","pdb:SN74LVC1G97","SN74LVC1G97DBVR AND",FP_SOT236,{"1":"GND","2":"GND","3":"UP_VBUS_SENSE","4":"USB_HUB_VBUS_DET","5":"+3V3_USB","6":"USB_RESET_N"},B,"C128411","TI SN74LVC1G97DBVR")
    c("100nF 50V","+3V3_USB","GND",B)

    B="USB3 B. USB5744 self-powered four-port hub"
    pins={str(i):f"NC_U500_{i}" for i in range(1,58)}
    for i in (5,12,15,21,28,33,43,49):pins[str(i)]="+1V2_USB";c("100nF 50V","+1V2_USB","GND",B)
    for i in (16,31,44,55):pins[str(i)]="+3V3_USB";c("100nF 50V","+3V3_USB","GND",B)
    pins.update({"1":"HUB_CHILD_DP","2":"HUB_CHILD_DM","8":"CAM_DP","9":"CAM_DM","10":"CAM_TXP","11":"CAM_TXN","13":"CAM_RXP","14":"CAM_RXN","17":"MIC_DP","18":"MIC_DM","19":"MIC_TXP","20":"MIC_TXN","22":"MIC_RXP","23":"MIC_RXN","24":"+3V3_USB","25":"+3V3_USB","34":"MIC_PRT_CTL","35":"CAM_PRT_CTL","37":"USB_HUB_VBUS_DET","40":"HUB_CFG_BC","41":"HUB_CFG_NONREM","42":"USB_RESET_N","45":"UP_DP","46":"UP_DM","47":"UP_TXP","48":"UP_TXN","50":"UP_RXP","51":"UP_RXN","52":"GND","53":"HUB_XO","54":"HUB_XI","56":"HUB_RBIAS","57":"GND"})
    p("U500","pdb:USB5744","USB5744-I/2G",FP["hub"],pins,B,"C633621","Microchip USB5744-I/2G")
    nc("U500",(3,4,6,7,26,27,29,30,32,36,38,39))
    r("12k","HUB_RBIAS","GND",B)
    r("200k","+3V3_USB","HUB_CFG_NONREM",B,"C25811")
    r("200k","HUB_CFG_BC","GND",B,"C25811")
    p("Y500","pdb:XTAL4","25MHz 12pF",FP_XTAL,{"1":"HUB_XI","2":"GND","3":"HUB_XO","4":"GND"},B,"C9006","YXC X322525MOB4SI")
    #12pF crystal:20pF each assumes approximately2pF aggregate stray load.
    for net in ("HUB_XI","HUB_XO"):
        n.P(ref("C"),"Device:C","20pF 50V C0G",FP_C0603,{"1":net,"2":"GND"},B,"C1648","Samsung CL10C200JB8NNNC","verify crystal effective load")
    c("10uF 25V","+1V2_USB","GND",B);c("10uF 25V","+3V3_USB","GND",B)

    B="USB3 C. Upstream UFP Type-C with autonomous orientation"
    usb_c("J500","UP","UP_VBUS",B)
    pins={"1":"UP_CC2","2":"UP_CC1","3":"GND","4":"GND","5":"UP_CC_VBUS_DET","6":"UP_TXP","7":"UP_TXN","8":"+3V3_USB","9":"UP_RXP","10":"UP_RXN","11":"UP_DIR","12":"GND","13":"GND","14":"UP_RX1N","15":"UP_RX1P","16":"UP_TX1N_AC","17":"UP_TX1P_AC","18":"UP_RX2N","19":"UP_RX2P","20":"UP_TX2N_AC","21":"UP_TX2P_AC","22":"NC_U501_ADDR","23":"NC_U501_OUT3","24":"NC_U501_VCONNFAULT","25":"NC_U501_OUT1","26":"NC_U501_OUT2","27":"NC_U501_ID","28":"GND","29":"UP_CC_EN_N","30":"+5_USB_RAW","31":"GND"}
    p("U501","pdb:HD3SS3220","HD3SS3220IRNHR",FP["up_mux"],pins,B,"C701817","TI HD3SS3220IRNHR")
    nc("U501",(22,23,24,25,26,27));r("200k","+3V3_USB","UP_DIR",B,"C25811")
    #900k is theHD3SS3220 value;887k is thecurrentTUSB320 value(not used).
    r("100k","UP_VBUS","UP_VBUS_R1",B)
    for i in range(4):r("200k",f"UP_VBUS_R{i+1}","UP_CC_VBUS_DET" if i==3 else f"UP_VBUS_R{i+2}",B,"C25811")
    c("100nF 50V","+5_USB_RAW","GND",B);c("100nF 50V","+3V3_USB","GND",B)
    for lane in (1,2):
        for sign in ("P","N"):c("100nF 50V",f"UP_TX{lane}{sign}_AC",f"UP_TX{lane}{sign}",B)
    ss_esd("U520",["UP_TX1P","UP_TX1N","UP_RX1P","UP_RX1N"],B)
    ss_esd("U521",["UP_TX2P","UP_TX2N","UP_RX2P","UP_RX2N"],B)
    two_esd("U525","UP_DP","UP_DM",B);two_esd("U526","UP_CC1","UP_CC2",B)
    #Input VBUS sense only:tiny local bypass, no hub/rail load or bulk.
    c("100nF 50V","UP_VBUS","GND",B)

    B="USB3 D. OAK-D downstream Type-C3A power and orientation"
    usb_c("J501","CAM","CAM_VBUS",B)
    p("U502","pdb:TPS25810","TPS25810RVCR",FP["camera_power"],{"1":"CAM_PRT_CTL","2":"+5_USB_RAW","3":"+5_USB_RAW","4":"+5_USB_RAW","5":"+3V3_USB","6":"CAM_PRT_CTL","7":"+3V3_USB","8":"+3V3_USB","9":"CAM_REF_RTN","10":"CAM_REF","11":"CAM_CC1","12":"GND","13":"CAM_CC2","14":"CAM_VBUS","15":"CAM_VBUS","16":"NC_U502_DEBUG","17":"NC_U502_AUDIO","18":"CAM_POL","19":"CAM_UFP_N","20":"NC_U502_LOAD","21":"GND"},B,"C473913","TI TPS25810RVCR")
    nc("U502",(16,17,20));r("100k","CAM_REF","CAM_REF_RTN",B)
    r("100k","+3V3_USB","CAM_POL",B);r("100k","+3V3_USB","CAM_UFP_N",B)
    c("10uF 25V","+5_USB_RAW","GND",B);c("100nF 50V","+5_USB_RAW","GND",B);c("100nF 50V","+3V3_USB","GND",B)
    #TI Fig15:POL high selectsC ->TX1/RX1;POL low selectsB ->TX2/RX2.
    p("U503","pdb:HD3SS3212","HD3SS3212IRKSR",FP["cam_mux"],{"1":"NC_U503_1","2":"CAM_UFP_N","3":"CAM_TXP","4":"CAM_TXN","5":"GND","6":"+3V3_USB","7":"CAM_RXP","8":"CAM_RXN","9":"CAM_POL","10":"NC_U503_10","11":"GND","12":"CAM_RX1N","13":"CAM_RX1P","14":"CAM_TX1N_AC","15":"CAM_TX1P_AC","16":"CAM_RX2N","17":"CAM_RX2P","18":"CAM_TX2N_AC","19":"CAM_TX2P_AC","20":"GND","21":"GND"},B,"C544517","TI HD3SS3212IRKSR")
    nc("U503",(1,10));c("100nF 50V","+3V3_USB","GND",B)
    for lane in (1,2):
        for sign in ("P","N"):c("100nF 50V",f"CAM_TX{lane}{sign}_AC",f"CAM_TX{lane}{sign}",B)
    ss_esd("U522",["CAM_TX1P","CAM_TX1N","CAM_RX1P","CAM_RX1N"],B)
    ss_esd("U523",["CAM_TX2P","CAM_TX2N","CAM_RX2P","CAM_RX2N"],B)
    two_esd("U527","CAM_DP","CAM_DM",B);two_esd("U528","CAM_CC1","CAM_CC2",B)
    for _ in range(2):
        c("22uF 25V","CAM_VBUS","GND",B)
        n.parts[-1].update(fp=FP_C0805,lcsc="C45783",mpn="Samsung CL21A226MAQNNNE",status="primaryDCbiasengineeringreview;verifyeffectiveCunderload")
    #Specified120uF port bulk, separate from6.8uF minimum atTypeCswitch.
    n.P(ref("C"),"Device:C_Polarized","150uF 10V POSCAP","Robot_PDB:Panasonic_POSCAP_D3L",{"1":"+5_USB_RAW","2":"GND"},B,"C347559","Panasonic 10TPF150ML","supplier-listed; compare D3L land pattern and actual JLC stock")

    B="USB3 E. Protected USB-A3 microphone port"
    p("U504","pdb:TPS2553","TPS2553DBVR",FP_SOT236,{"1":"+5_USB_RAW","2":"GND","3":"MIC_PRT_CTL","4":"MIC_PRT_CTL","5":"MIC_ILIM","6":"MIC_VBUS"},B,"C55266","TI TPS2553DBVR")
    r("26.1k","MIC_ILIM","GND",B,"C23356","UNI-ROYAL0603WAF2612T5E")
    c("100nF 50V","+5_USB_RAW","GND",B)
    tx_caps("MIC_TX","MIC_TX_CONN",B)
    n.P("J502","pdb:USB_A_3","MIC USB-A3 900mA",FP["usba"],{"1":"MIC_VBUS","2":"MIC_DM","3":"MIC_DP","4":"GND","5":"MIC_RXN","6":"MIC_RXP","7":"GND","8":"MIC_TX_CONNN","9":"MIC_TX_CONNP","10":"GND"},B,"","Molex48393-0003;hand-fit exact connector","hand-fit;verify1.6mm board compatibility and hole pattern",dnp=True)
    ss_esd("U524",["MIC_TX_CONNP","MIC_TX_CONNN","MIC_RXP","MIC_RXN"],B)
    two_esd("U529","MIC_DP","MIC_DM",B)
    n.P(ref("C"),"Device:C_Polarized","150uF 10V POSCAP","Robot_PDB:Panasonic_POSCAP_D3L",{"1":"MIC_VBUS","2":"GND"},B,"C347559","Panasonic 10TPF150ML","supplier-listed; compare D3L land pattern and actual JLC stock")
    n.P("J503","Connector_Generic:Conn_01x04","INTERNAL USB2 CHILD","Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical",{"1":"+5_USB_RAW","2":"HUB_CHILD_DM","3":"HUB_CHILD_DP","4":"GND"},B,"","Internal shielded USB2 harness to self-powered CH334F section","hand-fit; pin1 local5V optional, never parallel another regulator",dnp=True)
    n.P("J504","Connector_Generic:Conn_01x02","DEDICATED5V1 >=6A","Robot_PDB:Power_WirePort_P7.2mm",{"1":"GND","2":"+5_USB_RAW"},B,"","Hand-soldered dedicated5V supply pigtail; >=6A harness qualification","hand-fit",dnp=True)
    #RevB manufacturer checklist recommends330nF RX coupling on the connector
    #side. This keeps local hub receiver bias available to each passive mux.
    byref={p['ref']:p for p in n.parts}
    #Group connector rows for the physical escapes:Arow isSMT,Fside;Brow
    #isPTH and can reach theBsideESD array without crossing theArow lands.
    for prefix,a_ref,b_ref in (('UP','U520','U521'),('CAM','U522','U523')):
        for refname,signals in ((a_ref,[f'{prefix}_TX1P',f'{prefix}_TX1N',f'{prefix}_RX2N',f'{prefix}_RX2P']),
                                (b_ref,[f'{prefix}_TX2P',f'{prefix}_TX2N',f'{prefix}_RX1N',f'{prefix}_RX1P'])):
            for (i,j),net in zip((('1','10'),('2','9'),('4','7'),('5','6')),signals):
                byref[refname]['pins'][i]=byref[refname]['pins'][j]=net
    #Port4 is a serviceable internal USB2 expansion; itsSS lane staysunused.
    byref['U500']['pins'].update({'24':'BMS_USB_DP','25':'BMS_USB_DM','32':'BMS_PRT_CTL'})
    NO_CONNECT_PINS['U500'].remove('32')
    p('U505','pdb:TPS2553','TPS2553DBVR',FP_SOT236,{'1':'+5_USB_RAW','2':'GND','3':'BMS_PRT_CTL','4':'BMS_PRT_CTL','5':'BMS_ILIM','6':'BMS_USB_VBUS'},B,'C55266','TI TPS2553DBVR')
    r('26.1k','BMS_ILIM','GND',B,'C23356','UNI-ROYAL 0603WAF2612T5E')
    c('100nF 50V','+5_USB_RAW','GND',B)
    n.P('J505','Connector_Generic:Conn_01x04','BATTERY USB2 EXPANSION','Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical',{'1':'BMS_USB_VBUS','2':'BMS_USB_DM','3':'BMS_USB_DP','4':'GND'},B,'','Hand-fit internalUSB2 header;500mA budget; isolatedBMSUART hardware separately qualified','hand-fit; no battery UART direct connection',dnp=True)
    for prefix,uref,mapping in (("UP","U501",((14,15,1),(18,19,2))),("CAM","U503",((12,13,1),(16,17,2)))):
        for negpin,pospin,lane in mapping:
            for sign,pin in (("P",pospin),("N",negpin)):
                local=f"{prefix}_RX{lane}{sign}_AC";external=f"{prefix}_RX{lane}{sign}"
                byref[uref]['pins'][str(pin)]=local
                n.P(ref('C'),'Device:C','330nF 25V',FP_C0603,{'1':local,'2':external},B,'C1615','FH 0603B334K250NT','manufacturer-recommended RX coupling; verify actual assembly stock')
    byref['J502']['pins'].update({'5':'MIC_RX_CONNN','6':'MIC_RX_CONNP'})
    for pin,net in list(byref['U524']['pins'].items()):
        if net in ('MIC_RXP','MIC_RXN'):byref['U524']['pins'][pin]=net.replace('MIC_RX','MIC_RX_CONN')
    for sign in ('P','N'):
        n.P(ref('C'),'Device:C','330nF 25V',FP_C0603,{'1':'MIC_RX'+sign,'2':'MIC_RX_CONN'+sign},B,'C1615','FH 0603B334K250NT','manufacturer-recommended RX coupling; verify actual assembly stock')
    for prefix in ("UP","CAM"):
        for lane in (1,2):
            for direction in ("TX","RX"):
                SUPERSPEED_PAIRS.extend([(f"{prefix}_{direction}{lane}P",f"{prefix}_{direction}{lane}N"),(f"{prefix}_{direction}{lane}P_AC",f"{prefix}_{direction}{lane}N_AC")])
    SUPERSPEED_PAIRS.extend((a+"P",a+"N") for a in ("UP_TX","UP_RX","CAM_TX","CAM_RX","MIC_TX","MIC_RX"))
    SUPERSPEED_PAIRS.append(('MIC_RX_CONNP','MIC_RX_CONNN'))
    #The RC improves steady-fault OCS assertion. It is deliberately NOT
    #claimed to guarantee hub latching for every first-enable/thermal pulse;
    #Microchip also detects two short pulses within20ms. Bench cases remain.
    byref={p['ref']:p for p in n.parts}
    for uref,pin,prefix in (('U502','6','CAM'),('U504','3','MIC'),('U505','3','BMS')):
        enable=prefix+'_PWR_EN';byref[uref]['pins'][pin]=enable
        rr=r('220k',prefix+'_PRT_CTL',enable,'USB3 F. Port enable timing','C22961','UNI-ROYAL0603WAF2203T5E')
        cr=ref('C')
        n.P(cr,'Device:C','100nF 50V C0G EN','Capacitor_SMD:C_1206_3216Metric',{'1':enable,'2':'GND'},'USB3 F. Port enable timing','C97946','MurataGRM31C5C1H104JA01L','C0G5%/30ppmC;noDCbias;prototypeOCSfaulttimingrequiresbenchverification')
        PORT_EN_FILTER[prefix]={'resistor':rr,'capacitor':cr,'enable_net':enable,'hub_fault_net':prefix+'_PRT_CTL','r_ohm':220000,'c_f':1e-7}
    for i in range(4):
        n.P(f'H{500+i}','Mechanical:MountingHole','M3 SUPPORT / NYLON STANDOFF','MountingHole:MountingHole_3.2mm_M3',{},'USB3 mechanical supports','','M3 nylon standoff; support0.8mm PCB at all four cell corners','mechanical; support near USB cable loads',dnp=True)
    #One two-channel protection device perSuperSpeedpair followsTI Fig10-1.
    #The former centered fourchannelarrays boxed in theUSB2 escape on both
    #outerlayers. Replacement adds5devices and leaves thecentre corridor open.
    #DRT solderlands followTI drawing4211172/A07/10 (.30square at
    #IO±.35,+.425/GND0,-.425); maximumstencil.1016mm; factoryreviewrecorded.
    for oldref in ('U520','U521','U522','U523','U524'):
        part=next(p for p in n.parts if p['ref']==oldref);original=dict(part['pins'])
        one=[original['1'],original['2']];two=[original['4'],original['5']]
        for rr,nets in ((oldref,one),(f'U{int(oldref[1:])+10}',two)):
            nets=sorted(nets,key=lambda name:0 if name.endswith('P') else 1)
            if rr in ('U530','U531','U532','U533'):nets.reverse() #identicalESDchannels;matchRXconnectororder
            pins={'1':nets[0],'2':nets[1],'3':'GND'}
            if rr==oldref:part.update(sym='pdb:TPD2EUSB30A_DRT',value='TPD2EUSB30ADRTR',fp='Robot_PDB:TI_DRT0003A_1x0.8_P0.7',pins=pins,lcsc='C94934',mpn='TI TPD2EUSB30ADRTR',status='primaryTI pin/land4211172/Averified;100umstencil;factoryreviewpending')
            else:n.P(rr,'pdb:TPD2EUSB30A_DRT','TPD2EUSB30ADRTR','Robot_PDB:TI_DRT0003A_1x0.8_P0.7',pins,part['block'],'C94934','TI TPD2EUSB30ADRTR','primaryTI pin/land4211172/Averified;100umstencil;factoryreviewpending')
    return n.parts

PARTS=build_parts()
assert len({p["ref"] for p in PARTS})==len(PARTS),"duplicate USB3 ref"
assert len(CUSTOM_SYMBOL_PINS["pdb:USB5744"])==57
assert all(p["fp"] for p in PARTS)

if __name__=="__main__":
    import json
    print(json.dumps({"title":TITLE,"parts":PARTS,"custom_symbol_pins":CUSTOM_SYMBOL_PINS,"no_connect_pins":NO_CONNECT_PINS,"power_input":POWER_INPUT,"release_holds":RELEASE_HOLDS},indent=2))
