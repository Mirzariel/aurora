"""Loop-seam check: mean abs pixel difference (0-255, RGB) between consecutive frames vs. the last->first seam."""
import sys, subprocess
import numpy as np
W, H = 1920, 1080
def frames(path):
    p = subprocess.Popen(['ffmpeg', '-loglevel', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
for path in sys.argv[1:]:
    prev = first = None
    d = []
    cnt = 0
    for f in frames(path):
        f = f[::2, ::2].astype(np.int16)
        if first is None:
            first = f
        if prev is not None:
            d.append(np.abs(f - prev).mean())
        prev = f
        cnt += 1
    seam = np.abs(first - prev).mean()
    d = np.array(d)
    print(f'{path}: frames={cnt} neighbor mean={d.mean():.4f} median={np.median(d):.4f} p95={np.percentile(d,95):.4f} max={d.max():.4f} | seam(last->first)={seam:.4f}')
