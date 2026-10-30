"""AURORA hero background: flat-style aurora over a low horizon with a solar street lamp.
Procedural (numpy + Pillow), loops perfectly (all time dependence = sin/cos with integer cycles per 12 s).

Usage: python make_aurora_hero.py <workdir> [--frames N] [--only-frame K]
Writes <workdir>/hero_lossless.mkv (FFV1) and <workdir>/hero_poster_src.png.
Encoding is done by encode_hero.py (or the commands in the report).
"""
import sys, os, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from multiprocessing import Pool

W, H, FPS, DUR = 1920, 1080, 30, 12
NF = FPS * DUR
TAU = 2 * math.pi


def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lut(stops, s):
    """stops: list of (pos, '#hex'); s: array -> (...,3)"""
    pos = [p for p, _ in stops]
    cols = np.stack([hexc(c) for _, c in stops])
    return np.stack([np.interp(s, pos, cols[:, k]) for k in range(3)], -1).astype(np.float32)


# ---------------------------------------------------------------- static data (built once per worker)
S = {}


def hill_y(x, base, comps):
    y = np.full_like(x, base)
    for amp, wl, ph in comps:
        y += amp * np.sin(TAU * x / wl + ph)
    return y


CURTAINS = [
    # xc, half-width, y0(bottom edge), height, opacity, rays wavelength, seed-phase
    dict(xc=0.50, hw=0.44, y0=0.545, h=0.34, op=0.55, rl=210, ph=0.6, n=(1, 2, 3), amp=(46, 24, 12), lam=(1500, 760, 410)),
    dict(xc=0.96, hw=0.36, y0=0.500, h=0.31, op=0.52, rl=170, ph=2.3, n=(2, 1, 3), amp=(40, 22, 10), lam=(1100, 640, 330)),
    dict(xc=0.80, hw=0.50, y0=0.605, h=0.40, op=0.85, rl=240, ph=4.1, n=(1, 3, 2), amp=(52, 26, 11), lam=(1700, 820, 450)),
    dict(xc=0.30, hw=0.34, y0=0.665, h=0.22, op=0.42, rl=190, ph=1.4, n=(2, 1, 1), amp=(30, 18, 8), lam=(1300, 700, 380)),
    dict(xc=0.64, hw=0.28, y0=0.705, h=0.30, op=0.70, rl=150, ph=5.2, n=(1, 2, 3), amp=(34, 20, 9), lam=(1000, 560, 300)),
]
STOPS = [(0.0, '#0f6b5a'), (0.35, '#1d7c66'), (0.65, '#2f8f6f'), (0.88, '#4aa37f'), (1.0, '#56c785')]
LAMP = None


def build_static():
    if S:
        return
    xs = np.arange(W, dtype=np.float32)
    ys = np.arange(H, dtype=np.float32)
    S['xs'], S['ys'] = xs, ys
    # sky gradient
    sky = lut([(0.0, '#051f33'), (0.45, '#08304d'), (0.86, '#0e4f78'), (1.0, '#0e4f78')], ys / H)  # (H,3)
    S['sky'] = np.repeat(sky[:, None, :], W, 1)
    # hills
    far = hill_y(xs, 0.835 * H, [(26, 1750, 1.1), (15, 640, 2.0), (6, 230, 0.4)])
    near = hill_y(xs, 0.925 * H, [(20, 1450, 0.4), (10, 520, 3.1), (4, 190, 1.7)])
    S['far'], S['near'] = far, near
    Y = ys[:, None]
    mfar = np.clip((Y - far[None, :]) + 0.5, 0, 1)
    mnear = np.clip((Y - near[None, :]) + 0.5, 0, 1)
    S['mfar'], S['mnear'] = mfar[..., None], mnear[..., None]
    # far hill has slight vertical gradient (lighter near its ridge)
    rid = np.clip((Y - far[None, :]) / 140.0, 0, 1)
    S['colfar'] = (hexc('#0a3350')[None, None, :] * (1 - rid[..., None]) + hexc('#06243a')[None, None, :] * rid[..., None])
    S['colnear'] = hexc('#031621')[None, None, :]
    # lamp pole position
    px = int(0.835 * W)
    py = int(near[px]) + 6
    S['pole'] = (px, py)
    # stars
    rng = np.random.default_rng(7)
    n = 105
    sx = rng.uniform(10, W - 10, n)
    sy = rng.uniform(8, 0.60 * H, n) ** 1.0
    sr = rng.choice([0.9, 1.2, 1.6, 2.1], n, p=[0.35, 0.35, 0.22, 0.08])
    sb = rng.uniform(0.45, 1.0, n)
    sk = rng.choice([1, 2, 3, 4], n)
    sp = rng.uniform(0, TAU, n)
    sm = rng.random(n) < 0.45
    S['stars'] = (sx, sy, sr, sb, sk, sp, sm)
    # static dither
    S['noise'] = (np.random.default_rng(3).random((H, W, 3), dtype=np.float32) - 0.5)
    # pole layer (RGBA float, supersampled)
    build_pole(px, py)
    # calm mask (hero text area top-left)
    L = 1 - smoothstep(0.12 * W, 0.58 * W, xs)
    U = 1 - smoothstep(0.30 * H, 0.62 * H, ys)
    S['calm'] = (1 - 0.72 * (U[:, None] * L[None, :])).astype(np.float32)


def build_pole(px, py):
    SS = 4
    cw, ch = 760, 520
    ox, oy = px - 380, py - 500  # crop origin in image coords
    im = Image.new('RGBA', (cw * SS, ch * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    bx, by = 380, 500
    sil = (2, 11, 18, 255)

    def P(pts):
        return [(x * SS, y * SS) for x, y in pts]

    top = by - 300
    d.polygon(P([(bx - 6.5, by), (bx + 6.5, by), (bx + 4, top), (bx - 4, top)]), fill=sil)
    d.polygon(P([(bx - 15, by + 6), (bx + 15, by + 6), (bx + 12, by - 12), (bx - 12, by - 12)]), fill=sil)
    # solar panel (tilted slab) + strut
    ang = math.radians(-24)
    pc = (bx + 34, top - 22)
    pl, pt = 170, 17
    cs, sn = math.cos(ang), math.sin(ang)
    corners = [(-pl / 2, -pt / 2), (pl / 2, -pt / 2), (pl / 2, pt / 2), (-pl / 2, pt / 2)]
    d.polygon(P([(pc[0] + x * cs - y * sn, pc[1] + x * sn + y * cs) for x, y in corners]), fill=sil)
    d.polygon(P([(bx - 4, top + 6), (bx + 4, top + 6), (pc[0] + 8, pc[1] + 6), (pc[0] - 8, pc[1] + 6)]), fill=sil)
    # panel grid hint (very subtle lighter lines)
    for k in (-0.33, 0.0, 0.33):
        x = k * pl
        a = (pc[0] + x * cs + (-pt / 2) * (-sn), pc[1] + x * sn + (-pt / 2) * cs)
        b = (pc[0] + x * cs + (pt / 2) * (-sn), pc[1] + x * sn + (pt / 2) * cs)
        d.line(P([a, b]), fill=(14, 66, 92, 255), width=int(1.8 * SS))
    # arm: quadratic bezier from pole to the left, ending in the lamp head
    p0, p1, p2 = (bx, top + 46), (bx - 20, top + 6), (bx - 128, top + 14)
    pts = []
    for i in range(41):
        t = i / 40
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    d.line(P(pts), fill=sil, width=int(6 * SS), joint='curve')
    # lamp head (rounded slab) slightly tilted
    lx, ly = bx - 138, top + 17
    d.rounded_rectangle([(lx - 46) * SS, (ly - 8) * SS, (lx + 40) * SS, (ly + 8) * SS], radius=8 * SS, fill=sil)
    # emitter (amber) on the underside
    d.rounded_rectangle([(lx - 38) * SS, (ly + 5) * SS, (lx + 30) * SS, (ly + 10) * SS], radius=2.5 * SS, fill=(255, 190, 110, 255))
    im = im.resize((cw, ch), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255.0
    S['pole_rgba'] = a
    S['pole_org'] = (ox, oy)
    S['lamp'] = (ox + lx - 4, oy + ly + 9)  # emission point in image coords
    # separate mask for the emitter so it can be driven by flicker
    em = np.zeros((ch, cw), np.float32)
    S['em_box'] = (lx - 38, ly + 5, lx + 30, ly + 10)


def glow_patch(cx, cy, R, shape_fn):
    pass


def add_region(img, ox, oy, patch, mode='add'):
    h, w = patch.shape[:2]
    x0, y0 = max(ox, 0), max(oy, 0)
    x1, y1 = min(ox + w, W), min(oy + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    p = patch[y0 - oy:y1 - oy, x0 - ox:x1 - ox]
    img[y0:y1, x0:x1] += p


def render(fi, ret_float=False):
    build_static()
    t = fi / FPS
    w = TAU * t / DUR  # base angular phase; harmonics use integer multiples
    xs, ys = S['xs'], S['ys']
    img = S['sky'].copy()

    # ---- stars (drawn before aurora so curtains veil them)
    sx, sy, sr, sb, sk, sp, sm = S['stars']
    white = np.array([0.93, 0.98, 0.98], np.float32)
    mint = np.array([0.72, 0.95, 0.85], np.float32)
    for i in range(len(sx)):
        tw = 0.68 + 0.32 * math.sin(sk[i] * w + sp[i])
        br = sb[i] * tw
        R = int(math.ceil(sr[i] + 2))
        cx0, cy0 = int(sx[i]), int(sy[i])
        gx = np.arange(cx0 - R, cx0 + R + 1, dtype=np.float32) + 0.5
        gy = np.arange(cy0 - R, cy0 + R + 1, dtype=np.float32) + 0.5
        dd = np.sqrt((gx[None, :] - sx[i]) ** 2 + (gy[:, None] - sy[i]) ** 2)
        m = np.clip(sr[i] + 0.5 - dd, 0, 1) * br
        col = (mint if sm[i] else white)
        patch = m[..., None] * col[None, None, :]
        # blend 'screen-ish' by simple lerp towards colour
        x0, y0 = cx0 - R, cy0 - R
        if x0 < 0 or y0 < 0 or x0 + patch.shape[1] > W or y0 + patch.shape[0] > H:
            continue
        reg = img[y0:y0 + patch.shape[0], x0:x0 + patch.shape[1]]
        mm = m[..., None]
        reg[:] = reg * (1 - mm) + col[None, None, :] * mm

    # ---- aurora curtains
    Y = ys[:, None]
    for c in CURTAINS:
        n1, n2, n3 = c['n']
        a1, a2, a3 = c['amp']
        l1, l2, l3 = c['lam']
        ph = c['ph']
        xw = xs + 38 * np.sin(TAU * xs / 1300 + ph + w)  # horizontal sway (1 cycle / 12 s)
        yb = (c['y0'] * H + a1 * np.sin(TAU * xw / l1 + ph + n1 * w)
              + a2 * np.sin(TAU * xw / l2 + 2 * ph - n2 * w)
              + a3 * np.sin(TAU * xs / l3 + 3 * ph + n3 * w))
        u = np.abs((xs / W - c['xc']) / c['hw'])
        env = np.exp(-(u ** 2.4) * 1.6)
        breathe = 1 + 0.10 * np.sin(TAU * xs / 900 + ph - w)
        h = c['h'] * H * env * breathe
        ytop = yb - h
        rays = (0.80 + 0.13 * np.sin(TAU * xw / c['rl'] + ph + 2 * w)
                + 0.07 * np.sin(TAU * xw / (c['rl'] * 0.41) + 2 * ph - w))
        op = c['op'] * (1 + 0.10 * np.sin(w * n1 + ph)) * rays * np.clip(env * 1.4, 0, 1) ** 0.7
        s = (Y - ytop[None, :]) / np.maximum((yb - ytop)[None, :], 1.0)
        sc = np.clip(s, 0, 1)
        edge = np.clip((yb[None, :] - Y) / 5.0 + 0.5, 0, 1)
        edge = edge * edge * (3 - 2 * edge)
        top_m = np.clip((Y - ytop[None, :]) / 2.0, 0, 1)
        alpha = (sc ** 1.15) * op[None, :] * edge * top_m * S['calm']
        col = lut(STOPS, sc)
        img = img * (1 - alpha[..., None]) + col * alpha[..., None]

    # ---- lamp glow in the sky (behind hills)
    px, py = S['pole']
    lampx, lampy = S['lamp']
    flick = 1.0 + 0.05 * math.sin(3 * w + 0.7) + 0.02 * math.sin(7 * w + 2.0)
    amber = np.array([1.0, 0.70, 0.36], np.float32)
    R = 330
    gx = np.arange(lampx - R, lampx + R, dtype=np.float32)
    gy = np.arange(lampy - R, lampy + R, dtype=np.float32)
    r = np.sqrt((gx[None, :] - lampx) ** 2 + (gy[:, None] - lampy) ** 2)
    g = (0.34 * np.exp(-r / 40.0) + 0.14 * np.exp(-r / 130.0)) * flick * (r < R)
    patch = g[..., None] * amber[None, None, :] * 0.8
    reg_y0, reg_x0 = lampy - R, lampx - R
    add_region(img, reg_x0, reg_y0, patch)

    # ---- hills
    img = img * (1 - S['mfar']) + S['colfar'] * S['mfar']
    img = img * (1 - S['mnear']) + S['colnear'] * S['mnear']

    # ---- light cone / ground pool from the lamp (over hills)
    Rc = 300
    cxs = np.arange(lampx - Rc, lampx + Rc, dtype=np.float32)
    cys = np.arange(lampy, lampy + 420, dtype=np.float32)
    dx = (cxs[None, :] - lampx)
    dy = (cys[:, None] - lampy) + 1.0
    ang = np.abs(dx) / dy
    cone = np.clip(1 - ang / 0.52, 0, 1) ** 1.5 * np.exp(-dy / 360.0)
    ground = np.exp(-((dx / 150.0) ** 2 + ((cys[:, None] - (py - 4)) / 16.0) ** 2))
    patch = (0.085 * cone + 0.24 * ground)[..., None] * amber[None, None, :] * flick
    add_region(img, lampx - Rc, lampy, patch)

    # ---- pole layer
    pr = S['pole_rgba']
    ox, oy = S['pole_org']
    ch_, cw_ = pr.shape[:2]
    x0, y0 = ox, oy
    cw_ = min(cw_, W - x0)
    pr = pr[:, :cw_]
    reg = img[y0:y0 + ch_, x0:x0 + cw_]
    al = pr[..., 3:4]
    rgb = pr[..., :3].copy()
    # emitter pixels (amber) pulse with flicker
    isem = (rgb[..., 0] > 0.9) & (rgb[..., 1] > 0.6)
    rgb[isem] = np.array([1.0, 0.74, 0.42], np.float32) * (0.92 + 0.08 * flick)
    reg[:] = reg * (1 - al) + rgb * al

    if ret_float:
        return img
    out = np.clip(img * 255.0 + 0.5 + S['noise'], 0, 255).astype(np.uint8)
    return out


def worker(fi):
    return render(fi).tobytes()


if __name__ == '__main__':
    work = sys.argv[1]
    os.makedirs(work, exist_ok=True)
    if '--only-frame' in sys.argv:
        k = int(sys.argv[sys.argv.index('--only-frame') + 1])
        Image.fromarray(render(k)).save(os.path.join(work, f'hero_f{k:03d}.png'))
        sys.exit(0)
    nf = NF
    if '--frames' in sys.argv:
        nf = int(sys.argv[sys.argv.index('--frames') + 1])
    out = os.path.join(work, 'hero_lossless.mkv')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'gbrp', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(18) as pool:
        for i, b in enumerate(pool.imap(worker, range(nf), chunksize=1)):
            p.stdin.write(b)
            if i % 30 == 0:
                print('frame', i, flush=True)
    p.stdin.close()
    p.wait()
    print('done')
