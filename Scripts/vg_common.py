"""Utilidades compartidas del pipeline de construccion de Vigilia (se ejecuta dentro del editor de Unreal)."""
import json
import math
import os
import re

import unreal

PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
SCRIPTS_DIR = os.path.join(PROJECT_DIR, "Scripts")
SOURCE_DIR = os.path.join(PROJECT_DIR, "SourceAssets")
ROOT = "/Game/Vigilia"
FAB_ROOTS = ["/Game/Fab", "/Game/Megascans", "/Game/MSPresets"]

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
registry = unreal.AssetRegistryHelpers.get_asset_registry()

WARNINGS = []


def log(msg):
    unreal.log("[Vigilia] " + str(msg))


def warn(msg):
    WARNINGS.append(str(msg))
    unreal.log_warning("[Vigilia] " + str(msg))


def safe_set(obj, prop, value):
    """set_editor_property tolerante: un nombre de propiedad desconocido no aborta la construccion."""
    try:
        obj.set_editor_property(prop, value)
        return True
    except Exception as exc:  # noqa: BLE001
        warn("No se pudo fijar %s.%s: %s" % (type(obj).__name__, prop, exc))
        return False


def load_json(name, default=None):
    path = os.path.join(SCRIPTS_DIR, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def class_name(asset_data):
    try:
        return str(asset_data.asset_class_path.asset_name)
    except Exception:  # noqa: BLE001 - versiones antiguas
        return str(asset_data.asset_class)


def assets_under(path, classes):
    out = []
    if not eal.does_directory_exist(path):
        return out
    for data in registry.get_assets_by_path(path, recursive=True):
        if class_name(data) in classes:
            out.append(data)
    return out


def load(data_or_path):
    if isinstance(data_or_path, str):
        return eal.load_asset(data_or_path)
    return data_or_path.get_asset()


# --------------------------------------------------------------------------------------
# Importacion
# --------------------------------------------------------------------------------------
def import_files(files, destination):
    tasks = []
    for path in files:
        task = unreal.AssetImportTask()
        task.set_editor_property("filename", path)
        task.set_editor_property("destination_path", destination)
        task.set_editor_property("automated", True)
        task.set_editor_property("replace_existing", True)
        task.set_editor_property("save", True)
        tasks.append(task)
    if tasks:
        asset_tools.import_asset_tasks(tasks)
    registry.scan_paths_synchronous([destination], True)


def configure_texture(tex, kind=None, max_size=None):
    changed = False
    if kind == "normal":
        changed |= safe_set(tex, "compression_settings", unreal.TextureCompressionSettings.TC_NORMALMAP)
        changed |= safe_set(tex, "srgb", False)
    elif kind == "masks":
        changed |= safe_set(tex, "compression_settings", unreal.TextureCompressionSettings.TC_MASKS)
        changed |= safe_set(tex, "srgb", False)
    elif kind == "linear":
        changed |= safe_set(tex, "srgb", False)
    if max_size:
        try:
            if max(tex.blueprint_get_size_x(), tex.blueprint_get_size_y()) > max_size and tex.get_editor_property("max_texture_size") != max_size:
                changed |= safe_set(tex, "max_texture_size", max_size)
        except Exception as exc:  # noqa: BLE001
            warn("Textura %s: %s" % (tex.get_name(), exc))
    if changed:
        eal.save_loaded_asset(tex, False)


def texture_kind(tex):
    cs = tex.get_editor_property("compression_settings")
    if cs == unreal.TextureCompressionSettings.TC_NORMALMAP:
        return "normal"
    if cs == unreal.TextureCompressionSettings.TC_MASKS:
        return "masks"
    return "color" if tex.get_editor_property("srgb") else "linear"


def sampler_for(tex):
    cs = tex.get_editor_property("compression_settings")
    srgb = tex.get_editor_property("srgb")
    st = unreal.MaterialSamplerType
    if cs == unreal.TextureCompressionSettings.TC_NORMALMAP:
        return st.SAMPLERTYPE_NORMAL
    if cs == unreal.TextureCompressionSettings.TC_MASKS:
        return st.SAMPLERTYPE_MASKS
    if cs == unreal.TextureCompressionSettings.TC_GRAYSCALE:
        return st.SAMPLERTYPE_GRAYSCALE if srgb else st.SAMPLERTYPE_LINEAR_GRAYSCALE
    if cs == unreal.TextureCompressionSettings.TC_ALPHA:
        return st.SAMPLERTYPE_ALPHA
    return st.SAMPLERTYPE_COLOR if srgb else st.SAMPLERTYPE_LINEAR_COLOR


# --------------------------------------------------------------------------------------
# Resolucion de assets: Fab/Megascans primero, Poly Haven (CC0) como respaldo
# --------------------------------------------------------------------------------------
class Resolved(object):
    def __init__(self, name, spec, source, meshes, textures, materials, folder):
        self.name = name
        self.spec = spec
        self.source = source
        self.meshes = meshes
        self.textures = textures
        self.materials = materials
        self.folder = folder

    @property
    def is_fab(self):
        return self.source["type"] == "fab"

    @property
    def polyhaven_id(self):
        return self.source.get("id") if self.source["type"].startswith("polyhaven") else None


_fab_index = None
_fab_claimed = set()


def _build_fab_index():
    """Agrupa todo lo importado por el plugin de Fab por carpeta, con claves normalizadas para buscar por titulo."""
    global _fab_index
    index = {}
    for root in FAB_ROOTS:
        if not eal.does_directory_exist(root):
            continue
        registry.scan_paths_synchronous([root], True)
        for data in registry.get_assets_by_path(root, recursive=True):
            cls = class_name(data)
            if cls not in ("StaticMesh", "Texture2D", "MaterialInstanceConstant", "Material"):
                continue
            # Se ignoran entradas cuyo paquete ya no existe en disco (borrado a medias o descarga interrumpida).
            if not eal.does_asset_exist(str(data.package_name)):
                continue
            folder = str(data.package_path)
            index.setdefault(folder, []).append(data)
    _fab_index = index
    return index


# Calidades en las que el plugin de Fab importa Megascans, de mas a menos preferida para un juego.
# "Raw" son las texturas de escaneo a 8K: pesan gigas y no aportan nada a la distancia de juego.
FAB_QUALITY_ORDER = ["medium", "high", "low", "raw"]


def _fab_lookup(title):
    index = _fab_index if _fab_index is not None else _build_fab_index()
    key = norm(title)
    best = None
    for folder in index:
        parts = [p for p in folder.split("/") if p]
        for i, seg in enumerate(parts):
            n = norm(seg)
            if n.startswith(key):
                # Raiz del asset: la carpeta cuyo nombre empieza por el titulo (p. ej. Wooden_Table_ukphdffaw).
                root = "/" + "/".join(parts[: i + 1])
                score = len(n) - len(key)
                if root not in _fab_claimed and (best is None or score < best[0]):
                    best = (score, root)
                break
    if not best:
        return None
    root = best[1]

    # Agrupa por calidad (primer nivel bajo la raiz) y se queda con la mejor disponible.
    by_quality = {}
    for folder, items in index.items():
        if folder == root or folder.startswith(root + "/"):
            rest = folder[len(root):].strip("/").split("/")
            quality = rest[0].lower() if rest and rest[0] else ""
            by_quality.setdefault(quality, []).extend(items)
    chosen = None
    for quality in FAB_QUALITY_ORDER:
        if by_quality.get(quality):
            chosen = quality
            break
    if chosen is None:
        datas = [d for items in by_quality.values() for d in items]
    else:
        datas = by_quality[chosen]
        if chosen == "raw":
            warn("'%s' solo esta en calidad Raw (8K, muy pesada). Anadelo de nuevo desde Fab en calidad Medium." % title)
    _fab_claimed.add(root)
    return root, datas


def _polyhaven_folder(kind, category, asset_id):
    if kind == "polyhaven_texture":
        return "%s/Assets/PolyHaven/Surfaces/%s" % (ROOT, asset_id)
    return "%s/Assets/PolyHaven/%s/%s" % (ROOT, category, asset_id)


def _import_polyhaven_model(asset_id, folder):
    if assets_under(folder, ("StaticMesh",)):
        return True
    src = os.path.join(SOURCE_DIR, "PolyHaven", "models", asset_id, asset_id + ".gltf")
    if not os.path.exists(src):
        warn("Falta la descarga de Poly Haven '%s'. Ejecuta: python3 Tools/fetch_polyhaven.py" % asset_id)
        return False
    log("Importando Poly Haven %s" % asset_id)
    import_files([src], folder)
    return bool(assets_under(folder, ("StaticMesh",)))


def _import_polyhaven_texture(asset_id, folder):
    if not assets_under(folder, ("Texture2D",)):
        base = os.path.join(SOURCE_DIR, "PolyHaven", "textures", asset_id)
        if not os.path.isdir(base):
            warn("Falta la textura de Poly Haven '%s'. Ejecuta: python3 Tools/fetch_polyhaven.py" % asset_id)
            return False
        files = [os.path.join(base, f) for f in sorted(os.listdir(base)) if f.lower().endswith((".jpg", ".png"))]
        log("Importando superficie Poly Haven %s" % asset_id)
        import_files(files, folder)
    for data in assets_under(folder, ("Texture2D",)):
        name = str(data.asset_name).lower()
        tex = data.get_asset()
        if "_nor" in name:
            configure_texture(tex, "normal")
        elif name.endswith("_arm"):
            configure_texture(tex, "masks")
    return bool(assets_under(folder, ("Texture2D",)))


def resolve_all(manifest):
    """Devuelve {nombre: Resolved o None} para slots y superficies. Los titulos largos reclaman primero."""
    entries = []
    for group in ("slots", "surfaces"):
        for name, spec in manifest[group].items():
            entries.append((group, name, spec))

    result = {}
    # 1) Fab: de titulo mas largo a mas corto para que "Wooden Table With Drawer" no caiga en "Wooden Table".
    fab_entries = []
    for group, name, spec in entries:
        for src in spec["sources"]:
            if src["type"] == "fab":
                fab_entries.append((len(norm(src["title"])), group, name, spec, src))
    for _len, group, name, spec, src in sorted(fab_entries, key=lambda e: -e[0]):
        if name in result:
            continue
        found = _fab_lookup(src["title"])
        if not found:
            continue
        folder, datas = found
        meshes = [d for d in datas if class_name(d) == "StaticMesh"]
        textures = [d for d in datas if class_name(d) == "Texture2D"]
        materials = [d for d in datas if class_name(d) in ("MaterialInstanceConstant", "Material")]
        if group == "slots" and not meshes:
            continue
        if group == "surfaces" and not textures:
            continue
        result[name] = Resolved(name, spec, src, meshes, textures, materials, folder)

    # 2) Respaldo Poly Haven.
    for group, name, spec in entries:
        if name in result:
            continue
        result[name] = None
        for src in spec["sources"]:
            if src["type"] == "polyhaven":
                folder = _polyhaven_folder(src["type"], spec.get("category", "Misc"), src["id"])
                if _import_polyhaven_model(src["id"], folder):
                    result[name] = Resolved(name, spec, src, assets_under(folder, ("StaticMesh",)),
                                            assets_under(folder, ("Texture2D",)),
                                            assets_under(folder, ("MaterialInstanceConstant", "Material")), folder)
                    break
            elif src["type"] == "polyhaven_texture":
                folder = _polyhaven_folder(src["type"], "", src["id"])
                if _import_polyhaven_texture(src["id"], folder):
                    result[name] = Resolved(name, spec, src, [], assets_under(folder, ("Texture2D",)), [], folder)
                    break
    return result


# --------------------------------------------------------------------------------------
# Preparacion de mallas: colisiones y presupuesto de texturas
# --------------------------------------------------------------------------------------
def prepare_meshes(resolved):
    subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)
    spec = resolved.spec
    mode = spec.get("collision", "box")
    for data in resolved.meshes:
        mesh = data.get_asset()
        try:
            has_simple = subsystem.get_simple_collision_count(mesh) > 0
            if mode == "none":
                continue
            if not has_simple:
                shape = unreal.ScriptingCollisionShapeType.NDOP26 if mode == "ndop" else unreal.ScriptingCollisionShapeType.BOX
                subsystem.add_simple_collisions(mesh, shape)
                eal.save_loaded_asset(mesh, False)
        except Exception as exc:  # noqa: BLE001
            warn("Colision de %s: %s" % (mesh.get_name(), exc))
    for data in resolved.textures:
        configure_texture(data.get_asset(), None, spec.get("max_tex"))


# --------------------------------------------------------------------------------------
# Geometria: cajas envolventes, anclaje y orientacion
# --------------------------------------------------------------------------------------
class MeshGroup(object):
    """Una o varias mallas que comparten sistema de coordenadas y se colocan como un unico objeto."""

    def __init__(self, meshes):
        self.meshes = meshes
        mins = [1e9, 1e9, 1e9]
        maxs = [-1e9, -1e9, -1e9]
        for mesh in meshes:
            box = mesh.get_bounding_box()
            for i, axis in enumerate("xyz"):
                mins[i] = min(mins[i], getattr(box.min, axis))
                maxs[i] = max(maxs[i], getattr(box.max, axis))
        self.min = mins
        self.max = maxs
        self.size = [maxs[i] - mins[i] for i in range(3)]
        self.center = [(maxs[i] + mins[i]) * 0.5 for i in range(3)]

    @property
    def main(self):
        def volume(mesh):
            box = mesh.get_bounding_box()
            return (box.max.x - box.min.x) * (box.max.y - box.min.y) * (box.max.z - box.min.z)
        return max(self.meshes, key=volume)

    def centroid(self, top_fraction=1.0):
        """Centroide de vertices (ponderado por numero de vertices) relativo al centro de la caja, normalizado."""
        total = 0
        acc = [0.0, 0.0]
        for mesh in self.meshes:
            try:
                count = max(int(mesh.get_num_vertices(0)), 1)
                c = unreal.VGStatics.get_mesh_vertex_centroid(mesh, top_fraction)
            except Exception as exc:  # noqa: BLE001
                warn("Centroide de %s: %s" % (mesh.get_name(), exc))
                return None
            acc[0] += c.x * count
            acc[1] += c.y * count
            total += count
        if total == 0:
            return None
        return [(acc[i] / total - self.center[i]) / max(self.size[i], 0.01) for i in range(2)]


def group_for(resolved):
    meshes = [d.get_asset() for d in resolved.meshes]
    if resolved.is_fab and len(meshes) > 1:
        # En Fab varias mallas en una carpeta suelen ser variantes, no piezas: se usa la mas voluminosa.
        return MeshGroup([MeshGroup(meshes).main])
    return MeshGroup(meshes)


def _axis_dir(axis_index, sign):
    return (float(sign), 0.0) if axis_index == 0 else (0.0, float(sign))


def front_direction(resolved, group, metrics):
    """Devuelve (vector frontal local 2D, fiable). Usa metricas glTF, la regla de asiento o el eje largo."""
    rule = resolved.spec.get("front")
    pid = resolved.polyhaven_id
    if pid and metrics and pid in metrics:
        mapping = gltf_mapping(group, metrics[pid])
        if mapping:
            fx = {"+X": (1, 0), "-X": (-1, 0), "+Z": (0, 1), "-Z": (0, -1)}[metrics[pid].get("front", "+Z")]
            return mapping(fx[0], fx[1]), True
    if rule == "seat":
        top = group.centroid(0.2)
        if top:
            axis = 0 if abs(top[0]) > abs(top[1]) else 1
            if abs(top[axis]) > 0.01:
                # El respaldo es la parte alta: el frente mira al lado contrario.
                return _axis_dir(axis, -1 if top[axis] > 0 else 1), True
    # Sin informacion: el frente es perpendicular al eje largo; el sentido queda por verificar.
    axis = 1 if group.size[0] >= group.size[1] else 0
    return _axis_dir(axis, 1), False


def gltf_mapping(group, metric):
    """Deduce como quedaron los ejes glTF (X derecha, Z frente) en la malla importada comparando
    proporciones y la asimetria del centroide. Devuelve f(gx, gz) -> (ux, uy) en ejes locales."""
    cen = group.centroid(1.0)
    if cen is None:
        return None
    width, depth = metric["width_cm"], metric["depth_cm"]
    off_x, off_z = metric["centroid_off"]
    best = None
    for swap in (False, True):
        for sx in (1, -1):
            for sz in (1, -1):
                # sin swap: X_ue = sx * X_gltf, Y_ue = sz * Z_gltf
                ex, ey = (depth, width) if swap else (width, depth)
                cx, cy = (sz * off_z, sx * off_x) if swap else (sx * off_x, sz * off_z)
                err = abs(group.size[0] - ex) / max(ex, 1.0) + abs(group.size[1] - ey) / max(ey, 1.0)
                err += abs(cen[0] - cx) * 4.0 + abs(cen[1] - cy) * 4.0
                if best is None or err < best[0]:
                    best = (err, swap, sx, sz)
    _err, swap, sx, sz = best

    def mapping(gx, gz):
        return (sz * gz, sx * gx) if swap else (sx * gx, sz * gz)
    return mapping


def yaw_of(vec):
    return math.degrees(math.atan2(vec[1], vec[0]))


def rotate2d(x, y, yaw_deg):
    a = math.radians(yaw_deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def rotated_size(group, yaw_deg):
    """Tamano en ejes del mundo (X, Y) de la caja de la malla tras girarla yaw_deg."""
    a = math.radians(yaw_deg)
    c, s = abs(math.cos(a)), abs(math.sin(a))
    return group.size[0] * c + group.size[1] * s, group.size[0] * s + group.size[1] * c
