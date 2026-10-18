# Build two 9:16 ad drafts from the two source videos with ffmpeg.
# usage: python3 video/edit_ads.py <source_A.mp4> <source_B.mp4> <out_dir>
import os
import subprocess
import sys

SRC_A, SRC_B, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
W, H, FPS = 1080, 1920, 30
# Reels UI covers roughly the top 14% and bottom 35%; keep text between.
CAPTION_Y = 1030

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
}


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


def build(name, segments):
    inputs, chains = [], []
    total = 0.0
    for i, (src, start, dur, caption) in enumerate(segments):
        inputs += ["-ss", f"{start}", "-t", f"{dur}", "-i", SRC_A if src == "A" else SRC_B]
        f = (f"[{i}:v]scale={W}:{H}:flags=lanczos,fps={FPS},setsar=1,"
             f"setpts=PTS-STARTPTS")
        if caption == "__END__":
            f += (f",drawbox=x=0:y=860:w=iw:h=390:color=black@0.55:t=fill,"
                  + drawtext(f"{name}_{i}_a", END, 84, 905, 0) + ","
                  + drawtext(f"{name}_{i}_b", END_SUB, 62, 1040, 0))
        else:
            f += "," + drawtext(f"{name}_{i}", caption, 72, CAPTION_Y)
        chains.append(f + f"[v{i}]")
        total += dur
    n = len(segments)
    graph = ";".join(chains) + ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[v]"
    out = os.path.join(OUT, f"{name}.mp4")
    cmd = (["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + inputs
           + ["-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
              "-filter_complex", graph, "-map", "[v]", "-map", f"{n}:a",
              "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
              "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out])
    subprocess.run(cmd, check=True)
    print(f"{out}  segments={n}  planned={total:.1f}s")


os.makedirs(os.path.join(OUT, "txt"), exist_ok=True)
for name, segs in VARIANTS.items():
    build(name, segs)
