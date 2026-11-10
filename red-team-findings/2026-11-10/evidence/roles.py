import pcbnew,collections
b=pcbnew.LoadBoard('revisions/v0.9/kicad/robot_pdb.kicad_pcb')
want={'R13','C20','Y7002','Y1','FB2','C93','C94','C9902','D102','U9900','U9904','U17','U18','C27'}
vals=collections.defaultdict(list)
smd_pads=0; tht_pads=0; dnp=0
for fp in b.GetFootprints():
    r=fp.GetReference(); v=fp.GetValue()
    vals[v].append(r)
    if r in want or v in('6.8uH','10uH','100nF 100V','100uF 63V','470uF 25V','Green','SS1060'):
        print(r,v,[(p.GetNumber(),p.GetNetname()) for p in fp.Pads()][:4])
    att=fp.GetAttributes()
    excl=bool(att & pcbnew.FP_EXCLUDE_FROM_POS_FILES) or bool(att & pcbnew.FP_EXCLUDE_FROM_BOM)
    for p in fp.Pads():
        if excl: continue
        if p.GetAttribute()==pcbnew.PAD_ATTRIB_SMD: smd_pads+=1
        elif p.GetAttribute()==pcbnew.PAD_ATTRIB_PTH: tht_pads+=1
print('pads on non-excluded footprints: smd',smd_pads,'tht',tht_pads)
