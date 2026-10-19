# Compose an original, royalty-free instrumental bed (chill pop, F major, 100 BPM).
# usage: python3 video/compose_music.py <seconds> <out.wav>
import sys
import wave

import numpy as np

SR = 48000
BPM = 100
BEAT = 60 / BPM
BAR = 4 * BEAT
rng = np.random.default_rng(7)


def hz(note):
    names = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
    name, octave = note[:-1], int(note[-1])
    return 440.0 * 2 ** ((names[name] + 12 * (octave + 1) - 69) / 12)


# I - iii - vi - IV with extensions: Fmaj9, Am7, Dm9, Bbmaj9
CHORDS = [
    ("F2", ["A3", "C4", "E4", "G4"]),
    ("A2", ["G3", "C4", "E4", "A4"]),
    ("D2", ["F3", "A3", "C4", "E4"]),
    ("Bb1", ["A3", "C4", "D4", "F4"]),
]
MELODY = [  # (beat offset in bar, note) for the top line, played every other bar
    [(3.0, "A4"), (3.5, "C5")],
    [(3.0, "E5"), (3.5, "D5")],
    [(2.5, "C5"), (3.0, "A4"), (3.5, "G4")],
    [(3.0, "F4"), (3.5, "A4")],
]


def lowpass(x, cutoff):
    a = np.exp(-2 * np.pi * cutoff / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i in range(len(x)):  # small buffers only; one-pole filter
        acc = (1 - a) * x[i] + a * acc
        y[i] = acc
    return y


def epiano(f, dur, vel):
    n = int(dur * SR)
    t = np.arange(n) / SR
    mod = np.sin(2 * np.pi * f * 2 * t) * 1.2 * np.exp(-t * 6)  # short FM "tine" at the attack
    tone = (np.sin(2 * np.pi * f * t + mod) + 0.32 * np.sin(2 * np.pi * 2 * f * t)
            + 0.08 * np.sin(2 * np.pi * 3 * f * t))
    env = np.minimum(1, t / 0.004) * np.exp(-t * 2.2) * (1 + 0.04 * np.sin(2 * np.pi * 4.5 * t))
    return tone * env * vel


def pad(freqs, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for f in freqs:
        for detune in (-0.0025, 0.0025):
            ff = f * (1 + detune)
            for k in range(1, 9):
                out += np.sin(2 * np.pi * ff * k * t + rng.uniform(0, 6.28)) / k * (0.8 ** k)
    env = np.minimum(1, t / 0.5) * np.minimum(1, (dur - t) / 0.6).clip(0, 1)
    return lowpass(out * env, 1400) / len(freqs)


def bass(f, dur, vel):
    n = int(dur * SR)
    t = np.arange(n) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.18 * np.sin(2 * np.pi * 2 * f * t)
    env = np.minimum(1, t / 0.008) * np.exp(-t * 2.8) * np.minimum(1, (dur - t) / 0.03).clip(0, 1)
    return tone * env * vel


def kick():
    t = np.arange(int(0.32 * SR)) / SR
    f = 50 + 70 * np.exp(-t * 28)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 11)


def clap():
    t = np.arange(int(0.25 * SR)) / SR
    noise = rng.standard_normal(len(t))
    noise = noise - lowpass(noise, 1200)  # crude high-pass
    bursts = np.exp(-t * 28) + 0.6 * np.exp(-np.maximum(0, t - 0.011) * 30) * (t > 0.011)
    return lowpass(noise, 6500) * bursts * 0.5


def shaker():
    t = np.arange(int(0.06 * SR)) / SR
    noise = rng.standard_normal(len(t))
    noise = noise - lowpass(noise, 5000)
    return noise * np.minimum(1, t / 0.006) * np.exp(-t * 70)


def place(buf, sig, start, gain=1.0, pan=0.0):
    i = int(start * SR)
    if i >= buf.shape[1]:
        return
    j = min(buf.shape[1], i + len(sig))
    left, right = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[0, i:j] += sig[: j - i] * gain * left
    buf[1, i:j] += sig[: j - i] * gain * right


def reverb(x, seconds=1.7, mix=0.22):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((2, n)) * np.exp(-t * 3.6)
    ir[:, : int(0.015 * SR)] = 0  # pre-delay
    ir = np.stack([lowpass(ch, 5000) for ch in ir])
    size = 1 << int(np.ceil(np.log2(x.shape[1] + n)))
    wet = np.stack([np.fft.irfft(np.fft.rfft(x[c], size) * np.fft.rfft(ir[c], size), size)[: x.shape[1]] for c in range(2)])
    wet *= np.max(np.abs(x)) / (np.max(np.abs(wet)) + 1e-9)
    return x * (1 - mix) + wet * mix


def compose(seconds):
    bars = int(np.ceil(seconds / BAR)) + 1
    n = int((bars * BAR + 3) * SR)
    keys, drums, low = (np.zeros((2, n)) for _ in range(3))
    k, c, s = kick(), clap(), shaker()
    for b in range(bars):
        root, voicing = CHORDS[b % 4]
        t0 = b * BAR
        last = b == bars - 1
        full = 2 <= b < bars - 1
        place(keys, pad([hz(v) for v in voicing], BAR + 0.6), t0, 0.16)
        hits = [(0, 0.85, 1.4)] if last else [(0, 0.8, 1.2), (1.5, 0.5, 0.9), (2.5, 0.55, 1.2)]
        for beat, vel, dur in hits:
            jitter = rng.uniform(-0.008, 0.008)
            for idx, v in enumerate(voicing):  # slight strum, low to high
                place(keys, epiano(hz(v), dur + 1.2, vel * rng.uniform(0.9, 1.0)),
                      t0 + beat * BEAT + jitter + idx * 0.006, 0.17, pan=-0.25 + idx * 0.15)
        if b % 2 == 1 and not last:
            for beat, note in MELODY[(b // 2) % 4]:
                place(keys, epiano(hz(note), 1.4, 0.7), t0 + beat * BEAT, 0.2, pan=0.2)
        if full:
            r = hz(root)
            for beat, mult, dur, vel in [(0, 1, 0.9 * BEAT, 0.9), (2, 1, 0.5 * BEAT, 0.7), (3.5, 1.5, 0.4 * BEAT, 0.5)]:
                place(low, bass(r * mult, dur, vel), t0 + beat * BEAT, 0.42)
            for beat in (0, 2):
                place(drums, k, t0 + beat * BEAT, 0.55)
            for beat in (1, 3):
                place(drums, c, t0 + beat * BEAT, 0.16, pan=0.05)
            for e in range(8):
                swing = 0.03 * BEAT if e % 2 else 0
                place(drums, s, t0 + e * BEAT / 2 + swing, 0.07 if e % 2 else 0.045, pan=0.35)
    mix = reverb(keys, 1.8, 0.28) + reverb(drums, 1.0, 0.12) + low
    mix = mix[:, : int((seconds + 0.0) * SR)]
    fade = int(2.5 * SR)
    mix[:, -fade:] *= np.linspace(1, 0, fade) ** 1.5
    mix[:, : int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    mix = np.tanh(mix * 1.1)
    return mix / np.max(np.abs(mix)) * 0.89


def write_wav(path, stereo):
    data = (np.clip(stereo.T, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


if __name__ == "__main__":
    write_wav(sys.argv[2], compose(float(sys.argv[1])))
