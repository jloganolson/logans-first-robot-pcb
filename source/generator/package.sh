#!/bin/bash
# package.sh SRC_OUTDIR PROJ DEST
set -e
echo "Manufacturing release is on HOLD. See docs/HANDOFF.md; use the review package only." >&2
exit 1
S=$1; P=$2; D=$3
mkdir -p $D/kicad $D/jlcpcb $D/docs
cp $S/$P.kicad_pcb $S/$P.kicad_sch $S/pdb.kicad_sym $S/sym-lib-table $D/kicad/
[ -f $S/$P.kicad_pro ] && cp $S/$P.kicad_pro $D/kicad/ || true
cp $S/jlcpcb/* $D/jlcpcb/
cp $S/BOM_annotated.csv $S/drc.rpt $S/top.png $D/docs/
[ -f $S/bottom.png ] && cp $S/bottom.png $D/docs/ || true
cp $S/${P}_schematic.pdf $D/docs/ 2>/dev/null || true
kicad-cli pcb export pdf --layers F.Cu,F.SilkS,Edge.Cuts -o $D/docs/${P}_top_copper.pdf $S/$P.kicad_pcb >/dev/null
