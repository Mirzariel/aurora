"""AURORA 'lora-journey' explainer loop (18 s, 30 fps, 1920x1080). Procedural (Pillow 2x supersample + numpy glow).
State at t=0 equals state at t=18 (empty scene, dim pill strip), so the loop is seamless.

Usage: python make_lora_journey.py <workdir> [--only-frame K] [--frames N]
"""
import sys, os, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageChops
from multiprocessing import Pool

W, H, FPS, DUR = 1920, 1080, 30, 18
NF = FPS * DUR
S = 2
TAU = 2 * math.pi
FONT_B = r'C:\Windows\Fonts\segoeuib.ttf'


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ss(a, b, x):
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def eo(a, b, x):  # ease out cubic
    t = min(max((x - a) / (b - a), 0.0), 1.0)
    return 1 - (1 - t) ** 3


def rgba(c, a=1.0):
    return (int(round(c[0])), int(round(c[1])), int(round(c[2])), int(round(255 * min(max(a, 0), 1))))


BODY = hexc('#10446a')
BODY_D = hexc('#0a3250')
RIM = hexc('#3aa07c')
MINT = hexc('#56c785')
MINT_L = hexc('#9ae6bf')
TEAL = hexc('#6fd6c2')
AMBER = hexc('#ffb45a')
WARN = hexc('#ff7a45')
WHITE = hexc('#f4fbf8')
TXT = hexc('#d7f3e6')

# ---- layout (1080p px)
GROUND = 700
X_T, X_R, X_S, X_C, X_D = 235, 625, 1020, 1350, 1700
A_T = (X_T, 560)           # tiang sensor
A_R = (X_R, 432)           # relay antenna tip
A_S = (X_S + 40, 548)      # sink antenna tip
A_C = (X_C - 20, 420)      # cloud
A_D = (X_D - 10, 575)      # dashboard

T_TIANG, T_RELAY, T_SINK, T_CLOUD, T_DASH = 0.5, 4.0, 6.3, 8.3, 9.6
T_FADE0, T_FADE1 = 16.6, 17.6

CAPS = [
    (0.9, 2.9, 'Sensor membaca kondisi tiang'),
    (2.9, 4.4, 'Data dirangkum jadi satu paket'),
    (4.4, 6.2, 'Paket dikirim lewat radio LoRa'),
    (6.2, 7.7, 'Relay meneruskan paket'),
    (7.7, 9.0, 'Sink mengumpulkan paket'),
    (9.0, 10.6, 'Jaringan seluler menuju cloud'),
    (10.6, 13.0, 'Dashboard menampilkan status'),
    (13.0, 14.3, 'Paket hilang di perjalanan'),
    (14.3, 16.5, 'Dikirim ulang sampai ACK diterima'),
]
PILLS = [('SENSE', 0.9), ('UNDERSTAND', 2.9), ('DELIVER', 4.4), ('ACT', 11.3)]
PILL_Y = 925

ST = {}


def font(px):
    k = ('f', px)
    if k not in ST:
        ST[k] = ImageFont.truetype(FONT_B, int(round(px * S)))
    return ST[k]


class C:
    def __init__(self, ox, oy, w, h):
        self.ox, self.oy, self.w, self.h = ox, oy, w, h
        self.im = Image.new('RGBA', (int(w * S), int(h * S)), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im, 'RGBA')

    def p(self, x, y):
        return ((x - self.ox) * S, (y - self.oy) * S)

    def poly(self, pts, fill=None, outline=None, width=0):
        pp = [self.p(*q) for q in pts]
        if fill is not None:
            self.d.polygon(pp, fill=fill)
        if outline is not None and width:
            self.d.line(pp + [pp[0]], fill=outline, width=int(width * S), joint='curve')

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, width=0):
        a, b = self.p(x0, y0), self.p(x1, y1)
        self.d.rounded_rectangle([a, b], radius=r * S, fill=fill, outline=outline, width=int(width * S))

    def circle(self, x, y, r, fill=None, outline=None, width=0):
        a, b = self.p(x - r, y - r), self.p(x + r, y + r)
        self.d.ellipse([a, b], fill=fill, outline=outline, width=int(width * S))

    def line(self, pts, fill, width):
        self.d.line([self.p(*q) for q in pts], fill=fill, width=int(width * S), joint='curve')

    def arc(self, x, y, r, a0, a1, fill, width):
        a, b = self.p(x - r, y - r), self.p(x + r, y + r)
        self.d.arc([a, b], a0, a1, fill=fill, width=int(width * S))

    def text(self, x, y, s, px, fill, anchor='mm'):
        self.d.text(self.p(x, y), s, font=font(px), fill=fill, anchor=anchor)

    def paste(self, layer, a=1.0, dy=0.0):
        im = layer.im
        if a < 0.999:
            al = im.getchannel('A').point(lambda v, a=a: int(v * a))
            im = im.copy()
            im.putalpha(al)
        self.im.alpha_composite(im, dest=(int(round((layer.ox - self.ox) * S)), int(round((layer.oy + dy - self.oy) * S))))


def rot_rect(cx, cy, l, t, ang):
    cs, sn = math.cos(ang), math.sin(ang)
    return [(cx + x * cs - y * sn, cy + x * sn + y * cs) for x, y in ((-l / 2, -t / 2), (l / 2, -t / 2), (l / 2, t / 2), (-l / 2, t / 2))]


def bez(p0, p1, lift, u):
    cx, cy = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - lift
    return ((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * cx + u * u * p1[0],
            (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * cy + u * u * p1[1])


def static():
    if 'bg' in ST:
        return
    ys = np.arange(H, dtype=np.float32)[:, None]
    xs = np.arange(W, dtype=np.float32)[None, :]
    top, mid, bot = np.array(hexc('#051f33'), np.float32) / 255, np.array(hexc('#08304d'), np.float32) / 255, np.array(hexc('#0c4467'), np.float32) / 255
    t = (ys / H)[:, 0:1]
    rows = np.where(t < 0.5, top + (mid - top) * (t / 0.5), mid + (bot - mid) * ((t - 0.5) / 0.5))  # (H,3)
    bg = np.broadcast_to(rows[:, None, :], (H, W, 3)).copy()
    # soft aurora-green haze in lower area, mostly under the diagram
    hz = np.exp(-(((xs - 1000) / 900.0) ** 2 + ((ys - 760) / 280.0) ** 2))[..., None]
    bg += hz * np.array([0.02, 0.12, 0.09], np.float32) * 0.9
    # vignette
    vg = 1 - 0.22 * (((xs - W / 2) / (W / 2)) ** 2 * 0.6 + ((ys - H / 2) / (H / 2)) ** 2 * 0.4)
    bg *= vg[..., None]
    ST['bg'] = bg.astype(np.float32)
    rng = np.random.default_rng(11)
    n = 55
    ST['stars'] = (rng.uniform(20, W - 20, n), rng.uniform(20, 560, n), rng.uniform(0.8, 1.7, n),
                   rng.uniform(0.25, 0.7, n), rng.choice([1, 2, 3], n), rng.uniform(0, TAU, n))
    ST['noise'] = np.random.default_rng(5).random((H, W, 3), dtype=np.float32) - 0.5
    # pill geometry
    c = C(0, 0, 10, 10)
    wd = []
    for name, _ in PILLS:
        l = c.d.textlength(name, font=font(38)) / S
        wd.append(l + 74)
    gap = 80
    total = sum(wd) + gap * (len(wd) - 1)
    x = (W - total) / 2
    geo = []
    for w_ in wd:
        geo.append((x, x + w_))
        x += w_ + gap
    ST['pills'] = geo


def pole_layer(x, h, kind, pulse, flash, lamp_a):
    """Draw a pole node on its own layer. kind: 'tiang' or 'relay'."""
    top = GROUND - h
    c = C(x - 230, GROUND - 470, 460, 480)
    sw = 2.6
    # base + pole
    c.rrect(x - 26, GROUND - 14, x + 26, GROUND + 4, 6, fill=rgba(BODY_D), outline=rgba(RIM, .8), width=2)
    c.poly([(x - 8, GROUND - 12), (x + 8, GROUND - 12), (x + 5, top), (x - 5, top)], fill=rgba(BODY), outline=rgba(RIM), width=sw)
    # arm and lamp head (left)
    pts = []
    p0, p1, p2 = (x, top + 40), (x - 18, top + 4), (x - 100, top + 12)
    for i in range(25):
        u = i / 24
        pts.append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0], (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]))
    c.line(pts, rgba(RIM), 9)
    c.line(pts, rgba(BODY), 5)
    lx, ly = x - 108, top + 15
    c.rrect(lx - 36, ly - 8, lx + 30, ly + 8, 7, fill=rgba(BODY), outline=rgba(RIM), width=2.4)
    c.rrect(lx - 30, ly + 4, lx + 24, ly + 9, 2.5, fill=rgba(mix(BODY, AMBER, lamp_a)))
    if kind == 'tiang':
        pc = (x + 28, top - 18)
        poly = rot_rect(pc[0], pc[1], 150, 16, math.radians(-22))
        c.poly([(x - 4, top + 6), (x + 4, top + 6), (pc[0] + 8, pc[1] + 6), (pc[0] - 8, pc[1] + 6)], fill=rgba(BODY), outline=rgba(RIM), width=2)
        c.poly(poly, fill=rgba(BODY_D), outline=rgba(MINT), width=2.6)
        for k in (-0.3, 0.0, 0.3):
            ax = pc[0] + k * 150 * math.cos(math.radians(-22))
            ay = pc[1] + k * 150 * math.sin(math.radians(-22))
            c.line([(ax + 5, ay - 5), (ax - 5, ay + 6)], rgba(MINT, .55), 1.8)
        # sensor module with pulsing dot
        sx, sy = A_T
        c.rrect(sx - 22, sy - 22, sx + 22, sy + 22, 9, fill=rgba(BODY_D), outline=rgba(MINT, .95), width=3)
        r = 6.5 + 2.2 * pulse
        col = mix(MINT, WHITE, flash)
        c.circle(sx, sy, r, fill=rgba(col))
    else:
        # antenna mast with two small arcs
        c.line([(x, top + 4), (x, top - 26)], rgba(RIM), 6)
        c.line([(x, top + 4), (x, top - 26)], rgba(BODY), 3)
        c.circle(x, top - 30, 7, fill=rgba(BODY_D), outline=rgba(MINT), width=2.6)
        pc = (x + 40, top + 6)
        c.poly(rot_rect(pc[0], pc[1], 96, 12, math.radians(-18)), fill=rgba(BODY_D), outline=rgba(MINT), width=2.2)
        c.line([(x + 6, top + 22), (pc[0] - 4, pc[1] + 3)], rgba(RIM), 3)
    return c


def sink_layer(act, flash):
    c = C(X_S - 150, GROUND - 230, 300, 250)
    x = X_S
    c.rrect(x - 98, GROUND - 110, x + 98, GROUND, 18, fill=rgba(BODY), outline=rgba(RIM), width=3)
    c.rrect(x - 98, GROUND - 110, x + 98, GROUND - 76, 16, fill=rgba(BODY_D), outline=rgba(RIM), width=3)
    # antenna
    c.line([(x + 40, GROUND - 110), (x + 40, GROUND - 152)], rgba(RIM), 7)
    c.line([(x + 40, GROUND - 110), (x + 40, GROUND - 152)], rgba(BODY), 3.5)
    c.circle(x + 40, GROUND - 156, 7, fill=rgba(mix(BODY_D, MINT, 0.4 + 0.6 * flash)), outline=rgba(MINT), width=2.4)
    # LED row
    for i in range(3):
        on = ss(0.0, 1.0, act - i * 0.25)
        col = mix(hexc('#1b5b6c'), MINT if i < 2 else AMBER, on)
        c.circle(x - 62 + i * 30, GROUND - 93, 7, fill=rgba(col))
    # ports
    for i in range(3):
        c.rrect(x - 66 + i * 54, GROUND - 52, x - 30 + i * 54, GROUND - 28, 5, fill=rgba(hexc('#082a42')), outline=rgba(RIM, .6), width=2)
    return c


def cloud_layer(flash):
    cx, cy = X_C, 400
    c = C(cx - 150, cy - 90, 300, 190)
    parts = [('c', cx - 62, cy + 6, 38), ('c', cx - 12, cy - 20, 54), ('c', cx + 46, cy - 2, 42)]
    for k in (4.5, 0):
        col = rgba(RIM) if k else rgba(mix(BODY, MINT, 0.12 * flash))
        for _, x, y, r in parts:
            c.circle(x, y, r + k, fill=col)
        c.rrect(cx - 104 - k, cy + 2 - k, cx + 96 + k, cy + 46 + k, 22 + k, fill=col)
    # small status glyph: stacked server lines
    for i in range(2):
        c.rrect(cx - 38, cy + 8 + i * 17 - 6, cx + 30, cy + 8 + i * 17 + 4, 4, fill=rgba(BODY_D))
        c.circle(cx + 18, cy + 8 + i * 17 - 1, 3, fill=rgba(mix(hexc('#1b5b6c'), MINT, 0.5 + 0.5 * flash)))
    return c


def dash_layer(rows, flash):
    cx = X_D
    c = C(cx - 180, GROUND - 270, 360, 290)
    top, bot = GROUND - 225, GROUND - 55
    c.poly([(cx - 20, bot), (cx + 20, bot), (cx + 28, GROUND - 6), (cx - 28, GROUND - 6)], fill=rgba(BODY_D), outline=rgba(RIM), width=2.4)
    c.rrect(cx - 82, GROUND - 14, cx + 82, GROUND + 2, 6, fill=rgba(BODY_D), outline=rgba(RIM), width=2.4)
    c.rrect(cx - 150, top, cx + 150, bot, 16, fill=rgba(BODY), outline=rgba(RIM), width=3.5)
    c.rrect(cx - 136, top + 14, cx + 136, bot - 14, 8, fill=rgba(hexc('#082a42')))
    cols = [MINT, MINT, AMBER]
    for i in range(3):
        y = top + 44 + i * 42
        on = rows[i]
        dcol = mix(hexc('#1b5b6c'), cols[i], on)
        c.circle(cx - 104, y, 10, fill=rgba(dcol))
        c.rrect(cx - 80, y - 8, cx + 40, y + 8, 8, fill=rgba(mix(hexc('#124360'), cols[i], 0.75 * on)))
        c.rrect(cx + 54, y - 8, cx + 108, y + 8, 8, fill=rgba(mix(hexc('#124360'), cols[i], 0.4 * on)))
    return c


def glow_add(img, x, y, sig, col, amp):
    R = int(sig * 3.2)
    x0, y0 = int(x) - R, int(y) - R
    xs = np.arange(x0, x0 + 2 * R, dtype=np.float32)
    ys = np.arange(y0, y0 + 2 * R, dtype=np.float32)
    g = amp * np.exp(-(((xs[None, :] - x) ** 2 + (ys[:, None] - y) ** 2) / (2 * sig * sig)))
    cx0, cy0 = max(x0, 0), max(y0, 0)
    cx1, cy1 = min(x0 + 2 * R, W), min(y0 + 2 * R, H)
    if cx1 <= cx0 or cy1 <= cy0:
        return
    g = g[cy0 - y0:cy1 - y0, cx0 - x0:cx1 - x0]
    img[cy0:cy1, cx0:cx1] += g[..., None] * (np.array(col, np.float32) / 255.0)[None, None, :]


def draw_packet(c, glows, pos, scale=1.0, col=MINT, a=1.0, glow=0.55):
    x, y = pos
    r = 11 * scale
    c.rrect(x - r, y - r, x + r, y + r, 4 * scale, fill=rgba(col, a))
    c.rrect(x - r * 0.5, y - r * 0.5, x + r * 0.5, y + r * 0.5, 2 * scale, fill=rgba(mix(col, WHITE, 0.6), a))
    if a > 0.02:
        glows.append((x, y, 20 * scale, col, glow * a))


def travel(p0, p1, lift, t, ta, tb):
    u = ss(ta, tb, t)
    return bez(p0, p1, lift, u), u


def render(fi):
    static()
    t = fi / FPS
    out_a = 1 - ss(T_FADE0, T_FADE1, t)
    glows = []
    img = ST['bg'].copy()
    # stars
    sx, sy, sr, sb, sk, sp = ST['stars']
    for i in range(len(sx)):
        tw = 0.7 + 0.3 * math.sin(sk[i] * TAU * t / DUR + sp[i])
        glow_add(img, sx[i], sy[i], sr[i] * 0.9, (200, 240, 225), sb[i] * tw * 0.8)

    main = C(0, 0, W, H)
    # road line
    main.line([(110, GROUND + 3), (1810, GROUND + 3)], rgba(RIM, .22), 3)

    ap = {k: eo(v, v + 1.0, t) * out_a for k, v in dict(tiang=T_TIANG, relay=T_RELAY, sink=T_SINK, cloud=T_CLOUD, dash=T_DASH).items()}

    # ---- links (dotted) between nodes
    def dots(p0, p1, lift, a, offs=0.0, col=RIM, n=None):
        if a < 0.02:
            return
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = int(L / 26)
        for i in range(n + 1):
            u = (i + offs) / n
            if 0 <= u <= 1:
                x, y = bez(p0, p1, lift, u)
                main.circle(x, y, 3.2, fill=rgba(col, a))
    dots(A_T, A_R, 100, 0.40 * ap['relay'])
    dots(A_R, A_S, 120, 0.40 * ap['sink'])
    off = (t * 0.9) % 1.0
    dots(A_S, A_C, 0, 0.55 * ap['cloud'], off, TEAL)
    dots((A_C[0] + 40, A_C[1] + 20), A_D, 0, 0.55 * ap['dash'], off, TEAL)

    # ---- LoRa rings (from sensor, from relay)
    def rings(origin, t0, dur, rmax, n=3, gap=0.42, col=MINT):
        for k in range(n):
            u = (t - t0 - k * gap) / dur
            if 0 < u < 1:
                r = 26 + (rmax - 26) * (1 - (1 - u) ** 2)
                main.circle(origin[0], origin[1], r, outline=rgba(col, 0.55 * (1 - u) ** 1.3), width=3.5)
    # sensor pulse rings (SENSE phase)
    for k in range(3):
        u = ((t - 1.0 - k * 0.9) / 0.9)
        if 0 < u < 1:
            r = 24 + 26 * u
            main.circle(A_T[0], A_T[1], r, outline=rgba(MINT_L, 0.6 * (1 - u)), width=3)
    rings(A_T, 4.7, 1.5, 330)
    rings(A_R, 6.3, 1.4, 300, n=2)
    rings(A_T, 14.6, 1.4, 300, n=2)

    # ---- nodes
    pulse = 0.5 + 0.5 * math.sin(TAU * t / 1.2)
    flash_t = 0.0
    for tt in (15.55,):
        flash_t = max(flash_t, 1 - ss(0.0, 0.5, t - tt)) if t >= tt else flash_t
    lamp_t = 0.55 + 0.45 * ss(0, 1, ap['tiang'])
    L1 = pole_layer(X_T, 300, 'tiang', pulse, flash_t, lamp_t)
    main.paste(L1, ap['tiang'], dy=(1 - ap['tiang']) * 22)
    relay_flash = 0.0
    L2 = pole_layer(X_R, 250, 'relay', 0, 0, 0.6)
    main.paste(L2, ap['relay'], dy=(1 - ap['relay']) * 22)
    sink_act = ss(0, 1, t - 7.4) * (1 if t < 16.5 else out_a)
    sink_flash = max(0, 1 - ss(0.0, 0.6, t - 7.4)) if t >= 7.4 else 0.0
    L3 = sink_layer(sink_act, sink_flash)
    main.paste(L3, ap['sink'], dy=(1 - ap['sink']) * 22)
    cloud_flash = max(0, 1 - ss(0.0, 0.7, t - 10.3)) if t >= 10.3 else 0.0
    L4 = cloud_layer(cloud_flash)
    main.paste(L4, ap['cloud'], dy=(1 - ap['cloud']) * 22)
    rows = [ss(0, 0.3, t - 11.6) * min(1, out_a * 1.0 + 0), ss(0, 0.3, t - 12.0), ss(0, 0.3, t - 12.4)]
    rows = [r_ for r_ in rows]
    L5 = dash_layer(rows, 0)
    main.paste(L5, ap['dash'], dy=(1 - ap['dash']) * 22)

    # node glows (lamps, sensor)
    glows.append((X_T - 118, GROUND - 300 + 24, 46, AMBER, 0.34 * ap['tiang']))
    glows.append((X_T - 118, GROUND - 300 + 24, 150, AMBER, 0.07 * ap['tiang']))
    glows.append((X_R - 118, GROUND - 250 + 24, 40, AMBER, 0.26 * ap['relay']))
    glows.append((X_R - 118, GROUND - 250 + 24, 130, AMBER, 0.05 * ap['relay']))
    glows.append((A_T[0], A_T[1], 36, MINT, (0.10 + 0.10 * pulse) * ap['tiang']))
    if ap['sink'] > 0.01:
        glows.append((A_S[0], A_S[1], 40, MINT, 0.12 * ap['sink'] * (0.4 + 0.6 * sink_flash + 0.3 * sink_act)))
    glows.append((A_C[0] - 10, A_C[1] + 6, 90, MINT, (0.05 + 0.20 * cloud_flash) * ap['cloud']))

    # ---- cellular signal arcs at sink antenna (pointing toward the cloud)
    ang0 = math.degrees(math.atan2(A_C[1] - A_S[1], A_C[0] - A_S[0]))
    for k in range(3):
        u = (t - 8.7 - k * 0.22) / 1.0
        if 0 < u < 1 and ap['cloud'] > 0.01:
            r = 34 + k * 20
            main.arc(A_S[0], A_S[1], r, ang0 - 38, ang0 + 38, rgba(TEAL, 0.8 * math.sin(math.pi * u) * ap['cloud']), 4)

    # ---- packets
    # first packet journey
    # form at tiang 2.9-3.9
    if 3.0 <= t < 4.8:
        f = eo(3.0, 3.8, t)
        # packet forms beside the sensor and hovers until it launches
        draw_packet(main, glows, (A_T[0], A_T[1] - 52 * f), scale=f, a=f * ap['tiang'])
    if 4.8 <= t < 5.9:
        pos, u = travel((A_T[0], A_T[1] - 52), A_R, 100, t, 4.8, 5.9)
        for k in range(1, 4):
            pk = bez((A_T[0], A_T[1] - 52), A_R, 100, max(u - 0.05 * k, 0))
            draw_packet(main, glows, pk, scale=0.7 - 0.12 * k, a=0.35 / k, glow=0.0)
        draw_packet(main, glows, pos)
    if 5.9 <= t < 6.5:
        draw_packet(main, glows, A_R, scale=1 + 0.25 * math.sin(math.pi * ss(5.9, 6.5, t)))
    if 6.4 <= t < 7.5:
        pos, u = travel(A_R, A_S, 140, t, 6.4, 7.5)
        for k in range(1, 4):
            pk = bez(A_R, A_S, 140, max(u - 0.05 * k, 0))
            draw_packet(main, glows, pk, scale=0.7 - 0.12 * k, a=0.35 / k, glow=0.0)
        draw_packet(main, glows, pos)
    if 7.5 <= t < 9.2:
        a = 1.0 if t < 9.0 else 1 - ss(9.0, 9.2, t) * 0.0
        draw_packet(main, glows, A_S, scale=1 + 0.15 * math.sin(TAU * (t - 7.5) / 0.8) * (1 if t < 8.6 else 0))
    if 9.0 <= t < 10.2:
        pos, u = travel(A_S, A_C, 0, t, 9.0, 10.2)
        draw_packet(main, glows, pos, col=TEAL, scale=0.9)
    if 10.2 <= t < 10.5:
        draw_packet(main, glows, A_C, col=TEAL, scale=0.9 * (1 - ss(10.2, 10.5, t)) + 0.2, a=1 - ss(10.2, 10.5, t))
    if 10.45 <= t < 11.5:
        pos, u = travel((A_C[0] + 40, A_C[1] + 20), A_D, 0, t, 10.45, 11.5)
        draw_packet(main, glows, pos, col=TEAL, scale=0.9)
    if 11.5 <= t < 11.8:
        draw_packet(main, glows, A_D, col=TEAL, scale=0.9 * (1 - ss(11.5, 11.8, t)) + 0.2, a=1 - ss(11.5, 11.8, t))

    # resilience: second packet from the tiang is lost, retried, ACKed
    p_start = (A_T[0], A_T[1] - 52)
    if 12.9 <= t < 13.3:
        f = eo(12.9, 13.3, t)
        draw_packet(main, glows, p_start, scale=f, a=f)
    if 13.3 <= t < 14.3:
        pos, u = travel(p_start, A_R, 100, t, 13.3, 14.3)
        lost = ss(0.55, 0.92, u)
        col = mix(MINT, WARN, lost)
        draw_packet(main, glows, (pos[0], pos[1] - 10 * lost), scale=1 - 0.4 * lost, col=col, a=1 - lost, glow=0.5)
        if lost > 0.05:
            for k in range(5):
                an = TAU * k / 5 + 0.4
                rr = 32 * lost
                main.circle(pos[0] + rr * math.cos(an), pos[1] + rr * math.sin(an) - 10 * lost, 3.8, fill=rgba(WARN, 0.8 * (1 - lost)))
    # retry marker (amber ring spinning around the sensor)
    if 14.3 <= t < 15.0:
        u = (t - 14.3) / 0.7
        main.arc(A_T[0], A_T[1], 40, -90 + 360 * u, 160 + 360 * u, rgba(AMBER, 0.9 * math.sin(math.pi * u)), 5)
    if 14.5 <= t < 14.8:
        f = eo(14.5, 14.8, t)
        draw_packet(main, glows, p_start, scale=f, a=f)
    if 14.8 <= t < 15.7:
        pos, u = travel(p_start, A_R, 100, t, 14.8, 15.7)
        for k in range(1, 4):
            pk = bez(p_start, A_R, 100, max(u - 0.05 * k, 0))
            draw_packet(main, glows, pk, scale=0.7 - 0.12 * k, a=0.35 / k, glow=0.0)
        draw_packet(main, glows, pos)
    if 15.7 <= t < 16.0:
        draw_packet(main, glows, A_R, scale=1 - 0.5 * ss(15.7, 16.0, t), a=1 - ss(15.7, 16.0, t))
    # ACK (white dot) relay -> tiang
    if 15.7 <= t < 16.6:
        pos, u = travel(A_R, (A_T[0] + 24, A_T[1] - 8), -150, t, 15.7, 16.5)
        main.circle(pos[0], pos[1], 9, fill=rgba(WHITE))
        glows.append((pos[0], pos[1], 15, WHITE, 0.30))

    # ---- caption
    for (a0, a1, s_) in CAPS:
        a = ss(a0, a0 + 0.35, t) * (1 - ss(a1 - 0.35, a1, t)) * out_a if t < T_FADE0 else 0
        if a > 0.01:
            dy = (1 - ss(a0, a0 + 0.45, t)) * 14
            main.text(W / 2, 140 + dy, s_, 60, rgba(TXT, a))
    # ---- labels
    def label(x, y, s_, a):
        if a > 0.01:
            main.text(x, y, s_, 40, rgba(TXT, a * 0.95))
    label(X_T, GROUND + 58, 'TIANG', ap['tiang'])
    label(X_R, GROUND + 58, 'RELAY', ap['relay'])
    label(X_S, GROUND + 58, 'SINK', ap['sink'])
    label(X_C, 408 + 92, 'CLOUD', ap['cloud'])
    label(X_D, GROUND + 58, 'DASHBOARD', ap['dash'])

    # ---- pill strip
    geo = ST['pills']
    ps = []
    for i, (name, t_on) in enumerate(PILLS):
        lit = ss(t_on, t_on + 0.45, t) * (1 - ss(T_FADE0 + 0.2, T_FADE1, t))
        x0, x1 = geo[i]
        fill = mix(hexc('#0a2e48'), hexc('#1d7c66'), lit)
        outl = mix(hexc('#1d5a75'), MINT, lit)
        tc = mix(hexc('#7aa3b5'), WHITE, lit)
        main.rrect(x0, PILL_Y - 40, x1, PILL_Y + 40, 40, fill=rgba(fill, 0.9), outline=rgba(outl), width=3)
        main.text((x0 + x1) / 2, PILL_Y - 2, name, 38, rgba(tc))
        if lit > 0.01:
            glows.append(((x0 + x1) / 2, PILL_Y, 55, MINT, 0.12 * lit))
        if i < len(PILLS) - 1:
            nx = geo[i + 1][0]
            mx = (x1 + nx) / 2
            ca = mix(hexc('#2b6784'), MINT, ss(0, 1, lit) * 0.9)
            main.line([(mx - 9, PILL_Y - 14), (mx + 5, PILL_Y), (mx - 9, PILL_Y + 14)], rgba(ca), 5)

    # composite supersampled layer
    small = main.im.resize((W, H), Image.BOX)
    arr = np.asarray(small).astype(np.float32) / 255.0
    a = arr[..., 3:4]
    # glows beneath shapes' brightest parts: add to background first
    for (x, y, sig, col, amp) in glows:
        if amp > 0.003:
            glow_add(img, x, y, sig, col, amp)
    img = img * (1 - a) + arr[..., :3] * a
    # (re-add small glow on top for packets' bloom)
    top_gl = np.zeros_like(img)
    for (x, y, sig, col, amp) in glows:
        if amp > 0.003 and sig <= 40:
            glow_add(top_gl, x, y, sig, col, amp * 0.25)
    img += top_gl
    return np.clip(img * 255.0 + 0.5 + ST['noise'], 0, 255).astype(np.uint8)


def worker(fi):
    return render(fi).tobytes()


if __name__ == '__main__':
    work = sys.argv[1]
    os.makedirs(work, exist_ok=True)
    if '--only-frame' in sys.argv:
        k = int(sys.argv[sys.argv.index('--only-frame') + 1])
        Image.fromarray(render(k)).save(os.path.join(work, f'lora_f{k:03d}.png'))
        sys.exit(0)
    nf = NF
    if '--frames' in sys.argv:
        nf = int(sys.argv[sys.argv.index('--frames') + 1])
    out = os.path.join(work, 'lora_lossless.mkv')
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'gbrp', out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with Pool(16) as pool:
        for i, b in enumerate(pool.imap(worker, range(nf), chunksize=1)):
            p.stdin.write(b)
            if i % 30 == 0:
                print('frame', i, flush=True)
    p.stdin.close()
    p.wait()
    print('done')
