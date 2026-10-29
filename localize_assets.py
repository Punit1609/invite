#!/usr/bin/env python3
"""Download the invite's media next to the page and repoint the markup at it.

    python3 localize_assets.py index.html          -> rewrites index.html in place
    python3 localize_assets.py index.html out.html -> writes out.html

Files land under images/, video/ and audio/ with READABLE names (ganesh-pooja.webp, not
0390c6d6caea645554320fb2.webp) so a later swap is obvious. Every item reports OK or --.

The audio is included even though it was not asked for: bgMusic is the one media URL that lives in
the markup rather than CONFIG, and leaving a single file hotlinked defeats the point of localising
the other fourteen.

NOT the fonts. All 103 @font-face families point at the same CDN and NOTHING references them -- the
page draws only with Jost, Marcellus, Great Vibes, Cormorant Garamond, Tangerine and Pinyon Script,
which arrive from Google Fonts through an @import. Downloading the font library would add tens of
MB that no rule uses.
"""
import json
import pathlib
import re
import subprocess
import sys

if len(sys.argv) < 2:
    sys.exit(__doc__)

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else src
html = src.read_text(encoding="utf-8")

# ── locate CONFIG ────────────────────────────────────────────────────────────────────────────────
i = html.index("const CONFIG =")
s0 = html.index("{", i)
depth = 0
for j in range(s0, len(html)):
    if html[j] == "{":
        depth += 1
    elif html[j] == "}":
        depth -= 1
        if depth == 0:
            e0 = j + 1
            break
cfg = json.loads(html[s0:e0])


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ── plan: url -> (folder, filename). One entry per DISTINCT url. ─────────────────────────────────
plan: dict[str, tuple[str, str]] = {}
for key, fname in (("introImage", "intro"), ("filmPoster", "film-poster"),
                   ("closingImage", "closing")):
    url = cfg.get(key)
    if url:
        plan.setdefault(url, ("images", f"{fname}.{url.rsplit('.', 1)[-1]}"))
for fn in cfg.get("functions", []):
    url = fn.get("image")
    if url:
        plan.setdefault(url, ("images", f"{slug(fn['name'])}.{url.rsplit('.', 1)[-1]}"))
if cfg.get("filmVideo"):
    plan.setdefault(cfg["filmVideo"], ("video", "film.mp4"))
audio = re.search(r'<audio id="bgMusic" src="([^"]+)"', html)
if audio:
    plan.setdefault(audio.group(1), ("audio", "music.mp3"))

for folder in ("images", "video", "audio"):
    pathlib.Path(folder).mkdir(exist_ok=True)

# ── download ─────────────────────────────────────────────────────────────────────────────────────
report, failed = [], 0
for url, (folder, fname) in plan.items():
    out = pathlib.Path(folder) / fname
    r = subprocess.run(
        ["curl", "-fsSL", "--max-time", "120", "-o", str(out), url],
        capture_output=True, text=True,
    )
    if r.returncode == 0 and out.exists() and out.stat().st_size > 0:
        report.append(f"OK  {out}  ({out.stat().st_size:,} B)")
    else:
        failed += 1
        report.append(f"--  {out}  FAILED {r.stderr.strip()[:60] or 'empty file'}")
        out.unlink(missing_ok=True)

# ── repoint the markup ───────────────────────────────────────────────────────────────────────────
rewritten = 0
for url, (folder, fname) in plan.items():
    local = f"{folder}/{fname}"
    if not pathlib.Path(local).exists():
        report.append(f"--  kept remote (download failed): {url[-28:]}")
        continue
    n = html.count(url)
    html = html.replace(url, local)
    rewritten += n
    report.append(f"OK  -> {local}  ({n} reference{'s' if n != 1 else ''})")

dst.write_text(html, encoding="utf-8")
print("\n".join(report))
left = len(re.findall(r"cdn\.joyinvite\.in", html))
print(f"\n{len(plan)} file(s) planned, {failed} failed, {rewritten} reference(s) rewritten")
print(f"Wrote {dst}")
print(f"cdn.joyinvite.in references left in the page: {left}"
      f"{'  (all fonts -- nothing uses them)' if left else ''}")
