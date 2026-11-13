"""Materiales maestros de Vigilia generados por codigo (sin assets binarios en el repositorio)."""
import unreal

from vg_common import ROOT, asset_tools, eal, mel, safe_set, sampler_for, texture_kind, warn

MAT_DIR = ROOT + "/Materials"
MP = unreal.MaterialProperty


def _expr(mat, cls, x, y):
    return mel.create_material_expression(mat, cls, x, y)


def _connect(a, out_name, b, in_name):
    if not mel.connect_material_expressions(a, out_name, b, in_name):
        warn("Conexion de material fallida: %s.%s -> %s.%s" % (type(a).__name__, out_name, type(b).__name__, in_name))


def _to_prop(a, out_name, prop):
    if not mel.connect_material_property(a, out_name, prop):
        warn("Conexion a propiedad fallida: %s.%s -> %s" % (type(a).__name__, out_name, prop))


def _new_material(name):
    path = "%s/%s" % (MAT_DIR, name)
    if eal.does_asset_exist(path):
        return eal.load_asset(path), False
    mat = asset_tools.create_asset(name, MAT_DIR, unreal.Material, unreal.MaterialFactoryNew())
    return mat, True


def _finish(mat):
    mel.layout_material_expressions(mat)
    mel.recompile_material(mat)
    eal.save_loaded_asset(mat, False)
    return mat


def _scalar(mat, name, value, x, y):
    node = _expr(mat, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", value)
    return node


def _vector(mat, name, color, x, y):
    node = _expr(mat, unreal.MaterialExpressionVectorParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", unreal.LinearColor(*color))
    return node


def _const3(mat, rgb, x, y):
    node = _expr(mat, unreal.MaterialExpressionConstant3Vector, x, y)
    node.set_editor_property("constant", unreal.LinearColor(rgb[0], rgb[1], rgb[2], 1.0))
    return node


def _tex_param(mat, name, texture, x, y):
    node = _expr(mat, unreal.MaterialExpressionTextureSampleParameter2D, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("texture", texture)
    node.set_editor_property("sampler_type", sampler_for(texture))
    return node


def _mul(mat, a, a_out, b, b_out, x, y):
    node = _expr(mat, unreal.MaterialExpressionMultiply, x, y)
    _connect(a, a_out, node, "A")
    _connect(b, b_out, node, "B")
    return node


def _add(mat, a, b, x, y):
    node = _expr(mat, unreal.MaterialExpressionAdd, x, y)
    _connect(a, "", node, "A")
    _connect(b, "", node, "B")
    return node


# Proyecciones: (mascara de ejes, signo de V, tangente mundo, bitangente mundo)
PROJECTIONS = {
    "XY": ((True, True, False), 1.0, (1, 0, 0), (0, 1, 0)),    # suelo y techo
    "XZ": ((True, False, True), -1.0, (1, 0, 0), (0, 0, -1)),  # paredes norte/sur
    "YZ": ((False, True, True), -1.0, (0, 1, 0), (0, 0, -1)),  # paredes este/oeste
}


def surface_master(projection, default_base, default_normal, default_orm):
    """Material PBR con UV proyectadas en espacio de mundo (escala real, continua entre piezas).
    La normal se reconstruye en espacio de mundo para no depender de las tangentes de la malla."""
    mat, created = _new_material("M_Surface_" + projection)
    if not created:
        return mat
    mask_axes, v_sign, tangent, bitangent = PROJECTIONS[projection]
    safe_set(mat, "tangent_space_normal", False)

    wp = _expr(mat, unreal.MaterialExpressionWorldPosition, -1900, 0)
    mask = _expr(mat, unreal.MaterialExpressionComponentMask, -1700, 0)
    mask.set_editor_property("r", mask_axes[0])
    mask.set_editor_property("g", mask_axes[1])
    mask.set_editor_property("b", mask_axes[2])
    mask.set_editor_property("a", False)
    _connect(wp, "", mask, "")

    sign = _expr(mat, unreal.MaterialExpressionConstant2Vector, -1700, 160)
    sign.set_editor_property("r", 1.0)
    sign.set_editor_property("g", v_sign)
    signed = _mul(mat, mask, "", sign, "", -1500, 0)

    tile = _scalar(mat, "TileSize", 200.0, -1500, 200)
    uv = _expr(mat, unreal.MaterialExpressionDivide, -1300, 0)
    _connect(signed, "", uv, "A")
    _connect(tile, "", uv, "B")

    base = _tex_param(mat, "BaseColor", default_base, -1000, -300)
    _connect(uv, "", base, "UVs")
    tint = _vector(mat, "Tint", (1, 1, 1, 1), -1000, -520)
    _to_prop(_mul(mat, base, "RGB", tint, "", -700, -400), "", MP.MP_BASE_COLOR)

    orm = _tex_param(mat, "ORM", default_orm, -1000, 0)
    _connect(uv, "", orm, "UVs")
    rough_scale = _scalar(mat, "RoughnessScale", 1.0, -1000, 220)
    _to_prop(_mul(mat, orm, "G", rough_scale, "", -700, 60), "", MP.MP_ROUGHNESS)
    _to_prop(orm, "R", MP.MP_AMBIENT_OCCLUSION)

    nrm = _tex_param(mat, "Normal", default_normal, -1000, 420)
    _connect(uv, "", nrm, "UVs")
    strength = _scalar(mat, "NormalStrength", 1.0, -1000, 680)
    t_vec = _const3(mat, tangent, -700, 420)
    b_vec = _const3(mat, bitangent, -700, 560)
    n_vec = _expr(mat, unreal.MaterialExpressionVertexNormalWS, -700, 700)
    nx = _mul(mat, _mul(mat, nrm, "R", strength, "", -560, 380), "", t_vec, "", -400, 420)
    ny = _mul(mat, _mul(mat, nrm, "G", strength, "", -560, 520), "", b_vec, "", -400, 560)
    nz = _mul(mat, nrm, "B", n_vec, "", -400, 700)
    world_normal = _expr(mat, unreal.MaterialExpressionNormalize, -100, 560)
    _connect(_add(mat, _add(mat, nx, ny, -250, 480), nz, -180, 600), "", world_normal, "")
    _to_prop(world_normal, "", MP.MP_NORMAL)
    return _finish(mat)


def paint_master():
    mat, created = _new_material("M_Paint")
    if not created:
        return mat
    color = _vector(mat, "Color", (0.78, 0.74, 0.66, 1), -500, 0)
    _to_prop(color, "", MP.MP_BASE_COLOR)
    _to_prop(_scalar(mat, "Roughness", 0.55, -500, 240), "", MP.MP_ROUGHNESS)
    _to_prop(_scalar(mat, "Metallic", 0.0, -500, 360), "", MP.MP_METALLIC)
    return _finish(mat)


def glass_master():
    mat, created = _new_material("M_Glass")
    if not created:
        return mat
    safe_set(mat, "blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
    safe_set(mat, "translucency_lighting_mode", unreal.TranslucencyLightingMode.TLM_SURFACE)
    safe_set(mat, "two_sided", True)
    _to_prop(_vector(mat, "Color", (0.02, 0.025, 0.03, 1), -500, 0), "", MP.MP_BASE_COLOR)
    _to_prop(_scalar(mat, "Roughness", 0.06, -500, 240), "", MP.MP_ROUGHNESS)
    _to_prop(_scalar(mat, "Opacity", 0.16, -500, 360), "", MP.MP_OPACITY)
    return _finish(mat)


def fabric_master(default_base, default_normal, default_orm):
    """Tela de cortina: dos caras, UV de malla y transmision de luz (Two Sided Foliage)."""
    mat, created = _new_material("M_Fabric")
    if not created:
        return mat
    safe_set(mat, "two_sided", True)
    safe_set(mat, "shading_model", unreal.MaterialShadingModel.MSM_TWO_SIDED_FOLIAGE)
    coords = _expr(mat, unreal.MaterialExpressionTextureCoordinate, -1300, 0)
    tiling = _scalar(mat, "Tiling", 1.0, -1300, 160)
    uv = _mul(mat, coords, "", tiling, "", -1100, 0)
    base = _tex_param(mat, "BaseColor", default_base, -900, -200)
    _connect(uv, "", base, "UVs")
    tint = _vector(mat, "Tint", (1, 1, 1, 1), -900, -420)
    colored = _mul(mat, base, "RGB", tint, "", -600, -300)
    _to_prop(colored, "", MP.MP_BASE_COLOR)
    transmission = _scalar(mat, "Transmission", 0.35, -900, 80)
    _to_prop(_mul(mat, colored, "", transmission, "", -350, -120), "", MP.MP_SUBSURFACE_COLOR)
    orm = _tex_param(mat, "ORM", default_orm, -900, 240)
    _connect(uv, "", orm, "UVs")
    _to_prop(orm, "G", MP.MP_ROUGHNESS)
    nrm = _tex_param(mat, "Normal", default_normal, -900, 480)
    _connect(uv, "", nrm, "UVs")
    _to_prop(nrm, "RGB", MP.MP_NORMAL)
    return _finish(mat)


def tv_screen_master(noise_texture, additive):
    """Nieve de CRT. Variante aditiva (plano delante del cristal escaneado) u opaca (sustituye un slot)."""
    mat, created = _new_material("M_TVScreen_Additive" if additive else "M_TVScreen_Opaque")
    if not created:
        return mat
    if additive:
        safe_set(mat, "blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
        safe_set(mat, "shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
        safe_set(mat, "two_sided", True)

    time = _expr(mat, unreal.MaterialExpressionTime, -1900, 200)
    fps = _expr(mat, unreal.MaterialExpressionConstant, -1900, 320)
    fps.set_editor_property("r", 24.0)
    frame = _expr(mat, unreal.MaterialExpressionFloor, -1550, 240)
    _connect(_mul(mat, time, "", fps, "", -1720, 240), "", frame, "")

    def noise_layer(tile, jump, y):
        coords = _expr(mat, unreal.MaterialExpressionTextureCoordinate, -1550, y)
        coords.set_editor_property("u_tiling", tile[0])
        coords.set_editor_property("v_tiling", tile[1])
        step = _expr(mat, unreal.MaterialExpressionConstant2Vector, -1550, y + 120)
        step.set_editor_property("r", jump[0])
        step.set_editor_property("g", jump[1])
        # Salto de UV por fotograma: la nieve cambia a 24 fps en lugar de deslizarse.
        uv = _add(mat, coords, _mul(mat, frame, "", step, "", -1350, y + 100), -1150, y)
        sample = _expr(mat, unreal.MaterialExpressionTextureSample, -950, y)
        sample.set_editor_property("texture", noise_texture)
        sample.set_editor_property("sampler_type", sampler_for(noise_texture))
        _connect(uv, "", sample, "UVs")
        return sample

    a = noise_layer((1.7, 1.3), (0.371, 0.713), -300)
    b = noise_layer((0.9, 2.3), (0.619, 0.257), 500)
    grain = _mul(mat, a, "R", b, "G", -650, 100)
    tint = _vector(mat, "Tint", (0.72, 0.82, 1.0, 1), -650, 320)
    power = _scalar(mat, "Power", 0.0, -650, 540)
    brightness = _scalar(mat, "Brightness", 14.0, -650, 660)
    emissive = _mul(mat, _mul(mat, grain, "", tint, "", -420, 180), "", _mul(mat, power, "", brightness, "", -420, 580), "", -200, 300)
    _to_prop(emissive, "", MP.MP_EMISSIVE_COLOR)
    if not additive:
        _to_prop(_const3(mat, (0.004, 0.005, 0.005), -200, -200), "", MP.MP_BASE_COLOR)
        rough = _expr(mat, unreal.MaterialExpressionConstant, -200, -60)
        rough.set_editor_property("r", 0.12)
        _to_prop(rough, "", MP.MP_ROUGHNESS)
    return _finish(mat)


def photo_master(default_texture):
    mat, created = _new_material("M_Photo")
    if not created:
        return mat
    image = _tex_param(mat, "Image", default_texture, -700, 0)
    tint = _vector(mat, "Tint", (0.82, 0.76, 0.66, 1), -700, 260)
    _to_prop(_mul(mat, image, "RGB", tint, "", -400, 80), "", MP.MP_BASE_COLOR)
    _to_prop(_scalar(mat, "Roughness", 0.32, -700, 460), "", MP.MP_ROUGHNESS)
    return _finish(mat)


def instance(name, parent, textures=None, scalars=None, vectors=None):
    """Crea (o actualiza) una instancia de material."""
    path = "%s/Instances/%s" % (MAT_DIR, name)
    if eal.does_asset_exist(path):
        inst = eal.load_asset(path)
    else:
        inst = asset_tools.create_asset(name, MAT_DIR + "/Instances", unreal.MaterialInstanceConstant,
                                        unreal.MaterialInstanceConstantFactoryNew())
    mel.set_material_instance_parent(inst, parent)
    for key, tex in (textures or {}).items():
        if tex:
            mel.set_material_instance_texture_parameter_value(inst, key, tex)
    for key, value in (scalars or {}).items():
        mel.set_material_instance_scalar_parameter_value(inst, key, float(value))
    for key, value in (vectors or {}).items():
        mel.set_material_instance_vector_parameter_value(inst, key, unreal.LinearColor(*value))
    mel.update_material_instance(inst)
    eal.save_loaded_asset(inst, False)
    return inst


def classify_surface_textures(resolved):
    """Separa las texturas de una superficie en BaseColor / Normal / ORM segun sus ajustes reales."""
    out = {"BaseColor": None, "Normal": None, "ORM": None}
    candidates = {"BaseColor": [], "Normal": [], "ORM": []}
    for data in resolved.textures:
        tex = data.get_asset()
        name = str(data.asset_name).lower()
        kind = texture_kind(tex)
        if kind == "normal":
            candidates["Normal"].append((0, tex))
        elif kind == "masks":
            score = 0 if ("orm" in name or name.endswith("_arm")) else 1
            candidates["ORM"].append((score, tex))
        elif kind == "color":
            score = 0 if any(k in name for k in ("basecolor", "albedo", "diff", "_b", "_d")) else 1
            candidates["BaseColor"].append((score, tex))
    for key, items in candidates.items():
        if items:
            out[key] = sorted(items, key=lambda it: it[0])[0][1]
    return out


def canvas_master(default_texture):
    """Lienzo para marcos vacios. Las UV salen de la posicion local del plano (no de las UV de la malla),
    asi la imagen nunca sale girada ni en espejo. Parametros:
      Image, CropU/CropV (encuadre tipo "cover"), Mirror (1 = imagen en espejo, para eventos),
      Desaturation (0-1, foto vieja), Tint, Darkness (multiplicador)."""
    mat, created = _new_material("M_Canvas")
    if not created:
        return mat
    if hasattr(unreal, "MaterialExpressionLocalPosition"):
        local = _expr(mat, unreal.MaterialExpressionLocalPosition, -1900, 0)
    else:
        world = _expr(mat, unreal.MaterialExpressionWorldPosition, -2100, 0)
        local = _expr(mat, unreal.MaterialExpressionTransformPosition, -1900, 0)
        safe_set(local, "transform_source_type", unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_WORLD)
        safe_set(local, "transform_type", unreal.MaterialPositionTransformSource.TRANSFORMPOSSOURCE_LOCAL)
        _connect(world, "", local, "")
    xy = _expr(mat, unreal.MaterialExpressionComponentMask, -1700, 0)
    xy.set_editor_property("r", True)
    xy.set_editor_property("g", True)
    xy.set_editor_property("b", False)
    xy.set_editor_property("a", False)
    _connect(local, "", xy, "")
    # Plano de 100x100: X local = horizontal (el espectador lo ve hacia su izquierda), Y local = arriba.
    # UV centrada: u = -x/100, v = -y/100  (0 en el centro, V hacia abajo como en las texturas).
    k = _expr(mat, unreal.MaterialExpressionConstant2Vector, -1700, 160)
    k.set_editor_property("r", -0.01)
    k.set_editor_property("g", -0.01)
    centered = _mul(mat, xy, "", k, "", -1500, 0)

    mirror = _scalar(mat, "Mirror", 0.0, -1700, 320)
    flip = _expr(mat, unreal.MaterialExpressionLinearInterpolate, -1500, 300)
    one = _expr(mat, unreal.MaterialExpressionConstant, -1700, 420)
    one.set_editor_property("r", 1.0)
    minus = _expr(mat, unreal.MaterialExpressionConstant, -1700, 500)
    minus.set_editor_property("r", -1.0)
    _connect(one, "", flip, "A")
    _connect(minus, "", flip, "B")
    _connect(mirror, "", flip, "Alpha")
    mirror_vec = _expr(mat, unreal.MaterialExpressionAppendVector, -1350, 300)
    _connect(flip, "", mirror_vec, "A")
    _connect(one, "", mirror_vec, "B")

    crop = _expr(mat, unreal.MaterialExpressionAppendVector, -1350, 460)
    _connect(_scalar(mat, "CropU", 1.0, -1550, 560), "", crop, "A")
    _connect(_scalar(mat, "CropV", 1.0, -1550, 660), "", crop, "B")

    half = _expr(mat, unreal.MaterialExpressionConstant2Vector, -1150, 600)
    half.set_editor_property("r", 0.5)
    half.set_editor_property("g", 0.5)
    uv = _add(mat, _mul(mat, _mul(mat, centered, "", mirror_vec, "", -1200, 100), "", crop, "", -1050, 200), half, -900, 200)

    image = _tex_param(mat, "Image", default_texture, -700, 0)
    _connect(uv, "", image, "UVs")
    desat = _expr(mat, unreal.MaterialExpressionDesaturation, -450, 0)
    _connect(image, "RGB", desat, "Input")
    _connect(_scalar(mat, "Desaturation", 0.55, -700, 260), "", desat, "Fraction")
    tint = _vector(mat, "Tint", (0.86, 0.8, 0.7, 1), -450, 200)
    dark = _scalar(mat, "Darkness", 0.85, -450, 360)
    _to_prop(_mul(mat, _mul(mat, desat, "", tint, "", -250, 100), "", dark, "", -100, 150), "", MP.MP_BASE_COLOR)
    _to_prop(_scalar(mat, "Roughness", 0.55, -450, 480), "", MP.MP_ROUGHNESS)
    return _finish(mat)
