#!/usr/bin/env python3
"""Generate every graphic on the profile as a self-hosted animated SVG.

Standard library only. No matplotlib, no Pillow, no external widget service.

Why hand-written SVG: GitHub serves .svg from raw.githubusercontent.com with
    Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox
so inline CSS (including @keyframes) is explicitly allowed, SMIL is allowed,
and JavaScript plus external webfonts are blocked. That is the whole design
envelope: animate with CSS, never rely on a font being downloadable.
"""
from __future__ import annotations
import argparse, math, pathlib, random, xml.sax.saxutils as sx

SANS = "Inter,system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono',ui-monospace,SFMono-Regular,Menlo,Consolas,monospace"

T = {
    "dark": dict(
        bg="#0B1120", bg2="#131C31", panel="#0F1729", edge="#1E293B",
        fg="#F1F5F9", fg2="#94A3B8", fg3="#5B6B85",
        violet="#A78BFA", emerald="#34D399", amber="#FBBF24",
        cyan="#22D3EE", pink="#F472B6", aurora=".55", band=".085", wash=".10",
    ),
    "light": dict(
        bg="#FFFFFF", bg2="#F8FAFC", panel="#FFFFFF", edge="#E2E8F0",
        fg="#0F172A", fg2="#475569", fg3="#94A3B8",
        violet="#7C3AED", emerald="#059669", amber="#D97706",
        cyan="#0891B2", pink="#DB2777", aurora=".28", band=".07", wash=".07",
    ),
}

# ---------------------------------------------------------------- primitives
def esc(s): return sx.escape(str(s))
def w_mono(s, size): return len(s) * 0.600 * size
def w_sans(s, size):
    wide, narrow = set("MWmw@"), set("iljtfIr.,:;'|! ")
    return sum(0.86 if c in wide else 0.30 if c in narrow else 0.545 for c in s) * size

def txt(s, x, y, fam, size, fill, *, anchor="start", track=0.0, weight=None,
        opacity=None, cls=None, style=None):
    a = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-family="{esc(fam)}"',
         f'font-size="{size}"', f'fill="{fill}"']
    if anchor != "start":
        a.append(f'text-anchor="{anchor}"')
        if track: a.append(f'dx="{-track/2:.2f}"')
    if track:   a.append(f'letter-spacing="{track}"')
    if weight:  a.append(f'font-weight="{weight}"')
    if opacity is not None: a.append(f'fill-opacity="{opacity}"')
    if cls:     a.append(f'class="{cls}"')
    if style:   a.append(f'style="{style}"')
    return f'<text {" ".join(a)}>{esc(s)}</text>'

def rect(x, y, w, h, fill, *, rx=0, stroke=None, sw=1, fo=None, so=None, cls=None, style=None):
    a = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'width="{w:.1f}"', f'height="{h:.1f}"', f'fill="{fill}"']
    if rx:     a.append(f'rx="{rx}"')
    if stroke: a += [f'stroke="{stroke}"', f'stroke-width="{sw}"']
    if fo is not None: a.append(f'fill-opacity="{fo}"')
    if so is not None: a.append(f'stroke-opacity="{so}"')
    if cls:    a.append(f'class="{cls}"')
    if style:  a.append(f'style="{style}"')
    return f'<rect {" ".join(a)}/>'

def line(x1, y1, x2, y2, stroke, sw=1, *, o=None, cap=None, cls=None, style=None):
    a = [f'x1="{x1:.1f}"', f'y1="{y1:.1f}"', f'x2="{x2:.1f}"', f'y2="{y2:.1f}"',
         f'stroke="{stroke}"', f'stroke-width="{sw}"']
    if o is not None: a.append(f'stroke-opacity="{o}"')
    if cap:  a.append(f'stroke-linecap="{cap}"')
    if cls:  a.append(f'class="{cls}"')
    if style: a.append(f'style="{style}"')
    return f'<line {" ".join(a)}/>'

def circ(cx, cy, r, fill, *, o=None, stroke=None, sw=1, cls=None, style=None):
    a = [f'cx="{cx:.1f}"', f'cy="{cy:.1f}"', f'r="{r}"', f'fill="{fill}"']
    if o is not None: a.append(f'fill-opacity="{o}"')
    if stroke: a += [f'stroke="{stroke}"', f'stroke-width="{sw}"']
    if cls:  a.append(f'class="{cls}"')
    if style: a.append(f'style="{style}"')
    return f'<circle {" ".join(a)}/>'

def head(w, h, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title>')

def css(body):
    return "<style>/*<![CDATA[*/" + body + "/*]]>*/</style>"

# Shared keyframes. Entrance animations use `forwards` so the page settles
# instead of looping in the reader's peripheral vision.
BASE_CSS = """
*{transform-box:fill-box;transform-origin:center}
@keyframes rise{from{opacity:0;transform:translateY(9px)}to{opacity:1;transform:translateY(0)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes halo{0%{transform:scale(1);opacity:.55}70%,100%{transform:scale(3.2);opacity:0}}
.rise{opacity:0;animation:rise .75s cubic-bezier(.22,1,.36,1) forwards}
.fade{opacity:0;animation:fade .9s ease-out forwards}
.halo{animation:halo 2.6s ease-out infinite}
"""

# ------------------------------------------------------------------- 1. HERO
NAME = "MANAV SHARMA"
ROLE = [("ML RESEARCH", "violet"), ("SYSTEMS & COMPILERS", "cyan"),
        ("MARKET MICROSTRUCTURE", "pink")]

def hero(th: str, merged: int) -> str:
    c, W, H = T[th], 1600, 440
    M, MID = 88, 800
    chips = [("01", "IEEE PAPER, FIRST AUTHOR", "violet"),
             (str(merged), "UPSTREAM PRs MERGED", "emerald"),
             ("13M+", "ORDER-BOOK ROWS TESTED", "cyan")]
    o = [head(W, H, "Manav Sharma — ML research, systems and compilers")]
    o.append(f'''<defs>
<linearGradient id="sky" x1="0" y1="0" x2="1" y2="1">
  <stop offset="0" stop-color="{c['bg']}"/><stop offset="1" stop-color="{c['bg2']}"/>
</linearGradient>
<radialGradient id="b1"><stop offset="0" stop-color="{c['violet']}" stop-opacity="{c['aurora']}"/><stop offset="1" stop-color="{c['violet']}" stop-opacity="0"/></radialGradient>
<radialGradient id="b2"><stop offset="0" stop-color="{c['cyan']}" stop-opacity="{c['aurora']}"/><stop offset="1" stop-color="{c['cyan']}" stop-opacity="0"/></radialGradient>
<radialGradient id="b3"><stop offset="0" stop-color="{c['pink']}" stop-opacity="{c['aurora']}"/><stop offset="1" stop-color="{c['pink']}" stop-opacity="0"/></radialGradient>
<linearGradient id="ink" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{c['fg']}"/><stop offset=".55" stop-color="{c['violet']}"/><stop offset="1" stop-color="{c['cyan']}"/>
</linearGradient>
<linearGradient id="ul" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{c['violet']}"/><stop offset=".5" stop-color="{c['cyan']}"/><stop offset="1" stop-color="{c['pink']}"/>
</linearGradient>
<linearGradient id="gloss" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".85"/><stop offset="1" stop-color="#fff" stop-opacity="0"/>
</linearGradient>
<pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">
  <circle cx="1.2" cy="1.2" r="1.2" fill="{c['fg3']}" fill-opacity=".5"/>
</pattern>
<linearGradient id="vig" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="#000"/><stop offset=".28" stop-color="#fff"/>
  <stop offset=".72" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
</linearGradient>
<mask id="mgrid"><rect width="{W}" height="{H}" fill="url(#vig)"/></mask>
<clipPath id="nameclip">{txt(NAME, MID, 238, SANS, 104, "#000", anchor="middle", track=2, weight="800")}</clipPath>
<clipPath id="frame"><rect width="{W}" height="{H}" rx="0"/></clipPath>
</defs>''')
    o.append(css(BASE_CSS + f"""
@keyframes d1{{0%,100%{{transform:translate(0,0) scale(1)}}50%{{transform:translate(90px,34px) scale(1.18)}}}}
@keyframes d2{{0%,100%{{transform:translate(0,0) scale(1.08)}}50%{{transform:translate(-70px,-40px) scale(.92)}}}}
@keyframes d3{{0%,100%{{transform:translate(0,0) scale(.95)}}50%{{transform:translate(46px,58px) scale(1.2)}}}}
.a1{{animation:d1 23s ease-in-out infinite}}
.a2{{animation:d2 29s ease-in-out infinite}}
.a3{{animation:d3 26s ease-in-out infinite}}
@keyframes sweep{{0%{{transform:translateX(-780px)}}42%,100%{{transform:translateX(780px)}}}}
.gloss{{animation:sweep 7s cubic-bezier(.5,0,.5,1) infinite}}
"""))
    o.append(f'<g clip-path="url(#frame)">')
    o.append(rect(0, 0, W, H, "url(#sky)"))
    o.append(f'<g style="filter:blur(96px)">'
             f'<g class="a1">{circ(300, 118, 250, "url(#b1)")}</g>'
             f'<g class="a2">{circ(1310, 336, 268, "url(#b2)")}</g>'
             f'<g class="a3">{circ(838, -46, 224, "url(#b3)")}</g></g>')
    o.append(f'<rect width="{W}" height="{H}" fill="url(#grid)" mask="url(#mgrid)"/>')
    # top kickers
    o.append(f'<g class="fade" style="animation-delay:.15s">')
    o.append(circ(M + 5, 62, 4.5, c["emerald"]))
    o.append(circ(M + 5, 62, 4.5, c["emerald"], cls="halo"))
    o.append(txt("OPEN TO RESEARCH & SYSTEMS ROLES", M + 22, 67, MONO, 14.5, c["fg2"], track=1.5))
    o.append(txt("IEEE ICIPTM 2026  ·  FIRST AUTHOR", W - M, 67, MONO, 14.5, c["fg2"],
                 anchor="end", track=1.5))
    o.append('</g>')
    # display name + gloss sweep
    o.append('<g class="rise" style="animation-delay:.1s">')
    o.append(txt(NAME, MID, 238, SANS, 104, "url(#ink)", anchor="middle", track=2, weight="800"))
    o.append(f'<g clip-path="url(#nameclip)">'
             f'<g class="gloss">{rect(MID - 130, 130, 260, 130, "url(#gloss)")}</g></g>')
    o.append('</g>')
    o.append(line(MID - 240, 274, MID + 240, 274, "url(#ul)", 3, cap="round",
                  style="stroke-dasharray:480;stroke-dashoffset:480;"
                        "animation:draw 1.1s .5s cubic-bezier(.22,1,.36,1) forwards"))
    # role line, one <text> so it stays centred as a unit
    spans = f'<tspan fill="{c["fg3"]}">   ·   </tspan>'.join(
        f'<tspan fill="{c[k]}">{esc(s)}</tspan>' for s, k in ROLE)
    o.append(f'<text x="{MID}" y="326" text-anchor="middle" font-family="{esc(MONO)}" '
             f'font-size="18" letter-spacing="1.8" dx="-0.9" class="rise" '
             f'style="animation-delay:.42s">{spans}</text>')
    # fact chips, centred as a group
    ch, gap, pad, ig = 46, 22, 18, 11
    ws = [pad + w_sans(n, 22) + ig + w_mono(l, 13) + pad for n, l, _ in chips]
    x = MID - (sum(ws) + gap * (len(ws) - 1)) / 2
    for j, ((n, l, k), cw) in enumerate(zip(chips, ws)):
        o.append(f'<g class="rise" style="animation-delay:{.6 + .11 * j:.2f}s">')
        o.append(rect(x, 366, cw, ch, c[k], rx=23, fo=c["wash"], stroke=c[k], so=".45"))
        o.append(txt(n, x + pad, 396, SANS, 22, c[k], weight="750"))
        o.append(txt(l, x + pad + w_sans(n, 22) + ig, 395, MONO, 13, c["fg2"], track=.9))
        o.append('</g>')
        x += cw + gap
    o.append('</g></svg>')
    return "\n".join(o)

# ----------------------------------------------------------------- 2. LEDGER
LEDGER = [
    dict(title="Regime-Aware Meta-Learning for Selective Directional Trading",
         sub="Unsupervised regime clustering + a MAML-inspired classifier that abstains when unsure",
         verdict="PEER-REVIEWED", key="violet",
         fact="IEEE ICIPTM 2026  ·  DOI 10.1109/ICIPTM69057.2026.11466047"),
    dict(title="Regime-Route",
         sub="Proof-carrying execution: every routing decision emits a hash-verifiable receipt",
         verdict="FALSIFIED", key="amber",
         fact="13M+ ORDER-BOOK ROWS  ·  PAIRED COUNTERFACTUALS  ·  NO EDGE FOUND"),
    dict(title="Tensor-Forge",
         sub="A JIT tensor compiler that lowers and shape-specialises itself — no PyTorch, no CUDA",
         verdict="SHIPPED", key="emerald",
         fact="5 / 5 CTEST SUITES PASSING  ·  FULL CI"),
    dict(title="Bitcoin Alpha System",
         sub="In rebuild — walk-forward and holdout validation are still running",
         verdict="UNDER AUDIT", key="cyan",
         fact="NO RETURN FIGURE PUBLISHED UNTIL IT CLEARS"),
]
KEYS = [("PEER-REVIEWED", "violet", "external review passed"),
        ("SHIPPED", "emerald", "tested and running"),
        ("FALSIFIED", "amber", "effect not found, published anyway"),
        ("UNDER AUDIT", "cyan", "validation still running")]

def ledger(th: str) -> str:
    c, W, H, M = T[th], 1600, 580, 88
    RH, CH, Y0 = 112, 96, 96
    o = [head(W, H, "The ledger — four claims and the verdict on each")]
    o.append(css(BASE_CSS))
    o.append(rect(0, 0, W, H, c["bg"]))
    o.append(txt("THE LEDGER", M, 46, MONO, 15, c["fg2"], track=3.4, weight="600"))
    o.append(txt("EVERY CLAIM AND THE VERDICT ON IT  ·  TWO OF THE FOUR ARE NOT WINS",
                 M + 132, 46, MONO, 13, c["fg3"], track=1.2))
    o.append(txt("4 ENTRIES", W - M, 46, MONO, 13, c["fg3"], anchor="end", track=1.2))
    o.append(line(M, 66, W - M, 66, c["edge"], 1))

    for i, e in enumerate(LEDGER):
        y, hue = Y0 + i * RH, c[e["key"]]
        cy = y + CH / 2
        o.append(f'<g class="rise" style="animation-delay:{.12 + i * .13:.2f}s">')
        o.append(rect(M, y, W - 2 * M, CH, c["panel"], rx=14, stroke=c["edge"], sw=1))
        o.append(rect(M, y, 3, CH, hue, rx=1.5))                      # channel spine
        o.append(circ(M + 32, cy, 5.5, hue))
        o.append(circ(M + 32, cy, 5.5, hue, cls="halo",
                      style=f"animation-delay:{i * .5:.1f}s"))
        o.append(txt(e["title"], M + 56, cy - 6, SANS, 23, c["fg"], weight="680"))
        o.append(txt(e["sub"], M + 56, cy + 20, MONO, 13, c["fg3"], track=.2))
        pw = w_mono(e["verdict"], 13) + 30
        px = W - M - 22 - pw
        o.append(rect(px, cy - 32, pw, 27, hue, rx=13.5, fo=c["wash"], stroke=hue, so=".5"))
        o.append(txt(e["verdict"], px + pw / 2, cy - 13, MONO, 13, hue,
                     anchor="middle", track=1.3, weight="600"))
        o.append(txt(e["fact"], W - M - 22, cy + 22, MONO, 12.5, c["fg2"],
                     anchor="end", track=.5))
        o.append('</g>')

    ly = Y0 + 4 * RH + 14
    o.append(f'<g class="fade" style="animation-delay:.85s">')
    o.append(txt("KEY", M, ly, MONO, 12, c["fg3"], track=2.2))
    x = M + 44
    for name, k, meaning in KEYS:
        o.append(circ(x + 4, ly - 4, 4, c[k]))
        o.append(txt(name, x + 16, ly, MONO, 12, c[k], track=.8, weight="600"))
        x += 16 + w_mono(name, 12) + 8
        o.append(txt(meaning, x, ly, MONO, 12, c["fg3"], track=.2))
        x += w_mono(meaning, 12) + 26
    o.append('</g></svg>')
    return "\n".join(o)

# ------------------------------------------------- 3. SELECTIVE-SIGNAL TAPE
# A schematic of the paper's actual contribution: regimes are identified, and
# the classifier declines to trade inside the ones it is not confident about.
# Deterministic from a fixed seed so daily rebuilds never produce churn.
REGIMES = [(0.00, 0.34, "cyan", "REGIME A", True),
           (0.34, 0.63, "amber", "REGIME B", False),
           (0.63, 1.00, "violet", "REGIME C", True)]

def regime_at(frac: float) -> tuple[str, bool]:
    """Which regime band a horizontal position falls in, and whether it acts."""
    for lo, hi, key, _, act in REGIMES:
        if lo <= frac <= hi:
            return key, act
    return REGIMES[-1][2], REGIMES[-1][4]


def tape(th: str) -> str:
    c, W, H, M = T[th], 1600, 330, 88
    PX0, PX1, PY0, PY1 = M, W - M, 86, 250
    pw, ph = PX1 - PX0, PY1 - PY0
    rng = random.Random(11)
    n, v = 150, 0.5
    ys = []
    for i in range(n):
        v += rng.gauss(0, .052) + (.0016 if i < n * .34 else -.0022 if i < n * .63 else .0030)
        ys.append(v)
    lo, hi = min(ys), max(ys)
    TOP = PY0 + 70          # keeps the tallest marker tip clear of the regime labels
    span = PY1 - 8 - TOP
    pts = [(PX0 + i * pw / (n - 1), PY1 - 8 - (y - lo) / (hi - lo) * span)
           for i, y in enumerate(ys)]
    poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    length = sum(math.dist(pts[i], pts[i + 1]) for i in range(n - 1))

    o = [head(W, H, "Selective signal — the model declines to act when it is not confident")]
    o.append(f'''<defs>
<linearGradient id="tl" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{c['cyan']}"/><stop offset=".45" stop-color="{c['amber']}"/><stop offset="1" stop-color="{c['violet']}"/>
</linearGradient>
<linearGradient id="scan" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{c['fg']}" stop-opacity="0"/><stop offset="1" stop-color="{c['fg']}" stop-opacity=".16"/>
</linearGradient>
</defs>''')
    o.append(css(BASE_CSS + f"""
@keyframes scan{{0%{{transform:translateX(0)}}100%{{transform:translateX({pw - 90:.0f}px)}}}}
.scan{{animation:scan 9s cubic-bezier(.6,0,.4,1) infinite}}
"""))
    o.append(rect(0, 0, W, H, c["bg"]))
    o.append(txt("SELECTIVE SIGNAL", M, 44, MONO, 15, c["fg2"], track=3.4, weight="600"))
    o.append(txt("WHAT THE MODEL DOES WHEN IT IS NOT CONFIDENT", M + 208, 44, MONO, 13,
                 c["fg3"], track=1.2))
    o.append(txt("SCHEMATIC  ·  NOT BACKTEST OUTPUT", W - M, 44, MONO, 12, c["fg3"],
                 anchor="end", track=1.4))
    # regime bands
    for a, b, k, label, act in REGIMES:
        x, bw = PX0 + a * pw, (b - a) * pw
        o.append(rect(x, PY0, bw, ph, c[k], fo=c["band"]))
        o.append(line(x, PY0, x, PY1, c[k], 1, o=".35"))
        o.append(txt(label, x + 12, PY0 + 20, MONO, 12, c[k], track=1.6, weight="600"))
        o.append(txt("ACT" if act else "ABSTAIN", x + 12, PY0 + 38, MONO, 11,
                     c[k] if act else c["fg3"], track=1.4))
    o.append(line(PX0, PY1, PX1, PY1, c["edge"], 1))
    # travelling scan band, then the series drawing itself in
    o.append(f'<g class="scan">{rect(PX0, PY0, 90, ph, "url(#scan)")}</g>')
    o.append(f'<polyline points="{poly}" fill="none" stroke="url(#tl)" stroke-width="2.4" '
             f'stroke-linejoin="round" stroke-linecap="round" '
             f'style="stroke-dasharray:{length:.0f};stroke-dashoffset:{length:.0f};'
             f'animation:draw 2.1s .25s cubic-bezier(.4,0,.5,1) forwards"/>')
    # decision markers: filled arrow where it acts, hollow tick where it abstains
    for j in range(18):
        i = int((j + .5) * (n - 1) / 18)
        x, y = pts[i]
        k, act = regime_at((x - PX0) / pw)
        d = f'<g class="fade" style="animation-delay:{2.0 + j * .05:.2f}s">'
        if act:
            d += (f'<path d="M{x - 5.5:.1f},{y - 11:.1f} L{x + 5.5:.1f},{y - 11:.1f} '
                  f'L{x:.1f},{y - 21:.1f} Z" fill="{c[k]}"/>')
        else:
            d += line(x - 5, y - 15, x + 5, y - 15, c["fg3"], 2, cap="round")
        o.append(d + '</g>')
    # legend
    ly = 296
    o.append(f'<g class="fade" style="animation-delay:2.6s">')
    o.append(f'<path d="M{M + 5:.1f},{ly - 2:.1f} L{M + 16:.1f},{ly - 2:.1f} '
             f'L{M + 10.5:.1f},{ly - 12:.1f} Z" fill="{c["emerald"]}"/>')
    o.append(txt("ACT — confidence above threshold, position taken", M + 28, ly, MONO, 13,
                 c["fg2"], track=.4))
    x2 = M + 28 + w_mono("ACT — confidence above threshold, position taken", 13) + 40
    o.append(line(x2, ly - 6, x2 + 11, ly - 6, c["fg3"], 2, cap="round"))
    o.append(txt("ABSTAIN — below threshold, no position, no guess", x2 + 23, ly, MONO, 13,
                 c["fg3"], track=.4))
    o.append('</g></svg>')
    return "\n".join(o)

# -------------------------------------------------------------- 4. APPARATUS
STACK = [("SYSTEMS",  "cyan",    ["C++20", "Python", "TypeScript", "JavaScript"]),
         ("LEARNING", "violet",  ["PyTorch", "TensorFlow", "scikit-learn", "meta-learning"]),
         ("STATE",    "emerald", ["PostgreSQL", "Redis", "SQLite"]),
         ("SURFACE",  "pink",    ["Next.js", "React", "FastAPI"]),
         ("SHIPPING", "amber",   ["Docker", "GitHub Actions", "CMake / CTest"])]

def stack(th: str) -> str:
    c, W, M = T[th], 1600, 88
    RH, Y0, PH, PS, PAD, GAP = 54, 84, 32, 13.5, 14, 10
    H = Y0 + len(STACK) * RH + 26
    o = [head(W, H, "Apparatus — tools grouped by what they are for")]
    o.append(css(BASE_CSS))
    o.append(rect(0, 0, W, H, c["bg"]))
    o.append(txt("APPARATUS", M, 44, MONO, 15, c["fg2"], track=3.4, weight="600"))
    o.append(txt("GROUPED BY WHAT IT IS FOR, NOT BY LOGO AVAILABILITY", M + 130, 44, MONO,
                 13, c["fg3"], track=1.2))
    k = 0
    for i, (label, key, items) in enumerate(STACK):
        top, hue = Y0 + i * RH, c[key]
        o.append(txt(label, M, top + 22, MONO, 13, hue, track=2.2, weight="600"))
        o.append(line(M, top + 34, M + 150, top + 34, hue, 1, o=".28"))
        x = M + 176
        for it in items:
            pw = w_mono(it, PS) + PAD * 2
            o.append(f'<g class="rise" style="animation-delay:{.08 + k * .045:.2f}s">')
            o.append(rect(x, top, pw, PH, hue, rx=PH / 2, fo=c["wash"], stroke=hue, so=".38"))
            o.append(txt(it, x + pw / 2, top + 21, MONO, PS, c["fg"], anchor="middle"))
            o.append('</g>')
            x += pw + GAP
            k += 1
    o.append('</svg>')
    return "\n".join(o)

# ------------------------------------------------------------- 5. LIVE RULE
def rule(th: str) -> str:
    """A hairline divider with a light pulse travelling along it."""
    c, W, H = T[th], 1600, 10
    o = [head(W, H, "")]
    o.append(f'''<defs>
<linearGradient id="rl" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{c['violet']}" stop-opacity="0"/>
  <stop offset=".22" stop-color="{c['violet']}" stop-opacity=".55"/>
  <stop offset=".5" stop-color="{c['cyan']}" stop-opacity=".55"/>
  <stop offset=".78" stop-color="{c['pink']}" stop-opacity=".55"/>
  <stop offset="1" stop-color="{c['pink']}" stop-opacity="0"/>
</linearGradient>
<linearGradient id="pl" x1="0" y1="0" x2="1" y2="0">
  <stop offset="0" stop-color="{c['fg']}" stop-opacity="0"/>
  <stop offset=".5" stop-color="{c['fg']}" stop-opacity=".9"/>
  <stop offset="1" stop-color="{c['fg']}" stop-opacity="0"/>
</linearGradient>
</defs>''')
    o.append(css(f"""
@keyframes go{{0%{{transform:translateX(-260px)}}100%{{transform:translateX({W}px)}}}}
.p{{animation:go 6.5s linear infinite}}
"""))
    o.append(rect(0, 4, W, 1.6, "url(#rl)"))
    o.append(f'<g class="p">{rect(0, 3.4, 240, 2.6, "url(#pl)", rx=1.3)}</g>')
    o.append('</svg>')
    return "\n".join(o)

# ------------------------------------------------------------------- driver
PANELS = {"hero": hero, "ledger": ledger, "tape": tape, "stack": stack, "rule": rule}

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="assets")
    ap.add_argument("--merged", type=int, default=19,
                    help="upstream merged-PR count baked into the hero chip")
    a = ap.parse_args()
    d = pathlib.Path(a.out); d.mkdir(parents=True, exist_ok=True)
    for name, fn in PANELS.items():
        for th in T:
            svg = fn(th, a.merged) if name == "hero" else fn(th)
            p = d / f"{name}-{th}.svg"
            p.write_text(svg, encoding="utf-8")
            print(f"  {p}  {p.stat().st_size / 1024:5.1f} KB")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
