#!/usr/bin/env python3
"""
Clean up a JoyInvite page that was copied from DevTools (a live-DOM snapshot).

Usage:
    python3 fix_invite.py invite.html            -> writes invite-fixed.html
    python3 fix_invite.py invite.html out.html   -> writes out.html

Every fix is reported as OK (applied) or -- (pattern not found, nothing changed).
"""
import re
import sys

if len(sys.argv) < 2:
    sys.exit(__doc__)

src = sys.argv[1]
dst = sys.argv[2] if len(sys.argv) > 2 else re.sub(r"(\.html?)?$", "-fixed.html", src, count=1)
html = open(src, encoding="utf-8").read()
report = []


def sub(desc, pattern, repl, flags=re.S, count=0):
    """Regex replace across the file and log how many matches were changed."""
    global html
    html, n = re.subn(pattern, repl, html, count=count, flags=flags)
    report.append(f"{'OK' if n else '--'}  {desc} ({n})")


def literal(desc, old, new):
    """Plain string replace, for code where regex escaping would be noisy."""
    global html
    n = html.count(old)
    html = html.replace(old, new)
    report.append(f"{'OK' if n else '--'}  {desc} ({n})")


# 1. Doctype was not part of the outerHTML copy.
if not html.lstrip().lower().startswith("<!doctype"):
    html = "<!DOCTYPE html>\n" + html.lstrip()
    report.append("OK  added <!DOCTYPE html> (1)")

# 2. <html> carried a browser-extension attribute (nighteye) and live mouse-tilt
#    values. render() sets the image variables itself, so a clean tag is enough.
sub("clean <html> tag (nighteye attr, baked --mx/--my)", r"<html\b[^>]*>", '<html lang="en">', count=1)

# 3. The same set of @font-face rules is repeated ~10 times. Keep one copy of each,
#    in original order, so later overrides (e.g. the second Rebeque Demo) still win.
def dedupe_fonts(match):
    rules = re.findall(r"@font-face\{[^}]*\}", match.group(2))
    seen, kept = set(), []
    for rule in rules:
        if rule not in seen:
            seen.add(rule)
            kept.append(rule)
    report.append(f"OK  font-face rules: {len(rules)} -> {len(kept)}")
    return match.group(1) + "".join(kept) + match.group(3)

html, n = re.subn(r'(<style id="ji-fontfaces">)(.*?)(</style>)', dedupe_fonts, html, flags=re.S)
if not n:
    report.append("--  font-face block not found (0)")

# 4. The keyboard-lock script is injected twice; keep the first.
lock = list(re.finditer(r"<script>\(function\(\)\{var b=function\(e\)\{if\(e\.ctrlKey.*?</script>", html, re.S))
dupes = [m for m in lock[1:] if m.group(0) == lock[0].group(0)]
for m in reversed(dupes):
    html = html[: m.start()] + html[m.end():]
report.append(f"{'OK' if dupes else '--'}  removed duplicate lock script ({len(dupes)})")

# 5. Invalid CSS property.
sub("inset-right -> right", r"inset-right:\s*4%", "right: 4%")

# 6. Ganesh Pooja crop fix matched a file name that no longer exists (images are
#    hashed CDN URLs). Tag each card with its function kind and match on that.
literal("themeFor() also returns the kind", "return EVENT_THEMES[kind];",
        "return Object.assign({ kind: kind }, EVENT_THEMES[kind]);")
literal("event cards get data-kind",
        "'<article class=\"event-card\" data-image=\"' + inviteEscape(image)",
        "'<article class=\"event-card\" data-kind=\"' + theme.kind + '\" data-image=\"' + inviteEscape(image)")
literal("Ganesh Pooja crop selector", '.event-card[data-image$="ganesh-pooja.webp"]', '.event-card[data-kind="ganesh"]')

# 7. Page was copied after entering: restore the closed gate and locked scroll.
sub("body back to initial state", r'<body class="[^"]*"', '<body class="is-locked"', count=1)
sub("entry gate closed again",
    r'<div class="enter-gate[^"]*"( id="enterGate"[^>]*?)\s+aria-hidden="true"\s*>',
    r'<div class="enter-gate"\1>', count=1)

# 8. Baked petals (the script adds 18 more on load -> 36).
sub("empty petals container", r'(<div class="petals" id="petals" aria-hidden="true">).*?(</div>)', r"\1\2", count=1)

# 9. Runtime sizes / state frozen into the markup.
sub("fireworks canvas size reset", r'(<canvas class="fireworks-canvas" id="fireworksCanvas" aria-hidden="true")[^>]*>', r"\1>")
sub("music button starts off",
    r'class="music-button[^"]*" id="musicButton" type="button" aria-pressed="[^"]*"',
    'class="music-button" id="musicButton" type="button" aria-pressed="false"')
sub("dead blob: video src removed", r'\s+src="blob:[^"]*"', "")
sub("film/scratch canvas sizes reset", r'(<canvas id="(?:filmCanvas|scratchCanvas)"[^>]*?)\s+width="\d+"\s+height="\d+"', r"\1")
sub("captions not pre-activated", r'class="film-caption is-active"', 'class="film-caption"')
sub("caption inline styles removed", r'(<div class="film-caption[^"]*"[^>]*?)\s+style="[^"]*"', r"\1")
sub("film progress reset", r'(<span id="filmProgress")\s+style="[^"]*"', r"\1")
sub("film percent reset", r'(<div class="film-percent" id="filmPercent">)\d+(</div>)', r"\g<1>00\2")
sub("play button label", r'(<span id="filmPlayText">)[^<]*', r"\1Play film")
sub("scroll-in animations re-armed", r"\breveal is-visible\b", "reveal")
sub("countdown digits reset", r'(<b id="(?:days|hours|minutes|seconds)">)\d+(</b>)', r"\g<1>00\2")

# 10. Event cards are rebuilt by render() from CONFIG; the snapshot copy is redundant.
sub("empty static event stack", r'(<div class="event-stack" id="eventStack">).*?</article></div>', r"\1</div>", count=1)

# 11. Second music player. In the copy its <audio> has no src, and on load it
#     overwrites #bgMusic's src with "null", so the song never plays. The
#     template's own player (#bgMusic + Music button) is kept.
sub("removed duplicate ji-music player", r"<div data-ji-music=.*?</script></div>", "", count=1)

open(dst, "w", encoding="utf-8").write(html)
print("\n".join(report))
print(f"\nWrote {dst}")
