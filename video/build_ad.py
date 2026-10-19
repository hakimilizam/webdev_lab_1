# Build the long voice-led ad: graded clips, cutaways over fade dips, animated ASS text,
# host voice with an original music bed ducked underneath.
# usage: python3 video/build_ad.py <video_A.mp4> <video_B.mp4> <fonts_dir> <work_dir> <out.mp4>
import os
import subprocess
import sys
import wave

import numpy as np
from PIL import ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compose_music  # noqa: E402

SRC = {"A": sys.argv[1], "B": sys.argv[2]}
FONTS, WORK, OUT = sys.argv[3], sys.argv[4], sys.argv[5]
FPS, W, H = 30, 1080, 1920
XFADE_FRAMES = 14  # plain -> print section transition
SR = 48000

PRE = {  # per-source fixes before scaling: video B carries a static "syanatasya" watermark
    "A": "",
    "B": "delogo=x=592:y=1000:w=118:h=44,",
}
GRADE = {  # light denoise, upscale, sharpen, gentle contrast; B is cooler so warm it slightly
    "A": "hqdn3d=1.2:1.2:3:3,scale=1080:1920:flags=lanczos,cas=0.35,eq=contrast=1.04:saturation=1.06",
    "B": "hqdn3d=1.2:1.2:3:3,scale=1080:1920:flags=lanczos,cas=0.35,eq=contrast=1.04:saturation=1.06,"
         "colorbalance=rm=0.02:bm=-0.02",
}

# id, source, start, duration, voice (bool), cutaways [(rel, src, start, dur, crop_wxhxy or None)]
SECTION_PLAIN = [
    ("V1", "B", 50.04, 5.92, True, []),
    ("V2", "B", 6.30, 6.15, True, [(0.0, "B", 4.95, 0.62, None)]),
    ("V3", "B", 61.56, 2.62, True, []),
    ("V4", "B", 17.72, 3.23, True, [(1.08, "B", 43.45, 0.70, None)]),
    ("V5", "B", 22.24, 2.76, True, []),
    ("V6", "B", 26.62, 4.90, True, [(0.0, "B", 42.45, 0.42, (450, 800, 150, 420))]),
    ("M1", "B", 36.00, 5.00, False, []),
    ("M2", "B", 58.60, 2.80, False, []),
]
SECTION_PRINT = [
    ("P1", "A", 3.24, 6.46, True, []),  # voice only for the first 2.06 s
    ("P2", "A", 10.80, 3.50, False, []),
    ("P3", "A", 25.94, 4.31, True, []),
    ("P4", "A", 18.80, 3.50, False, []),
    ("P5", "A", 31.50, 3.50, False, []),
    ("P6", "A", 37.10, 3.50, False, []),
    ("END", "B", 13.00, 4.40, False, []),
]
VOICE_LEN = {"P1": 2.06}  # voice shorter than the clip

SUBS = {  # clip -> [(rel_start, rel_end, text)] from the host's own words
    "V1": [(0.0, 3.14, "Labuh baju akak adalah 35."), (3.14, 5.92, "Akak tinggi 1.70 pun tak senteng.")],
    "V2": [(0.0, 1.56, "Awak nak pakai dengan palazzo boleh,"), (1.56, 2.86, "nak pakai dengan skirt pun cantik."),
           (2.86, 6.15, "Free size dari dada 36 sampai 53.")],
    "V3": [(0.0, 2.62, "Memang cantik, kain dia sejuk, tak panas, terletak lawa.")],
    "V4": [(0.0, 1.40, "I pakai kaler silver."), (1.40, 3.23, "Ada kaler royal blue, ada kaler lavender.")],
    "V5": [(0.0, 2.76, "Okey, ni kita ada kaler maroon dengan kaler mint green.")],
    "V6": [(0.0, 3.18, "Lepas tu kita ada kaler army dengan oren susu,"), (3.18, 4.90, "yang tiga kaler ni tak ada kolar.")],
    "P1": [(0.0, 2.06, "Saiz dari dada 36 sampai 52.")],
    "P3": [(0.0, 1.92, "Putih dia, putih off-white."), (1.92, 4.31, "Yang kain dia sejuk.")],
}
BADGES = {  # clip -> [(rel_start, rel_end, text)]
    "V1": [(2.25, 4.0, "Labuh 35 inci"), (4.0, 5.92, "Model tinggi 170 cm")],
    "V2": [(3.0, 6.15, "Free size · Dada 36–53 inci")],
    "V3": [(0.6, 2.62, "Kain sejuk, tak panas")],
    "M2": [(0.3, 2.8, "Penghantaran ke Singapura")],
    "P1": [(0.25, 2.4, "Versi corak bunga"), (2.4, 6.2, "Free size · Dada 36–52 inci")],
    "P2": [(0.3, 2.9, "Pilihan corak bunga")],
}
COLOURS = {  # sampled from the garments in video B
    "Silver": "#8892AB", "Royal blue": "#0A35A8", "Lavender": "#A38AF0", "Maroon": "#C72E57",
    "Mint green": "#7A9384", "Army": "#4A4F2C", "Oren susu": "#E2A889", "Emerald": "#12704A",
}
PILLS = [  # (clip, rel_start, rel_end, colour) shown as the host names each colour
    ("V4", 0.45, 1.45, "Silver"), ("V4", 1.45, 2.45, "Royal blue"), ("V4", 2.45, 3.23, "Lavender"),
    ("V5", 0.9, 2.0, "Maroon"), ("V5", 2.0, 2.76, "Mint green"),
    ("V6", 1.1, 2.2, "Army"), ("V6", 2.2, 4.9, "Oren susu"),
]


def run(cmd):
    subprocess.run(cmd, check=True)


def frames(sec):
    return int(round(sec * FPS))


# ---------- clips ----------
def render_clip(clip, path):
    cid, src, start, dur, _, cutaways = clip
    n = frames(dur)
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start}", "-t", f"{dur + 0.2}", "-i", SRC[src]]
    graph = [f"[0:v]{PRE[src]}{GRADE[src]},fps={FPS},setpts=PTS-STARTPTS[m0]"]
    for k, (rel, csrc, cstart, cdur, crop) in enumerate(cutaways, start=1):
        args += ["-ss", f"{cstart}", "-t", f"{cdur + 0.2}", "-i", SRC[csrc]]
        crop_f = f"crop={crop[0]}:{crop[1]}:{crop[2]}:{crop[3]}," if crop else ""
        graph.append(f"[{k}:v]{PRE[csrc]}{crop_f}{GRADE[csrc]},fps={FPS},setpts=PTS-STARTPTS+{rel}/TB[c{k}]")
        graph.append(f"[m{k - 1}][c{k}]overlay=eof_action=pass:enable='between(t,{rel},{rel + cdur - 0.001})'[m{k}]")
    last = f"m{len(cutaways)}"
    run(args + ["-filter_complex", ";".join(graph), "-map", f"[{last}]", "-frames:v", str(n),
                "-c:v", "libx264", "-preset", "slow", "-crf", "14", "-pix_fmt", "yuv420p", "-an", path])
    return n


def build_section(clips, name):
    os.makedirs(os.path.join(WORK, "clips"), exist_ok=True)
    listing, starts, total = [], {}, 0
    for clip in clips:
        p = os.path.join(WORK, "clips", f"{clip[0]}.mp4")
        starts[clip[0]] = total
        total += render_clip(clip, p)
        listing.append(f"file '{p}'")
    lst = os.path.join(WORK, f"{name}.txt")
    with open(lst, "w") as f:
        f.write("\n".join(listing) + "\n")
    out = os.path.join(WORK, f"{name}.mp4")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", out])
    return out, starts, total


# ---------- audio ----------
def load_mono(path):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], check=True, capture_output=True).stdout
    return np.frombuffer(raw, "<f4")


def write_wav(path, x, channels):
    data = (np.clip(x.T if channels == 2 else x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def build_voice(timeline, total_sec):
    src_audio = {k: load_mono(v) for k, v in SRC.items()}
    voice = np.zeros(int(total_sec * SR) + SR)
    fade = int(0.012 * SR)
    for cid, src, start, dur, has_voice, _ in SECTION_PLAIN + SECTION_PRINT:
        if not has_voice:
            continue
        length = VOICE_LEN.get(cid, dur)
        seg = src_audio[src][int(start * SR):int((start + length) * SR)].copy()
        seg[:fade] *= np.linspace(0, 1, fade)
        seg[-fade:] *= np.linspace(1, 0, fade)
        i = int(timeline[cid] * SR)
        voice[i:i + len(seg)] += seg
    return voice[: int(total_sec * SR)]


# ---------- ASS ----------
def ass_colour(hex_rgb, alpha=0):
    r, g, b = int(hex_rgb[1:3], 16), int(hex_rgb[3:5], 16), int(hex_rgb[5:7], 16)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def ts(sec):
    sec = max(0.0, sec)
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h)}:{int(m):02d}:{s:05.2f}"


def rrect(w, h, r):
    c = r * 0.5523
    return (f"m {r} 0 l {w - r} 0 b {w - r + c} 0 {w} {r - c} {w} {r} l {w} {h - r} "
            f"b {w} {h - r + c} {w - r + c} {h} {w - r} {h} l {r} {h} b {r - c} {h} 0 {h - r + c} 0 {h - r} "
            f"l 0 {r} b 0 {r - c} {r - c} 0 {r} 0")


def circle(r):
    c = r * 0.5523
    return (f"m {r} 0 b {r + c} 0 {2 * r} {r - c} {2 * r} {r} b {2 * r} {r + c} {r + c} {2 * r} {r} {2 * r} "
            f"b {r - c} {2 * r} 0 {r + c} 0 {r} b 0 {r - c} {r - c} 0 {r} 0")


_font_cache = {}


def text_w(text, font_file, size):
    key = (font_file, size)
    if key not in _font_cache:
        _font_cache[key] = ImageFont.truetype(os.path.join(FONTS, font_file), size)
    return _font_cache[key].getlength(text)


def slide(x, y, dy=24, ms=220):
    return f"\\move({x},{y + dy},{x},{y},0,{ms})"


def build_ass(timeline, total_sec, print_start):
    ev = []

    def add(start, end, layer, text, style="Default"):
        ev.append(f"Dialogue: {layer},{ts(start)},{ts(end)},{style},,0,0,0,,{text}")

    def shape(start, end, layer, x, y, path, colour, alpha, extra=""):
        add(start, end, layer, f"{{\\an5{slide(x, y)}\\fad(160,160)\\bord0\\shad0\\1c{ass_colour(colour)}\\1a&H{alpha:02X}&{extra}\\p1}}{path}{{\\p0}}")

    def badge(start, end, text, y=880):
        size = 44
        w = int(text_w(text, "Poppins_600SemiBold.ttf", size) + 64)
        shape(start, end, 2, 540, y, rrect(w, 84, 42), "#FFFFFF", 0x14)
        add(start, end, 3, f"{{\\an5{slide(540, y)}\\fad(160,160)\\fnPoppins SemiBold\\fs{size}\\bord0\\shad0\\1c{ass_colour('#1B1B1F')}}}{text}")

    # Hook title, 0 - 2.2 s: two lines slide up in turn, accent bar grows from the centre
    add(0.0, 2.2, 4, f"{{\\an5{slide(540, 720, 28, 260)}\\fad(180,180)\\fnPoppins ExtraBold\\fs96\\bord0\\shad3\\4a&H90&}}Blouse labuh")
    add(0.12, 2.2, 4, f"{{\\an5{slide(540, 826, 28, 260)}\\fad(180,180)\\fnPoppins ExtraBold\\fs96\\bord0\\shad3\\4a&H90&\\1c{ass_colour('#FFD9A3')}}}yang tak senteng")
    add(0.25, 2.2, 3, f"{{\\an5\\pos(540,900)\\fad(120,180)\\bord0\\shad0\\1c{ass_colour('#FFD9A3')}\\fscx0\\t(0,320,0.6,\\fscx100)\\p1}}{rrect(220, 10, 5)}{{\\p0}}")

    for cid, items in SUBS.items():
        for a, b, text in items:
            t0 = timeline[cid]
            add(t0 + a + 0.02, t0 + b, 5, f"{{\\fad(90,70)\\move(540,1232,540,1220,0,160)}}{text}", "Sub")
    for cid, items in BADGES.items():
        for a, b, text in items:
            t0 = timeline[cid]
            badge(t0 + a, t0 + b, text)

    # Colour pills: one at a time, a swatch with the host's name for the colour
    for cid, a, b, name in PILLS:
        t0 = timeline[cid] + a
        t1 = timeline[cid] + b
        tw = text_w(name, "Poppins_600SemiBold.ttf", 44)
        w = int(tw + 64 + 56)
        left = 540 - w / 2
        shape(t0, t1, 2, 540, 880, rrect(w, 84, 42), "#111114", 0x40)
        add(t0, t1, 3, f"{{\\an5{slide(int(left + 50), 880)}\\fad(160,160)\\bord3\\3c&HFFFFFF&\\shad0\\1c{ass_colour(COLOURS[name])}\\p1}}{circle(18)}{{\\p0}}")
        add(t0, t1, 3, f"{{\\an4{slide(int(left + 84), 880)}\\fad(160,160)\\fnPoppins SemiBold\\fs44\\bord0\\shad0}}{name}")

    # Summary grid over M1: all eight colours
    g0, g1 = timeline["M1"] + 0.2, timeline["M1"] + 5.0
    shape(g0, g1, 2, 540, 900, rrect(940, 330, 36), "#111114", 0x48)
    add(g0, g1, 3, f"{{\\an5{slide(540, 790)}\\fad(160,160)\\fnPoppins SemiBold\\fs46\\bord0\\shad0}}Pilihan warna plain")
    for i, (name, hexc) in enumerate(COLOURS.items()):
        col, row = i % 4, i // 4
        x, y = 195 + col * 230, 870 + row * 120
        d = 0.15 + i * 0.07
        add(g0 + d, g1, 3, f"{{\\an5{slide(x, y, 16, 200)}\\fad(140,160)\\bord3\\3c&HFFFFFF&\\shad0\\1c{ass_colour(hexc)}\\p1}}{circle(24)}{{\\p0}}")
        add(g0 + d, g1, 3, f"{{\\an5{slide(x, y + 50, 16, 200)}\\fad(140,160)\\fnPoppins Medium\\fs30\\bord0\\shad0}}{name}")

    # End card
    e0 = timeline["END"]
    e1 = total_sec
    add(e0, e1, 1, f"{{\\an7\\pos(0,0)\\fad(260,0)\\bord0\\shad0\\1c&H000000&\\1a&H70&\\p1}}m 0 0 l {W} 0 l {W} {H} l 0 {H}{{\\p0}}")
    add(e0 + 0.15, e1, 4, f"{{\\an5{slide(540, 760, 28, 280)}\\fad(200,0)\\fnPoppins ExtraBold\\fs88\\bord0\\shad0}}Hantar ke Singapura")
    add(e0 + 0.3, e1, 4, f"{{\\an5{slide(540, 850, 20, 260)}\\fad(200,0)\\fnPoppins Medium\\fs42\\bord0\\shad0\\1c{ass_colour('#E6E6EA')}}}Free size · Labuh 35 inci · Kain sejuk")
    pulse = "".join(f"\\t({ms},{ms + 260},\\fscx105\\fscy105)\\t({ms + 260},{ms + 520},\\fscx100\\fscy100)" for ms in (900, 2100, 3300))
    add(e0 + 0.45, e1, 4, f"{{\\an5{slide(540, 1010, 24, 260)}\\fad(200,0)\\bord0\\shad0\\1c{ass_colour('#1877F2')}{pulse}\\p1}}{rrect(700, 124, 62)}{{\\p0}}")
    add(e0 + 0.45, e1, 5, f"{{\\an5{slide(540, 1010, 24, 260)}\\fad(200,0)\\fnPoppins SemiBold\\fs48\\bord0\\shad0{pulse}}}Tanya harga & saiz")
    add(e0 + 0.6, e1, 4, f"{{\\an5{slide(540, 1112, 16, 240)}\\fad(200,0)\\fnPoppins Medium\\fs34\\bord0\\shad0\\1c{ass_colour('#E6E6EA')}}}Tekan “Send Message”")

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Poppins SemiBold,44,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,5,0,0,0,1
Style: Sub,Poppins SemiBold,58,&H00FFFFFF,&H00FFFFFF,&H50000000,&H96000000,0,0,0,0,100,100,0,0,1,3.2,1.5,2,90,90,700,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    path = os.path.join(WORK, "overlay.ass")
    with open(path, "w", encoding="utf-8") as f:
        f.write(header + "\n".join(ev) + "\n")
    return path


def main():
    os.makedirs(WORK, exist_ok=True)
    sec1, starts1, n1 = build_section(SECTION_PLAIN, "sec_plain")
    sec2, starts2, n2 = build_section(SECTION_PRINT, "sec_print")
    offset = n1 - XFADE_FRAMES
    timeline = {k: v / FPS for k, v in starts1.items()}
    timeline.update({k: (offset + v) / FPS for k, v in starts2.items()})
    total_frames = offset + n2
    total = total_frames / FPS

    voice = build_voice(timeline, total)
    write_wav(os.path.join(WORK, "voice.wav"), voice, 1)
    write_wav(os.path.join(WORK, "music.wav"), compose_music.compose(total), 2)
    ass = build_ass(timeline, total, offset / FPS)

    # Voice: clean up and level. Music: duck under the voice, then mix and normalise.
    mix_graph = (
        "[0:a]highpass=f=85,acompressor=threshold=-22dB:ratio=3:attack=8:release=180:makeup=2,"
        "loudnorm=I=-17:TP=-2:LRA=9,aresample=48000,asplit=2[v][key];"
        "[1:a]volume=-7dB[m];"
        "[m][key]sidechaincompress=threshold=0.02:ratio=7:attack=60:release=450:makeup=1[md];"
        "[v]pan=stereo|c0=c0|c1=c0[vs];"
        "[vs][md]amix=inputs=2:normalize=0,alimiter=limit=0.89[a]"
    )
    mixed = os.path.join(WORK, "mix.wav")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", os.path.join(WORK, "voice.wav"),
         "-i", os.path.join(WORK, "music.wav"), "-filter_complex", mix_graph, "-map", "[a]", "-ar", "48000", mixed])

    vgraph = (f"[0:v][1:v]xfade=transition=smoothleft:duration={XFADE_FRAMES / FPS:.4f}:offset={offset / FPS:.4f},"
              f"ass={ass}:fontsdir={FONTS},format=yuv420p[v];"
              "[2:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", sec1, "-i", sec2, "-i", mixed,
         "-filter_complex", vgraph, "-map", "[v]", "-map", "[a]", "-frames:v", str(total_frames),
         "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", OUT])
    print(f"{OUT}  {total:.2f}s")
    for k, v in timeline.items():
        print(f"  {k:4s} starts {v:6.2f}s")


if __name__ == "__main__":
    main()
