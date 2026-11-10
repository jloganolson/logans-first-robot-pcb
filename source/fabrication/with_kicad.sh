#!/usr/bin/env bash
# Run a command with KiCad 7's Python module and kicad-cli available.
# By default this uses the system KiCad 7 install. To use a relocated KiCad 7
# tree instead, set PDB_KICAD_RUNTIME to its root (the directory holding usr/).
# PDB_KICAD_STATE keeps KiCad's config and cache out of your own profile.
set -euo pipefail
if [ -n "${PDB_KICAD_RUNTIME:-}" ]; then
  runtime=$PDB_KICAD_RUNTIME
  export PATH="$runtime/usr/bin:$PATH"
  export LD_LIBRARY_PATH="$runtime/usr/lib/x86_64-linux-gnu:$runtime/usr/lib/kicad${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export PYTHONPATH="$runtime/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
  export KICAD7_SYMBOL_DIR="$runtime/usr/share/kicad/symbols"
  export KICAD7_FOOTPRINT_DIR="$runtime/usr/share/kicad/footprints"
else
  export KICAD7_SYMBOL_DIR="${KICAD7_SYMBOL_DIR:-/usr/share/kicad/symbols}"
  export KICAD7_FOOTPRINT_DIR="${KICAD7_FOOTPRINT_DIR:-/usr/share/kicad/footprints}"
fi
state=${PDB_KICAD_STATE:-/tmp/pdb-kicad}
export XDG_CONFIG_HOME="$state/config" XDG_CACHE_HOME="$state/cache" XDG_DATA_HOME="$state/data"
mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME"
exec "$@"
