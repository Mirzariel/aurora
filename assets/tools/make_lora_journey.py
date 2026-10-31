"""AURORA 'lora-journey' explainer loop (21 s, 30 fps, 1920x1080), revisi 2.
Procedural (Pillow 2x supersample + numpy glow). Kamera bergeser mengikuti paket; semua node selalu tampak
(redup bila belum aktif) sehingga tidak pernah ada layar kosong. State pada t=21 s identik dengan t=0
(kamera di posisi awal, semua node kembali redup, hanya tiang + pil SENSE menyala, judul sama).

Aturan teks: tidak ada teks yang memudar (alpha selalu 1); pergantian judul berupa potongan cepat.
Label kejujuran permanen: "Ilustrasi alur satu paket"; relay berlabel "Relay (emulasi)";
momen paket hilang berlabel "Paket hilang (contoh ilustrasi)". Tidak ada angka performa.

Usage: python make_lora_journey.py <workdir> [--only-frame K] [--frames N]
"""
import sys, os, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from multiprocessing import Pool

W, H, FPS, DUR = 1920, 1080, 30, 22
NF = FPS * DUR
S = 2                      # supersample
K = 1.4                    # skala objek
LWB = 1.25                 # penebal garis
TAU = 2 * math.pi
FONT_B = r'C:\Windows\Fonts\segoeuib.ttf'


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    t = min(max(t, 0.0), 1.0)
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ss(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def eo(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return 1 - (1 - t) ** 3


def rgba(c, a=1.0):
    return (int(round(c[0])), int(round(c[1])), int(round(c[2])), int(round(255 * min(max(a, 0), 1))))


BODY = hexc('#0d4a78')
BODY_D = hexc('#0a3354')
RIM = hexc('#2cc7a8')
MINT = hexc('#4fe0b3')
MINT_L = hexc('#9af7cb')
TEAL = hexc('#3cc3dc')
AMBER = hexc('#ffb45a')
LOSS = hexc('#ff9a4a')       # oranye-amber lembut untuk momen paket hilang
WHITE = hexc('#f4fbf8')
TXT = hexc('#e6f9f0')
RIM_DIM = hexc('#2f7a96')
BODY_DIM = hexc('#0a2e4a')
BODY_D_DIM = hexc('#082540')
DARK = hexc('#082a42')

# ---- layout dunia (px layar pada kamera L=0)
G = 760                              # garis tanah
XT, XR, XS, XC, XD = 300, 1000, 1650, 2300, 2950
CAM_KEYS = [(0.0, 0), (4.4, 0), (6.0, 560), (6.2, 560), (7.6, 1050), (8.9, 1050), (10.3, 1350), (12.2, 1350), (13.5, 0)]

CAPS = [
    (0.0, 2.8, 'Sensor membaca kondisi tiang'),
    (2.8, 4.2, 'Data dirangkum jadi satu paket'),
    (4.2, 6.0, 'Paket dikirim lewat radio LoRa'),
    (6.0, 7.4, 'Relay meneruskan paket'),
    (7.4, 8.8, 'Sink mengumpulkan paket'),
    (8.8, 10.4, 'Jaringan seluler menuju cloud'),
    (10.4, 12.2, 'Dashboard menampilkan status'),
    (12.2, 15.6, 'Kadang paket hilang di perjalanan'),
    (15.6, 19.4, 'Dikirim ulang sampai ACK diterima'),
    (19.4, 22.0, 'Sensor membaca kondisi tiang'),   # kembali ke awal (loop)
]
PILLS = [('SENSE', 0.0), ('UNDERSTAND', 2.8), ('DELIVER', 4.2), ('ACT', 11.2)]
PILL_Y = 987
PILL_H = 104
T_RESET0, T_RESET1 = 19.6, 20.8      # semua node kembali redup
T_ON = dict(relay=5.6, sink=7.0, cloud=9.4, dash=10.8)

ST = {}


def font(px):
    k = ('f', px)
    if k not in ST:
        ST[k] = ImageFont.truetype(FONT_B, int(round(px * S)))
    return ST[k]


class Lay:
    """Kanvas RGBA supersampled. Koordinat desain dikalikan k; origin kanvas = (left, up) px."""

    def __init__(self, left, up, right, down, k=K, lwb=LWB):
        self.OX, self.OY, self.k, self.lwb = left, up, k, lwb
        self.w, self.h = left + right, up + down
        self.im = Image.new('RGBA', (int(self.w * S), int(self.h * S)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im, 'RGBA')

    def p(self, x, y):
        return ((x * self.k + self.OX) * S, (y * self.k + self.OY) * S)

    def lw(self, w):
        return max(1, int(round(w * self.k * self.lwb * S)))

    def poly(self, pts, fill=None, outline=None, width=0):
        pp = [self.p(*q) for q in pts]
        if fill is not None:
            self.d.polygon(pp, fill=fill)
        if outline is not None and width:
            self.d.line(pp + [pp[0]], fill=outline, width=self.lw(width), joint='curve')

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, width=0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        self.d.rounded_rectangle([a, b], radius=r * self.k * S, fill=fill, outline=outline, width=self.lw(width) if outline else 0)

    def circle(self, x, y, r, fill=None, outline=None, width=0):
        a, b = self.p(x - r, y - r), self.p(x + r, y + r)
        self.d.ellipse([a, b], fill=fill, outline=outline, width=self.lw(width) if outline else 0)

    def line(self, pts, fill, width):
        self.d.line([self.p(*q) for q in pts], fill=fill, width=self.lw(width), joint='curve')

    def arc(self, x, y, r, a0, a1, fill, width):
        a, b = self.p(x - r, y - r), self.p(x + r, y + r)
        self.d.arc([a, b], a0, a1, fill=fill, width=self.lw(width))

    def text(self, x, y, s, px, fill, anchor='mm'):
        self.d.text(self.p(x, y), s, font=font(px), fill=fill, anchor=anchor)


def paste_clip(dst, src, x, y):
    sw, sh = src.size
    dw, dh = dst.size
    x0, y0, x1, y1 = max(x, 0), max(y, 0), min(x + sw, dw), min(y + sh, dh)
    if x1 <= x0 or y1 <= y0:
        return
    dst.alpha_composite(src.crop((x0 - x, y0 - y, x1 - x, y1 - y)), dest=(x0, y0))


def paste_node(main, lay, wx, wy, L):
    """base node ada di (wx - L, wy) pada layar."""
    x = int(round((wx - L - lay.OX) * S))
    y = int(round((wy - lay.OY) * S))
    paste_clip(main.im, lay.im, x, y)


def bez(p0, p1, lift, u):
    cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - lift
    return ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * cx + u * u * p1[0],
            (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * cy + u * u * p1[1])


def rot_rect(cx, cy, l, t, ang):
    cs, sn = math.cos(ang), math.sin(ang)
    return [(cx + x * cs - y * sn, cy + x * sn + y * cs) for x, y in ((-l / 2, -t / 2), (l / 2, -t / 2), (l / 2, t / 2), (-l / 2, t / 2))]


def camera(t):
    for (t0, x0), (t1, x1) in zip(CAM_KEYS, CAM_KEYS[1:]):
        if t0 <= t <= t1:
            return x0 + (x1 - x0) * ss(t0, t1, t)
    return CAM_KEYS[-1][1] if t > CAM_KEYS[-1][0] else CAM_KEYS[0][1]


# ---- titik penting (koordinat dunia)
A_T = (XT, G - 140 * K)                    # modul sensor
P_START = (XT + 66, A_T[1] - 46)           # paket muncul di samping sensor
A_R = (XR, G - 289 * K)                    # ujung antena relay
A_S = (XS + 40 * K, G - 163 * K)           # ujung antena sink
A_C = (XC, G - 275 * K)                    # pusat awan
A_CL = (XC - 105 * K, A_C[1] + 26)         # sisi kiri awan
A_CR = (XC + 100 * K, A_C[1] + 34)         # sisi kanan awan
A_DT = (XD - 110 * K, G - 232 * K)         # sisi atas-kiri dashboard


def static():
    if 'bg' in ST:
        return
    ys = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(W, dtype=np.float32)[None, :]
    top, mid, bot = (np.array(hexc(c), np.float32) / 255 for c in ('#04080f', '#071522', '#0a3550'))
    t = (ys / H)[:, 0:1]
    rows = np.where(t < 0.5, top + (mid - top) * (t / 0.5), mid + (bot - mid) * ((t - 0.5) / 0.5))
    bg = np.broadcast_to(rows[:, None, :], (H, W, 3)).copy()
    hz = np.exp(-(((xs - 1000) / 1000.0) ** 2 + ((ys - 780) / 300.0) ** 2))[..., None]
    bg += hz * np.array([0.015, 0.10, 0.08], np.float32) * 0.8
    vg = 1 - 0.20 * (((xs - W / 2) / (W / 2)) ** 2 * 0.6 + ((ys - H / 2) / (H / 2)) ** 2 * 0.4)
    bg *= vg[..., None]
    ST['bg'] = bg.astype(np.float32)
    rng = np.random.default_rng(11)
    n = 70
    ST['stars'] = (rng.uniform(-200, W + 200, n), rng.uniform(20, 640, n), rng.uniform(0.9, 1.9, n),
                   rng.uniform(0.3, 0.75, n), rng.choice([1, 2, 3], n), rng.uniform(0, TAU, n))
    ST['noise'] = (np.random.default_rng(5).random((H, W, 3), dtype=np.float32) - 0.5) * 1.3
    # geometri pil
    c = Lay(0, 0, 10, 10, k=1)
    wd = [c.d.textlength(nm, font=font(52)) / S + 84 for nm, _ in PILLS]
    gap = 78
    total = sum(wd) + gap * (len(wd) - 1)
    x = (W - total) / 2
    geo = []
    for w_ in wd:
        geo.append((x, x + w_))
        x += w_ + gap
    ST['pills'] = geo


# ----------------------------------------------------------------- node layers (origin = pusat dasar, y ke atas negatif)
def cols(act):
    return dict(rim=mix(RIM_DIM, RIM, act), body=mix(BODY_DIM, BODY, act), bd=mix(BODY_D_DIM, BODY_D, act))


def tiang_layer(pulse, flash, check):
    c = Lay(300, 520, 330, 44)
    q = cols(1.0)
    rim, body, bd = rgba(q['rim']), rgba(q['body']), rgba(q['bd'])
    c.rrect(-30, -16, 30, 4, 6, fill=bd, outline=rim, width=2.6)
    c.poly([(-10, -14), (10, -14), (6.5, -300), (-6.5, -300)], fill=body, outline=rim, width=3)
    top = -300
    # lengan + kepala lampu (kiri)
    pts = []
    p0, p1, p2 = (0, top + 40), (-18, top + 4), (-100, top + 12)
    for i in range(25):
        u = i / 24
        pts.append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]))
    c.line(pts, rim, 11)
    c.line(pts, body, 6)
    lx, ly = -108, top + 15
    c.rrect(lx - 38, ly - 9, lx + 32, ly + 9, 8, fill=body, outline=rim, width=2.6)
    c.rrect(lx - 32, ly + 4, lx + 26, ly + 10, 3, fill=rgba(AMBER))
    # panel surya
    pc = (28, top - 20)
    c.poly([(-4, top + 6), (4, top + 6), (pc[0] + 8, pc[1] + 6), (pc[0] - 8, pc[1] + 6)], fill=body, outline=rim, width=2.4)
    c.poly(rot_rect(pc[0], pc[1], 156, 19, math.radians(-22)), fill=bd, outline=rgba(MINT), width=3)
    for k in (-0.3, 0.0, 0.3):
        ax = pc[0] + k * 156 * math.cos(math.radians(-22))
        ay = pc[1] + k * 156 * math.sin(math.radians(-22))
        c.line([(ax + 5, ay - 5), (ax - 5, ay + 6)], rgba(MINT, .6), 2.2)
    # modul sensor
    sy = -140
    c.rrect(-28, sy - 28, 28, sy + 28, 11, fill=bd, outline=rgba(MINT), width=3.4)
    if check > 0.01:
        c.circle(0, sy, 14, fill=rgba(WHITE))
        c.line([(-6.5, sy + 0.5), (-1.5, sy + 6), (7.5, sy - 5.5)], rgba(hexc('#0a6a4a')), 3.6)
    else:
        r = 8.5 + 3 * pulse
        c.circle(0, sy, r, fill=rgba(mix(MINT, WHITE, flash)))
    return c


def relay_layer(act, flash):
    c = Lay(300, 480, 300, 44)
    q = cols(act)
    rim, body, bd = rgba(q['rim']), rgba(q['body']), rgba(q['bd'])
    lit = mix(RIM_DIM, MINT, act)
    top = -250
    c.rrect(-30, -16, 30, 4, 6, fill=bd, outline=rim, width=2.6)
    c.poly([(-10, -14), (10, -14), (6.5, top), (-6.5, top)], fill=body, outline=rim, width=3)
    pts = []
    p0, p1, p2 = (0, top + 40), (-18, top + 4), (-100, top + 12)
    for i in range(25):
        u = i / 24
        pts.append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]))
    c.line(pts, rim, 11)
    c.line(pts, body, 6)
    lx, ly = -108, top + 15
    c.rrect(lx - 38, ly - 9, lx + 32, ly + 9, 8, fill=body, outline=rim, width=2.6)
    c.rrect(lx - 32, ly + 4, lx + 26, ly + 10, 3, fill=rgba(mix(BODY_DIM, AMBER, 0.35 + 0.65 * act)))
    # mast antena + panel kecil
    c.line([(0, top + 4), (0, top - 30)], rim, 8)
    c.line([(0, top + 4), (0, top - 30)], body, 4)
    c.circle(0, top - 36, 9, fill=rgba(mix(bd, MINT, 0.9 * flash)), outline=rgba(lit), width=3.2)
    pc = (42, top + 6)
    c.poly(rot_rect(pc[0], pc[1], 100, 14, math.radians(-18)), fill=bd, outline=rgba(lit), width=2.8)
    c.line([(6, top + 24), (pc[0] - 4, pc[1] + 3)], rim, 3.6)
    # modul radio kecil di tiang
    c.rrect(-20, -118, 20, -78, 8, fill=bd, outline=rgba(lit), width=3)
    c.circle(0, -98, 6.5 + 2.5 * flash, fill=rgba(mix(hexc('#1b5b6c'), MINT, act)))
    return c


def sink_layer(act, flash):
    c = Lay(240, 340, 240, 44)
    q = cols(act)
    rim, body, bd = rgba(q['rim']), rgba(q['body']), rgba(q['bd'])
    c.rrect(-100, -112, 100, 0, 18, fill=body, outline=rim, width=3.4)
    c.rrect(-100, -112, 100, -76, 16, fill=bd, outline=rim, width=3.4)
    c.line([(40, -112), (40, -156)], rim, 8)
    c.line([(40, -112), (40, -156)], body, 4)
    c.circle(40, -163, 9, fill=rgba(mix(bd, MINT, 0.15 + 0.85 * flash * act)), outline=rgba(mix(RIM_DIM, MINT, act)), width=3)
    for i in range(3):
        on = ss(0.0, 1.0, act * 1.0 - i * 0.2)
        col = mix(hexc('#1b5b6c'), MINT if i < 2 else AMBER, on)
        c.circle(-62 + i * 32, -94, 8.5, fill=rgba(col))
    for i in range(3):
        c.rrect(-68 + i * 54, -52, -30 + i * 54, -26, 5, fill=rgba(DARK), outline=rgba(q['rim'], .7), width=2.2)
    return c


def cloud_layer(act, flash):
    c = Lay(300, 170, 300, 170)
    q = cols(act)
    parts = [(-62, 6, 38), (-12, -20, 54), (46, -2, 42)]
    for k in (4.5, 0):
        col = rgba(q['rim']) if k else rgba(mix(q['body'], MINT, 0.12 * flash))
        for x, y, r in parts:
            c.circle(x, y, r + k, fill=col)
        c.rrect(-104 - k, 2 - k, 96 + k, 46 + k, 22 + k, fill=col)
    for i in range(2):
        c.rrect(-40, 8 + i * 18 - 7, 32, 8 + i * 18 + 5, 4, fill=rgba(q['bd']))
        c.circle(20, 8 + i * 18 - 1, 3.6, fill=rgba(mix(hexc('#1b5b6c'), MINT, act * (0.5 + 0.5 * flash))))
    return c


def dash_layer(act, rows):
    c = Lay(260, 340, 260, 44)
    q = cols(act)
    rim, body, bd = rgba(q['rim']), rgba(q['body']), rgba(q['bd'])
    top, bot = -225, -55
    c.poly([(-20, bot), (20, bot), (28, -6), (-28, -6)], fill=bd, outline=rim, width=2.8)
    c.rrect(-82, -14, 82, 2, 6, fill=bd, outline=rim, width=2.8)
    c.rrect(-150, top, 150, bot, 16, fill=body, outline=rim, width=4)
    c.rrect(-136, top + 14, 136, bot - 14, 8, fill=rgba(DARK))
    cc = [MINT, MINT, AMBER]
    for i in range(3):
        y = top + 44 + i * 42
        on = rows[i]
        c.circle(-104, y, 11, fill=rgba(mix(hexc('#1b5b6c'), cc[i], on)))
        c.rrect(-80, y - 9, 40, y + 9, 9, fill=rgba(mix(hexc('#124360'), cc[i], 0.8 * on)))
        c.rrect(54, y - 9, 108, y + 9, 9, fill=rgba(mix(hexc('#124360'), cc[i], 0.45 * on)))
    return c


def glow_add(img, x, y, sig, col, amp):
    R = int(sig * 3.2)
    x0, y0 = int(x) - R, int(y) - R
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x0 + 2 * R, W), min(y0 + 2 * R, H)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    xs = np.arange(cx0, cx1, dtype=np.float32)
    ys = np.arange(cy0, cy1, dtype=np.float32)
    g = amp * np.exp(-(((xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2) / (2 * sig * sig)))
    img[cy0:cy1, cx0:cx1] += g[..., None] * (np.array(col, np.float32) / 255.0)[None, None, :]


def draw_packet(c, glows, pos, scale=1.0, col=MINT, a=1.0, glow=0.6):
    x, y = pos
    r = 13 * K * scale
    c.rrect(x - r, y - r, x + r, y + r, 5 * scale, fill=rgba(col, a))
    c.rrect(x - r * 0.52, y - r * 0.52, x + r * 0.52, y + r * 0.52, 3 * scale, fill=rgba(mix(col, WHITE, 0.65), a))
    if a > 0.02:
        glows.append((x, y, 26 * scale, col, glow * a))


def shard(c, x, y, size, ang, fill):
    pts = [(x + size * math.cos(ang + da) * f, y + size * math.sin(ang + da) * f) for da, f in ((0, 1.0), (2.3, 0.75), (4.0, 0.55))]
    c.poly_px(pts, fill)


def render(fi):
    static()
    t = fi / FPS
    L = camera(t)
    reset = 1 - ss(T_RESET0, T_RESET1, t)
    glows = []
    img = ST['bg'].copy()
    sx, sy, sr, sb, sk, sp = ST['stars']
    for i in range(len(sx)):
        tw = 0.7 + 0.3 * math.sin(sk[i] * TAU * t / DUR + sp[i])
        glow_add(img, sx[i] - 0.12 * L, sy[i], sr[i] * 0.9, (200, 240, 225), sb[i] * tw * 0.8)

    main = Lay(0, 0, W, H, k=1, lwb=1.0)

    def X(wx):
        return wx - L

    # lampu & pulsa
    act = dict(relay=ss(T_ON['relay'], T_ON['relay'] + 0.6, t) * reset,
               sink=ss(T_ON['sink'], T_ON['sink'] + 0.6, t) * reset,
               cloud=ss(T_ON['cloud'], T_ON['cloud'] + 0.6, t) * reset,
               dash=ss(T_ON['dash'], T_ON['dash'] + 0.6, t) * reset)
    # ---- garis tanah
    main.d.line([(0, (G + 6) * S), (W * S, (G + 6) * S)], fill=rgba(RIM_DIM, .55), width=int(4 * S))

    # ---- tautan titik (selalu tampak redup, menyala saat dilalui)
    def dots(p0, p1, lift, a, offs=0.0, col=RIM):
        Ln = math.hypot(p1[0] - p0[0], p1[1] - p0[1]) + abs(lift) * 0.6
        n = max(int(Ln / 30), 4)
        for i in range(n + 1):
            u = (i + offs) / n
            if 0 <= u <= 1:
                x, y = bez(p0, p1, lift, u)
                x -= L
                if -20 < x < W + 20:
                    main.circle(x, y, 4.6, fill=rgba(col, a))
    off = (t / 2.2) % 1.0
    dots(P_START, A_R, 130, 0.30 + 0.45 * act['relay'], col=mix(RIM_DIM, RIM, act['relay']))
    dots(A_R, A_S, 170, 0.30 + 0.45 * act['sink'], col=mix(RIM_DIM, RIM, act['sink']))
    dots(A_S, A_CL, 40, 0.30 + 0.35 * act['cloud'], off * act['cloud'], col=mix(RIM_DIM, TEAL, act['cloud']))
    dots(A_CR, A_DT, 40, 0.30 + 0.35 * act['dash'], off * act['dash'], col=mix(RIM_DIM, TEAL, act['dash']))

    # ---- cincin (sensor, LoRa)
    def ring_at(origin, r0, r1, u, col, a0, w=4.5):
        r = r0 + (r1 - r0) * u
        o = (origin[0] - L, origin[1])
        main.circle(o[0], o[1], r, outline=rgba(col, a0 * (1 - u) ** 1.3), width=w)

    for k in range(3):
        u = (t - 1.0 - k * 0.9) / 0.9
        if 0 < u < 1:
            ring_at(A_T, 36, 82, u, MINT_L, 0.7, 3.8)
    for k in range(3):
        u = (t - 4.7 - k * 0.45) / 1.5
        if 0 < u < 1:
            ring_at(A_T, 40, 360, 1 - (1 - u) ** 2, MINT, 0.6)
    for k in range(2):
        u = (t - 6.3 - k * 0.45) / 1.4
        if 0 < u < 1:
            ring_at(A_R, 40, 320, 1 - (1 - u) ** 2, MINT, 0.6)
    for k in range(2):
        u = (t - 16.6 - k * 0.45) / 1.4
        if 0 < u < 1:
            ring_at(A_T, 40, 320, 1 - (1 - u) ** 2, MINT, 0.6)

    # ---- node
    pulse = 0.5 + 0.5 * math.sin(TAU * t / 1.1)
    flash_t = max(0.0, 1 - ss(0.0, 0.5, t - 18.8)) if 18.8 <= t < 19.4 else 0.0
    check = ss(0, 0.2, t - 18.8) * (1 - ss(19.2, 19.45, t)) if 18.8 <= t < 19.5 else 0.0
    L1 = tiang_layer(pulse, flash_t, check)
    paste_node(main, L1, XT, G, L)
    relay_flash = (max(0, 1 - ss(0.0, 0.5, t - 5.9)) if 5.9 <= t < 6.5 else 0.0) + (max(0, 1 - ss(0.0, 0.5, t - 17.6)) if 17.6 <= t < 18.2 else 0.0)
    paste_node(main, relay_layer(act['relay'], min(relay_flash, 1)), XR, G, L)
    sink_flash = max(0, 1 - ss(0.0, 0.6, t - 7.4)) if 7.4 <= t < 8.0 else 0.0
    paste_node(main, sink_layer(act['sink'], sink_flash), XS, G, L)
    cloud_flash = max(0, 1 - ss(0.0, 0.7, t - 10.3)) if 10.3 <= t < 11.0 else 0.0
    paste_node(main, cloud_layer(act['cloud'], cloud_flash), XC, A_C[1], L)
    rows = [ss(0, 0.3, t - 11.6) * reset, ss(0, 0.3, t - 12.0) * reset, ss(0, 0.3, t - 12.4) * reset]
    paste_node(main, dash_layer(act['dash'], rows), XD, G, L)

    # ---- label node (alpha 1, warna berubah)
    def label(wx, y, s_, a):
        main.text(X(wx), y, s_, 48, rgba(mix(hexc('#93bccb'), TXT, a)))
    label(XT, G + 62, 'Tiang', 1.0)
    label(XR, G + 62, 'Relay (emulasi)', max(act['relay'], 0.0))
    label(XS, G + 62, 'Sink', act['sink'])
    label(XC, A_C[1] + 130, 'Cloud', act['cloud'])
    label(XD, G + 62, 'Dashboard', act['dash'])

    # ---- glow lampu/sensor
    lampT = (XT - 108 * K - L, G - 285 * K + 24)
    lampR = (XR - 108 * K - L, G - 235 * K + 24)
    glows.append((lampT[0], lampT[1], 56, AMBER, 0.34))
    glows.append((lampT[0], lampT[1], 170, AMBER, 0.07))
    glows.append((lampR[0], lampR[1], 52, AMBER, 0.12 + 0.20 * act['relay']))
    glows.append((lampR[0], lampR[1], 150, AMBER, 0.03 + 0.03 * act['relay']))
    glows.append((A_T[0] - L, A_T[1], 44, MINT, 0.10 + 0.10 * pulse))
    glows.append((A_S[0] - L, A_S[1], 46, MINT, 0.12 * act['sink'] * (0.4 + 0.6 * sink_flash + 0.3 * act['sink'])))
    glows.append((A_C[0] - L, A_C[1] + 6, 110, MINT, (0.03 + 0.20 * cloud_flash) * (0.4 + 0.6 * act['cloud'])))

    # ---- sinyal seluler di antena sink
    ang0 = math.degrees(math.atan2(A_CL[1] - A_S[1], A_CL[0] - A_S[0]))
    for k in range(3):
        u = (t - 8.8 - k * 0.22) / 1.0
        if 0 < u < 1:
            r = 40 + k * 24
            main.arc(A_S[0] - L, A_S[1], r, ang0 - 38, ang0 + 38, rgba(TEAL, 0.85 * math.sin(math.pi * u)), 5)

    # ---- paket
    def trail(p0, p1, lift, u, n=3):
        for k in range(1, n + 1):
            pk = bez(p0, p1, lift, max(u - 0.05 * k, 0))
            draw_packet(main, glows, (pk[0] - L, pk[1]), scale=0.72 - 0.12 * k, a=0.38 / k, glow=0.0)

    def fly(p0, p1, lift, ta, tb, col=MINT, scale=1.0, tr=True):
        u = ss(ta, tb, t)
        pos = bez(p0, p1, lift, u)
        if tr:
            trail(p0, p1, lift, u)
        draw_packet(main, glows, (pos[0] - L, pos[1]), scale=scale, col=col)
        return pos

    PS = (P_START[0] - L, P_START[1])
    if 2.8 <= t < 4.7:      # paket terbentuk di samping sensor
        f = eo(3.0, 3.8, t)
        draw_packet(main, glows, PS, scale=f, a=f)
    if 4.7 <= t < 5.9:
        fly(P_START, A_R, 130, 4.7, 5.9)
    if 5.9 <= t < 6.5:
        draw_packet(main, glows, (A_R[0] - L, A_R[1]), scale=1 + 0.25 * math.sin(math.pi * ss(5.9, 6.5, t)))
    if 6.5 <= t < 7.5:
        fly(A_R, A_S, 170, 6.5, 7.5)
    if 7.5 <= t < 8.9:
        draw_packet(main, glows, (A_S[0] - L, A_S[1]), scale=1 + 0.15 * math.sin(TAU * (t - 7.5) / 0.8) * (1 if t < 8.6 else 0))
    if 8.9 <= t < 10.2:
        fly(A_S, A_CL, 40, 8.9, 10.2, col=TEAL, scale=0.95, tr=False)
    if 10.2 <= t < 10.5:
        f = ss(10.2, 10.5, t)
        draw_packet(main, glows, (A_CL[0] - L, A_CL[1]), col=TEAL, scale=0.95 * (1 - f) + 0.25, a=1 - f)
    if 10.45 <= t < 11.4:
        fly(A_CR, A_DT, 40, 10.45, 11.4, col=TEAL, scale=0.95, tr=False)
    if 11.4 <= t < 11.7:
        f = ss(11.4, 11.7, t)
        draw_packet(main, glows, (A_DT[0] - L, A_DT[1]), col=TEAL, scale=0.95 * (1 - f) + 0.25, a=1 - f)

    # ---- paket hilang (contoh ilustrasi): pecah, serpihan oranye-amber, label
    LOST_U = 0.5
    T_BREAK = 14.55
    LP = bez(P_START, A_R, 130, LOST_U)
    if 13.1 <= t < 13.9:
        f = eo(13.1, 13.7, t)
        draw_packet(main, glows, PS, scale=f, a=f)
    if 13.9 <= t < T_BREAK:
        u = ss(13.9, T_BREAK, t) * LOST_U
        warn = ss(0.25, LOST_U, u)
        pos = bez(P_START, A_R, 130, u)
        jit = math.sin(TAU * (t - 13.9) * 3.0) * 4 * warn
        for k in range(1, 4):
            pk = bez(P_START, A_R, 130, max(u - 0.05 * k, 0))
            draw_packet(main, glows, (pk[0] - L, pk[1]), scale=0.72 - 0.12 * k, a=0.38 / k, col=mix(MINT, LOSS, warn), glow=0.0)
        draw_packet(main, glows, (pos[0] - L, pos[1] + jit), scale=1 - 0.12 * warn, col=mix(MINT, LOSS, warn), glow=0.6)
    if T_BREAK <= t < 16.1:
        e = t - T_BREAK
        # cincin pecah
        ur = min(e / 0.7, 1)
        if ur < 1:
            main.circle(LP[0] - L, LP[1], 22 + 100 * (1 - (1 - ur) ** 2), outline=rgba(LOSS, 0.8 * (1 - ur)), width=5)
        glows.append((LP[0] - L, LP[1], 60, LOSS, 0.30 * (1 - ss(0, 0.9, e))))
        rng = np.random.default_rng(23)
        for k in range(12):
            an = TAU * k / 12 + rng.uniform(-0.2, 0.2)
            sp_ = rng.uniform(95, 190)
            rot0, rotv = rng.uniform(0, TAU), rng.uniform(-6, 6)
            sz = rng.uniform(15, 27)
            ee = min(e, 1.5)
            fade = 1 - ss(0.9, 1.5, e)
            if fade <= 0.01:
                continue
            dist = sp_ * (1 - math.exp(-3.2 * ee)) / 3.2 * 3.3
            x = LP[0] - L + dist * math.cos(an)
            y = LP[1] + dist * math.sin(an) + 70 * ee * ee
            pts = [(x + sz * math.cos(rot0 + rotv * ee + da) * f, y + sz * math.sin(rot0 + rotv * ee + da) * f)
                   for da, f in ((0, 1.0), (2.1, 0.8), (3.5, 0.9), (4.9, 0.55))]
            main.d.polygon([(px_ * S, py_ * S) for px_, py_ in pts], fill=rgba(mix(LOSS, AMBER, k / 11.0), 0.95 * fade))
    # label paket hilang (alpha 1, muncul/hilang cepat)
    if 14.5 <= t < 16.4:
        lx, ly = LP[0] - L - 10, LP[1] + 195
        wbox, hbox = 500, 142
        main.rrect(lx - wbox / 2, ly - hbox / 2, lx + wbox / 2, ly + hbox / 2, 30, fill=rgba(hexc('#06263c'), .96), outline=rgba(LOSS), width=4)
        main.text(lx, ly - 34, 'Paket hilang', 54, rgba(hexc('#ffc27d')))
        main.text(lx, ly + 28, '(contoh ilustrasi)', 48, rgba(hexc('#ffd9ae')))
        # tangkai kecil ke titik pecah
        main.line([(lx, ly - hbox / 2), (lx, ly - hbox / 2 - 38)], rgba(LOSS), 4)

    # ---- kirim ulang
    if 15.7 <= t < 16.5:
        u = (t - 15.7) / 0.8
        r0 = 50
        main.arc(A_T[0] - L, A_T[1], r0, -90 + 360 * u, 170 + 360 * u, rgba(AMBER, 0.95 * math.sin(math.pi * u)), 7)
    if 16.3 <= t < 16.8:
        f = eo(16.3, 16.7, t)
        draw_packet(main, glows, PS, scale=f, a=f)
    if 16.8 <= t < 17.7:
        fly(P_START, A_R, 130, 16.8, 17.7)
    if 17.7 <= t < 18.0:
        f = ss(17.7, 18.0, t)
        draw_packet(main, glows, (A_R[0] - L, A_R[1]), scale=1 - 0.4 * f, a=1 - f)
    # ACK (chip putih) relay -> tiang
    if 17.8 <= t < 18.85:
        u = ss(17.8, 18.8, t)
        pos = bez((A_R[0], A_R[1] + 40), (A_T[0] + 40, A_T[1] - 20), -170, u)
        x, y = pos[0] - L, pos[1]
        main.rrect(x - 62, y - 31, x + 62, y + 31, 31, fill=rgba(WHITE), outline=rgba(MINT_L), width=4)
        main.text(x, y - 2, 'ACK', 42, rgba(hexc('#0a5a42')))
        glows.append((x, y, 34, WHITE, 0.28))

    # ---- judul (alpha selalu 1; pergantian berupa potongan cepat)
    for (a0, a1, s_) in CAPS:
        if a0 <= t < a1:
            e = (t - a0) / 0.22 if a0 > 0 else 1.0
            dy = (1 - ss(0, 1, e)) * 16
            main.text(W / 2, 148 + dy + 3, s_, 66, rgba(hexc('#031826'), 0.55))
            main.text(W / 2, 148 + dy, s_, 66, rgba(TXT))
    # ---- strip pil
    geo = ST['pills']
    for i, (name, t_on) in enumerate(PILLS):
        base = ss(t_on, t_on + 0.45, t) if t_on > 0 else 1.0
        lit = base * (reset if i > 0 else 1.0)
        x0, x1 = geo[i]
        fill = mix(hexc('#0a2a44'), hexc('#168270'), lit)
        outl = mix(hexc('#2a7390'), MINT, lit)
        tc = mix(hexc('#b4d2de'), WHITE, lit)
        main.rrect(x0, PILL_Y - PILL_H / 2, x1, PILL_Y + PILL_H / 2, PILL_H / 2, fill=rgba(fill), outline=rgba(outl), width=4)
        main.text((x0 + x1) / 2, PILL_Y - 3, name, 52, rgba(tc))
        if lit > 0.01:
            glows.append(((x0 + x1) / 2, PILL_Y, 70, MINT, 0.10 * lit))
        if i < len(PILLS) - 1:
            nx = geo[i + 1][0]
            mx = (x1 + nx) / 2
            ca = mix(hexc('#3c7f9a'), MINT, lit * 0.9)
            main.line([(mx - 11, PILL_Y - 18), (mx + 7, PILL_Y), (mx - 11, PILL_Y + 18)], rgba(ca), 6)

    small = main.im.resize((W, H), Image.BOX)
    arr = np.asarray(small).astype(np.float32) / 255.0
    a = arr[..., 3:4]
    for (x, y, sig, col, amp) in glows:
        if amp > 0.003:
            glow_add(img, x, y, sig, col, amp)
    img = img * (1 - a) + arr[..., :3] * a
    top_gl = np.zeros_like(img)
    for (x, y, sig, col, amp) in glows:
        if amp > 0.003 and sig <= 40:
            glow_add(top_gl, x, y, sig, col, amp * 0.25)
    img += top_gl
    img = brand_overlay(img, t)
    return np.clip(img * 255.0 + 0.5 + ST['noise'], 0, 255).astype(np.uint8)


def load_mark():
    if 'mark' not in ST:
        ST['mark'] = Image.open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'aurora-mark.png')).convert('RGBA')
    return ST['mark']


def brand_overlay(img, t):
    """Overlay gelap + lockup penutup (19.4-21.6), watermark logo + label kejujuran permanen di pojok."""
    dim = ss(19.4, 19.6, t) * (1 - ss(21.0, 21.35, t)) * 0.93
    if dim > 0.001:
        img = img * (1 - dim) + np.array(hexc('#03090f'), np.float32)[None, None, :] / 255.0 * dim
    top = Lay(0, 0, W, H, k=1, lwb=1.0)
    mk = load_mark()
    # posisi mark: tengah (lockup) -> pojok kiri atas (watermark)
    m = 1 - ss(19.4, 19.8, t) * (1 - ss(21.0, 21.6, t))
    w_c, cx_c, cy_c = 300.0, W / 2, 395.0
    w_s, cx_s, cy_s = 140.0, 40 + 70.0, 34 + 44.5
    mw = w_c + (w_s - w_c) * m
    mcx = cx_c + (cx_s - cx_c) * m
    mcy = cy_c + (cy_s - cy_c) * m
    mh = mw * mk.size[1] / mk.size[0]
    mi = mk.resize((int(round(mw * S)), int(round(mh * S))), Image.LANCZOS)
    top.im.alpha_composite(mi, dest=(int(round((mcx - mw / 2) * S)), int(round((mcy - mh / 2) * S))))
    # wordmark AURORA (putih, tracking lebar) hanya pada lockup
    wa = ss(19.7, 19.9, t) * (1 - ss(20.95, 21.3, t))
    if wa > 0.01:
        f = font(104)
        word = 'AURORA'
        track = 30 * S
        widths = [f.getlength(ch) for ch in word]
        tot = sum(widths) + track * (len(word) - 1)
        x = W * S / 2 - tot / 2
        for ch, wd in zip(word, widths):
            top.d.text((x, 640 * S), ch, font=f, fill=rgba(WHITE, wa), anchor='lm')
            x += wd + track
    # label kejujuran permanen
    lab = 'Ilustrasi alur satu paket'
    lw_ = top.d.textlength(lab, font=font(38)) / S
    x0 = 40 + 140 + 26
    top.rrect(x0, 34, x0 + lw_ + 52, 104, 35, fill=rgba(hexc('#052136'), .85), outline=rgba(RIM_DIM), width=2.5)
    top.text(x0 + 26 + lw_ / 2, 69, lab, 38, rgba(hexc('#d3ece3')))
    small = top.im.resize((W, H), Image.BOX)
    arr = np.asarray(small).astype(np.float32) / 255.0
    a = arr[..., 3:4]
    return img * (1 - a) + arr[..., :3] * a


def worker(fi):
    return render(fi).tobytes()


if __name__ == '__main__':
    work = sys.argv[1]
    os.makedirs(work, exist_ok=True)
    if '--only-frame' in sys.argv:
        ks = sys.argv[sys.argv.index('--only-frame') + 1].split(',')
        for k in ks:
            Image.fromarray(render(int(k))).save(os.path.join(work, f'lora_f{int(k):03d}.png'))
        sys.exit(0)
    nf = NF
    if '--frames' in sys.argv:
        nf = int(sys.argv[sys.argv.index('--frames') + 1])
    out = os.path.join(work, 'lora_lossless.mkv')
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
