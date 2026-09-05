"""Geometry + integrity check on the rendered plates. Standard library only.

There is no browser in the build, so this re-measures every <text> and <rect>
straight out of the emitted XML -- accumulating translate() from ancestor groups,
which the first pass got wrong -- and looks for overlap, overflow and dangling
references. It exists because version one of this page shipped with 6.6px type:
the plates were drawn on a 1600px canvas and embedded at width=100% in an 880px
column. Nobody caught it because nothing checked. The floor below is that check.

Run from the repo root. Exits non-zero on any finding, so CI fails loudly rather
than publishing an unreadable page.
"""
import re, sys, math, shutil, itertools, pathlib, xml.etree.ElementTree as ET

# Import render.py from source, never from a cached .pyc. CPython treats a cache
# as valid when the source's (mtime_seconds, size) match the header, and an edit
# that swaps one hex literal for another -- #626C78 for #768290, say -- changes
# neither, so a same-second edit is invisible to that test. This bit during
# development: the verifier read the palette from stale bytecode and reported a
# colour that was no longer in the file. The dangerous direction is the mirror of
# that -- render draws with a new bad palette while the check reads an old good
# one and passes. A geometry check that can validate something other than what
# was drawn is not a check, so the cache is removed rather than trusted.
sys.dont_write_bytecode = True
shutil.rmtree(pathlib.Path(__file__).with_name("__pycache__"), ignore_errors=True)
sys.path.insert(0, "build")
import render as R

NS = "{http://www.w3.org/2000/svg}"
TR = re.compile(r"translate\(\s*(-?[\d.]+)[ ,]+(-?[\d.]+)\s*\)")


def walk(node, dx=0.0, dy=0.0, out=None):
    """Flatten the tree into absolute-coordinate leaves."""
    out = [] if out is None else out
    for e in node:
        ex, ey = dx, dy
        m = TR.search(e.get("transform", "") or "")
        if m:
            ex, ey = dx + float(m.group(1)), dy + float(m.group(2))
        if e.tag in (f"{NS}text", f"{NS}rect", f"{NS}circle", f"{NS}line"):
            out.append((e, ex, ey))
        walk(e, ex, ey, out)
    return out


bad = []

# ---- palette: WCAG AA on every ground, before a single pixel is measured ----
# Checked at the palette level rather than per element: if every foreground
# clears 4.5:1 against bg AND panel AND strip, then no placement can be wrong.
# Pill labels sit on a 12% tint of their own colour over one of those grounds,
# which moves the ratio by a hair, so the ground itself is the honest test.
INK = ("fg", "fg2", "fg3", "amber", "mint", "rose", "cyan", "violet")
GROUND = ("bg", "panel", "strip")
SEMANTIC = ("amber", "mint", "rose", "cyan", "violet")
NEUTRAL = ("fg", "fg2", "fg3")
AA = 4.5
# Lab dE floor for "these two carry different meanings". Set from the two cases
# there is evidence for, not from a round number: light cyan at #0A78A0 sat 25.3
# dE from fg2 and flattened its KPI tile, so the floor has to be above that; dark
# cyan sits 33.0 from dark fg2 and reads unmistakably as cyan in a real render, so
# the floor has to be below that. 30 is the only decade in between. Every value in
# the shipped table is 40 or more, so this trips on a regression, not on a nudge.
DE = 30.0


def _lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + .05) / (min(la, lb) + .05)


def _lab(h):
    """sRGB hex -> CIE L*a*b* under D65, so colour distance is perceptual."""
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in c]
    X = (.4124 * c[0] + .3576 * c[1] + .1805 * c[2]) / .95047
    Y = (.2126 * c[0] + .7152 * c[1] + .0722 * c[2])
    Z = (.0193 * c[0] + .1192 * c[1] + .9505 * c[2]) / 1.08883
    f = lambda u: u ** (1 / 3) if u > (6 / 29) ** 3 else u / (3 * (6 / 29) ** 2) + 4 / 29
    fx, fy, fz = f(X), f(Y), f(Z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def dist(a, b):
    return math.dist(_lab(a), _lab(b))


for th, t in R.T.items():
    for k in INK:
        for g in GROUND:
            if (r := contrast(t[k], t[g])) < AA:
                bad.append(f"{th}: {k} {t[k]} on {g} {t[g]} is {r:.2f}:1, under {AA}")
    if (r := contrast(t["bg"], t["amber"])) < AA:      # panel-number square
        bad.append(f"{th}: bg on amber is {r:.2f}:1, under {AA}")
    # Colour is load-bearing on this page: it is what says which project a row
    # belongs to and whether a regime was traded. Two data colours converging is
    # therefore a correctness bug, not a matter of taste, and it is invisible to
    # every contrast check above -- both members can clear AA and still be the
    # same colour to a reader. Semantic inks must part from each other and from
    # the neutral prose greys they are printed next to.
    for a, b in itertools.combinations(SEMANTIC, 2):
        if (d := dist(t[a], t[b])) < DE:
            bad.append(f"{th}: {a} {t[a]} and {b} {t[b]} are {d:.1f} dE apart, "
                       f"under {DE} -- two data colours reading as one")
    for s in SEMANTIC:
        for n in NEUTRAL:
            if (d := dist(t[s], t[n])) < DE:
                bad.append(f"{th}: {s} {t[s]} is {d:.1f} dE from {n} {t[n]}, under "
                           f"{DE} -- a value would read as ordinary prose")

for p in sorted(pathlib.Path("assets").glob("*.svg")):
    src = p.read_text()
    try:
        root = ET.fromstring(src)
    except ET.ParseError as e:
        bad.append(f"{p.name}: XML PARSE {e}"); continue
    Wv, Hv = float(root.get("width")), float(root.get("height"))

    scrub = re.sub(r'xmlns(:\w+)?="[^"]*"', "", src)
    for tok in ("<script", "onload", "onclick", "onerror", "http://", "https://",
                "xlink:href", "<foreignObject", "<image", "@import"):
        if tok in scrub:
            bad.append(f"{p.name}: external/script token {tok!r}")
    ids = set(re.findall(r'\bid="([^"]+)"', src))
    for ref in set(re.findall(r"url\(#([^)]+)\)", src)):
        if ref not in ids:
            bad.append(f"{p.name}: url(#{ref}) does not resolve")
    decl = set(re.findall(r"\.([A-Za-z][\w-]*)\s*[,{]", src))
    for cls in set(w for a in re.findall(r'class="([^"]+)"', src) for w in a.split()):
        if cls not in decl:
            bad.append(f"{p.name}: class .{cls} used but never declared")
    # `animation:none` is how the reduced-motion block switches motion off, and
    # `none` is a CSS-wide keyword, not a keyframe name. Reading it as one made
    # this check fail on all 14 plates the moment that block was added -- a false
    # positive, and the noisiest kind, because it fires everywhere at once.
    for kf in set(re.findall(r"animation:\s*([\w-]+)", src)) - {"none", "inherit",
                                                               "initial", "unset"}:
        if f"@keyframes {kf}" not in src:
            bad.append(f"{p.name}: @keyframes {kf} missing")
    # Motion on this page is decoration, so a reader who has asked the OS for
    # less of it must get the finished frame -- not the empty one .r and .f start
    # from. Every plate animates something, so every plate needs the escape.
    if "animation" in src and "prefers-reduced-motion" not in src:
        bad.append(f"{p.name}: animates but has no prefers-reduced-motion block")

    leaves, rows, ntext, inks, boxes = walk(root), {}, 0, [], []
    for e, dx, dy in leaves:
        if e.tag == f"{NS}text":
            ntext += 1
            s = "".join(e.itertext())
            size = float(e.get("font-size", 13))
            track = float(e.get("letter-spacing", 0) or 0)
            fam = e.get("font-family") or ""
            mono = "Mono" in fam or "ui-monospace" in fam
            wid = (R.w_mono if mono else (lambda s,z,k=0: len(s)*.55*z))(s, size, track)
            x, y = float(e.get("x")) + dx, float(e.get("y")) + dy
            x0 = x - wid if e.get("text-anchor") == "end" else x
            if size < 9:
                bad.append(f"{p.name}: {size}px is under the 9px floor: {s[:28]!r}")
            if x0 < 0 or x0 + wid > Wv + .6:
                bad.append(f"{p.name}: text overflows [{x0:.0f}..{x0+wid:.0f}] of "
                           f"{Wv:.0f}: {s[:34]!r}")
            # Inside the canvas is not the same as inside the margin. Every plate
            # sets its type between PAD and X1, and a string that runs past X1 is
            # still "in bounds" by the test above -- it just reads as touching the
            # frame. Rasterising the plates turned up three of these in the
            # blotter, all right-aligned evidence strings that had quietly grown
            # past the column. Only text is held to the margin; the panel-header
            # strip and the frame are full-bleed rects on purpose.
            elif x0 < R.PAD - .6 or x0 + wid > R.X1 + .6:
                bad.append(f"{p.name}: text breaks the {R.PAD}px margin "
                           f"[{x0:.0f}..{x0+wid:.0f}] of {R.PAD}..{R.X1:.0f}: "
                           f"{s[:34]!r}")
            if y > Hv or y - size < -1:
                bad.append(f"{p.name}: baseline {y} outside 0..{Hv}: {s[:28]!r}")
            rows.setdefault(round(y / 7), []).append((x0, x0 + wid, s))
            # Ink box, for the border-crossing test below. 0.72em above the
            # baseline is cap height and 0.18em below is the descender, which is
            # the box a reader sees rather than the full em square.
            inks.append((x0, y - .72 * size, x0 + wid, y + .18 * size, s))
        elif e.tag == f"{NS}rect":
            x, y = float(e.get("x")) + dx, float(e.get("y")) + dy
            w, h = float(e.get("width")), float(e.get("height"))
            if x < -.6 or y < -.6 or x + w > Wv + .6 or y + h > Hv + .6:
                bad.append(f"{p.name}: rect {x:.0f},{y:.0f} {w:.0f}x{h:.0f} "
                           f"escapes {Wv:.0f}x{Hv:.0f}")
            if e.get("stroke") and e.get("stroke") != "none":
                boxes.append((x, y, x + w, y + h))
    # A stroked rect either contains a string or stands clear of it by a visible
    # margin. Anything in between means a border line is drawn along the glyphs.
    # This is the one geometric defect the same-baseline check above cannot see --
    # it compares text against text, and a pill's outline is a rect.
    #
    # Rasterising the blotter is what turned it up: the verdict pill and the
    # evidence string under it were both anchored to X1, the pill's bottom edge
    # sat at row+27 and the evidence cap height reached row+26.8. Two tenths of a
    # pixel of clearance in a 0.600em model -- and a plainly visible cyan rule
    # through "VALIDATION CLEARS" once a real font renders it, because every
    # fallback in the stack is taller in the cap than the model assumes.
    #
    # So the threshold is a design rule, not a rounding allowance: a border and a
    # glyph get 2px of daylight or the build fails. Written as slack (.5px, say)
    # this check passes on the very defect it exists to catch -- which it did, on
    # the first run, before the number was set from the fault instead of from
    # habit.
    GAP = 2.0
    for bx0, by0, bx1, by1 in boxes:
        for ix0, iy0, ix1, iy1, s in inks:
            if ix0 >= bx1 - GAP or ix1 <= bx0 + GAP:
                continue                                   # clear left or right
            if iy0 >= by1 + GAP or iy1 <= by0 - GAP:
                continue                                   # clear above or below
            if bx0 - .6 <= ix0 and ix1 <= bx1 + .6 and by0 - .6 <= iy0 and iy1 <= by1 + .6:
                continue                                   # contained: fine
            bad.append(f"{p.name}: border [{bx0:.0f},{by0:.0f}..{bx1:.0f},"
                       f"{by1:.0f}] comes within {GAP}px of {s[:26]!r} "
                       f"[{ix0:.0f},{iy0:.1f}..{ix1:.0f},{iy1:.1f}]")
    for _, items in rows.items():
        items.sort()
        for (a0, a1, sa), (b0, b1, sb) in zip(items, items[1:]):
            if b0 < a1 - .6:
                bad.append(f"{p.name}: COLLIDE {sa[:24]!r} ends {a1:.0f} / "
                           f"{sb[:24]!r} starts {b0:.0f}")
    print(f"  {p.name:22s} {Wv:.0f}x{Hv:.0f}  texts={ntext:3d}")

# ---- README <-> assets, both directions ------------------------------------
# This is the check for the failure the reader actually notices. Version one of
# this page shipped three <img> tags whose sources 404'd, and nothing in the
# build knew: the plates were fine, the references were not. A broken <picture>
# on GitHub renders as alt text or as nothing at all, so the page silently loses
# a panel. Both directions matter -- a reference with no file is a hole in the
# page, and a file with no reference is a plate nobody will ever see.
readme = pathlib.Path("README.md").read_text()
refs = {m for m in re.findall(r'(?:src|srcset)="(assets/[^"]+)"', readme)}
have = {f"assets/{p.name}" for p in pathlib.Path("assets").glob("*.svg")}
want = {f"assets/{n}-{th}.svg" for n in R.PLATES for th in R.T}
for r in sorted(refs - have):
    bad.append(f"README.md references {r}, which is not in assets/")
for f in sorted(have - refs):
    bad.append(f"{f} is rendered but never referenced by README.md")
for f in sorted(want - have):
    bad.append(f"render.PLATES declares {f}, which was not rendered")
print(f"  README.md              {len(refs)} image refs, all present" if not
      (refs - have) else f"  README.md              {len(refs)} image refs")

print()
if bad:
    print(f"{len(bad)} PROBLEM(S):")
    for b in bad:
        print("  -", b)
    sys.exit(1)
print("clean: AA on every ground, data colours separable, in bounds, no baseline "
      "collisions, 2px between every border and every glyph,\n"
      "       no dangling url(#), no external fetches, nothing under 9px, "
      "reduced-motion escape on every animated plate,\n"
      "       README and assets agree in both directions")
