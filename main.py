"""Halved blood orange, rendered from scratch with the Python standard library.

Writes /output/entry.png (1024x1024 PNG). Deterministic: no randomness besides
fixed integer hashing.
"""
import math
import os
import struct
import zlib

W = H = 1024
OUT = "/output/entry.png"

# Geometry (pixels)
CX, CY = 512.0, 478.0          # centre of the cut face
R = 352.0                      # radius of the cut face (outer peel edge)
BX, BY = 516.0, 520.0          # centre of the fruit body (dome below the face)
BR = 350.0
SEG = 11                       # segments
ROT = 0.23                     # segment rotation

# Light: key from upper-left (warm), rim from right
LX, LY = -0.62, -0.78


def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def smooth(e0, e1, x):
    t = clamp((x - e0) / (e1 - e0))
    return t * t * (3 - 2 * t)


def mix(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def hash2(i, j, s=0):
    h = (i * 374761393 + j * 668265263 + s * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    h ^= h >> 16
    return (h & 0xFFFF) / 65535.0


def vnoise(x, y, s=0):
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = x - xi, y - yi
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = hash2(xi, yi, s)
    b = hash2(xi + 1, yi, s)
    c = hash2(xi, yi + 1, s)
    d = hash2(xi + 1, yi + 1, s)
    return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy


# Water droplets on the cut face / peel: (x, y, radius)
DROPS = [
    (300, 372, 22), (690, 322, 16), (612, 632, 25), (405, 602, 13),
    (735, 552, 18), (470, 292, 11), (566, 400, 9), (348, 505, 14),
    (318, 410, 8), (650, 650, 9), (222, 600, 13), (660, 822, 15), (392, 818, 11),
]

TWO_PI = 2 * math.pi
SEG_W = TWO_PI / SEG

# per-segment colour variation (blood orange: some segments deep crimson, some orange)
SEG_TONE = [hash2(k, 7, 3) for k in range(SEG)]


def background(x, y):
    # warm dark slate with soft vignette and light pool upper-left
    dx, dy = (x - 470) / 760.0, (y - 430) / 760.0
    d = math.sqrt(dx * dx + dy * dy)
    v = clamp(1.0 - d * 1.05)
    v = v * v
    base = mix((16, 11, 10), (104, 70, 52), v)
    # contact shadow under the fruit (soft ellipse, offset down-right)
    sx, sy = (x - 540) / 400.0, (y - 600) / 330.0
    sd = math.sqrt(sx * sx + sy * sy)
    sh = 1.0 - 0.85 * (1.0 - smooth(0.78, 1.18, sd))
    sx2, sy2 = (x - 525) / 368.0, (y - 560) / 340.0
    sd2 = math.sqrt(sx2 * sx2 + sy2 * sy2)
    sh *= 1.0 - 0.6 * (1.0 - smooth(0.95, 1.06, sd2))
    # faint surface grain
    g = (vnoise(x * 0.02, y * 0.02, 11) - 0.5) * 6
    return (base[0] * sh + g, base[1] * sh + g, base[2] * sh + g)


def peel_body(x, y):
    """Outside of the fruit (dome) seen below the cut face."""
    nx, ny = (x - BX) / BR, (y - BY) / BR
    rr = nx * nx + ny * ny
    nz = math.sqrt(max(0.0, 1.0 - rr))
    # dimpled peel texture perturbs the normal
    n1 = vnoise(x * 0.11, y * 0.11, 5)
    n2 = vnoise(x * 0.23, y * 0.23, 6)
    bump = (n1 - 0.5) * 0.5 + (n2 - 0.5) * 0.25
    lam = clamp(nx * LX + ny * LY + nz * 0.55 + 0.05 + bump * 0.25)
    lam *= 0.55 + 0.45 * clamp(1.2 - ny * 1.3)
    col = mix((40, 6, 4), (215, 78, 24), lam)
    # reddish blush typical of blood orange peel
    blush = vnoise(x * 0.008, y * 0.008, 9)
    col = mix(col, (col[0] * 0.95, col[1] * 0.55, col[2] * 0.6), blush * 0.6)
    # rim light on the right edge
    rim = smooth(0.80, 1.0, math.sqrt(rr)) * clamp(nx * 1.2)
    col = mix(col, (255, 170, 120), rim * 0.25)
    # glossy speculars on the peel (tiny, from dimples)
    spec = clamp((n2 - 0.72) * 5) * clamp(-ny * 0.6 + nx * 0.2 + 0.4)
    col = mix(col, (255, 230, 200), spec * 0.35)
    return col


def cut_face(x, y):
    dx, dy = x - CX, y - CY
    r = math.sqrt(dx * dx + dy * dy)
    rn = r / R
    th = math.atan2(dy, dx)

    # ---- rind ring (outer) ----
    if rn > 0.945:
        t = (rn - 0.945) / 0.055
        n = vnoise(th * 60, rn * 30, 2)
        col = mix((236, 122, 44), (178, 50, 18), smooth(0.2, 1.0, t))
        col = mix(col, (150, 30, 14), (n - 0.5) * 0.4 + 0.1)
        # light on upper-left rim, rim light right
        lit = clamp(-(dx * LX + dy * LY) / r * -1.0) if r > 0 else 0
        col = mix(col, (255, 170, 90), clamp((dx * LX + dy * LY) / r) * 0.35)
        return col
    # ---- pith ----
    if rn > 0.905:
        t = (rn - 0.905) / 0.04
        n = vnoise(th * 90, rn * 40, 4)
        col = mix((228, 150, 118), (246, 206, 168), t)
        col = mix(col, (200, 70, 56), (1 - t) * 0.55 + (n - 0.5) * 0.25)
        return col

    # ---- flesh ----
    a = (th - ROT + 0.012 * math.sin(rn * 17.0 + th * 3) + (vnoise(rn * 9, th * 4, 12) - 0.5) * 0.025) % TWO_PI
    k = int(a / SEG_W)
    u = (a - k * SEG_W) / SEG_W          # 0..1 across segment
    # membrane between segments: width in pixels roughly constant
    arc_d = min(u, 1 - u) * SEG_W * r    # px distance to membrane
    mem = (1.0 - smooth(0.6, 2.6 + 1.2 * rn, arc_d)) * (0.55 + 0.45 * rn)
    # outer membrane along pith, and central core
    edge_d = (0.905 - rn) * R
    mem = max(mem, 1.0 - smooth(1.0, 5.0, edge_d))
    core = 1.0 - smooth(0.035, 0.085, rn + 0.012 * math.sin(th * SEG))

    tone = SEG_TONE[k]
    # blood-orange flesh: crimson to ruby with orange streaks
    deep = (122, 6, 22)
    ruby = (205, 22, 34)
    orng = (238, 92, 30)
    # radial gradient: richer toward centre, lighter near rind
    g = smooth(0.0, 0.9, rn)
    base = mix(deep, ruby, 0.35 + 0.55 * g)
    streak = vnoise(th * 9 + k * 3.1, rn * 6, 8)
    base = mix(base, orng, clamp(tone * 0.55 + (streak - 0.55) * 1.1) * (0.35 + 0.5 * g))

    # ---- juice vesicles: elongated radial cells ----
    wr = (vnoise(x * 0.05, y * 0.05, 13) - 0.5) * 9.0
    cell_r = 13.0 + 9.0 * rn
    ri = (r + wr) / cell_r
    ii = math.floor(ri)
    across = u * SEG_W * r + (vnoise(x * 0.06, y * 0.06, 14) - 0.5) * 6.0
    cell_w = 6.5 + 3.5 * rn
    jj = math.floor(across / cell_w + hash2(ii, k, 1) * 0.9)
    fr = ri - ii
    fa = across / cell_w + hash2(ii, k, 1) * 0.9 - jj
    ex = (fa - 0.5) * 2.0
    ey = (fr - 0.5) * 2.0
    asp = 0.8 + 0.5 * hash2(ii, jj, 5)
    ey2 = ey + 0.25 * ex * ex  # teardrop bend
    vd = math.sqrt(ex * ex * asp + ey2 * ey2 * 0.85)
    vh = hash2(ii, jj + k * 97, 2)
    inside = 1.0 - smooth(0.45, 1.05, vd)
    # translucent juicy shading: bright core, darker borders
    shade = 0.80 + 0.30 * inside + (vh - 0.5) * 0.22
    col = (base[0] * shade, base[1] * shade, base[2] * shade)
    # vesicle highlight (upper-left of each cell)
    hx, hy = ex + 0.35, ey + 0.35
    hl = 1.0 - smooth(0.0, 0.45, math.sqrt(hx * hx + hy * hy))
    col = mix(col, (255, 190, 170), hl * 0.38 * inside * (0.4 + 0.6 * vh))
    sx, sy = (x - CX) / R + 0.36, (y - CY) / R + 0.40
    wet = math.exp(-(sx * sx * 2.2 + sy * sy * 4.0) * 2.0)
    col = mix(col, (255, 245, 235), clamp(hl * inside * wet * 1.6 * (0.3 + vh)))

    # inner glow: subsurface warmth near centre
    glow = (1 - smooth(0.0, 0.55, rn)) * 0.25
    col = mix(col, (255, 70, 50), glow)

    # membranes and core: pale, translucent pink-white
    memc = mix((235, 160, 140), (250, 210, 190), smooth(0.2, 0.9, rn))
    col = mix(col, memc, mem * 0.78)
    col = mix(col, (246, 196, 176), core * 0.9)
    return col


def face_lighting(x, y, col):
    dx, dy = (x - CX) / R, (y - CY) / R
    # broad soft wet sheen upper-left
    sx, sy = dx + 0.38, dy + 0.42
    sheen = math.exp(-(sx * sx * 3.0 + sy * sy * 6.0) * 2.2)
    # key light falloff across face
    lit = 0.88 + 0.22 * clamp(-(dx * 0.6 + dy * 0.75))
    col = (col[0] * lit, col[1] * lit, col[2] * lit)
    col = mix(col, (255, 236, 222), sheen * 0.20)
    return col


def drop_shade(x, y, col):
    for (px, py, pr) in DROPS:
        dx, dy = x - px, y - py
        if abs(dx) > pr + 2 or abs(dy) > pr + 2:
            continue
        d = math.sqrt(dx * dx + dy * dy) / pr
        if d >= 1.08:
            continue
        a = 1.0 - smooth(0.92, 1.05, d)
        # lens: magnify/brighten underlying colour, dark edge at bottom-right
        nx, ny = dx / pr, dy / pr
        inner = mix(col, (min(255, col[0] * 1.25 + 20), min(255, col[1] * 1.25 + 12), min(255, col[2] * 1.2 + 12)), 0.8)
        edge = smooth(0.55, 1.0, d) * clamp(0.5 + 0.7 * (nx * 0.6 + ny * 0.8))
        inner = mix(inner, (col[0] * 0.25, col[1] * 0.2, col[2] * 0.2), edge * 0.85)
        # bright caustic at lower-right inside
        cx2, cy2 = nx - 0.45, ny - 0.45
        caus = 1.0 - smooth(0.0, 0.35, math.sqrt(cx2 * cx2 + cy2 * cy2))
        inner = mix(inner, (255, 220, 200), caus * 0.35)
        # specular highlight upper-left
        sx, sy = nx + 0.38, ny + 0.4
        sp = 1.0 - smooth(0.05, 0.28, math.sqrt(sx * sx + sy * sy))
        inner = mix(inner, (255, 255, 255), sp * 0.95)
        col = mix(col, inner, a)
    return col


def pixel(x, y):
    dfx, dfy = x - CX, y - CY
    df = math.sqrt(dfx * dfx + dfy * dfy)
    dbx, dby = x - BX, y - BY
    db = math.sqrt(dbx * dbx + dby * dby)
    col = background(x, y)
    # body (dome) with anti-aliased edge
    ab = clamp(BR + 0.5 - db)
    if ab > 0:
        col = mix(col, peel_body(x, y), ab)
        # thin dark crease where face meets dome
        crease = 1.0 - smooth(0.0, 6.0, abs(df - R) )
        col = mix(col, (40, 6, 4), crease * 0.5 * (1 if df > R else 0))
    af = clamp(R + 0.5 - df)
    if af > 0:
        c = cut_face(x, y)
        c = face_lighting(x, y, c)
        col = mix(col, c, af)
    col = drop_shade(x, y, col)
    return col


def gamma_boost(c):
    # gentle contrast curve
    out = []
    for v in c:
        t = clamp(v / 255.0)
        t = t * t * (3 - 2 * t) * 0.35 + t * 0.65
        out.append(int(t * 255 + 0.5))
    return out


def write_png(path, rows):
    raw = bytearray()
    for row in rows:
        raw.append(1)  # Sub filter: smaller file for smooth gradients
        prev = bytes(3) + bytes(row[:-3])
        raw.extend(bytes((a - b) & 0xFF for a, b in zip(row, prev)))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(png)
    return len(png)


def main():
    rows = []
    for y in range(H):
        row = bytearray()
        for x in range(W):
            r, g, b = gamma_boost(pixel(x + 0.5, y + 0.5))
            row += bytes((r, g, b))
        rows.append(row)
    n = write_png(OUT, rows)
    print("wrote", OUT, n, "bytes")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        OUT = sys.argv[1]
    main()
