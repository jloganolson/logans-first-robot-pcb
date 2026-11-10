> Report from Google Gemini (Argon), reproduced as received apart from local paths being made repository-relative.
> It contains errors; see `docs/HANDOFF_V10_VALUE_ENGINEERED.md` for how each finding was checked. Links to earlier
> packages and removed files no longer resolve.

### Verdict: **DO NOT ORDER** (fix blockers and re-export before paying)

Do not pay for the `$289.41` cart entry (`Robot_PDB_v10_Gerbers_Y3`). While several value-engineering changes (`LM5146RGYR` commercial controller, `FB2` `GZ1608D601TF`, `100 µF` 1206 MLCC substitutions, and the `0.29 mm` USB trace widening) are electrically sound, the candidate package contains **four blockers**—including 180°-reversed XT30 connectors and a missing/rotated electrolytic capacitor in the JLCPCB placement preview, an under-dimensioned `LM5146` valley current-limit threshold (`R13 = 180 Ω`) that folds back below the 8 A Thor load and leaves no saturation margin for the downgraded `SRP1265A-100M` inductor, a `0.20 mm` drill / `0.30 mm` quote mismatch on 70 vias, and `0.40 mm` of FR-4 edge web remaining at the top M3 mounting holes (`H1`, `H2`).

---

### Summary Map to the 9 Review Questions

| # | Review Question | Disposition | Finding Ref |
|---|---|---|---|
| **1** | Thor 24.33 V / 8 A buck (`SRP1265A-100M`, `R13`, `Q3`, `LM5146RGYR`) | **BLOCKER** on `R13 = 180 Ω` + `SRP1265A-100M` saturation window; **PASS** on `LM5146RGYR` drop-in | **F1**, **F11** |
| **2** | `L1` hybrid footprint (`L_Bourns_SRP1265A_on_XAL1510_lands`) | **SHOULD FIX** — mask/paste matches Bourns `14.2 / 8.0 / 5.0 mm`, but asymmetric SMD/NSMD edges and mask under body create assembly tilt/cold-joint risk | **F5** |
| **3** | USB 2.0 HS widened pair (`0.29 mm` / `0.175 mm` gap) & `~7.6 mm` narrow remnants | **NOTE / PASS with inherited risk** — $Z_{diff} \approx 85\text{–}90\text{ }\Omega$ verified; $6.59\text{ mm}$ vs $1.05\text{ mm}$ narrow segments are electrically short ($<l_r/12$) at 480 Mbit/s | **F9** |
| **4** | `0.20 mm` via drills / `0.45 mm` lands, `0.125 mm` annular ring, `0.15 mm` clearance | **BLOCKER** — `0.20 mm` drill is **not** in JLCPCB's 4-layer free tier (`0.30 mm` min); quote selected `0.3mm/(0.4/0.45mm)` against `0.20 mm` drills in `robot_pdb-PTH.drl` | **F3** |
| **5** | `2 oz / 1 oz` $\to$ `1 oz / 0.5 oz` copper thermal consequences | **SHOULD FIX** — Thor corner (`~3.1 W`) + 36 removed vias + spoke-only thermal reliefs run hot ($\sim 85\text{–}105^\circ\text{C}$); motor passthrough (`10 A`), `TPS54560` (nominal), and `TPA3118` pass | **F6** |
| **6** | `FB2` change to `GZ1608D601TF` (`600 Ω`, `200 mA`, `450 mΩ`) on `CM108B` `A_AVDD` | **PASS (NOTE)** — feeds only `CM108B` `AVDD` ($\sim 15\text{ mA}$, $6.8\text{ mV}$ drop, $>13\times$ current margin) | **F10** |
| **7** | Lead-free HASL + JLCPCB Economic PCBA ($255^\circ\text{C}$ fixed reflow, no SPI) | **SHOULD FIX** — high bridging/open-joint risk on `U9902` (`UQFN-10`), `J10` (`USB-C`), `LQFP-48` (`U12`, `U7002`), and untented `0.20 mm` vias in QFN thermal pads | **F7** |
| **8** | Weaknesses in [`audit_v10.py`](/source/fabrication/audit_v10.py) | **SHOULD FIX** — blinded to `L1` pad geometry (`changed_fp` skip), zone fill polygons, design-rule edits, silkscreen collisions, and `H1`/`H2` edge web (`0.40 mm`) | **F4**, **F8** |
| **9** | BOM / CPL / Factory quote & placement preview inconsistencies | **BLOCKER** — `J101`/`J501` (`XT30PW-F`) rotated 180°, `J3` (`Micro-Fit`) rotated 90°, `C20` missing in DFM render & rotated `-90°`, `U9902` missing rotation offset | **F2**, **F11** |

---

### Findings (Ordered by Severity)

---

#### F1 [BLOCKER] — Thor 24.33 V / 8 A buck: `R13 = 180 Ω` causes premature valley current-limit foldback below 8 A, and `SRP1265A-100M` (`Isat = 15.5 A`) cannot span the `Q3` $R_{DS(on)}$ tolerance window if `R13` is raised
- **Evidence**:
  - Schematic components in [`robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L1779-L2269) and nets in [`robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L7618-L7635):
    - `U2`: `LM5146RGYR` (`C3188679`), `R10` (`RT`) $= 49.9\text{ k}\Omega$, `R14` $= 150\text{ k}\Omega$, `R15` $= 5.1\text{ k}\Omega$, `R13` (`T_ILIM` to `T_SW`) $= 180\text{ }\Omega$ (`C22828`), `C27` (`T_ILIM` to `GND`) $= 33\text{ pF}$ (`C1663`).
    - `Q2`, `Q3`: Infineon `BSC034N06NS` (`C534325`, 60 V SuperSO8).
    - `L1`: Bourns `SRP1265A-100M` (`C840531`, $10\text{ }\mu\text{H} \pm 20\%$, $I_{rms} = 10\text{ A}$, $I_{sat} = 15.5\text{ A}$ for 20% drop, $DCR = 13.2\text{ m}\Omega$ typ / $16.5\text{ m}\Omega$ max) replacing Coilcraft `XAL1510-103MED` ($I_{rms} = 22\text{ A}$, $I_{sat} = 26.3\text{ A}$, $DCR = 9.0\text{ m}\Omega$ typ).
- **Calculations & Reasoning**:
  1. **Operating point, ripple, and peak current**:
     - $V_{out} = 0.800\text{ V} \times (1 + 150 / 5.1) = 24.33\text{ V}$; $f_{sw} \approx \frac{10^{10}}{49900} \approx 200\text{ kHz}$.
     - At $V_{in} = 27.0\text{ V}$ (low battery): $D = 24.33/27.0 = 0.901$, $\Delta I_{L,pp} = \frac{24.33(1-0.901)}{200\text{ kHz} \times 10\text{ }\mu\text{H}} = 1.20\text{ A}_{pp}$, $I_{L,pk} = 8 + 0.60 = 8.60\text{ A}$.
     - At $V_{in} = 28.8\text{ V}$ (nominal): $D = 0.845$, $\Delta I_{L,pp} = 1.89\text{ A}_{pp}$, $I_{L,pk} = 8.94\text{ A}$.
     - At $V_{in} = 33.6\text{ V}$ (full charge): $D = 0.724$, $\Delta I_{L,pp} = 3.36\text{ A}_{pp}$ ($L = 10\text{ }\mu\text{H}$), $I_{L,pk} = 9.68\text{ A}$, $I_{L,rms} = \sqrt{8^2 + 3.36^2/12} = 8.06\text{ A}$. With $-20\%$ inductance tolerance and soft carbonyl-iron roll-off at $10\text{ A}$ ($L_{eff} \approx 7.2\text{ }\mu\text{H}$), $\Delta I_{L,pp} = 4.66\text{ A}_{pp}$ and $I_{L,pk} = 10.33\text{ A}$.
  2. **Inductor loss (`SRP1265A-100M` vs `XAL1510-103MED`)**:
     - At $I_{rms} = 8.06\text{ A}$ and $T_L = 100^\circ\text{C}$ ($\alpha_{Cu} = 0.00393\text{ K}^{-1} \implies 1.295\times$):
       $$DCR(100^\circ\text{C}) = 17.1\text{ m}\Omega\text{ (typ) to }21.4\text{ m}\Omega\text{ (max)}$$
       $$P_{Cu} = I_{rms}^2 \cdot DCR(100^\circ\text{C}) = 1.11\text{ W (typ) to }1.39\text{ W (max)}$$
     - Adding AC core loss at $200\text{ kHz}$, $\Delta I_{pp} = 3.36\text{ A}$ ($P_{core} \approx 0.25\text{–}0.35\text{ W}$) yields **$P_{L1} = 1.36\text{ W}$ (typ) to $1.74\text{ W}$ (max)**—more than $2\times$ the `XAL1510-103MED` ($0.75\text{ W}$ typ) and exceeding the `SRP1265A-100M`'s $40^\circ\text{C}$-rise power budget ($10\text{ A}^2 \times 13.2\text{ m}\Omega = 1.32\text{ W}$).
  3. **`LM5146` valley current limit with `R13 = 180 Ω` and `Q3` (`BSC034N06NS`)**:
     - `LM5146` sinks $I_{ILIM} = 100\text{ }\mu\text{A}$ typ ($90\text{–}110\text{ }\mu\text{A}$ min/max over temp) into `ILIM` (pin 11) and trips cycle-by-cycle valley current limit when `T_SW` drops below $-I_{ILIM} R_{13}$ during low-side `Q3` on-time:
       $$V_{ILIM} = 100\text{ }\mu\text{A} \times 180\text{ }\Omega = 18.0\text{ mV}\quad (16.2\text{ mV min to }19.8\text{ mV max})$$
     - For `BSC034N06NS` driven at $V_{GS} = V_{CC} = 7.5\text{ V}$, $R_{DS(on)}(25^\circ\text{C}) \approx 3.0\text{ m}\Omega$ typ ($3.7\text{ m}\Omega$ max). Even at $25^\circ\text{C}$ typical:
       $$I_{valley,lim}(25^\circ\text{C, typ}) = \frac{18.0\text{ mV}}{3.0\text{ m}\Omega} = 6.00\text{ A}$$
       $$I_{out,max}(25^\circ\text{C, typ}) = I_{valley,lim} + \frac{\Delta I_L}{2} = \begin{cases} 6.00 + 0.60 = \mathbf{6.60\text{ A}} & (V_{in} = 27.0\text{ V}) \\ 6.00 + 1.68 = \mathbf{7.68\text{ A}} & (V_{in} = 33.6\text{ V}) \end{cases}$$
     - At $T_J = 100^\circ\text{C}$ ($R_{DS(on)}$ multiplier $\approx 1.45\times \implies 4.35\text{ m}\Omega$ typ, $5.37\text{ m}\Omega$ max):
       $$I_{valley,lim}(100^\circ\text{C, typ}) = \frac{18.0\text{ mV}}{4.35\text{ m}\Omega} = 4.14\text{ A} \implies I_{out,max}(27\text{ V}) = \mathbf{4.74\text{ A}}$$
       $$I_{valley,lim}(100^\circ\text{C, worst-case}) = \frac{16.2\text{ mV}}{5.37\text{ m}\Omega} = 3.02\text{ A} \implies I_{out,max}(27\text{ V}) = \mathbf{3.62\text{ A}}$$
     - **Why this also breaks `SRP1265A-100M`**: To guarantee $I_{out} \ge 8.0\text{ A}$ at $V_{in}=27\text{ V}$ ($I_{valley} \ge 7.4\text{ A}$) under worst-case hot conditions ($R_{DS(on)}=5.37\text{ m}\Omega, I_{ILIM}=90\text{ }\mu\text{A}$), `R13` must be $\ge \frac{7.4\text{ A} \times 5.37\text{ m}\Omega}{90\text{ }\mu\text{A}} = 442\text{ }\Omega$ (e.g., $442\text{–}470\text{ }\Omega$). But with $R_{13} = 453\text{ }\Omega$, a nominal/low-$R_{DS(on)}$ `Q3` at $25^\circ\text{C}$ ($2.5\text{ m}\Omega, I_{ILIM}=110\text{ }\mu\text{A}$) at $V_{in}=33.6\text{ V}$ has $I_{valley,lim} = \frac{110\text{ }\mu\text{A} \times 453\text{ }\Omega}{2.5\text{ m}\Omega} = 19.9\text{ A}$ and peak inductor current $I_{L,pk} = 19.9 + 2.3 = \mathbf{22.2\text{ A}} > I_{sat}(\text{SRP1265A-100M}) = 15.5\text{ A}$! The v0.9 `XAL1510-103MED` ($I_{sat} = 26.3\text{ A}$) had the headroom to absorb MOSFET $R_{DS(on)}$ sensing spread; `SRP1265A-100M` does not.
  4. **`LM5146RGYR` vs `LM5146QRGYRQ1`**:
     - **Drop-in status**: **Yes.** Both share the identical `RGY` (`VQFN-20`, $3.5 \times 4.5\text{ mm}$) pinout and electrical specifications ($100\text{ V}$ rating, $0.8\text{ V}$ FB, $7.5\text{ V}$ $V_{CC}$, $100\text{ }\mu\text{A}$ $I_{ILIM}$); `-Q1` only adds AEC-Q100 Grade 1 automotive qualification.
- **Verified vs Inferred**:
  - *Verified*: Schematic values (`R10 = 49.9k`, `R13 = 180`, `R14 = 150k`, `R15 = 5.1k`, `C27 = 33pF`, `T_VCCX` grounded) from [`robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch).
  - *Inferred/Calculated*: Inductor ripple, losses, and `LM5146` / `BSC034N06NS` valley current-limit spread from TI `LM5146`, Infineon `BSC034N06NS`, and Bourns `SRP1265A-100M` datasheet parameters.
- **Recommended Action**:
  - **Minimum fix**: Change `R13` from `180 Ω` (`C22828`) to **`330 Ω`–`360 Ω`** (0603 1%), which raises $I_{valley,lim}(100^\circ\text{C, typ})$ to $7.6\text{–}8.3\text{ A}$ ($I_{out,max} \approx 8.2\text{–}9.9\text{ A}$) while keeping $25^\circ\text{C}$ typical peak current ($\sim 13.7\text{–}15.0\text{ A}$) just inside `SRP1265A-100M`'s $15.5\text{ A}$ saturation rating.
  - **Preferred fix**: Also upgrade `L1` to a $10\text{ }\mu\text{H}$ inductor with $I_{sat} \ge 20\text{ A}$ and $I_{rms} \ge 14\text{ A}$ (e.g., a $12\times 12\text{ mm}$ or $15\times 13\text{ mm}$ molded inductor on JLCPCB, or retain `XAL1510-103MED`).

---

#### F2 [BLOCKER] — `J101`/`J501` (`XT30PW-F`), `J3` (`Micro-Fit`), `C20` (`220 µF`), and `U9902` (`UQFN-10`) have severe placement/orientation errors in `CPL_JLCPCB.csv` and `factory-placement-preview.png`
- **Evidence**:
  - [`outputs/v10-order-preparation/factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png)
  - [`outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv#L17) (and lines 139–143, 297)
  - [`outputs/v10-order-preparation/package-1c92e0044935/raw-positions.csv`](/outputs/v10-order-preparation/package-1c92e0044935/raw-positions.csv#L17)
  - [`source/fabrication/export_v10.py`](/source/fabrication/export_v10.py#L14-L18) (`ROT_OFFSETS` dictionary)
- **Reasoning**:
  1. **`J101` (`RASPBERRY PI 5V`) & `J501` (`12V AUX`) — 180° reversed (`C2913282`, `AMASS_XT30PW_F_2oz`)**:
     - `AMASS_XT30PW` is omitted from `ROT_OFFSETS` in [`export_v10.py`](/source/fabrication/export_v10.py#L14-L18), exporting `Rotation = 0.0` in [`CPL_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv#L140-L143).
     - In [`factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png), both yellow XT30PW-F bodies are rotated **180° upside-down** relative to their PCB footprint outlines: their electrical pins point North off the pads, their polarity (`+`/`-`) is inverted, and their housings hang South directly over buck inductors `L2` (`(113.5, -56.0)`) and `L6` (`(113.5, -158.0)`).
  2. **`J3` (`THOR 24V`, `Molex_MicroFit_43045-0400_2oz`, `C501342`) — 90° rotated**:
     - Exported at `Rotation = 0.0` in [`CPL_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv#L139). In [`factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png) at `(205.0, -34.0)`, the 4-pin right-angle header is rotated **90°** relative to its footprint pads.
  3. **`C20` (`220uF 35V`, `CP_Elec_10x10`, `C3029711`) — missing from DFM render and rotated `-90°` (`90.0°` in CPL)**:
     - In [`raw-positions.csv`](/outputs/v10-order-preparation/package-1c92e0044935/raw-positions.csv#L17), `C20` at `(63.5, -61.0)` is at `Rot = -90.0` (`90.0` in [`CPL_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv#L17)), whereas all other eight `CP_Elec_10x10` capacitors (`C3, C4, C14, C88, C311, C411, C7111, C7112`) are at `0.0` (`180.0` in CPL).
     - In [`factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png) immediately below `L1`, **`C20` has no rendered component body and no red polarity dot at all**—its pads are completely empty in the JLCPCB DFM preview (likely rejected or dropped by JLCPCB's placement engine due to courtyard/pad overlap with `L1`'s `13.2 mm` vertical copper lands reaching `y = -49.6 mm`).
  4. **`U9902` (`TS3USB221ARSER`, `Texas_UQFN-10_1.5x2mm_P0.5mm`, `C128396`) — missing from `ROT_OFFSETS`**:
     - `Texas_UQFN-10` is not in `ROT_OFFSETS` in [`export_v10.py`](/source/fabrication/export_v10.py#L14-L18) (`Rotation = 0.0` in [`CPL_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv#L297)). Because `U9902` is a rectangular $1.5 \times 2.0\text{ mm}$ 10-pin package, a $90^\circ$ or $180^\circ$ tape-and-reel mismatch destroys the USB mux path (`J10` $\leftrightarrow$ `U10`).
- **Verified vs Inferred**:
  - *Verified*: Visual inspection of [`factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png), [`CPL_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/CPL_JLCPCB.csv), and [`export_v10.py`](/source/fabrication/export_v10.py).
  - *Inferred*: That `C20`'s disappearance in the JLCPCB preview is triggered by `L1`/`C20` overlap or DFM parser rejection.
- **Recommended Action**:
  - Add explicit rotation corrections in [`export_v10.py`](/source/fabrication/export_v10.py#L14-L18) (`'AMASS_XT30PW': 180`, `'Molex_MicroFit': 270` or `90`, and verify `U9902` pin-1 dot in JLCPCB's interactive DFM viewer).
  - Investigate why `C20` is absent in JLCPCB's DFM preview (fix `L1` copper Y-extent in **F5** and verify `C20` is populated and oriented correctly in the DFM viewer before checkout).

---

#### F3 [BLOCKER] — 70 vias with `0.20 mm` drills violate the quoted `0.3mm/(0.4/0.45mm)` no-surcharge tier; annular ring is `0.125 mm` and copper clearance is `0.15 mm`
- **Evidence**:
  - [`outputs/v10-order-preparation/factory-drills.json`](/outputs/v10-order-preparation/factory-drills.json#L3-L19) (`min_via_drill_mm: 0.2`, 70 vias at `0.20 mm` drill / `0.45 mm` pad)
  - [`outputs/v10-order-preparation/factory-quote.json`](/outputs/v10-order-preparation/factory-quote.json#L13) (`"min_via": "0.3mm/(0.4/0.45mm)"`)
  - [`outputs/v10-order-preparation/factory-quote-charge-details.png`](/outputs/v10-order-preparation/factory-quote-charge-details.png)
  - [`outputs/v10-order-preparation/audit-v10.json`](/outputs/v10-order-preparation/audit-v10.json#L88-L90) (`min_annular_mm: 0.125`)
- **Calculations & Reasoning**:
  1. **Surcharge claim check**:
     - JLCPCB's 4-layer no-surcharge tier is **`0.30 mm` minimum via drill / `0.40 mm` (`0.45 mm` recommended) minimum via diameter**. A `0.20 mm` drill falls into JLCPCB's `0.2mm/(0.3/0.35mm)` 4-layer surcharge tier.
     - The `$289.41` quote in [`factory-quote.json`](/outputs/v10-order-preparation/factory-quote.json#L13) avoided the fee only because `"0.3mm/(0.4/0.45mm)"` was manually selected on the quote form while [`robot_pdb-PTH.drl`](/outputs/v10-order-preparation/package-1c92e0044935/robot_pdb-PTH.drl) still specifies `T1C0.2000` for 70 vias (`60` footprint thermal vias on `U3–U7`, `U7003`, `U10`, `U13`, `U14` + `10` free vias; [`res1.json`](/red-team-findings/2026-11-10/evidence/res1.json#L796)).
     - After payment, JLCPCB CAM inspection will either (a) stop the order to bill the `0.20 mm` 4-layer via surcharge (exceeding the `$300` budget ceiling), or (b) enlarge the `0.20 mm` drills to `0.30 mm` inside the existing `0.45 mm` pads, which shrinks the annular ring to $(0.45 - 0.30)/2 = \mathbf{0.075\text{ mm}}$ ($2.95\text{ mil}$)—below JLCPCB's $0.125\text{ mm}$ ($5\text{ mil}$) minimum annular ring for $0.30\text{ mm}$ vias!
  2. **`0.125 mm` annular ring and `0.15 mm` clearance safety on 1 oz**:
     - With `0.20 mm` drill on `0.45 mm` pad, the annular ring is $(0.45 - 0.20)/2 = 0.125\text{ mm}$ ($4.92\text{ mil}$), which is safe on 1 oz / 0.5 oz copper *if* the `0.20 mm` drill tier is paid for.
     - `0.15 mm` ($5.9\text{ mil}$) copper-to-copper clearance is well within JLCPCB's 4-layer 1 oz capability ($0.09\text{ mm}$ / $3.5\text{ mil}$ min, $0.127\text{ mm}$ / $5\text{ mil}$ standard).
     - Note that enlarging only a via's **drill** from `0.20 mm` to `0.30 mm` does not change outer copper-to-copper clearance, and enlarging the 70 via pads from `0.45 mm` to `0.50 mm` (for a `0.10 mm` annular ring with `0.30 mm` drill) adds only $0.025\text{ mm}$ of radius.
- **Verified vs Inferred**:
  - *Verified*: Drill counts/sizes in [`factory-drills.json`](/outputs/v10-order-preparation/factory-drills.json) and quote tier in [`factory-quote.json`](/outputs/v10-order-preparation/factory-quote.json).
  - *Inferred*: JLCPCB post-payment CAM hold / surcharge enforcement per standard JLCPCB 4-layer capabilities.
- **Recommended Action**:
  - In [`build_v10.py`](/source/generator/build_v10.py#L64-L74), upsize all 70 remaining `0.20 mm` drills to **`0.30 mm` drill / `0.50 mm` (or `0.45 mm` where tight) pad** so the Gerber drill file genuinely meets the `0.3mm/(0.4/0.45mm)` no-surcharge tier.

---

#### F4 [BLOCKER] — Top-edge 4 mm crop leaves only `0.40 mm` of FR-4 web above M3 mounting holes `H1` and `H2`, and causes top-left silkscreen text overlap
- **Evidence**:
  - [`revisions/v0.10/drc.rpt`](/revisions/v0.10/drc.rpt#L11-L20) (`hole_near_hole` / edge warnings at `(16.0000, 26.0000)` and `(232.0000, 26.0000)`)
  - [`source/generator/build_v10.py`](/source/generator/build_v10.py#L46-L62) (`Y_OLD = 20.0`, `Y_NEW = 24.0`, silkscreen moved to `y = 24.6 mm`)
  - [`red-team-findings/2026-11-10/evidence/res2.json`](/red-team-findings/2026-11-10/evidence/res2.json#L491-L509)
  - [`outputs/v10-order-preparation/factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png) (top-left corner)
- **Calculations & Reasoning**:
  - `H1` at `(16.0, 26.0)` and `H2` at `(232.0, 26.0)` are `3.2 mm` NPTH M3 mounting holes (`MountingHole_3.2mm_M3`, radius $1.60\text{ mm}$).
  - Moving the top `Edge.Cuts` line from `y = 20.0 mm` to `y = 24.0 mm` reduced the hole-center-to-edge distance to $26.0 - 24.0 = 2.00\text{ mm}$ and the remaining FR-4 wall thickness to:
    $$w_{\text{FR4}} = 2.00\text{ mm} - 1.60\text{ mm} = \mathbf{0.40\text{ mm}}$$
  - Under JLCPCB routing tolerances ($\pm 0.2\text{ mm}$ outline + $\pm 0.08\text{ mm}$ NPTH), a $0.40\text{ mm}$ web will break out during V-scoring/routing or crack the moment an M3 screw/standoff ($5.5\text{–}6.0\text{ mm}$ OD, which also overhangs the top board edge by $0.75\text{–}1.0\text{ mm}$) is torqued.
  - Simultaneously, [`build_v10.py`](/source/generator/build_v10.py#L59-L62) clamped four silkscreen labels to `y = 24.6 mm`, pushing `"F1\nMOTOR 30A"` (`x = 34.0, y = 24.6`) directly on top of `"J2\nMOTOR PASSTHROUGH"` (`x = 38.0, y = 24.6`) as visibly mangled in [`factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png).
- **Verified vs Inferred**:
  - *Verified*: Exact coordinates and hole diameter in [`drc.rpt`](/revisions/v0.10/drc.rpt#L11-L20), [`res2.json`](/red-team-findings/2026-11-10/evidence/res2.json#L491-L509), and [`factory-placement-preview.png`](/outputs/v10-order-preparation/factory-placement-preview.png).
- **Recommended Action**:
  - If the chassis mounting hole positions (`H1`, `H2`) are mechanically locked (`docs/CURRENT_FUNCTIONALITY.md`), **crop the bottom edge (`y = 250.0 -> 246.0 mm`) or split the crop** if bottom holes `H3`/`H4` have margin, OR if `H1`/`H2` are not locked to an existing chassis plate, move `H1` and `H2` down by $4.0\text{ mm}$ to `y = 30.0 mm` (restoring the $4.4\text{ mm}$ FR-4 web). Reposition the `"F1"` and `"J2"` silkscreen labels so they do not overlap and stay $\ge 1.0\text{ mm}$ inside `Edge.Cuts`.

---

#### F5 [SHOULD FIX] — `L1` hybrid footprint (`L_Bourns_SRP1265A_on_XAL1510_lands`) matches Bourns mask/paste dimensions (`14.2 / 8.0 / 5.0 mm`), but creates an asymmetric SMD/NSMD joint with solder mask under the inductor body
- **Evidence**:
  - [`revisions/v0.10/kicad/Robot_PDB.pretty/L_Bourns_SRP1265A_on_XAL1510_lands.kicad_mod`](/revisions/v0.10/kicad/Robot_PDB.pretty/L_Bourns_SRP1265A_on_XAL1510_lands.kicad_mod#L1-L14)
  - [`source/generator/build_v10.py`](/source/generator/build_v10.py#L14-L30)
- **Calculations & Reasoning**:
  - **Dimension verification against Bourns `SRP1265A` recommended layout (`14.2 mm` outer span, `8.0 mm` inner gap, `5.0 mm` pad width)**:
    - The mask/paste pads `(at ±5.55 0) (size 3.1 5.0) (layers "F.Cu" "F.Mask" "F.Paste")` give:
      - Outer X span: $2 \times (5.55 + 3.1/2) = \mathbf{14.20\text{ mm}}$ (exact match).
      - Inner X gap: $2 \times (5.55 - 3.1/2) = \mathbf{8.00\text{ mm}}$ (exact match).
      - Y pad width: $\mathbf{5.00\text{ mm}}$ (exact match).
  - **Assembly risks from the retained `3.43 × 13.2 mm` copper lands `(at ±5.425 0)`**:
    1. **3-edge SMD / 1-edge NSMD asymmetry**: On the inner heel (`±4.00 mm` mask vs `±3.71 mm` copper, `0.29 mm` overlap) and both Y sides (`±2.50 mm` mask vs `±6.60 mm` copper, `4.10 mm` overlap), the joint is **solder-mask-defined (SMD)**. On the outer toe (`±7.10 mm` mask vs `±7.14 mm` copper), the copper extends only **$0.04\text{ mm}$ ($40\text{ }\mu\text{m}$)** beyond the mask edge—smaller than JLCPCB's $\pm 0.05\text{–}0.075\text{ mm}$ solder-mask registration tolerance—so the toe will randomly transition between SMD and NSMD across the pad width.
    2. **Solder mask step under the inductor body/terminations**: The `SRP1265A` body ($13.5 \times 12.5\text{ mm}$) sits over the $0.29\text{ mm} \times 12.5\text{ mm}$ strips of solder mask covering the inner edges of the $1\text{ oz}$ copper pads (`x = ±3.71 to ±4.00 mm`), creating a $\sim 25\text{ }\mu\text{m}$ raised ridge under the package bottom that can rock or tilt the inductor during reflow.
    3. **Excessive thermal mass during Economic $255^\circ\text{C}$ reflow**: Each $3.43 \times 13.2\text{ mm}$ (`45.3 mm²`) copper pad is $2.92\times$ the area of the $3.1 \times 5.0\text{ mm}$ (`15.5 mm²`) paste window, drawing heat out of the solder paste during reflow.
- **Verified vs Inferred**:
  - *Verified*: Exact pad coordinates and sizes in [`L_Bourns_SRP1265A_on_XAL1510_lands.kicad_mod`](/revisions/v0.10/kicad/Robot_PDB.pretty/L_Bourns_SRP1265A_on_XAL1510_lands.kicad_mod).
  - *Inferred*: Reflow wetting/coplanarity risk from IPC-7351B / Bourns `SRP1265A` mechanical dimensions.
- **Recommended Action**:
  - Replace the two-pad-per-terminal trick with a **single NSMD copper/mask/paste pad per terminal** of `(at ±5.55 0) (size 3.1 5.0) (layers "F.Cu" "F.Mask" "F.Paste")`, and add short copper polygon/trace tapers to bridge from `(±5.55, 0)` to the existing `T_SW` and `24V_THOR` traces (this also resolves any courtyard/pad conflict with `C20` in **F2**).

---

#### F6 [SHOULD FIX] — Copper weight halving (`2 oz / 1 oz` $\to$ `1 oz / 0.5 oz`) + 36 deleted vias + spoke-only thermal reliefs cause elevated temperatures (`~85–105 °C`) in the Thor LM5146 stage (`U2, Q2, Q3, L1`)
- **Evidence**:
  - [`docs/HANDOFF_V10_VALUE_ENGINEERED.md`](/docs/HANDOFF_V10_VALUE_ENGINEERED.md#L27-L30) (`1 oz` outer / `0.5 oz` inner)
  - [`source/generator/build_v10.py`](/source/generator/build_v10.py#L76-L86) (36 deleted vias: 14 `GND`, 22 `BATT_IN`)
  - [`red-team-findings/2026-11-10/evidence/res1.json`](/red-team-findings/2026-11-10/evidence/res1.json#L791-L800) and [`res2.json`](/red-team-findings/2026-11-10/evidence/res2.json#L510-L530) (via counts per IC, zone thermal reliefs)
- **Calculations & Reasoning**:
  - Halving copper thickness on all four layers (`70/35/35/70 µm` $\to$ `35/17.5/17.5/35 µm`) cuts total copper thickness from $210\text{ }\mu\text{m}$ to $105\text{ }\mu\text{m}$, **doubling DC sheet resistance** ($0.59\text{ m}\Omega/\square$ on `1 oz`, $1.18\text{ m}\Omega/\square$ on `0.5 oz` at $75^\circ\text{C}$) and **halving in-plane lateral thermal conductance ($k \cdot t$)**.
  1. **10 A Motor Passthrough (`J1 -> F1 -> J2`, plus `U1` on `BATT_IN`)**:
     - `F1` (`FUSE_MOTOR`) to `J2` uses a $7.3\text{ mm}$ pour on `F.Cu` in parallel with an $11.2\text{ mm}$ pour on `B.Cu` (stitched by 16 vias of $0.40\text{ mm}$ drill at `F1`). At $1\text{ oz}$, total cross-section is $18.5\text{ mm} \times 0.035\text{ mm} = 0.648\text{ mm}^2$ ($R \approx 1.1\text{ m}\Omega$ over $35\text{ mm}$).
     - At $10\text{ A}$ continuous: trace loss is $10^2 \times 0.0011 = 0.11\text{ W}$; `U1` (`SQJ148EP`, $5.1\text{ m}\Omega$ max) dissipates $\sim 0.51\text{ W}$ (plus $8\text{ A}$ Thor input $= 18\text{ A}$ total battery current through `U1` $\implies P_{U1} = 18^2 \times 0.0045 \approx 1.46\text{ W}$ across 14 vias). Safe for $10\text{ A}$ continuous motor load.
  2. **`LM5146` 24.33 V / 8 A Thor Stage (`U2`, `Q2`, `Q3`, `L1`)**:
     - At $V_{in} = 33.6\text{ V}$, $I_{out} = 8\text{ A}$, $f_{sw} = 200\text{ kHz}$:
       - High-side `Q2` (`BSC034N06NS`): $P_{cond} = 0.20\text{ W}$, $P_{sw+Qoss} \approx 0.44\text{ W} \implies P_{Q2} \approx 0.64\text{ W}$ (only **5 thermal vias** at $0.30\text{ mm}$ drill).
       - Low-side `Q3` (`BSC034N06NS`): $P_{cond} = 0.08\text{ W}$, $P_{dt+Qrr} \approx 0.32\text{ W} \implies P_{Q3} \approx 0.40\text{ W}$ (only **4 thermal vias** at $0.30\text{ mm}$ drill).
       - Controller `U2` (`LM5146RGYR`, `T_VCCX` grounded so internal LDO drops $33.6\text{ V} \to 7.5\text{ V}$ at $I_Q + f_{sw} Q_{g,tot} \approx 13.4\text{ mA}$): $P_{U2} \approx 0.45\text{ W}$.
       - Inductor `L1` (`SRP1265A-100M`): $P_{L1} \approx 1.36\text{–}1.74\text{ W}$.
       - **Total stage dissipation**: **$2.85\text{–}3.23\text{ W}$** concentrated in a $\sim 35 \times 30\text{ mm}$ corner (`x = 55–85, y = 24–55`), where all zone connections use `0.50 mm` spoke thermal reliefs (`0` solid zone pads; [`res2.json`](/red-team-findings/2026-11-10/evidence/res2.json#L510-L530)). With $1\text{ oz}/0.5\text{ oz}$ planes, local PCB temperature will reach $\sim 85\text{–}105^\circ\text{C}$ in still air, directly exacerbating the `Q3` $R_{DS(on)}$ current-limit foldback in **F1**.
  3. **Six `TPS54560DDAR` Regulators (`U3–U7`, `U7003`, $f_{sw} \approx 600\text{ kHz}$)**:
     - On `1 oz / 0.5 oz` with 6 in-pad `0.20 mm` vias (`TI_SO-PowerPAD-8_ThermalVias`), effective $R_{\theta JA}$ rises from $\sim 36^\circ\text{C/W}$ to $\sim 48^\circ\text{C/W}$.
     - At typical robot loads (`U3` Pi 5 at $3\text{ A}$: $P_{U3} \approx 0.91\text{ W}$, `D101` $\approx 1.28\text{ W}$, $\Delta T_J \approx 44^\circ\text{C}$; `U6`/`U7`/`U7003` at $1\text{–}2\text{ A}$: $P_U < 0.6\text{ W}$), thermal margins remain acceptable. However, continuous $4.5\text{–}5\text{ A}$ servo stall on `U5` (`10V_XL430` at $600\text{ kHz}$: $P_{U5} \approx 1.85\text{ W}$, `D301` $\approx 1.6\text{ W}$, `L4` $\approx 1.1\text{ W}$) will push `U5` $T_J > 125^\circ\text{C}$ within $\sim 15\text{–}30\text{ s}$.
  4. **`TPA3118D2DAPR` Audio Amplifier (`U13`)**:
     - Powered from `12V_AUDIO` (`12 V`) with **15 in-pad thermal vias**. At $2\text{–}10\text{ W}$ class-D audio output ($\eta \approx 88\%$), $P_{U13} \approx 0.3\text{–}1.2\text{ W}$ and $\Delta T_J < 45^\circ\text{C}$ on `1 oz / 0.5 oz`.
- **Verified vs Inferred**:
  - *Verified*: Via counts, trace/zone widths, and thermal-relief settings in [`res1.json`](/red-team-findings/2026-11-10/evidence/res1.json) and [`res2.json`](/red-team-findings/2026-11-10/evidence/res2.json); schematic values in [`robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch).
  - *Inferred/Calculated*: Component power dissipation and $R_{\theta JA}$ scaling from `2 oz / 1 oz` to `1 oz / 0.5 oz`.
- **Recommended Action**:
  - Set `zone_connection = solid` (or widen thermal spokes to $\ge 0.8\text{ mm}$) on the high-current pads of `Q2`, `Q3`, `L1`, `U1`, `F1`, and `D101–D501`, and add 6–10 `0.30/0.50 mm` `GND`/`BATT_IN` stitching vias around `Q2`, `Q3`, and `U2`.

---

#### F7 [SHOULD FIX] — Lead-free HASL + JLCPCB Economic PCBA (fixed $255^\circ\text{C}$ reflow, no SPI) poses bridging and open-joint risks on `U9902` (`UQFN-10`), `J10` (`USB-C`), `LQFP-48` (`U12`, `U7002`), and QFN thermal pads with untented vias
- **Evidence**:
  - [`outputs/v10-order-preparation/factory-quote.json`](/outputs/v10-order-preparation/factory-quote.json#L11) (`"surface_finish": "LeadFree HASL"`, `"pcba_type": "Economic"`, `"via_covering": "Tenting Vias"`)
  - [`outputs/v10-order-preparation/package-1c92e0044935/BOM_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/BOM_JLCPCB.csv) (`U9902` `UQFN-10_1.5x2mm_P0.5mm`, `U2` `VQFN-20`, `U10`/`U14` `QFN-24`, `U12`/`U7002` `LQFP-48`, `U15`/`U16` `VSSOP-8`, `J10` `TYPE-C-31-M-12`)
- **Reasoning**:
  1. **Surface planarity on `0.5 mm` pitch leadless and fine-pitch packages**: Lead-free HASL leaves an uneven solder dome ($1\text{–}40\text{ }\mu\text{m}$ height variation), especially between large central thermal pads (`U2`, `U10`, `U14`) and small peripheral lands, and across `U9902` (`TS3USB221ARSER`, $1.5 \times 2.0\text{ mm}$ UQFN-10 with $0.20 \times 0.40\text{ mm}$ lands and no center pad). Without Solder Paste Inspection (SPI) in Economic PCBA, paste volume variation on domed HASL pads elevates the risk of open peripheral pins on `U9902`/`U10`/`U14` and solder bridges on `0.5 mm` pitch `U12`, `U7002`, and `J10` (`TYPE-C-31-M-12`).
  2. **Solder wicking down open `0.20/0.30 mm` vias inside exposed thermal pads**: `U3–U7`, `U7003`, `U10`, `U13`, and `U14` place open PTH thermal vias directly inside their exposed center pads (`TI_SO-PowerPAD-8_ThermalVias`, `QFN-24-1EP`, `HTSSOP-32-1EP`). Under `Tenting Vias` (which only tents vias without solder-mask openings, leaving in-pad vias open on top and only tented on bottom), solder wicks into the via barrels during the fixed $255^\circ\text{C}$ reflow, causing center-pad voiding or package tilt.
- **Verified vs Inferred**:
  - *Verified*: Package types in [`BOM_JLCPCB.csv`](/outputs/v10-order-preparation/package-1c92e0044935/BOM_JLCPCB.csv) and process settings in [`factory-quote.json`](/outputs/v10-order-preparation/factory-quote.json).
  - *Inferred*: Yield risk for $n=2$ Economic PCBA prototypes.
- **Recommended Action**:
  - Since this is a 2-board prototype where ENIG ($+\$43$) would break the $\$300$ budget, keep Lead-Free HASL if required for cost **only after** fixing `L1`'s oversized copper pads (**F5**), and perform a mandatory microscope + continuity/diode-drop inspection on `U9902`, `J10`, `U2`, `U10`, `U14`, `U12`, and `U7002` before applying battery or USB power.

---

#### F8 [SHOULD FIX] — Structural blind spots in `audit_v10.py` allow pad-geometry bugs, zone shrinkage, clearance-rule relaxation, silkscreen overlaps, and edge-web violations to pass silently
- **Evidence**:
  - [`source/fabrication/audit_v10.py`](/source/fabrication/audit_v10.py#L1-L156)
  - [`outputs/v10-order-preparation/audit-v10.json`](/outputs/v10-order-preparation/audit-v10.json#L1-L130)
- **Verified Blind Spots in `audit_v10.py`**:
  1. **`changed_fp` completely skips pad geometry, mask, and paste checks ([`audit_v10.py` line 41](/source/fabrication/audit_v10.py#L41))**:
     - For `L1`, `audit_v10.py` checks only `{q.GetNumber(): q.GetNetname()}` (`{"1": "T_SW", "2": "24V_THOR"}`) and executes `continue`, ignoring pad count (`4` vs `2`), pad coordinates, copper dimensions, mask openings, and paste openings.
  2. **Zone check compares only boundary outlines, not poured copper islands ([`audit_v10.py` line 113](/source/fabrication/audit_v10.py#L113))**:
     - `Check 9` compares `outline(z)` (the un-filled zone boundary polygon) rather than `z.GetFilledPolysList()`. It missed that `In1.Cu` (`GND`) and `In2.Cu` (`BATT_IN`) lost $1526\text{ mm}^2$ of poured copper each and that wider pullbacks formed around the widened USB traces ([`res1.json`](/red-team-findings/2026-11-10/evidence/res1.json#L789)).
  3. **Removed stitching vias are exempted by list without checking plane connectivity or return-path impact ([`audit_v10.py` lines 67–72](/source/fabrication/audit_v10.py#L67-L72))**:
     - The 36 deleted `GND`/`BATT_IN` vias in `derivation.json` are simply filtered out of the comparison (`vkey(v) not in rem`).
  4. **No check on project design rules (`.kicad_pro`) or `drc.rpt` warning count**:
     - Relaxing global copper clearance from `0.20 mm` to `0.15 mm` in [`build_v10.py`](/source/generator/build_v10.py#L140-L157) is invisible to `audit_v10.py`, even though `build_v10.py`'s USB widening loop used `not drc()` under that lowered rule.
  5. **Zero inspection of `F.SilkS`/`B.SilkS` graphic items or hole-to-edge web**:
     - `board.GetDrawings()` is only filtered for `Edge.Cuts` ([`audit_v10.py` line 104](/source/fabrication/audit_v10.py#L104)), missing the `"F1"`/`"J2"` silkscreen collision and the $0.40\text{ mm}$ FR-4 wall at `H1`/`H2` (**F4**).
  6. **Zero inspection of exported CPL rotations (`CPL_JLCPCB.csv`)**:
     - `audit_v10.py` stops at `.kicad_pcb` and never audits `CPL_JLCPCB.csv` or `ROT_OFFSETS` in `export_v10.py` (**F2**).
- **Recommended Action**:
  - Extend `audit_v10.py` to assert: (a) minimum hole-to-`Edge.Cuts` wall $\ge 1.5\text{ mm}$, (b) zero overlapping silkscreen bounding boxes and $\ge 0.5\text{ mm}$ clearance to `Edge.Cuts`, (c) filled zone island count and area delta, and (d) explicit `ROT_OFFSETS` coverage for every non-passive footprint in `CPL_JLCPCB.csv`.

---

#### F9 [NOTE] — USB 2.0 High-Speed pair (`0.29 mm` width / `0.175 mm` gap) achieves ~85–90 Ω differential impedance; the ~7.6 mm narrow unequal remnants are electrically short at 480 Mbit/s
- **Evidence**:
  - [`source/generator/build_v10.py`](/source/generator/build_v10.py#L97-L115)
  - [`outputs/v10-order-preparation/audit-v10.json`](/outputs/v10-order-preparation/audit-v10.json#L20-L53)
  - [`red-team-findings/2026-11-10/evidence/solve.py`](/red-team-findings/2026-11-10/evidence/solve.py#L1-L40)
  - [`docs/V09_USB_PROTOTYPE_REVIEW.md`](/docs/V09_USB_PROTOTYPE_REVIEW.md#L22-L67)
- **Calculations & Reasoning**:
  1. **Differential impedance on `JLC04161H-7628` ($w = 0.290\text{ mm}, s = 0.175\text{ mm}, h = 0.2104\text{ mm}, t = 0.035\text{ mm}, \varepsilon_r = 4.4$)**:
     - Effective width $w_e = w + \frac{t}{\pi}(1 + \ln(2h/t)) = 0.329\text{ mm}$ ($w_e/h = 1.563$, $s/h = 0.832$).
     - Effective permittivity $\varepsilon_{eff} = \frac{4.4+1}{2} + \frac{4.4-1}{2}(1 + 12 h / w_e)^{-1/2} = 3.277$.
     - Single-ended microstrip impedance (Hammerstad-Jensen):
       $$Z_0 = \frac{120\pi}{\sqrt{3.277}\,[1.563 + 1.393 + 0.667\ln(1.563 + 1.444)]} = \mathbf{56.4\text{ }\Omega}$$
     - Edge-coupled differential impedance ($s/h = 0.832$):
       $$Z_{diff} \approx 2 Z_0 \left(1 - 0.48 e^{-0.96 s/h}\right) = 112.8 \times 0.784 = \mathbf{88.4\text{ }\Omega}\text{ bare}\quad(\mathbf{85\text{–}87\text{ }\Omega}\text{ with solder mask})$$
     - This confirms the handoff's **85–92 Ω estimate is accurate** and well inside the USB 2.0 $90\text{ }\Omega \pm 15\%$ ($76.5\text{–}103.5\text{ }\Omega$) window—a major improvement over v0.9's $0.165\text{ mm}$ traces ($Z_{diff} \approx 106\text{–}108\text{ }\Omega$).
  2. **Remaining narrow, unequal-width segments (`6.587 mm` on `HUB_UP_DP` vs `1.047 mm` on `HUB_UP_DM`)**:
     - Because [`build_v10.py`](/source/generator/build_v10.py#L106-L115) widened each track segment independently (`s.SetWidth(w29); if drc(): revert`), `HUB_UP_DP` reverted to $0.165\text{ mm}$ over $6.587\text{ mm}$ near pad entries while its partner `HUB_UP_DM` reverted over only $1.047\text{ mm}$ (leaving $5.54\text{ mm}$ of asymmetric $0.165\text{ mm}$ vs $0.290\text{ mm}$ pairing).
     - At USB 2.0 High-Speed ($480\text{ Mbit/s}$, rise time $t_r \ge 500\text{ ps}$, propagation velocity $v_p = c/\sqrt{3.28} \approx 165\text{ mm/ns}$), the rising-edge spatial length is $l_r = v_p t_r \approx 82.5\text{ mm}$.
     - The $6.59\text{ mm}$ segment has a one-way propagation delay of $t_{seg} = 6.59 / 165 = 40\text{ ps} \approx 0.08\,t_r$. For a distributed discontinuity with $2 t_{seg} < t_r$, the peak reflection is scaled by $2 t_{seg}/t_r$:
       $$\Gamma_{pk} \approx \frac{107\text{ }\Omega - 88\text{ }\Omega}{107\text{ }\Omega + 88\text{ }\Omega} \times \frac{2 \times 40\text{ ps}}{500\text{ ps}} \approx 0.097 \times 0.16 = \mathbf{1.6\%}$$
       and the propagation skew introduced by the $\Delta \varepsilon_{eff} \approx 0.11$ asymmetry over $5.54\text{ mm}$ is $\Delta t \approx 0.6\text{ ps}$.
     - Therefore, the $6.59\text{ mm}$ narrow remnants are **not a standalone signal-integrity blocker**; the dominant USB risks remain the inherited v0.9 layout items documented in [`V09_USB_PROTOTYPE_REVIEW.md`](/docs/V09_USB_PROTOTYPE_REVIEW.md#L22-L67) ($134.3\text{ mm}$ total length across `J10 -> U11 -> U9902 -> U10`, $5.47\text{ mm}$ `VBUS_CONN` proximity, and the $1.45\text{ mm}$ `In1.Cu` `GND` slot under `HUB_UP_DM/DP`).
- **Verified vs Inferred**:
  - *Verified*: Exact track lengths and widths per net in [`audit-v10.json`](/outputs/v10-order-preparation/audit-v10.json#L20-L53) and [`solve.py`](/red-team-findings/2026-11-10/evidence/solve.py).
  - *Inferred/Calculated*: Microstrip $Z_{diff}$ and time-domain reflection scaling at $t_r = 500\text{ ps}$.
- **Recommended Action**:
  - Optional cleanup: in [`build_v10.py`](/source/generator/build_v10.py#L106-L115), lock coupled segment pairs together so that if either `DP` or `DM` reverts to `0.165 mm`, its opposite partner segment also stays `0.165 mm` (preserving symmetry).

---

#### F10 [NOTE] — `FB2` change to `GZ1608D601TF` (`600 Ω`, `200 mA`, `450 mΩ`) on `CM108B` `A_AVDD` is completely safe
- **Evidence**:
  - [`revisions/v0.10/kicad/robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L4188-L4202) and [#L7812-L7819](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L7812-L7819)
- **Calculations & Reasoning**:
  - In [`robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L7812-L7819), `U12` (`CM108B`) digital supply (`DVDD`, pin 35) is powered directly from `V5_USB`, while `FB2` (`Sunlord GZ1608D601TF`, `C1002`, $600\text{ }\Omega$ at $100\text{ MHz}$, $I_{max} = 200\text{ mA}$, $R_{DC} \le 0.45\text{ }\Omega$) feeds **only** the `A_AVDD` net (`U12` analog pins 40 and 42 + decoupling capacitors `C53 = 100 nF` and `C54 = 10 µF`). The downstream class-D amplifier `U13` (`TPA3118D2`) is powered separately from `12V_AUDIO`.
  - `CM108B` analog supply current is $I_{AVDD} \approx 10\text{–}15\text{ mA}$ ($<8\%$ of the $200\text{ mA}$ rating), producing a negligible DC drop of $\Delta V = 15\text{ mA} \times 0.45\text{ }\Omega = \mathbf{6.75\text{ mV}}$ and power dissipation of $\mathbf{0.10\text{ mW}}$.
- **Verified vs Inferred**:
  - *Verified*: Exact `A_AVDD` net connectivity in [`robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L7815-L7818).
  - *Inferred/Calculated*: `CM108B` `AVDD` current draw from datasheet specification.
- **Recommended Action**:
  - None required; `GZ1608D601TF` (`C1002`) is acceptable as-is.

---

#### F11 [NOTE] — Schematic `MPN` property for `U2` still says `LM5146-Q1`, and top-level docs (`README.md`, `CURRENT_FUNCTIONALITY.md`) still describe `v0.9`
- **Evidence**:
  - [`revisions/v0.10/kicad/robot_pdb.kicad_sch`](/revisions/v0.10/kicad/robot_pdb.kicad_sch#L1788) (`(property "MPN" "TI LM5146-Q1 100V sync buck controller")`)
  - [`source/generator/build_v10.py`](/source/generator/build_v10.py#L40) (`PART_CHANGES['U2']` updates `'val'` and `'lcsc'`, omitting `'mpn'`)
  - [`README.md`](/README.md#L5-L9) and [`docs/CURRENT_FUNCTIONALITY.md`](/docs/CURRENT_FUNCTIONALITY.md#L1-L45)
- **Recommended Action**:
  - Add `'mpn'` update for `U2` in [`build_v10.py`](/source/generator/build_v10.py#L40) and update [`README.md`](/README.md) once the `v0.10` blockers (**F1–F4**) are resolved.
