#!/usr/bin/env python3
"""Genera los recursos procedurales incluidos en el repositorio: textura de ruido para el CRT,
panel de cortina plisado (OBJ) y efectos de sonido sintetizados (provisionales).

Requiere numpy y Pillow. Los resultados ya estan versionados en SourceAssets/; solo hay que
ejecutarlo si se quieren regenerar o ajustar.
"""
import math
import os
import wave

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "SourceAssets", "Generated")
AUDIO = os.path.join(ROOT, "SourceAssets", "Audio")
SR = 44100
rng = np.random.default_rng(1994)


# ------------------------------------------------------------------ textura
def make_noise_texture():
    r = rng.random((512, 512))
    g = rng.random((512, 512))
    # Canal R: grano fino. Canal G: grano con bandas horizontales (lineas de barrido).
    g = 0.55 * g + 0.45 * np.repeat(rng.random((512, 1)), 512, axis=1)
    b = rng.random((512, 512))
    img = (np.dstack([r, g, b]) * 255).astype(np.uint8)
    Image.fromarray(img, "RGB").save(os.path.join(GEN, "T_TVNoise.png"))


# ------------------------------------------------------------------ cortina
def make_curtain(width=105.0, height=238.0, columns=96, rows=24):
    """Panel plisado. Ejes: X ancho, Y fondo, Z alto (cm). Origen en el centro superior (la barra)."""
    verts, uvs, faces = [], [], []
    folds = 7.5
    for j in range(rows + 1):
        t = j / rows                      # 0 arriba, 1 abajo
        z = -height * t
        amp = 2.2 + 3.6 * t               # pliegues mas abiertos hacia el suelo
        spread = 1.0 - 0.10 * (1.0 - t)   # recogida en la barra
        arc = 0.0
        prev = None
        for i in range(columns + 1):
            s = i / columns
            x = (s - 0.5) * width * spread
            phase = s * folds * 2.0 * math.pi
            y = amp * math.sin(phase) + 0.9 * math.sin(phase * 2.3 + 1.7 * t) * t
            if prev is not None:
                arc += math.hypot(x - prev[0], y - prev[1])
            prev = (x, y)
            verts.append((x, y, z))
            uvs.append((arc / 100.0, 1.0 - (height * t) / 100.0))
    row = columns + 1
    for j in range(rows):
        for i in range(columns):
            a = j * row + i + 1
            b, c, d = a + 1, a + row + 1, a + row
            faces.append((a, d, c))
            faces.append((a, c, b))
    with open(os.path.join(GEN, "SM_CurtainPanel.obj"), "w", encoding="ascii") as fh:
        fh.write("# Vigilia - panel de cortina plisado (cm, Z arriba)\no CurtainPanel\n")
        for v in verts:
            fh.write("v %.4f %.4f %.4f\n" % v)
        for uv in uvs:
            fh.write("vt %.5f %.5f\n" % uv)
        for f in faces:
            fh.write("f %d/%d %d/%d %d/%d\n" % (f[0], f[0], f[1], f[1], f[2], f[2]))


# ------------------------------------------------------------------ audio
def write_wav(name, samples, peak=0.85):
    samples = np.asarray(samples, dtype=np.float64)
    top = np.max(np.abs(samples)) or 1.0
    data = (samples / top * peak * 32767.0).astype("<i2")
    with wave.open(os.path.join(AUDIO, name + ".wav"), "wb") as fh:
        fh.setnchannels(1)
        fh.setsampwidth(2)
        fh.setframerate(SR)
        fh.writeframes(data.tobytes())


def noise(n):
    return rng.standard_normal(n)


def lowpass(x, cutoff):
    a = math.exp(-2.0 * math.pi * cutoff / SR)
    out = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1.0 - a) * v + a * acc
        out[i] = acc
    return out


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def bandpass(x, low, high):
    return lowpass(highpass(x, low), high)


def env(n, attack, decay):
    t = np.arange(n) / SR
    return np.minimum(t / max(attack, 1e-5), 1.0) * np.exp(-t / decay)


def seamless(x, fade=0.5):
    """Fundido cruzado de la cola sobre el inicio para que el bucle no tenga corte."""
    f = int(fade * SR)
    ramp = np.linspace(0.0, 1.0, f)
    body = x[:-f].copy()
    body[:f] = body[:f] * ramp + x[-f:] * (1.0 - ramp)
    return body


def tone(freq, n, phase=0.0):
    return np.sin(2.0 * math.pi * freq * np.arange(n) / SR + phase)


def impact(length, low, high, decay, pitch=None):
    n = int(length * SR)
    out = bandpass(noise(n), low, high) * env(n, 0.002, decay)
    if pitch:
        out += 0.8 * tone(pitch, n) * env(n, 0.003, decay * 1.4)
    return out


def creak(length, f0, f1, roughness=0.5):
    """Chirrido de bisagra/madera: diente de sierra con friccion irregular (stick-slip)."""
    n = int(length * SR)
    t = np.arange(n) / SR
    wobble = lowpass(noise(n), 6.0) * 900.0
    freq = np.linspace(f0, f1, n) * (1.0 + 0.06 * np.sin(2 * math.pi * 3.1 * t)) + wobble
    phase = 2.0 * math.pi * np.cumsum(freq) / SR
    saw = 2.0 * ((phase / (2.0 * math.pi)) % 1.0) - 1.0
    gate = np.clip(lowpass(noise(n), 9.0) * 220.0 + 0.55, 0.0, 1.0)
    body = bandpass(saw, 300.0, 4200.0) * gate
    body += roughness * bandpass(noise(n), 900.0, 5000.0) * gate * 0.25
    shape = np.sin(np.pi * np.clip(t / length, 0, 1)) ** 0.6
    return body * shape


def make_audio():
    # Tono de sala: aire + zumbido electrico de 50 Hz casi inaudible.
    n = 24 * SR
    air = lowpass(noise(n), 180.0) * 1.0 + bandpass(noise(n), 200.0, 900.0) * 0.05
    hum = 0.035 * tone(50.0, n) + 0.018 * tone(100.0, n) + 0.006 * tone(150.0, n)
    swell = 1.0 + 0.25 * np.sin(2 * math.pi * np.arange(n) / SR / 11.0)
    write_wav("room_tone_loop", seamless(air / np.max(np.abs(air)) * 0.5 * swell + hum, 2.0), 0.5)

    # Estatica de TV + pitido de linea de 15,6 kHz.
    n = 8 * SR
    static = highpass(noise(n), 400.0) * (0.85 + 0.15 * lowpass(noise(n), 3.0) * 30.0)
    static += 0.04 * tone(15625.0, n) * np.max(np.abs(static))
    write_wav("tv_static_loop", seamless(static, 0.4), 0.6)

    # Encendido de CRT: golpe del rele + desmagnetizado.
    n = int(0.9 * SR)
    t = np.arange(n) / SR
    thunk = impact(0.9, 60.0, 900.0, 0.05, 82.0)
    degauss = 0.5 * tone(100.0, n) * np.exp(-t / 0.22) * (t > 0.03)
    whine = 0.05 * np.sin(2 * math.pi * np.cumsum(np.linspace(3000.0, 15625.0, n)) / SR) * np.minimum(t / 0.5, 1.0)
    write_wav("tv_power", thunk + degauss + whine, 0.8)

    click = impact(0.12, 1200.0, 7000.0, 0.008, 2100.0)
    click[int(0.035 * SR):] += impact(0.12, 900.0, 5000.0, 0.01, 1500.0)[: len(click) - int(0.035 * SR)] * 0.6
    write_wav("switch_click", click, 0.7)

    write_wav("door_open_creak", creak(1.5, 520.0, 760.0), 0.6)
    latch = impact(0.5, 150.0, 2500.0, 0.03, 180.0)
    latch[int(0.06 * SR):] += impact(0.5, 800.0, 6000.0, 0.012, 2400.0)[: len(latch) - int(0.06 * SR)] * 0.5
    write_wav("door_close", latch, 0.75)
    slam = impact(1.2, 40.0, 1400.0, 0.11, 62.0) + 0.5 * impact(1.2, 500.0, 5000.0, 0.03)
    write_wav("door_slam", slam, 0.98)
    rattle = np.zeros(int(0.7 * SR))
    for start in (0.0, 0.11, 0.2, 0.34):
        hit = impact(0.25, 700.0, 6000.0, 0.02, 1300.0)
        i = int(start * SR)
        rattle[i:i + len(hit)] += hit[: len(rattle) - i]
    write_wav("door_locked", rattle, 0.7)

    for index in range(1, 5):
        heel = impact(0.32, 50.0 + 8 * index, 700.0, 0.035, 68.0 + 5 * index)
        toe = impact(0.32, 200.0, 2600.0, 0.02) * 0.45
        step = heel.copy()
        offset = int((0.05 + 0.01 * index) * SR)
        step[offset:] += toe[: len(step) - offset]
        step += creak(0.32, 180.0 + 20 * index, 210.0, 0.2)[: len(step)] * 0.05
        write_wav("footstep_wood_%02d" % index, step, 0.6)

    # Reloj de pared: tic-tac a 1 Hz.
    n = 2 * SR
    tick = np.zeros(n)
    tic = impact(0.2, 1500.0, 7000.0, 0.012, 2600.0)
    tac = impact(0.2, 1100.0, 6000.0, 0.014, 1900.0)
    tick[: len(tic)] += tic
    tick[SR: SR + len(tac)] += tac * 0.85
    write_wav("clock_tick_loop", tick, 0.45)

    write_wav("creak_wood_01", creak(1.1, 240.0, 190.0, 0.3), 0.5)
    write_wav("creak_wood_02", np.concatenate([creak(0.5, 310.0, 260.0, 0.3), np.zeros(int(0.25 * SR)), creak(0.8, 220.0, 170.0, 0.3)]), 0.5)
    write_wav("distant_thump", lowpass(impact(1.6, 30.0, 300.0, 0.16, 48.0), 260.0), 0.7)
    knocks = np.zeros(int(1.6 * SR))
    for start in (0.0, 0.28, 0.62):
        hit = impact(0.6, 200.0, 2200.0, 0.05, 430.0)
        i = int(start * SR)
        knocks[i:i + len(hit)] += hit[: len(knocks) - i]
    write_wav("pipe_knock", lowpass(knocks, 1800.0), 0.6)
    write_wav("object_pickup", impact(0.25, 500.0, 5000.0, 0.02) * 0.6 + creak(0.25, 900.0, 1200.0, 0.4) * 0.1, 0.4)
    write_wav("object_putdown", impact(0.3, 90.0, 1800.0, 0.03, 140.0), 0.5)


def make_horror_audio():
    # Tres golpes secos en una puerta de madera, con la pausa de alguien que espera respuesta.
    knock = np.zeros(int(2.4 * SR))
    for start, gain in ((0.0, 1.0), (0.42, 0.9), (0.84, 1.05)):
        hit = impact(0.5, 90.0, 1600.0, 0.045, 150.0) + 0.35 * impact(0.5, 600.0, 3500.0, 0.015)
        i = int(start * SR)
        knock[i:i + len(hit)] += hit[: len(knock) - i] * gain
    write_wav("door_knock", lowpass(knock, 2400.0), 0.9)

    # Timbre de telefono de los 90 (campanilla electromecanica): 1,5 s sonando, 3 s en silencio.
    n = int(4.5 * SR)
    t = np.arange(n) / SR
    on = (t < 1.5).astype(float)
    hammer = 0.5 + 0.5 * np.sign(np.sin(2 * math.pi * 20.0 * t))
    bell = (np.sin(2 * math.pi * 1150 * t) + 0.7 * np.sin(2 * math.pi * 1385 * t) + 0.25 * np.sin(2 * math.pi * 2780 * t))
    ring = bell * lowpass(hammer, 120.0) * on
    ring *= np.minimum(1.0, (1.5 - t).clip(0) * 40.0)
    write_wav("phone_ring_loop", ring, 0.7)

    # Llamada: linea con ruido, respiracion lenta y un murmullo ininteligible en banda telefonica.
    n = int(11.0 * SR)
    t = np.arange(n) / SR
    line = bandpass(noise(n), 300.0, 3400.0) * 0.06
    breath_env = np.clip(np.sin(2 * math.pi * t / 4.2), 0, None) ** 2
    breathing = bandpass(noise(n), 400.0, 2600.0) * breath_env * 0.5
    pulses = np.zeros(n)
    period = int(SR / 92.0)
    pulses[::period] = 1.0
    syllables = np.clip(lowpass(noise(n), 4.0) * 60.0, 0, 1) * (t > 5.5)
    voice = (bandpass(pulses, 500.0, 900.0) + 0.6 * bandpass(pulses, 1100.0, 1500.0)) * syllables * 8.0
    call = bandpass(line + breathing + voice, 300.0, 3400.0)
    write_wav("phone_voice", call, 0.6)

    # Exhalacion cercana, a la altura de la nuca.
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    env_b = np.sin(np.pi * np.clip(t / 1.6, 0, 1)) ** 1.5
    exhale = bandpass(noise(n), 250.0, 2200.0) * env_b + 0.08 * bandpass(noise(n), 90.0, 300.0) * env_b
    write_wav("breath", exhale, 0.55)

    # Tres campanadas graves del reloj de pie (parciales inarmonicos de campana).
    n = int(7.5 * SR)
    chime = np.zeros(n)
    for k in range(3):
        start = int(k * 2.3 * SR)
        m = n - start
        tt = np.arange(m) / SR
        strike = sum(a * np.sin(2 * math.pi * 330.0 * r * tt) * np.exp(-tt / d)
                     for r, a, d in ((0.5, 0.6, 3.0), (1.0, 1.0, 2.2), (2.0, 0.45, 1.2), (2.76, 0.3, 0.8), (5.4, 0.12, 0.4)))
        chime[start:] += strike * np.minimum(tt / 0.003, 1.0)
    write_wav("clock_chime", chime, 0.8)


if __name__ == "__main__":
    os.makedirs(GEN, exist_ok=True)
    os.makedirs(AUDIO, exist_ok=True)
    make_noise_texture()
    make_curtain()
    make_audio()
    make_horror_audio()
    print("Recursos generados en", GEN, "y", AUDIO)
