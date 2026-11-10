#!/usr/bin/env bash
set -euo pipefail

root_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
default_runtime=/opt/kicad7-runtime
runtime=${PDB_KICAD_RUNTIME:-$default_runtime}
if [[ -x "$runtime/usr/bin/kicad-cli" ]]; then
  export PATH="$runtime/usr/bin:$PATH"
  export LD_LIBRARY_PATH="$runtime/usr/lib/x86_64-linux-gnu:$runtime/usr/lib/kicad${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export PYTHONPATH="$runtime/usr/lib/python3/dist-packages${PYTHONPATH:+:$PYTHONPATH}"
  export KICAD7_SYMBOL_DIR="$runtime/usr/share/kicad/symbols"
  export KICAD7_FOOTPRINT_DIR="$runtime/usr/share/kicad/footprints"
  scratch=$(mktemp -d "${TMPDIR:-/tmp}/pdb-kicad.XXXXXX")
  trap 'rm -rf "$scratch"' EXIT
  export XDG_CONFIG_HOME="$scratch/config" XDG_CACHE_HOME="$scratch/cache" XDG_DATA_HOME="$scratch/data"
fi
exec_python=${PDB_PYTHON:-/usr/bin/python3}
"$exec_python" "$root_dir/source/fabrication/review_v05.py" "$@"
