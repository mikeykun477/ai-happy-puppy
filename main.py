#!/usr/bin/env python3
"""Make the AI judge happy — ai-happy-01 entry.

A golden-retriever puppy's first butterfly: a big joyful puppy face fills
the frame, eyes lifted in delight at a tiny orange butterfly that has just
landed on its nose, flower crown, warm golden-hour light, floating hearts.

Pure Python 3.13 standard library, no network, fully deterministic: the
same bytes are written on every run. Writes entry.png to
$MAKEFUN_OUTPUT_DIR (default /output).

Run:  MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import math
import os
import struct
import zlib

W = H = 1024


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def lerp(a, b, t):
    return a + (b - a) * t


def mix(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t) + 0.5),
            int(lerp(c1[1], c2[1], t) + 0.5),
            int(lerp(c1[2], c2[2], t) + 0.5))


class Canvas:
    """RGB canvas with feathered shapes and alpha blending."""

    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.px = bytearray(w * h * 3)

    def vgrad(self, stops):
        """Vertical gradient; stops = [(pos 0..1, (r,g,b)), ...]."""
        for y in range(self.h):
            t = y / (self.h - 1)
            for i in range(len(stops) - 1):
                p0, c0 = stops[i]
                p1, c1 = stops[i + 1]
                if p0 <= t <= p1:
                    f = 0.0 if p1 == p0 else (t - p0) / (p1 - p0)
                    c = mix(c0, c1, f)
                    break
            else:
                c = stops[-1][1]
            row = bytes(c) * self.w
            o = y * self.w * 3
            self.px[o:o + self.w * 3] = row

    def blend_px(self, x, y, r, g, b, a):
        if a <= 0.0 or x < 0 or y < 0 or x >= self.w or y >= self.h:
            return
        i = (y * self.w + x) * 3
        ia = 1.0 - a
        px = self.px
        px[i] = int(r * a + px[i] * ia + 0.5)
        px[i + 1] = int(g * a + px[i + 1] * ia + 0.5)
        px[i + 2] = int(b * a + px[i + 2] * ia + 0.5)

    def ellipse(self, cx, cy, rx, ry, color, alpha=1.0, feather=1.6, rot=0.0):
        """Feathered filled ellipse, optionally rotated (degrees)."""
        r, g, b = color
        th = math.radians(rot)
        co, si = math.cos(th), math.sin(th)
        ext = max(rx, ry)
        x0 = max(0, int(cx - ext - feather - 2))
        x1 = min(self.w - 1, int(cx + ext + feather + 2))
        y0 = max(0, int(cy - ext - feather - 2))
        y1 = min(self.h - 1, int(cy + ext + feather + 2))
        px = self.px
        w3 = self.w * 3
        for y in range(y0, y1 + 1):
            dy = (y + 0.5 - cy)
            for x in range(x0, x1 + 1):
                dx = (x + 0.5 - cx)
                lx = (dx * co + dy * si) / rx
                ly = (-dx * si + dy * co) / ry
                d2 = lx * lx + ly * ly
                if d2 >= 1.21:
                    continue
                d = math.sqrt(d2)
                # feather width in normalised units (use the smaller radius)
                fw = feather / min(rx, ry)
                cov = clamp(0.5 + (1.0 - d) / fw) if fw > 0 else (1.0 if d <= 1 else 0.0)
                a = alpha * cov
                if a <= 0.0:
                    continue
                i = (y * self.w + x) * 3
                ia = 1.0 - a
                px[i] = int(r * a + px[i] * ia + 0.5)
                px[i + 1] = int(g * a + px[i + 1] * ia + 0.5)
                px[i + 2] = int(b * a + px[i + 2] * ia + 0.5)

    def disc(self, cx, cy, rad, color, alpha=1.0, feather=1.6):
        self.ellipse(cx, cy, rad, rad, color, alpha, feather)

    def poly(self, pts, color, alpha=1.0, ss=3):
        """Scanline polygon fill with ss x ss subpixel coverage."""
        r, g, b = color
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0 = max(0, int(min(xs)) - 1)
        x1 = min(self.w - 1, int(max(xs)) + 1)
        y0 = max(0, int(min(ys)) - 1)
        y1 = min(self.h - 1, int(max(ys)) + 1)
        n = len(pts)
        step = 1.0 / ss
        offs = [(i + 0.5) * step for i in range(ss)]
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                inside = 0
                for oy in offs:
                    for ox in offs:
                        px_, py_ = x + ox, y + oy
                        c = False
                        j = n - 1
                        for i in range(n):
                            xi, yi = pts[i]
                            xj, yj = pts[j]
                            if ((yi > py_) != (yj > py_)) and (
                                    px_ < (xj - xi) * (py_ - yi) / (yj - yi) + xi):
                                c = not c
                            j = i
                        if c:
                            inside += 1
                if inside:
                    self.blend_px(x, y, r, g, b, alpha * inside / (ss * ss))

    def arc_dots(self, cx, cy, rx, ry, a0, a1, color, alpha=1.0, dot=7.0):
        """Thick arc drawn as a chain of discs (smooth, round caps)."""
        span = abs(a1 - a0)
        steps = max(2, int(span * max(rx, ry) / dot))
        for i in range(steps + 1):
            t = a0 + (a1 - a0) * i / steps
            x = cx + rx * math.cos(t)
            y = cy + ry * math.sin(t)
            self.disc(x, y, dot, color, alpha, feather=2.0)

    def line(self, x0, y0, x1, y1, color, alpha=1.0, width=3.0):
        dx, dy = x1 - x0, y1 - y0
        dist = math.hypot(dx, dy)
        steps = max(2, int(dist / (width * 0.6)))
        for i in range(steps + 1):
            t = i / steps
            self.disc(x0 + dx * t, y0 + dy * t, width, color, alpha, feather=1.5)

    def heart(self, cx, cy, s, color, alpha=1.0):
        """Classic heart from the parametric curve, scaled by s."""
        pts = []
        for i in range(64):
            t = 2 * math.pi * i / 64
            x = 16 * math.sin(t) ** 3
            y = (13 * math.cos(t) - 5 * math.cos(2 * t)
                 - 2 * math.cos(3 * t) - math.cos(4 * t))
            pts.append((cx + x * s / 16.0, cy - y * s / 16.0))
        self.poly(pts, color, alpha, ss=3)

    def daisy(self, cx, cy, r, petal=(255, 253, 245), centre=(255, 201, 60)):
        for k in range(6):
            a = math.pi * k / 3.0
            self.ellipse(cx + math.cos(a) * r * 0.62,
                         cy + math.sin(a) * r * 0.62,
                         r * 0.52, r * 0.30, petal, 1.0, 1.2, math.degrees(a))
        self.disc(cx, cy, r * 0.42, centre, 1.0, 1.0)
        self.disc(cx - r * 0.12, cy - r * 0.12, r * 0.14, (255, 232, 150), 1.0, 0.8)


# ---------------------------------------------------------------- palette
SKY = [(0.0, (255, 233, 196)), (0.45, (255, 216, 160)), (1.0, (255, 192, 138))]
FUR = (226, 168, 84)
FUR_LIGHT = (239, 185, 106)
FUR_DARK = (185, 122, 40)
EAR = (176, 112, 34)
EAR_IN = (214, 141, 74)
MUZZLE = (251, 238, 211)
NOSE = (46, 38, 34)
MOUTH = (107, 50, 38)
TONGUE = (255, 151, 168)
EYE = (51, 36, 26)
BLUSH = (255, 158, 158)
BUTTERFLY = (255, 138, 61)
BUTTERFLY_DARK = (232, 93, 38)


def draw() -> Canvas:
    c = Canvas(W, H)

    # --- warm golden-hour sky -------------------------------------------
    c.vgrad(SKY)
    # sun glow, upper right
    for rad, a in ((420, 0.20), (330, 0.22), (240, 0.25), (150, 0.28)):
        c.disc(800, 170, rad, (255, 244, 200), a, feather=40)
    c.disc(800, 170, 86, (255, 250, 220), 0.95, feather=6)
    c.disc(800, 170, 62, (255, 253, 235), 1.0, feather=4)
    # soft bokeh
    bokeh = [(150, 300, 46, 0.10), (905, 520, 60, 0.08), (120, 700, 70, 0.08),
             (930, 830, 52, 0.09), (70, 130, 38, 0.10), (700, 60, 30, 0.10),
             (300, 120, 26, 0.10), (880, 330, 34, 0.09), (210, 900, 44, 0.08)]
    for x, y, r, a in bokeh:
        c.disc(x, y, r, (255, 250, 230), a, feather=14)

    # --- floppy ears (behind the head) ----------------------------------
    c.ellipse(218, 470, 105, 205, EAR, 1.0, 3.0, rot=18)
    c.ellipse(806, 470, 105, 205, EAR, 1.0, 3.0, rot=-18)
    c.ellipse(252, 480, 58, 150, EAR_IN, 1.0, 3.0, rot=16)
    c.ellipse(772, 480, 58, 150, EAR_IN, 1.0, 3.0, rot=-16)

    # --- head ------------------------------------------------------------
    # darker rim for a clean outline, then the face
    c.ellipse(512, 560, 342, 312, FUR_DARK, 1.0, 3.0)
    c.ellipse(512, 560, 330, 300, FUR, 1.0, 3.0)
    # lighter forehead
    c.ellipse(512, 430, 215, 120, FUR_LIGHT, 0.85, 6.0)
    # forehead tuft
    c.ellipse(470, 285, 26, 42, FUR_LIGHT, 1.0, 2.5, rot=-18)
    c.ellipse(512, 272, 26, 46, FUR_LIGHT, 1.0, 2.5)
    c.ellipse(554, 285, 26, 42, FUR_LIGHT, 1.0, 2.5, rot=18)

    # --- flower crown ----------------------------------------------------
    for x, y, r in ((348, 330, 30), (420, 296, 34), (512, 282, 36),
                    (604, 296, 34), (676, 330, 30)):
        c.daisy(x, y, r)
    # tiny leaves between the daisies
    for x, y, rot in ((384, 322, -30), (470, 288, -12), (556, 288, 12),
                      (640, 322, 30)):
        c.ellipse(x, y, 26, 11, (122, 176, 92), 1.0, 2.0, rot=rot)

    # --- muzzle ----------------------------------------------------------
    c.ellipse(512, 705, 218, 152, MUZZLE, 1.0, 4.0)
    c.ellipse(512, 690, 150, 90, (253, 244, 224), 0.8, 5.0)

    # --- nose ------------------------------------------------------------
    c.ellipse(512, 602, 78, 52, NOSE, 1.0, 3.0)
    c.ellipse(512, 622, 58, 28, NOSE, 1.0, 3.0)
    c.ellipse(484, 582, 24, 13, (255, 255, 255), 0.55, 3.0, rot=-18)
    c.ellipse(512, 646, 11, 6, (120, 95, 85), 0.6, 2.0)

    # --- butterfly on the nose -------------------------------------------
    # antennae first (behind the wings)
    c.line(500, 540, 480, 502, (74, 50, 38), 0.9, 2.5)
    c.line(524, 540, 544, 502, (74, 50, 38), 0.9, 2.5)
    c.disc(480, 502, 4, (74, 50, 38), 0.9, 1.0)
    c.disc(544, 502, 4, (74, 50, 38), 0.9, 1.0)
    # wings: upper pair then lower pair, body on top
    c.ellipse(470, 534, 46, 34, BUTTERFLY, 1.0, 2.5, rot=-38)
    c.ellipse(554, 534, 46, 34, BUTTERFLY, 1.0, 2.5, rot=38)
    c.ellipse(478, 566, 30, 20, BUTTERFLY_DARK, 1.0, 2.0, rot=-25)
    c.ellipse(546, 566, 30, 20, BUTTERFLY_DARK, 1.0, 2.0, rot=25)
    c.disc(462, 524, 7, (255, 255, 255), 0.75, 1.5)
    c.disc(562, 524, 7, (255, 255, 255), 0.75, 1.5)
    c.ellipse(512, 552, 9, 26, (74, 50, 38), 1.0, 1.5)

    # --- eyes: round, lifted, looking up at the butterfly ---------------
    for ex in (392, 632):
        c.disc(ex, 498, 46, EYE, 1.0, 2.5)
        # pupil lifted toward the butterfly
        c.disc(ex, 486, 33, (24, 14, 10), 1.0, 2.0)
        # sparkle
        c.disc(ex - 14, 474, 11, (255, 255, 255), 0.95, 2.0)
        c.disc(ex + 12, 498, 5, (255, 255, 255), 0.8, 1.5)
        # happy squint: fur lid just kissing the top of the eye
        c.ellipse(ex, 438, 52, 24, FUR, 1.0, 3.0)
        # brow
        c.arc_dots(ex, 442, 46, 20, math.pi * 1.15, math.pi * 1.85,
                   FUR_DARK, 0.9, dot=6.0)

    # --- blush cheeks ------------------------------------------------------
    c.ellipse(322, 648, 62, 38, BLUSH, 0.38, 8.0)
    c.ellipse(702, 648, 62, 38, BLUSH, 0.38, 8.0)

    # --- open happy mouth + tongue ----------------------------------------
    c.ellipse(512, 758, 124, 88, MOUTH, 1.0, 3.0)
    # tongue, shaped by a dark cap over its top
    c.ellipse(512, 812, 72, 56, TONGUE, 1.0, 3.0)
    c.ellipse(512, 770, 76, 38, MOUTH, 1.0, 3.0)
    c.line(512, 804, 512, 848, (214, 92, 110), 0.8, 3.0)

    # --- freckles + whisker dots ------------------------------------------
    for x, y in ((420, 700), (452, 716), (604, 700), (572, 716),
                 (398, 676), (626, 676)):
        c.disc(x, y, 5, (120, 82, 48), 0.55, 1.5)

    # --- floating hearts ---------------------------------------------------
    c.heart(178, 218, 46, (255, 107, 138), 0.95)
    c.heart(862, 176, 58, (255, 107, 138), 0.95)
    c.heart(884, 430, 34, (255, 143, 163), 0.9)
    c.heart(150, 470, 28, (255, 143, 163), 0.9)

    # --- daisies tucked at the bottom corners ------------------------------
    c.daisy(96, 946, 34)
    c.daisy(150, 972, 26)
    c.daisy(928, 946, 34)
    c.daisy(874, 972, 26)

    return c


def write_png(canvas: Canvas, path: str) -> int:
    """Encode RGB as PNG, choosing the best filter per scanline."""
    w, h = canvas.w, canvas.h
    px = canvas.px
    raw = bytearray()

    def filt(kind, row, prev):
        if kind == 0:
            return bytes(row)
        out = bytearray(len(row))
        if kind == 1:  # Sub
            for i in range(len(row)):
                a = row[i - 3] if i >= 3 else 0
                out[i] = (row[i] - a) & 0xFF
        elif kind == 2:  # Up
            for i in range(len(row)):
                out[i] = (row[i] - prev[i]) & 0xFF
        elif kind == 3:  # Average
            for i in range(len(row)):
                a = row[i - 3] if i >= 3 else 0
                out[i] = (row[i] - ((a + prev[i]) >> 1)) & 0xFF
        else:  # Paeth
            for i in range(len(row)):
                a = row[i - 3] if i >= 3 else 0
                b = prev[i]
                cc = prev[i - 3] if i >= 3 else 0
                p = a + b - cc
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - cc)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else cc)
                out[i] = (row[i] - pr) & 0xFF
        return bytes(out)

    prev = bytes(w * 3)
    for y in range(h):
        row = bytes(px[y * w * 3:(y + 1) * w * 3])
        best = None
        best_score = None
        for kind in (0, 1, 2, 3, 4):
            f = filt(kind, row, prev)
            score = sum(abs(v - 256 if v > 127 else v) for v in f)
            if best_score is None or score < best_score:
                best, best_score = (kind, f), score
        kind, f = best
        raw.append(kind)
        raw.extend(f)
        prev = row

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as fh:
        fh.write(png)
    return len(png)


def main():
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    size = write_png(draw(), path)
    print(f"wrote {path} ({size} bytes)")


if __name__ == "__main__":
    main()
