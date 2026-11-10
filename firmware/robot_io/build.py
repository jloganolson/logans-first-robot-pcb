#!/usr/bin/env python3
"""Fetch pinned upstreams (--fetch), apply tracked CAN patch, build both images.

Needs arm-none-eabi-gcc/newlib/binutils and CMake. No flashing is performed.
Set TOOLCHAIN_BIN_DIR for a toolchain outside PATH.
"""
import argparse, hashlib, json, os, pathlib, shutil, subprocess
ROOT=pathlib.Path(__file__).resolve().parent
def run(args,**kwargs):
    print("+", " ".join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,**kwargs)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--fetch',action='store_true');args=ap.parse_args()
    manifest=json.loads((ROOT/'dependencies.json').read_text())
    for folder,meta in manifest.items():
        path=ROOT/folder
        if not path.exists():
            if not args.fetch:raise SystemExit('Missing upstream; rerun with --fetch')
            run(['git','clone',meta['url'],path])
        # Only ignored dependency trees are reset; project sources are untouched.
        run(['git','-C',path,'checkout','--detach',meta['commit']])
        if folder=='candlelight_upstream':
            patch=ROOT/'can.patch'
            check=subprocess.run(['git','-C',str(path),'apply','--reverse','--check',str(patch)],capture_output=True)
            if check.returncode:run(['git','-C',path,'apply',patch])
        actual=subprocess.check_output(['git','-C',str(path),'rev-parse','HEAD'],text=True).strip()
        if actual!=meta['commit']:raise SystemExit('Dependency hash mismatch')
        diff=subprocess.check_output(['git','-C',str(path),'diff','--binary'])
        expected=(ROOT/'can.patch').read_bytes() if folder=='candlelight_upstream' else b''
        if diff!=expected:raise SystemExit('Unexpected upstream source modifications: '+folder)
    env=os.environ.copy()
    if env.get('TOOLCHAIN_BIN_DIR'):env['PATH']=env['TOOLCHAIN_BIN_DIR']+os.pathsep+env['PATH']
    cc=shutil.which('arm-none-eabi-gcc',path=env['PATH'])
    if not cc:raise SystemExit('Install an ARM GNU/newlib toolchain or set TOOLCHAIN_BIN_DIR')
    can=ROOT/'candlelight_upstream';build=ROOT/'build';build.mkdir(exist_ok=True)
    run(['cmake','-S',can,'-B',build/'can','-DCMAKE_TOOLCHAIN_FILE='+str(can/'cmake/arm-none-eabi-gcc.cmake')],env=env)
    run(['cmake','--build',build/'can','--target','robot_io_can_fw','-j4'],env=env)
    cmsis=can/'libs/STM32_HAL/include/cmsis';tiny=ROOT/'tinyusb_upstream/src';pwm=ROOT/'pwm'
    sources=[pwm/x for x in ('startup.c','main.c','controller.c','usb_descriptors.c')]
    sources += [tiny/x for x in ('tusb.c','common/tusb_fifo.c','device/usbd.c','device/usbd_control.c','class/cdc/cdc_device.c','portable/st/stm32_fsdev/dcd_stm32_fsdev.c','portable/st/stm32_fsdev/fsdev_common.c') if (tiny/x).exists()]
    flags=['-mcpu=cortex-m0','-mthumb','-Os','-g3','-std=gnu11','-Wall','-Wextra','-Werror','-ffunction-sections','-fdata-sections','-DSTM32F072xB','-DHSE_VALUE=8000000','-I'+str(pwm),'-I'+str(tiny),'-I'+str(cmsis),'-I'+str(cmsis/'device')]
    objects=[]
    for index,source in enumerate(sources):
        obj=build/f'pwm-{index}.o';run([cc,*flags,'-c',source,'-o',obj],env=env);objects.append(obj)
    elf=build/'robot_io_pwm.elf'
    run([cc,*flags,'-nostartfiles','--specs=nano.specs','--specs=nosys.specs','-Wl,--gc-sections,-Map='+str(build/'robot_io_pwm.map'),'-T'+str(pwm/'stm32f072cb.ld'),*objects,'-o',elf],env=env)
    run([str(pathlib.Path(cc).with_name('arm-none-eabi-objcopy')),'-O','binary',elf,build/'robot_io_pwm.bin'],env=env)
    run([str(pathlib.Path(cc).with_name('arm-none-eabi-size')),build/'can/robot_io_can_fw',elf],env=env)
    artifacts=[build/'can/robot_io_can_fw',build/'can/robot_io_can_fw.bin',elf,build/'robot_io_pwm.bin']
    source_paths=sorted(pwm.glob('*.c'))+sorted(pwm.glob('*.h'))+[pwm/'stm32f072cb.ld',ROOT/'can.patch',ROOT/'build.py']
    report={'dependencies':manifest,'compiler':subprocess.check_output([cc,'--version'],text=True).splitlines()[0],
            'project_sources':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths},
            'artifacts':{str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in artifacts},
            'hardware_tested':False,'release_holds':['USB suspend current not measured; low-power suspend implementation not qualified','PWM/CAN electrical timing, boot states and real actuators require bench tests','USB prototype VID/PID requires authorized identity before distribution']}
    (build/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
    published=ROOT/'artifacts';published.mkdir(exist_ok=True)
    for source in (build/'can/robot_io_can_fw.bin',build/'robot_io_pwm.bin'):
        shutil.copy2(source,published/source.name)
    (published/'build_report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
