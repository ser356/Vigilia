#!/usr/bin/env python3
"""Sustituye los sonidos sintetizados por grabaciones reales CC0 de Freesound (freesound.org).

Requisitos (solo la primera vez):
  1. Crea una cuenta gratuita en https://freesound.org y pide una clave de API en
     https://freesound.org/apiv2/apply  (te la dan al momento).
  2. Ejecuta en macOS:   FREESOUND_API_KEY=tu_clave python3 Tools/fetch_sounds.py

Que hace:
  - Busca cada sonido (consultas y duraciones en SOUNDS), solo licencia CC0, y elige el mejor valorado.
  - Descarga la vista previa de alta calidad, la convierte a WAV mono 44,1 kHz con afconvert (incluido
    en macOS) o ffmpeg, y la guarda en SourceAssets/Audio/<nombre>.wav sustituyendo a la sintetica.
  - Los bucles (*_loop) se suavizan con un fundido cruzado para que no se note el corte.
  - Guarda la eleccion en Scripts/sound_choices.json (reproducible) y los creditos en
    SourceAssets/Audio/CREDITS.md.
  - Para cambiar un sonido: pon el id de Freesound que prefieras en sound_choices.json y vuelve a
    ejecutarlo, o usa --reroll nombre para coger la siguiente opcion.

Despues, en el editor: Scripts/build_room.py (reimporta los WAV que hayan cambiado).
Solo usa la biblioteca estandar de Python.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
import wave
from array import array

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO = os.path.join(ROOT, "SourceAssets", "Audio")
CHOICES = os.path.join(ROOT, "Scripts", "sound_choices.json")
API = "https://freesound.org/apiv2/search/text/"

# nombre: (consultas alternativas, duracion minima, duracion maxima)
# La busqueda de Freesound exige todas las palabras: consultas cortas primero falla menos.
SOUNDS = {
    "room_tone_loop": (["room tone", "interior ambience quiet", "house ambience night"], 15, 180),
    "tv_static_loop": (["tv static", "white noise static"], 6, 60),
    "tv_power": (["crt tv on", "television turn on", "power on button"], 0.4, 5),
    "switch_click": (["light switch", "switch click"], 0.1, 1.5),
    "door_open_creak": (["door creak", "creaky door"], 1.0, 6),
    "door_close": (["door close", "door latch"], 0.3, 3),
    "door_slam": (["door slam"], 0.4, 3),
    "door_locked": (["locked door", "door handle rattle"], 0.5, 3),
    "clock_tick_loop": (["clock ticking", "clock tick"], 4, 40),
    "clock_chime": (["grandfather clock", "clock chime"], 3, 25),
    "creak_wood_01": (["floor creak", "wood creak"], 0.5, 4),
    "creak_wood_02": (["floorboard creak", "wooden floor creak", "creak"], 0.5, 5),
    "distant_thump": (["thud", "thump", "bang"], 0.4, 4),
    "pipe_knock": (["pipe knock", "radiator knock", "pipes", "knock metal"], 0.5, 8),
    # Coger/dejar: sonidos de manipulacion suaves (roce de tela/papel y un toque leve de madera).
    "object_pickup": (["cloth rustle", "fabric movement", "paper handling", "foley handling"], 0.2, 1.5),
    "object_putdown": (["wood tap", "tap on wood", "small object on table", "wood knock light"], 0.1, 1.2),
    "door_knock": (["door knock", "knocking", "knock"], 0.8, 8),
    "phone_ring_loop": (["telephone ring", "phone ring"], 2, 15),
    "phone_voice": (["heavy breathing", "breathing", "whisper"], 4, 30),
    "breath": (["breath", "exhale"], 0.8, 4),
}

# Pasos: una grabacion de alguien andando sobre madera, troceada automaticamente en pisadas sueltas.
FOOTSTEPS = (["footsteps wood", "footsteps wooden floor", "walking wood", "footsteps"], 3, 40)

HEADERS = {"User-Agent": "vigilia-sound-fetch/1.0"}


def search_any(key, queries, dmin, dmax, exclude=()):
    for query in queries:
        results = [r for r in api_search(key, query, dmin, dmax) if r["id"] not in exclude]
        if results:
            return query, results
    return None, []


def api_search(key, query, dmin, dmax, page_size=15):
    params = {
        "query": query,
        "filter": 'license:"Creative Commons 0" duration:[%s TO %s]' % (dmin, dmax),
        "sort": "rating_desc",
        "fields": "id,name,username,license,duration,previews,avg_rating,num_ratings,num_downloads,url",
        "page_size": str(page_size),
    }
    req = urllib.request.Request(API + "?" + urllib.parse.urlencode(params),
                                 headers=dict(HEADERS, Authorization="Token " + key))
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)["results"]


def api_sound(key, sound_id):
    url = "https://freesound.org/apiv2/sounds/%d/?fields=id,name,username,license,duration,previews,url" % sound_id
    req = urllib.request.Request(url, headers=dict(HEADERS, Authorization="Token " + key))
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def score(result):
    # Valoracion media ponderada por cuantos la votaron, y algo de popularidad.
    return (result.get("avg_rating") or 0) * min(result.get("num_ratings") or 0, 20) + 0.002 * (result.get("num_downloads") or 0)


def convert(src, dst):
    if shutil.which("afconvert"):
        cmd = ["afconvert", "-f", "WAVE", "-d", "LEI16@44100", "-c", "1", src, dst]
    elif shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "44100", "-sample_fmt", "s16", dst]
    else:
        raise RuntimeError("Hace falta afconvert (macOS) o ffmpeg para convertir a WAV")
    subprocess.run(cmd, check=True)


def smooth_loop(path, fade_seconds=0.6):
    """Fundido cruzado del final sobre el principio para que el bucle no tenga corte."""
    with wave.open(path, "rb") as fh:
        params = fh.getparams()
        data = array("h", fh.readframes(fh.getnframes()))
    rate = params.framerate
    fade = min(int(fade_seconds * rate), len(data) // 4)
    if fade < 32:
        return
    body = data[:-fade]
    tail = data[-fade:]
    for i in range(fade):
        w = i / float(fade)
        body[i] = int(max(-32768, min(32767, body[i] * w + tail[i] * (1.0 - w))))
    with wave.open(path, "wb") as fh:
        fh.setparams(params)
        fh.writeframes(body.tobytes())


def slice_steps(path, out_paths, step_len=0.38):
    """Detecta pisadas (picos de energia separados >= 0,3 s) y guarda las mas limpias por separado."""
    with wave.open(path, "rb") as fh:
        params = fh.getparams()
        data = array("h", fh.readframes(fh.getnframes()))
    rate = params.framerate
    win = int(0.01 * rate)
    energy = [sum(abs(v) for v in data[i:i + win]) / float(win) for i in range(0, len(data) - win, win)]
    if not energy:
        return 0
    threshold = max(energy) * 0.35
    peaks, last = [], -999
    for i in range(1, len(energy) - 1):
        if energy[i] >= threshold and energy[i] >= energy[i - 1] and energy[i] >= energy[i + 1] and i - last >= 30:
            peaks.append(i)
            last = i
    # Las pisadas mas fuertes suelen ser las mas limpias; se conservan en orden temporal.
    peaks = sorted(sorted(peaks, key=lambda i: energy[i], reverse=True)[:len(out_paths)])
    length = int(step_len * rate)
    for path_out, peak in zip(out_paths, peaks):
        start = max(0, peak * win - int(0.02 * rate))
        chunk = data[start:start + length]
        fade = int(0.06 * rate)
        for j in range(min(fade, len(chunk))):
            chunk[len(chunk) - 1 - j] = int(chunk[len(chunk) - 1 - j] * j / float(fade))
        with wave.open(path_out, "wb") as fh:
            fh.setparams(params)
            fh.writeframes(chunk.tobytes())
        normalize(path_out, 0.8)
    return len(peaks)


def normalize(path, peak=0.85):
    with wave.open(path, "rb") as fh:
        params = fh.getparams()
        data = array("h", fh.readframes(fh.getnframes()))
    top = max((abs(v) for v in data), default=0)
    if top == 0:
        return
    gain = peak * 32767.0 / top
    if 0.9 < gain < 1.1:
        return
    data = array("h", (int(max(-32768, min(32767, v * gain))) for v in data))
    with wave.open(path, "wb") as fh:
        fh.setparams(params)
        fh.writeframes(data.tobytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reroll", nargs="*", default=[], help="nombres de sonidos a sustituir por la siguiente opcion")
    parser.add_argument("--only", nargs="*", default=[], help="procesar solo estos nombres")
    args = parser.parse_args()

    key = os.environ.get("FREESOUND_API_KEY")
    if not key:
        print("Falta FREESOUND_API_KEY. Pide una clave gratis en https://freesound.org/apiv2/apply")
        return 1

    choices = {}
    if os.path.exists(CHOICES):
        with open(CHOICES, encoding="utf-8") as fh:
            choices = json.load(fh)

    used_ids = {c["id"] for k, c in choices.items() if not k.startswith("_")}
    credits = []
    tmpdir = tempfile.mkdtemp(prefix="vigilia_sfx_")
    # Pasos individuales de una version anterior del script: se descartan para trocear una grabacion real.
    for k in ("footstep_wood_01", "footstep_wood_02", "footstep_wood_03", "footstep_wood_04"):
        choices.pop(k, None)
    jobs = dict(SOUNDS)
    jobs["footsteps"] = FOOTSTEPS
    names = args.only or list(jobs)
    for name in names:
        queries, dmin, dmax = jobs[name]
        chosen = choices.get(name)
        try:
            if chosen and name not in args.reroll:
                sound = api_sound(key, chosen["id"])
            else:
                exclude = used_ids - ({chosen["id"]} if chosen else set())
                rejected = set(choices.get("_rechazados", {}).get(name, []))
                if chosen and name in args.reroll:
                    # El descartado no vuelve a salir en futuros --reroll.
                    rejected.add(chosen["id"])
                    choices.setdefault("_rechazados", {})[name] = sorted(rejected)
                exclude = exclude | rejected
                query, results = search_any(key, queries, dmin, dmax, exclude)
                if not results:
                    print("[%s] sin resultados CC0 (%s); se mantiene el actual" % (name, ", ".join(queries)))
                    continue
                sound = sorted(results, key=score, reverse=True)[0]
            preview = sound["previews"].get("preview-hq-mp3") or sound["previews"].get("preview-lq-mp3")
            src = os.path.join(tmpdir, "%s.mp3" % name)
            req = urllib.request.Request(preview, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as resp, open(src, "wb") as out:
                out.write(resp.read())
            if name == "footsteps":
                full = os.path.join(tmpdir, "footsteps.wav")
                convert(src, full)
                outs = [os.path.join(AUDIO, "footstep_wood_%02d.wav" % i) for i in range(1, 4)]
                found = slice_steps(full, outs)
                if found < 3:
                    print("[footsteps] solo %d pisadas detectadas; prueba --reroll footsteps" % found)
            else:
                dst = os.path.join(AUDIO, name + ".wav")
                convert(src, dst)
                normalize(dst)
                if name.endswith("_loop"):
                    smooth_loop(dst)
            used_ids.add(sound["id"])
            choices[name] = {"id": sound["id"], "name": sound["name"], "user": sound["username"],
                             "url": sound["url"], "license": sound["license"]}
            print("[%s] %s - %s (%.1f s)" % (name, sound["name"], sound["username"], sound.get("duration", 0)))
        except Exception as exc:  # noqa: BLE001
            print("[%s] ERROR %s; se mantiene el actual" % (name, exc))

    with open(CHOICES, "w", encoding="utf-8") as fh:
        json.dump(choices, fh, indent=1, ensure_ascii=False, sort_keys=True)
    for name, c in sorted(choices.items()):
        if name.startswith("_"):
            continue
        credits.append("- `%s`: [%s](%s) por %s (CC0)" % (name, c["name"], c["url"], c["user"]))
    with open(os.path.join(AUDIO, "CREDITS.md"), "w", encoding="utf-8") as fh:
        fh.write("# Sonidos (Freesound, CC0)\n\nNo exigen atribucion; se lista por cortesia.\n\n" + "\n".join(credits) + "\n")
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("Listo. Ejecuta Scripts/build_room.py en el editor para reimportar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
