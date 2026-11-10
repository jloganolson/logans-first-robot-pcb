#!/usr/bin/env python3
"""Analytical preflight for the DDSM350 companion supply. No KiCad dependency.

This evaluates explicitly declared assumptions. A passing arithmetic check is
not evidence of loop stability, actual regenerative current, thermal performance
or an unpublished motor voltage rating. Run with --json for machine-readable data.
"""
import argparse
import cmath
import itertools
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generator"))
from motor_addon import PARTS, RELEASE_HOLDS, DATASHEETS


def buck_voltage(ref=0.8, rt=150000.0, rb=5100.0, extra=470.0):
    return ref * (1 + rt / (rb + extra))


def clamp_voltage(vref=3.3, rt=60400.0, rb=10000.0, rh=1000000.0,
                  output=0.1, offset=0.0):
    # KCL at comparator IN+: motor/Rt + output/Rh = threshold*(1/Rt+1/Rb+1/Rh).
    return (vref + offset) * (1 + rt / rb + rt / rh) - output * rt / rh


def loop_sweep(rt=150000., rb=5570., vout=22.34,
               downstream=(0., .0016, .0024), load_limits=(.1, 10.), rt_tolerance=.0025):
    """TI section9.1.3 averaged plant + exact compensator nodal impedances.

    Includes finite one-pole EA(assumed0.5/1/3MHz GBW vs6.5MHz typical),
    one-full-switching-period delay (conservative approximation), both diode
    states, L +/-20%, bulk +/-20%, ESR range and compensation C +/-25%.
    ESR is an exploration range, NOT a guaranteed cold/hot part limit.
    Parasitics, diode servo dynamics, sampled current-limit and motor input
    impedance are absent. This is a reproducible screening calculation.
    """
    frequencies = [10**(1+j*4/600) for j in range(601)]
    plant_corners = list(itertools.product((8e-6, 12e-6), (.0008, .0012), downstream, (.005, .030), load_limits))
    # All endpoint combinations for three compensation capacitors and R14,
    # R16/R17. C0G C25 uses5%; X7R C24/C26 use25% including temperature.
    # R16/R17 use2%, R14 uses0.25% including temperature. This still is
    # not a proof of actual frequency/temperature-dependent capacitor limits.
    comp_corners = itertools.product((.75,1.25),(.95,1.05),(.75,1.25),(.98,1.02),(.98,1.02),(1-rt_tolerance,1+rt_tolerance),(.5e6,1e6,3e6,6.5e6))
    compensators = []
    for c1f,c2f,c3f,r1f,r2f,rtf,gbw in comp_corners:
        values=[]
        for f in frequencies:
            s=2j*math.pi*f
            zfeedback=1/(1/(10000*r1f+1/(s*47e-9*c1f))+s*100e-12*c2f)
            zinput=1/(1/(rt*rtf)+1/(3300*r2f+1/(s*2.2e-9*c3f)))
            amp=2*math.pi*gbw/s
            values.append(amp/zinput/(amp/zfeedback+1/zinput+1/zfeedback+1/rb))
        compensators.append(((c1f,c2f,c3f,r1f,r2f,rtf,gbw),values))
    min_margin, crossover_min, crossover_max = 999., float("inf"), 0.
    crossings, worst_case, profiles = 0, None, 0
    for inductance, prebulk, motorbulk, esr, load in plant_corners:
        plants=[]
        for f in frequencies:
            s=2j*math.pi*f
            output_y=load/vout
            for capacitance,resistance in ((220e-6,.060),(20e-6,.003),(prebulk,esr),(motorbulk,esr)):
                output_y+=s*capacitance/(1+s*capacitance*resistance)
            output_z=1/output_y
            plants.append(15*output_z/(output_z+.010+s*inductance)*cmath.exp(-s/200000))
        for factors, comp_response in compensators:
            profiles += 1
            previous_gain, previous_phase = None, None
            for f,plant,compensator in zip(frequencies,plants,comp_response):
                loop=compensator*plant
                gain = 20*math.log10(abs(loop))
                phase = math.degrees(cmath.phase(loop))
                if previous_phase is not None:
                    while phase-previous_phase > 180: phase -= 360
                    while phase-previous_phase < -180: phase += 360
                if previous_gain is not None and gain < 0 <= previous_gain:
                    crossings += 1
                    margin = 180+phase
                    crossover_min, crossover_max = min(crossover_min,f), max(crossover_max,f)
                    if margin < min_margin:
                        min_margin = margin
                        worst_case = dict(L_H=inductance, prebulk_F=prebulk, motorbulk_F=motorbulk, bulk_ESR_ohm=esr, load_A=load, factors_C24_C25_C26_R16_R17_R14_GBW=factors, crossover_Hz=f)
                previous_gain, previous_phase = gain, phase
    return dict(model="LM5146-Q1 TI Tables9-2/9-3; exact compensator impedances, assumed finite EA and PWM delay", profiles=profiles, downward_crossings=crossings, minimum_phase_margin_deg=min_margin, crossover_Hz_range=[crossover_min,crossover_max], worst_case=worst_case, screening_pass=min_margin>=50 and crossings>=profiles, qualification="Bench loop injection and startup/load-step tests remain required. No model of ideal-diode servo/nonlinear transitions or actual motor negative incremental input impedance.")


def calculate():
    vout = buck_voltage()
    # IC feedback +/-1%; precision divider 0.1%+25ppm/C over +/-60 C;
    # 470R ordinary part conservative +/-1%+200ppm/C over +/-60 C.
    tprec, textra = .001 + 25e-6 * 60, .01 + 200e-6 * 60
    buck_corners = [buck_voltage(.8 * vr, 150000 * rt, 5100 * rb, 470 * rx)
                    for vr, rt, rb, rx in itertools.product((.99, 1.01), (1-tprec, 1+tprec), (1-tprec, 1+tprec), (1-textra, 1+textra))]
    ordinary_max = buck_voltage(.808, 151500, 5049, 465.3)
    # REF3333 initial +/-0.15%, drift <=30ppm/C; comparator +/-4mV
    # offset specification is at midrail. Add 2mV allowance for common-mode,
    # hysteresis uncertainty, bias/leakage and model error; VERIFY by measurement.
    tref = .0015 + 30e-6 * 60
    rtolerance = .001 + 25e-6 * 60
    def trip_range(outputs):
        vals = [clamp_voltage(3.3*vr, 60400*rt, 10000*rb, 1e6*rh, out, vos)
                for vr, rt, rb, rh, out, vos in itertools.product((1-tref, 1+tref), (1-rtolerance, 1+rtolerance), (1-rtolerance, 1+rtolerance), (1-rtolerance, 1+rtolerance), outputs, (-.006, .006))]
        return [min(vals), max(vals)]
    on_range, off_range = trip_range((0, .225)), trip_range((4.73, 5.1))
    # 5mR low-side source shunt / 649R ILIM candidate, including +60 C TCR.
    shunt_tol = .01 + 50e-6 * 60
    rilim_tol = .01 + 100e-6 * 60
    valley_min = (90e-6*649*(1-rilim_tol)-.0035)/(.005*(1+shunt_tol))
    valley_max = (110e-6*649*(1+rilim_tol)+.008)/(.005*(1-shunt_tol))
    valley_typ = (100e-6*649+.002)/.005
    vinmax, fsw, inductance = 33.6, 200000., 10e-6
    ripple_max = vout*(1-vout/vinmax)/(.8*inductance*fsw)
    ripple_nom = vout*(1-vout/vinmax)/(inductance*fsw)
    # At lower input/headroom ripple approaches zero. Do not claim 12 A
    # guaranteed over the full input range simply by adding max ripple/2.
    ipeak_target = 12+ripple_max/2
    max_peak_trip = valley_max+ripple_max
    c_nom, c_min = .002, .0016
    delta_hyst = clamp_voltage(output=.1)-clamp_voltage(output=4.9)
    dump_r = 3.3
    dump_i = clamp_voltage()/dump_r
    dump_power = clamp_voltage()**2/dump_r
    # Budget, not guaranteed response: 20us + 9mR step impedance at 20 C.
    dynamic_budget = dump_i * 20e-6/c_min + dump_i*.009
    mass, velocity = 20*.45359237, 3*.44704
    energy = .5*mass*velocity**2
    illustrative_energy, stop_time = 20., .5
    # Uniform deceleration gives a triangular kinetic-power profile.
    max_stop_power = 2*illustrative_energy/stop_time
    max_chop_hz = dump_i/(4*c_min*delta_hyst)
    qgate = 11.1e-9  # CSD18534Q5A maximum at 4.5V; budget 25nC at 5.1V.
    gate_charge_budget = 25e-9
    igate_budget = gate_charge_budget*max_chop_hz
    total_control_budget = .003 + igate_budget  # conservative 3mA electronics budget; measure.
    ldo_loss = (24-4.9)*total_control_budget
    # Power stage LC frequencies demonstrate why original compensation needs redesign.
    c_original, c_forward = 1260e-6, 3260e-6
    resonance_original = 1/(2*math.pi*math.sqrt(inductance*c_original))
    resonance_new = 1/(2*math.pi*math.sqrt(inductance*c_forward))
    softstart_nominal = .8*220e-9/10e-6
    # X7R SS cap ±10% initial +15% temp; IC SS current8.5..12uA,
    # 0.8V reference1% and tracking offset included conservatively as15mV.
    softstart_minimum = (.792-.015)*220e-9*.75/12e-6
    startup_charge_nominal = c_forward*vout/softstart_nominal
    startup_charge_worst = 1.2*c_forward*max(buck_corners)/softstart_minimum
    loop = loop_sweep()
    checks = {
        "unique_references": len({p["ref"] for p in PARTS}) == len(PARTS),
        "buck_worst_below_clamp_off_estimate": max(buck_corners) < off_range[0],
        "buck_to_clamp_off_headroom_above_150mV": off_range[0]-max(buck_corners) > .15,
        "clamp_estimated_peak_below_24V_nominal_not_a_rating": on_range[1]+dynamic_budget < 24,
        "20J_0p5s_triangular_peak_below_dump_full_on": max_stop_power < on_range[0]**2/(dump_r*1.01),
        "target_peak_below_26p3A_typical_inductor_Isat25C": ipeak_target < 26.3,
        "max_trip_peak_below_26p3A_typical_Isat25C": max_peak_trip < 26.3,
        "declared_averaged_loop_screen": loop["screening_pass"],
        "unloaded_bulk_charge_below_10A_target_estimate": startup_charge_worst<10,
    }
    return {
        "disposition": "ENGINEERING PROTOTYPE ANALYSIS; release holds remain",
        "checks": checks,
        "buck": {"setpoint_V": vout, "estimated_corner_V": [min(buck_corners), max(buck_corners)], "ordinary_1pct_divider_max_V": ordinary_max,
                 "continuous_target_A_unqualified": 10, "transient_target_A_unqualified": 12, "continuous_target_W_unqualified": 10*vout, "input_A_at_24V_90pct_assumed_12Atransient": 12*vout/(24*.90),
                 "max_ripple_App_Lminus20pct": ripple_max, "nominal_ripple_App": ripple_nom, "target_peak_A": ipeak_target,
                 "shunt_ohm": .005, "ilim_ohm": 649, "valley_limit_A_typ": valley_typ, "valley_limit_A_corners": [valley_min, valley_max], "maximum_trip_peak_A": max_peak_trip,
                 "current_limit_note": "Threshold range is broad even with shunt. 12A is not guaranteed near dropout. Enforce measured continuous limit and coordinate source fuse/wiring.",
                 "shunt_loss_W_upper_bound_at12A": 12**2*.005, "shunt_loss_W_upper_bound_at_max_peak": max_peak_trip**2*.005,
                 "inductor_DCR_max_ohm_25C": .009, "inductor_copper_loss_W_10A_85C": 100*.009*(1+.00393*60),
                 "inductor_typ_Isat30pctdrop_A_25C": 26.3, "inductor_Irms_A_20C_rise_reference": 16., "inductor_Irms_A_40C_rise_reference": 22.,
                 "inductor_note": "Isat is typical30% inductance drop at25C; Irms is a reference temperature-rise condition, not an absolute maximum. DC-bias/temperature inductance reduction and core loss remain to verify.",
                 "soft_start_cap_F": 220e-9, "soft_start_s_nominal": softstart_nominal, "soft_start_s_estimated_minimum": softstart_minimum,
                 "bulk_charge_current_A_nominal_no_load": startup_charge_nominal, "bulk_charge_current_A_worst_estimate_no_load": startup_charge_worst,
                 "startup_note": "Keep motors disabled until rail settles; idle motor input load and ideal-diode startup dynamics are not included. Scope cold start and warm restart.",
                 "lc_resonance_Hz_permanent_bulk_nominal": resonance_original, "lc_resonance_Hz_with_forward_motor_bulk_nominal": resonance_new,
                 "compensation_status": "Revised R16=10k,C24=47nF,C25=100pF,R17=3.3k,C26=2.2nF; declared averaged-model screen only. Nonlinear ideal diode and actual capacitor ESR/MLCC bias, layout parasitics and motor input impedance require bench measurement.",
                 "uvlo_note": "Retained 220k/12k UVLO approximately23.2V on/21.0V off permits dropout below22.5V; motor operation at reduced bus voltage must be confirmed or raise UVLO."},
        "clamp": {"on_V_nominal": clamp_voltage(output=.1), "off_V_nominal": clamp_voltage(output=4.9), "on_V_estimated_corners": on_range, "off_V_estimated_corners": off_range,
                  "dynamic_overshoot_budget_V": dynamic_budget, "estimated_peak_V": on_range[1]+dynamic_budget, "motor_absolute_maximum_V": None,
                  "bulk_F_nominal": c_nom, "bulk_F_minimum": c_min, "dump_R_ohm": dump_r, "full_on_current_A_nominal": dump_i, "full_on_power_W_nominal": dump_power,
                  "approx_max_hysteretic_frequency_Hz": max_chop_hz, "gate_charge_C_4p5V_max": qgate, "gate_drive_current_A_budget": igate_budget, "LDO_dissipation_W_budget": ldo_loss,
                  "note": "24V is only the motor's published nominal supply. Being below24V is not proof of permissible operation; overshoot budget and comparator common-mode allowance require bench confirmation. No continuous-downhill rating."},
        "stopping": {"mass_kg": mass, "speed_m_s": velocity, "translation_energy_J": energy, "illustrative_design_pulse_J_not_verified_bound": illustrative_energy, "illustrative_stop_s": stop_time, "triangular_peak_return_W": max_stop_power,
                     "20J_every10s_average_W": 2, "20J_every1s_average_W": 20,
                     "note": "Rotating inertia, payload, descending potential energy and external pushing are additional. Stop pulse is not a bound on downhill or fault energy. NH100100W rating requires specified heatsink; free-air rating is40W at25C. Thermal cutoff must permanently inhibit buck and leave resistor connected."},
        "source_urls": DATASHEETS,
        "loop_screen": loop,
        "release_holds": RELEASE_HOLDS,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = calculate()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(result["disposition"])
        for key, value in result["checks"].items():
            print(f"{'PASS' if value else 'REVIEW'}: {key}")
        for section in ("buck", "clamp", "stopping"):
            print(f"\n{section.upper()}")
            for key, value in result[section].items():
                print(f"  {key}: {value}")
        print("\nRELEASE HOLDS")
        for hold in result["release_holds"]:
            print(f"- {hold}")
    # Arithmetic failures mean revisit assumptions; release holds are always
    # visible and intentionally cannot be cleared by this script.
    return 0 if all(result["checks"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
