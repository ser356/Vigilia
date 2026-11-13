"""Guarda en Scripts/layout_overrides.json la posicion y el giro de los objetos que hayas movido a mano
en el editor, para que las siguientes reconstrucciones los respeten.

Uso: mueve o gira los actores VG_* en el nivel y ejecuta este script (Tools > Execute Python Script...).
"""
import json
import os

import unreal

project = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
path = os.path.join(project, "Scripts", "layout_overrides.json")

overrides = {}
if os.path.exists(path):
    with open(path, encoding="utf-8") as fh:
        overrides = json.load(fh)

changed = 0
for actor in unreal.get_editor_subsystem(unreal.EditorActorSubsystem).get_all_level_actors():
    tags = [str(t) for t in actor.tags]
    key = next((t[7:] for t in tags if t.startswith("VGSlot:")), None)
    auto = next((t[7:] for t in tags if t.startswith("VGAuto:")), None)
    if not key or not auto:
        continue
    ax, ay, az, ayaw = [float(v) for v in auto.split(",")]
    loc = actor.get_actor_location()
    yaw = actor.get_actor_rotation().yaw
    moved = abs(loc.x - ax) + abs(loc.y - ay) + abs(loc.z - az) > 0.5
    turned = abs(((yaw - ayaw + 180.0) % 360.0) - 180.0) > 0.5
    if moved or turned or key in overrides:
        overrides[key] = {"loc": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)], "yaw": round(yaw, 2)}
        changed += 1

with open(path, "w", encoding="utf-8") as fh:
    json.dump(overrides, fh, indent=1, sort_keys=True)
unreal.log("[Vigilia] %d ajustes guardados en %s" % (changed, path))
