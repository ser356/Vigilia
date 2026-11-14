"""Punto de entrada: construye (o reconstruye) la mansion completo.

Desde el editor:   Tools > Execute Python Script...  -> Scripts/build_room.py
Desde la consola:  py "Scripts/build_room.py"
Desde terminal:    Tools/setup_mac.sh  (lo ejecuta automaticamente)
"""
import importlib
import os
import sys

import unreal

_scripts = os.path.join(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()), "Scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

if not hasattr(unreal, "VGDoor"):
    raise RuntimeError("El modulo C++ 'Vigilia' no esta cargado. Compila el proyecto antes (Tools/setup_mac.sh).")

import vg_common  # noqa: E402
import vg_materials  # noqa: E402
import vg_room  # noqa: E402

# Recarga para poder iterar sobre los scripts sin reiniciar el editor.
for _module in (vg_common, vg_materials, vg_room):
    importlib.reload(_module)

vg_room.build()
