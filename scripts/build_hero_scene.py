"""Generates the hero's parallax scene: inline SVG layers, plus the handful of
small HTML elements that move.

Hand-writing this is impractical: the suspender cables have to land exactly on
the main cable's bezier, the tower legs step inward so every brace and flute
has to follow them, the stiffening truss repeats across 1440px, and the traffic
strips have to tile seamlessly. The geometry is solved here and the markup
emitted.

Two rules shape the output:

- No colour is written into the drawing. Every shape is painted through a class
  or `currentColor`, and the stylesheet decides what those are. That is what
  lets the same geometry read as a night scene under the slate palette and a
  daylit one under the default palette. Things that only exist at one time of
  day carry `omb-n` (night) or `omb-d` (day) and CSS hides the other.

- Nothing inside an SVG animates. Browsers repaint an SVG whenever anything in
  it changes, and these SVGs are 1440px wide. Everything alive — traffic,
  beacons, twinkling, water, boats, fog, birds — is its own small HTML element
  animating only `transform` or `opacity`, which the compositor moves without
  repainting anything. Those elements are placed in percentages of the layer,
  so they stay pinned to the drawing at any width.

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

# The moon (or the sun) sits low, left of centre, where it shows below the
# hero's text column on a desktop and inside the frame on a phone, and where
# the main cable and its suspenders cross in front of it.
ORB = (600, 192)

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


def n(v):
    """A compact number: one decimal at most, and none when it is whole."""
    s = "%.1f" % v
    return s[:-2] if s.endswith(".0") else s


def px(x):
    return n(x / W * 100) + "%"


def py(y):
    return n(y / H * 100) + "%"


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
        cx, cy = cubic(*seg, i / steps)
        d = abs(cx - x)
        if d < best_d:
            best, best_d = cy, d
    return best


def path(seg):
    return "C %s %s, %s %s, %s %s" % tuple(n(v) for p in seg[1:] for v in p)


class Ridge:
    """A chain of cubic segments: its SVG path, and its height at any x, so
    that trees and grass can be stood on it."""

    def __init__(self, start, segs):
        self.d = "M%s %s" % (n(start[0]), n(start[1])) + "".join(
            "C%s %s %s %s %s %s" % tuple(n(v) for p in seg for v in p) for seg in segs
        )
        pts, p0 = [], start
        for seg in segs:
            pts += [cubic(p0, *seg, i / 40) for i in range(40)]
            p0 = seg[-1]
        self.pts = pts + [p0]

    def y(self, x):
        for (x0, y0), (x1, y1) in zip(self.pts, self.pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / ((x1 - x0) or 1)
        return self.pts[-1][1] if x > self.pts[-1][0] else self.pts[0][1]


def dots(points, width):
    """Pinpoints as zero-length round-capped strokes: a star or a lit window in
    a dozen bytes instead of a whole <circle>."""
    return '<path d="%s" stroke-width="%s"/>' % ("".join("M%s %sh0" % (n(x), n(y)) for x, y in points), width)


def svg(inner, cls="", view=(0, 0, W, H), align="xMidYMax slice"):
    """A scene SVG. `overflow: visible` lets shapes bleed past the viewBox, so
    that a layer shifted by the parallax never uncovers its own edge."""
    return '<svg%s viewBox="%s" preserveAspectRatio="%s" overflow="visible" fill="currentColor">%s</svg>' % (
        ' class="%s"' % cls if cls else "",
        " ".join(n(v) for v in view),
        align,
        inner,
    )


def at(x, y):
    return "left:%s;top:%s" % (px(x), py(y))


# ===========================================================================
# The bridge
# ===========================================================================

# Main cable: anchorage -> tower -> sag -> tower -> anchorage. The main span's
# control points sit *below* the deck on purpose; that is what pulls the curve
# down to graze it at mid-span.
left = ((0, 236), (120, 220), (268, 116), (TOWER_X[0], SADDLE_Y))
main = ((TOWER_X[0], SADDLE_Y), (640, 318), (800, 318), (TOWER_X[1], SADDLE_Y))
right = ((TOWER_X[1], SADDLE_Y), (1172, 116), (1320, 220), (W, 236))
SPANS = ((left, (0, TOWER_X[0])), (main, TOWER_X), (right, (TOWER_X[1], W)))


def cable_at(x):
    for seg, (a, b) in SPANS:
        if a <= x <= b:
            return y_at_x(seg, x)
    return None


cable = "M %d %d %s %s %s" % (left[0][0], left[0][1], path(left), path(main), path(right))
# A second strand a few pixels off, so the cable reads as a rope with volume
# rather than as a hairline.
cable_2 = "M %d %d %s %s %s" % (left[0][0], left[0][1] + 5, path(left), path(main), path(right))

# Suspenders, with the little band that clamps each one to the main cable.
susp, susp_2, bands = [], [], []
for seg, (a, b) in ((left, (36, TOWER_X[0])), (main, TOWER_X), (right, (TOWER_X[1], W - 36))):
    x = a + 14
    while x < b - 8:
        if all(abs(x - tx) > half(DECK_Y) + 7 for tx in TOWER_X):
            y = y_at_x(seg, x)
            if DECK_Y - y > 10:
                susp.append("M%d %sV%d" % (x, n(y), DECK_Y))
                susp_2.append("M%s %sV%d" % (n(x + 1.8), n(y + 0.8), DECK_Y))
                bands.append("M%s %sH%s" % (n(x - 2.5), n(y), n(x + 2.5)))
        x += 14

# Towers: stepped legs, a band at every setback, recessed panels between them,
# fluting down each leg, and the inner third of every leg in shade — the light
# comes from the orb on the left, so the right-hand faces turn away from it.
legs, lit, shade, braces, panels, flutes, saddles, xbrace = [], [], [], [], [], [], [], []
for tx in TOWER_X:
    hw_top = TOWER_STEPS[0][2]
    saddles.append(
        '<rect x="%s" y="%d" width="%s" height="9" rx="1.5"/>' % (n(tx - hw_top - 5), TOWER_TOP - 9, n(2 * hw_top + 10))
    )
    for i, (y0, y1, hw) in enumerate(TOWER_STEPS):
        for side in (-1, 1):
            x = tx - hw if side < 0 else tx + hw - LEG_W
            legs.append('<rect x="%s" y="%d" width="%d" height="%d"/>' % (n(x), y0, LEG_W, y1 - y0))
            lit.append('<rect x="%s" y="%d" width="1.6" height="%d"/>' % (n(x), y0, y1 - y0))
            shade.append('<rect x="%s" y="%d" width="3" height="%d"/>' % (n(x + LEG_W - 3), y0, y1 - y0))
            for f in (0.32, 0.66):
                fx = x + LEG_W * f
                flutes.append("M%s %dV%d" % (n(fx), y0 + 5, y1 - 3))
        band_y = y0 - (4 if i else 0)
        braces.append('<rect x="%s" y="%d" width="%s" height="8" rx="1"/>' % (n(tx - hw - 2.5), band_y, n(2 * hw + 5)))
        inner = hw - LEG_W
        if y1 - y0 > 34 and inner > 6 and y0 < DECK_Y - 20:
            panels.append(
                '<rect x="%s" y="%d" width="%s" height="%d" rx="2"/>'
                % (n(tx - inner + 3), band_y + 13, n(2 * inner - 6), y1 - band_y - 18)
            )
    hw = TOWER_STEPS[-1][2]
    braces.append(
        '<rect x="%s" y="%d" width="%s" height="8" rx="1"/>' % (n(tx - hw - 2.5), PIER_BOT - 8, n(2 * hw + 5))
    )
    # Under the deck the portal is braced with an X, as on the real towers.
    top, bot = DECK_BOT + 3, PIER_BOT - 10
    a, b = half(top) - LEG_W, half(bot) - LEG_W
    xbrace.append(
        "M%s %dL%s %dM%s %dL%s %dM%s %sH%s"
        % (n(tx - a), top, n(tx + b), bot, n(tx + a), top, n(tx - b), bot, n(tx - b), n((top + bot) / 2), n(tx + b))
    )

piers = []
for tx in TOWER_X:
    hw = half(PIER_BOT) + 4
    piers.append('<rect x="%s" y="%d" width="%s" height="14" rx="2"/>' % (n(tx - hw), PIER_BOT - 8, n(2 * hw)))
    piers.append('<ellipse cx="%d" cy="%d" rx="%s" ry="5"/>' % (tx, PIER_BOT + 6, n(hw + 9)))

rail = "".join("M%d %dV%d" % (x, DECK_Y - 6, DECK_Y) for x in range(12, W, 13))

truss = "".join(
    "M%d %dV%dM%d %dL%d %dM%d %dL%d %d"
    % (x, DECK_BOT, TRUSS_BOT, x, DECK_BOT, x + 22, TRUSS_BOT, x, TRUSS_BOT, x + 22, DECK_BOT)
    for x in range(0, W, 22)
)

LAMPS = [x for x in range(64, W, 104) if all(abs(x - tx) > 40 for tx in TOWER_X)]
lamp_posts = "".join("M%d %dV%d" % (x, DECK_Y - 20, DECK_Y - 6) for x in LAMPS)
lamp_heads = "".join('<circle cx="%d" cy="%d" r="2.2"/>' % (x, DECK_Y - 22) for x in LAMPS)
lamp_halos = "".join('<circle cx="%d" cy="%d" r="9"/>' % (x, DECK_Y - 22) for x in LAMPS)

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
    arches.append("M%d %dA%s %d 0 0 1 %d %d" % (x0, COLUMN_BOT, n(rx), ry, x1, COLUMN_BOT))
    for foot in (x0, x1):
        columns.append('<rect x="%s" y="%d" width="9" height="10" rx="1.5"/>' % (n(foot - 4.5), COLUMN_BOT - 3))
        columns.append('<ellipse cx="%d" cy="%d" rx="12" ry="3.5"/>' % (foot, COLUMN_BOT + 7))
    for k in range(1, 6):
        t = k / 6
        ax = cx - rx * math.cos(math.pi * t)
        ay = COLUMN_BOT - ry * math.sin(math.pi * t)
        arch_posts.append("M%s %sV%d" % (n(ax), n(ay), TRUSS_BOT))


# Anchorages: the blocks the side spans' cables die into. Stepped, and no
# bigger than they have to be.
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

bridge_svg = svg(
    "<defs>"
    '<radialGradient id="omb-halo">'
    '<stop offset="0" class="omb-lamp-stop" stop-opacity="0.75"/>'
    '<stop offset="0.35" class="omb-lamp-stop" stop-opacity="0.22"/>'
    '<stop offset="1" class="omb-lamp-stop" stop-opacity="0"/>'
    "</radialGradient>"
    "</defs>"
    '<g fill="none" stroke="currentColor" stroke-linecap="round">'
    '<path d="%s" stroke-width="1.3" opacity="0.72"/>'
    '<path d="%s" stroke-width="0.9" opacity="0.4"/>'
    '<path d="%s" stroke-width="2.6" opacity="0.85"/>'
    '<path d="%s" stroke-width="3.4"/>'
    '<path d="%s" stroke-width="1.6" opacity="0.5"/>'
    '<path class="omb-bridge__lit" d="%s" stroke-width="1" opacity="0.8" transform="translate(0 -1.4)"/>'
    "</g>"
    "%s"
    "<g>%s</g>"
    '<g class="omb-bridge__lit">%s</g>'
    "<g>%s%s</g>"
    '<g class="omb-bridge__shade">%s</g>'
    '<g fill="none" stroke="currentColor" stroke-width="1" opacity="0.45">%s</g>'
    '<path class="omb-bridge__shade" d="%s" fill="none" stroke="currentColor" stroke-width="0.9" opacity="0.7"/>'
    '<path class="omb-bridge__shade" d="%s" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/>'
    "<g>%s%s</g>"
    '<g fill="none" stroke="currentColor" stroke-linecap="round">'
    '<path d="%s" stroke-width="2.2" opacity="0.85"/>'
    '<path d="%s" stroke-width="1.1" opacity="0.6"/>'
    '<path class="omb-bridge__shade" d="%s" stroke-width="1" opacity="0.8"/>'
    '<path d="%s" stroke-width="1.2" opacity="0.7"/>'
    '<path d="%s" stroke-width="1.4" opacity="0.8"/>'
    "</g>"
    '<rect x="-40" y="%d" width="%d" height="4"/>'
    '<rect class="omb-bridge__shade" x="-40" y="%d" width="%d" height="%d"/>'
    '<path class="omb-bridge__lit" d="M-40 %sH%d" stroke="currentColor" stroke-width="1.1"/>'
    '<g fill="none" stroke="currentColor" stroke-width="1.6" opacity="0.75">'
    '<path d="M-40 %dH%d M-40 %dH%d"/>'
    "</g>"
    '<g class="omb-bridge__lamp">%s</g>'
    '<g class="omb-n" fill="url(#omb-halo)">%s</g>'
    % (
        "".join(susp),
        "".join(susp_2),
        "".join(bands),
        cable,
        cable_2,
        cable,
        '<g opacity="0.95">%s</g>' % anchors,
        "".join(legs),
        "".join(lit),
        "".join(braces),
        "".join(saddles),
        "".join(shade),
        "".join(panels),
        "".join(flutes),
        "".join(xbrace),
        "".join(columns),
        "".join(piers),
        "".join(arches),
        "".join(arch_posts),
        truss,
        rail,
        lamp_posts,
        DECK_Y,
        W + 80,
        DECK_Y + 4,
        W + 80,
        DECK_BOT - DECK_Y - 4,
        n(DECK_Y + 0.6),
        W + 40,
        DECK_BOT,
        W + 40,
        TRUSS_BOT,
        W + 40,
        lamp_heads,
        lamp_halos,
    )
)


# ---------------------------------------------------------------------------
# Traffic. Each lane is a strip twice the scene's width holding the same cars
# twice over, so sliding it by half its own width loops without a seam. It sits
# *behind* the bridge drawing: the railing crosses in front of the cars, and
# they disappear through the tower portals and behind the anchorages.
# ---------------------------------------------------------------------------
LANE_TOP, LANE_H = DECK_Y - 8, 8


def lane(seed, heading, y):
    random.seed(seed)
    cars, x = [], random.uniform(0, 30)
    while x < W - 40:
        w = random.choice((8, 9, 9, 10, 10, 11, 17, 20))
        cars.append((x, w, random.randint(0, 4)))
        x += w + random.uniform(16, 120)
    bodies, heads, tails = [], [], []
    for off in (0, W):
        for x, w, tint in cars:
            x += off
            h = 3.6 if w < 14 else 5.4
            bodies.append(
                '<rect class="omb-car omb-car--%d" x="%s" y="%s" width="%d" height="%s" rx="1.2"/>'
                % (tint, n(x), n(y - h), w, n(h))
            )
            front, back = (x + w, x) if heading > 0 else (x, x + w)
            heads.append('<circle cx="%s" cy="%s" r="1.2"/>' % (n(front), n(y - 1.6)))
            tails.append('<circle cx="%s" cy="%s" r="1"/>' % (n(back), n(y - 1.6)))
    glow = lambda pts, r: pts.replace('r="1.2"', 'r="%s"' % r).replace('r="1"', 'r="%s"' % r)  # noqa: E731
    return svg(
        "%s"
        '<g class="omb-n omb-car__head" opacity="0.28">%s</g><g class="omb-n omb-car__head">%s</g>'
        '<g class="omb-n omb-car__tail" opacity="0.3">%s</g><g class="omb-n omb-car__tail">%s</g>'
        % ("".join(bodies), glow("".join(heads), 3.4), "".join(heads), glow("".join(tails), 3), "".join(tails)),
        view=(0, LANE_TOP, 2 * W, LANE_H),
        align="xMinYMin meet",
    )


traffic = (
    '<div class="omb-lane omb-lane--west omb-amb" style="top:%s">%s</div>'
    '<div class="omb-lane omb-lane--east omb-amb" style="top:%s">%s</div>'
    % (py(LANE_TOP - 1.2), lane(21, -1, DECK_Y - 1.2), py(LANE_TOP), lane(5, 1, DECK_Y))
)

# Aviation beacons on the tower tops, blinking out of step with each other.
beacons = "".join(
    '<i class="omb-beacon omb-amb" style="%s;--d:%ss"></i>' % (at(tx, TOWER_TOP - 12), n(-i * 1.1))
    for i, tx in enumerate(TOWER_X)
)


# Lights strung along the main cable at night, in two alternating sets that
# fade in and out of phase — the shimmer comes from that and nothing else.
def necklace(parity):
    dots, i = [], 0
    for x in range(8, W, 26):
        y = cable_at(x)
        if y is None or any(abs(x - tx) < 26 for tx in TOWER_X):
            continue
        if i % 2 == parity:
            dots.append(
                '<circle cx="%d" cy="%s" r="1.3"/><circle cx="%d" cy="%s" r="3.6" opacity="0.25"/>' % (x, n(y), x, n(y))
            )
        i += 1
    top, bottom = SADDLE_Y - 8, 250
    return '<div class="omb-necklace omb-necklace--%s omb-n omb-amb" style="top:%s;height:%s">%s</div>' % (
        "ab"[parity],
        py(top),
        py(bottom - top),
        svg("".join(dots), view=(0, top, W, bottom - top), align="none"),
    )


bridge_layer = traffic + bridge_svg + necklace(0) + necklace(1) + beacons


# ===========================================================================
# Sky
# ===========================================================================
ox, oy = ORB


def build_moon(r=27):
    """A full moon rising, with its maria as darker patches clipped to the disc
    and a soft halo. The halo is a radial gradient, not a flat disc: a disc has
    an edge, and an edge around a moon reads as an eclipse rather than as glow."""
    maria = ((-7, -6, 10, 6), (9, -11, 4, 3), (8, 3, 6, 4), (-12, 9, 3, 2), (1, 14, 5, 2), (15, -2, 2, 2))
    return (
        '<circle class="omb-moon__halo" cx="%d" cy="%d" r="%d" fill="url(#omb-orb-halo)"/>'
        '<circle class="omb-moon" cx="%d" cy="%d" r="%d"/>'
        '<g class="omb-moon__maria" clip-path="url(#omb-orb-clip)">%s</g>'
        % (
            ox,
            oy,
            r * 5,
            ox,
            oy,
            r,
            "".join(
                '<ellipse cx="%d" cy="%d" rx="%d" ry="%d" transform="rotate(-24 %d %d)"/>'
                % (ox + dx, oy + dy, rx, ry, ox + dx, oy + dy)
                for dx, dy, rx, ry in maria
            ),
        )
    )


def build_sun(r=30):
    return (
        '<circle class="omb-sun__halo" cx="%d" cy="%d" r="%d" fill="url(#omb-orb-halo)"/>'
        '<circle class="omb-sun" cx="%d" cy="%d" r="%d"/>' % (ox, oy, r * 6, ox, oy, r)
    )


sky_svg = svg(
    "<defs>"
    '<radialGradient id="omb-orb-halo">'
    '<stop offset="0" class="omb-halo-stop" stop-opacity="0.5"/>'
    '<stop offset="0.25" class="omb-halo-stop" stop-opacity="0.16"/>'
    '<stop offset="1" class="omb-halo-stop" stop-opacity="0"/>'
    "</radialGradient>"
    '<radialGradient id="omb-horizon-glow" cx="%s" cy="1" r="0.75" gradientTransform="translate(0 0) scale(1 1)">'
    '<stop offset="0" class="omb-horizon-stop" stop-opacity="0.8"/>'
    '<stop offset="0.5" class="omb-horizon-stop" stop-opacity="0.22"/>'
    '<stop offset="1" class="omb-horizon-stop" stop-opacity="0"/>'
    "</radialGradient>"
    '<linearGradient id="omb-haze" x1="0" y1="0" x2="0" y2="1">'
    '<stop offset="0" class="omb-haze-stop" stop-opacity="0"/>'
    '<stop offset="1" class="omb-haze-stop" stop-opacity="0.7"/>'
    "</linearGradient>"
    '<clipPath id="omb-orb-clip"><circle cx="%d" cy="%d" r="27"/></clipPath>'
    "</defs>"
    '<rect x="-60" y="-80" width="%d" height="%d" fill="url(#omb-horizon-glow)"/>'
    '<rect x="-60" y="110" width="%d" height="%d" fill="url(#omb-haze)"/>'
    '<g class="omb-n">%s</g>'
    '<g class="omb-d">%s</g>'
    % (n(ox / W), ox, oy, W + 120, SHORE_Y + 90, W + 120, SHORE_Y - 100, build_moon(), build_sun())
)

# An airliner crossing high over the bay: navigation lights and a strobe by
# night, a contrail by day. It rides a track the height of the plane only.
PLANE_Y = 150
plane = (
    '<div class="omb-plane-track omb-amb" style="top:%s">'
    '<div class="omb-plane">'
    '<i class="omb-contrail omb-d"></i>'
    '<svg viewBox="-12 -5 24 9" fill="currentColor">'
    '<path d="M-10 -0.9C-4 -1.8 6 -1.8 9 -0.9Q11 0 9 0.9C6 1.6 -4 1.6 -10 0.9Z"/>'
    '<path d="M-2.5 0.2L3.5 0.2L-1.5 4.2L-3.4 4.2Z"/>'
    '<path d="M-8.2 -0.6L-10.4 -4.6L-8.6 -4.6L-5.8 -0.8Z"/>'
    "</svg>"
    '<i class="omb-nav omb-nav--port omb-n"></i>'
    '<i class="omb-nav omb-nav--strobe omb-n omb-amb"></i>'
    "</div></div>" % py(PLANE_Y - 4)
)

# A shooting star, every so often, across the upper sky.
shooting = '<i class="omb-shoot omb-n omb-amb" style="%s"></i>' % at(640, 96)


# Stars: tiled patterns in screen pixels rather than scene units, so they stay
# pinpoints at any width. Two tiles of coprime-ish sizes, each fading in and out
# on its own clock — the twinkle is the two of them drifting out of phase.
def star_tile(pid, tw, th, count, sparkles, seed):
    random.seed(seed)
    dots = []
    for _ in range(count):
        dots.append(
            '<circle cx="%s" cy="%s" r="%s" opacity="%s"/>'
            % (
                n(random.uniform(3, tw - 3)),
                n(random.uniform(3, th - 3)),
                random.choice(("0.6", "0.7", "0.8", "0.9", "1.1")),
                n(random.uniform(0.35, 0.95)),
            )
        )
    for _ in range(sparkles):
        x, y = random.uniform(10, tw - 10), random.uniform(10, th - 10)
        dots.append(
            '<path d="M%s %sh8M%s %sv8" stroke="currentColor" stroke-width="0.6" stroke-linecap="round" opacity="0.7"/>'
            '<circle cx="%s" cy="%s" r="1.3"/>' % (n(x - 4), n(y), n(x), n(y - 4), n(x), n(y))
        )
    return (
        '<svg class="omb-stars omb-stars--%s omb-amb" width="100%%" height="100%%" fill="currentColor">'
        '<defs><pattern id="omb-stars-%s" width="%d" height="%d" patternUnits="userSpaceOnUse">%s</pattern></defs>'
        '<rect width="100%%" height="100%%" fill="url(#omb-stars-%s)"/></svg>' % (pid, pid, tw, th, "".join(dots), pid)
    )


stars = star_tile("a", 347, 283, 16, 1, 7) + star_tile("b", 419, 331, 20, 1, 13)


# ---------------------------------------------------------------------------
# Clouds and birds: one strip, twice the scene's width with every cloud drawn
# twice, drifting left forever.
# ---------------------------------------------------------------------------
def cloud(x, y, s):
    """A cloud as overlapping discs on a flat base, with a shaded underside."""
    blobs = ((0, 0, 1.0), (-1.05, 0.24, 0.7), (1.0, 0.2, 0.76), (-0.52, -0.36, 0.6), (0.58, -0.3, 0.54))
    discs = "".join(
        '<circle cx="%s" cy="%s" r="%s"/>' % (n(x + dx * s), n(y + dy * s), n(r * s)) for dx, dy, r in blobs
    )
    base = '<rect x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (n(x - 1.72 * s), n(y), n(3.5 * s), n(s), n(s / 2))
    belly = '<rect class="omb-cloud__shade" x="%s" y="%s" width="%s" height="%s" rx="%s"/>' % (
        n(x - 1.5 * s),
        n(y + 0.55 * s),
        n(3.06 * s),
        n(0.45 * s),
        n(0.22 * s),
    )
    return discs + base + belly


def wisp(x, y, s):
    """A streak of high cloud. Night wants this and not the puffy kind: at the
    contrast the night sky allows, stacked discs read as floating bubbles."""
    parts = ((0, 0, 1.0, 0.1), (-0.86, 0.08, 0.6, 0.07), (0.84, 0.07, 0.56, 0.06), (0.26, -0.09, 0.44, 0.05))
    return "".join(
        '<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/>' % (n(x + dx * s), n(y + dy * s), n(rx * s), n(ry * s))
        for dx, dy, rx, ry in parts
    )


CLOUDS = ((120, 118, 22), (430, 70, 17), (700, 150, 26), (980, 96, 20), (1250, 138, 23))
WISPS = ((200, 150, 110), (520, 196, 86), (860, 130, 120), (1200, 176, 96))
clouds_d = "".join(cloud(x + off, y, s) for off in (0, W) for x, y, s in CLOUDS)
clouds_n = "".join(wisp(x + off, y, s) for off in (0, W) for x, y, s in WISPS)
clouds = '<div class="omb-drift omb-amb">%s</div>' % svg(
    '<g class="omb-d">%s</g><g class="omb-n omb-wisps">%s</g>' % (clouds_d, clouds_n),
    view=(0, 0, 2 * W, H),
    align="xMinYMax meet",
)


def bird(i, x, y, s):
    wing = (
        '<svg viewBox="-12 -8 24 10" fill="none" stroke="currentColor" stroke-width="1.8" '
        'stroke-linecap="round"><path d="M-11 -1Q-5 -8 0 0Q5 -8 11 -1"/></svg>'
    )
    return '<i class="omb-bird omb-amb" style="left:%dpx;top:%dpx;width:%dpx;--d:%ss">%s</i>' % (
        x,
        y,
        s,
        n(-i * 0.23),
        wing,
    )


flock = '<div class="omb-flock omb-d omb-amb" style="top:%s">%s</div>' % (
    py(128),
    "".join(bird(i, x, y, s) for i, (x, y, s) in enumerate(((0, 8, 16), (22, 0, 13), (40, 14, 12), (60, 5, 11)))),
)


# ===========================================================================
# Land
# ===========================================================================
# Both ridges run far below the waterline: the water paints over the excess,
# and it is what keeps the parallax from ever showing a gap under a hill.
FAR = Ridge(
    (-60, 214),
    (
        ((130, 168), (250, 204), (372, 186)),
        ((470, 172), (560, 206), (660, 198)),
        ((790, 188), (860, 150), (966, 172)),
        ((1090, 198), (1214, 168), (1330, 192)),
        ((1382, 203), (1414, 200), (1500, 194)),
    ),
)
MID = Ridge(
    (-60, 242),
    (
        ((96, 224), (178, 248), (286, 240)),
        ((402, 231), (470, 206), (590, 226)),
        ((700, 244), (812, 224), (930, 236)),
        ((1070, 250), (1180, 222), (1300, 238)),
        ((1362, 246), (1406, 244), (1500, 236)),
    ),
)
hills_far = FAR.d + "L1500 460L-60 460Z"
hills_mid = MID.d + "L1500 460L-60 460Z"


def forest(ridge, spans, lo, hi, gap, seed):
    """Treetops standing on a ridge line. At this distance a wood is nothing
    but a serrated edge, and that edge is what stops a hill reading as a blob."""
    random.seed(seed)
    out = []
    for a, b in spans:
        x = a
        while x < b:
            h = random.uniform(lo, hi)
            w = h * random.uniform(0.5, 0.75)
            base = ridge.y(x) + 1.5
            out.append("M%s %sL%s %sL%s %sZ" % (n(x - w / 2), n(base), n(x), n(base - h), n(x + w / 2), n(base)))
            x += random.uniform(*gap)
    return '<path d="%s"/>' % "".join(out)


far_trees = forest(FAR, ((-60, 1500),), 2, 4.5, (3, 12), 31)
mid_trees = forest(MID, ((-60, 250), (290, 440), (600, 690), (990, 1110), (1300, 1500)), 3.5, 8, (2.5, 5.5), 37)


def skyline(x0, x1, seed):
    """A city on the far shore, tallest in the middle, with a pyramid and a
    round-topped tower for landmarks. Windows light up at night in scattered
    floors; by day the right-hand face of each block falls in shade."""
    random.seed(seed)
    base = SHORE_Y
    blocks, shade, windows = [], [], []

    def block(x, w, h):
        blocks.append("M%s %sh%sv%sh%sZ" % (n(x), n(base), n(w), n(-h), n(-w)))
        shade.append("M%s %sh%sv%sh%sZ" % (n(x + w * 0.62), n(base), n(w * 0.38), n(-h), n(-w * 0.38)))
        y = base - h + 2
        while y < base - 2:
            wx = x + 1.4
            while wx < x + w - 1.2:
                if random.random() < 0.3:
                    windows.append((wx, y))
                wx += 2.4
            y += 2.6

    x = x0
    while x < x1:
        w = random.uniform(6, 13)
        m = (x - x0) / (x1 - x0)
        block(x, w, (9 + 28 * math.sin(math.pi * m) ** 1.4) * random.uniform(0.45, 1))
        x += w + random.uniform(0.5, 3)
    # The landmarks, in front of the blocks around them. Their own path: wound
    # the other way round, inside the blocks' path they would punch holes.
    marks = []
    marks.append(
        "M806 %dL812 %dL818 %dZM809.5 %dh-2v-4h2ZM814.5 %dh2v-4h-2Z" % (base, base - 46, base, base - 16, base - 16)
    )
    shade.append("M812 %dL818 %dH812Z" % (base - 46, base))
    marks.append("M852.5 %dV%dQ858 %d 863.5 %dV%dZ" % (base, base - 44, base - 56, base - 44, base))
    shade.append("M859.5 %dV%dQ862 %d 863.5 %dV%dZ" % (base, base - 44, base - 50, base - 44, base))
    for y in range(base - 42, base - 2, 3):
        for wx in (854.5, 857.5, 860.5):
            if random.random() < 0.45:
                windows.append((wx, y))
    return (
        '<path class="omb-city" d="%s"/><path class="omb-city" d="%s"/>'
        '<path class="omb-city__shade" d="%s"/>'
        '<g class="omb-city__windows omb-n" fill="none" stroke="currentColor" stroke-linecap="square">%s</g>'
        % ("".join(blocks), "".join(marks), "".join(shade), dots(windows, 1.1))
    )


# A lighthouse on its own headland, just clear of the left tower.
LH_X, LH_LAMP = 456, 219.5
lighthouse = (
    '<path class="omb-headland" d="M396 252C414 246 430 239 446 239C464 239 476 243 496 252Z"/>'
    '<path class="omb-lh" d="M452 240L453.2 224H458.8L460 240ZM462 240V235.5L466 232.5L470 235.5V240Z"/>'
    '<path class="omb-lh__trim" d="M453 233.5h6v-2.6h-6ZM452.3 224.4h7.4v-1.8h-7.4ZM453.6 217.6L456 214.2L458.4 217.6Z"/>'
    '<rect class="omb-lh__lamp" x="454" y="217.6" width="4" height="4.8"/>'
)
lighthouse_beam = (
    '<div class="omb-lighthouse omb-n" style="%s">'
    '<i class="omb-beam omb-amb"></i><i class="omb-flash omb-amb"></i></div>' % at(LH_X, LH_LAMP)
)
city_beacon = '<i class="omb-beacon omb-beacon--sm omb-amb" style="%s;--d:-0.6s"></i>' % at(858, SHORE_Y - 57)

# Towns along the far shore: warm windows at night, little white houses by day.
random.seed(17)
town = []
for x0, x1 in ((0, 250), (470, 620), (1110, 1440)):
    for _ in range((x1 - x0) // 7):
        x = random.uniform(x0, x1)
        y = random.uniform(236, 249) if x < 250 or x > 1110 else random.uniform(226, 247)
        town.append((x, y))
lights = "".join(
    '<circle cx="%s" cy="%s" r="%s"/>' % (n(x), n(y), random.choice(("0.7", "0.9", "1.1"))) for x, y in town
)
houses = "".join('<rect x="%s" y="%s" width="3" height="2"/>' % (n(x), n(y)) for x, y in town[::2])


def hill_gradient(name, y0, y1):
    """Hills fade toward the haze at their feet: atmospheric perspective, and
    the only depth cue a flat silhouette can carry."""
    return (
        '<linearGradient id="omb-%s-g" x1="0" y1="%d" x2="0" y2="%d" gradientUnits="userSpaceOnUse">'
        '<stop offset="0" class="omb-%s-top"/><stop offset="1" class="omb-%s-base"/></linearGradient>'
        % (name, y0, y1, name, name)
    )


far_svg = svg(
    "<defs>%s</defs>" % hill_gradient("far", 150, 250)
    + '<g fill="url(#omb-far-g)"><path d="%s"/>%s</g>' % (hills_far, far_trees)
    + '<path class="omb-rim" d="%s" fill="none" stroke-width="1.2"/>' % FAR.d
)
mid_svg = svg(
    "<defs>%s</defs>" % hill_gradient("mid", 206, 252)
    + '<g fill="url(#omb-mid-g)"><path d="%s"/>%s</g>' % (hills_mid, mid_trees)
    + '<g class="omb-town omb-n">%s</g><g class="omb-town omb-d">%s</g>' % (lights, houses)
    + skyline(690, 960, 43)
    + lighthouse
)


# ---------------------------------------------------------------------------
# Water
# ---------------------------------------------------------------------------
random.seed(11)
ripples = []
y = SHORE_Y + 6
while y < H:
    depth = (y - SHORE_Y) / (H - SHORE_Y)
    for _ in range(int(3 + depth * 7)):
        x = random.randint(-60, W + 20)
        ln = random.randint(18, 60) + int(depth * 80)
        ripples.append('<path d="M%d %dh%d" opacity="%s"/>' % (x, y, ln, n(0.25 + depth * 0.5)))
    y += int(7 + depth * 9)

reflections = []
for tx in TOWER_X:
    ry = PIER_BOT + 16
    while ry < H - 10:
        f = (ry - PIER_BOT) / (H - PIER_BOT)
        hw = half(PIER_BOT) * (1 - f * 0.35)
        j = random.uniform(-5, 5)
        reflections.append(
            '<path d="M%s %dH%s" opacity="%s"/>' % (n(tx - hw + j), ry, n(tx + hw + j), n(0.5 * (1 - f)))
        )
        ry += random.randint(7, 13)


def glints(parity):
    """The orb's path of light on the water, and each deck lamp's broken streak.
    Split into two alternating sets so the water glitters."""
    random.seed(40 + parity)
    out = []
    y, i = SHORE_Y + 4, 0
    while y < H:
        depth = (y - SHORE_Y) / (H - SHORE_Y)
        if i % 2 == parity:
            w = 6 + depth * 44 * random.uniform(0.5, 1.2)
            x = ox + random.uniform(-10, 10) * (0.4 + depth * 2.2)
            out.append('<path d="M%s %sh%s" stroke-width="%s"/>' % (n(x - w / 2), n(y), n(w), n(1 + depth * 1.2)))
        y += 3.2 + depth * 7
        i += 1
    lamps = []
    for k, lx in enumerate(LAMPS):
        y = PIER_BOT + 4 + (k % 3) * 2
        j = parity
        while y < H - 16:
            if j % 2 == 0:
                w = random.uniform(3, 8)
                lamps.append('<path d="M%s %sh%s"/>' % (n(lx - w / 2 + random.uniform(-2, 2)), n(y), n(w)))
            y += random.uniform(5, 9)
            j += 1
    return '<div class="omb-glints omb-glints--%s omb-amb" style="top:%s;height:%s">%s</div>' % (
        "ab"[parity],
        py(SHORE_Y),
        py(H - SHORE_Y),
        svg(
            '<g class="omb-glints__orb" fill="none" stroke="currentColor" stroke-linecap="round">%s</g>'
            '<g class="omb-glints__lamp omb-n" fill="none" stroke="currentColor" stroke-width="1.6" '
            'stroke-linecap="round">%s</g>' % ("".join(out), "".join(lamps)),
            view=(0, SHORE_Y, W, H - SHORE_Y),
            align="none",
        ),
    )


def boat(s):
    """A sailboat in silhouette — hull, mast, mainsail, jib — drawn around its
    own waterline so it can be placed as a unit, with a masthead light at night."""
    return svg(
        '<path d="M%s 0L%s 0L%s %sL%s %sZ"/>' % (n(-s), n(s), n(0.62 * s), n(0.3 * s), n(-0.72 * s), n(0.3 * s))
        + '<path class="omb-sail" d="M%s %sL%s %sL%s %sZ"/>'
        % (n(0.02 * s), n(-1.55 * s), n(0.78 * s), n(-0.06 * s), n(0.02 * s), n(-0.06 * s))
        + '<path class="omb-sail" d="M%s %sL%s %sL%s %sZ"/>'
        % (n(-0.12 * s), n(-1.45 * s), n(-0.78 * s), n(-0.06 * s), n(-0.12 * s), n(-0.06 * s))
        + '<rect x="%s" y="%s" width="1.6" height="%s"/>' % (n(-0.1 * s), n(-1.6 * s), n(1.6 * s))
        + '<g class="omb-n omb-masthead"><circle cx="0" cy="%s" r="4" opacity="0.3"/>'
        '<circle cx="0" cy="%s" r="1.4"/></g>' % (n(-1.65 * s), n(-1.65 * s))
        + '<g fill="none" stroke="currentColor" stroke-linecap="round" opacity="0.5">%s</g>'
        % "".join(
            '<path d="M%s %sh%s" stroke-width="1.2" opacity="%s"/>'
            % (n(-s * (1.4 + i * 0.9)), n(0.45 * s + i * 3), n(s * (1.1 + i * 0.5)), n(1 - i * 0.3))
            for i in range(3)
        ),
        view=(-2 * s, -2 * s, 4 * s, 3 * s),
        align="xMidYMid meet",
    )


def boat_el(x, y, s, sail=False):
    """A boat sized in scene units. It bobs in place; with `sail` it also rides a
    track across the whole bay. The track is only as tall as the boat — it is a
    composited layer of its own, and an empty full-height one would still cost
    a full-height bitmap."""
    if not sail:
        return '<div class="omb-boat omb-amb" style="left:%s;top:%s;width:%s">%s</div>' % (
            px(x - 2 * s),
            py(y - 2 * s),
            px(4 * s),
            boat(s),
        )
    return '<div class="omb-sailing omb-amb" style="top:%s;height:%s">%s</div>' % (
        py(y - 2 * s),
        py(3 * s),
        '<div class="omb-boat omb-amb" style="left:%s;width:%s">%s</div>' % (px(x - 2 * s), px(4 * s), boat(s)),
    )


def ferry():
    """A two-deck bay ferry, bow to the left, drawn around its waterline.
    It passes *behind* the bridge, framed between the truss and the water."""
    win_lo = "".join("M%s -6.4h1.8v2h-1.8Z" % n(-24 + i * 3.2) for i in range(15))
    win_hi = "".join("M%s -11.2h1.6v1.8h-1.6Z" % n(-16 + i * 3.2) for i in range(8))
    glow = "".join(
        '<path d="M%s %sh%s" opacity="%s"/>' % (n(x), n(y), n(w), o)
        for x, y, w, o in ((-22, 6, 14, "0.5"), (-6, 7.5, 18, "0.45"), (-18, 10, 9, "0.35"), (4, 11.5, 10, "0.3"))
    )
    return svg(
        '<path class="omb-ferry__hull" d="M-33 -2.4H30L26.5 4H-28.5Z"/>'
        '<path class="omb-ferry__stripe" d="M-31.4 -0.6H28.6v1.3H-30.4Z"/>'
        '<path class="omb-ferry__cabin" d="M-26 -8.2h50v5.8h-50ZM-18 -12.8h30v4.6h-30ZM-8 -15.8h10v3h-10ZM6 -19.4h0.9v6.6H6Z"/>'
        '<path class="omb-ferry__win" d="%s%s"/>'
        '<g class="omb-n omb-ferry__glow" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">'
        "%s</g>"
        '<g class="omb-n omb-masthead"><circle cx="6.4" cy="-19.6" r="3.4" opacity="0.3"/>'
        '<circle cx="6.4" cy="-19.6" r="1.1"/></g>' % (win_lo, win_hi, glow),
        view=(-34, -21, 68, 36),
        align="xMidYMid meet",
    )


FERRY_Y = 318
ferry_el = '<div class="omb-ferry-track omb-amb" style="top:%s;height:%s">%s</div>' % (
    py(FERRY_Y - 21),
    py(36),
    '<div class="omb-ferry" style="left:100%%;width:%s">%s</div>' % (px(68), ferry()),
)

water_svg = svg(
    "<defs>"
    '<linearGradient id="omb-water" x1="0" y1="%d" x2="0" y2="%d" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" class="omb-water-top"/>'
    '<stop offset="0.3" class="omb-water-mid"/>'
    '<stop offset="1" class="omb-water-deep"/>'
    "</linearGradient>"
    "</defs>"
    '<rect x="-60" y="%d" width="%d" height="%d" fill="url(#omb-water)"/>'
    '<path class="omb-sheen" d="M-60 %dH%d" stroke="currentColor" stroke-width="1.4"/>'
    '<g class="omb-reflect" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round">%s</g>'
    % (SHORE_Y, H, SHORE_Y - 1, W + 120, H - SHORE_Y + 200, SHORE_Y + 1, W + 60, "".join(reflections))
)
water_layer = (
    water_svg
    + '<div class="omb-ripples omb-amb" style="top:%s;height:%s">%s</div>'
    % (
        py(SHORE_Y),
        py(H - SHORE_Y),
        svg(
            '<g fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round">%s</g>' % "".join(ripples),
            view=(0, SHORE_Y, W, H - SHORE_Y),
            align="none",
        ),
    )
    + glints(0)
    + glints(1)
    + ferry_el
    + boat_el(880, 364, 9)
    + boat_el(30, 404, 13, sail=True)
)


# ---------------------------------------------------------------------------
# Fog: a low bank rolling through the piers. Blurred once when the strip is
# first painted; after that the compositor only slides the bitmap.
# ---------------------------------------------------------------------------
random.seed(5)
puffs = []
for _ in range(16):
    x = random.uniform(0, W)
    y = random.uniform(318, 352)
    rx, ry = random.uniform(90, 200), random.uniform(10, 18)
    for off in (0, W):
        puffs.append('<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/>' % (n(x + off), n(y), n(rx), n(ry)))
FOG_TOP, FOG_H = 290, 90
fog = '<div class="omb-drift omb-drift--fog omb-amb" style="top:%s">%s</div>' % (
    py(FOG_TOP),
    svg(
        '<defs><filter id="omb-fog-blur" x="-10%%" y="-60%%" width="120%%" height="220%%">'
        '<feGaussianBlur stdDeviation="9"/></filter></defs>'
        '<g filter="url(#omb-fog-blur)">%s</g>' % "".join(puffs),
        view=(0, FOG_TOP, 2 * W, FOG_H),
        align="xMinYMin meet",
    ),
)


# ---------------------------------------------------------------------------
# The viewer's own shore, in front of everything.
# ---------------------------------------------------------------------------
SHORE = Ridge(
    (-60, 404),
    (
        ((120, 380), (214, 398), (330, 392)),
        ((430, 387), (500, 408), (610, 412)),
        ((760, 418), (900, 404), (1040, 400)),
        ((1172, 396), (1300, 384), (1500, 396)),
    ),
)
shore = SHORE.d + "L1500 640L-60 640Z"

# A fringe of grass along the whole edge of the shore, so it reads as a
# meadow against the water instead of a cut-out.
random.seed(71)
blades, x = [], -60.0
while x < W + 60:
    h = random.uniform(1.5, 4.5) * (2.3 if random.random() < 0.12 else 1)
    blades.append("M%s %sl%s %s" % (n(x), n(SHORE.y(x) + 0.8), n(random.uniform(-1.6, 1.6)), n(-h)))
    x += random.uniform(2, 4.2)
grass = (
    '<path class="omb-grass" d="%s" fill="none" stroke="currentColor" stroke-width="1.1" stroke-linecap="round"/>'
    % "".join(blades)
)


def cypress(x, h, lean, seed):
    """A Monterey cypress: a stout trunk that leans with the wind and forks,
    under a dense canopy of overlapping lobes combed downwind — flat on top,
    trailing and drooping on the lee side."""
    random.seed(seed)
    base = SHORE.y(x) + 3
    k = lean * h
    tx, ty = x + k * 0.22, base - h * 0.58  # where the trunk meets the canopy
    trunk = "M%s %sC%s %s %s %s %s %sL%s %sC%s %s %s %s %s %sZ" % tuple(
        n(v)
        for v in (
            x - 3,
            base,
            x - 1.5,
            base - h * 0.3,
            tx - 3,
            ty + h * 0.12,
            tx - 1.2,
            ty,
            tx + 1.6,
            ty,
            tx + 0.5,
            ty + h * 0.14,
            x + 2.5,
            base - h * 0.28,
            x + 3.6,
            base,
        )
    )
    fork = "M%s %sL%s %sl2.2 0.8L%s %sZ" % tuple(
        n(v) for v in (x + k * 0.08, base - h * 0.34, x - k * 0.14, base - h * 0.6, x + k * 0.1 + 2, base - h * 0.32)
    )
    lobes = []
    for _ in range(16):
        u = random.uniform(-0.3, 0.8)  # along the wind: downwind is positive
        v = random.random()
        rx = h * random.uniform(0.09, 0.17)
        lobes.append(
            '<ellipse cx="%s" cy="%s" rx="%s" ry="%s"/>'
            % (
                n(x + k * (0.1 + u * 0.55)),
                n(base - h * (0.6 + 0.3 * v * (1 - 0.5 * max(u, 0)) - 0.1 * max(u, 0) ** 2)),
                n(rx),
                n(rx * random.uniform(0.42, 0.62)),
            )
        )
    return '<path d="%s%s"/>%s' % (trunk, fork, "".join(lobes))


cypresses = cypress(478, 84, 1, 3) + cypress(1176, 60, -1, 9)

# A rope fence along the path to the bench.
posts = [x for x in range(706, 812, 15)]
fence = '<path d="%s%s" fill="none" stroke="currentColor" stroke-linecap="round"/>' % (
    "".join("M%d %sv-9" % (x, n(SHORE.y(x) + 1)) for x in posts),
    "".join(
        "M%d %sQ%s %s %d %s"
        % (a, n(SHORE.y(a) - 6.5), n((a + b) / 2), n(SHORE.y((a + b) / 2) - 3.5), b, n(SHORE.y(b) - 6.5))
        for a, b in zip(posts, posts[1:])
    ),
)

# Wildflowers in the grass, by day.
random.seed(83)
flowers = "".join(
    '<g class="omb-flowers omb-flowers--%d omb-d" fill="none" stroke="currentColor" stroke-linecap="round">%s</g>'
    % (
        k,
        dots(
            [
                (x, SHORE.y(x) + random.uniform(1.5, 9))
                for x in (random.uniform(*random.choice(((520, 700), (880, 1010), (230, 380)))) for _ in range(14))
            ],
            2.2,
        ),
    )
    for k in range(3)
)


def conifer(x, base, h, w):
    """A silhouetted pine: a trunk under three stacked skirts."""
    parts = [
        '<rect x="%s" y="%s" width="%s" height="%s"/>' % (n(x - w * 0.07), n(base - h * 0.16), n(w * 0.14), n(h * 0.2))
    ]
    for i in range(3):
        cy = base - h * 0.16 - h * 0.26 * i
        hw = w * 0.5 * (1 - 0.2 * i)
        parts.append('<path d="M%s %sL%s %sL%s %sZ"/>' % (n(x - hw), n(cy), n(x), n(cy - h * 0.42), n(x + hw), n(cy)))
    return "".join(parts)


def rock(x, y, s):
    """A boulder: two overlapping domes so the silhouette is not a plain arc."""
    return '<path d="M%s %sQ%s %s %s %sZM%s %sQ%s %s %s %sZ"/>' % tuple(
        n(v) for v in (x - s, y, x, y - 1.5 * s, x + s, y, x + 0.4 * s, y, x + 1.05 * s, y - 0.95 * s, x + 1.7 * s, y)
    )


def tuft(x, y, s):
    """A clump of grass: three blades fanning out."""
    return "".join(
        '<path d="M%s %sQ%s %s %s %s"/>'
        % tuple(n(v) for v in (x, y, x + k * s * 0.3, y - s * 0.6, x + k * s * 0.75, y - s))
        for k in (-1, 0, 1)
    )


LAMP_X, LAMP_BASE = 836, 413
rocks = "".join(rock(*r) for r in ((212, 404, 9), (404, 412, 7), (660, 415, 6), (1196, 400, 8), (1424, 404, 11)))
tufts = "".join(
    tuft(*t)
    for t in (
        (246, 404, 11),
        (268, 406, 8),
        (352, 410, 9),
        (520, 412, 8),
        (716, 414, 9),
        (812, 413, 7),
        (996, 404, 10),
        (1160, 400, 10),
        (1232, 402, 8),
    )
)
trees = "".join(
    conifer(*t)
    for t in (
        (44, 400, 44, 23),
        (72, 404, 58, 28),
        (104, 399, 36, 19),
        (132, 402, 68, 32),
        (172, 406, 30, 16),
        (196, 403, 47, 24),
        (1058, 402, 34, 18),
        (1082, 399, 48, 24),
        (1258, 394, 40, 21),
        (1292, 391, 62, 29),
        (1330, 396, 33, 18),
        (1364, 393, 52, 26),
        (1402, 398, 38, 20),
    )
)
# Two lamp posts and a bench on the near shore, the rope fence running
# between them: somewhere for the viewer to stand.
LAMPS_SHORE = (694, LAMP_X)


def street_lamp(x):
    base = LAMP_BASE if x == LAMP_X else round(SHORE.y(x) + 1)
    post = '<rect x="%s" y="%d" width="2.4" height="44"/><path d="M%s %dh10l-2 4h-6z"/>' % (
        n(x - 1.2),
        base - 44,
        n(x - 5),
        base - 48,
    )
    glow = (
        '<g class="omb-n"><circle cx="%d" cy="%d" r="46" fill="url(#omb-pool)"/>'
        '<ellipse cx="%d" cy="%d" rx="46" ry="9" fill="url(#omb-pool)"/>'
        '<circle class="omb-shore__bulb" cx="%d" cy="%d" r="2.4"/></g>' % (x, base - 44, x + 4, base + 1, x, base - 43)
    )
    return post, glow


bench = (
    '<rect x="%d" y="%d" width="26" height="2.4" rx="1"/>' % (LAMP_X + 10, LAMP_BASE - 10)
    + '<rect x="%d" y="%d" width="26" height="2" rx="1"/>' % (LAMP_X + 10, LAMP_BASE - 17)
    + '<path d="M%d %dv9M%d %dv9M%d %dv16M%d %dv16" stroke="currentColor" stroke-width="1.6"/>'
    % (LAMP_X + 12, LAMP_BASE - 9, LAMP_X + 34, LAMP_BASE - 9, LAMP_X + 12, LAMP_BASE - 17, LAMP_X + 34, LAMP_BASE - 17)
)
street_lamps = [street_lamp(x) for x in LAMPS_SHORE]
lamp_post = bench + "".join(post for post, _ in street_lamps)
lamp_glow = (
    '<defs><radialGradient id="omb-pool">'
    '<stop offset="0" class="omb-lamp-stop" stop-opacity="0.55"/>'
    '<stop offset="0.3" class="omb-lamp-stop" stop-opacity="0.16"/>'
    '<stop offset="1" class="omb-lamp-stop" stop-opacity="0"/>'
    "</radialGradient></defs>" + "".join(glow for _, glow in street_lamps)
)

fireflies = "".join(
    '<i class="omb-firefly omb-n omb-amb" style="%s;--d:%ss;--t:%ss"></i>' % (at(x, y), n(d), n(t))
    for x, y, d, t in (
        (150, 380, 0, 5.2),
        (238, 390, -1.7, 6.1),
        (596, 396, -3.1, 5.6),
        (742, 402, -0.8, 6.8),
        (962, 388, -2.4, 5.9),
        (1126, 384, -4, 6.4),
        (1318, 372, -1.2, 5.4),
    )
)

shore_svg = svg(
    '<defs><linearGradient id="omb-shore-g" x1="0" y1="384" x2="0" y2="470" gradientUnits="userSpaceOnUse">'
    '<stop offset="0" class="omb-shore-top"/><stop offset="1" class="omb-shore-base"/></linearGradient></defs>'
    '<path d="%s" fill="url(#omb-shore-g)"/>%s%s'
    '<g fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">%s</g>%s%s%s%s%s'
    % (shore, grass, rocks, tufts, flowers, fence, cypresses, trees, lamp_post + lamp_glow)
)


# ===========================================================================
# Assembly, far to near. `--r` is each layer's parallax rate: the fraction of
# the scroll it resists. Far layers resist most and so barely move on screen;
# the near shore has a negative rate and so outruns the page.
# ===========================================================================
def layer(name, rate, inner, anchor=""):
    return '<div class="omb-scene omb-scene--%s omb-par"%s style="--r:%s">\n  %s\n</div>\n' % (
        name,
        ' data-anchor="%s"' % anchor if anchor else "",
        ("%.2f" % rate).rstrip("0"),
        inner,
    )


html = (
    "{# Generated by scripts/build_hero_scene.py — do not edit by hand. #}\n"
    '<div class="omb-scene__stage"></div>\n'
    + layer("stars", 0.46, stars)
    + layer("sky", 0.4, sky_svg + shooting + plane)
    + layer("clouds", 0.34, clouds + flock)
    + layer("hills-far", 0.28, far_svg)
    + layer("hills-mid", 0.21, mid_svg + lighthouse_beam + city_beacon)
    + layer("water", 0.15, water_layer)
    + layer("bridge", 0.1, bridge_layer)
    + layer("fog", 0.06, fog)
    + layer("shore", -0.1, shore_svg + fireflies)
)

out = pathlib.Path("docs-overrides/partials/hero-scene.html")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(html)
print(
    "wrote %s — %.1f KB, %d suspenders, %d lamps, %d ripples"
    % (out, len(html.encode()) / 1024, len(susp), len(LAMPS), len(ripples))
)
