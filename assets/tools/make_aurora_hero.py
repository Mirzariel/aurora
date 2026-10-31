"""AURORA hero background (revisi 2): flat aurora, langit hampir hitam kebiruan, tirai vertikal semi-transparan
dengan tepi bawah melengkung, gradasi selaras logo (biru #0a5ca6 -> teal #1aa7c4 -> hijau #2cc7a8/#4fe0b3 -> mint #9af7cb),
tiang lampu surya (skala 1,3x) di ~70% lebar dengan dua denyut hijau "melapor" per putaran.
Prosedural (numpy + Pillow); semua ketergantungan waktu = sin/cos dengan siklus bulat per 12 s => loop mulus.

Usage: python make_aurora_hero.py <workdir> [--frames N] [--only-frame K[,K2,...]]
Menulis <workdir>/hero_lossless.mkv (FFV1). Encode: lihat perintah di laporan / README.
"""
import sys, os, subprocess, math
import numpy as np
from PIL import Image, ImageDraw
from multiprocessing import Pool

W, H, FPS, DUR = 1920, 1080, 30, 12
NF = FPS * DUR
TAU = 2 * math.pi
K = 1.3                       # skala tiang
POLE_X = 0.70                 # posisi tiang (fraksi lebar)
PULSE_T = (2.6, 8.6)          # dua denyut "melapor" (detik)
PULSE_D = 1.7
GREEN = np.array([0.31, 0.88, 0.70], np.float32)   # #4fe0b3


def hexc(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32) / 255.0


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def lut(stops, s):
    pos = [p for p, _ in stops]
    cols = np.stack([hexc(c) for _, c in stops])
    return np.stack([np.interp(s, pos, cols[:, k]) for k in range(3)], -1).astype(np.float32)


S = {}


def hill_y(x, base, comps):
    y = np.full_like(x, base)
    for amp, wl, ph in comps:
        y += amp * np.sin(TAU * x / wl + ph)
    return y


# xc: pusat, hw: setengah lebar, y0: tepi bawah (fraksi H), h: tinggi, op: opasitas dasar, rl: panjang gelombang sinar,
# sh: pergeseran nuansa dasar (+ = lebih hijau/mint, - = lebih biru/teal), k1: siklus intensitas, k2: siklus nuansa
CURTAINS = [
    dict(xc=0.46, hw=0.46, y0=0.560, h=0.36, op=0.62, rl=210, ph=0.6, n=(1, 2, 3), amp=(46, 24, 12), lam=(1500, 760, 410), sh=-0.10, k1=1, k2=2),
    dict(xc=0.96, hw=0.38, y0=0.520, h=0.33, op=0.58, rl=170, ph=2.3, n=(2, 1, 3), amp=(40, 22, 10), lam=(1100, 640, 330), sh=-0.16, k1=2, k2=1),
    dict(xc=0.76, hw=0.50, y0=0.625, h=0.40, op=0.78, rl=240, ph=4.1, n=(1, 3, 2), amp=(52, 26, 11), lam=(1700, 820, 450), sh=0.06, k1=1, k2=3),
    dict(xc=0.24, hw=0.34, y0=0.640, h=0.25, op=0.46, rl=190, ph=1.4, n=(2, 1, 1), amp=(30, 18, 8), lam=(1300, 700, 380), sh=0.00, k1=3, k2=1),
]
# gradasi vertikal tirai (s=0 puncak, s=1 tepi bawah) - warna logo
STOPS = [(0.0, '#0a5ca6'), (0.30, '#1aa7c4'), (0.58, '#2cc7a8'), (0.80, '#4fe0b3'), (1.0, '#9af7cb')]


def build_static():
    if S:
        return
    xs = np.arange(W, dtype=np.float32)
    ys = np.arange(H, dtype=np.float32)
    S['xs'], S['ys'] = xs, ys
    sky = lut([(0.0, '#04080f'), (0.45, '#061220'), (0.70, '#07192a'), (0.80, '#08233a'), (0.865, '#0a3550'), (1.0, '#0a3550')], ys / H)
    S['sky'] = np.repeat(sky[:, None, :], W, 1)
    far = hill_y(xs, 0.865 * H, [(14, 1750, 1.1), (8, 640, 2.0), (3, 230, 0.4)])
    near = hill_y(xs, 0.945 * H, [(12, 1450, 0.4), (6, 520, 3.1), (2.5, 190, 1.7)])
    S['far'], S['near'] = far, near
    Y = ys[:, None]
    S['mfar'] = np.clip((Y - far[None, :]) + 0.5, 0, 1)[..., None]
    S['mnear'] = np.clip((Y - near[None, :]) + 0.5, 0, 1)[..., None]
    rid = np.clip((Y - far[None, :]) / 90.0, 0, 1)
    S['colfar'] = hexc('#07203a')[None, None, :] * (1 - rid[..., None]) + hexc('#041421')[None, None, :] * rid[..., None]
    S['colnear'] = hexc('#02080e')[None, None, :]
    px = int(POLE_X * W)
    py = int(near[px]) + 4
    S['pole'] = (px, py)
    rng = np.random.default_rng(7)
    n = 120
    S['stars'] = (rng.uniform(10, W - 10, n), rng.uniform(8, 0.60 * H, n),
                  rng.choice([0.9, 1.2, 1.6, 2.1], n, p=[0.35, 0.35, 0.22, 0.08]), rng.uniform(0.5, 1.0, n),
                  rng.choice([1, 2, 3, 4], n), rng.uniform(0, TAU, n), rng.random(n) < 0.45)
    r = np.random.default_rng(3)
    S['noise'] = (r.random((H, W, 3), dtype=np.float32) + r.random((H, W, 3), dtype=np.float32) - 1.0) * 1.05  # dither segitiga +-1.05 LSB
    build_pole(px, py)
    L = 1 - smoothstep(0.12 * W, 0.58 * W, xs)
    U = 1 - smoothstep(0.30 * H, 0.62 * H, ys)
    S['calm'] = (1 - 0.65 * (U[:, None] * L[None, :])).astype(np.float32)


def build_pole(px, py):
    SS = 3
    cw, ch = 920, 640
    bx, by = 580, 600
    ox, oy = px - bx, py - by
    im = Image.new('RGBA', (cw * SS, ch * SS), (0, 0, 0, 0))
    ac = Image.new('L', (cw * SS, ch * SS), 0)          # aksen (panel, LED) untuk denyut hijau
    d, da = ImageDraw.Draw(im), ImageDraw.Draw(ac)
    sil = (2, 9, 15, 255)

    def P(pts):
        return [(bx * SS + x * K * SS, by * SS + y * K * SS) for x, y in pts]

    top = -300
    d.polygon(P([(-7.5, 0), (7.5, 0), (4.6, top), (-4.6, top)]), fill=sil)
    d.polygon(P([(-17, 6), (17, 6), (13.5, -12), (-13.5, -12)]), fill=sil)
    # panel surya
    ang = math.radians(-24)
    pc = (34, top - 22)
    pl, pt = 170, 18
    cs, sn = math.cos(ang), math.sin(ang)
    corners = [(-pl / 2, -pt / 2), (pl / 2, -pt / 2), (pl / 2, pt / 2), (-pl / 2, pt / 2)]
    tr = lambda cx, cy, l, t: [(pc[0] + x * cs - y * sn, pc[1] + x * sn + y * cs) for x, y in ((-l / 2, -t / 2), (l / 2, -t / 2), (l / 2, t / 2), (-l / 2, t / 2))]
    d.polygon(P(tr(0, 0, pl, pt)), fill=sil)
    d.polygon(P([(-4.6, top + 6), (4.6, top + 6), (pc[0] + 9, pc[1] + 6), (pc[0] - 9, pc[1] + 6)]), fill=sil)
    # muka panel (aksen) : inset + garis sel
    da.polygon(P(tr(0, 0, pl - 14, pt - 7)), fill=150)
    for k in (-0.33, 0.0, 0.33):
        x = k * pl
        a = (pc[0] + x * cs + (-pt / 2) * (-sn), pc[1] + x * sn + (-pt / 2) * cs)
        b = (pc[0] + x * cs + (pt / 2) * (-sn), pc[1] + x * sn + (pt / 2) * cs)
        da.line(P([a, b]), fill=255, width=int(2.2 * K * SS))
    # lengan + kepala lampu
    p0, p1, p2 = (0, top + 46), (-20, top + 6), (-128, top + 14)
    pts = []
    for i in range(41):
        t = i / 40
        pts.append(((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
                    (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1]))
    d.line(P(pts), fill=sil, width=int(7 * K * SS), joint='curve')
    lx, ly = -138, top + 17
    d.rounded_rectangle([bx * SS + (lx - 46) * K * SS, by * SS + (ly - 8) * K * SS, bx * SS + (lx + 40) * K * SS, by * SS + (ly + 8) * K * SS], radius=8 * K * SS, fill=sil)
    d.rounded_rectangle([bx * SS + (lx - 38) * K * SS, by * SS + (ly + 5) * K * SS, bx * SS + (lx + 30) * K * SS, by * SS + (ly + 10) * K * SS], radius=2.5 * K * SS, fill=(255, 190, 110, 255))
    # LED status kecil di badan tiang + di kepala lampu (aksen hijau)
    for (cx_, cy_, r_) in ((0, -150, 4.2), (lx + 38, ly - 2, 3.2)):
        da.ellipse([bx * SS + (cx_ - r_) * K * SS, by * SS + (cy_ - r_) * K * SS, bx * SS + (cx_ + r_) * K * SS, by * SS + (cy_ + r_) * K * SS], fill=255)
    # modul kecil di badan tiang
    d.rounded_rectangle([bx * SS - 9 * K * SS, by * SS - 162 * K * SS, bx * SS + 9 * K * SS, by * SS - 138 * K * SS], radius=3 * K * SS, fill=sil)
    da.ellipse([bx * SS - 4.2 * K * SS, by * SS - 154.2 * K * SS, bx * SS + 4.2 * K * SS, by * SS - 145.8 * K * SS], fill=255)

    im = im.resize((cw, ch), Image.LANCZOS)
    ac = ac.resize((cw, ch), Image.LANCZOS)
    S['pole_rgba'] = np.asarray(im).astype(np.float32) / 255.0
    S['pole_acc'] = np.asarray(ac).astype(np.float32)[..., None] / 255.0
    S['pole_org'] = (ox, oy)
    S['lamp'] = (ox + bx + (lx - 4) * K, oy + by + (ly + 9) * K)
    S['panel_c'] = (ox + bx + pc[0] * K, oy + by + pc[1] * K)
    S['led_c'] = (ox + bx, oy + by - 150 * K)


def add_region(img, ox, oy, patch):
    h, w = patch.shape[:2]
    x0, y0 = max(ox, 0), max(oy, 0)
    x1, y1 = min(ox + w, W), min(oy + h, H)
    if x1 <= x0 or y1 <= y0:
        return
    img[y0:y1, x0:x1] += patch[y0 - oy:y1 - oy, x0 - ox:x1 - ox]


def pulse_env(t):
    v = 0.0
    for tp in PULSE_T:
        u = (t - tp) / PULSE_D
        if 0 < u < 1:
            v = max(v, math.sin(math.pi * u) ** 2)
    return v


def render(fi, ret_float=False):
    build_static()
    t = fi / FPS
    w = TAU * t / DUR
    xs, ys = S['xs'], S['ys']
    img = S['sky'].copy()

    # ---- bintang
    sx, sy, sr, sb, sk, sp, sm = S['stars']
    white = np.array([0.93, 0.98, 0.98], np.float32)
    mint = np.array([0.72, 0.95, 0.88], np.float32)
    for i in range(len(sx)):
        tw = 0.68 + 0.32 * math.sin(sk[i] * w + sp[i])
        br = sb[i] * tw
        R = int(math.ceil(sr[i] + 2))
        cx0, cy0 = int(sx[i]), int(sy[i])
        gx = np.arange(cx0 - R, cx0 + R + 1, dtype=np.float32) + 0.5
        gy = np.arange(cy0 - R, cy0 + R + 1, dtype=np.float32) + 0.5
        dd = np.sqrt((gx[None, :] - sx[i]) ** 2 + (gy[:, None] - sy[i]) ** 2)
        m = np.clip(sr[i] + 0.5 - dd, 0, 1) * br
        col = mint if sm[i] else white
        x0, y0 = cx0 - R, cy0 - R
        if x0 < 0 or y0 < 0 or x0 + m.shape[1] > W or y0 + m.shape[0] > H:
            continue
        reg = img[y0:y0 + m.shape[0], x0:x0 + m.shape[1]]
        mm = m[..., None]
        reg[:] = reg * (1 - mm) + col[None, None, :] * mm

    # ---- tirai aurora
    Y = ys[:, None]
    for c in CURTAINS:
        n1, n2, n3 = c['n']
        a1, a2, a3 = c['amp']
        l1, l2, l3 = c['lam']
        ph = c['ph']
        xw = xs + 38 * np.sin(TAU * xs / 1300 + ph + w)
        yb = (c['y0'] * H + a1 * np.sin(TAU * xw / l1 + ph + n1 * w)
              + a2 * np.sin(TAU * xw / l2 + 2 * ph - n2 * w)
              + a3 * np.sin(TAU * xs / l3 + 3 * ph + n3 * w))
        u = np.abs((xs / W - c['xc']) / c['hw'])
        env = np.exp(-(u ** 2.4) * 1.5)
        breathe = 1 + 0.10 * np.sin(TAU * xs / 900 + ph - w)
        # sinar vertikal: pita-pita tegas (tirai terbaca), tinggi puncak ikut bervariasi
        r1 = 0.5 + 0.5 * np.sin(TAU * xw / c['rl'] + ph + 2 * w)
        r2 = 0.5 + 0.5 * np.sin(TAU * xw / (c['rl'] * 0.43) + 2 * ph - w)
        r3 = 0.5 + 0.5 * np.sin(TAU * xw / (c['rl'] * 2.7) + 3 * ph + 3 * w)
        rays = 0.50 + 0.30 * r1 + 0.12 * r2 + 0.08 * r3
        h = c['h'] * H * env * breathe * (0.84 + 0.30 * r3)
        ytop = yb - h
        # variasi intensitas periodik antar-pita (+-34%) dan nuansa (geser gradasi)
        pop = 1 + 0.34 * math.sin(c['k1'] * w + 1.7 * ph) + 0.10 * np.sin(TAU * xs / 1700 + ph - w)
        op = c['op'] * pop * rays * np.clip(env * 1.4, 0, 1) ** 0.7
        shift = c['sh'] + 0.17 * math.sin(c['k2'] * w + 2.3 * ph) + 0.07 * np.sin(TAU * xs / 1500 + ph + w)
        s = (Y - ytop[None, :]) / np.maximum((yb - ytop)[None, :], 1.0)
        sc = np.clip(s, 0, 1)
        edge = np.clip((yb[None, :] - Y) / 2.2 + 0.5, 0, 1)       # tepi bawah lebih tegas
        edge = edge * edge * (3 - 2 * edge)
        top_m = np.clip((Y - ytop[None, :]) / 2.0, 0, 1)
        alpha = (sc ** 1.30) * op[None, :] * edge * top_m * S['calm']
        alpha = np.minimum(alpha, 0.92)
        col = lut(STOPS, np.clip(sc + np.broadcast_to(np.asarray(shift, np.float32), (xs.shape[0],))[None, :] * (0.3 + 0.7 * sc), 0, 1))
        img = img * (1 - alpha[..., None]) + col * alpha[..., None]

    px, py = S['pole']
    lampx, lampy = int(round(S['lamp'][0])), int(round(S['lamp'][1]))
    flick = 1.0 + 0.05 * math.sin(3 * w + 0.7) + 0.02 * math.sin(7 * w + 2.0)
    amber = np.array([1.0, 0.70, 0.36], np.float32)
    pe = pulse_env(t)

    # ---- cahaya lampu di langit (di belakang bukit)
    R = int(330 * K)
    gx = np.arange(lampx - R, lampx + R, dtype=np.float32)
    gy = np.arange(lampy - R, lampy + R, dtype=np.float32)
    r = np.sqrt((gx[None, :] - lampx) ** 2 + (gy[:, None] - lampy) ** 2)
    g = (0.30 * np.exp(-r / (40.0 * K)) + 0.12 * np.exp(-r / (130.0 * K))) * flick * (r < R)
    add_region(img, lampx - R, lampy - R, g[..., None] * amber[None, None, :] * 0.8)

    # ---- bukit
    img = img * (1 - S['mfar']) + S['colfar'] * S['mfar']
    img = img * (1 - S['mnear']) + S['colnear'] * S['mnear']

    # ---- kerucut cahaya + genangan tanah
    Rc = int(300 * K)
    cxs = np.arange(lampx - Rc, lampx + Rc, dtype=np.float32)
    cys = np.arange(lampy, lampy + int(420 * K), dtype=np.float32)
    dx = cxs[None, :] - lampx
    dy = (cys[:, None] - lampy) + 1.0
    cone = np.clip(1 - np.abs(dx) / dy / 0.52, 0, 1) ** 1.5 * np.exp(-dy / (360.0 * K))
    ground = np.exp(-((dx / (150.0 * K)) ** 2 + ((cys[:, None] - (py - 4)) / (16.0 * K)) ** 2))
    add_region(img, lampx - Rc, lampy, (0.075 * cone + 0.20 * ground)[..., None] * amber[None, None, :] * flick)

    # ---- denyut hijau halus (melapor): cahaya di panel + cincin tipis
    pcx, pcy = S['panel_c']
    if pe > 0.002:
        Rg = 260
        gx = np.arange(int(pcx) - Rg, int(pcx) + Rg, dtype=np.float32)
        gy = np.arange(int(pcy) - Rg, int(pcy) + Rg, dtype=np.float32)
        rr = np.sqrt((gx[None, :] - pcx) ** 2 + (gy[:, None] - pcy) ** 2)
        gl = (0.16 * np.exp(-rr / 55.0) + 0.05 * np.exp(-rr / 150.0)) * pe
        add_region(img, int(pcx) - Rg, int(pcy) - Rg, gl[..., None] * GREEN[None, None, :])
        # cincin yang melebar dari panel (hanya garis tipis, lembut)
        for kk, (tp) in enumerate(PULSE_T):
            uu = (t - tp) / (PULSE_D * 1.35)
            if 0 < uu < 1:
                rad = 24 + 230 * (1 - (1 - uu) ** 2)
                ring = np.exp(-((rr - rad) / 3.2) ** 2) * (0.30 * (1 - uu) ** 1.6)
                add_region(img, int(pcx) - Rg, int(pcy) - Rg, ring[..., None] * GREEN[None, None, :] * (rr < Rg)[..., None])

    # ---- tiang
    pr = S['pole_rgba']
    ox, oy = S['pole_org']
    ch_, cw_ = pr.shape[:2]
    x0, y0 = ox, oy
    cw_ = min(cw_, W - x0)
    pr = pr[:, :cw_]
    reg = img[y0:y0 + ch_, x0:x0 + cw_]
    al = pr[..., 3:4]
    rgb = pr[..., :3].copy()
    isem = (rgb[..., 0] > 0.9) & (rgb[..., 1] > 0.6)
    rgb[isem] = np.array([1.0, 0.74, 0.42], np.float32) * (0.92 + 0.08 * flick)
    reg[:] = reg * (1 - al) + rgb * al
    # aksen hijau (panel + LED): redup permanen, menyala saat denyut
    acc = S['pole_acc'][:, :cw_]
    lvl = 0.10 + 0.78 * pe
    reg[:] = reg + acc * GREEN[None, None, :] * lvl * al.clip(0.5, 1)
    ledx, ledy = S['led_c']
    # halo kecil LED
    Rl = 70
    gx = np.arange(int(ledx) - Rl, int(ledx) + Rl, dtype=np.float32)
    gy = np.arange(int(ledy) - Rl, int(ledy) + Rl, dtype=np.float32)
    rr2 = np.sqrt((gx[None, :] - ledx) ** 2 + (gy[:, None] - ledy) ** 2)
    add_region(img, int(ledx) - Rl, int(ledy) - Rl, (np.exp(-rr2 / 12.0) * (0.04 + 0.34 * pe))[..., None] * GREEN[None, None, :])

    if ret_float:
        return img
    return np.clip(img * 255.0 + 0.5 + S['noise'], 0, 255).astype(np.uint8)


def worker(fi):
    return render(fi).tobytes()


if __name__ == '__main__':
    work = sys.argv[1]
    os.makedirs(work, exist_ok=True)
    if '--only-frame' in sys.argv:
        for k in sys.argv[sys.argv.index('--only-frame') + 1].split(','):
            Image.fromarray(render(int(k))).save(os.path.join(work, f'hero_f{int(k):03d}.png'))
        sys.exit(0)
    nf = NF
    if '--frames' in sys.argv:
        nf = int(sys.argv[sys.argv.index('--frames') + 1])
    out = os.path.join(work, 'hero_lossless.mkv')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'gbrp', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(12) as pool:
        for i, b in enumerate(pool.imap(worker, range(nf), chunksize=1)):
            p.stdin.write(b)
            if i % 30 == 0:
                print('frame', i, flush=True)
    p.stdin.close()
    p.wait()
    print('done')
