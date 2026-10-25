"""Synthesizes the background music (a warm kalimba-and-pad loop in C major) and mixes it under the voiceover."""
import json, re, subprocess, wave
import numpy as np

SR = 44100
T = json.loads(re.search(r"const T=(.*);", open("timeline.js").read()).group(1))
total = T["total"]
N = int((total + 1) * SR)
BPM = 100.0
beat = 60.0 / BPM
rng = np.random.default_rng(7)

def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)

def pluck(m, dur, vel=1.0):
    t = np.arange(int(dur * SR)) / SR
    f = hz(m)
    y = (np.sin(2 * np.pi * f * t) * np.exp(-t * 5.5) + 0.35 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 9)
         + 0.12 * np.sin(2 * np.pi * 4.02 * f * t) * np.exp(-t * 16))
    y *= np.minimum(1, t / 0.004)
    return y * vel

def add(buf, start, sig):
    i = int(start * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    buf[i:i + len(sig)] += sig

def pad(m_list, dur):
    t = np.arange(int(dur * SR)) / SR
    y = np.zeros_like(t)
    for m in m_list:
        for det in (-0.12, 0.0, 0.12):
            y += np.sin(2 * np.pi * hz(m) * (1 + det / 100) * t)
    env = np.minimum(1, t / 0.7) * np.minimum(1, (dur - t) / 0.8)
    return y * env / (3 * len(m_list))

CH = [([60, 64, 67], 36), ([55, 59, 62], 31), ([57, 60, 64], 33), ([53, 57, 60], 29)]  # C G Am F (triad, bass root)
bar = 4 * beat
nbars = int(total / bar) + 2
mel = np.zeros(N); bass = np.zeros(N); padb = np.zeros(N); perc = np.zeros(N)
ARP = [0, 1, 2, 1, 2, 1, 2, 0]
HIGH = {0: [76, None, 79, None, 72, None, 76, None], 1: [74, None, 79, None, 71, None, 74, None],
        2: [72, None, 76, None, 69, None, 72, None], 3: [72, None, 77, None, 69, None, 72, 74]}
for b in range(nbars):
    ch, root = CH[b % 4]
    t0 = b * bar
    add(padb, t0, pad([n for n in ch], bar + 0.3))
    for q in range(4):
        add(bass, t0 + q * beat, np.sin(2 * np.pi * hz(root) * np.arange(int(beat * 1.1 * SR)) / SR) * np.exp(-np.arange(int(beat * 1.1 * SR)) / SR * 3) * (0.9 if q % 2 == 0 else 0.55))
    for e in range(8):
        add(mel, t0 + e * beat / 2, pluck(ch[ARP[e]] + (12 if b >= 2 else 0), 1.0, 0.55 if e % 2 else 0.8))
        n = HIGH[b % 4][e]
        if n and b >= 2:
            add(mel, t0 + e * beat / 2, pluck(n, 1.2, 0.5))
    for e in range(8):  # soft shaker on off-beats once the video gets going
        if b >= 1 and e % 2 == 1:
            nz = rng.standard_normal(int(0.07 * SR))
            nz = np.diff(nz, prepend=0)  # crude high-pass
            add(perc, t0 + e * beat / 2, nz * np.exp(-np.arange(len(nz)) / SR * 60) * 0.12)
# a bright resolving flourish under the final line
fin = T["starts"][5]
for k, m in enumerate([72, 76, 79, 84, 88]):
    add(mel, fin + 0.05 + k * 0.11, pluck(m, 2.5, 0.7))
add(padb, fin, pad([60, 64, 67, 72], total - fin + 1))

mix = mel * 0.5 + padb * 0.55 + bass * 0.3 + perc
# a gentle room: short decaying noise impulse response
ir = rng.standard_normal(int(0.9 * SR)) * np.exp(-np.arange(int(0.9 * SR)) / SR * 5)
ir[0] = 0
L = len(mix) + len(ir)
wet = np.fft.irfft(np.fft.rfft(mix, L) * np.fft.rfft(ir, L))[: len(mix)]
mix = mix + 0.12 * wet / (np.abs(wet).max() + 1e-9) * np.abs(mix).max()
mix = mix[: int(total * SR)]
fade = np.ones(len(mix)); n_in, n_out = int(1.2 * SR), int(2.5 * SR)
fade[:n_in] = np.linspace(0, 1, n_in); fade[-n_out:] = np.linspace(1, 0, n_out) ** 1.5
mix = mix * fade
mix = mix / np.abs(mix).max() * 0.8
st = np.stack([mix, np.roll(mix, int(0.012 * SR))], axis=1)  # tiny stereo widening
with wave.open("music.wav", "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes((st * 32767).astype("<i2").tobytes())
subprocess.check_call([
    "ffmpeg", "-y", "-v", "error", "-i", "music.wav", "-i", "voice.wav", "-filter_complex",
    "[0]volume=0.55[m];[1]asplit=2[v][sc];[m][sc]sidechaincompress=threshold=0.015:ratio=7:attack=30:release=500[d];"
    "[d][v]amix=inputs=2:normalize=0,alimiter=limit=0.95[out]", "-map", "[out]", "-ar", "44100", "mix.wav"])
print("ok")
