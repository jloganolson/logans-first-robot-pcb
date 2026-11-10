#!/usr/bin/env python3
"""Declared screens for shared-bus resistor-clamp development cell.

Reuses frozen component/corner equations, not their old ideal-diode topology.
Arithmetic does not establish actual wheel voltage limits or thermal ratings.
"""
import json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'source/generator'))
from motor_resistor import PARTS,RELEASE_HOLDS,DATASHEETS
import motor_addon_calculations as old

def calculate():
    previous=old.calculate()
    buck=previous['buck'];clamp=previous['clamp']
    loop=old.loop_sweep(vout=buck['setpoint_V'],downstream=(.0016,.0024))
    loop['qualification']=('Bench loop injection and startup/load-step tests remain required. '
        'No model of discontinuous-mode transitions, input-protection dynamics, layout parasitics '
        'or actual motor negative incremental input impedance.')
    # The inherited calculation considers an output diode separating two bulk
    # groups. Here all three capacitors are permanent shared-bus capacitance.
    buck['lc_resonance_Hz_shared_bulk_nominal']=buck.pop('lc_resonance_Hz_with_forward_motor_bulk_nominal')
    buck.pop('lc_resonance_Hz_permanent_bulk_nominal')
    buck.pop('input_A_at_24V_90pct_assumed_12Atransient')
    buck['input_A_at27V_90pct_assumed_12Atransient']=12*buck['setpoint_V']/(27*.90)
    buck['uvlo_note']=('Retained220k/12kUVLO approximately23.2Von/21.0Voff permits dropout '
        'below22.34V; actual wheel undervoltage behavior remains to verify.')
    # Keep the old, smaller local capacitor bank for the fast clamp response
    # estimate rather than silently crediting the more distant third capacitor.
    clamp['fast_local_clamp_bulk_F_nominal']=clamp.pop('bulk_F_nominal')
    clamp['fast_local_clamp_bulk_F_minimum']=clamp.pop('bulk_F_minimum')
    clamp['shared_bus_bulk_F_nominal']=.00326
    # HS1003R3F1% plus conservative100ppm/C for100C winding excursion.
    rmin,rmax=3.3*(1-.01-.01),3.3*(1+.01+.01)
    voltage_min=clamp['off_V_estimated_corners'][0]
    voltage_max=clamp['estimated_peak_V']
    sink_min=voltage_min**2/rmax
    sink_peak=voltage_max**2/rmin
    omega=(3*.44704)/(.1143/2)
    mechanical=2*3*omega
    energy=20.; stop=.5; recurrence=2.
    # 30W free-air@25C is the HS100 family figure, NOT100W unrestricted.
    # Do not assume it certifies a custom bracket/cutoff normal temperature.
    checks=dict(reference_uniqueness=len({s['ref'] for s in PARTS})==len(PARTS),
        buck_below_clamp_off=clamp['off_V_estimated_corners'][0]>buck['estimated_corner_V'][1],
        buck_to_clamp_off_margin_over150mV=clamp['off_V_estimated_corners'][0]-buck['estimated_corner_V'][1]>.15,
        declared_full_sink_above_two_wheel3Nm3mph_mechanical=sink_min>mechanical,
        proposed20J_halfsecond_uniform_stop_peak_below_sink=2*energy/stop<sink_min,
        proposed_average_below30W25C_freeair=energy/recurrence<30,
        declared_loop_screen=loop['screening_pass'])
    buck['compensation_status']='SharedMOTOR_BUS; all3bulk capacitors always coupled. New averaged screen only; measure real loop/startup/load response.'
    buck['startup_note']='All3bulk capacitors remain directly connected. Keep drives disabled through startup; scope shutdown backfeed into isolatedVIN and re-enable.'
    result=dict(disposition='DEVELOPMENT_HELD; not a measured motor/brake rating',checks=checks,
        inventory_parts=len(PARTS),output_net='MOTOR_BUS',buck=buck,clamp=clamp,loop_screen=loop,
        resistor=dict(mpn='Ohmite/ARCOL HS1003R3F',nominal_ohm=3.3,resistance_corner_ohm=[rmin,rmax],
            tolerance_fraction=.01,temperature_TCR_ppm_C_assumed_max=100,temperature_excursion_C=100,
            minimum_full_on_power_at_clamp_off_corner_W=sink_min,
            maximum_estimated_instantaneous_power_W=sink_peak,
            maximum_estimated_current_A=voltage_max/rmin,
            nameplate_chassis_W=100,manufacturer_freeair_W_25C=30,
            manufacturer_typical_overload=dict(power_multiple_duration=[[10,1],[5,5],[2,180]],
                conditions='Historical ARCOLTI004-03:25C,resistoronrecommendedheatsinkwiththermalcompound,criticalvoltage/resistanceobserved. Typicaldata,notguaranteedrepetitivehot-pulsequalification.',
                source='https://us.rs-online.com/m/d/840dcab3450261b61b91e3aa6789a31d.pdf'),
            pulse_qualification='Estimated175W switchpulse is below historicalHS-family2x100W overloadexample;20J/0.5s repeatedhot-pulse assembly stillrequiresmeasurement. Only citedHS100-family guidance applies; largerHS400-600 specifications do not establish this rating.',
            mounting='Thermalcompound to cleanflat aluminum chassis/heatsink;100Wreference995cm2/3mm perHS100family table; actual mount qualification required.'),
        stopping=dict(translation_J=previous['stopping']['translation_energy_J'],
            mechanical_peak_estimate_two3Nm_wheels3mph_W=mechanical,
            proposed_total_energy_J=energy,proposed_uniform_stop_s=stop,
            proposed_peak_uniform_decel_W=2*energy/stop,
            proposed_minimum_start_to_start_s=recurrence,proposed_average_W=energy/recurrence,
            limitations='20Jbudget includes margin but is not a verified inertia bound. Torque/speed/current enforcement, grade and external forcing must be checked. No continuousdownhill rating.'),
        power_off='No output ideal diode: motor bus can charge isolatedVIN through L1/high-side bodydiode. Main input diode must still prevent packbackfeed. Measure EN/thermal behavior and startup/restart.',
        source_urls=DATASHEETS,release_holds=RELEASE_HOLDS)
    return result

if __name__=='__main__':
    r=calculate();out=ROOT/'revisions/motor-resistor/calculations.json'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2)+'\n')
    print(json.dumps({k:r[k] for k in ('disposition','checks','inventory_parts','resistor','stopping','loop_screen')},indent=2))
    raise SystemExit(not all(r['checks'].values()))
