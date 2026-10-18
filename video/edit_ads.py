# Build 9:16 ad drafts from the two source videos with ffmpeg.
# usage: python3 video/edit_ads.py <source_A.mp4> <source_B.mp4> <out_dir>
import os
import subprocess
import sys

SRC_A, SRC_B, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, FPS = 1080, 1920, 30
# Reels UI covers roughly the top 14% and bottom 35%; keep text between.
CAPTION_Y = 1030
# Static "syanatasya" watermark in video B, in source (720x1280) pixels.
DELOGO_B = "delogo=x=592:y=1000:w=118:h=44"
AUDIO_FADE = 0.06  # short fade at each cut so chopped speech does not click

PLAIN_MONTAGE = [  # (src, start, dur): plain colours from video B, all clear of the fade dips
    ("B", 20.0, 1.4), ("B", 24.0, 1.4), ("B", 29.8, 1.4), ("B", 36.5, 1.4), ("B", 59.0, 1.4),
]
PRINT_MONTAGE = [  # printed versions from video A
    ("A", 19.0, 1.4), ("A", 24.5, 1.4), ("A", 33.0, 1.4), ("A", 37.2, 1.4),
]
END = "Hantar ke Singapura"
END_SUB = "Tanya harga & saiz\ndi Messenger"

VARIANTS = {
    "draf1_15s": [
        ("B", 4.3, 1.6, "Cari blouse labuh\nyang longgar?"),
        ("B", 42.4, 0.9, "Potongan longgar,\nlengan lebar"),
        ("B", 43.4, 1.5, "Tengok tekstur kain"),
        ("A", 1.0, 1.5, "Ada corak bunga juga"),
        *[(s, t, d, "Banyak pilihan warna") for s, t, d in PLAIN_MONTAGE],
        ("B", 13.6, 2.2, "__END__"),
    ],
    "draf2_23s": [
        ("B", 0.0, 1.6, "Blouse labuh untuk\nkerja & jalan-jalan"),
        ("B", 4.3, 1.6, "Labuh, tutup punggung"),
        ("B", 42.4, 0.9, "Potongan longgar"),
        ("B", 43.4, 1.5, "Kain bertekstur"),
        *[(s, t, d, "Pilihan warna plain") for s, t, d in PLAIN_MONTAGE],
        *[(s, t, d, "Pilihan corak bunga") for s, t, d in PRINT_MONTAGE],
        ("A", 5.0, 1.6, "Plain atau corak?"),
        ("B", 46.2, 2.8, "__END__"),
    ],
    # Long cut: whole takes kept, live-selling pace. Every clip avoids the fade dips.
    "draf3_71s": [
        ("B", 4.3, 1.8, "Cari blouse labuh\nyang longgar?"),
        ("B", 7.2, 5.0, "Potongan longgar,\nlabuh tutup punggung"),
        ("B", 13.0, 5.0, "Lengan getah\ndi pergelangan"),
        ("B", 41.5, 3.5, "Tengok tekstur kain"),
        ("B", 19.6, 6.6, "Pilihan warna plain"),
        ("B", 27.2, 5.0, "Pilihan warna plain"),
        ("B", 36.0, 5.4, "Pilihan warna plain"),
        ("B", 58.5, 5.5, "Boleh hantar\nke Singapura"),
        ("A", 0.0, 2.5, "Ada versi corak bunga"),
        ("A", 3.4, 4.5, "Ada versi corak bunga"),
        ("A", 10.8, 4.5, "Pilihan corak bunga"),
        ("A", 18.8, 4.0, "Pilihan corak bunga"),
        ("A", 23.8, 5.0, "Pilihan corak bunga"),
        ("A", 31.5, 4.4, "Pilihan corak bunga"),
        ("A", 37.1, 3.7, "Plain atau corak?"),
        ("B", 46.0, 5.0, "__END__"),
    ],
}
# Variants that also get a copy with the host's original voice.
VOICE_VARIANTS = {"draf3_71s"}


def text_file(name, text):
    path = os.path.join(OUT, "txt", name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def drawtext(name, text, size, y, box_alpha=0.55):
    # One drawtext per line so each line is centred on its own.
    parts = []
    for j, line in enumerate(text.split("\n")):
        path = text_file(f"{name}_{j}.txt", line)
        parts.append(f"drawtext=fontfile={FONT}:textfile={path}:fontsize={size}:fontcolor=white"
                     f":x=(w-text_w)/2:y={y + int(j * size * 1.3)}"
                     f":box=1:boxcolor=black@{box_alpha}:boxborderw=20")
    return ",".join(parts)


def build(name, segments, voice=False):
    inputs, chains, pads = [], [], []
    total = 0.0
    for i, (src, start, dur, caption) in enumerate(segments):
        inputs += ["-ss", f"{start}", "-t", f"{dur}", "-i", SRC_A if src == "A" else SRC_B]
        f = f"[{i}:v]" + (DELOGO_B + "," if src == "B" else "")
        f += (f"scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1,"
              f"setpts=PTS-STARTPTS")
        if caption == "__END__":
            f += (f",drawbox=x=0:y=860:w=iw:h=390:color=black@0.55:t=fill,"
                  + drawtext(f"{name}_{i}_a", END, 84, 905, 0) + ","
                  + drawtext(f"{name}_{i}_b", END_SUB, 62, 1040, 0))
        else:
            f += "," + drawtext(f"{name}_{i}", caption, 72, CAPTION_Y)
        chains.append(f + f"[v{i}]")
        pads.append(f"[v{i}]")
        if voice:
            chains.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,asetpts=PTS-STARTPTS,"
                          f"afade=t=in:d={AUDIO_FADE},afade=t=out:st={dur - AUDIO_FADE:.2f}:d={AUDIO_FADE}[a{i}]")
            pads.append(f"[a{i}]")
        total += dur
    n = len(segments)
    if voice:
        # The two sources differ in loudness, so normalise the joined track.
        graph = (";".join(chains) + ";" + "".join(pads) + f"concat=n={n}:v=1:a=1[v][ac];"
                 "[ac]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=44100[a]")
        extra, amap, suffix = [], "[a]", "_suara"
    else:
        graph = ";".join(chains) + ";" + "".join(pads) + f"concat=n={n}:v=1:a=0[v]"
        extra = ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        amap, suffix = f"{n}:a", "_senyap"
    out = os.path.join(OUT, f"{name}{suffix}.mp4")
    cmd = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + inputs + extra
           + ["-filter_complex", graph, "-map", "[v]", "-map", amap,
              "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out])
    subprocess.run(cmd, check=True)
    print(f"{out}  segments={n}  planned={total:.1f}s")


os.makedirs(os.path.join(OUT, "txt"), exist_ok=True)
for name, segs in VARIANTS.items():
    build(name, segs)
    if name in VOICE_VARIANTS:
        build(name, segs, voice=True)
