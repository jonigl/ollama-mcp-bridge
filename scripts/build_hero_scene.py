"""Generates the hero's parallax scene as inline SVG layers.

Hand-writing this is impractical: the suspender cables have to land exactly on
the main cable's bezier, the tower legs taper so every brace and flute has to
follow them, and the stiffening truss repeats across 1440px. The geometry is
solved here and the markup emitted.

No colour is written into the SVG — every layer paints with `currentColor` and
picks it up from CSS, which is what lets the same drawing read as a night scene
under the slate palette and as a daylit one under the default palette. The two
exceptions are the sun and the moon, which live in their own groups so CSS can
show one and hide the other.

Run:  python scripts/build_hero_scene.py
Output is written into docs-overrides/partials/hero-scene.html
"""

import math
import pathlib
import random

W, H = 1440, 460

# Vertical composition, from the horizon down to the viewer's own shore.
SHORE_Y = 250  # waterline on the horizon
DECK_Y = 272  # roadway surface
DECK_BOT = 286  # underside of the deck box
TRUSS_BOT = 300  # bottom chord of the stiffening truss
COLUMN_BOT = 336  # where the approach columns enter the water
PIER_BOT = 350  # where the towers do

TOWER_TOP = 24
SADDLE_Y = TOWER_TOP + 13
TOWER_X = (398, 1042)
LEG_W = 8  # thickness of one tower leg

# The tower steps inward as it rises rather than tapering smoothly, and wears a
# band at every setback. That stepping is most of what makes a suspension tower
# read as this particular bridge and not as two sticks.
TOWER_STEPS = (
    (TOWER_TOP, 88, 12.0),
    (88, 148, 14.5),
    (148, 206, 17.0),
    (206, 252, 19.0),
    (252, 314, 21.0),
    (314, PIER_BOT, 23.0),
)


def half(y):
    """Half the tower's outer width at a given height."""
    for _, bottom, hw in TOWER_STEPS:
        if y <= bottom:
            return hw
    return TOWER_STEPS[-1][2]


def cubic(p0, p1, p2, p3, t):
    """Point on a cubic bezier at t."""
    m = 1 - t
    return (
        m**3 * p0[0] + 3 * m**2 * t * p1[0] + 3 * m * t**2 * p2[0] + t**3 * p3[0],
        m**3 * p0[1] + 3 * m**2 * t * p1[1] + 3 * m * t**2 * p2[1] + t**3 * p3[1],
    )


def y_at_x(seg, x, steps=800):
    """Invert the bezier: the y where the curve crosses a given x."""
    best, best_d = None, 1e9
    for i in range(steps + 1):
        px, py = cubic(*seg, i / steps)
        d = abs(px - x)
        if d < best_d:
            best, best_d = py, d
    return best


def path(seg):
    return "C %.0f %.0f, %.0f %.0f, %.0f %.0f" % (seg[1][0], seg[1][1], seg[2][0], seg[2][1], seg[3][0], seg[3][1])


# ---------------------------------------------------------------------------
# Main cable: anchorage -> tower -> sag -> tower -> anchorage.
# The main span's control points sit *below* the deck on purpose; that is what
# pulls the curve down to graze it at mid-span.
# ---------------------------------------------------------------------------
left = ((0, 236), (120, 220), (268, 116), (TOWER_X[0], SADDLE_Y))
main = ((TOWER_X[0], SADDLE_Y), (640, 318), (800, 318), (TOWER_X[1], SADDLE_Y))
right = ((TOWER_X[1], SADDLE_Y), (1172, 116), (1320, 220), (W, 236))

cable = f"M {left[0][0]} {left[0][1]} {path(left)} {path(main)} {path(right)}"

# A second strand, a few pixels off, so the cable reads as a rope with volume
# rather than as a hairline.
cable_2 = f"M {left[0][0]} {left[0][1] + 5} {path(left)} {path(main)} {path(right)}"

# ---------------------------------------------------------------------------
# Suspenders, with the little band that clamps each one to the main cable.
# ---------------------------------------------------------------------------
susp, bands = [], []
for seg, (a, b) in ((left, (36, TOWER_X[0])), (main, TOWER_X), (right, (TOWER_X[1], W - 36))):
    x = a + 14
    while x < b - 8:
        clear = all(abs(x - tx) > half(DECK_Y) + 7 for tx in TOWER_X)
        if clear:
            y = y_at_x(seg, x)
            if DECK_Y - y > 10:
                susp.append('<line x1="%d" y1="%.1f" x2="%d" y2="%d"/>' % (x, y, x, DECK_Y))
                bands.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (x - 2.5, y, x + 2.5, y))
        x += 14

# ---------------------------------------------------------------------------
# Towers: two tapering legs, art-deco stepped braces, recessed panels between
# them, and vertical fluting down each leg.
# ---------------------------------------------------------------------------
legs, braces, panels, flutes, saddles = [], [], [], [], []
for tx in TOWER_X:
    hw_top = TOWER_STEPS[0][2]
    # The saddle the main cable rides over at the top of each tower.
    saddles.append(
        '<rect x="%.1f" y="%d" width="%.1f" height="9" rx="1.5"/>' % (tx - hw_top - 5, TOWER_TOP - 9, 2 * hw_top + 10)
    )

    for i, (y0, y1, hw) in enumerate(TOWER_STEPS):
        for side in (-1, 1):
            x = tx + side * hw if side < 0 else tx + hw - LEG_W
            legs.append('<rect x="%.1f" y="%d" width="%d" height="%d"/>' % (x, y0, LEG_W, y1 - y0))
            for f in (0.32, 0.66):
                fx = x + LEG_W * f
                flutes.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f"/>' % (fx, y0 + 5, fx, y1 - 3))

        # The band at each setback: it spans the whole tower, so it doubles as
        # the portal brace between the two legs.
        band_y = y0 - (4 if i else 0)
        braces.append('<rect x="%.1f" y="%.1f" width="%.1f" height="8" rx="1"/>' % (tx - hw - 2.5, band_y, 2 * hw + 5))

        # The recessed opening between this band and the next one down.
        inner = hw - LEG_W
        if y1 - y0 > 34 and inner > 6:
            panels.append(
                '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="2"/>'
                % (tx - inner + 3, band_y + 13, 2 * inner - 6, y1 - band_y - 18)
            )

    # A closing band at the foot, so the tower does not just stop.
    hw = TOWER_STEPS[-1][2]
    braces.append('<rect x="%.1f" y="%d" width="%.1f" height="8" rx="1"/>' % (tx - hw - 2.5, PIER_BOT - 8, 2 * hw + 5))

# Pier caissons at the foot of each tower, with a fender ring at the waterline.
piers = []
for tx in TOWER_X:
    hw = half(PIER_BOT) + 4
    piers.append('<rect x="%.1f" y="%d" width="%.1f" height="14" rx="2"/>' % (tx - hw, PIER_BOT - 8, 2 * hw))
    piers.append('<ellipse cx="%d" cy="%d" rx="%.1f" ry="5"/>' % (tx, PIER_BOT + 6, hw + 9))

# ---------------------------------------------------------------------------
# Deck: roadway, railing, stiffening truss, lamp posts, approach columns.
# ---------------------------------------------------------------------------
rail = "".join('<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, DECK_Y - 6, x, DECK_Y) for x in range(12, W, 13))

truss = []
for x in range(0, W, 22):
    truss.append('<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, DECK_BOT, x, TRUSS_BOT))
    truss.append('<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, DECK_BOT, x + 22, TRUSS_BOT))
    truss.append('<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, TRUSS_BOT, x + 22, DECK_BOT))

lamps = []
for x in range(64, W, 104):
    if all(abs(x - tx) > 40 for tx in TOWER_X):
        lamps.append('<line x1="%d" y1="%d" x2="%d" y2="%d"/>' % (x, DECK_Y - 20, x, DECK_Y - 6))
        lamps.append('<circle cx="%d" cy="%d" r="2.2"/>' % (x, DECK_Y - 22))

columns = []
for x in (64, 1376):
    columns.append('<rect x="%d" y="%d" width="6" height="%d"/>' % (x - 3, TRUSS_BOT, COLUMN_BOT - TRUSS_BOT))
    columns.append('<ellipse cx="%d" cy="%d" rx="11" ry="3.5"/>' % (x, COLUMN_BOT))

# The approach spans ride a steel arch on each side — the one the real bridge
# throws over Fort Point. Posts stand from the arch up to the deck; their feet
# are solved on the ellipse so they meet it instead of ending in mid-air.
arches, arch_posts = [], []
for x0, x1 in ((160, 340), (1100, 1280)):
    cx, rx, ry = (x0 + x1) / 2, (x1 - x0) / 2, 34
    arches.append('<path d="M %d %d A %.1f %d 0 0 1 %d %d"/>' % (x0, COLUMN_BOT, rx, ry, x1, COLUMN_BOT))
    for foot in (x0, x1):
        columns.append('<rect x="%.1f" y="%d" width="9" height="10" rx="1.5"/>' % (foot - 4.5, COLUMN_BOT - 3))
        columns.append('<ellipse cx="%d" cy="%d" rx="12" ry="3.5"/>' % (foot, COLUMN_BOT + 7))
    for k in range(1, 6):
        t = k / 6
        px = cx - rx * math.cos(math.pi * t)
        py = COLUMN_BOT - ry * math.sin(math.pi * t)
        arch_posts.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%d"/>' % (px, py, px, TRUSS_BOT))

# Traffic, for scale. Without something the size of a car on it, the deck is
# just a line and the bridge has no size at all.
random.seed(3)
cars = []
for _ in range(22):
    x = random.randint(16, W - 34)
    if any(abs(x - tx) < half(DECK_Y) + 12 for tx in TOWER_X):
        continue
    w = random.choice((7, 8, 9, 9, 10, 15, 18))
    h = 3.5 if w < 14 else 5.5
    cars.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" rx="1.2"/>' % (x, DECK_Y - h, w, h))


# Anchorages: the blocks the side spans' cables die into. Stepped, and no
# bigger than they have to be — as a single wide slab this was the one filled
# shape big enough to read as a wash laid over the landscape instead of as a
# structure standing in front of it.
def anchorage(edge, inward):
    steps = ((26, 236), (40, 246), (58, 256))
    pts = ["%d %d" % (edge, steps[0][1])]
    for i, (w, y) in enumerate(steps):
        pts.append("%d %d" % (edge + inward * w, y))
        nxt = steps[i + 1][1] if i + 1 < len(steps) else DECK_Y + 6
        pts.append("%d %d" % (edge + inward * w, nxt))
    pts.append("%d %d" % (edge, DECK_Y + 6))
    return '<path d="M %s Z"/>' % " L ".join(pts)


anchors = anchorage(0, 1) + anchorage(W, -1)

# ---------------------------------------------------------------------------
# Water: a filled bay, ripples that thin out toward the horizon, and broken
# reflections under the towers.
# ---------------------------------------------------------------------------
# Non-overlapping bands, each a step darker: stacking translucent rects on top
# of one another would compound instead of grading.
water_fill = "".join(
    '<rect x="0" y="%.1f" width="%d" height="2.6" opacity="%.3f"/>' % (SHORE_Y + i * 2.5, W, 0.72 * (i + 1) / 10)
    for i in range(10)
) + '<rect x="0" y="%.1f" width="%d" height="%.1f" opacity="0.72"/>' % (SHORE_Y + 25, W, H - SHORE_Y - 25)

random.seed(11)
ripples = []
y = SHORE_Y + 6
while y < H:
    depth = (y - SHORE_Y) / (H - SHORE_Y)
    for _ in range(int(3 + depth * 7)):
        x = random.randint(-40, W)
        ln = random.randint(18, 60) + int(depth * 80)
        ripples.append('<line x1="%d" y1="%d" x2="%d" y2="%d" opacity="%.2f"/>' % (x, y, x + ln, y, 0.25 + depth * 0.5))
    y += int(7 + depth * 9)

reflections = []
for tx in TOWER_X:
    ry = PIER_BOT + 16
    while ry < H - 10:
        f = (ry - PIER_BOT) / (H - PIER_BOT)
        hw = half(PIER_BOT) * (1 - f * 0.35)
        jitter = random.uniform(-5, 5)
        reflections.append(
            '<line x1="%.1f" y1="%d" x2="%.1f" y2="%d" opacity="%.2f"/>'
            % (tx - hw + jitter, ry, tx + hw + jitter, ry, 0.5 * (1 - f))
        )
        ry += random.randint(7, 13)


def boat(x, y, s):
    """A sailboat in silhouette: hull, mast, mainsail, jib, and a wake."""
    return (
        '<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f L %.1f %.1f Z"/>'
        % (x - s, y, x + s, y, x + 0.62 * s, y + 0.3 * s, x - 0.72 * s, y + 0.3 * s)
        + '<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f Z"/>'
        % (x + 0.02 * s, y - 1.55 * s, x + 0.78 * s, y - 0.06 * s, x + 0.02 * s, y - 0.06 * s)
        + '<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f Z"/>'
        % (x - 0.12 * s, y - 1.45 * s, x - 0.78 * s, y - 0.06 * s, x - 0.12 * s, y - 0.06 * s)
        + '<rect x="%.1f" y="%.1f" width="1.6" height="%.1f"/>' % (x - 0.1 * s, y - 1.6 * s, 1.6 * s)
    )


def wake(x, y, s):
    return "".join(
        '<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" opacity="%.2f"/>'
        % (
            x - s * (1.4 + i * 0.9),
            y + 0.4 * s + i * 3.5,
            x - s * (0.3 + i * 0.4),
            y + 0.4 * s + i * 3.5,
            0.5 - i * 0.12,
        )
        for i in range(3)
    )


boats = boat(628, 400, 13) + boat(1168, 356, 9)
boat_wakes = wake(628, 400, 13) + wake(1168, 356, 9)

# ---------------------------------------------------------------------------
# Sky: stars and a crescent for the night, sun and birds for the day.
# ---------------------------------------------------------------------------
random.seed(7)
stars = "".join(
    '<circle cx="%d" cy="%d" r="%.1f" opacity="%.2f"/>'
    % (random.randint(0, W), random.randint(8, 224), random.choice([0.9, 1.1, 1.5]), random.uniform(0.12, 0.45))
    for _ in range(78)
)

MOON = (1255, 80, 30)  # centre and radius
MOON_CUT = (1236, 60, 44)  # the disc that carves the terminator


def build_moon():
    """A waxing crescent with craters along the terminator, under a soft halo.

    Carved with a <mask> rather than by drawing arcs. A mask subtracts by
    luminance, so the same pass that cuts the terminator can also sink craters
    into the lit face at partial strength — black is cut away, grey is dimmed.
    Neither fill-rule="evenodd" (which gives the symmetric difference, not a
    subtraction) nor an explicit two-arc outline can do that.

    The halo is a radial gradient, not a flat disc: a disc has an edge, and an
    edge under a crescent reads as an eclipse rather than as glow. Its stops
    use currentColor, so the halo still follows the palette like everything
    else in the scene.
    """
    cx, cy, r = MOON
    kx, ky, kr = MOON_CUT
    ux, uy = cx - kx, cy - ky
    d = math.hypot(ux, uy)
    ux, uy = ux / d, uy / d  # from the cutter toward the lit limb

    craters = []
    for dist, deg, rad, dark in ((0.66, -30, 3.4, 0.5), (0.86, 2, 2.3, 0.4), (0.70, 30, 1.7, 0.55)):
        a = math.radians(deg)
        px = cx + r * dist * (ux * math.cos(a) - uy * math.sin(a))
        py = cy + r * dist * (ux * math.sin(a) + uy * math.cos(a))
        if math.hypot(px - kx, py - ky) <= kr:
            continue  # would fall in the shadow; nothing to show
        craters.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="#000" opacity="%.2f"/>' % (px, py, rad, dark))

    halo = (
        '<radialGradient id="omb-moon-halo">'
        '<stop offset="0%" stop-color="currentColor" stop-opacity="0.12"/>'
        '<stop offset="38%" stop-color="currentColor" stop-opacity="0.05"/>'
        '<stop offset="100%" stop-color="currentColor" stop-opacity="0"/>'
        "</radialGradient>"
    )
    disc = '<circle cx="{}" cy="{}" r="{}"'.format(cx, cy, r)
    return (
        "<defs>"
        + halo
        + '<mask id="omb-moon-face">'
        + disc
        + ' fill="#fff"/>'
        + '<circle cx="{}" cy="{}" r="{}" fill="#000"/>'.format(kx, ky, kr)
        + "".join(craters)
        + "</mask></defs>"
        + '<circle cx="{}" cy="{}" r="{:.0f}" fill="url(#omb-moon-halo)"/>'.format(cx, cy, r * 3.4)
        + disc
        + ' mask="url(#omb-moon-face)"/>'
    )


moon = build_moon()


def bird(x, y, s):
    return (
        '<path d="M %.1f %.1f q %.1f %.1f %.1f 0 q %.1f %.1f %.1f 0" fill="none" '
        'stroke="currentColor" stroke-width="1.7" stroke-linecap="round"/>'
        % (x - s, y, s * 0.5, -s * 0.75, s, s * 0.5, -s * 0.75, s)
    )


# Placed in the one patch of sky the hero's own content leaves clear.
birds = "".join(bird(x, y, s) for x, y, s in ((556, 74, 9), (592, 88, 7), (624, 62, 6), (668, 96, 7)))


def wisp(x, y, s):
    """A streak of high cloud. Night wants this and not the puffy kind: at the
    contrast the night sky allows, stacked discs read as floating bubbles."""
    parts = ((0, 0, 1.0, 0.14), (-0.86, 0.1, 0.6, 0.09), (0.84, 0.09, 0.56, 0.08), (0.26, -0.12, 0.44, 0.06))
    return "<g>%s</g>" % "".join(
        '<ellipse cx="%.1f" cy="%.1f" rx="%.1f" ry="%.1f"/>' % (x + dx * s, y + dy * s, rx * s, ry * s)
        for dx, dy, rx, ry in parts
    )


wisps = "".join(
    wisp(x, y, s) for x, y, s in ((206, 128, 92), (524, 72, 64), (858, 148, 104), (1188, 60, 74), (1404, 176, 62))
)


def cloud(x, y, s):
    """A cloud as overlapping discs sitting on a flat base — the daylight kind."""
    blobs = ((0, 0, 1.0), (-1.05, 0.24, 0.7), (1.0, 0.2, 0.76), (-0.52, -0.36, 0.6), (0.58, -0.3, 0.54))
    discs = "".join('<circle cx="%.1f" cy="%.1f" r="%.1f"/>' % (x + dx * s, y + dy * s, r * s) for dx, dy, r in blobs)
    base = '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f"/>' % (
        x - 1.72 * s,
        y,
        3.5 * s,
        1.0 * s,
        0.5 * s,
    )
    return "<g>%s%s</g>" % (discs, base)


clouds = "".join(
    cloud(x, y, s)
    for x, y, s in ((150, 86, 26), (470, 54, 19), (700, 112, 30), (980, 64, 22), (1250, 128, 24), (1390, 72, 17))
)

# ---------------------------------------------------------------------------
# Land: two distant ridges behind the bay, and the viewer's own shore in front.
# ---------------------------------------------------------------------------
hills_far = (
    "M0 214 C 130 168, 250 204, 372 186 C 470 172, 560 206, 660 198 "
    "C 790 188, 860 150, 966 172 C 1090 198, 1214 168, 1330 192 C 1382 203, 1414 200, 1440 194 "
    f"L 1440 {SHORE_Y + 4} L 0 {SHORE_Y + 4} Z"
)
hills_mid = (
    "M0 242 C 96 224, 178 248, 286 240 C 402 231, 470 206, 590 226 "
    "C 700 244, 812 224, 930 236 C 1070 250, 1180 222, 1300 238 C 1362 246, 1406 244, 1440 236 "
    f"L 1440 {SHORE_Y + 4} L 0 {SHORE_Y + 4} Z"
)
shore = (
    "M0 404 C 120 380, 214 398, 330 392 C 430 387, 500 408, 610 412 "
    "C 760 418, 900 404, 1040 400 C 1172 396, 1300 384, 1440 396 "
    f"L 1440 {H} L 0 {H} Z"
)


def conifer(x, base, h, w):
    """A silhouetted pine: a trunk under three stacked skirts."""
    parts = [
        '<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f"/>' % (x - w * 0.07, base - h * 0.16, w * 0.14, h * 0.2)
    ]
    for i in range(3):
        cy = base - h * 0.16 - h * 0.26 * i
        hw = w * 0.5 * (1 - 0.2 * i)
        parts.append('<path d="M %.1f %.1f L %.1f %.1f L %.1f %.1f Z"/>' % (x - hw, cy, x, cy - h * 0.42, x + hw, cy))
    return "".join(parts)


def rock(x, y, s):
    """A boulder: two overlapping domes so the silhouette is not a plain arc."""
    return '<path d="M %.1f %.1f Q %.1f %.1f %.1f %.1f Z"/>' % (
        x - s,
        y,
        x,
        y - 1.5 * s,
        x + s,
        y,
    ) + '<path d="M %.1f %.1f Q %.1f %.1f %.1f %.1f Z"/>' % (x + 0.4 * s, y, x + 1.05 * s, y - 0.95 * s, x + 1.7 * s, y)


def tuft(x, y, s):
    """A clump of grass: three blades fanning out."""
    return "".join(
        '<path d="M %.1f %.1f Q %.1f %.1f %.1f %.1f" fill="none" stroke="currentColor" stroke-width="1.5"/>'
        % (x, y, x + lean * s * 0.3, y - s * 0.6, x + lean * s * 0.75, y - s)
        for lean in (-1, 0, 1)
    )


rocks = rock(212, 404, 9) + rock(404, 412, 7) + rock(1196, 400, 8) + rock(1424, 404, 11)
tufts = "".join(
    tuft(x, y, s) for x, y, s in ((246, 404, 11), (268, 406, 8), (352, 410, 9), (1160, 400, 10), (1232, 402, 8))
)

trees = "".join(
    conifer(x, b, h, w)
    for x, b, h, w in (
        (44, 400, 44, 23),
        (72, 404, 58, 28),
        (104, 399, 36, 19),
        (132, 402, 68, 32),
        (172, 406, 30, 16),
        (196, 403, 47, 24),
        (1258, 394, 40, 21),
        (1292, 391, 62, 29),
        (1330, 396, 33, 18),
        (1364, 393, 52, 26),
        (1402, 398, 38, 20),
    )
)

html = f"""{{# Generated by scripts/build_hero_scene.py — do not edit by hand. #}}
<div class="omb-scene omb-scene--sky" data-parallax="0.40">
  <svg viewBox="0 0 {W} 250" preserveAspectRatio="xMidYMin slice" fill="currentColor">
    <g class="omb-scene__night">
      {stars}
      <g class="omb-scene__moon">{moon}</g>
    </g>
    <g class="omb-scene__day">
      <g class="omb-scene__sun" opacity="0.8">
        <circle cx="1255" cy="80" r="34"/>
        <circle cx="1255" cy="80" r="54" opacity="0.3"/>
        <circle cx="1255" cy="80" r="78" opacity="0.14"/>
      </g>
      <g opacity="0.5">{birds}</g>
    </g>
  </svg>
</div>

<div class="omb-scene omb-scene--clouds" data-parallax="0.32">
  <svg viewBox="0 0 {W} 250" preserveAspectRatio="xMidYMin slice" fill="currentColor">
    <g class="omb-scene__night">{wisps}</g>
    <g class="omb-scene__day">{clouds}</g>
  </svg>
</div>

<div class="omb-scene omb-scene--hills-far" data-parallax="0.26">
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" fill="currentColor">
    <path d="{hills_far}"/>
  </svg>
</div>

<div class="omb-scene omb-scene--hills-mid" data-parallax="0.20">
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" fill="currentColor">
    <path d="{hills_mid}"/>
  </svg>
</div>

<div class="omb-scene omb-scene--water" data-parallax="0.16">
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" fill="currentColor">
    {water_fill}
    <g stroke="currentColor" stroke-width="1.4" stroke-linecap="round">{''.join(reflections)}</g>
    <g stroke="currentColor" stroke-width="1.1" stroke-linecap="round">{''.join(ripples)}</g>
    <g stroke="currentColor" stroke-width="1.3" stroke-linecap="round">{boat_wakes}</g>
    <g opacity="1">{boats}</g>
  </svg>
</div>

<div class="omb-scene omb-scene--bridge" data-parallax="0.12">
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice"
       fill="currentColor" stroke="currentColor"
       stroke-linecap="round" stroke-linejoin="round">
    <g fill="none" stroke-width="1.3" opacity="0.72">{''.join(susp)}</g>
    <g fill="none" stroke-width="2.6" opacity="0.8">{''.join(bands)}</g>
    <g fill="none" stroke-width="3.4"><path d="{cable}"/></g>
    <g fill="none" stroke-width="1.6" opacity="0.5"><path d="{cable_2}"/></g>
    <g stroke="none" opacity="0.9">{anchors}</g>
    <g stroke="none">{''.join(legs)}{''.join(braces)}{''.join(saddles)}</g>
    <g fill="none" stroke-width="1" opacity="0.45">{''.join(panels)}</g>
    <g fill="none" stroke-width="0.9" opacity="0.4">{''.join(flutes)}</g>
    <g stroke="none" opacity="0.85">{''.join(columns)}{''.join(piers)}</g>
    <g fill="none" stroke-width="2.2" opacity="0.8">{''.join(arches)}</g>
    <g fill="none" stroke-width="1.1" opacity="0.6">{''.join(arch_posts)}</g>
    <g fill="none" stroke-width="1" opacity="0.5">{''.join(truss)}</g>
    <g fill="none" stroke-width="1.2" opacity="0.6">{rail}</g>
    <g fill="none" stroke-width="1.4" opacity="0.75">{''.join(lamps)}</g>
    <rect x="0" y="{DECK_Y}" width="{W}" height="4"/>
    <g stroke="none" opacity="0.9">{''.join(cars)}</g>
    <g fill="none" stroke-width="1.6" opacity="0.7">
      <line x1="0" y1="{DECK_BOT}" x2="{W}" y2="{DECK_BOT}"/>
      <line x1="0" y1="{TRUSS_BOT}" x2="{W}" y2="{TRUSS_BOT}"/>
    </g>
  </svg>
</div>

<div class="omb-scene omb-scene--shore" data-parallax="0.03">
  <svg viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMax slice" fill="currentColor">
    <path d="{shore}"/>
    {rocks}
    {tufts}
    {trees}
  </svg>
</div>
"""

out = pathlib.Path("docs-overrides/partials/hero-scene.html")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(
    "wrote %s — %d suspenders, %d truss members, %d cars, %d stars, %d ripples"
    % (out, len(susp), len(truss), len(cars), stars.count("<circle"), len(ripples))
)
