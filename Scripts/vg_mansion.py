"""Ala principal de tres niveles. Reutiliza los assets resueltos por el pipeline Fab/CC0."""
import unreal

from vg_mansion_layout import LEVELS, WALL_HEIGHT, rooms, stair_blocks


def build(v, res, mats, photos):
    """v es vg_room: evita importar circularmente el constructor del salon."""
    house = v.STATE["house"]

    def block(key, mn, mx, material, collision=True, shadow=True):
        return v.box("mansion_" + key, mn, mx, material, folder="Mansion", collision=collision, shadow=shadow)

    def wall(key, axis, start, end, fixed, z, openings=()):
        # Huecos locales (a0, a1, z0, z1). Nada de una pared entera detras de las puertas.
        def part(suffix, a0, a1, h0, h1):
            if a1 <= a0 or h1 <= h0:
                return
            mn, mx = ((a0, fixed, z + h0), (a1, fixed + 10, z + h1)) if axis == "X" else (
                (fixed, a0, z + h0), (fixed + 10, a1, z + h1))
            block(key + suffix, mn, mx, mats["wall_XZ" if axis == "X" else "wall_YZ"])
            # Rodapie y moldura de cornisa, interrumpidos en los pasos.
            if h0 == 0:
                lo, hi = list(mn), list(mx)
                hi[2] = z + 12
                lo[1 if axis == "X" else 0] -= 2
                hi[1 if axis == "X" else 0] += 2
                block(key + suffix + "_base", lo, hi, mats["trim"], False)
        cursor = start
        for i, (a0, a1, h0, h1) in enumerate(sorted(openings)):
            part("_%d_left" % i, cursor, a0, 0, WALL_HEIGHT)
            part("_%d_bottom" % i, a0, a1, 0, h0)
            part("_%d_top" % i, a0, a1, h1, WALL_HEIGHT)
            cursor = a1
        part("_end", cursor, end, 0, WALL_HEIGHT)
        if axis == "X":
            block(key + "_cornice", (start, fixed - 4, z + 267), (end, fixed + 14, z + 280), mats["trim"], False)
        else:
            block(key + "_cornice", (fixed - 4, start, z + 267), (fixed + 14, end, z + 280), mats["trim"], False)

    def window(key, cx, y, z, basement=False):
        low, high = (205, 250) if basement else (90, 225)
        for suffix, mn, mx in (
            ("sill", (cx - 95, y - 4, z + low - 5), (cx + 95, y + 14, z + low)),
            ("top", (cx - 95, y - 2, z + high), (cx + 95, y + 12, z + high + 5)),
            ("left", (cx - 95, y - 2, z + low), (cx - 90, y + 12, z + high)),
            ("right", (cx + 90, y - 2, z + low), (cx + 95, y + 12, z + high)),
            ("mullion", (cx - 2, y, z + low), (cx + 2, y + 10, z + high)),
        ):
            block(key + suffix, mn, mx, mats["trim"], False)
        block(key + "glass", (cx - 90, y + 4, z + low), (cx + 90, y + 5, z + high), mats["glass"], False, False)
        # Luz exterior motivada por una abertura real; sin rellenos omnidireccionales sin sombras.
        north = y > 0
        light = v.spawn_marked(unreal.SpotLight, "mansion_" + key + "_moon",
                               v.V(cx + 70, y + (130 if north else -130), z + high + 60), folder="Mansion/Lighting")
        target = v.V(cx - 70, y + (-400 if north else 400), z + 25)
        light.set_actor_rotation(v.ML.find_look_at_rotation(light.get_actor_location(), target), False)
        comp = light.get_component_by_class(unreal.SpotLightComponent)
        comp.set_mobility(unreal.ComponentMobility.MOVABLE)
        for prop, value in (("intensity_units", unreal.LightUnits.LUMENS), ("intensity", 110 if basement else 260),
                            ("use_temperature", True), ("temperature", 7600), ("attenuation_radius", 1150),
                            ("inner_cone_angle", 20), ("outer_cone_angle", 42), ("cast_shadows", True),
                            ("source_radius", 18), ("max_draw_distance", 2200), ("max_distance_fade_range", 400)):
            v.safe_set(comp, prop, value)

    def lamp_and_switch(key, x, y, z, switch_x, switch_y):
        lamp = v.spawn_marked(unreal.VGLamp, key, v.V(x, y, z + 250), folder="Mansion/Lights")
        bulb = res.get("bulb")
        if bulb:
            g = v.group_for(bulb)
            lamp.setup_mesh(g.main, v.V(-g.center[0], g.center[1], g.min[2]), v.R(roll=180))
        lamp.setup_light(v.V(0, 0, -8), 110, 2600, 650)
        lamp.set_on(False, False)
        v.set_bool(lamp, "directly_interactable", False)
        house["lamps"][key] = lamp
        switch = v.spawn_marked(unreal.VGLightSwitch, key + "_switch", v.V(switch_x, switch_y, z + 110), folder="Mansion/Switches")
        switch.setup_mesh(v.eal.load_asset("/Engine/BasicShapes/Cube"), v.V(0, 0, 0), v.R())
        comp = switch.get_editor_property("mesh")
        comp.set_relative_scale3d(v.V(.08, .025, .1))
        comp.set_material(0, mats["switch"])
        v.safe_set(switch, "switch_sound", v.sfx("switch_click"))
        switch.add_target(lamp)

    def prop(key, slot, x, y, z, **kw):
        if not res.get(slot):
            return None
        return v.Prep("mansion_" + key, res[slot], **kw).spawn(x, y, z, folder="Mansion/Furniture")

    # El antiguo vestibulo conecta ahora con la galeria principal, sin muro terminal ni cerradura.
    for actor in list(v.actor_sub.get_all_level_actors()):
        if actor.get_actor_label().startswith("VG_vestibule_E_"):
            v.actor_sub.destroy_actor(actor)
    house["doors"]["door_end"].set_locked(False)
    house["doors"]["door_bathroom"].set_locked(False)

    for level, z in LEVELS:
        # Losa continua, con hueco real para ambos tramos de escalera. El sotano tiene suelo completo.
        if level == "basement":
            block(level + "_floor", (870, -1000, z - 20), (2440, 600, z), mats["floor"])
        else:
            for i, bounds in enumerate(((870, 1940, -1000, 600), (2360, 2440, -1000, 600),
                                         (1940, 2360, -1000, -180), (1940, 2360, 260, 600))):
                x0, x1, y0, y1 = bounds
                block(level + "_floor_%d" % i, (x0, y0, z - 20), (x1, y1, z), mats["floor"])
        if level == "upper":
            block("roof", (870, -1000, z + WALL_HEIGHT), (2440, 600, z + 300), mats["ceiling"])
        # Fachadas del ala principal y paso desde el ala antigua solo en planta baja.
        west_hole = [(-345, -225, 0, 245)] if level == "ground" else []
        wall(level + "_west", "Y", -1000, 600, 870, z, west_hole)
        wall(level + "_east", "Y", -1000, 600, 2430, z)
        # Escalera cerrada al exterior y ventana alta en el rellano.
        wall(level + "_bay_south", "X", 1900, 2440, -1000, z)
        low, high = (205, 250) if level == "basement" else (90, 225)
        wall(level + "_bay_north", "X", 1900, 2440, 590, z, [(2080, 2260, low, high)])
        window(level + "_stair_window", 2170, 590, z, level == "basement")
        lamp_and_switch("mansion_" + level + "_hall", 1580, -285, z, 1470, -184)
        # Habitaciones con escalas domesticas y funciones reconocibles, sin mobiliario en el paso.
        for name, (x0, x1, y0, y1), side in rooms(level):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            outer_y, inner_y = (590, -175) if side == "N" else (-1000, -405)
            door_y = inner_y + 5
            half = v.DOOR_W / 2 + v.JAMB + 1
            wall(name + "_outer", "X", x0, x1, outer_y, z, [(cx - 90, cx + 90, low, high)])
            window(name + "_window", cx, outer_y, z, level == "basement")
            wall(name + "_inner", "X", x0, x1, inner_y, z, [(cx - half, cx + half, 0, v.DOOR_H + v.JAMB + 1)])
            # Medianera unica por pareja; borde este cierra contra la caja de escalera.
            wall(name + "_east", "Y", y0 + 10, y1 - 10, x1 - 10, z)
            door = v.spawn_house_door("mansion_" + name + "_door", "X", cx - v.DOOR_W / 2, door_y, res, mats,
                                      open_sign=-1 if side == "N" else 1)
            loc = door.get_actor_location()
            door.set_actor_location(v.V(loc.x, loc.y, loc.z + z), False, False)
            # Marcos construidos a cota cero y trasladados con sus componentes.
            before = set(v.actor_sub.get_all_level_actors())
            v.house_door_frame("mansion_" + name + "_frame", "X", cx - half, cx + half, inner_y - 1, inner_y + 11, mats)
            for actor in set(v.actor_sub.get_all_level_actors()) - before:
                loc = actor.get_actor_location()
                actor.set_actor_location(v.V(loc.x, loc.y, loc.z + z), False, False)
            house["doors"][name] = door
            lamp_and_switch("mansion_" + name, cx, cy, z, cx + half + 18, inner_y + (14 if side == "N" else -4))
            block(name + "_rug", (cx - 130, cy - 170, z + .1), (cx + 130, cy + 170, z + .5), mats["rug"], False)
            # Mantiene despejados al menos 150 cm junto a la puerta.
            far_y = y1 - 140 if side == "N" else y0 + 140
            if "bedroom" in name or name == "nursery":
                prop(name + "_bed", "bed", cx + 60, far_y, z, long_axis="Y")
                prop(name + "_nightstand", "nightstand", x0 + 85, far_y, z)
                prop(name + "_wardrobe", "wardrobe", x1 - 100, cy, z, face_yaw=180)
            elif name == "upstairs_bath":
                prop(name + "_bath", "bathtub", cx, far_y, z, long_axis="X")
                prop(name + "_towel", "towel", cx + 130, cy, z, yaw_extra=22)
            else:
                slot = "kitchen_table" if name in ("dining_room", "workshop", "laundry") else "side_table"
                table = prop(name + "_table", slot, cx, far_y, z, long_axis="X")
                prop(name + "_chair", "kitchen_chair", cx, far_y + (100 if side == "S" else -100), z, face_yaw=90 if side == "S" else -90)
                if table:
                    prop(name + "_books", "books", cx, far_y, table.top + .2)
                prop(name + "_cabinet", "wardrobe", x1 - 95, cy, z, face_yaw=180)
                if name in ("library", "study", "drawing_room"):
                    prop(name + "_armchair", "armchair", x0 + 115, cy, z, face_yaw=0)
            # Zocalo de madera y paneles en las salas nobles, no la misma pared desnuda en todas.
            if level != "basement" and name != "upstairs_bath":
                for py in range(int(y0 + 80), int(y1 - 60), 95):
                    block(name + "_panel_%d" % py, (x1 - 13, py - 35, z + 15),
                          (x1 - 9, py + 35, z + 88), mats["floor"], False)
                block(name + "_dado", (x1 - 16, y0 + 10, z + 92), (x1 - 8, y1 - 10, z + 96), mats["trim"], False)
            frame = prop(name + "_frame", "frame_medium", x1 - 18, cy + 110, z + 150, face_yaw=180)
            if frame and photos:
                # El helper del salon usa su pared oeste como referencia; se traslada el lienzo
                # al marco de esta estancia y se vuelve a adjuntar conservando transformacion.
                canvas = v.spawn_canvas("mansion_" + name, frame, "west", mats, photos[0])
                canvas.set_actor_location(v.V(frame.x - frame.wx * .45, frame.y, frame.z + frame.h * .5), False, False)
                canvas.set_actor_rotation(v.ML.make_rotation_from_axes(v.V(0, -1, 0), v.V(0, 0, 1), v.V(-1, 0, 0)), False)
            if name in ("library", "archive"):
                # Biblioteca de madera con libros escaneados; deja la puerta y su giro libres.
                for shelf in range(4):
                    shelf_z = z + 30 + shelf * 42
                    block(name + "_shelf_%d" % shelf, (x0 + 15, cy - 110, shelf_z),
                          (x0 + 50, cy + 110, shelf_z + 4), mats["floor"])
                    for book in range(4):
                        prop(name + "_book_%d_%d" % (shelf, book), "books", x0 + 32,
                             cy - 80 + book * 48, shelf_z + 4, yaw_extra=book * 5)
                for py in (cy - 114, cy + 110):
                    block(name + "_shelf_side_%d" % py, (x0 + 15, py, z), (x0 + 50, py + 4, z + 190), mats["floor"])
            room_audio = v.spawn_marked(unreal.VGRoomAudio, "mansion_" + name + "_audio", v.V(cx, cy, z + 140), folder="Mansion/Audio")
            room_audio.set_box_extent(v.V((x1 - x0) / 2 - 10, (y1 - y0) / 2 - 10, 130))
            room_audio.setup_reverb(1.5 if level == "basement" else .8, .5, .3)

    # Escaleras: 15 cm de contrahuella (< MaxStepHeight=30), rellano sin techo atravesandolo.
    for base_z in (-300, 0):
        for i, (mn, mx) in enumerate(stair_blocks(base_z)):
            block("stair_%d_%d" % (base_z, i), mn, mx, mats["floor"])
        # Peto central impide caer entre tramos, sin tapar la zona de giro del rellano.
        block("stair_spine_%d" % base_z, (2110, -180, base_z), (2190, 100, base_z + 245), mats["trim"])
        for i in range(10):
            y = -180 + i * 28
            top = base_z + (i + 1) * 15
            block("stair_rail_a_%d_%d" % (base_z, i), (2110, y, top + 95), (2115, y + 28, top + 100), mats["trim"])
            y = 100 - (i + 1) * 28
            top = base_z + 150 + (i + 1) * 15
            block("stair_rail_b_%d_%d" % (base_z, i), (2185, y, top + 95), (2190, y + 28, top + 100), mats["trim"])
    # Barandilla del hueco de la ultima planta. Los dos accesos a los tramos quedan libres al sur.
    for x in (1935, 2360):
        block("upper_guard_%d" % x, (x, -180, 300), (x + 5, 260, 405), mats["trim"])
    block("upper_guard_north", (1940, 260, 300), (2360, 265, 405), mats["trim"])
    v.STATE["mansion"] = True


def gameplay(v, out, door, info, mats):
    """Exploracion primero. Una sola presencia sin carrera ni fallo forzado de linterna."""
    identity = unreal.Transform()
    salon_lamp = out["floor_lamp"].actor if out.get("floor_lamp") else None
    switch = v.spawn_marked(unreal.VGLightSwitch, "mansion_salon_switch", v.V(info["door"]["opening"][0] - 20, -v.HY + 1, 108), folder="Mansion/Switches")
    switch.setup_mesh(v.eal.load_asset("/Engine/BasicShapes/Cube"), v.V(0, 0, 0), v.R())
    switch.get_editor_property("mesh").set_relative_scale3d(v.V(.08, .02, .1))
    switch.get_editor_property("mesh").set_material(0, mats["switch"])
    v.safe_set(switch, "switch_sound", v.sfx("switch_click"))
    if salon_lamp:
        switch.add_target(salon_lamp)
    v.spawn_marked(unreal.PlayerStart, "player_start", v.V(1100, -285, 95), v.R(yaw=0), folder="Gameplay")
    ambient = v.spawn_marked(unreal.VGAmbientAudio, "ambient_audio", v.V(1300, -285, 150), folder="Audio")
    ambient.set_bed_sound(v.sfx("room_tone_loop"), .3)
    for name in ("creak_wood_01", "creak_wood_02", "pipe_knock"):
        ambient.add_random_sound(v.sfx(name))
    # Interruptor del ala antigua: cada grupo es accionable, aunque empiece todo apagado.
    for key, lamp in list(v.STATE["house"]["lamps"].items()):
        lamp.set_on(False, False)
        if key.startswith("mansion_"):
            continue
        v.set_bool(lamp, "directly_interactable", True)
    for key, seconds, source in (("upstairs_steps", 90, (1600, -285, 320)),
                                  ("basement_pipe", 185, (2070, -600, -180))):
        t = v.trigger(key, (1500, -285, 110), (400, 100, 110), min_game_time=seconds,
                      auto_fire_after=seconds, require_player_inside=True, fire_on_overlap=False)
        t.add_step(v.action("PlaySound"), None, 0, v.sfx("creak_wood_02" if seconds == 90 else "pipe_knock"), v.at(t, *source), False)
    entity = v.spawn_entity("entity_watcher")
    if entity:
        # Volumen en el extremo OESTE de cada galeria; aparicion al ESTE, a mas de ocho metros.
        for level, z in LEVELS:
            t = v.trigger("presence_" + level, (975, -285, z + 100), (65, 85, 100),
                          min_game_time=300, required_entries=2, once=False)
            t.add_step(v.action("EntityAppear"), entity, 1.5, None,
                       unreal.Transform(location=v.V(1860, -285, z)), False)
            t.add_step(v.action("EntityWatch"), entity, 1.6, None,
                       unreal.Transform(location=v.V(600, 4, 0)), False)
    # Reglas de luz consistentes en editor y PIE: nada de una lampara encendida de fondo.
    for actor in v.actor_sub.get_all_level_actors():
        if isinstance(actor, unreal.VGLamp) and "VG" in [str(t) for t in actor.tags]:
            actor.set_on(False, False)
