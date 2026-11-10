"""Independent static corner arithmetic; not a temperature qualification test."""
import json, math
from pathlib import Path
root=Path(__file__).resolve().parents[2]
out=root/'outputs/usb3-design';out.mkdir(parents=True,exist_ok=True)
top_lo=.99*(1-100e-6*100);top_hi=1.01*(1+100e-6*100)
bot_lo=.999*(1-25e-6*100);bot_hi=1.001*(1+25e-6*100)
rails={}
for name,top,bottom,nom,acc,hyst,op_min,op_max in [('core',105000,100000,1.12,.015,.025,1.08,1.32),('io',460000,100000,3.07,.015,.025,3.,3.6)]:
    lo=.588*(1+top*top_lo/(bottom*bot_hi));hi=.612*(1+top*top_hi/(bottom*bot_lo))
    release=nom*(1+acc)*(1+hyst);fall=nom*(1-acc)
    rails[name]={'nominal_v':.6*(1+top/bottom),'output_low_v_at_published_25C_FB_limit_plus_resistor_TCR':lo,'output_high_v_at_published_25C_FB_limit_plus_resistor_TCR':hi,'supervisor_min_falling_v':fall,'supervisor_max_rising_v':release,'startup_margin_v_conditional':lo-release,'hub_operating_range_v':[op_min,op_max]}
    assert lo>release and hi<op_max and fall>op_min
rlo=220000*.99*(1-.01);rhi=220000*1.01*(1+.01)
clo=100e-9*.95*(1-.003);chi=100e-9*1.05*(1+.003)
leak=.5e-6;initial=1.9-leak*rhi;fast=-leak*rlo;slow=.4+leak*rhi
hold=rlo*clo*math.log((initial-fast)/(1.17-fast))
off=rhi*chi*math.log((3.6-slow)/(.63-slow))
assert hold>.005 and initial>1.17 and slow<.63
result={'scope':'Analytical startup/fault corners; prototype unreleased until physical checks. Not full-temperature regulator accuracy certification.',
'conditions':{'resistor_temperature_delta_C':100,'top_resistors':'1% 100ppm/C; multiplicative worst signs','bottom_resistors':'Yageo RT0603BRD07100KL C122538 0.1%25ppm/C','TLV62569_VFB_v':[.588,.612],'TLV62569_VFB_table_temperature_C':25,'TLV62569_full_temperature_FB_or_FB_bias_bound':'not specified by cited table; no invented guaranteed bound','TPS3808_fixed_SENSE_current':'1.7uA typical only; no published max. Direct copper connection, zero external divider resistance; source impedance/ripple bench test remains.'},
'rails':rails,'raw_5V':{'minimum_v':5.0509770374,'supervisor_max_release_v':4.65*1.02*1.025,'supervisor_min_fall_v':4.65*.98},
'port_EN_RC':{'R_range_ohm':[rlo,rhi],'C_range_f':[clo,chi],'initial_high_min_v':initial,'fast_low_asymptote_v':fast,'slow_low_asymptote_v':slow,'conditional_steady_fault_high_hold_min_ms':hold*1000,'slow_guaranteed_camera_low_ms':off*1000,'slow_switch_off_including_3ms_TPS2553_ms':off*1000+3,'hub_continuous_low_requirement_ms':5,'hub_two_short_low_pulses_window_ms':20,'limitation':'Initially charged capacitor and stated PRT_CTL/input leakage bounds. First-enable hard short and very short thermal pulses are not covered; no universal OCS latch guarantee.'},
'bench':['cold-start hard short on each powered port','repeated short and independent current limit/thermal action','thermal fault pulses and OCS report','unplug fault and host clear/re-enable recovery','all rail startup/brownout/fall/reset sequencing','core/IO regulation and ripple over temperature/load','full OAK-D + microphone simultaneous streaming; both Type-C orientations'],
'sources':{'TPS3808':'https://www.ti.com/lit/ds/symlink/tps3808.pdf §6.5; fixed threshold ±1.5%/±2%, fixed hysteresis max2.5%','TLV62569':'https://www.ti.com/lit/ds/symlink/tlv62569.pdf §6.5/§8.2.2.1','USB5744':'https://ww1.microchip.com/downloads/aemDocuments/documents/UNG/ProductDocuments/DataSheets/USB5744-Data-Sheet-DS00001855.pdf §8.4.2.1 Table8-2 Figure8-2 and §10.2','TPS25810':'https://www.ti.com/lit/ds/symlink/tps25810.pdf §6.5 EN thresholds/leakage','TPS2553':'https://www.ti.com/lit/ds/symlink/tps2553.pdf §6.5 and auto-retry discussion','Murata_C0G':'https://search.murata.co.jp/Ceramy/image/img/A01X/G101/ENG/GRM31C5C1H104JA01-01A.pdf','Murata_no_DC_bias':'https://www.murata.com/support/faqs/capacitor/ceramiccapacitor/char/0005'}}
(out/'calculations.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
