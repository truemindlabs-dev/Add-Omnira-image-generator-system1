"""
image_engine.py — True Alpha RGBA Image Generator Engine
Core generator yang menghasilkan PNG dengan background benar-benar transparan.
Mendukung berbagai style berdasarkan prompt.
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
import math, io, re, hashlib, colorsys
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

class ImageStyle(str, Enum):
    AUTO       = "auto"        # Deteksi otomatis dari prompt
    GEOMETRIC  = "geometric"   # Bentuk geometris abstrak
    GRADIENT   = "gradient"    # Gradient artistik
    GLOW       = "glow"        # Efek cahaya glow
    STARBURST  = "starburst"   # Sinar radial
    BADGE      = "badge"       # Badge/icon glassmorphism
    PORTRAIT   = "portrait"    # Silhouette/portrait artistik
    LANDSCAPE  = "landscape"   # Landscape abstrak
    TEXT_ART   = "text_art"    # Tipografi artistik
    MANDALA    = "mandala"     # Pola mandala
    WAVE       = "wave"        # Gelombang cair
    PIXEL      = "pixel"       # Pixel art
    FLOWER     = "flower"      # Bunga artistik berlapis dengan true alpha
    ISOMETRIC  = "isometric"   # Scene 3D isometric dengan true alpha

@dataclass
class GenerationConfig:
    prompt: str
    width: int = 512
    height: int = 512
    style: ImageStyle = ImageStyle.AUTO
    seed: Optional[int] = None

@dataclass
class GenerationResult:
    image: Image.Image
    style_used: str
    alpha_verified: bool
    transparent_pct: float


# ================================================================
# UTILITIES
# ================================================================

def prompt_to_colors(prompt: str) -> Tuple[Tuple, Tuple, Tuple]:
    """Ekstrak palet warna dari kata kunci dalam prompt."""
    p = prompt.lower()
    palettes = {
        "merah|red|api|fire|marah|cinta|love":    ((220,50,70), (255,120,80), (180,20,40)),
        "biru|blue|laut|ocean|langit|sky|air":     ((30,100,220), (80,180,255), (10,60,160)),
        "hijau|green|alam|nature|hutan|forest":    ((40,180,80), (100,220,120), (20,120,50)),
        "kuning|yellow|matahari|sun|emas|gold":    ((255,200,30), (255,240,100), (200,140,0)),
        "ungu|purple|violet|mistis|mystic|magic":  ((140,50,200), (200,100,255), (80,20,140)),
        "orange|jingga|senja|sunset|autumn":       ((255,120,30), (255,180,80), (200,70,10)),
        "pink|merah muda|bunga|flower|sakura":     ((255,100,160), (255,180,210), (200,50,120)),
        "putih|white|bersih|clean|salju|snow":     ((220,230,240), (255,255,255), (180,190,210)),
        "hitam|black|gelap|dark|malam|night":      ((30,30,50), (80,80,120), (10,10,20)),
        "cyan|tosca|turquoise":                    ((0,180,200), (80,220,230), (0,120,140)),
    }
    for keywords, colors in palettes.items():
        if any(re.search(kw, p) for kw in keywords.split("|")):
            return colors

    # Default: hash prompt → warna deterministik
    h = int(hashlib.md5(prompt.encode()).hexdigest()[:6], 16)
    hue = (h % 360) / 360.0
    r,g,b = [int(x*255) for x in colorsys.hsv_to_rgb(hue, 0.7, 0.9)]
    r2,g2,b2 = [int(x*255) for x in colorsys.hsv_to_rgb((hue+0.3)%1, 0.6, 1.0)]
    r3,g3,b3 = [int(x*255) for x in colorsys.hsv_to_rgb((hue+0.6)%1, 0.8, 0.7)]
    return (r,g,b), (r2,g2,b2), (r3,g3,b3)


def detect_style(prompt: str) -> ImageStyle:
    """Deteksi style terbaik dari kata kunci prompt."""
    p = prompt.lower()
    rules = [
        (ImageStyle.FLOWER,    ["bunga","flower","petal","rose","mawar","sakura","flora","bloom","blossom","lotus","teratai","dahlia","tulip"]),
        (ImageStyle.ISOMETRIC, ["isometric","isometri","3d","cube","kubus","kota","city","building","gedung","perspektif","voxel","minecraft"]),
        (ImageStyle.MANDALA,   ["mandala","pola","pattern","simetri","symmetric","spiritual"]),
        (ImageStyle.WAVE,      ["gelombang","wave","cair","liquid","fluid","ombak","laut","ocean"]),
        (ImageStyle.GLOW,      ["cahaya","glow","neon","bercahaya","radiant","glowing","shine"]),
        (ImageStyle.STARBURST, ["bintang","star","sinar","sun","matahari","burst","ray","cahaya matahari"]),
        (ImageStyle.BADGE,     ["badge","icon","logo","sticker","label","emblem","shield"]),
        (ImageStyle.PORTRAIT,  ["wajah","face","orang","person","manusia","human","portrait","karakter"]),
        (ImageStyle.LANDSCAPE, ["pemandangan","landscape","alam","nature","gunung","mountain"]),
        (ImageStyle.TEXT_ART,  ["teks","text","tulisan","kata","word","huruf","typography","font"]),
        (ImageStyle.GRADIENT,  ["gradien","gradient","warna","colorful","pelangi","rainbow","abstract"]),
        (ImageStyle.PIXEL,     ["pixel","piksel","retro","8bit","game","sprite"]),
        (ImageStyle.GEOMETRIC, ["geometri","geometric","bentuk","shape","sudut","angular","abstract"]),
    ]
    for style, keywords in rules:
        if any(kw in p for kw in keywords):
            return style
    return ImageStyle.GEOMETRIC


def new_canvas(width: int, height: int) -> Tuple[Image.Image, ImageDraw.Draw]:
    """Buat canvas RGBA kosong — background benar-benar transparan."""
    img  = Image.new("RGBA", (width, height), (0, 0, 0, 0))  # TRUE ALPHA
    draw = ImageDraw.Draw(img)
    return img, draw


def verify_alpha(img: Image.Image) -> Tuple[bool, float]:
    data  = np.array(img)
    alpha = data[:, :, 3]
    has_t = bool(np.any(alpha == 0))
    pct   = round(100.0 * np.sum(alpha == 0) / alpha.size, 2)
    return has_t, pct


def try_font(size: int) -> ImageFont.ImageFont:
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except:
            pass
    return ImageFont.load_default()


# ================================================================
# STYLE GENERATORS
# ================================================================

def gen_geometric(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)
    rng = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)
    cx, cy = W // 2, H // 2

    # Bentuk berlapis
    for i in range(8, 0, -1):
        alpha = int(180 * (i / 8))
        col   = c1 if i % 3 == 0 else (c2 if i % 3 == 1 else c3)
        r     = int((min(W,H) // 2) * (i / 8))
        ang   = rng.uniform(0, math.pi * 2)
        sides = rng.integers(3, 8)

        pts = []
        for j in range(sides):
            a = ang + j * (2 * math.pi / sides)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        draw.polygon(pts, fill=(*col, alpha))

    # Lingkaran tengah
    r2 = min(W,H) // 6
    draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(*c1, 240))
    draw.ellipse([cx-r2//2, cy-r2//2, cx+r2//2, cy+r2//2], fill=(255,255,255,100))
    return img


def gen_gradient(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    pixels = np.zeros((H, W, 4), dtype=np.uint8)

    for y in range(H):
        for x in range(W):
            t   = x / W
            s   = y / H
            r   = int(c1[0]*(1-t) + c2[0]*t*(1-s) + c3[0]*s*t)
            g   = int(c1[1]*(1-t) + c2[1]*t*(1-s) + c3[1]*s*t)
            b   = int(c1[2]*(1-t) + c2[2]*t*(1-s) + c3[2]*s*t)
            # Alpha: pudar di tepi
            dx  = abs(x - W/2) / (W/2)
            dy  = abs(y - H/2) / (H/2)
            a   = int(255 * max(0, 1 - (dx**2 + dy**2)**0.5 * 0.6))
            pixels[y,x] = [r,g,b,a]

    img = Image.fromarray(pixels, "RGBA")

    # Overlay lingkaran glow
    overlay, draw = new_canvas(W, H)
    cx, cy = W//2, H//2
    for r in range(min(W,H)//3, 0, -5):
        a = int(60 * (1 - r/(min(W,H)//3)))
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(*c2, a))
    return Image.alpha_composite(img, overlay)


def gen_glow(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)
    cx, cy = W//2, H//2
    rng = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)

    # Multiple glow sources
    sources = [(cx, cy, c1, min(W,H)//3)]
    for _ in range(3):
        x = rng.integers(W//4, 3*W//4)
        y = rng.integers(H//4, 3*H//4)
        col = c2 if rng.random() > 0.5 else c3
        sources.append((x, y, col, rng.integers(W//8, W//4)))

    for sx, sy, col, max_r in sources:
        glow = Image.new("RGBA", (W,H), (0,0,0,0))
        gd   = ImageDraw.Draw(glow)
        for r in range(max_r, 0, -3):
            a = int(120 * (1 - r/max_r)**1.5)
            gd.ellipse([sx-r, sy-r, sx+r, sy+r], fill=(*col, a))
        glow = glow.filter(ImageFilter.GaussianBlur(radius=15))
        img  = Image.alpha_composite(img, glow)

    # Titik pusat terang
    draw = ImageDraw.Draw(img)
    r2 = min(W,H) // 12
    draw.ellipse([cx-r2, cy-r2, cx+r2, cy+r2], fill=(255,255,255,220))
    return img


def gen_starburst(cfg: GenerationConfig, c1, c2, c3, rays=16) -> Image.Image:
    W, H = cfg.width, cfg.height
    cx, cy = W/2, H/2
    pixels = np.zeros((H, W, 4), dtype=np.uint8)

    for y in range(H):
        for x in range(W):
            dx, dy = x - cx, y - cy
            r      = math.sqrt(dx*dx + dy*dy)
            ang    = math.atan2(dy, dx)
            radial = max(0, 1 - r / (min(W,H)/2))
            ray_f  = 0.5 + 0.5 * math.cos(rays * ang)
            secondary = 0.3 + 0.3 * math.cos(rays*2 * ang)
            t      = ray_f * 0.7 + secondary * 0.3
            col    = (int(c1[0]*t + c2[0]*(1-t)),
                      int(c1[1]*t + c2[1]*(1-t)),
                      int(c1[2]*t + c2[2]*(1-t)))
            a      = int(radial * (ray_f * 0.8 + 0.2) * 255)
            pixels[y,x] = [*col, a]

    return Image.fromarray(pixels, "RGBA")


def gen_badge(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)
    pad = W // 8
    cx, cy = W//2, H//2

    # Background kaca
    draw.rounded_rectangle([pad, pad, W-pad, H-pad], radius=W//8,
                           fill=(*c1, 50))
    draw.rounded_rectangle([pad, pad, W-pad, H-pad], radius=W//8,
                           outline=(*c2, 160), width=3)
    # Gloss
    draw.rounded_rectangle([pad+10, pad+10, W-pad-10, pad+H//6],
                           radius=W//12, fill=(255,255,255,35))

    # Ikon bintang
    star_pts = []
    for i in range(10):
        ang = math.radians(i*36 - 90)
        r   = W//5 if i%2==0 else W//10
        star_pts.append((cx + r*math.cos(ang), cy + r*math.sin(ang)))
    draw.polygon(star_pts, fill=(*c1, 230))
    draw.polygon(star_pts, outline=(255,255,220,200), width=2)

    # Teks prompt (3 kata pertama)
    words = cfg.prompt.split()[:3]
    label = " ".join(words).upper()
    font  = try_font(max(14, W//16))
    draw.text((cx - W//4, H - H//5), label, fill=(255,255,255,200), font=font)
    return img


def gen_mandala(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)
    cx, cy = W//2, H//2
    rng = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)
    symmetry = 8
    layers   = 6

    for layer in range(layers, 0, -1):
        r     = int((min(W,H)//2 - 10) * (layer/layers))
        alpha = int(200 * (layer/layers))
        col   = c1 if layer%3==0 else (c2 if layer%3==1 else c3)
        petals = symmetry * (layer % 3 + 2)

        for i in range(petals):
            ang     = i * (2*math.pi/petals)
            offset  = rng.uniform(0.1, 0.4) * r
            px      = cx + r * math.cos(ang)
            py      = cy + r * math.sin(ang)
            pr      = max(5, int(r * rng.uniform(0.08, 0.2)))
            draw.ellipse([px-pr, py-pr, px+pr, py+pr], fill=(*col, alpha))

        # Ring
        for i in range(0, 360, 360//symmetry):
            ang = math.radians(i)
            x1  = cx + (r-10)*math.cos(ang)
            y1  = cy + (r-10)*math.sin(ang)
            x2  = cx + r*math.cos(ang)
            y2  = cy + r*math.sin(ang)
            draw.line([(x1,y1),(x2,y2)], fill=(*col, alpha//2), width=2)

    # Inti
    r0 = min(W,H)//10
    draw.ellipse([cx-r0, cy-r0, cx+r0, cy+r0], fill=(*c1, 255))
    draw.ellipse([cx-r0//2, cy-r0//2, cx+r0//2, cy+r0//2], fill=(255,255,255,180))
    return img


def gen_wave(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    pixels = np.zeros((H, W, 4), dtype=np.uint8)
    rng = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)
    waves = [(rng.uniform(0.01, 0.04), rng.uniform(0, math.pi*2), rng.uniform(0.3, 0.7), c)
             for c in [c1, c2, c3]]

    for y in range(H):
        for x in range(W):
            val = 0
            for freq, phase, amp, _ in waves:
                val += amp * math.sin(freq * x * math.pi * 2 + phase + y * 0.01)
            val = max(0.0, min(1.0, (val + 1.5) / 3.0))  # Clamp 0..1
            t   = val
            col = (
                max(0, min(255, int(c1[0]*t + c2[0]*(1-t)))),
                max(0, min(255, int(c1[1]*t + c2[1]*(1-t)))),
                max(0, min(255, int(c1[2]*t + c2[2]*(1-t)))),
            )
            # Alpha: berbasis posisi vertikal + nilai gelombang
            a = max(0, min(255, int(255 * (0.4 + 0.6 * val) * max(0, 1 - abs(y/H - 0.5)*1.5))))
            pixels[y,x] = [*col, a]

    img = Image.fromarray(pixels, "RGBA")
    return img.filter(ImageFilter.GaussianBlur(radius=1))


def gen_portrait(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)
    cx, cy = W//2, H//2

    # Latar aura
    aura = Image.new("RGBA", (W,H), (0,0,0,0))
    for r in range(min(W,H)//2, 0, -4):
        a = int(80 * (1 - r/(min(W,H)//2))**0.5)
        ad = ImageDraw.Draw(aura)
        ad.ellipse([cx-r, cy-r//2-H//8, cx+r, cy+r//2+H//8], fill=(*c1, a))
    aura = aura.filter(ImageFilter.GaussianBlur(30))
    img  = Image.alpha_composite(img, aura)
    draw = ImageDraw.Draw(img)

    # Silhouette kepala & bahu
    head_r = min(W,H) // 5
    head_y = cy - H//8
    draw.ellipse([cx-head_r, head_y-head_r, cx+head_r, head_y+head_r],
                 fill=(*c2, 230))
    # Bahu
    sw = W//2
    sh = H//6
    draw.ellipse([cx-sw, head_y+head_r, cx+sw, head_y+head_r+sh*2],
                 fill=(*c2, 200))

    # Detail wajah
    eye_r = head_r // 5
    for ex in [cx - head_r//3, cx + head_r//3]:
        draw.ellipse([ex-eye_r, head_y-eye_r//2, ex+eye_r, head_y+eye_r//2],
                     fill=(255,255,255,200))
    # Highlight
    draw.ellipse([cx-head_r//4, head_y-head_r//2, cx+head_r//4, head_y-head_r//4],
                 fill=(255,255,255,60))

    return img


def gen_landscape(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)
    rng = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)

    # Langit gradient
    sky = Image.new("RGBA", (W,H), (0,0,0,0))
    for y in range(H//2):
        t = y / (H//2)
        r = int(c1[0]*(1-t) + c2[0]*t)
        g = int(c1[1]*(1-t) + c2[1]*t)
        b = int(c1[2]*(1-t) + c2[2]*t)
        a = int(220 * (1 - t * 0.3))
        ImageDraw.Draw(sky).line([(0,y),(W,y)], fill=(r,g,b,a))
    img = Image.alpha_composite(img, sky)
    draw = ImageDraw.Draw(img)

    # Gunung/bukit
    for i in range(3):
        peak_x = rng.integers(W//4, 3*W//4)
        peak_y = rng.integers(H//4, H//2)
        base_w = rng.integers(W//3, 2*W//3)
        pts = [(peak_x-base_w//2, H//2+20), (peak_x, peak_y), (peak_x+base_w//2, H//2+20)]
        draw.polygon(pts, fill=(*c3, int(180 - i*30)))

    # Tanah/ground
    draw.rectangle([0, H//2, W, H], fill=(*c3, 180))

    # Matahari/bulan
    sx, sy = W//5, H//5
    draw.ellipse([sx-40, sy-40, sx+40, sy+40], fill=(255,230,100,230))
    draw.ellipse([sx-20, sy-20, sx+20, sy+20], fill=(255,255,200,255))
    return img


def gen_text_art(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    img, draw = new_canvas(W, H)

    # Background gradient ringan
    for y in range(H):
        t = y / H
        a = int(40 * (1 - abs(t - 0.5) * 2))
        draw.line([(0,y),(W,y)], fill=(*c1, a))

    # Teks utama besar
    words = cfg.prompt.split()
    main_text = words[0].upper() if words else "AI"
    font_big  = try_font(min(W, H) // 3)

    # Shadow
    draw.text((W//2 - W//4 + 4, H//2 - H//5 + 4), main_text,
              fill=(0,0,0,100), font=font_big)
    # Teks utama dengan alpha
    draw.text((W//2 - W//4, H//2 - H//5), main_text,
              fill=(*c1, 240), font=font_big)

    # Sub-teks
    if len(words) > 1:
        sub = " ".join(words[1:]).upper()
        font_sm = try_font(min(W,H) // 10)
        draw.text((W//2 - W//5, H//2 + H//8), sub,
                  fill=(*c2, 180), font=font_sm)

    # Garis dekorasi
    draw.line([(W//8, H//2+5), (7*W//8, H//2+5)], fill=(*c2, 120), width=2)
    return img


def gen_pixel(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    W, H = cfg.width, cfg.height
    CELL = max(16, min(W,H) // 20)
    cols = W // CELL
    rows = H // CELL
    rng  = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)

    img, draw = new_canvas(W, H)
    palette = [c1, c2, c3, (255,255,255), (50,50,50)]

    for gy in range(rows):
        for gx in range(cols):
            if rng.random() < 0.3:
                continue  # Pixel transparan
            col = palette[rng.integers(len(palette))]
            a   = rng.integers(150, 255)
            x0, y0 = gx*CELL, gy*CELL
            draw.rectangle([x0, y0, x0+CELL-1, y0+CELL-1], fill=(*col, a))
    return img


# ================================================================
# FLOWER GENERATOR — Bunga Artistik Berlapis RGBA
# ================================================================

def gen_flower(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    """
    Bunga artistik berlapis dengan true alpha.
    - Kelopak digambar satu per satu dengan rotasi
    - Setiap layer: kelopak luar → dalam → putik → detail
    - Background benar-benar transparan (RGBA alpha=0)
    - Mendukung berbagai jenis bunga dari prompt:
      mawar, sakura, lotus, dahlia, tulip, dll.
    """
    W, H  = cfg.width, cfg.height
    cx, cy = W / 2, H / 2
    rng   = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)
    p     = cfg.prompt.lower()

    # Tentukan karakter bunga dari prompt
    if any(k in p for k in ["mawar", "rose", "red"]):
        petals, layers, petal_ratio = 5, 4, 0.45
        c1 = (200, 30, 50); c2 = (240, 80, 100); c3 = (255, 160, 140)
    elif any(k in p for k in ["sakura", "cherry", "pink"]):
        petals, layers, petal_ratio = 5, 3, 0.38
        c1 = (255, 160, 180); c2 = (255, 200, 210); c3 = (255, 230, 235)
    elif any(k in p for k in ["lotus", "teratai"]):
        petals, layers, petal_ratio = 8, 4, 0.42
        c1 = (220, 100, 160); c2 = (240, 150, 190); c3 = (255, 220, 230)
    elif any(k in p for k in ["matahari", "sunflower", "yellow"]):
        petals, layers, petal_ratio = 13, 2, 0.50
        c1 = (255, 200, 20); c2 = (255, 220, 60); c3 = (200, 130, 20)
    elif any(k in p for k in ["dahlia"]):
        petals, layers, petal_ratio = 12, 5, 0.35
        c1 = (180, 40, 120); c2 = (220, 80, 160); c3 = (255, 140, 200)
    elif any(k in p for k in ["tulip"]):
        petals, layers, petal_ratio = 6, 2, 0.50
        c1 = (200, 50, 80); c2 = (240, 100, 120); c3 = (255, 200, 180)
    else:
        # Bunga generik berdasarkan warna dari prompt
        petals     = rng.integers(5, 9)
        layers     = rng.integers(3, 5)
        petal_ratio = rng.uniform(0.38, 0.50)

    max_r    = min(W, H) * 0.46
    img      = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # TRUE ALPHA

    # ── Layer 1: Aura latar belakang bunga ──
    aura = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for r in range(int(max_r * 0.9), 0, -6):
        t = r / (max_r * 0.9)
        a = int(45 * (1 - t) ** 1.8)
        ImageDraw.Draw(aura).ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(*c2, a)
        )
    aura = aura.filter(ImageFilter.GaussianBlur(radius=max_r * 0.12))
    img  = Image.alpha_composite(img, aura)

    # ── Layer 2: Kelopak per layer (luar → dalam) ──
    for layer_idx in range(layers):
        t        = layer_idx / max(layers - 1, 1)
        layer_r  = max_r * (1 - t * 0.55)
        petal_h  = layer_r * petal_ratio * (1 - t * 0.2)
        petal_w  = layer_r * 0.32 * (1 + t * 0.15)
        rot_off  = (layer_idx * math.pi / petals) * (0.5 if layer_idx % 2 else 0)

        # Interpolasi warna antar layer
        col = (
            int(c1[0] * t + c2[0] * (1 - t)),
            int(c1[1] * t + c2[1] * (1 - t)),
            int(c1[2] * t + c2[2] * (1 - t)),
        )
        alpha_petal = int(200 + 40 * t)

        for p_idx in range(petals):
            angle = rot_off + p_idx * (2 * math.pi / petals)

            # Buat kelopak sebagai ellipse dirotasi
            petal_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            pd = ImageDraw.Draw(petal_layer)

            # Titik pusat kelopak
            px = cx + layer_r * 0.55 * math.cos(angle)
            py = cy + layer_r * 0.55 * math.sin(angle)

            # Gambar kelopak sebagai polygon oval
            pts = []
            num_pts = 24
            for k in range(num_pts):
                a2 = k * (2 * math.pi / num_pts)
                # Bentuk kelopak: lebih panjang ke arah luar, meruncing
                rx = petal_w * (0.5 + 0.5 * math.cos(a2)) * 0.9
                ry = petal_h * math.sin(a2) if math.sin(a2) > 0 else petal_h * math.sin(a2) * 0.4
                # Rotasi sesuai arah kelopak
                rrx = rx * math.cos(angle) - ry * math.sin(angle)
                rry = rx * math.sin(angle) + ry * math.cos(angle)
                pts.append((px + rrx, py + rry))

            if len(pts) >= 3:
                pd.polygon(pts, fill=(*col, alpha_petal))

                # Garis vena kelopak
                tip_x = cx + layer_r * math.cos(angle)
                tip_y = cy + layer_r * math.sin(angle)
                base_x = cx + layer_r * 0.1 * math.cos(angle)
                base_y = cy + layer_r * 0.1 * math.sin(angle)
                pd.line([(base_x, base_y), (tip_x, tip_y)],
                        fill=(255, 255, 255, 50), width=1)

            img = Image.alpha_composite(img, petal_layer)

    # ── Layer 3: Putik (stamen) ──
    draw = ImageDraw.Draw(img)
    stamen_r = max_r * 0.14
    # Lingkaran putik utama
    draw.ellipse(
        [cx - stamen_r, cy - stamen_r, cx + stamen_r, cy + stamen_r],
        fill=(*c3, 240)
    )
    # Lingkaran dalam putik
    inner_r = stamen_r * 0.55
    draw.ellipse(
        [cx - inner_r, cy - inner_r, cx + inner_r, cy + inner_r],
        fill=(255, 240, 180, 250)
    )
    # Titik-titik serbuk sari
    sari_count = 8
    sari_r = stamen_r * 0.7
    for i in range(sari_count):
        ang = i * (2 * math.pi / sari_count)
        sx = cx + sari_r * math.cos(ang)
        sy = cy + sari_r * math.sin(ang)
        dot_r = stamen_r * 0.12
        draw.ellipse([sx - dot_r, sy - dot_r, sx + dot_r, sy + dot_r],
                     fill=(255, 220, 50, 230))

    # ── Layer 4: Highlight glossy di kelopak atas ──
    gloss = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd    = ImageDraw.Draw(gloss)
    gloss_r = max_r * 0.25
    gd.ellipse(
        [cx - gloss_r * 1.2, cy - gloss_r * 1.5,
         cx + gloss_r * 0.4, cy - gloss_r * 0.2],
        fill=(255, 255, 255, 30)
    )
    gloss = gloss.filter(ImageFilter.GaussianBlur(radius=10))
    img   = Image.alpha_composite(img, gloss)

    return img


# ================================================================
# ISOMETRIC GENERATOR — Scene 3D Isometric True Alpha
# ================================================================

def _iso_project(x: float, y: float, z: float, origin_x: float, origin_y: float,
                 scale: float = 1.0):
    """Konversi koordinat 3D ke 2D isometric."""
    iso_x = (x - y) * math.cos(math.radians(30)) * scale
    iso_y = (x + y) * math.sin(math.radians(30)) * scale - z * scale
    return origin_x + iso_x, origin_y + iso_y


def _draw_iso_face(draw, pts, fill_rgba, outline_rgba=None):
    """Gambar satu face isometric polygon."""
    if len(pts) >= 3:
        draw.polygon(pts, fill=fill_rgba)
        if outline_rgba:
            draw.polygon(pts, outline=outline_rgba)


def gen_isometric(cfg: GenerationConfig, c1, c2, c3) -> Image.Image:
    """
    Scene 3D Isometric dengan true alpha.
    - Menggambar kubus, platform, dan objek isometric
    - Setiap face (atas, kiri, kanan) punya shade berbeda
    - Background benar-benar transparan (RGBA alpha=0)
    - Prompt menentukan jenis scene: kota, taman, bunga isometric, dll.
    """
    W, H  = cfg.width, cfg.height
    img   = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # TRUE ALPHA
    draw  = ImageDraw.Draw(img)
    rng   = np.random.default_rng(cfg.seed or hash(cfg.prompt) % 99999)
    p     = cfg.prompt.lower()

    ox    = W / 2       # Origin X (tengah)
    oy    = H * 0.62    # Origin Y (sedikit ke bawah dari tengah)
    scale = min(W, H) / 9.0

    # Deteksi tema scene
    is_flower  = any(k in p for k in ["bunga", "flower", "taman", "garden", "flora"])
    is_city    = any(k in p for k in ["kota", "city", "building", "gedung", "urban"])
    is_fantasy = any(k in p for k in ["fantasy", "magic", "castle", "istana", "kristal"])

    # Warna shade per face
    def shade(col, factor):
        return tuple(max(0, min(255, int(c * factor))) for c in col)

    def draw_cube(cx, cy, cz, sx, sy, sz, base_col, alpha=230):
        """Gambar satu kubus isometric."""
        # 8 sudut kubus
        corners = {}
        for dx in [0, sx]:
            for dy in [0, sy]:
                for dz in [0, sz]:
                    key = (dx > 0, dy > 0, dz > 0)
                    corners[key] = _iso_project(cx + dx, cy + dy, cz + dz, ox, oy, scale)

        # Face ATAS
        top = [corners[(0,0,1)], corners[(1,0,1)], corners[(1,1,1)], corners[(0,1,1)]]
        top_col = (*shade(base_col, 1.15), alpha)
        _draw_iso_face(draw, top, top_col, (*shade(base_col, 0.6), alpha))

        # Face KIRI (depan kiri)
        left = [corners[(0,0,0)], corners[(0,0,1)], corners[(0,1,1)], corners[(0,1,0)]]
        left_col = (*shade(base_col, 0.75), alpha)
        _draw_iso_face(draw, left, left_col, (*shade(base_col, 0.5), alpha))

        # Face KANAN (depan kanan)
        right = [corners[(1,0,0)], corners[(1,0,1)], corners[(1,1,1)], corners[(1,1,0)]]
        right_col = (*shade(base_col, 0.55), alpha)
        _draw_iso_face(draw, right, right_col, (*shade(base_col, 0.4), alpha))

    def draw_platform(cx, cy, cz, sx, sy, sz=0.3, col=None):
        """Platform tipis (base/ground tile)."""
        base = col or c3
        draw_cube(cx, cy, cz, sx, sy, sz, base, alpha=200)

    # ── GROUND PLATFORM ──
    platform_w, platform_d = 6, 6
    for gx in range(-platform_w//2, platform_w//2 + 1):
        for gy in range(-platform_d//2, platform_d//2 + 1):
            dist = abs(gx) + abs(gy)
            if dist <= platform_w // 2 + 1:
                tile_col = (
                    max(0, c3[0] - rng.integers(0, 20)),
                    max(0, c3[1] - rng.integers(0, 20)),
                    max(0, c3[2] - rng.integers(0, 20)),
                )
                draw_platform(gx, gy, 0, 1, 1, 0.25, tile_col)

    if is_flower or (not is_city and not is_fantasy):
        # ── SCENE: ISOMETRIC FLOWER GARDEN ──

        # Tangkai bunga
        stem_positions = [
            (0, 0), (-1.5, -1), (1.5, -1), (-1, 1.2), (1, 1.2),
            (-2.5, 0.5), (2.5, 0.5),
        ]
        for (sx_pos, sy_pos) in stem_positions:
            # Tangkai (kubus tinggi sempit hijau)
            stem_col = (
                max(0, 40 + rng.integers(-15, 15)),
                max(0, 160 + rng.integers(-20, 20)),
                max(0, 60 + rng.integers(-15, 15)),
            )
            h_stem = rng.uniform(1.5, 3.0)
            draw_cube(sx_pos - 0.1, sy_pos - 0.1, 0.25,
                      0.2, 0.2, h_stem, stem_col, alpha=240)

            # Kepala bunga (tumpukan kubus kecil melingkar)
            flower_z = 0.25 + h_stem
            flower_col = (
                max(0, c1[0] + rng.integers(-30, 30)),
                max(0, c1[1] + rng.integers(-30, 30)),
                max(0, c1[2] + rng.integers(-30, 30)),
            )
            # Kelopak: 4 kubus kecil sekitar pusat
            offsets = [(-0.25, 0), (0.25, 0), (0, -0.25), (0, 0.25)]
            for ofx, ofy in offsets:
                draw_cube(sx_pos + ofx - 0.15, sy_pos + ofy - 0.15,
                          flower_z, 0.3, 0.3, 0.2, flower_col, alpha=230)
            # Putik tengah
            center_col = (255, 220, 50)
            draw_cube(sx_pos - 0.15, sy_pos - 0.15, flower_z + 0.18,
                      0.3, 0.3, 0.25, center_col, alpha=255)

        # Daun
        leaf_col = (50, 180, 70)
        for i in range(8):
            lx = rng.uniform(-3, 3)
            ly = rng.uniform(-3, 3)
            draw_cube(lx, ly, 0.25, 0.5, 0.15, 0.08, leaf_col, alpha=200)

    elif is_city:
        # ── SCENE: ISOMETRIC CITY ──
        building_configs = [
            (0, 0, 2.5, c1), (-2, -1, 1.8, c2), (2, -1, 2.0, c2),
            (-1, 1.5, 1.5, c3), (1, 1.5, 1.2, c3),
            (-3, 0.5, 1.0, c1), (3, 0.5, 1.3, c1),
        ]
        for bx, by, bh, bcol in building_configs:
            bw = rng.uniform(0.7, 1.2)
            bd = rng.uniform(0.7, 1.2)
            draw_cube(bx - bw/2, by - bd/2, 0.25, bw, bd, bh, bcol, alpha=235)
            # Atap
            roof_col = shade(bcol, 1.3)
            draw_cube(bx - bw/2 + 0.1, by - bd/2 + 0.1, 0.25 + bh,
                      bw - 0.2, bd - 0.2, 0.15, roof_col, alpha=240)

    else:
        # ── SCENE: ISOMETRIC FANTASY / DEFAULT ──
        # Menara utama
        draw_cube(-0.5, -0.5, 0.25, 1, 1, 3.5, c1, alpha=240)
        # Atap menara (piramid simulasi dengan kubus kecil makin kecil)
        for lvl in range(4):
            s = 1 - lvl * 0.22
            draw_cube(-s/2, -s/2, 0.25 + 3.5 + lvl * 0.25, s, s, 0.28, c2, alpha=230)

        # Tembok
        for wx in [-2, 2]:
            draw_cube(wx - 0.2, -2, 0.25, 0.4, 4, 1.2, c3, alpha=220)
        for wy in [-2, 2]:
            draw_cube(-2.5, wy - 0.2, 0.25, 5, 0.4, 1.2, c3, alpha=220)

        # Kristal dekorasi
        crystal_col = (
            min(255, c2[0] + 60),
            min(255, c2[1] + 60),
            min(255, c2[2] + 80),
        )
        for angle in [0, 90, 180, 270]:
            rad = math.radians(angle)
            kx  = 1.8 * math.cos(rad)
            ky  = 1.8 * math.sin(rad)
            draw_cube(kx - 0.2, ky - 0.2, 0.25, 0.4, 0.4, 0.8, crystal_col, alpha=200)

    # ── Overlay bayangan lembut di bawah scene ──
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    sw, sh = int(W * 0.7), int(H * 0.12)
    shadow_draw.ellipse(
        [int(ox - sw/2), int(oy - sh/2), int(ox + sw/2), int(oy + sh/2)],
        fill=(0, 0, 0, 30)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=20))
    img    = Image.alpha_composite(img, shadow)

    return img


# ================================================================
# MAIN ENGINE
# ================================================================

STYLE_MAP = {
    ImageStyle.GEOMETRIC: gen_geometric,
    ImageStyle.GRADIENT:  gen_gradient,
    ImageStyle.GLOW:      gen_glow,
    ImageStyle.STARBURST: gen_starburst,
    ImageStyle.BADGE:     gen_badge,
    ImageStyle.MANDALA:   gen_mandala,
    ImageStyle.WAVE:      gen_wave,
    ImageStyle.PORTRAIT:  gen_portrait,
    ImageStyle.LANDSCAPE: gen_landscape,
    ImageStyle.TEXT_ART:  gen_text_art,
    ImageStyle.PIXEL:     gen_pixel,
    ImageStyle.FLOWER:    gen_flower,
    ImageStyle.ISOMETRIC: gen_isometric,
}


def generate_image(cfg: GenerationConfig) -> GenerationResult:
    """
    Entry point utama generator.
    - Deteksi style dari prompt
    - Generate gambar dengan true RGBA alpha
    - Verifikasi alpha channel
    """
    # Clamp resolusi
    cfg.width  = max(256, min(cfg.width,  1024))
    cfg.height = max(256, min(cfg.height, 1024))

    # Detect style
    if cfg.style == ImageStyle.AUTO:
        cfg.style = detect_style(cfg.prompt)

    # Ambil warna dari prompt
    c1, c2, c3 = prompt_to_colors(cfg.prompt)

    # Generate
    gen_fn = STYLE_MAP.get(cfg.style, gen_geometric)
    img    = gen_fn(cfg, c1, c2, c3)

    # Verifikasi RGBA
    assert img.mode == "RGBA", f"Mode harus RGBA, bukan {img.mode}"
    has_alpha, transparent_pct = verify_alpha(img)

    return GenerationResult(
        image=img,
        style_used=cfg.style.value,
        alpha_verified=has_alpha,
        transparent_pct=transparent_pct,
    )


def image_to_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=False)
    return buf.getvalue()


def image_to_base64(img: Image.Image) -> str:
    import base64
    return base64.b64encode(image_to_bytes(img)).decode("utf-8")
