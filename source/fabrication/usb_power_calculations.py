"""Reproducible USB supply tolerance/current and averaged-loop screen."""
import itertools,json,sys,math
from pathlib import Path
from motor_addon_calculations import loop_sweep

def calculate():
 # Precision100k and2×10k:0.1%initial +25ppm/°C over±60°C.
 # 8.2k:1%initial +100ppm/°C over±60°C; FB0.8V±1%.
 precision=.001+25e-6*60;ordinary=.01+100e-6*60
 voltages=[ref*(1+(r100+r8)/(ra+rb)) for ref,r100,r8,ra,rb in itertools.product((.792,.808),(100000*(1-precision),100000*(1+precision)),(8200*(1-ordinary),8200*(1+ordinary)),(10000*(1-precision),10000*(1+precision)),(10000*(1-precision),10000*(1+precision)))]
 nominal=.8*(1+108200/20000)
 #5mR1%+50ppm/°C shunt;470R1%+200ppm/°C sense-setting resistor.
 rs=.005;rstol=.01+50e-6*60;rltol=.01+200e-6*60
 valley_min=(90e-6*470*(1-rltol)-.0035)/(rs*(1+rstol))
 valley_max=(110e-6*470*(1+rltol)+.008)/(rs*(1-rstol))
 ripple=max(voltages)*(1-max(voltages)/33.6)/(8e-6*200000)
 loop=loop_sweep(rt=108200,rb=20000,vout=nominal,downstream=(0.,.00024,.0006),load_limits=(.1,8.),rt_tolerance=(100000*precision+8200*ordinary)/108200)
 loop['qualification']='USB supply averaged-model screen only. Measure actual loop injection, startup, port inrush/load steps and simultaneous USB device behavior.'
 checks={
  'unloaded feedback corners below5.25V':max(voltages)<5.25,
  'minimum setpoint above5.0V before path drop':min(voltages)>5.0,
  'maximum modeled shunt/FET peak below22A coil40C-rise rating':valley_max+ripple<22,
  'averaged-loop screen passes declared margin':loop['screening_pass'],
 }
 return {'status':'PASS' if all(checks.values()) else 'FAIL','checks':checks,'nominal_voltage_v':nominal,'setpoint_corner_v':[min(voltages),max(voltages)],
  'available_drop_budget_to4_75_v':min(voltages)-4.75,'drop_budget_note':'Switch, copper, connector, ripple and transient losses must fit within this combined budget; no port-compliance claim follows without that audit and measurement.',
  'valley_limit_a':[valley_min,valley_max],'ripple_peak_to_peak_max_a':ripple,'design_load_a':8.,'qualification':'8A is a thermal design target, not a demonstrated output rating; valley limiting is not a precise output-current ceiling.',
  'loop':loop,'sources':['https://www.ti.com/lit/ds/symlink/lm5146-q1.pdf','https://jlcpcb.com/partdetail/YAGEO-RT0603BRD07100KL/C122538','https://jlcpcb.com/partdetail/0603WAF8201T5E/C25981']}

if __name__=='__main__':
 report=calculate();out=Path(__file__).resolve().parents[2]/'outputs/usb-power-design';out.mkdir(parents=True,exist_ok=True);(out/'calculations.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2));raise SystemExit(0 if report['status']=='PASS' else 1)
