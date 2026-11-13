"""Constructor procedural del salon de Vigilia. Idempotente: borra y regenera solo lo etiquetado como VG."""
import math
import os

import unreal

import vg_materials as vm
from vg_common import (PROJECT_DIR, cap_fab_textures, ROOT, SOURCE_DIR, WARNINGS, assets_under, configure_texture, eal, front_direction,
                       gltf_mapping, group_for, import_files, load_json, log, prepare_meshes, resolve_all, safe_set,
                       warn, yaw_of)

TAG = "VG"
MAP_PATH = ROOT + "/Maps/L_LivingRoom"
SFX_DIR = ROOT + "/Audio/SFX"

# Dimensiones interiores (cm): salon de 5,20 x 4,10 m con techo a 2,55 m, tipico de vivienda de los 90.
HX, HY, H, T = 260.0, 205.0, 255.0, 20.0

actor_sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
level_sub = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
ML = unreal.MathLibrary

STATE = {"metrics": {}, "overrides": {}, "unverified": [], "used": {}, "blockouts": []}


def V(x, y, z):
    return unreal.Vector(float(x), float(y), float(z))


def R(yaw=0.0, pitch=0.0, roll=0.0):
    return unreal.Rotator(roll=float(roll), pitch=float(pitch), yaw=float(yaw))


def sfx(name):
    path = "%s/%s" % (SFX_DIR, name)
    return eal.load_asset(path) if eal.does_asset_exist(path) else None


def mark(actor, key, folder, auto=None):
    tags = [TAG]
    if key:
        tags.append("VGSlot:" + key)
        actor.set_actor_label("VG_" + key)
    if auto:
        tags.append("VGAuto:%.2f,%.2f,%.2f,%.2f" % auto)
    safe_set(actor, "tags", tags)
    actor.set_folder_path("Vigilia/" + folder)


# --------------------------------------------------------------------------------------
# Piezas basicas
# --------------------------------------------------------------------------------------
def box(key, mn, mx, material, folder="Room", collision=True, shadow=True):
    cube = eal.load_asset("/Engine/BasicShapes/Cube")
    size = [mx[i] - mn[i] for i in range(3)]
    center = [(mx[i] + mn[i]) * 0.5 for i in range(3)]
    actor = actor_sub.spawn_actor_from_object(cube, V(*center), R())
    actor.set_actor_scale3d(V(size[0] / 100.0, size[1] / 100.0, size[2] / 100.0))
    comp = actor.static_mesh_component
    comp.set_material(0, material)
    if not collision:
        comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    if not shadow:
        safe_set(comp, "cast_shadow", False)
    mark(actor, key, folder)
    return actor


def wall_along_x(key, y0, y1, x0, x1, material, openings=()):
    """Pared que corre a lo largo de X con huecos (ox0, ox1, oz0, oz1)."""
    cursor = x0
    index = 0
    for ox0, ox1, oz0, oz1 in sorted(openings):
        if ox0 > cursor:
            box("%s_%d" % (key, index), (cursor, y0, 0), (ox0, y1, H), material)
            index += 1
        if oz0 > 0:
            box("%s_%d" % (key, index), (ox0, y0, 0), (ox1, y1, oz0), material)
            index += 1
        if oz1 < H:
            box("%s_%d" % (key, index), (ox0, y0, oz1), (ox1, y1, H), material)
            index += 1
        cursor = ox1
    if cursor < x1:
        box("%s_%d" % (key, index), (cursor, y0, 0), (x1, y1, H), material)


# --------------------------------------------------------------------------------------
# Colocacion de assets por caja envolvente (independiente del pivote y de los ejes del modelo)
# --------------------------------------------------------------------------------------
class Prep(object):
    def __init__(self, key, resolved, face_yaw=None, long_axis=None, tilt=None, yaw_extra=0.0):
        self.key = key
        self.resolved = resolved
        self.group = group_for(resolved)
        g = self.group
        yaw = 0.0
        if long_axis:
            long_is_x = g.size[0] >= g.size[1]
            yaw = 0.0 if long_is_x == (long_axis == "X") else 90.0
        elif face_yaw is not None:
            front, reliable = front_direction(resolved, g, STATE["metrics"])
            yaw = face_yaw - yaw_of(front)
            if not reliable:
                STATE["unverified"].append(key)
        yaw += yaw_extra
        rot = R(yaw=yaw)
        if tilt == "flat":
            # Tumba el objeto: su eje horizontal mas fino pasa a ser el vertical.
            lay = R(roll=90.0) if g.size[1] <= g.size[0] else R(pitch=90.0)
            rot = ML.compose_rotators(lay, rot)
        self.rotation = rot
        self.scale = self._sanity_scale()
        self._measure()

    def _sanity_scale(self):
        """Corrige errores de unidades al importar (m/cm/pulgadas): si el objeto mide mas del doble
        o menos de la mitad de su tamano real esperado, se escala uniformemente a ese tamano."""
        expected = self.resolved.spec.get("size_cm")
        if not expected:
            return 1.0
        biggest = max(self.group.size)
        if biggest <= 0.01:
            return 1.0
        ratio = expected / biggest
        if 0.5 <= ratio <= 2.0:
            return 1.0
        warn("'%s' mide %.0f cm y deberia rondar %.0f cm: se escala x%.3f (unidades del modelo)."
             % (self.key, biggest, expected, ratio))
        return ratio

    def _measure(self):
        g = self.group
        sc = self.scale
        xf = unreal.Transform(location=V(0, 0, 0), rotation=self.rotation, scale=V(sc, sc, sc))
        xs, ys, zs = [], [], []
        for cx in (g.min[0], g.max[0]):
            for cy in (g.min[1], g.max[1]):
                for cz in (g.min[2], g.max[2]):
                    p = ML.transform_location(xf, V(cx, cy, cz))
                    xs.append(p.x)
                    ys.append(p.y)
                    zs.append(p.z)
        self.rmin = (min(xs), min(ys), min(zs))
        self.rmax = (max(xs), max(ys), max(zs))
        self.wx = self.rmax[0] - self.rmin[0]
        self.wy = self.rmax[1] - self.rmin[1]
        self.h = self.rmax[2] - self.rmin[2]

    def spawn(self, x, y, z, cls=None, folder="Props", movable=False):
        """Coloca el objeto con el centro de su base en (x, y, z). Devuelve Placed."""
        ax = (self.rmin[0] + self.rmax[0]) * 0.5
        ay = (self.rmin[1] + self.rmax[1]) * 0.5
        loc = (x - ax, y - ay, z - self.rmin[2])
        rot = self.rotation
        auto = (loc[0], loc[1], loc[2], rot.yaw)
        override = STATE["overrides"].get(self.key)
        if override:
            dx, dy, dz = [override["loc"][i] - loc[i] for i in range(3)]
            loc = tuple(override["loc"])
            rot = R(yaw=override["yaw"], pitch=rot.pitch, roll=rot.roll)
            self.rotation = rot
            self._measure()
            x, y, z = x + dx, y + dy, z + dz

        main_mesh = self.group.main
        extras = [m for m in self.group.meshes if m != main_mesh]
        if cls is None:
            actor = actor_sub.spawn_actor_from_object(main_mesh, V(*loc), rot)
            if movable:
                actor.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        else:
            actor = actor_sub.spawn_actor_from_class(cls, V(*loc), rot)
            actor.setup_mesh(main_mesh, V(0, 0, 0), R())
        if self.scale != 1.0:
            actor.set_actor_scale3d(V(self.scale, self.scale, self.scale))
        mark(actor, self.key, folder, auto)
        for index, mesh in enumerate(extras):
            part = actor_sub.spawn_actor_from_object(mesh, V(*loc), rot)
            if self.scale != 1.0:
                part.set_actor_scale3d(V(self.scale, self.scale, self.scale))
            if movable or cls is not None:
                part.static_mesh_component.set_mobility(unreal.ComponentMobility.MOVABLE)
            mark(part, None, folder)
            part.set_actor_label("VG_%s_part%d" % (self.key, index + 1))
            part.attach_to_actor(actor, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                                 unreal.AttachmentRule.KEEP_WORLD, False)
        STATE["used"][self.key] = self.resolved
        return Placed(self, actor, x, y, z)


class Placed(object):
    def __init__(self, prep, actor, x, y, z):
        self.prep = prep
        self.actor = actor
        self.x, self.y, self.z = x, y, z
        self.wx, self.wy, self.h = prep.wx, prep.wy, prep.h
        self.min_x, self.max_x = x - prep.wx * 0.5, x + prep.wx * 0.5
        self.min_y, self.max_y = y - prep.wy * 0.5, y + prep.wy * 0.5
        self.top = z + prep.h


def surface_z(x, y, from_z, fallback):
    """Altura real de la superficie bajo (x, y): traza contra la geometria (tableros, asientos...).
    Si la traza no encuentra nada devuelve fallback (que puede ser None)."""
    try:
        world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
        hit = unreal.SystemLibrary.line_trace_single(world, V(x, y, from_z), V(x, y, from_z - 400.0),
                                                     unreal.TraceTypeQuery.TRACE_TYPE_QUERY1, True, [],
                                                     unreal.DrawDebugTrace.NONE, False)
        if hit:
            data = hit.to_tuple()
            if data[0]:
                return data[5].z
    except Exception as exc:  # noqa: BLE001
        warn("Traza de apoyo fallida en (%.0f, %.0f): %s" % (x, y, exc))
    return fallback


def put_on(prep, support, dx=0.0, dy=0.0, cls=None, folder="Props", movable=True, require_hit=False):
    """Apoya un objeto sobre otro. Con require_hit (asientos: su caja es mas alta que el cojin)
    no se coloca nada si la traza no encuentra la superficie real."""
    x, y = support.x + dx, support.y + dy
    z = surface_z(x, y, support.top + 40.0, None if require_hit else support.top)
    if z is None:
        warn("No se encontro apoyo para '%s' sobre '%s'; se omite." % (prep.key, support.prep.key))
        return None
    return prep.spawn(x, y, z + 0.2, cls=cls, folder=folder, movable=movable)


def fit_rotation(mesh, target_size):
    """Rotacion (multiplo de 90 grados) que deja la caja de la malla con el tamano objetivo (X, Y, Z)."""
    box_ = mesh.get_bounding_box()
    size = [box_.max.x - box_.min.x, box_.max.y - box_.min.y, box_.max.z - box_.min.z]
    best = None
    for yaw in (0, 90):
        for pitch in (0, 90):
            for roll in (0, 90):
                rot = R(yaw=yaw, pitch=pitch, roll=roll)
                xf = unreal.Transform(location=V(0, 0, 0), rotation=rot, scale=V(1, 1, 1))
                a = ML.transform_location(xf, V(*size))
                got = [abs(a.x), abs(a.y), abs(a.z)]
                err = sum(abs(got[i] - target_size[i]) for i in range(3))
                if best is None or err < best[0]:
                    best = (err, rot)
    return best[1]


# --------------------------------------------------------------------------------------
# Importacion de recursos propios (audio, ruido, cortina, fotos)
# --------------------------------------------------------------------------------------
def import_local_sources():
    audio_dir = os.path.join(SOURCE_DIR, "Audio")
    wavs = [os.path.join(audio_dir, f) for f in sorted(os.listdir(audio_dir)) if f.endswith(".wav")] if os.path.isdir(audio_dir) else []
    missing = [w for w in wavs if not eal.does_asset_exist("%s/%s" % (SFX_DIR, os.path.splitext(os.path.basename(w))[0]))]
    if missing:
        import_files(missing, SFX_DIR)
    for data in assets_under(SFX_DIR, ("SoundWave",)):
        if str(data.asset_name).endswith("_loop"):
            wave = data.get_asset()
            if not wave.get_editor_property("looping"):
                wave.set_editor_property("looping", True)
                eal.save_loaded_asset(wave, False)

    gen = os.path.join(SOURCE_DIR, "Generated")
    if not eal.does_asset_exist(ROOT + "/Textures/T_TVNoise"):
        import_files([os.path.join(gen, "T_TVNoise.png")], ROOT + "/Textures")
        noise = eal.load_asset(ROOT + "/Textures/T_TVNoise")
        if noise:
            configure_texture(noise, "linear")
    if not eal.does_asset_exist(ROOT + "/Meshes/SM_CurtainPanel"):
        import_files([os.path.join(gen, "SM_CurtainPanel.obj")], ROOT + "/Meshes")

    photos_dir = os.path.join(SOURCE_DIR, "Photos")
    photos = []
    if os.path.isdir(photos_dir):
        files = [os.path.join(photos_dir, f) for f in sorted(os.listdir(photos_dir)) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
        new = [f for f in files if not eal.does_asset_exist("%s/Textures/Photos/%s" % (ROOT, os.path.splitext(os.path.basename(f))[0]))]
        if new:
            import_files(new, ROOT + "/Textures/Photos")
        photos = [d.get_asset() for d in assets_under(ROOT + "/Textures/Photos", ("Texture2D",))]
    if not photos:
        # Sin fotos propias: cuadros y fotos antiguas CC0 (recortadas de los modelos de Poly Haven).
        art_dir = os.path.join(SOURCE_DIR, "DefaultArt")
        if os.path.isdir(art_dir):
            files = [os.path.join(art_dir, f) for f in sorted(os.listdir(art_dir)) if f.lower().endswith(".jpg")]
            new = [f for f in files if not eal.does_asset_exist("%s/Textures/DefaultArt/%s" % (ROOT, os.path.splitext(os.path.basename(f))[0]))]
            if new:
                import_files(new, ROOT + "/Textures/DefaultArt")
            photos = [d.get_asset() for d in assets_under(ROOT + "/Textures/DefaultArt", ("Texture2D",))]
    return photos


# --------------------------------------------------------------------------------------
# Materiales de superficie
# --------------------------------------------------------------------------------------
def build_materials(res):
    trim = res.get("trim_wood") or res.get("floor")
    if not trim:
        raise RuntimeError("Faltan las texturas base de Poly Haven. Ejecuta primero: python3 Tools/fetch_polyhaven.py")
    defaults = vm.classify_surface_textures(trim)
    if not all(defaults.values()):
        raise RuntimeError("Texturas base incompletas en %s" % trim.folder)

    masters = {p: vm.surface_master(p, defaults["BaseColor"], defaults["Normal"], defaults["ORM"]) for p in ("XY", "XZ", "YZ")}
    mats = {"paint": vm.paint_master(), "glass": vm.glass_master()}
    fabric = vm.fabric_master(defaults["BaseColor"], defaults["Normal"], defaults["ORM"])
    noise = eal.load_asset(ROOT + "/Textures/T_TVNoise")
    mats["tv_add"] = vm.tv_screen_master(noise, True)
    mats["tv_opaque"] = vm.tv_screen_master(noise, False)
    mats["photo_master"] = vm.photo_master(defaults["BaseColor"])
    mats["canvas_master"] = vm.canvas_master(defaults["BaseColor"])

    def surface(name, projection, **scalars):
        r = res.get(name)
        if not r:
            warn("Superficie '%s' sin texturas: se usa el material de madera por defecto" % name)
            return masters[projection]
        STATE["used"][name] = r
        tex = vm.classify_surface_textures(r)
        params = {"TileSize": r.spec.get("tile_cm", 200)}
        vectors = {}
        for key, value in scalars.items():
            (vectors if isinstance(value, tuple) else params)[key] = value
        return vm.instance("MI_%s_%s" % (name, projection), masters[projection], tex, params, vectors)

    # Paredes y suelo mas sucios y apagados (el papel de Megascans es naranja intenso).
    wall_tint = {"Tint": (0.62, 0.6, 0.56, 1)}
    mats["wall_XZ"] = surface("wall", "XZ", **wall_tint)
    mats["wall_YZ"] = surface("wall", "YZ", **wall_tint)
    mats["floor"] = surface("floor", "XY", RoughnessScale=0.85, Tint=(0.7, 0.68, 0.64, 1))
    mats["ceiling"] = surface("ceiling", "XY")
    mats["rug"] = surface("rug", "XY")

    curtain = res.get("curtain_fabric")
    if curtain:
        STATE["used"]["curtain_fabric"] = curtain
        mats["curtain"] = vm.instance("MI_Curtain", fabric, vm.classify_surface_textures(curtain),
                                      {"Tiling": 100.0 / curtain.spec.get("tile_cm", 120), "Transmission": 0.18},
                                      {"Tint": (0.92, 0.9, 0.86, 1)})
    else:
        mats["curtain"] = fabric

    mats["trim"] = vm.instance("MI_Paint_Trim", mats["paint"], None, {"Roughness": 0.42}, {"Color": (0.62, 0.57, 0.47, 1)})
    mats["switch"] = vm.instance("MI_Paint_Switch", mats["paint"], None, {"Roughness": 0.35}, {"Color": (0.78, 0.74, 0.62, 1)})
    mats["brass"] = vm.instance("MI_Paint_Brass", mats["paint"], None, {"Roughness": 0.38, "Metallic": 1.0}, {"Color": (0.45, 0.33, 0.16, 1)})
    mats["blockout"] = vm.instance("MI_Paint_Blockout", mats["paint"], None, {"Roughness": 0.5}, {"Color": (0.36, 0.25, 0.16, 1)})
    return mats


# --------------------------------------------------------------------------------------
# Arquitectura
# --------------------------------------------------------------------------------------
def horizontal_dims(resolved):
    g = group_for(resolved)
    return max(g.size[0], g.size[1]), min(g.size[0], g.size[1]), g.size[2]


def build_shell(res, mats):
    info = {}

    # --- Puerta (pared sur, junto a la esquina este) ---
    door_res = res.get("door")
    if door_res:
        door_w, door_t, door_h = horizontal_dims(door_res)
        door_h = min(door_h, H - 6.0)
    else:
        door_w, door_t, door_h = 82.5, 4.0, 203.0
    door_x0 = 250.0 - 12.0 - door_w
    opening = (door_x0 - 1.0, door_x0 + door_w + 1.0, 0.0, door_h + 1.0)
    info["door"] = dict(x0=door_x0, w=door_w, t=door_t, h=door_h, opening=opening)

    # --- Ventana (pared norte) ---
    win_res = res.get("window")
    if win_res:
        win_w, win_t, win_h = horizontal_dims(win_res)
    else:
        win_w, win_t, win_h = 120.0, 6.0, 125.0
    win_cx = -30.0
    win_z0 = max(40.0, min(92.0, H - 22.0 - win_h))
    win_open = (win_cx - win_w * 0.5, win_cx + win_w * 0.5, win_z0, min(win_z0 + win_h, H - 8.0))
    info["window"] = dict(cx=win_cx, w=win_w, t=win_t, h=win_h, z0=win_z0, opening=win_open)

    # --- Suelo, techo y paredes del salon ---
    box("floor", (-HX - T, -HY - T, -T), (HX + T, HY + T, 0), mats["floor"])
    box("ceiling", (-HX - T, -HY - T, H), (HX + T, HY + T, H + T), mats["ceiling"])
    box("wall_west", (-HX - T, -HY, 0), (-HX, HY, H), mats["wall_YZ"])
    box("wall_east", (HX, -HY, 0), (HX + T, HY, H), mats["wall_YZ"])
    wall_along_x("wall_north", HY, HY + T, -HX - T, HX + T, mats["wall_XZ"], [win_open])
    wall_along_x("wall_south", -HY - T, -HY, -HX - T, HX + T, mats["wall_XZ"], [opening])

    # --- Pasillo oscuro al otro lado de la puerta ---
    cy0, cy1 = -HY - T - 135.0, -HY - T
    cx0, cx1 = 40.0, HX + T
    box("hall_floor", (cx0 - T, cy0 - T, -T), (cx1 + T, cy1, 0), mats["floor"])
    box("hall_ceiling", (cx0 - T, cy0 - T, H), (cx1 + T, cy1, H + T), mats["ceiling"])
    box("hall_wall_south", (cx0 - T, cy0 - T, 0), (cx1 + T, cy0, H), mats["wall_XZ"])
    box("hall_wall_west", (cx0 - T, cy0, 0), (cx0, cy1, H), mats["wall_YZ"])
    box("hall_wall_east", (cx1, cy0, 0), (cx1 + T, cy1, H), mats["wall_YZ"])
    info["hall"] = dict(x0=cx0, x1=cx1, y0=cy0, y1=cy1)

    # --- Rodapie ---
    bh, bt = 8.0, 1.4
    box("base_west", (-HX, -HY, 0), (-HX + bt, HY, bh), mats["trim"], collision=False)
    box("base_east", (HX - bt, -HY, 0), (HX, HY, bh), mats["trim"], collision=False)
    box("base_north", (-HX, HY - bt, 0), (HX, HY, bh), mats["trim"], collision=False)
    box("base_south_a", (-HX, -HY, 0), (opening[0] - 7.0, -HY + bt, bh), mats["trim"], collision=False)
    if opening[1] + 7.0 < HX:
        box("base_south_b", (opening[1] + 7.0, -HY, 0), (HX, -HY + bt, bh), mats["trim"], collision=False)

    # --- Marco de la puerta (si el modelo no trae el suyo) ---
    framed = door_res is not None and door_t >= 11.0
    if not framed:
        jy0, jy1 = -HY - T - 1.5, -HY + 1.5
        box("door_jamb_l", (opening[0] - 6.0, jy0, 0), (opening[0], jy1, opening[3] + 6.0), mats["trim"])
        box("door_jamb_r", (opening[1], jy0, 0), (opening[1] + 6.0, jy1, opening[3] + 6.0), mats["trim"])
        box("door_lintel", (opening[0], jy0, opening[3]), (opening[1], jy1, opening[3] + 6.0), mats["trim"])
    info["door"]["framed"] = framed
    return info


def build_door(res, mats, info):
    d = info["door"]
    door_cls = unreal.VGDoor
    leaf_y = -HY - T * 0.5 if d["framed"] else -HY - 4.0
    door = actor_sub.spawn_actor_from_class(door_cls, V(d["x0"], leaf_y, 0.0), R(yaw=-90.0))
    door_res = res.get("door")
    if door_res:
        door.setup_door_mesh(group_for(door_res).main)
        STATE["used"]["door"] = door_res
    else:
        # Prototipo: hoja lisa hasta que se anada la puerta de Megascans desde Fab.
        door.setup_door_mesh(eal.load_asset("/Engine/BasicShapes/Cube"))
        mesh = door.get_editor_property("mesh")
        mesh.set_relative_scale3d(V(d["t"] / 100.0, d["w"] / 100.0, d["h"] / 100.0))
        mesh.set_relative_location(V(0, d["w"] * 0.5, d["h"] * 0.5), False, False)
        mesh.set_material(0, mats["blockout"])
        STATE["blockouts"].append("door")
    safe_set(door, "open_sound", sfx("door_open_creak"))
    safe_set(door, "close_sound", sfx("door_close"))
    safe_set(door, "slam_sound", sfx("door_slam"))
    safe_set(door, "locked_sound", sfx("door_locked"))
    mark(door, "door", "Interactables")
    return door


def build_window(res, mats, info):
    w = info["window"]
    x0, x1, z0, z1 = w["opening"]
    win_res = res.get("window")
    if win_res:
        prep = Prep("window", win_res, long_axis="X")
        prep.spawn(w["cx"], HY + T * 0.5, z0, folder="Room")
        STATE["unverified"].append("window")
    else:
        # Prototipo: marco y cristal simples hasta que se anada la ventana de Megascans.
        y0, y1 = HY + 6.0, HY + 12.0
        f = 5.0
        box("window_frame_l", (x0, y0, z0), (x0 + f, y1, z1), mats["trim"])
        box("window_frame_r", (x1 - f, y0, z0), (x1, y1, z1), mats["trim"])
        box("window_frame_b", (x0, y0, z0), (x1, y1, z0 + f), mats["trim"])
        box("window_frame_t", (x0, y0, z1 - f), (x1, y1, z1), mats["trim"])
        box("window_mullion", (w["cx"] - 2.5, y0, z0), (w["cx"] + 2.5, y1, z1), mats["trim"])
        box("window_glass", (x0, y0 + 2.5, z0), (x1, y0 + 3.1, z1), mats["glass"], collision=True, shadow=False)
        box("window_sill", (x0 - 6.0, HY - 5.0, z0 - 3.0), (x1 + 6.0, HY + 8.0, z0), mats["trim"])
        STATE["blockouts"].append("window")

    # Cortinas: dos paneles plisados recogidos a los lados y barra de laton.
    panel = eal.load_asset(ROOT + "/Meshes/SM_CurtainPanel")
    top = min(H - 6.0, z1 + 16.0)
    if panel:
        rot = fit_rotation(panel, (105.0, 13.0, 238.0))
        xf = unreal.Transform(location=V(0, 0, 0), rotation=rot, scale=V(1, 1, 1))
        pb = panel.get_bounding_box()
        a, b = ML.transform_location(xf, pb.min), ML.transform_location(xf, pb.max)
        lo = (min(a.x, b.x), min(a.y, b.y), min(a.z, b.z))
        hi = (max(a.x, b.x), max(a.y, b.y), max(a.z, b.z))
        sx = 0.60
        sz = (top - 3.0) / max(hi[2] - lo[2], 1.0)
        for side, cx in (("l", x0 - 4.0), ("r", x1 + 4.0)):
            loc = V(cx - (lo[0] + hi[0]) * 0.5 * sx, HY - 9.0 - (lo[1] + hi[1]) * 0.5, top - hi[2] * sz)
            actor = actor_sub.spawn_actor_from_object(panel, loc, rot)
            # La escala se aplica en ejes del mundo: se traslada a los ejes locales segun la rotacion elegida.
            local = ML.inverse_transform_direction(xf, V(sx, 1.0, sz))
            actor.set_actor_scale3d(V(abs(local.x) or 1.0, abs(local.y) or 1.0, abs(local.z) or 1.0))
            comp = actor.static_mesh_component
            comp.set_material(0, mats["curtain"])
            comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
            mark(actor, "curtain_" + side, "Room")
    cyl = eal.load_asset("/Engine/BasicShapes/Cylinder")
    rod = actor_sub.spawn_actor_from_object(cyl, V(w["cx"], HY - 9.0, top + 1.5), R(pitch=90.0))
    rod.set_actor_scale3d(V(0.025, 0.025, (w["w"] + 110.0) / 100.0))
    rod.static_mesh_component.set_material(0, mats["brass"])
    rod.static_mesh_component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    mark(rod, "curtain_rod", "Room")


# --------------------------------------------------------------------------------------
# Mobiliario, decoracion e interactuables
# --------------------------------------------------------------------------------------
def examinable(actor, name, text):
    safe_set(actor, "display_name", name)
    safe_set(actor, "examine_text", text)
    safe_set(actor, "pick_up_sound", sfx("object_pickup"))
    safe_set(actor, "put_down_sound", sfx("object_putdown"))


def find_slot(mesh, keywords):
    try:
        for index, slot in enumerate(mesh.get_editor_property("static_materials")):
            name = str(slot.get_editor_property("material_slot_name")).lower()
            if any(k in name for k in keywords):
                return index
    except Exception as exc:  # noqa: BLE001
        warn("Slots de material de %s: %s" % (mesh.get_name(), exc))
    return -1


def setup_television(tv, prep, mats):
    g = prep.group
    mesh = g.main
    metric = STATE["metrics"].get(prep.resolved.polyhaven_id or "", {})
    slot = find_slot(mesh, ("screen", "glass", "display", "crt", "tube", "pantalla"))
    front, _ = front_direction(prep.resolved, g, STATE["metrics"])
    right = (-front[1], front[0])
    depth_half = (g.size[0] if abs(front[0]) > 0.5 else g.size[1]) * 0.5
    width = g.size[1] if abs(front[0]) > 0.5 else g.size[0]
    sw, sh, cx_off, cz, inset = width * 0.55, g.size[2] * 0.5, 0.0, g.min[2] + g.size[2] * 0.55, -0.4

    screen = metric.get("screen")
    mapping = gltf_mapping(g, metric) if screen else None
    if screen and mapping:
        right = mapping(1, 0)
        sw, sh = screen["width_cm"], screen["height_cm"]
        cx_off, cz, inset = screen["center_x_cm"], g.min[2] + screen["center_height_cm"], screen["inset_from_front_cm"]
    elif slot < 0:
        warn("Televisor '%s': no se encontro un slot de pantalla; se usa un plano aproximado. Revisalo." % mesh.get_name())
        STATE["unverified"].append("television(pantalla)")

    fwd = V(front[0], front[1], 0)
    rgt = V(right[0], right[1], 0)
    center = V(g.center[0] + right[0] * cx_off + front[0] * (depth_half - inset),
               g.center[1] + right[1] * cx_off + front[1] * (depth_half - inset), cz)
    # Plano: X local = ancho, Z local = normal hacia el espectador, Y local = alto (F x R es vertical).
    up = V(0, 0, front[0] * right[1] - front[1] * right[0])
    plane_rot = ML.make_rotation_from_axes(rgt, up, fwd)
    plane_xf = unreal.Transform(location=center, rotation=plane_rot, scale=V(sw / 100.0, sh / 100.0, 1.0))
    glow_loc = V(center.x + front[0] * 4.0, center.y + front[1] * 4.0, center.z)

    if slot < 0:
        safe_set(tv.get_editor_property("screen_plane"), "static_mesh", eal.load_asset("/Engine/BasicShapes/Plane"))
    tv.setup_screen(mats["tv_opaque"] if slot >= 0 else mats["tv_add"], slot, plane_xf, glow_loc,
                    ML.make_rot_from_x(fwd), sw, sh)
    safe_set(tv, "power_sound", sfx("tv_power"))
    safe_set(tv, "static_loop_sound", sfx("tv_static_loop"))


def setup_lamp(lamp, prep, lumens=150.0):
    g = prep.group
    top = g.centroid(0.2) or [0.0, 0.0]
    local = V(g.center[0] + top[0] * g.size[0], g.center[1] + top[1] * g.size[1], g.min[2] + g.size[2] * 0.86)
    lamp.setup_light(local, lumens, 2400.0, 520.0)
    # Una bombilla a pocos cm de la pared la quema (mancha blanca). Se separa hacia el centro
    # de la sala lo que haga falta para quedar a >= 35 cm de las paredes, y se suaviza la fuente.
    light = lamp.get_editor_property("light")
    pos = light.get_world_location()
    x = max(-HX + 35.0, min(HX - 35.0, pos.x))
    y = max(-HY + 35.0, min(HY - 35.0, pos.y))
    light.set_world_location(V(x, y, pos.z), False, False)
    safe_set(light, "source_radius", 6.0)
    safe_set(light, "soft_source_radius", 18.0)
    safe_set(lamp, "switch_sound", sfx("switch_click"))


def furnish(res, mats, info, photos):
    out = {}

    def prep(key, **kw):
        r = res.get(key)
        if not r:
            return None
        return Prep(key, r, **kw)

    # --- Sofa contra la pared oeste, mirando al televisor ---
    p = prep("sofa", face_yaw=0.0)
    sofa = p.spawn(-HX + 6.0 + p.wx * 0.5, -10.0, 0.0, folder="Furniture") if p else None
    out["sofa"] = sofa
    sofa_front = sofa.max_x if sofa else -170.0
    sofa_min_y, sofa_max_y = (sofa.min_y, sofa.max_y) if sofa else (-110.0, 90.0)

    # --- Mesa de centro y alfombra ---
    p = prep("coffee_table", long_axis="Y")
    table = p.spawn(sofa_front + 44.0 + p.wx * 0.5, -10.0, 0.0, folder="Furniture") if p else None
    out["coffee_table"] = table
    rug_cx = table.x if table else sofa_front + 80.0
    box("rug", (rug_cx - 105.0, -150.0, 0.0), (rug_cx + 105.0, 130.0, 1.2), mats["rug"], folder="Furniture", collision=False)

    # --- Mueble de TV y televisor en la pared este ---
    p = prep("tv_stand", face_yaw=180.0)
    stand = p.spawn(HX - 4.0 - p.wx * 0.5, -10.0, 0.0, folder="Furniture") if p else None
    out["tv_stand"] = stand
    p = prep("television", face_yaw=180.0)
    if p and stand:
        tv = put_on(p, stand, cls=unreal.VGTelevision, folder="Interactables")
        setup_television(tv.actor, p, mats)
        out["television"] = tv

    # --- Sillon girado hacia el televisor ---
    p = prep("armchair", face_yaw=28.0)
    out["armchair"] = p.spawn(-35.0, -138.0, 0.0, folder="Furniture") if p else None

    # --- Mesita auxiliar y lampara ---
    p = prep("side_table", long_axis="Y")
    side = p.spawn(-HX + 7.0 + p.wx * 0.5, min(sofa_max_y + 10.0 + p.wy * 0.5, HY - 30.0), 0.0, folder="Furniture") if p else None
    out["side_table"] = side
    p = prep("floor_lamp")
    if p:
        if p.h > 120.0 or not side:
            lamp = p.spawn(-HX + 9.0 + p.wx * 0.5, max(sofa_min_y - 14.0 - p.wy * 0.5, -HY + 30.0), 0.0,
                           cls=unreal.VGLamp, folder="Interactables")
        else:
            lamp = put_on(p, side, cls=unreal.VGLamp, folder="Interactables")
        setup_lamp(lamp.actor, p)
        out["floor_lamp"] = lamp

    # --- Reloj de pie en la pared sur ---
    p = prep("grandfather_clock", face_yaw=90.0)
    if p:
        clock = p.spawn(-185.0, -HY + 3.0 + p.wy * 0.5, 0.0, folder="Furniture")
        out["grandfather_clock"] = clock
        tick = actor_sub.spawn_actor_from_class(unreal.AmbientSound, V(clock.x, clock.y, 150.0), R())
        comp = tick.get_component_by_class(unreal.AudioComponent)
        safe_set(comp, "sound", sfx("clock_tick_loop"))
        safe_set(comp, "volume_multiplier", 0.55)
        safe_set(comp, "override_attenuation", True)
        try:
            att = comp.get_editor_property("attenuation_overrides")
            att.set_editor_property("falloff_distance", 900.0)
            att.set_editor_property("attenuation_shape_extents", V(40, 0, 0))
            comp.set_editor_property("attenuation_overrides", att)
        except Exception as exc:  # noqa: BLE001
            warn("Atenuacion del reloj: %s" % exc)
        mark(tick, "clock_tick", "Audio")

    # --- Planta, radiocasete grande y radiador ---
    p = prep("plant")
    out["plant"] = p.spawn(212.0, 158.0, 0.0, folder="Decor") if p else None
    p = prep("boombox", face_yaw=180.0, yaw_extra=-14.0)
    if p and stand and stand.max_y + 30.0 + p.wy < HY - 60.0:
        out["boombox"] = p.spawn(HX - 8.0 - p.wx * 0.5, stand.max_y + 28.0 + p.wy * 0.5, 0.0, folder="Decor")
    p = prep("radiator", face_yaw=-90.0)
    if p:
        out["radiator"] = p.spawn(info["window"]["cx"], HY - 3.0 - p.wy * 0.5, 9.0, folder="Decor")

    # --- Cuadros colgados ---
    def hang(key, wall, along, center_z):
        hp = prep(key, face_yaw={"west": 0.0, "south": 90.0, "north": -90.0}[wall])
        if not hp:
            return None
        z = center_z - hp.h * 0.5
        if wall == "west":
            return hp.spawn(-HX + hp.wx * 0.5 + 0.3, along, z, folder="Decor", movable=True)
        if wall == "south":
            return hp.spawn(along, -HY + hp.wy * 0.5 + 0.3, z, folder="Decor", movable=True)
        return hp.spawn(along, HY - hp.wy * 0.5 - 0.3, z, folder="Decor", movable=True)

    out["frame_large"] = hang("frame_large", "west", -10.0, 172.0)
    out["frame_medium"] = hang("frame_medium", "south", -65.0, 160.0)
    out["frame_oval"] = hang("frame_oval", "north", 178.0, 158.0)

    # --- Objetos sobre el mueble de TV ---
    if stand:
        p = prep("mantel_clock", face_yaw=180.0)
        if p and stand.wy > 125.0:
            out["mantel_clock"] = put_on(p, stand, dy=-(stand.wy * 0.5 - p.wy * 0.5 - 8.0))
        p = prep("frame_standing", face_yaw=180.0, yaw_extra=18.0)
        if p and stand.wy > 125.0:
            out["frame_standing"] = put_on(p, stand, dy=stand.wy * 0.5 - p.wy * 0.5 - 9.0)

    # --- Objetos sobre la mesa de centro ---
    if table:
        p = prep("books", long_axis="Y", yaw_extra=11.0)
        if p:
            out["books"] = put_on(p, table, dx=-4.0, dy=-table.wy * 0.24)
        p = prep("ashtray")
        if p:
            out["ashtray"] = put_on(p, table, dx=6.0, dy=table.wy * 0.05)
        p = prep("cassette_player", tilt="flat", yaw_extra=24.0)
        if p:
            item = put_on(p, table, dx=-2.0, dy=table.wy * 0.27, cls=unreal.VGExaminable, folder="Interactables")
            examinable(item.actor, "la grabadora", "Una grabadora de casete. Dentro hay una cinta sin etiqueta.")
            out["cassette_player"] = item

    # --- Objetos sobre la mesita ---
    if side:
        p = prep("frame_small", face_yaw=0.0, yaw_extra=-12.0)
        if p:
            item = put_on(p, side, dx=2.0, dy=-side.wy * 0.18, cls=unreal.VGExaminable, folder="Interactables")
            examinable(item.actor, "la fotografia", "La foto esta descolorida. No reconoces a nadie.")
            out["frame_small"] = item
        p = prep("vase")
        if p:
            out["vase"] = put_on(p, side, dx=-4.0, dy=side.wy * 0.22)
        p = prep("telephone", face_yaw=0.0)
        if p:
            out["telephone"] = put_on(p, side, dx=4.0, dy=0.0)
        p = prep("book_old", tilt=None)
        if p and not res.get("telephone"):
            item = put_on(p, side, dx=5.0, dy=0.0, cls=unreal.VGExaminable, folder="Interactables")
            examinable(item.actor, "el libro", "Las paginas estan hinchadas por la humedad.")
            out["book_old"] = item

    # --- Detalles sobre el sofa, el sillon y el suelo ---
    if sofa:
        p = prep("cushion")
        if p:
            out["cushion"] = put_on(p, sofa, dx=6.0, dy=sofa.wy * 0.28, require_hit=True)
    if out.get("armchair"):
        p = prep("toy_bear")
        if p:
            item = put_on(p, out["armchair"], dx=4.0, dy=3.0, cls=unreal.VGExaminable, folder="Interactables", require_hit=True)
            if item:
                examinable(item.actor, "el juguete", "Un oso de madera. Alguien lo ha dejado mirando hacia la puerta.")
                out["toy_bear"] = item
    p = prep("newspaper")
    if p:
        out["newspaper"] = p.spawn(25.0, -95.0, 0.3, folder="Decor")

    add_pictures(out, mats, photos)
    return out


# --------------------------------------------------------------------------------------
# Imagenes en los marcos: SourceAssets/Photos (o DefaultArt si no hay fotos propias)
# --------------------------------------------------------------------------------------
FRAME_WALLS = {"frame_large": "west", "frame_medium": "south", "frame_oval": "north"}
WALL_NORMALS = {"west": (1.0, 0.0), "south": (0.0, 1.0), "north": (0.0, -1.0)}


def _aspect(tex):
    try:
        return tex.blueprint_get_size_x() / float(max(tex.blueprint_get_size_y(), 1))
    except Exception:  # noqa: BLE001
        return 1.0


def _pick_photo(photos, used, aspect):
    """Foto aun no usada con la proporcion mas parecida (retrato para marcos verticales, etc.)."""
    pool = [p for p in photos if p.get_name() not in used] or photos
    best = min(pool, key=lambda p: abs(math.log(max(_aspect(p), 0.01) / max(aspect, 0.01))))
    used.add(best.get_name())
    return best


def _cover_crop(photo_aspect, canvas_aspect):
    """Encuadre tipo "cover": rellena el lienzo sin deformar, recortando lo que sobre."""
    if photo_aspect > canvas_aspect:
        return canvas_aspect / photo_aspect, 1.0
    return 1.0, photo_aspect / canvas_aspect


def spawn_canvas(key, placed, wall, mats, photo, mirror=False):
    nx, ny = WALL_NORMALS[wall]
    along = (-ny, nx)
    face_w = placed.wy if wall == "west" else placed.wx
    width, height = face_w * 0.9, placed.h * 0.9
    cz = placed.z + placed.h * 0.5
    # A media profundidad del marco: por delante de un posible fondo y por detras de la moldura.
    depth = placed.wx if wall == "west" else placed.wy
    inset = max(0.5, depth * 0.45)
    if wall == "west":
        loc = V(-HX + inset, placed.y, cz)
    elif wall == "south":
        loc = V(placed.x, -HY + inset, cz)
    else:
        loc = V(placed.x, HY - inset, cz)
    # Ejes del plano: X = a lo largo de la pared, Y = arriba, Z = normal hacia la sala.
    rot = ML.make_rotation_from_axes(V(along[0], along[1], 0), V(0, 0, 1), V(nx, ny, 0))
    actor = actor_sub.spawn_actor_from_object(eal.load_asset("/Engine/BasicShapes/Plane"), loc, rot)
    actor.set_actor_scale3d(V(width / 100.0, height / 100.0, 1.0))
    comp = actor.static_mesh_component
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    crop_u, crop_v = _cover_crop(_aspect(photo), width / max(height, 1.0))
    inst = vm.instance("MI_Canvas_%s%s" % (key, "_mirror" if mirror else ""), mats["canvas_master"], {"Image": photo},
                       {"CropU": crop_u, "CropV": crop_v, "Mirror": 1.0 if mirror else 0.0,
                        "Darkness": 0.6 if mirror else 0.85})
    comp.set_material(0, inst)
    mark(actor, "canvas_%s%s" % (key, "_mirror" if mirror else ""), "Decor")
    # El lienzo se mueve con el cuadro (p. ej. cuando un evento lo tuerce).
    actor.attach_to_actor(placed.actor, "", unreal.AttachmentRule.KEEP_WORLD, unreal.AttachmentRule.KEEP_WORLD,
                          unreal.AttachmentRule.KEEP_WORLD, False)
    return actor


def add_pictures(out, mats, photos):
    """Pone una imagen en cada marco. Marcos con superficie propia (Poly Haven): se sustituye su material.
    Marcos vacios (Megascans): lienzo detras. En el cuadro grande se crea ademas una copia en espejo
    oculta que un evento intercambia cuando no lo miras."""
    STATE["canvases"] = {}
    if not photos:
        return
    used = set()
    for key in ("frame_large", "frame_medium", "frame_oval", "frame_standing", "frame_small"):
        placed = out.get(key)
        if not placed:
            continue
        slot = find_slot(placed.prep.group.main, ("artwork", "canvas", "photo", "picture"))
        if slot >= 0:
            photo = _pick_photo(photos, used, 1.0)
            inst = vm.instance("MI_Photo_%s" % key, mats["photo_master"], {"Image": photo})
            placed.actor.get_component_by_class(unreal.StaticMeshComponent).set_material(slot, inst)
            continue
        wall = FRAME_WALLS.get(key)
        if not wall:
            continue  # marcos de mesa sin superficie: se dejan tal cual
        face_w = placed.wy if wall == "west" else placed.wx
        photo = _pick_photo(photos, used, face_w / max(placed.h, 1.0))
        normal = spawn_canvas(key, placed, wall, mats, photo)
        entry = {"normal": normal}
        if key == "frame_large":
            mirrored = spawn_canvas(key, placed, wall, mats, photo, mirror=True)
            mirrored.set_actor_hidden_in_game(True)
            entry["mirror"] = mirrored
        STATE["canvases"][key] = entry


# --------------------------------------------------------------------------------------
# Iluminacion, postproceso, audio y eventos
# --------------------------------------------------------------------------------------
def spawn_marked(cls, key, loc, rot=None, folder="Lighting"):
    actor = actor_sub.spawn_actor_from_class(cls, loc, rot or R())
    mark(actor, key, folder)
    return actor


def build_lighting(info):
    w = info["window"]
    win_z = (w["opening"][2] + w["opening"][3]) * 0.5

    spawn_marked(unreal.SkyAtmosphere, "sky_atmosphere", V(0, 0, 0))
    moon = spawn_marked(unreal.DirectionalLight, "moon", V(0, 600, 600), R(yaw=-78.0, pitch=-55.0))
    comp = moon.get_component_by_class(unreal.DirectionalLightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    safe_set(comp, "intensity", 0.2)
    safe_set(comp, "light_color", unreal.Color(r=168, g=192, b=255, a=255))
    safe_set(comp, "atmosphere_sun_light", True)

    sky = spawn_marked(unreal.SkyLight, "skylight", V(0, 0, 400))
    comp = sky.get_component_by_class(unreal.SkyLightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    safe_set(comp, "real_time_capture", True)
    safe_set(comp, "intensity", 0.12)
    safe_set(comp, "light_color", unreal.Color(r=150, g=170, b=210, a=255))

    # Farola fria en la calle: entra en diagonal por la ventana y dibuja las cortinas en la pared.
    # Fria a proposito: contrasta con la lampara calida del salon (una farola de sodio lo tenia todo naranja).
    street = spawn_marked(unreal.SpotLight, "street_lamp", V(w["cx"] + 210.0, HY + 330.0, win_z + 190.0))
    target = V(w["cx"] - 40.0, HY - 60.0, win_z - 40.0)
    street.set_actor_rotation(ML.find_look_at_rotation(street.get_actor_location(), target), False)
    comp = street.get_component_by_class(unreal.SpotLightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    safe_set(comp, "intensity_units", unreal.LightUnits.LUMENS)
    safe_set(comp, "intensity", 700.0)
    safe_set(comp, "use_temperature", True)
    safe_set(comp, "temperature", 8500.0)
    safe_set(comp, "attenuation_radius", 1600.0)
    safe_set(comp, "inner_cone_angle", 16.0)
    safe_set(comp, "outer_cone_angle", 30.0)
    safe_set(comp, "source_radius", 12.0)
    # Rayos visibles en el polvo: la luz fria "corta" la habitacion.
    safe_set(comp, "volumetric_scattering_intensity", 4.0)

    fog = spawn_marked(unreal.ExponentialHeightFog, "fog", V(0, 0, 0))
    comp = fog.get_component_by_class(unreal.ExponentialHeightFogComponent)
    safe_set(comp, "fog_density", 0.03)
    safe_set(comp, "fog_height_falloff", 0.05)
    safe_set(comp, "enable_volumetric_fog", True)
    safe_set(comp, "volumetric_fog_scattering_distribution", 0.6)
    safe_set(comp, "volumetric_fog_extinction_scale", 1.4)

    ppv = spawn_marked(unreal.PostProcessVolume, "post_process", V(0, 0, 100))
    safe_set(ppv, "unbound", True)
    s = ppv.get_editor_property("settings")
    values = {
        # --- Ambiente: penumbra fria, colores apagados, una sola luz calida y debil ---
        # Rango de exposicion estrecho (EV100 0-2,5): la camara NO "normaliza" la sala; la zona de la
        # lampara se ve iluminada y todo lo demas se queda en sombra. Con la lampara apagada se ve la
        # ventana y siluetas (y la linterna, F).
        "auto_exposure_min_brightness": 0.0,
        "auto_exposure_max_brightness": 2.5,
        "auto_exposure_bias": -0.5,
        "auto_exposure_speed_up": 0.8,
        "auto_exposure_speed_down": 0.5,
        "bloom_intensity": 0.12,
        "vignette_intensity": 0.7,
        "film_grain_intensity": 0.35,
        "scene_fringe_intensity": 0.25,
        # Gradacion: desaturado y algo verdoso (estetica de cinta VHS vieja / P.T.), negros densos.
        "color_saturation": unreal.Vector4(x=0.55, y=0.55, z=0.55, w=1.0),
        "color_contrast": unreal.Vector4(x=1.12, y=1.12, z=1.12, w=1.0),
        "color_gain": unreal.Vector4(x=0.9, y=1.0, z=0.96, w=1.0),
        "color_saturation_highlights": unreal.Vector4(x=0.7, y=0.7, z=0.7, w=1.0),
        "color_gamma_shadows": unreal.Vector4(x=0.95, y=1.0, z=1.03, w=1.0),
        "lumen_scene_lighting_quality": 2.0,
        "lumen_scene_detail": 2.0,
        "lumen_final_gather_quality": 2.0,
        "lumen_reflection_quality": 2.0,
        "ambient_occlusion_intensity": 0.6,
    }
    for name, value in values.items():
        try:
            s.set_editor_property("override_" + name, True)
            s.set_editor_property(name, value)
        except Exception as exc:  # noqa: BLE001
            warn("Postproceso %s: %s" % (name, exc))
    safe_set(ppv, "settings", s)


def action(name):
    wanted = name.replace("_", "").lower()
    for attr in dir(unreal.VGEventAction):
        if attr.replace("_", "").lower() == wanted:
            return getattr(unreal.VGEventAction, attr)
    raise RuntimeError("Accion de evento desconocida: " + name)


def trigger(key, center, extent, **props):
    actor = actor_sub.spawn_actor_from_class(unreal.VGEventTrigger, V(*center), R())
    actor.set_box_extent(V(*extent))
    for name, value in props.items():
        safe_set(actor, name, value)
    mark(actor, key, "Events")
    return actor


def build_gameplay(out, door, info, mats):
    identity = unreal.Transform()
    lamp = out["floor_lamp"].actor if out.get("floor_lamp") else None
    tv = out["television"].actor if out.get("television") else None
    d = info["door"]

    # Interruptor junto a la puerta: controla la lampara del salon.
    sx = d["opening"][0] - 22.0
    switch = actor_sub.spawn_actor_from_class(unreal.VGLightSwitch, V(sx, -HY + 0.6, 108.0), R())
    switch.setup_mesh(eal.load_asset("/Engine/BasicShapes/Cube"), V(0, 0, 0), R())
    mesh = switch.get_editor_property("mesh")
    mesh.set_relative_scale3d(V(0.08, 0.012, 0.08))
    mesh.set_material(0, mats["switch"])
    safe_set(switch, "switch_sound", sfx("switch_click"))
    if lamp:
        switch.add_target(lamp)
    mark(switch, "light_switch", "Interactables")

    # Audio ambiental: tono de sala + sonidos domesticos lejanos.
    ambient = actor_sub.spawn_actor_from_class(unreal.VGAmbientAudio, V(0, 0, 150), R())
    ambient.set_bed_sound(sfx("room_tone_loop"), 0.5)
    for name in ("creak_wood_01", "creak_wood_02", "distant_thump", "pipe_knock"):
        ambient.add_random_sound(sfx(name))
    mark(ambient, "ambient_audio", "Audio")

    start = actor_sub.spawn_actor_from_class(unreal.PlayerStart, V(d["x0"] + d["w"] * 0.5 - 20.0, -HY + 95.0, 95.0), R(yaw=140.0))
    mark(start, "player_start", "Gameplay")

    # --- Eventos: la habitacion empieza normal y se va torciendo ---
    # 1) Al acercarte por segunda vez a la mesa, el televisor se enciende solo.
    table = out.get("coffee_table")
    if tv:
        t = trigger("event_tv", (table.x if table else -60.0, -10.0, 100.0), (110.0, 150.0, 100.0),
                    required_entries=2, min_game_time=45.0)
        t.add_step(action("TVOn"), tv, 1.2, None, identity, False)
        if lamp:
            t.add_step(action("LampFlicker"), lamp, 1.5, None, identity, False)

    # 2) Junto a la ventana: golpes en la tuberia, la puerta se entreabre y un cuadro se tuerce
    #    (solo si no lo estas mirando).
    w = info["window"]
    t = trigger("event_window", (w["cx"], HY - 75.0, 100.0), (90.0, 70.0, 100.0), min_game_time=20.0)
    t.add_step(action("PlaySound"), door, 0.8, sfx("pipe_knock"), unreal.Transform(location=V(0, -200, 120)), False)
    t.add_step(action("DoorOpen"), door, 4.5, None, identity, True)
    canvas = STATE.get("canvases", {}).get("frame_large", {})
    if canvas.get("mirror"):
        # Alteracion sutil: el cuadro grande aparece en espejo (y algo mas oscuro) si no lo estas mirando.
        t.add_step(action("ToggleVisibility"), canvas["normal"], 6.0, None, identity, True)
        t.add_step(action("ToggleVisibility"), canvas["mirror"], 6.0, None, identity, True)
    frame = out.get("frame_medium")
    if frame:
        tilt = unreal.Transform(location=V(0, 0, 0), rotation=R(roll=0.0, pitch=7.0), scale=V(1, 1, 1))
        t.add_step(action("MoveActor"), frame.actor, 2.0, None, tilt, True)

    # 3) Si sales al pasillo, la lampara se apaga a tu espalda.
    hall = info["hall"]
    t = trigger("event_hall", ((hall["x0"] + hall["x1"]) * 0.5 - 60.0, (hall["y0"] + hall["y1"]) * 0.5, 100.0),
                (70.0, 60.0, 100.0), min_game_time=30.0)
    if lamp:
        t.add_step(action("LampOff"), lamp, 0.6, None, identity, False)
    t.add_step(action("PlaySound"), None, 2.4, sfx("creak_wood_02"), unreal.Transform(location=V(-260, 180, 0)), False)


# --------------------------------------------------------------------------------------
# Informe y punto de entrada
# --------------------------------------------------------------------------------------
def write_report(manifest, res):
    lines = ["# Vigilia - estado de los assets", ""]
    pending, using_fallback = [], []
    lines += ["| Hueco | Fuente en uso | Licencia |", "|---|---|---|"]
    for group in ("slots", "surfaces"):
        for name, spec in manifest[group].items():
            r = res.get(name)
            fab = [s for s in spec["sources"] if s["type"] == "fab"]
            if r:
                src = r.source
                label = src.get("title") or src.get("id")
                origin = "Fab / %s" % src.get("seller") if src["type"] == "fab" else "Poly Haven"
                lines.append("| %s | %s (%s) | %s |" % (name, label, origin, src.get("license", "")))
                if fab and src["type"] != "fab":
                    using_fallback.append((name, fab[0]))
            else:
                lines.append("| %s | **sin asset** | |" % name)
                if fab:
                    pending.append((name, fab[0]))
    lines += ["", "## Pendiente de anadir desde Fab (My Library > Add to Project)", ""]
    for name, src in pending + using_fallback:
        note = "sin asset" if (name, src) in pending else "ahora con respaldo CC0"
        lines.append("- **%s** - %s (%s, %s) - %s - %s" % (name, src["title"], src["seller"], src["license"], src["url"], note))
    if STATE["blockouts"]:
        lines += ["", "## Prototipos geometricos temporales", ""] + ["- %s" % b for b in STATE["blockouts"]]
    if STATE["unverified"]:
        lines += ["", "## Orientacion por revisar (gira el actor y ejecuta Scripts/save_layout.py)", ""]
        lines += ["- %s" % u for u in sorted(set(STATE["unverified"]))]
    if WARNINGS:
        lines += ["", "## Avisos", ""] + ["- %s" % w for w in WARNINGS]
    out_dir = os.path.join(PROJECT_DIR, "Saved", "Vigilia")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "asset_report.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    log("Informe de assets: " + path)
    for line in lines:
        log(line)
    return path


def open_level():
    if eal.does_asset_exist(MAP_PATH):
        level_sub.load_level(MAP_PATH)
    else:
        level_sub.new_level(MAP_PATH)
    for actor in actor_sub.get_all_level_actors():
        if actor and TAG in [str(t) for t in actor.tags]:
            actor_sub.destroy_actor(actor)


def build():
    manifest = load_json("asset_manifest.json")
    STATE["metrics"] = load_json("polyhaven_metrics.json", {}) or {}
    STATE["overrides"] = load_json("layout_overrides.json", {}) or {}
    STATE["unverified"], STATE["blockouts"], STATE["used"] = [], [], {}
    del WARNINGS[:]

    with unreal.ScopedSlowTask(8, "Vigilia: construyendo el salon") as task:
        task.make_dialog(False)
        task.enter_progress_frame(1, "Importando recursos propios")
        photos = import_local_sources()
        task.enter_progress_frame(1, "Resolviendo assets (Fab / Megascans / Poly Haven)")
        res = resolve_all(manifest)
        cap_fab_textures(2048)
        for name, resolved in res.items():
            if resolved and name in manifest["slots"]:
                prepare_meshes(resolved)
        task.enter_progress_frame(1, "Materiales")
        mats = build_materials(res)
        task.enter_progress_frame(1, "Nivel")
        open_level()
        task.enter_progress_frame(1, "Arquitectura")
        info = build_shell(res, mats)
        door = build_door(res, mats, info)
        build_window(res, mats, info)
        task.enter_progress_frame(1, "Mobiliario y decoracion")
        out = furnish(res, mats, info, photos)
        task.enter_progress_frame(1, "Iluminacion, audio y eventos")
        build_lighting(info)
        build_gameplay(out, door, info, mats)
        task.enter_progress_frame(1, "Guardando")
        level_sub.save_current_level()
        eal.save_directory(ROOT, True, True)
    report = write_report(manifest, res)
    log("Salon construido: %s (%d avisos). Pulsa Play para probarlo." % (MAP_PATH, len(WARNINGS)))
    return report
