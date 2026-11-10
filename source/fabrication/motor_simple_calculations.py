#!/usr/bin/env python3
"""Declared analytical screens for simple24V development cell, no motor approval."""
import itertools, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/generator'))
from motor_simple import PARTS, RELEASE_HOLDS
from motor_addon_calculations import loop_sweep

def calculate():
    def voltage(ref=.8,top=150000.,bottom=5100.,extra=75.):
        return ref*(1+top/(bottom+extra))
    precision=.001+25e-6*60
    ordinary=.01+200e-6*60
    corners=[voltage(.8*v,150000*t,5100*b,75*e)
             for v,t,b,e in itertools.product((.99,1.01),(1-precision,1+precision),
                                             (1-precision,1+precision),(1-ordinary,1+ordinary))]
    nominal=voltage()
    # TI minimum-off-time max200ns; oscillator+RT corner conservatively10%.
    fmax=220000.; maxduty=1-fmax*200e-9
    vmin_ideal=max(corners)/maxduty
    loop=loop_sweep(rb=5175.,vout=nominal,downstream=(.0016,.0024))
    mass,speed=20*.45359237,3*.44704
    energy=.5*mass*speed**2
    shunt_tol=.01+50e-6*60
    rilim_tol=.01+100e-6*60
    valley_min=(90e-6*649*(1-rilim_tol)-.0035)/(.005*(1+shunt_tol))
    valley_max=(110e-6*649*(1+rilim_tol)+.008)/(.005*(1-shunt_tol))
    ripple=max(v*(1-v/33.6)/(.8*10e-6*180000.) for v in corners)
    return dict(status='DEVELOPMENT_HELD',nominal_output_V=nominal,
        divider_corner_output_V=[min(corners),max(corners)],
        divider_assumptions=dict(reference_fraction=.01,precision_resistor_initial_fraction=.001,
            precision_TCR_ppm_C=25,ordinary_resistor_initial_fraction=.01,
            ordinary_TCR_ppm_C=200,temperature_excursion_C=60),
        headroom=dict(input_operating_design_window_V=[27,33.6],maximum_switching_Hz=fmax,
            maximum_minimum_offtime_s=200e-9,ideal_maximum_duty=maxduty,
            worst_case_ideal_minimum_input_V=vmin_ideal,
            ideal_margin_at27V_V=27-vmin_ideal,
            limitation='Ideal timing only; MOSFET/inductor/shunt/copper/reverse-stage losses, loaded sag and regulation require measurement.'),
        output_bulk_nominal_F=.00326,
        energy=dict(translational_J=energy,nominal_bulk_energy24to26V_J=.5*.00326*(26**2-24**2),
            hypothetical_all_energy_final_V=math.sqrt(24**2+2*energy/.00326),
            limitation='26V is illustrative, NOT an allowed wheel voltage. Capacitors are not an energy sink.'),
        current_limit=dict(valley_A=[valley_min,valley_max],worst_declared_ripple_A=ripple,
            worst_peak_trip_A=valley_max+ripple,
            limitation='Reused shunt649R limit; not a precise output limit. Thermal and inductor-current qualification required.'),
        loop=loop,
        inventory=dict(parts=len(PARTS),references_unique=len({p['ref'] for p in PARTS})==len(PARTS)),
        release_holds=RELEASE_HOLDS)

if __name__=='__main__':
    result=calculate()
    output=ROOT/'revisions/motor-simple/calculations.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('status','nominal_output_V','divider_corner_output_V','headroom','current_limit','loop')},indent=2))
    raise SystemExit(not result['loop']['screening_pass'])
