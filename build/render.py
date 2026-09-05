#!/usr/bin/env python3
"""Draw the profile plates as self-hosted animated SVG. Standard library only.

SCALE -- what version one got wrong. GitHub's README column is about 880 CSS px.
The plates were drawn on a 1600px canvas and embedded at width=100%, so every
12px label rendered at 6.6px and the page read as grey mush. Everything here is
drawn at W=880, one logical unit per rendered pixel, so a 12px label is 12px. It
stays sharp above 880 because it is vector.

ENVELOPE -- GitHub serves .svg from raw.githubusercontent.com under
    Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox
Inline CSS, @keyframes included, is allowed. JavaScript, webfonts and every
external subresource are not. CSS animation rather than SMIL, because SMIL
inside <img> does not begin until page load has finished.

LANGUAGE -- lifted from the two terminals in this repo's orbit: ALPHABIT and the
RegimeRoute blotter. Near-black ground, amber primary, mint positive, rose
negative. Monospace for everything, square corners, hairline rules, numbered
panel headers, a status line, an F-key bar. Colour carries data and nothing
else: no gradient fills, no blur, no glow. A profile page for someone who reads
terminals should look like one.
"""
from __future__ import annotations

import argparse
import math
import pathlib
import random

W = 880                      # == GitHub's content column. Do not raise this.
PAD = 20
X1 = W - PAD

MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,'Courier New',monospace"

# Two properties hold across this table, and build/verify.py fails the build on
# either one breaking.
#
# 1. CONTRAST. Every foreground clears WCAG AA 4.5:1 against all three grounds
#    (bg, panel, strip). fg3 carries the 9px annotations -- the smallest type on
#    the page -- and the first pass had it at 3.30:1 on the strip: the least
#    readable colour on the least readable text. Nothing sits closer to the line
#    than 4.77 now, because a value that only just clears it is one rounding away
#    from not clearing it.
#
# 2. SEPARABILITY. The page's argument is that colour carries data, so two data
#    colours that look alike break it silently. Every semantic ink is >=40 Lab dE
#    from every other and >=44 from every neutral. Light cyan used to be #0A78A0,
#    which is 25 dE from fg2 -- and the KPI tile puts a 9.5px fg2 label directly
#    above its 22px semantic value, so that one tile read as a grey label over a
#    slightly-bluer-grey number while the other three read as label over colour.
#    #0069BF is 45 dE out and matches the other three in lightness besides.
T = {
    "dark": dict(
        bg="#07090C", panel="#0D1014", strip="#141922", edge="#232A33",
        rule="#1A2029", fg="#E8EDF2", fg2="#98A2AE", fg3="#7B8896",
        amber="#FFA92B", mint="#4ADE80", rose="#FF6B6B", cyan="#56D4E8",
        violet="#B08CFF", wash=".10", band=".06",
    ),
    "light": dict(
        bg="#FFFFFF", panel="#FBFCFD", strip="#F1F4F8", edge="#D3DBE4",
        rule="#E8EDF3", fg="#0A0F14", fg2="#4C5865", fg3="#636C75",
        amber="#95600A", mint="#007D3A", rose="#C0324E", cyan="#0069BF",
        violet="#6A43C4", wash=".085", band=".07",
    ),
}
def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def w_mono(s: str, size: float, track: float = 0.0) -> float:
    """Advance width. JetBrains Mono and every fallback here are 0.600em."""
    return len(s) * (0.600 * size + track)


def txt(x, y, s, *, size=11.5, fill="#fff", weight=400, track=0, anchor="start",
        cls=None, style=None, op=None) -> str:
    a = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-size="{size}"',
         f'font-family="{MONO}"', f'fill="{fill}"']
    if weight != 400:
        a.append(f'font-weight="{weight}"')
    if track:
        a.append(f'letter-spacing="{track}"')
    if anchor != "start":
        a.append(f'text-anchor="{anchor}"')
    if op is not None:
        a.append(f'opacity="{op}"')
    if cls:
        a.append(f'class="{cls}"')
    if style:
        a.append(f'style="{style}"')
    return f'<text {" ".join(a)}>{esc(s)}</text>'


def rect(x, y, w, h, *, fill="none", stroke=None, rx=0, op=None, cls=None,
         style=None, sw=1) -> str:
    a = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'width="{w:.1f}"', f'height="{h:.1f}"',
         f'fill="{fill}"']
    if rx:
        a.append(f'rx="{rx}"')
    if stroke:
        a += [f'stroke="{stroke}"', f'stroke-width="{sw}"']
    if op is not None:
        a.append(f'opacity="{op}"')
    if cls:
        a.append(f'class="{cls}"')
    if style:
        a.append(f'style="{style}"')
    return f'<rect {" ".join(a)}/>'


def line(x1, y1, x2, y2, *, stroke, sw=1, op=None, cls=None, style=None) -> str:
    a = [f'x1="{x1:.1f}"', f'y1="{y1:.1f}"', f'x2="{x2:.1f}"', f'y2="{y2:.1f}"',
         f'stroke="{stroke}"', f'stroke-width="{sw}"']
    for k, v in (("opacity", op), ("class", cls), ("style", style)):
        if v is not None:
            a.append(f'{k}="{v}"')
    return f'<line {" ".join(a)}/>'
def pill(x, y, label, colour, *, size=10.5, h=21, pad=8, track=.8,
         cls=None, style=None) -> tuple[str, float]:
    """Flat square-cornered tag: the BUY / TRENDING / FALSIFIED chip."""
    w = w_mono(label, size, track) + pad * 2
    g = (rect(x, y, w, h, fill=colour, op=".12", rx=2)
         + rect(x + .5, y + .5, w - 1, h - 1, stroke=colour, op=".60", rx=2)
         + txt(x + pad, y + h / 2 + size * .36, label, size=size, fill=colour,
               weight=600, track=track))
    if cls:
        g = f'<g class="{cls}"{f" style={style!r}" if style else ""}>{g}</g>'
    return g, w


def head(h: int, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" '
            f'viewBox="0 0 {W} {h}" role="img" aria-label="{esc(title)}">'
            f"<title>{esc(title)}</title>")


def css(body: str) -> str:
    return f"<style>/*<![CDATA[*/{body}/*]]>*/</style>"


BASE = """
*{transform-box:fill-box;transform-origin:center}
@keyframes rise{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes blink{0%,48%{opacity:1}52%,100%{opacity:.08}}
@keyframes tick{0%,100%{opacity:.3}50%{opacity:1}}
.r{opacity:0;animation:rise .55s cubic-bezier(.22,1,.36,1) forwards}
.f{opacity:0;animation:fade .7s ease-out forwards}
.bl{animation:blink 1.4s steps(1,end) infinite}
.k{animation:tick 2.6s ease-in-out infinite}
"""


def frame(t, h) -> str:
    return (rect(0, 0, W, h, fill=t["bg"], rx=2)
            + rect(.5, .5, W - 1, h - 1, stroke=t["edge"], rx=2))


def panel_head(t, n, title, note, colour) -> str:
    """`3 VITALS -- CHAMPION` ... right-aligned dim annotation. ALPHABIT's grammar."""
    return "".join([
        rect(0, 0, W, 28, fill=t["strip"]),
        rect(PAD, 7, 15, 15, fill=colour, rx=2),
        txt(PAD + 7.5, 18, str(n), size=10, fill=t["bg"], weight=700,
            anchor="middle"),
        txt(PAD + 24, 18, title, size=10.5, fill=t["fg"], weight=700, track=1.3),
        txt(X1, 18, note, size=9.5, fill=t["fg3"], track=.4, anchor="end"),
        line(0, 28, W, 28, stroke=t["edge"]),
    ])


def fields(t, x, y, pairs, *, size=10.5, hi=None) -> str:
    """`FOCUS CHAMPION | SHARPE 0.78 | ...` -- dim key, bright value, thin bars."""
    o, cx = [], x
    for i, (k, v, c) in enumerate(pairs):
        if i:
            o.append(txt(cx, y, "|", size=size, fill=t["edge"]))
            cx += w_mono("|  ", size)
        o.append(txt(cx, y, k, size=size, fill=t["fg3"], track=.5))
        cx += w_mono(k + " ", size, .5)
        o.append(txt(cx, y, v, size=size, fill=c or hi or t["fg"], weight=600))
        cx += w_mono(v + "  ", size)
    return "".join(o)
NAME = "MANAV SHARMA"
LINE = "I build learning systems, then build the harness that tries to break them."
BEAT = ("// UNSUPERVISED REGIME CLUSTERING  ·  META-LEARNED ABSTENTION  ·  "
        "PROOF-CARRYING EXECUTION")
MENU = "PAPER   ROUTE   FORGE   ALPHA   OSS   CONTACT"


def ident(t, merged: int = 19) -> str:
    """Plate 1 -- masthead: menu rail, status line, one display size, four tiles."""
    H = 236
    o = [head(H, f"{NAME} -- machine learning research, systems, market "
                f"microstructure"), css(BASE), frame(t, H)]

    # ---- menu rail -------------------------------------------------------
    o.append(rect(0, 0, W, 26, fill=t["strip"]))
    o.append(txt(PAD, 17, "MANAVMAX", size=11.5, fill=t["amber"], weight=700,
                 track=1.2, cls="f"))
    o.append(txt(100, 17, MENU, size=10, fill=t["fg3"], track=.8, cls="f",
                 style="animation-delay:.06s"))
    gx = X1 - w_mono("OPEN TO RESEARCH & SYSTEMS ROLES", 10, .8) - 14
    o.append('<g class="f" style="animation-delay:.12s">')
    o.append(rect(gx - 46, 5.5, 38, 15, fill=t["amber"], op=".14", rx=2))
    o.append(rect(gx - 45.5, 6, 37, 14, stroke=t["amber"], op=".7", rx=2))
    o.append(txt(gx - 41, 16, "<GO>", size=9.5, fill=t["amber"], weight=700, track=.4))
    o.append(f'<circle cx="{gx - 1}" cy="12.5" r="3.2" fill="{t["mint"]}" class="bl"/>')
    o.append(txt(X1, 16, "OPEN TO RESEARCH & SYSTEMS ROLES", size=10,
                 fill=t["mint"], track=.8, anchor="end"))
    o.append("</g>")
    o.append(line(0, 26, W, 26, stroke=t["edge"]))

    # ---- status line -----------------------------------------------------
    o.append(rect(0, 26, W, 24, fill=t["panel"]))
    o.append(f'<g class="f" style="animation-delay:.18s">')
    o.append(fields(t, PAD, 42, [
        ("FOCUS", "ML RESEARCH + SYSTEMS", t["fg"]),
        ("PAPER", "IEEE ICIPTM 2026", t["violet"]),
        ("MERGED", f"{merged} UPSTREAM", t["mint"]),
        ("ROWS", "13M+", t["cyan"]),
        ("CLASS", "2026", t["fg2"]),
    ], size=10))
    o.append("</g>")
    o.append(line(0, 50, W, 50, stroke=t["edge"]))

    # ---- identity --------------------------------------------------------
    o.append(txt(PAD, 74, BEAT, size=10, fill=t["fg3"], track=.8, cls="r",
                 style="animation-delay:.14s"))
    o.append(txt(PAD, 116, NAME, size=38, fill=t["fg"], weight=700, track=.5,
                 cls="r", style="animation-delay:.2s"))
    o.append(rect(PAD + w_mono(NAME, 38, .5) + 9, 95, 13, 25, fill=t["amber"],
                  cls="bl"))
    o.append(txt(PAD, 140, LINE, size=11.5, fill=t["fg2"], cls="r",
                 style="animation-delay:.26s"))

    # ---- tiles: label / value / caption ----------------------------------
    KPI = [("IEEE PAPER", "01", "FIRST AUTHOR, ICIPTM 2026", "violet"),
           ("UPSTREAM MERGED", str(merged), "INTO REPOS I DO NOT OWN", "mint"),
           ("ORDER-BOOK ROWS", "13M+", "REPLAYED, NOT SIMULATED", "cyan"),
           ("CLAIMS FALSIFIED", "01", "PUBLISHED ANYWAY", "rose")]
    cw = (X1 - PAD - 24) / 4
    for i, (lab, val, cap, key) in enumerate(KPI):
        x, c = PAD + i * (cw + 8), t[key]
        o.append(f'<g class="r" style="animation-delay:{.32 + i * .07:.2f}s">')
        o.append(rect(x, 158, cw, 62, fill=c, op=t["wash"], rx=2))
        o.append(rect(x + .5, 158.5, cw - 1, 61, stroke=c, op=".30", rx=2))
        o.append(rect(x + 11, 170, 6, 6, fill=c, rx=1, cls="k",
                      style=f"animation-delay:{i * .55:.2f}s"))
        o.append(txt(x + 23, 176, lab, size=9.5, fill=t["fg2"], track=1.2))
        o.append(txt(x + 11, 202, val, size=22, fill=c, weight=700, track=.3))
        o.append(txt(x + 11, 214, cap, size=9, fill=t["fg3"], track=.4))
        o.append("</g>")
    return "".join(o) + "</svg>"
BLOTTER = [
    dict(key="violet", verdict="PEER-REVIEWED",
         work="Regime-aware meta-learning for selective trading",
         how="UNSUPERVISED TEMPORAL CLUSTERING  ·  MAML  ·  ABSTENTION",
         evidence="DOI 10.1109/ICIPTM69057.2026.11466047"),
    dict(key="rose", verdict="FALSIFIED", work="Regime-Route",
         how="C++20  ·  POSTGRES  ·  REDIS  ·  HASH-VERIFIED RECEIPTS",
         evidence="26 ORDERS  ·  -451.96 bps AVG EDGE  ·  38% WIN RATE"),
    dict(key="mint", verdict="SHIPPED", work="Tensor-Forge",
         how="C++20  ·  WGSL  ·  ITS OWN JIT, NO PYTORCH, NO CUDA",
         evidence="5 / 5 CTEST SUITES  ·  FULL CI"),
    dict(key="cyan", verdict="UNDER AUDIT", work="Bitcoin Alpha System",
         how="PYTHON  ·  PYTORCH  ·  WALK-FORWARD + HOLDOUT RUNNING",
         evidence="NO RETURN FIGURE UNTIL VALIDATION CLEARS"),
]
KEY = ("PEER-REVIEWED outside review passed  ·  SHIPPED tested and running  ·  "
       "FALSIFIED effect absent, published anyway  ·  UNDER AUDIT still validating")


def blotter(t) -> str:
    """Plate 2 -- four claims, one row each, in the execution-blotter grammar.

    A verdict column that is allowed to say FALSIFIED is the entire point. It is
    the one column a portfolio page never has.
    """
    RH, Y0 = 44, 48
    H = Y0 + RH * len(BLOTTER) + 26
    o = [head(H, "Claim blotter: four projects, each with a verdict"),
         css(BASE), frame(t, H)]
    o.append(panel_head(t, 1, "CLAIM BLOTTER — WHAT I BUILT AND HOW IT ENDED",
                        "2 of 4 are not wins  ·  none of it is unaudited",
                        t["amber"]))
    for x, s, a in ((PAD, "#", "start"), (PAD + 34, "WORK / METHOD", "start"),
                    (X1 - 118, "EVIDENCE", "end"), (X1, "VERDICT", "end")):
        o.append(txt(x, 42, s, size=9, fill=t["fg3"], track=1.2, anchor=a))
    o.append(line(0, Y0, W, Y0, stroke=t["rule"]))

    for i, r in enumerate(BLOTTER):
        y, c = Y0 + i * RH, t[r["key"]]
        o.append(f'<g class="r" style="animation-delay:{.14 + i * .09:.2f}s">')
        o.append(txt(PAD, y + 19, f"{i + 1:02d}", size=11, fill=c, weight=700))
        o.append(txt(PAD + 34, y + 19, r["work"], size=13, fill=t["fg"], weight=700))
        o.append(txt(PAD + 34, y + 34, r["how"], size=9.5, fill=t["fg3"], track=.4))
        o.append(txt(X1, y + 34, r["evidence"], size=10, fill=t["fg2"],
                     track=.3, anchor="end"))
        p, pw = pill(0, 0, r["verdict"], c)
        o.append(f'<g transform="translate({X1 - pw:.1f},{y + 6})">{p}</g>')
        if i < len(BLOTTER) - 1:
            o.append(line(PAD, y + RH, X1, y + RH, stroke=t["rule"]))
        o.append("</g>")

    o.append(line(0, H - 26, W, H - 26, stroke=t["rule"]))
    o.append(txt(PAD, H - 10, KEY, size=9, fill=t["fg3"], track=.2, cls="f",
                 style="animation-delay:.6s"))
    return "".join(o) + "</svg>"
REGIMES = [(0.00, 0.36, "cyan", "TRENDING", True),
           (0.36, 0.66, "rose", "VOLATILE", False),
           (0.66, 1.00, "mint", "CALM", True)]

# (drift, vol) per regime. The first draft ran one cumulative walk with a wider
# sigma inside VOLATILE, and a walk with wide steps still trends: the abstain
# band came out as smooth and as directional as the other two, which destroys
# the only point the plate makes. So the level is frozen there instead and the
# shocks alternate sign -- chop with no net direction, which is what "unsure"
# looks like and what the rule is meant to sit out.
WALK = {"TRENDING": (0.42, 0.20), "VOLATILE": (0.0, 2.6), "CALM": (0.22, 0.11)}


def regime_at(f: float):
    for lo, hi, key, name, act in REGIMES:
        if lo <= f <= hi:
            return key, name, act
    return REGIMES[-1][2], REGIMES[-1][3], REGIMES[-1][4]


def regime(t) -> str:
    """Plate 3 -- the paper's rule, drawn: cluster the tape, act only when sure.

    Schematic, and labelled as one. The series is a seeded walk, not a backtest;
    the thing being illustrated is the decision rule, which is the contribution.
    """
    PY0, PY1, H = 72, 152, 200
    pw = X1 - PAD
    o = [head(H, "Selective signal: the model stands down inside the volatile "
                 "regime"),
         css(BASE + ".ln{stroke-dasharray:var(--l);stroke-dashoffset:var(--l);"
                    "animation:draw 2.2s ease-out .3s forwards}"),
         frame(t, H)]
    o.append(panel_head(t, 2, "SELECTIVE SIGNAL — IT STANDS DOWN WHEN UNSURE",
                        "schematic of the rule, not a backtest", t["cyan"]))

    rnd = random.Random(11)
    n, ys, base, sgn = 132, [], 0.0, 1
    for i in range(n):
        _, nm, act = regime_at(i / (n - 1))
        drift, vol = WALK[nm]
        if act:
            base += rnd.gauss(drift, drift * .3)
            ys.append(base + rnd.gauss(0, vol))
        else:
            # Mostly alternating, not strictly: a perfect sawtooth reads as a
            # decorative glyph. Sign flips 78% of the time, so the period varies
            # while every point still sits within +/-vol of the frozen level.
            if rnd.random() < .78:
                sgn = -sgn
            ys.append(base + sgn * rnd.uniform(vol * .55, vol))
    lo, hi = min(ys), max(ys)
    pts = [(PAD + i * pw / (n - 1), PY1 - (y - lo) / (hi - lo) * (PY1 - PY0))
           for i, y in enumerate(ys)]

    for lo_f, hi_f, key, nm, act in REGIMES:
        x0, x1 = PAD + lo_f * pw, PAD + hi_f * pw
        c = t[key]
        o.append(rect(x0, 32, x1 - x0, 124, fill=c, op=t["band"]))
        if lo_f:
            o.append(line(x0, 32, x0, 156, stroke=c, op=".40",
                          style="stroke-dasharray:3 3"))
        p, pwid = pill(x0 + 9, 36, nm, c, size=10, h=18, pad=8, track=.8)
        o.append(f'<g class="f" style="animation-delay:.15s">{p}</g>')
        o.append(txt(x0 + 17 + pwid, 49, "ACTS" if act else "ABSTAINS", size=10,
                     fill=t["fg2"] if act else t["fg3"], weight=600, track=1,
                     cls="f", style="animation-delay:.2s"))

    d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    L = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    o.append(f'<path d="{d}" fill="none" stroke="{t["fg2"]}" stroke-width="1.6" '
             f'stroke-linejoin="round" class="ln" style="--l:{L:.0f}"/>')

    # ---- decision rug: one mark per bar, so the stood-down block is visible --
    # Step 1, not 2. When it sampled every other bar the footer count described
    # the rug rather than the series, so the plate stated 46 of 66 for a 132-bar
    # picture. One mark per bar makes the caption true by construction.
    acted = 0
    for i in range(n):
        key, _, act = regime_at(i / (n - 1))
        x = PAD + i * pw / (n - 1)
        if act:
            acted += 1
            o.append(rect(x, 158, 1.6, 8, fill=t[key], op=".85"))
        else:
            o.append(rect(x, 162, 1.6, 3, fill=t["fg3"], op=".55"))

    for i in range(6, n, 13):                       # markers only where it acts
        key, _, act = regime_at(i / (n - 1))
        if not act:
            continue
        x, y = pts[i]
        c = t["mint"] if ys[i] >= ys[max(0, i - 6)] else t["rose"]
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3.4" fill="{t["bg"]}" '
                 f'stroke="{c}" stroke-width="1.8" class="f" '
                 f'style="animation-delay:{.9 + i * .008:.2f}s"/>')

    o.append('<g class="f" style="animation-delay:1.5s">')
    o.append(txt(PAD, 186, "MARKER = POSITION TAKEN   ·   FAINT TICK = STOOD DOWN",
                 size=9.5, fill=t["fg3"], track=.8))
    o.append(txt(X1, 186, f"ACTED ON {acted} OF {n} BARS  ·  ABSTAINED "
                          f"{n - acted}  ({(n - acted) * 100 // n}%)",
                 size=9.5, fill=t["fg2"], track=.8, anchor="end"))
    o.append("</g>")
    return "".join(o) + "</svg>"
STACK = [("SYSTEMS", "cyan", ["C++20", "Python", "TypeScript", "JavaScript"],
          "c++20 in regime-route and tensor-forge · python in bitcoin-alpha"),
         ("LEARNING", "violet", ["PyTorch", "TensorFlow", "scikit-learn",
                                 "meta-learning"],
          "pytorch in bitcoin-alpha · maml + clustering in the paper"),
         ("STATE", "mint", ["PostgreSQL", "Redis", "SQLite"],
          "postgres and redis behind regime-route's 13m+ rows"),
         ("SURFACE", "amber", ["Next.js", "React", "FastAPI"],
          "next.js consoles: regime-route, tensor-forge"),
         ("SHIPPING", "rose", ["Docker", "GitHub Actions", "CMake / CTest"],
          "github actions + ctest: 5/5 suites green in tensor-forge")]


def stack(t) -> str:
    """Plate 4 -- the apparatus as five labelled lanes, not a wall of badges."""
    RH, Y0 = 32, 44
    H = Y0 + RH * len(STACK) + 14
    o = [head(H, "Apparatus: systems, learning, state, surface, shipping"),
         css(BASE), frame(t, H)]
    o.append(panel_head(t, 3, "APPARATUS — WHAT I HAVE ACTUALLY SHIPPED WITH",
                        "grouped by what it is for, not by badge count",
                        t["violet"]))
    for i, (lab, key, items, where) in enumerate(STACK):
        y, c = Y0 + i * RH, t[key]
        o.append(f'<g class="r" style="animation-delay:{.12 + i * .08:.2f}s">')
        o.append(rect(PAD, y + 7, 3, 12, fill=c, rx=1))
        o.append(txt(PAD + 11, y + 19, lab, size=10, fill=c, weight=700, track=1.3))
        x = PAD + 100
        for it in items:
            p, pwid = pill(x, y + 5, it, c, size=11, h=21, pad=8, track=0)
            o.append(p)
            x += pwid + 6
        o.append(txt(X1, y + 19, where, size=9, fill=t["fg3"], track=.3,
                     anchor="end"))
        if i < len(STACK) - 1:
            o.append(line(PAD, y + RH, X1, y + RH, stroke=t["rule"]))
        o.append("</g>")
    return "".join(o) + "</svg>"


FKEYS = [("F1", "IEEE PAPER"), ("F2", "REGIME-ROUTE"), ("F3", "TENSOR-FORGE"),
         ("F4", "BITCOIN-ALPHA"), ("F5", "LINKEDIN"), ("F6", "EMAIL")]


def keys(t) -> str:
    """Plate 5 -- the F-key rail off the bottom of a terminal. The links below it
    in the README are the real, clickable version; this is the chrome."""
    H = 36
    o = [head(H, "Function key rail: paper, projects, contact"), css(BASE),
         rect(0, 0, W, H, fill=t["strip"], rx=2),
         rect(.5, .5, W - 1, H - 1, stroke=t["edge"], rx=2)]
    cw = (X1 - PAD - 5 * 6) / 6
    for i, (fk, lab) in enumerate(FKEYS):
        x = PAD + i * (cw + 6)
        o.append(f'<g class="f" style="animation-delay:{.06 + i * .05:.2f}s">')
        o.append(rect(x, 6, cw, 24, fill=t["panel"], rx=2))
        o.append(rect(x + .5, 6.5, cw - 1, 23, stroke=t["edge"], rx=2))
        o.append(rect(x + 5, 10, 19, 16, fill=t["amber"], op=".16", rx=2))
        o.append(rect(x + 5.5, 10.5, 18, 15, stroke=t["amber"], op=".55", rx=2))
        o.append(txt(x + 8.5, 21, fk, size=9, fill=t["amber"], weight=700, track=.4))
        o.append(txt(x + 29, 21, lab, size=10, fill=t["fg2"], track=.3))
        o.append("</g>")
    return "".join(o) + "</svg>"


PLATES = {"ident": ident, "blotter": blotter, "regime": regime, "stack": stack,
          "keys": keys}


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the profile plates.")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--merged", type=int, default=19,
                    help="upstream merged-PR count shown in the masthead")
    a = ap.parse_args()
    d = pathlib.Path(a.out)
    d.mkdir(parents=True, exist_ok=True)
    for name, fn in PLATES.items():
        for th, t in T.items():
            svg = fn(t, a.merged) if name == "ident" else fn(t)
            p = d / f"{name}-{th}.svg"
            p.write_text(svg, encoding="utf-8")
            print(f"  {p}  {p.stat().st_size / 1024:5.1f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())






