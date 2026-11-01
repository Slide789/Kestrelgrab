"""Erzeugt das App-Icon (assets/icon.png und assets/icon.ico) mit Pillow.

Motiv: ein Turmfalke (Kestrel) im Sturzflug von oben gesehen. Die angelegten
Flügel bilden einen nach unten zeigenden Pfeil, darunter die Download-Ablage.

Aufruf:  python tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
SIZE = 1024  # Arbeitsauflösung, danach herunterskaliert

TOP = (244, 142, 72)     # helles Rostorange
BOTTOM = (176, 66, 28)   # dunkles Rotbraun


def _gradient(size: int) -> Image.Image:
    grad = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(grad)
    for y in range(size):
        t = y / (size - 1)
        color = tuple(int(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))
        draw.line([(0, y), (size, y)], fill=color)
    return grad


def _cubic(p0, p1, p2, p3, steps: int = 40) -> list[tuple[float, float]]:
    pts = []
    for i in range(steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        pts.append((x, y))
    return pts


# Rechte Hälfte des Falken (Einheitskoordinaten, Kopf unten), als Bézier-Segmente.
_RIGHT_HALF = [
    ((0.500, 0.755), (0.522, 0.745), (0.550, 0.700), (0.548, 0.655)),  # Kopf
    ((0.548, 0.655), (0.550, 0.620), (0.560, 0.600), (0.575, 0.585)),  # Hals → Schulter
    ((0.575, 0.585), (0.700, 0.520), (0.820, 0.360), (0.870, 0.200)),  # Flügel-Vorderkante
    ((0.870, 0.200), (0.810, 0.330), (0.680, 0.430), (0.568, 0.470)),  # Flügel-Hinterkante
    ((0.568, 0.470), (0.556, 0.410), (0.548, 0.350), (0.545, 0.300)),  # Rumpf
    ((0.545, 0.300), (0.555, 0.240), (0.580, 0.170), (0.590, 0.130)),  # Schwanz außen
    ((0.590, 0.130), (0.565, 0.115), (0.530, 0.112), (0.500, 0.112)),  # Schwanzende
]


def _bird_polygon(s: int) -> list[tuple[float, float]]:
    right: list[tuple[float, float]] = []
    for seg in _RIGHT_HALF:
        right.extend(_cubic(*seg))
    left = [(1 - x, y) for x, y in reversed(right)]
    return [(x * s, y * s) for x, y in right + left]


def make_icon() -> Image.Image:
    s = SIZE
    margin = int(s * 0.06)
    radius = int(s * 0.23)

    # Abgerundetes Quadrat mit Farbverlauf
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([margin, margin, s - margin, s - margin], radius, fill=255)
    base = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    base.paste(_gradient(s), (0, 0), mask)

    # Dezenter Glanz oben
    gloss = Image.new("L", (s, s), 0)
    ImageDraw.Draw(gloss).ellipse([-s * 0.3, -s * 0.75, s * 1.3, s * 0.42], fill=40)
    gloss = Image.composite(gloss, Image.new("L", (s, s), 0), mask).filter(ImageFilter.GaussianBlur(s * 0.02))
    base = Image.composite(Image.new("RGBA", (s, s), (255, 255, 255, 255)), base, gloss)
    base.putalpha(mask)

    # Falke + Ablage
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    white = (255, 255, 255, 255)
    d.polygon(_bird_polygon(s), fill=white)
    tray_w, tray_h = s * 0.50, s * 0.065
    d.rounded_rectangle([s / 2 - tray_w / 2, s * 0.82, s / 2 + tray_w / 2, s * 0.82 + tray_h],
                        radius=tray_h / 2, fill=white)
    # Kanten glätten
    alpha = layer.split()[3].filter(ImageFilter.GaussianBlur(s * 0.004))
    layer.putalpha(alpha)

    # Weicher Schatten unter dem Symbol
    shadow = Image.new("RGBA", (s, s), (80, 20, 0, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(s * 0.025)).point(lambda v: int(v * 0.35)))
    base.alpha_composite(shadow, (0, int(s * 0.012)))
    base.alpha_composite(layer)
    return base


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = make_icon()
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon.png")
    icon.resize((512, 512), Image.LANCZOS).save(ASSETS / "icon@2x.png")
    sizes = [(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)]
    icon.resize((256, 256), Image.LANCZOS).save(ASSETS / "icon.ico", sizes=sizes)
    print(f"Icon geschrieben: {ASSETS / 'icon.ico'}")


if __name__ == "__main__":
    main()
