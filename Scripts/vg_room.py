"""Constructor procedural de la mansion de Vigilia. Idempotente: borra y regenera solo lo etiquetado como VG."""
import json
import math
import os

import unreal

import vg_materials as vm
from vg_common import (PROJECT_DIR, cap_fab_textures, slim_raw_meshes, ROOT, SOURCE_DIR, WARNINGS, assets_under, configure_texture, eal, front_direction,
                       gltf_mapping, group_for, import_files, load_json, log, prepare_meshes, resolve_all, safe_set,
                       warn, yaw_of)

TAG = "VG"
MAP_PATH = ROOT + "/Maps/L_Mansion"
SFX_DIR = ROOT + "/Audio/SFX"

# Dimensiones interiores (cm): salon de 5,20 x 4,10 m con techo a 2,55 m, tipico de vivienda de los 90.
HX, HY, H, T = 260.0, 205.0, 255.0, 20.0

# Resto del piso (rectangulos exteriores de cada estancia; los tabiques de TW se levantan hacia dentro).
TW = 10.0
CORR_X0, CORR_X1, CORR_Y0, CORR_Y1 = -720.0, 720.0, -355.0, -HY - T   # pasillo de 14 m
HOUSE_BOTTOM = -735.0
MIN_DOOR_W = 88.0   # ancho minimo de hoja: si el modelo es mas estrecho se ensancha
DOOR_LEAF_W = [0.0]  # ancho final de la hoja (lo fija build_shell y lo usan todas las puertas)
JAMB = 6.0   # ancho de las jambas de las puertas

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


def set_bool(obj, name, value):
    """Propiedades bool de C++ (bOn) se exponen en Python sin la b ('on'); se prueban ambas formas."""
    for prop in (name, "b_" + name):
        try:
            obj.set_editor_property(prop, value)
            return True
        except Exception:  # noqa: BLE001
            continue
    warn("No se pudo fijar %s.%s" % (type(obj).__name__, name))
    return False


def no_collision(comp):
    """Quita la colision de verdad. set_collision_enabled() solo no basta: el componente conserva su
    perfil ("BlockAll") y al empezar la partida Unreal vuelve a aplicarlo, con lo que el objeto bloquea
    aunque no se vea (asi la figura oculta del pasillo taponaba el paso). Hay que cambiar el perfil."""
    comp.set_collision_profile_name("NoCollision")
    comp.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    safe_set(comp, "generate_overlap_events", False)


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
        no_collision(comp)
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
            rot = R(yaw=override["yaw"], pitch=override.get("pitch", rot.pitch), roll=override.get("roll", rot.roll))
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
    # Reimporta los WAV nuevos o modificados (p. ej. tras Tools/fetch_sounds.py), comparando un hash.
    import hashlib
    import json as _json
    hash_path = os.path.join(PROJECT_DIR, "Saved", "Vigilia", "audio_hashes.json")
    known = {}
    if os.path.exists(hash_path):
        with open(hash_path, encoding="utf-8") as fh:
            known = _json.load(fh)
    current = {}
    for w in wavs:
        with open(w, "rb") as fh:
            current[os.path.basename(w)] = hashlib.md5(fh.read()).hexdigest()
    missing = [w for w in wavs
               if not eal.does_asset_exist("%s/%s" % (SFX_DIR, os.path.splitext(os.path.basename(w))[0]))
               or known.get(os.path.basename(w)) != current[os.path.basename(w)]]
    if missing:
        log("Importando %d sonidos nuevos o modificados" % len(missing))
        import_files(missing, SFX_DIR)
    os.makedirs(os.path.dirname(hash_path), exist_ok=True)
    with open(hash_path, "w", encoding="utf-8") as fh:
        _json.dump(current, fh, indent=1)
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
    # Paredes: proyeccion automatica por cara (sin cantos estirados). XZ e YZ apuntan al mismo material.
    auto = vm.surface_auto_master(defaults["BaseColor"], defaults["Normal"], defaults["ORM"])
    masters["XZ"] = masters["YZ"] = auto
    mats = {"paint": vm.paint_master(), "glass": vm.glass_master()}
    fabric = vm.fabric_master(defaults["BaseColor"], defaults["Normal"], defaults["ORM"])
    noise = eal.load_asset(ROOT + "/Textures/T_TVNoise")
    mats["tv_add"] = vm.tv_screen_master(noise, True)
    mats["tv_opaque"] = vm.tv_screen_master(noise, False)
    mats["photo_master"] = vm.photo_master(defaults["BaseColor"])
    mats["canvas_master"] = vm.canvas_master(defaults["BaseColor"])
    mats["dust"] = vm.dust_master()

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
    # Resto del piso: azulejos en cocina y bano, papel distinto en el dormitorio.
    mats["tile_wall_XZ"] = surface("tile_wall", "XZ")
    mats["tile_wall_YZ"] = surface("tile_wall", "YZ")
    mats["tile_floor"] = surface("tile_floor", "XY")
    bed_tint = {"Tint": (0.6, 0.6, 0.58, 1)}
    mats["bed_wall_XZ"] = surface("bedroom_wall", "XZ", **bed_tint)
    mats["bed_wall_YZ"] = surface("bedroom_wall", "YZ", **bed_tint)

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
        # Paso libre minimo: con la hoja abierta (grosor + pomo) el jugador necesita ~80 cm.
        door_w = max(door_w, MIN_DOOR_W)
        DOOR_LEAF_W[0] = door_w
    else:
        door_w, door_t, door_h = 82.5, 4.0, 203.0
    door_x0 = 250.0 - 12.0 - door_w
    framed = door_res is not None and door_t >= 11.0
    # Si la puerta no trae marco, el hueco deja sitio para jambas DENTRO del hueco (asi tapan los cantos
    # de la pared, que con la textura proyectada se verian estirados).
    jw = 0.0 if framed else JAMB
    opening = (door_x0 - jw - 1.0, door_x0 + door_w + jw + 1.0, 0.0, door_h + jw + 1.0)
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

    # --- Pasillo: lo construye build_house (piso completo); aqui solo se reservan sus medidas ---
    info["hall"] = dict(x0=CORR_X0 + TW, x1=CORR_X1 - TW, y0=CORR_Y0 + TW, y1=CORR_Y1)

    # --- Rodapie ---
    bh, bt = 8.0, 1.4
    box("base_west", (-HX, -HY, 0), (-HX + bt, HY, bh), mats["trim"], collision=False)
    box("base_east", (HX - bt, -HY, 0), (HX, HY, bh), mats["trim"], collision=False)
    box("base_north", (-HX, HY - bt, 0), (HX, HY, bh), mats["trim"], collision=False)
    box("base_south_a", (-HX, -HY, 0), (opening[0] - 7.0, -HY + bt, bh), mats["trim"], collision=False)
    if opening[1] + 7.0 < HX:
        box("base_south_b", (opening[1] + 7.0, -HY, 0), (HX, -HY + bt, bh), mats["trim"], collision=False)

    # --- Marco de la puerta (si el modelo no trae el suyo) ---
    if not framed:
        jy0, jy1 = -HY - T - 1.5, -HY + 1.5
        o0, o1, o3 = opening[0], opening[1], opening[3]
        box("door_jamb_l", (o0, jy0, 0), (o0 + JAMB, jy1, o3), mats["trim"])
        box("door_jamb_r", (o1 - JAMB, jy0, 0), (o1, jy1, o3), mats["trim"])
        box("door_lintel", (o0, jy0, o3 - JAMB), (o1, jy1, o3), mats["trim"])
    info["door"]["framed"] = framed
    return info


def build_door(res, mats, info):
    d = info["door"]
    door_cls = unreal.VGDoor
    leaf_y = -HY - T * 0.5 if d["framed"] else -HY - 4.0
    # 1 cm sobre el suelo: deja pasar una rendija de luz por debajo.
    door = actor_sub.spawn_actor_from_class(door_cls, V(d["x0"], leaf_y, 1.0), R(yaw=-90.0))
    door_res = res.get("door")
    if door_res:
        door.setup_door_mesh(group_for(door_res).main, DOOR_LEAF_W[0])
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
    # Abre hacia dentro del salon (local -X = +Y del mundo): abierta hacia el pasillo lo taponaba.
    safe_set(door, "preferred_open_sign", 1.0)
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
            no_collision(comp)
            mark(actor, "curtain_" + side, "Room")
    cyl = eal.load_asset("/Engine/BasicShapes/Cylinder")
    rod = actor_sub.spawn_actor_from_object(cyl, V(w["cx"], HY - 9.0, top + 1.5), R(pitch=90.0))
    rod.set_actor_scale3d(V(0.025, 0.025, (w["w"] + 110.0) / 100.0))
    rod.static_mesh_component.set_material(0, mats["brass"])
    no_collision(rod.static_mesh_component)
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
    # Encendida desde el principio: la nieve es la luz principal del salon.
    set_bool(tv, "on", False)
    safe_set(tv, "glow_lumens", 95.0)


def setup_lamp(lamp, prep, lumens=45.0):
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
    # Empieza apagada: la luz principal es la tele (se enciende con el interruptor o por eventos).
    set_bool(lamp, "on", False)


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
        tick = spatial_ambient("clock_tick", V(clock.x, clock.y, 150.0), sfx("clock_tick_loop"), 0.55, 900.0)
        out["clock_tick"] = tick

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
        # Busto de escayola: mira a la sala... y te sigue con la mirada cuando no lo ves.
        p = prep("bust", face_yaw=0.0)
        if p:
            bust = put_on(p, side, dx=-4.0, dy=side.wy * 0.22)
            if bust:
                out["bust"] = bust
                front, _ = front_direction(p.resolved, p.group, STATE["metrics"])
                STATE["bust_face_offset"] = -yaw_of(front)
        else:
            p = prep("vase")
            if p:
                out["vase"] = put_on(p, side, dx=-4.0, dy=side.wy * 0.22)
        p = prep("telephone", face_yaw=0.0)
        if p:
            out["telephone"] = put_on(p, side, dx=4.0, dy=0.0, cls=unreal.VGPhone, folder="Interactables")
            if out["telephone"]:
                safe_set(out["telephone"].actor, "ring_sound", sfx("phone_ring_loop"))
                safe_set(out["telephone"].actor, "answer_sound", sfx("phone_voice"))
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
    no_collision(comp)
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
    safe_set(comp, "intensity", 0.08)
    safe_set(comp, "light_color", unreal.Color(r=168, g=192, b=255, a=255))
    safe_set(comp, "atmosphere_sun_light", True)

    sky = spawn_marked(unreal.SkyLight, "skylight", V(0, 0, 400))
    comp = sky.get_component_by_class(unreal.SkyLightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    safe_set(comp, "real_time_capture", True)
    safe_set(comp, "intensity", 0.04)
    safe_set(comp, "light_color", unreal.Color(r=150, g=170, b=210, a=255))

    # Farola fria en la calle: entra en diagonal por la ventana y dibuja las cortinas en la pared.
    # Fria a proposito: contrasta con la lampara calida del salon (una farola de sodio lo tenia todo naranja).
    street = spawn_marked(unreal.SpotLight, "street_lamp", V(w["cx"] + 210.0, HY + 330.0, win_z + 190.0))
    target = V(w["cx"] - 40.0, HY - 60.0, win_z - 40.0)
    street.set_actor_rotation(ML.find_look_at_rotation(street.get_actor_location(), target), False)
    comp = street.get_component_by_class(unreal.SpotLightComponent)
    comp.set_mobility(unreal.ComponentMobility.MOVABLE)
    safe_set(comp, "intensity_units", unreal.LightUnits.LUMENS)
    safe_set(comp, "intensity", 320.0)
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
    safe_set(comp, "fog_density", 0.006)
    safe_set(comp, "fog_height_falloff", 0.05)
    safe_set(comp, "enable_volumetric_fog", True)
    safe_set(comp, "volumetric_fog_scattering_distribution", 0.6)
    safe_set(comp, "volumetric_fog_extinction_scale", 1.4)

    ppv = spawn_marked(unreal.PostProcessVolume, "post_process", V(0, 0, 100))
    safe_set(ppv, "unbound", True)
    s = ppv.get_editor_property("settings")
    values = {
        # --- Ambiente: penumbra fria, colores apagados, una sola luz calida y debil ---
        # Rango de exposicion estrecho (EV100 -1 a 1): la camara NO "normaliza" la sala; la zona de la
        # lampara se ve iluminada y todo lo demas se queda en sombra. Con la lampara apagada se ve la
        # ventana y siluetas (y la linterna, F).
        "auto_exposure_min_brightness": -1.0,
        "auto_exposure_max_brightness": 1.0,
        "auto_exposure_bias": -0.2,
        "auto_exposure_speed_up": 0.8,
        "auto_exposure_speed_down": 0.5,
        "bloom_intensity": 0.12,
        "vignette_intensity": 0.35,
        "film_grain_intensity": 0.08,
        "scene_fringe_intensity": 0.0,
        # Gradacion contenida: conserva los tonos de los materiales y el detalle en sombra.
        "color_saturation": unreal.Vector4(x=0.82, y=0.82, z=0.82, w=1.0),
        "color_contrast": unreal.Vector4(x=1.03, y=1.03, z=1.03, w=1.0),
        "color_gain": unreal.Vector4(x=0.9, y=1.0, z=0.96, w=1.0),
        "color_saturation_highlights": unreal.Vector4(x=0.7, y=0.7, z=0.7, w=1.0),
        "color_gamma_shadows": unreal.Vector4(x=0.95, y=1.0, z=1.03, w=1.0),
        # Calidad de Lumen por defecto (1). Con 2 el M4 iba a tirones en el editor; subir solo para capturas.
        "lumen_scene_lighting_quality": 1.0,
        "lumen_scene_detail": 1.0,
        "lumen_final_gather_quality": 1.0,
        "lumen_reflection_quality": 1.0,
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


def at(trigger_actor, x, y, z):
    """Offset para PlaySound sin Target: posicion absoluta (x, y, z) relativa al trigger."""
    c = trigger_actor.get_actor_location()
    return unreal.Transform(location=V(x - c.x, y - c.y, z - c.z))


CHARACTER_HINTS = ("zombie", "nurse", "ghost", "woman", "female", "girl", "horror", "monster")
MANNEQUIN_HINTS = ("mannequin", "manny", "quinn")


def find_character():
    """Solo personajes de terror con idle del mismo esqueleto. Devuelve un dict o None."""
    from vg_common import class_name, registry
    try:
        registry.scan_paths_synchronous(["/Game"], True)
        datas = list(registry.get_assets_by_path("/Game", recursive=True))
    except Exception as exc:  # noqa: BLE001
        warn("No se pudo explorar el proyecto en busca de personajes: %s" % exc)
        return None
    # No elegir un maniqui o cualquier personaje ajeno por orden alfabetico.
    meshes = [d for d in datas if class_name(d) == "SkeletalMesh"
              and any(h in (str(d.package_path) + "/" + str(d.asset_name)).lower() for h in CHARACTER_HINTS)
              and not any(h in (str(d.package_path) + "/" + str(d.asset_name)).lower() for h in MANNEQUIN_HINTS)]
    if not meshes:
        return None

    def score(d):
        name = (str(d.package_path) + "/" + str(d.asset_name)).lower()
        if any(h in name for h in CHARACTER_HINTS):
            return 0
        if any(h in name for h in MANNEQUIN_HINTS):
            return 1
        return 2

    best = sorted(meshes, key=lambda d: (score(d), str(d.asset_name)))[0]
    mesh = best.get_asset()
    skeleton = None
    try:
        skeleton = mesh.get_editor_property("skeleton")
    except Exception as exc:  # noqa: BLE001
        warn("Esqueleto de %s: %s" % (best.asset_name, exc))
    skel_path = str(skeleton.get_path_name()) if skeleton else ""

    anims = [d for d in datas if class_name(d) == "AnimSequence"]
    compatible = []
    for d in anims:
        tag = ""
        try:
            tag = str(d.get_tag_value("Skeleton") or "")
        except Exception:  # noqa: BLE001
            tag = ""
        if skel_path and tag.split("'")[-2 if "'" in tag else 0] == skel_path:
            compatible.append(d)
    # Sin coincidencia exacta de esqueleto no se asignan animaciones de otra carpeta.

    def pick(words, avoid=()):
        found = [d for d in compatible if any(w in str(d.asset_name).lower() for w in words)
                 and not any(w in str(d.asset_name).lower() for w in avoid)]
        # Prefiere las que avanzan de frente y los nombres mas cortos (las variantes llevan sufijos).
        found.sort(key=lambda d: (0 if any(w in str(d.asset_name).lower() for w in ("fwd", "forward")) else 1,
                                  len(str(d.asset_name))))
        return found[0].get_asset() if found else None

    sideways = ("back", "left", "right", "strafe", "turn", "start", "stop", "pivot", "lean", "crouch", "attack")
    info = {
        "mesh": mesh,
        "name": str(best.asset_name),
        "idle": pick(("idle",), ("turn", "break", "crouch")),
        "walk": pick(("walk",), sideways),
        "run": pick(("run", "jog", "sprint"), sideways),
        "silhouette": True,
    }
    if not info["idle"]:
        warn("El personaje no tiene idle compatible: se omiten las apariciones para evitar una pose rigida.")
        return None
    log("Personaje para las entidades: %s (idle=%s, andar=%s, correr=%s)" % (
        info["name"], bool(info["idle"]), bool(info["walk"]), bool(info["run"])))
    return info


def spawn_entity(key="entity"):
    """Presencia animada distante; sin estatua ni maniqui de respaldo."""
    mats = STATE.get("mats", {})
    if "paint" not in mats:
        return None
    silhouette = vm.instance("MI_Paint_Entity", mats["paint"], None, {"Roughness": 0.7, "Metallic": 0.0},
                             {"Color": (0.003, 0.003, 0.004, 1)})
    if "character" not in STATE:
        STATE["character"] = find_character()
    character = STATE["character"]
    if not character:
        warn("Sin personaje de terror con idle compatible: solo tension ambiental, sin estatua de respaldo.")
        return None
    actor = actor_sub.spawn_actor_from_class(unreal.VGEntity, V(0.0, 0.0, -1500.0), R())
    if character:
        mesh = character["mesh"]
        scale = 1.0
        try:
            height = mesh.get_bounds().box_extent.z * 2.0
            if height > 1.0 and not 140.0 <= height <= 215.0:
                scale = 175.0 / height
        except Exception as exc:  # noqa: BLE001
            warn("Altura del personaje: %s" % exc)
        # Los personajes de Unreal miran hacia +Y y tienen el origen en los pies.
        actor.setup_skeletal(mesh, character["idle"], character["walk"], character["run"],
                             silhouette if character["silhouette"] else None, V(0, 0, 0), -90.0, scale)
    safe_set(actor, "chase_loop_sound", sfx("tv_static_loop"))
    safe_set(actor, "catch_sound", sfx("door_slam"))
    for name in ("footstep_wood_01", "footstep_wood_02", "footstep_wood_03"):
        actor.add_step_sound(sfx(name))
    for lamp in (STATE.get("house") or {}).get("lamps", {}).values():
        actor.add_linked_lamp(lamp)
    mark(actor, key, "Events")
    return actor


def dress_house(out):
    """Decoracion extra con modelos CC0 de Poly Haven (se descargan solos, sin pasos manuales).
    Todo va pegado a paredes o sobre muebles: el pasillo y los pasos de puerta quedan libres."""
    res = STATE.get("res", {})

    def prep(key, **kw):
        r = res.get(key)
        return Prep(key, r, **kw) if r else None

    def wall(key, room, side, along, **kw):
        p = prep(key, face_yaw=FACE[side], **kw)
        if not p:
            return None
        x, y = against(p, room, side, along)
        return p.spawn(x, y, 0.0, folder="Decor/Dressing")

    def floor(key, x, y, face=None, yaw_extra=0.0):
        p = prep(key, face_yaw=face, yaw_extra=yaw_extra) if face is not None else prep(key, yaw_extra=yaw_extra)
        return p.spawn(x, y, 0.0, folder="Decor/Dressing") if p else None

    def on(key, support, dx=0.0, dy=0.0, require_hit=False, **kw):
        p = prep(key, **kw)
        if not p or not support:
            return None
        return put_on(p, support, dx=dx, dy=dy, folder="Decor/Dressing", require_hit=require_hit)

    def hang(key, room, side, along, center_z):
        p = prep(key, face_yaw=FACE[side])
        if not p:
            return None
        x, y = against(p, room, side, along, gap=0.3)
        return p.spawn(x, y, center_z - p.h * 0.5, folder="Decor/Dressing", movable=True)

    # Salon
    on("d_pillows", out.get("sofa"), dy=-20.0, require_hit=True, long_axis="Y")
    table = out.get("coffee_table")
    if table:
        on("d_cigs", table, dx=-table.wx * 0.25, dy=table.wy * 0.05, yaw_extra=33.0)
        on("d_lighter", table, dx=-table.wx * 0.25, dy=table.wy * 0.05 + 9.0, yaw_extra=-20.0)
    on("d_glasses", out.get("side_table"), dx=-6.0, dy=-8.0, yaw_extra=15.0)
    floor("d_basket", -112.0, -HY + 30.0)

    # Pasillo: solo en las paredes
    hang("d_wallclock", "corridor", "N", -450.0, 170.0)
    hang("d_hallframe", "corridor", "S", -320.0, 158.0)
    hang("d_hallframe2", "corridor", "S", 480.0, 158.0)

    # Cocina
    house_out = STATE.setdefault("house_out", {})
    wall("d_kcabinet", "kitchen", "S", -360.0)
    wall("d_trash", "kitchen", "E", -560.0, yaw_extra=0.0)
    wall("d_kbasket", "kitchen", "S", -640.0)
    floor("d_broom", ROOMS["kitchen"]["x1"] - 40.0, ROOMS["kitchen"]["y1"] - 45.0)
    ktable = house_out.get("kitchen_table")
    if ktable:
        on("d_teaset", ktable, dx=0.0, dy=0.0, long_axis="X")
        on("d_bowl", ktable, dx=ktable.wx * 0.3, dy=-ktable.wy * 0.2)
    kcab = house_out.get("kitchen_cabinet")
    if kcab:
        on("d_bottles", kcab, dx=0.0, dy=kcab.wy * 0.2, long_axis="Y")
    on("d_pot", house_out.get("kitchen_stove"), dx=-8.0, dy=10.0, require_hit=True)

    # Bano
    br = ROOMS["bathroom"]
    floor("d_plunger", br["x0"] + 32.0, br["y1"] - 70.0)
    floor("d_bleach", br["x1"] - 20.0, br["y0"] + 42.0, yaw_extra=25.0)
    floor("d_cleaner", br["x1"] - 36.0, br["y0"] + 30.0, yaw_extra=-40.0)
    floor("d_stool", br["x1"] - 45.0, br["y1"] - 60.0)
    on("d_duck", house_out.get("bathtub"), dx=25.0, dy=0.0, require_hit=True)

    # Dormitorio
    bd = ROOMS["bedroom"]
    floor("d_rocking", bd["x1"] - 160.0, bd["y1"] - 75.0, face=-150.0)   # mirando hacia la cama
    wall("d_suitcase", "bedroom", "W", -560.0)
    bed = house_out.get("bed")
    if bed:
        floor("d_ottoman", bed.x, bed.max_y + 45.0, yaw_extra=0.0)
    night = house_out.get("nightstand")
    if night:
        on("d_alarm", night, dx=0.0, dy=0.0, face_yaw=90.0)


def spawn_dust(mats):
    """Motas de polvo en suspension (se ven donde les da la luz: linterna, tele, ventana)."""
    dust = actor_sub.spawn_actor_from_class(unreal.VGDustMotes, V(0, 0, 120), R())
    dust.setup_dust(eal.load_asset("/Engine/BasicShapes/Cube"), mats["dust"], 380, V(260.0, 260.0, 130.0), 0.4)
    mark(dust, "dust_motes", "Atmosphere")
    return dust


def prep_slot(out, key, **kw):
    r = STATE.get("res", {}).get(key)
    return Prep(key, r, **kw) if r else None


# ======================================================================================
# Ala domestica original: cocina, bano, dormitorio y conexion con la mansion
# ======================================================================================
# Planta (cm, Y negativo = sur). El salon queda al norte del pasillo, con su puerta al pasillo.
#
#            +-------- salon --------+
#  [salida]  |                       |                        [vestibulo]
#  +--+------+-----------------------+------------------------+--+
#  |  |  entrada          pasillo (14 m)              puerta fondo| <- bucle: vuelves a la entrada
#  +--+--+----------+------+-------+------------------------------+
#        |  cocina  | bano |       dormitorio                     |
#        |          |      |                                      |
#        +----------+------+--------------------------------------+
ROOMS = {
    "corridor": dict(x0=CORR_X0, x1=CORR_X1, y0=CORR_Y0, y1=CORR_Y1, walls="wall", floor="floor", reverb=(1.3, 0.55, 0.4)),
    "kitchen": dict(x0=-720.0, x1=-250.0, y0=HOUSE_BOTTOM, y1=CORR_Y0, walls="tile", floor="tile_floor", reverb=(1.0, 0.8, 0.35)),
    "bathroom": dict(x0=-250.0, x1=30.0, y0=-600.0, y1=CORR_Y0, walls="tile", floor="tile_floor", reverb=(1.9, 0.95, 0.5)),
    "bedroom": dict(x0=30.0, x1=720.0, y0=HOUSE_BOTTOM, y1=CORR_Y0, walls="bed", floor="floor", reverb=(0.5, 0.25, 0.25)),
    "vestibule": dict(x0=CORR_X1, x1=CORR_X1 + 150.0, y0=CORR_Y0, y1=CORR_Y1, walls="wall", floor="floor", reverb=(0.6, 0.4, 0.3)),
    "exit": dict(x0=CORR_X0 - 150.0, x1=CORR_X0, y0=CORR_Y0, y1=CORR_Y1, walls="wall", floor="floor", reverb=(0.6, 0.4, 0.3)),
}
DOOR_W = 82.0
DOOR_H = 205.0
CORR_YC = (CORR_Y0 + TW + CORR_Y1) * 0.5     # eje del pasillo (dentro de sus tabiques)
# Puertas: (estancia, lado, centro a lo largo de la pared)
HOUSE_DOORS = {
    "door_kitchen": ("kitchen", "N", -520.0),
    "door_bathroom": ("bathroom", "N", -110.0),
    "door_bedroom": ("bedroom", "N", 230.0),
    "door_end": ("vestibule", "W", CORR_YC),
    "door_front": ("exit", "E", CORR_YC),
}


def wall_mats(mats, kind):
    if kind == "tile":
        return mats["tile_wall_XZ"], mats["tile_wall_YZ"]
    if kind == "bed":
        return mats["bed_wall_XZ"], mats["bed_wall_YZ"]
    return mats["wall_XZ"], mats["wall_YZ"]


def wall_run(key, axis, a0, a1, f0, f1, mat, openings=(), skip=(), base_side=None, trim=None):
    """Tabique a lo largo de 'X' o 'Y' entre a0 y a1, ocupando f0..f1 en el otro eje.
    openings: (o0, o1, z0, z1) huecos; skip: (s0, s1) tramos sin pared (otra pared ya existe ahi).
    base_side: +1/-1 = lado (en el otro eje) donde va el rodapie."""
    cuts = sorted([(o0, o1, z0, z1) for o0, o1, z0, z1 in openings] + [(s0, s1, 0.0, H) for s0, s1 in skip])

    def piece(name, b0, b1, z0, z1):
        if b1 - b0 < 0.5 or z1 - z0 < 0.5:
            return
        if axis == "X":
            box(name, (b0, f0, z0), (b1, f1, z1), mat)
        else:
            box(name, (f0, b0, z0), (f1, b1, z1), mat)
        if base_side and z0 <= 0.0 and trim is not None:
            bt, bh = 1.4, 8.0
            ff = (f1, f1 + bt) if base_side > 0 else (f0 - bt, f0)
            if axis == "X":
                box(name + "_base", (b0, ff[0], 0), (b1, ff[1], bh), trim, collision=False)
            else:
                box(name + "_base", (ff[0], b0, 0), (ff[1], b1, bh), trim, collision=False)

    cursor, index = a0, 0
    for o0, o1, z0, z1 in cuts:
        o0, o1 = max(o0, a0), min(o1, a1)
        if o1 <= o0:
            continue
        piece("%s_%d" % (key, index), cursor, o0, 0.0, H)
        index += 1
        if z0 > 0:
            piece("%s_%d" % (key, index), o0, o1, 0.0, z0)
            index += 1
        if z1 < H:
            piece("%s_%d" % (key, index), o0, o1, z1, H)
            index += 1
        cursor = max(cursor, o1)
    piece("%s_%d" % (key, index), cursor, a1, 0.0, H)


def house_door_frame(name, axis, c0, c1, f0, f1, mats):
    """Marco (jambas + dintel) DENTRO del hueco [c0, c1], atravesando todo el grosor del tabique."""
    jw = JAMB
    top = DOOR_H + 1.0 + jw
    if axis == "X":
        box(name + "_jl", (c0, f0 - 1.5, 0), (c0 + jw, f1 + 1.5, top), mats["trim"])
        box(name + "_jr", (c1 - jw, f0 - 1.5, 0), (c1, f1 + 1.5, top), mats["trim"])
        box(name + "_jt", (c0, f0 - 1.5, DOOR_H + 1.0), (c1, f1 + 1.5, top), mats["trim"])
    else:
        box(name + "_jl", (f0 - 1.5, c0, 0), (f1 + 1.5, c0 + jw, top), mats["trim"])
        box(name + "_jr", (f0 - 1.5, c1 - jw, 0), (f1 + 1.5, c1, top), mats["trim"])
        box(name + "_jt", (f0 - 1.5, c0, DOOR_H + 1.0), (f1 + 1.5, c1, top), mats["trim"])


def spawn_house_door(key, axis, along0, wall_center, res, mats, locked=False, open_sign=0.0):
    """Hoja con bisagra en along0; para paredes a lo largo de X la hoja avanza en +X, en Y en +Y."""
    yaw = -90.0 if axis == "X" else 0.0
    loc = V(along0, wall_center, 1.0) if axis == "X" else V(wall_center, along0, 1.0)
    door = actor_sub.spawn_actor_from_class(unreal.VGDoor, loc, R(yaw=yaw))
    door_res = res.get("door")
    if door_res:
        door.setup_door_mesh(group_for(door_res).main, DOOR_LEAF_W[0])
    else:
        door.setup_door_mesh(eal.load_asset("/Engine/BasicShapes/Cube"))
        mesh = door.get_editor_property("mesh")
        mesh.set_relative_scale3d(V(0.04, DOOR_W / 100.0, DOOR_H / 100.0))
        mesh.set_relative_location(V(0, DOOR_W * 0.5, DOOR_H * 0.5), False, False)
        mesh.set_material(0, mats["blockout"])
    safe_set(door, "open_sound", sfx("door_open_creak"))
    safe_set(door, "close_sound", sfx("door_close"))
    safe_set(door, "slam_sound", sfx("door_slam"))
    safe_set(door, "locked_sound", sfx("door_locked"))
    if locked:
        door.set_locked(True)
    if open_sign:
        safe_set(door, "preferred_open_sign", open_sign)
    mark(door, key, "House/Doors")
    return door


def spatial_ambient(key, loc, sound, volume=0.6, falloff=900.0, folder="Audio"):
    """Fuente de sonido en bucle en un punto, con atenuacion, reverberacion y oclusion por paredes."""
    actor = actor_sub.spawn_actor_from_class(unreal.AmbientSound, loc, R())
    comp = actor.get_component_by_class(unreal.AudioComponent)
    safe_set(comp, "sound", sound)
    safe_set(comp, "volume_multiplier", volume)
    safe_set(comp, "override_attenuation", True)
    try:
        att = comp.get_editor_property("attenuation_overrides")
        for name, value in (("falloff_distance", falloff), ("attenuation_shape_extents", V(40, 0, 0)),
                            ("enable_occlusion", True), ("occlusion_low_pass_filter_frequency", 700.0),
                            ("occlusion_volume_attenuation", 0.35), ("occlusion_interpolation_time", 0.25),
                            ("enable_reverb_send", True)):
            try:
                att.set_editor_property(name, value)
            except Exception as exc:  # noqa: BLE001
                warn("Atenuacion %s.%s: %s" % (key, name, exc))
        comp.set_editor_property("attenuation_overrides", att)
    except Exception as exc:  # noqa: BLE001
        warn("Atenuacion de %s: %s" % (key, exc))
    mark(actor, key, folder)
    return actor


def build_house(res, mats, info, out):
    """Levanta el resto del piso, sus puertas, luces y acustica. Devuelve un dict con todo lo creado."""
    house = {"doors": {}, "lamps": {}, "rooms": ROOMS}
    salon_x0, salon_x1 = -HX - T, HX + T

    # Medidas reales de la puerta (Megascans) si encajan en un tabique normal.
    global DOOR_W, DOOR_H
    if res.get("door"):
        w, _t, h = horizontal_dims(res["door"])
        if 60.0 <= w <= 110.0:
            DOOR_W = max(w, MIN_DOOR_W)
        if DOOR_LEAF_W[0] > 0.0:
            DOOR_W = DOOR_LEAF_W[0]
        # La puerta de Megascans mide ~240 cm de alto: se respeta (antes el limite era 230 y los huecos
        # del pasillo se quedaban en 205, con la hoja metida en la pared por arriba).
        if 180.0 <= h <= H - 8.0:
            DOOR_H = h

    def hole(c):
        return [(c - DOOR_W * 0.5 - JAMB - 1.0, c + DOOR_W * 0.5 + JAMB + 1.0, 0.0, DOOR_H + JAMB + 1.0)]

    # Huecos por estancia y lado. Las puertas de cocina/bano/dormitorio (lado N de su estancia) atraviesan
    # tambien el lado S del pasillo; las del fondo y la entrada, los lados E y W del pasillo.
    openings = {}
    for key, (room, side, center) in HOUSE_DOORS.items():
        openings.setdefault((room, side), []).extend(hole(center))
        if side == "N":
            openings.setdefault(("corridor", "S"), []).extend(hole(center))
        elif key == "door_end":
            openings.setdefault(("corridor", "E"), []).extend(hole(center))
        elif key == "door_front":
            openings.setdefault(("corridor", "W"), []).extend(hole(center))

    for name, r in ROOMS.items():
        xz, yz = wall_mats(mats, r["walls"])
        floor_mat = mats["tile_floor"] if r["floor"] == "tile_floor" else mats["floor"]
        box("%s_floor" % name, (r["x0"], r["y0"], -T), (r["x1"], r["y1"], 0), floor_mat, folder="House")
        box("%s_ceiling" % name, (r["x0"], r["y0"], H), (r["x1"], r["y1"], H + T), mats["ceiling"], folder="House")
        skip_n = [(salon_x0, salon_x1)] if name == "corridor" else []
        wall_run(name + "_N", "X", r["x0"], r["x1"], r["y1"] - TW, r["y1"], xz, openings.get((name, "N"), []), skip_n, -1, mats["trim"])
        wall_run(name + "_S", "X", r["x0"], r["x1"], r["y0"], r["y0"] + TW, xz, openings.get((name, "S"), []), (), +1, mats["trim"])
        wall_run(name + "_W", "Y", r["y0"] + TW, r["y1"] - TW, r["x0"], r["x0"] + TW, yz, openings.get((name, "W"), []), (), +1, mats["trim"])
        wall_run(name + "_E", "Y", r["y0"] + TW, r["y1"] - TW, r["x1"] - TW, r["x1"], yz, openings.get((name, "E"), []), (), -1, mats["trim"])
        # Acustica de la estancia.
        ra = actor_sub.spawn_actor_from_class(unreal.VGRoomAudio, V((r["x0"] + r["x1"]) * 0.5, (r["y0"] + r["y1"]) * 0.5, H * 0.5), R())
        ra.set_box_extent(V((r["x1"] - r["x0"]) * 0.5 - TW, (r["y1"] - r["y0"]) * 0.5 - TW, H * 0.5))
        ra.setup_reverb(*r["reverb"])
        mark(ra, "audio_" + name, "Audio")

    # Puertas.
    for key, (room, side, c) in HOUSE_DOORS.items():
        r = ROOMS[room]
        if side == "N":
            axis, wall_c = "X", r["y1"] - TW * 0.0      # entre el tabique del pasillo y el de la estancia
            f0, f1 = r["y1"] - TW, r["y1"] + TW
        elif side == "W":
            axis, wall_c = "Y", r["x0"]
            f0, f1 = r["x0"] - TW, r["x0"] + TW
        else:
            axis, wall_c = "Y", r["x1"]
            f0, f1 = r["x1"] - TW, r["x1"] + TW
        c0, c1 = c - DOOR_W * 0.5 - JAMB - 1.0, c + DOOR_W * 0.5 + JAMB + 1.0
        house_door_frame("frame_" + key, axis, c0, c1, f0, f1, mats)
        # La del fondo es una puerta cerrada sin mas (antes era el bucle tipo P.T.).
        locked = key in ("door_bathroom", "door_front", "door_end")
        # Todas abren hacia dentro de su estancia, nunca hacia el pasillo (ver signos en VGDoor).
        open_sign = {"door_front": 1.0}.get(key, -1.0)
        house["doors"][key] = spawn_house_door(key, axis, c - DOOR_W * 0.5, wall_c, res, mats, locked, open_sign)
    if res.get("door"):
        STATE["used"]["door"] = res["door"]

    # Bombillas del pasillo (desnudas, colgando del techo).
    bulb_res = res.get("bulb")
    for i, x in enumerate((-470.0, 0.0, 470.0)):
        lamp = actor_sub.spawn_actor_from_class(unreal.VGLamp, V(x, CORR_YC, H - 32.0), R())
        if bulb_res:
            # Girada 180 grados: el casquillo arriba, colgando del cable.
            g = group_for(bulb_res)
            lamp.setup_mesh(g.main, V(-g.center[0], g.center[1], g.min[2]), R(roll=180.0))
        set_bool(lamp, "directly_interactable", False)
        lamp.setup_light(V(0, 0, -4.0), 22.0, 2300.0, 420.0)
        lamp.set_on(False, False)
        if i != 1:
            # Rendimiento: solo la bombilla central proyecta sombras (cada sombra cuesta en la GPU del M4).
            safe_set(lamp.get_editor_property("light"), "cast_shadows", False)
        safe_set(lamp, "switch_sound", sfx("switch_click"))
        mark(lamp, "corridor_bulb_%d" % (i + 1), "House/Lights")
        cord = actor_sub.spawn_actor_from_object(eal.load_asset("/Engine/BasicShapes/Cylinder"), V(x, CORR_YC, H - 14.0), R())
        cord.set_actor_scale3d(V(0.006, 0.006, 0.28))
        cord.static_mesh_component.set_material(0, mats["blockout"])
        no_collision(cord.static_mesh_component)
        mark(cord, None, "House/Lights")
        house["lamps"]["bulb_%d" % (i + 1)] = lamp

    # Fluorescentes apagados al inicio, accionables por el jugador.
    for name, room, on, lumens in (("fluo_kitchen", "kitchen", False, 300.0), ("fluo_bathroom", "bathroom", False, 170.0)):
        r = ROOMS[room]
        cx, cy = (r["x0"] + r["x1"]) * 0.5, (r["y0"] + r["y1"]) * 0.5
        lamp = actor_sub.spawn_actor_from_class(unreal.VGLamp, V(cx, cy, H - 8.0), R())
        fres = res.get("fluorescent")
        if fres:
            g = group_for(fres)
            # Pegado al techo, centrado sobre el origen de la lampara.
            lamp.setup_mesh(g.main, V(-g.center[0], -g.center[1], -g.max[2]), R())
        set_bool(lamp, "directly_interactable", False)
        lamp.setup_light(V(0, 0, -14.0), lumens, 5600.0, 650.0)
        safe_set(lamp.get_editor_property("light"), "cast_shadows", False)
        set_bool(lamp, "on", on)
        mark(lamp, name, "House/Lights")
        house["lamps"][name] = lamp

    # Acustica del salon (moqueta, sofa y cortinas: poca reverberacion).
    sa = actor_sub.spawn_actor_from_class(unreal.VGRoomAudio, V(0, 0, H * 0.5), R())
    sa.set_box_extent(V(HX, HY, H * 0.5))
    sa.setup_reverb(0.7, 0.3, 0.3)
    mark(sa, "audio_salon", "Audio")

    furnish_house(res, house)

    # Sonido de cada estancia: el bano gotea y su fluorescente zumba (apagado a traves de la puerta).
    br = ROOMS["bathroom"]
    bcx, bcy = (br["x0"] + br["x1"]) * 0.5, (br["y0"] + br["y1"]) * 0.5
    spatial_ambient("bath_drip", V(bcx - 40.0, br["y0"] + 40.0, 60.0), sfx("water_drip_loop"), 0.7, 700.0)
    spatial_ambient("bath_hum", V(bcx, bcy, H - 20.0), sfx("fluorescent_hum_loop"), 0.35, 500.0)
    kr = ROOMS["kitchen"]
    spatial_ambient("kitchen_fridge", V(kr["x0"] + 40.0, kr["y1"] - 60.0, 90.0), sfx("fridge_hum_loop"), 0.3, 600.0)
    # El pasillo pasa a ser el "hall" de los eventos existentes.
    info["hall"] = dict(x0=CORR_X0 + TW, x1=CORR_X1 - TW, y0=CORR_Y0 + TW, y1=CORR_Y1)
    return house


def against(prep, room, side, along, gap=2.0):
    """Coordenadas (x, y) para apoyar el objeto contra la pared 'side' de la estancia."""
    r = ROOMS[room]
    if side == "N":
        return along, r["y1"] - TW - gap - prep.wy * 0.5
    if side == "S":
        return along, r["y0"] + TW + gap + prep.wy * 0.5
    if side == "W":
        return r["x0"] + TW + gap + prep.wx * 0.5, along
    return r["x1"] - TW - gap - prep.wx * 0.5, along


FACE = {"N": -90.0, "S": 90.0, "W": 0.0, "E": 180.0}   # yaw para mirar hacia el interior desde cada pared


def furnish_house(res, house):
    house_out = STATE.setdefault("house_out", {})

    def place(slot, key, room, side, along, folder="House/Furniture", face=True, long_axis=None, yaw_extra=0.0):
        r = res.get(slot)
        if not r:
            return None
        p = Prep(key, r, face_yaw=FACE[side] if face and not long_axis else None, long_axis=long_axis, yaw_extra=yaw_extra)
        x, y = against(p, room, side, along)
        placed = p.spawn(x, y, 0.0, folder=folder)
        house_out[key] = placed
        return placed

    # Cocina: mueble y cocina electrica contra la pared oeste, mesa con dos sillas en el centro.
    k = ROOMS["kitchen"]
    place("kitchen_cabinet", "kitchen_cabinet", "kitchen", "W", -470.0)
    place("stove", "kitchen_stove", "kitchen", "W", -590.0)
    table_res = res.get("kitchen_table")
    if table_res:
        tp = Prep("kitchen_table", table_res, long_axis="X")
        tx, ty = (k["x0"] + k["x1"]) * 0.5 + 40.0, (k["y0"] + k["y1"]) * 0.5 - 30.0
        table = tp.spawn(tx, ty, 0.0, folder="House/Furniture")
        house_out["kitchen_table"] = table
        chair_res = res.get("kitchen_chair")
        if chair_res:
            for i, (dy, face) in enumerate(((-table.wy * 0.5 - 30.0, 90.0), (table.wy * 0.5 + 30.0, -90.0))):
                cp = Prep("kitchen_chair_%d" % (i + 1), chair_res, face_yaw=face, yaw_extra=(-9.0 if i else 14.0))
                cp.spawn(tx + (12.0 if i else -15.0), ty + dy, 0.0, folder="House/Furniture")

    # Bano: banera contra la pared sur, toalla tirada en el suelo, espejo.
    place("bathtub", "bathtub", "bathroom", "S", -110.0, long_axis="X")
    b = ROOMS["bathroom"]
    towel_res = res.get("towel")
    if towel_res:
        Prep("towel", towel_res, yaw_extra=37.0).spawn(-40.0, (b["y0"] + b["y1"]) * 0.5 + 25.0, 0.0, folder="House/Furniture")
    mirror_res = res.get("bath_mirror")
    if mirror_res:
        mp = Prep("bath_mirror", mirror_res, face_yaw=180.0)
        mx, my = against(mp, "bathroom", "E", (b["y0"] + b["y1"]) * 0.5, gap=0.3)
        mp.spawn(mx, my, 150.0 - mp.h * 0.5, folder="House/Furniture", movable=True)

    # Dormitorio: cama con el cabecero contra la pared sur, mesilla, armario frente a la cama.
    bed = place("bed", "bed", "bedroom", "S", 330.0, long_axis="Y")
    if bed:
        place("nightstand", "nightstand", "bedroom", "S", bed.max_x + 32.0)
    place("wardrobe", "wardrobe", "bedroom", "E", -560.0)


# --------------------------------------------------------------------------------------
# Informe y punto de entrada
# --------------------------------------------------------------------------------------
def write_report(manifest, res):
    lines = ["# Vigilia - estado de los assets", ""]
    if STATE.get("mansion"):
        lines += ["Mapa: L_Mansion. Ala principal: sotano, planta baja y planta superior; 12 estancias nuevas.",
                  "Arquitectura, ventanas y escalera: geometria procedural con materiales del manifiesto.",
                  "Mobiliario: Fab cuando esta importado; Poly Haven CC0 como respaldo.",
                  "Presencia animada: %s." % ((STATE.get("character") or {}).get("name") or "no disponible; apariciones omitidas"),
                  "Pendiente: revision visual y de rendimiento dentro de Unreal (este informe no certifica el aspecto).", ""]
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


def capture_layout(overrides=None):
    """Lee del nivel abierto los actores VG_* movidos o girados a mano respecto a donde los puso el
    script y los guarda en Scripts/layout_overrides.json. build() lo hace siempre antes de reconstruir,
    asi que los ajustes manuales ya no se pierden."""
    path = os.path.join(PROJECT_DIR, "Scripts", "layout_overrides.json")
    if overrides is None:
        overrides = load_json("layout_overrides.json", {}) or {}
    changed = 0
    for actor in actor_sub.get_all_level_actors():
        if not actor:
            continue
        tags = [str(t) for t in actor.tags]
        key = next((t[7:] for t in tags if t.startswith("VGSlot:")), None)
        auto = next((t[7:] for t in tags if t.startswith("VGAuto:")), None)
        if not key or not auto:
            continue
        ax, ay, az, ayaw = [float(v) for v in auto.split(",")]
        loc = actor.get_actor_location()
        rot = actor.get_actor_rotation()
        moved = abs(loc.x - ax) + abs(loc.y - ay) + abs(loc.z - az) > 0.5
        turned = abs(((rot.yaw - ayaw + 180.0) % 360.0) - 180.0) > 0.5
        if moved or turned or key in overrides:
            entry = {"loc": [round(loc.x, 2), round(loc.y, 2), round(loc.z, 2)], "yaw": round(rot.yaw, 2),
                     "pitch": round(rot.pitch, 2), "roll": round(rot.roll, 2)}
            if overrides.get(key) != entry:
                overrides[key] = entry
                changed += 1
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(overrides, fh, indent=1, sort_keys=True)
    if changed:
        log("%d ajustes manuales guardados en %s" % (changed, path))
    return overrides


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
    # Si el nivel del salon esta abierto, primero se guardan los objetos movidos a mano.
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world and world.get_path_name().startswith(MAP_PATH):
        STATE["overrides"] = capture_layout()
    else:
        STATE["overrides"] = load_json("layout_overrides.json", {}) or {}
    STATE["unverified"], STATE["blockouts"], STATE["used"] = [], [], {}
    STATE.pop("character", None)
    STATE.pop("entity_warned", None)
    DOOR_LEAF_W[0] = 0.0
    STATE["house_out"] = {}
    del WARNINGS[:]

    import vg_mansion
    import vg_mansion_layout
    import importlib
    importlib.reload(vg_mansion_layout)
    importlib.reload(vg_mansion)
    with unreal.ScopedSlowTask(8, "Vigilia: construyendo la mansion") as task:
        task.make_dialog(False)
        task.enter_progress_frame(1, "Importando recursos propios")
        photos = import_local_sources()
        task.enter_progress_frame(1, "Resolviendo assets (Fab / Megascans / Poly Haven)")
        res = resolve_all(manifest)
        STATE["res"] = res
        # Solo las texturas de los assets de Fab que se usan: cargar todo /Game/Fab (Raw a 8K) disparaba la memoria.
        cap_fab_textures(2048, [d for r in res.values() if r and r.is_fab for d in r.textures])
        slim_raw_meshes([r for r in res.values() if r and r.is_fab])
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
        STATE["house"] = build_house(res, mats, info, None)
        task.enter_progress_frame(1, "Mobiliario y decoracion")
        out = furnish(res, mats, info, photos)
        task.enter_progress_frame(1, "Iluminacion, audio y eventos")
        build_lighting(info)
        STATE["mats"] = mats
        STATE["salon_door_x"] = info["door"]["x0"] + info["door"]["w"] * 0.5
        dress_house(out)
        import sys
        vg_mansion.build(sys.modules[__name__], res, mats, photos)
        vg_mansion.gameplay(sys.modules[__name__], out, door, info, mats)
        spawn_dust(mats)
        task.enter_progress_frame(1, "Guardando")
        level_sub.save_current_level()
        eal.save_directory(ROOT, True, True)
    # Libera lo cargado durante la construccion (texturas fuente de 8K, mallas Raw...).
    unreal.SystemLibrary.collect_garbage()
    report = write_report(manifest, res)
    log("Mansion construida: %s (%d avisos). Pulsa Play para probarlo." % (MAP_PATH, len(WARNINGS)))
    return report
