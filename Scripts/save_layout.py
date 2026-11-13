"""Guarda en Scripts/layout_overrides.json los objetos VG_* movidos o girados a mano.

Ya no hace falta ejecutarlo antes de reconstruir: Scripts/build_room.py lo hace solo.
Sirve para guardar los ajustes sin reconstruir el nivel.
"""
import importlib
import os
import sys

import unreal

_scripts = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

import vg_room  # noqa: E402

importlib.reload(vg_room)
vg_room.capture_layout()
