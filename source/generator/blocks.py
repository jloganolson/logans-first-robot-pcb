"""Shared circuit blocks for the robot PDB family (big board + test board).

Each function appends parts to a PARTS list via P(). The same blocks are laid out by
cells.py, so the test board and the big board use identical converter layouts.
"""

FP_R = "Resistor_SMD:R_0603_1608Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1210 = "Capacitor_SMD:C_1210_3225Metric"
FP_LED = "LED_SMD:LED_0603_1608Metric"
FP_SMC = "Diode_SMD:D_SMC"
FP_XT60M = "Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal"
FP_XT60F = "Connector_AMASS:AMASS_XT60PW-F_1x02_P7.20mm_Horizontal"
FP_XT30F = "Connector_AMASS:AMASS_XT30PW-F_1x02_P2.50mm_Horizontal"
FP_EH3 = "Connector_JST:JST_EH_B3B-EH-A_1x03_P2.50mm_Vertical"
FP_FUSE = "Fuse:FuseHolder_Blade_ATO_Littelfuse_FLR_178.6165"
FP_TDSON = "Package_TO_SOT_SMD:TDSON-8-1"
FP_TPS = "Package_SO:TI_SO-PowerPAD-8_ThermalVias"
FP_LM5146 = "Package_DFN_QFN:Texas_RGY_R-PVQFN-N20_EP2.05x3.05mm"
FP_SOT236 = "Package_TO_SOT_SMD:SOT-23-6"
FP_L1004 = "Inductor_SMD:L_Sunlord_MWSA1004S"
FP_L1770 = "Inductor_SMD:L_Bourns_SRP1770TA_16.9x16.9mm"
FP_HOLE = "MountingHole:MountingHole_3.2mm_M3"
FP_TP = "TestPoint:TestPoint_Pad_D1.5mm"
FP_QFN24 = "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.6x2.6mm"
FP_LQFP48 = "Package_QFP:LQFP-48_7x7mm_P0.5mm"
FP_HTSSOP32 = "Package_SO:HTSSOP-32-1EP_6.1x11mm_P0.65mm_EP5.2x11mm_Mask4.11x4.36mm_ThermalVias"
FP_VSSOP8 = "Package_SO:VSSOP-8_2.3x2mm_P0.5mm"
FP_USBC = "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12"
FP_XTAL = "Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm"
FP_FB = "Inductor_SMD:L_0603_1608Metric"
FP_TERM2 = "TerminalBlock:TerminalBlock_bornier-2_P5.08mm"
FP_HDR4 = "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical"
FP_JP = "Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm"

# JLC basic-library resistor numbers (0603 1%); confirm at order
RES = {
    "300": "C23025", "1k": "C21190", "2.2k": "C4190", "7.5k": "C23234",
    "10k": "C25804", "12k": "C22790", "20k": "C4184", "22k": "C31850", "30k": "C22984",
    "39k": "C23153", "49.9k": "C23184", "100k": "C25803", "150k": "C22807", "5.1k": "C23186",
    "220k": "C22961", "4.7k": "C23162",
    "180": "C22828", "5.6k": "C23189", "2.4k": "C22940",
}
# value -> (footprint, lcsc, status). "verified" = LCSC page checked 2026-11-03, in stock
CAP = {
    "33pF 50V": (FP_C0603, "C1663", "basic"),        # Samsung CL10C330JB8NNNC C0G
    "100nF 50V": (FP_C0603, "C14663", "basic"),
    "100nF 100V": (FP_C0603, "C15725", "verified"),     # Samsung CL10B104KC8NNNC
    "4.7uF 16V": (FP_C0603, "C19666", "basic"),
    "47pF": (FP_C0603, "C1671", "basic"),
    "2.2nF": (FP_C0603, "C1604", "basic"),
    "4.7nF": (FP_C0603, "C53987", "basic"),
    "47nF": (FP_C0603, "C1622", "basic"),
    "22uF 25V": (FP_C0805, "C45783", "basic"),
    "2.2uF 100V": (FP_C1210, "C55151", "verified"),     # Samsung CL32B225KCJSNNE
    "10uF 50V": (FP_C1210, "C138687", "verified"),      # Samsung CL32B106KBJNNNE
    "1uF 25V": (FP_C0603, "C15849", "basic"),
    "10uF 25V": (FP_C0805, "C15850", "basic"),
    "220nF 25V": (FP_C0603, "C21120", "basic"),
    "1nF": (FP_C0603, "C1588", "basic"),
    "680nF 50V": ("Capacitor_SMD:C_1206_3216Metric", "C1881", "confirm"),  # FH 1206B684K500NT X7R
}
ELEC = {  # value -> (lcsc, mpn); selected 2026-11-05 from public LCSC listings, confirm stock in cart
    "100uF 63V": ("C249468", "Lelon VE-101M1JTR-1010 100uF 63V 10x10mm"),
    "220uF 35V": ("C3029711", "Lelon VUX221M1VTR-1010 220uF 35V 10x10mm"),
    "470uF 25V": ("C249933", "Lelon VZH471M1ETR-1010 470uF 25V 10x10mm low-ESR"),
}


class Netlist:
    def __init__(self):
        self.parts = []

    def P(self, ref, sym, value, fp, pins, block, lcsc="", mpn="", status="confirm", dnp=False):
        self.parts.append(dict(ref=ref, sym=sym, value=value, fp=fp, pins=pins, block=block,
                               lcsc=lcsc, mpn=mpn, status=status, dnp=dnp))

    def R(self, ref, val, a, b, block):
        self.P(ref, "Device:R", val, FP_R, {"1": a, "2": b}, block, RES.get(val, ""),
               f"0603 1% {val}", "basic" if val in RES else "confirm")

    def C(self, ref, val, a, b, block):
        fp, lcsc, st = CAP[val]
        dielectric = "C0G" if val == "33pF 50V" else ("X5R" if lcsc in ("C19666", "C45783") else "X7R")
        self.P(ref, "Device:C", val, fp, {"1": a, "2": b}, block, lcsc, f"MLCC {dielectric} {val}", st)

    def CP(self, ref, val, size, pos, neg, block):
        self.P(ref, "Device:C_Polarized", val, f"Capacitor_SMD:CP_Elec_{size}", {"1": pos, "2": neg},
               block, *ELEC.get(val, ("", f"Aluminium electrolytic {val}")), "confirm")

    def LED(self, ref, rref, net, rval, block):
        self.P(ref, "Device:LED", "Green", FP_LED, {"1": "GND", "2": f"{ref}_A"}, block,
               "C12624", "KT-0603G 0603 green LED", "basic")
        self.R(rref, rval, net, f"{ref}_A", block)

    def TP(self, ref, net, label, block):
        self.P(ref, "Connector:TestPoint", label, FP_TP, {"1": net}, block, "", "bare copper test pad", "", dnp=True)

    def JP(self, ref, a, b, label, block):
        self.P(ref, "Jumper:SolderJumper_2_Open", label, FP_JP, {"1": a, "2": b}, block, "",
               "solder jumper (open, bridge with solder)", "", dnp=True)

    # ------------------------------------------------------------ blocks
    def input_block(self, motor=True, bulk=2):
        B = "A. Battery input" + (", motor pass-through" if motor else "") + ", logic protection"
        P = self.P
        P("J1", "Connector_Generic:Conn_01x02", "BATTERY IN (XT60 male)", FP_XT60M,
          {"1": "GND", "2": "VBAT"}, B, "C98732", "Amass XT60PW-M", "verified")
        # Holder: Littelfuse 178.6165.0002 (C207061), 30A, 8 solder pins = FLR_178.6165 footprint.
        # v0.3 listed 178.6164.0002 (C207059), a 15A 2-pin holder that did not fit this footprint.
        # Fuses are inserted by hand: use 58V-rated ATO fuses (32V parts are below 33.6V full charge).
        if motor:
            P("F1", "Device:Fuse", "MOTOR FUSE 30A ATO", FP_FUSE, {"1": "VMOT", "2": "VBAT"}, B,
              "C207061", "Littelfuse 178.6165.0002 ATO holder 30A/80V (fuse not assembled; use 58V ATO fuse)", "verified")
            P("J2", "Connector_Generic:Conn_01x02", "WHEEL MOTORS (XT60 female)", FP_XT60F,
              {"1": "GND", "2": "VMOT"}, B, "C428722", "Amass XT60PW-F", "verified")
        P("F2", "Device:Fuse", "LOGIC FUSE 20A ATO", FP_FUSE, {"1": "VBAT_L", "2": "VBAT"}, B,
          "C207061", "Littelfuse 178.6165.0002 ATO holder 30A/80V (fuse not assembled; use 58V ATO fuse)", "verified")
        P("D1", "Device:D_TVS", "SMCJ36CA", FP_SMC, {"1": "VBAT_L", "2": "GND"}, B,
          "C151283", "Littelfuse SMCJ36CA bidirectional 36V TVS; surge envelope unqualified", "confirm")
        self.C("C1", "100nF 100V", "VBAT_L", "GND", B)
        P("Q1", "pdb:NMOS_TDSON8", "BSC040N10NS5", FP_TDSON,
          {"1": "VBAT_L", "2": "VBAT_L", "3": "VBAT_L", "4": "Q1_G", "5": "VIN"}, B,
          "C534334", "Infineon BSC040N10NS5ATMA1 100V 4mR at VGS=10V", "confirm")
        P("U1", "pdb:LM74700", "LM74700QDBVRQ1", FP_SOT236,
          {"1": "U1_VCAP", "2": "GND", "3": "VBAT_L", "4": "VIN", "5": "Q1_G", "6": "VBAT_L"}, B,
          "C2941042", "TI LM74700-Q1 ideal diode controller", "verified")
        self.C("C2", "100nF 50V", "U1_VCAP", "VBAT_L", B)
        for i in range(bulk):
            self.CP(f"C{3+i}", "100uF 63V", "10x10", "VIN", "GND", B)  # v0.3 220uF 10x12.6 had no stocked part
        self.C("C5", "100nF 100V", "VIN", "GND", B)
        self.LED("D2", "R1", "VIN", "22k", B)
        self.TP("TP1", "VIN", "VIN", B)
        self.TP("TP2", "GND", "GND", B)

    def thor_block(self, out_conn=True):
        B = "B. 24V for Thor dev kit (8A connector ceiling; unqualified) (LM5146 sync buck, 200 kHz)"
        P, R, C = self.P, self.R, self.C
        P("U2", "pdb:LM5146", "LM5146QRGYRQ1", FP_LM5146,
          {"1": "T_EN", "2": "T_RT", "3": "T_SS", "4": "T_COMP", "5": "T_FB", "6": "GND",
           "7": "T_SYNCOUT", "8": "GND", "9": "T_NC9", "10": "T_PG", "11": "T_ILIM", "12": "GND",
           "13": "T_LO", "14": "T_VCC", "15": "GND", "16": "T_NC16", "17": "T_BST", "18": "T_HO",
           "19": "T_SW", "20": "VIN", "21": "GND"}, B,
          "C1850329", "TI LM5146-Q1 100V sync buck controller", "verified")
        P("Q2", "pdb:NMOS_TDSON8", "BSC034N06NS", FP_TDSON,
          {"1": "T_SW", "2": "T_SW", "3": "T_SW", "4": "T_HO", "5": "VIN"}, B,
          "C534325", "Infineon BSC034N06NS (high side)", "verified")
        P("Q3", "pdb:NMOS_TDSON8", "BSC034N06NS", FP_TDSON,
          {"1": "GND", "2": "GND", "3": "GND", "4": "T_LO", "5": "T_SW"}, B,
          "C534325", "Infineon BSC034N06NS (low side)", "verified")
        # SRP1770TA-100M is not stocked at LCSC. ZE ZEMS1770-100M: 10uH, Isat 25A, Irated 16.5A, DCR 10mR,
        # 17.5x17.2mm. Check its land pattern against the SRP1770TA footprint before ordering.
        P("L1", "Device:L", "10uH 16.5A", FP_L1770, {"1": "T_SW", "2": "+24V"}, B,
          "C41438691", "ZE ZEMS1770-100M (SRP1770TA-100M equivalent); confirm land pattern", "confirm")
        for ref in ["C10", "C11", "C12", "C13"]:
            C(ref, "2.2uF 100V", "VIN", "GND", B)
        self.CP("C14", "100uF 63V", "10x10", "VIN", "GND", B)
        C("C15", "100nF 100V", "VIN", "GND", B)
        for ref in ["C16", "C17", "C18", "C19"]:
            C(ref, "10uF 50V", "+24V", "GND", B)
        self.CP("C20", "220uF 35V", "10x10", "+24V", "GND", B)
        C("C21", "4.7uF 16V", "T_VCC", "GND", B)
        C("C22", "100nF 50V", "T_BST", "T_SW", B)
        C("C23", "47nF", "T_SS", "GND", B)
        R("R10", "49.9k", "T_RT", "GND", B)
        R("R11", "220k", "VIN", "T_EN", B)
        R("R12", "12k", "T_EN", "GND", B)
        R("R13", "180", "T_ILIM", "T_SW", B)
        C("C27", "33pF 50V", "T_ILIM", "GND", B)  # 180R * 33pF = 5.94ns; final trip-current validation pending
        R("R14", "150k", "+24V", "T_FB", B)
        R("R15", "5.1k", "T_FB", "GND", B)
        R("R16", "49.9k", "T_COMP", "T_CZ", B)
        C("C24", "2.2nF", "T_CZ", "T_FB", B)
        C("C25", "47pF", "T_COMP", "T_FB", B)
        R("R17", "1k", "+24V", "T_C3", B)
        C("C26", "2.2nF", "T_C3", "T_FB", B)
        self.LED("D3", "R19", "+24V", "22k", B)
        self.JP("JP1", "T_EN", "GND", "24V OFF", B)
        self.TP("TP3", "T_SW", "SW24", B)
        self.TP("TP4", "+24V", "24V", B)
        self.TP("TP5", "T_PG", "PG24", B)
        if out_conn:
            P("J3", "Connector_Generic:Conn_01x02", "JETSON THOR 24V (XT30 female)", FP_XT30F,
              {"1": "GND", "2": "+24V"}, B, "C2913282", "Amass XT30PW-F", "verified")

    def tps_block(self, n, k, net, title, lval, rtop, rbot, rcomp, rled):
        """TPS54560 cell. Designators: U{3+n}, L{2+n}, and C/R/D/J/TP/JP with base b=100*(n+1)."""
        b = 100 * (n + 1)
        pfx = f"{k}_"
        P, R, C = self.P, self.R, self.C
        P(f"U{3+n}", "pdb:TPS54560", "TPS54560DDAR", FP_TPS,
          {"1": pfx + "BST", "2": "VIN", "3": pfx + "EN", "4": pfx + "RT", "5": pfx + "FB",
           "6": pfx + "COMP", "7": "GND", "8": pfx + "SW", "9": "GND"}, title,
          "C31966", "TI TPS54560 60V 5A buck", "verified")
        C(f"C{b+1}", "2.2uF 100V", "VIN", "GND", title)
        C(f"C{b+2}", "2.2uF 100V", "VIN", "GND", title)
        C(f"C{b+3}", "100nF 100V", "VIN", "GND", title)
        C(f"C{b+4}", "100nF 50V", pfx + "BST", pfx + "SW", title)
        P(f"D{b+1}", "Device:D_Schottky", "SS1060", FP_SMC, {"1": pfx + "SW", "2": "GND"}, title,
          "C2922189", "SS1060 60V 10A SMC", "verified")
        lm = "MWSA1004S-6R8MT" if lval == "6.8uH" else "MWSA1004S-100MT"
        P(f"L{2+n}", "Device:L", lval, FP_L1004, {"1": pfx + "SW", "2": net}, title,
          "C408485" if lval == "6.8uH" else "C408487", f"Sunlord {lm} (11x10mm, Isat 8.5A+)", "confirm")
        for j in range(4):
            C(f"C{b+5+j}", "22uF 25V", net, "GND", title)
        R(f"R{b+1}", rtop, net, pfx + "FB", title)
        R(f"R{b+2}", rbot, pfx + "FB", "GND", title)
        R(f"R{b+3}", "220k", pfx + "RT", "GND", title)
        R(f"R{b+4}", "220k", "VIN", pfx + "EN", title)
        R(f"R{b+5}", "12k", pfx + "EN", "GND", title)
        R(f"R{b+6}", rcomp, pfx + "COMP", pfx + "CZ", title)
        C(f"C{b+9}", "4.7nF", pfx + "CZ", "GND", title)
        C(f"C{b+10}", "47pF", pfx + "COMP", "GND", title)
        self.LED(f"D{b+2}", f"R{b+7}", net, rled, title)
        self.JP(f"JP{b+1}", pfx + "EN", "GND", "OFF", title)
        self.TP(f"TP{b+1}", net, net.lstrip("+"), title)
        self.TP(f"TP{b+2}", pfx + "SW", "SW", title)
        return b

    # ------------------------------------------------------------ one USB: hub -> audio + 2 Dynamixel buses
    def usb_block(self):
        B = "I. USB in + 4-port hub (CH334F)"
        P, R, C = self.P, self.R, self.C
        P("J10", "pdb:USB_C_USB2", "USB-C to Jetson", FP_USBC,
          {"A1": "GND", "A12": "GND", "B1": "GND", "B12": "GND", "A4": "VBUS_IN", "A9": "VBUS_IN",
           "B4": "VBUS_IN", "B9": "VBUS_IN", "A5": "USB_CC1", "B5": "USB_CC2", "A6": "USB_DP", "B6": "USB_DP",
           "A7": "USB_DM", "B7": "USB_DM", "S1": "GND"}, B, "C165948", "HRO TYPE-C-31-M-12 USB-C receptacle", "confirm")
        R("R60", "5.1k", "USB_CC1", "GND", B)
        R("R61", "5.1k", "USB_CC2", "GND", B)
        P("U11", "pdb:USBLC6", "USBLC6-2SC6", "Package_TO_SOT_SMD:SOT-23-6",
          {"1": "USB_DP", "6": "USB_DP", "3": "USB_DM", "4": "USB_DM", "5": "VBUS_IN", "2": "GND"}, B,
          "C7519", "ST USBLC6-2SC6 USB ESD", "confirm")
        P("FB1", "Device:FerriteBead", "600R", FP_FB, {"1": "VBUS_IN", "2": "V5_USB"}, B,
          "C1015", "0603 ferrite bead 600R", "confirm")
        C("C60", "10uF 25V", "V5_USB", "GND", B)
        C("C61", "100nF 50V", "V5_USB", "GND", B)
        P("U10", "pdb:CH334F", "CH334F", FP_QFN24,
          {"1": "H_OVCUR", "3": "H_XO", "4": "H_XI", "18": "GND", "5": "P4_DM", "6": "P4_DP", "7": "P3_DM", "8": "P3_DP",
           "9": "P2_DM", "10": "P2_DP", "11": "P1_DM", "12": "P1_DP", "14": "USB_DM", "15": "USB_DP",
           "19": "V5_USB", "20": "H_V33", "22": "H_LED", "25": "GND"}, B,
          "C5187527", "WCH CH334F USB 2.0 4-port hub (MTT)", "verified")
        R("R62", "10k", "H_V33", "H_OVCUR", B)
        P("Y1", "pdb:XTAL4", "12MHz", FP_XTAL, {"1": "H_XI", "3": "H_XO", "2": "GND", "4": "GND"}, B,
          "C9002", "12MHz 3225 crystal (CH334F has internal caps)", "confirm")
        C("C62", "1uF 25V", "V5_USB", "GND", B)
        C("C63", "10uF 25V", "H_V33", "GND", B)
        C("C64", "100nF 50V", "H_V33", "GND", B)
        P("D60", "Device:LED", "Green", FP_LED, {"1": "H_LED", "2": "D60_A"}, B, "C12624", "KT-0603G 0603 green LED", "basic")
        R("R63", "1k", "H_V33", "D60_A", B)
        # Ports 3/4 are unused. No unprotected external USB headers.

    def audio_block(self):
        B = "J. USB audio (CM108B) + 2x15W class-D amp (TPA3118D2) on the 12V audio rail"
        P, R, C = self.P, self.R, self.C
        P("U12", "pdb:CM108B", "CM108B", FP_LQFP48,
          {"8": "A_REG18", "9": "A_REG33", "10": "A_MODE", "14": "GND", "23": "GND", "24": "GND",
           "26": "A_VREF", "29": "A_AVDD", "30": "AUD_LOL", "31": "AUD_LOBS", "32": "AUD_LOR", "33": "GND",
           "34": "A_AVDD", "35": "V5_USB", "36": "GND", "37": "A_REG36", "41": "P1_DP", "42": "P1_DM"}, B,
          "C371347", "C-Media CM108B USB audio codec (crystal-less)", "verified")
        P("FB2", "Device:FerriteBead", "600R", FP_FB, {"1": "V5_USB", "2": "A_AVDD"}, B,
          "C1015", "0603 ferrite bead 600R", "confirm")
        C("C70", "10uF 25V", "A_AVDD", "GND", B)
        C("C71", "100nF 50V", "A_AVDD", "GND", B)
        C("C72", "100nF 50V", "V5_USB", "GND", B)
        C("C73", "4.7uF 16V", "A_REG18", "GND", B)
        C("C74", "4.7uF 16V", "A_REG33", "GND", B)
        C("C75", "4.7uF 16V", "A_REG36", "GND", B)
        C("C76", "4.7uF 16V", "A_VREF", "GND", B)
        C("C77", "4.7uF 16V", "AUD_LOBS", "GND", B)
        R("R70", "10k", "GND", "A_MODE", B)  # MODE=0 + default PWRSEL=1: 100mA bus-powered headset topology
        # line out -> amp inputs (pseudo-differential, LOBS = bias reference)
        C("C78", "1uF 25V", "AUD_LOL", "AMP_LINP", B)
        C("C79", "1uF 25V", "AUD_LOBS", "AMP_LINN", B)
        C("C80", "1uF 25V", "AUD_LOR", "AMP_RINP", B)
        C("C81", "1uF 25V", "AUD_LOBS", "AMP_RINN", B)
        P("U13", "pdb:TPA3118D2", "TPA3118D2DAPR", FP_HTSSOP32,
          {"1": "GND", "2": "AMP_SDZ", "3": "AMP_SDZ", "4": "AMP_RINP", "5": "AMP_RINN", "6": "AMP_GVDD",
           "7": "AMP_GVDD", "8": "AMP_GAIN", "9": "GND", "10": "AMP_LINP", "11": "AMP_LINN", "12": "AMP_MUTE",
           "13": "GND", "14": "GND", "15": "GND", "17": "+12V_AUD", "18": "+12V_AUD", "19": "+12V_AUD",
           "20": "AMP_BSNL", "21": "AMP_OUTNL", "22": "GND", "23": "AMP_OUTPL", "24": "AMP_BSPL", "25": "GND",
           "26": "AMP_BSNR", "27": "AMP_OUTNR", "28": "GND", "29": "AMP_OUTPR", "30": "AMP_BSPR",
           "31": "+12V_AUD", "32": "+12V_AUD", "33": "GND"}, B,
          "C46497", "TI TPA3118D2 2x30W class-D, pad down", "verified")
        R("R71", "100k", "+12V_AUD", "AMP_SDZ", B)       # FAULTZ tied to SDZ: auto-recover from faults
        R("R72", "100k", "AMP_MUTE", "GND", B)
        R("R73", "5.6k", "AMP_GAIN", "GND", B)           # 20 dB, master
        C("C82", "1uF 25V", "AMP_GVDD", "GND", B)
        C("C83", "1uF 25V", "+12V_AUD", "GND", B)        # AVCC
        for ref in ("C84", "C85"):
            C(ref, "10uF 50V", "+12V_AUD", "GND", B)
        for ref in ("C86", "C87"):
            C(ref, "100nF 50V", "+12V_AUD", "GND", B)
        self.CP("C88", "470uF 25V", "10x10", "+12V_AUD", "GND", B)
        for ref, bs, out in (("C89", "AMP_BSNL", "AMP_OUTNL"), ("C90", "AMP_BSPL", "AMP_OUTPL"),
                             ("C91", "AMP_BSNR", "AMP_OUTNR"), ("C92", "AMP_BSPR", "AMP_OUTPR")):
            C(ref, "220nF 25V", bs, out, B)
        for ref, a, b in (("L70", "AMP_OUTPR", "SPK_RP"), ("L71", "AMP_OUTNR", "SPK_RN"),
                          ("L72", "AMP_OUTPL", "SPK_LP"), ("L73", "AMP_OUTNL", "SPK_LN")):
            P(ref, "Device:L", "10uH", FP_L1004, {"1": a, "2": b}, B, "C408487",
              "Sunlord MWSA1004S-100MT (same part as the 12V rails)", "confirm")
        C("C93", "680nF 50V", "SPK_RP", "SPK_RN", B)
        C("C94", "680nF 50V", "SPK_LP", "SPK_LN", B)
        P("J13", "Connector_Generic:Conn_01x02", "SPEAKER L (screw terminal)", FP_TERM2,
          {"1": "SPK_LN", "2": "SPK_LP"}, B, "C474881", "Kefa KF301-5.0-2P", "confirm")
        P("J14", "Connector_Generic:Conn_01x02", "SPEAKER R (screw terminal)", FP_TERM2,
          {"1": "SPK_RN", "2": "SPK_RP"}, B, "C474881", "Kefa KF301-5.0-2P", "confirm")

    def dxl_block(self):
        B = "K. Dynamixel USB interface: CH342F dual serial + half-duplex buffers (U2D2 replacement)"
        P, R, C = self.P, self.R, self.C
        P("U14", "pdb:CH342F", "CH342F", FP_QFN24,
          {"2": "GND", "3": "P2_DP", "4": "P2_DM", "5": "V3_IO", "6": "S_V3", "7": "V5_USB", "8": "V5_USB",
           "12": "DXL1_RX", "13": "DXL1_TX", "15": "DXL1_TNOW", "20": "DXL0_RX", "21": "DXL0_TX",
           "23": "DXL0_TNOW", "25": "GND"}, B,
          "C2841530", "WCH CH342F USB to dual UART (half-duplex TNOW)", "verified")
        C("C95", "100nF 50V", "S_V3", "GND", B)
        C("C96", "100nF 50V", "V5_USB", "GND", B)
        C("C97", "1uF 25V", "V5_USB", "GND", B)
        R("R74", "4.7k", "DXL0_TNOW", "GND", B)   # strap: DTR0 -> TNOW0 (half duplex)
        R("R75", "4.7k", "DXL1_TNOW", "GND", B)   # strap: DTR1 -> TNOW1
        for i, (u, data) in enumerate((("U15", "DXL330_DATA"), ("U16", "DXL430_DATA"))):
            P(u, "pdb:74LVC2G241", "SN74LVC2G241DCUR", FP_VSSOP8,
              {"1": f"DXL{i}_TNOW", "2": data, "3": data, "4": "GND", "5": f"DXL{i}_TX", "6": f"DXL{i}_RX",
               "7": f"DXL{i}_TNOW", "8": "V3_IO"}, B, "C10430", "TI SN74LVC2G241 (RX buffer /OE, TX buffer OE)", "confirm")
            C(f"C{98+i}", "100nF 50V", "V3_IO", "GND", B)
            R(f"R{76+i}", "10k", "V3_IO", data, B)

        P("U17", "pdb:AP2112K", "AP2112K-3.3TRG1", "Package_TO_SOT_SMD:SOT-23-5",
          {"1": "V5_USB", "2": "GND", "3": "V5_USB", "5": "V3_IO"}, B,
          "C51118", "Diodes AP2112K-3.3TRG1, dedicated 3.3V IO regulator", "confirm")
        C("C65", "1uF 25V", "V5_USB", "GND", B)
        C("C66", "1uF 25V", "V3_IO", "GND", B)

RAILS = [
    # key, net, title, L, Rtop, Rbot, Rcomp, led R
    ("P", "+5V_PI", "C. 5V / 5A Raspberry Pi", "6.8uH", "39k", "7.5k", "12k", "2.2k"),
    ("O", "+5V_OAK", "D. 5V / 5A OAK-D depth camera", "6.8uH", "39k", "7.5k", "12k", "2.2k"),
    ("S", "+5V_SRV", "E. 5V / 5A Dynamixel XL330 x4", "6.8uH", "39k", "7.5k", "12k", "2.2k"),
    ("H", "+12V_SRV", "F. 10.8V Dynamixel XL430 x3 (unqualified)", "10uH", "30k", "2.4k", "20k", "10k"),
    ("A", "+12V_AUD", "G. 11.7V / 5A Audio amplifier", "10uH", "30k", "2.2k", "20k", "10k"),
]
