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

# nombre: (consulta, duracion minima, duracion maxima)
SOUNDS = {
    "room_tone_loop": ("room tone quiet house night", 20, 120),
    "tv_static_loop": ("tv static noise crt", 6, 60),
    "tv_power": ("crt television turn on", 0.4, 5),
    "switch_click": ("light switch click", 0.1, 1.5),
    "door_open_creak": ("wooden door creak open slow", 1.0, 6),
    "door_close": ("wooden door close latch", 0.3, 3),
    "door_slam": ("door slam interior", 0.4, 3),
    "door_locked": ("locked door handle rattle", 0.5, 3),
    "footstep_wood_01": ("footstep wooden floor single", 0.15, 1.2),
    "footstep_wood_02": ("footstep wooden floor single", 0.15, 1.2),
    "footstep_wood_03": ("footstep wooden floor single", 0.15, 1.2),
    "footstep_wood_04": ("footstep wooden floor single", 0.15, 1.2),
    "clock_tick_loop": ("grandfather clock ticking", 4, 40),
    "clock_chime": ("grandfather clock chime", 3, 25),
    "creak_wood_01": ("wood floor creak", 0.5, 4),
    "creak_wood_02": ("old house creak", 0.5, 5),
    "distant_thump": ("distant thud house", 0.4, 4),
    "pipe_knock": ("water pipe knock", 0.5, 6),
    "object_pickup": ("pick up small object foley", 0.2, 2),
    "object_putdown": ("put down object on wooden table", 0.2, 2),
    "door_knock": ("knocking on wooden door", 1.0, 6),
    "phone_ring_loop": ("old telephone ringing bell", 2, 15),
    "phone_voice": ("breathing on the phone", 4, 25),
    "breath": ("breath exhale close", 0.8, 4),
}

HEADERS = {"User-Agent": "vigilia-sound-fetch/1.0"}


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

    used_ids = {c["id"] for c in choices.values()}
    credits = []
    tmpdir = tempfile.mkdtemp(prefix="vigilia_sfx_")
    names = args.only or list(SOUNDS)
    for name in names:
        query, dmin, dmax = SOUNDS[name]
        chosen = choices.get(name)
        try:
            if chosen and name not in args.reroll:
                sound = api_sound(key, chosen["id"])
            else:
                results = [r for r in api_search(key, query, dmin, dmax)
                           if r["id"] not in used_ids or (chosen and r["id"] == chosen["id"])]
                if chosen and name in args.reroll:
                    results = [r for r in results if r["id"] != chosen["id"]] or results
                if not results:
                    print("[%s] sin resultados CC0 para '%s'; se mantiene el actual" % (name, query))
                    continue
                sound = sorted(results, key=score, reverse=True)[0]
            preview = sound["previews"].get("preview-hq-mp3") or sound["previews"].get("preview-lq-mp3")
            src = os.path.join(tmpdir, "%s.mp3" % name)
            req = urllib.request.Request(preview, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as resp, open(src, "wb") as out:
                out.write(resp.read())
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
        credits.append("- `%s`: [%s](%s) por %s (CC0)" % (name, c["name"], c["url"], c["user"]))
    with open(os.path.join(AUDIO, "CREDITS.md"), "w", encoding="utf-8") as fh:
        fh.write("# Sonidos (Freesound, CC0)\n\nNo exigen atribucion; se lista por cortesia.\n\n" + "\n".join(credits) + "\n")
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("Listo. Ejecuta Scripts/build_room.py en el editor para reimportar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
