"""Картинки-заглушки для демо-данных (Pillow, без внешних URL) — как SeedImage в других магазинах."""

import io
import random

from PIL import Image, ImageDraw


def make_png(rgb: tuple[int, int, int], seed: int, size: int = 800) -> bytes:
    img = Image.new("RGB", (size, size))
    draw = ImageDraw.Draw(img)
    # Вертикальный градиент от цвета категории к светлому.
    for y in range(size):
        t = y / size * 0.75
        draw.line([(0, y), (size, y)], fill=tuple(int(c + (255 - c) * t) for c in rgb))
    rnd = random.Random(seed)  # noqa: S311 - декоративная картинка, не криптография
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for _ in range(5):
        d = rnd.randint(int(size * 0.15), int(size * 0.45))
        cx, cy = rnd.randint(0, size), rnd.randint(0, size)
        od.ellipse([cx - d // 2, cy - d // 2, cx + d // 2, cy + d // 2], fill=(255, 255, 255, 110))
    w = int(size * (0.35 + rnd.randint(0, 15) / 100))
    h = int(size * (0.30 + rnd.randint(0, 20) / 100))
    x, y = (size - w) // 2, (size - h) // 2
    dark = (int(rgb[0] * 0.5), int(rgb[1] * 0.5), int(rgb[2] * 0.5), 175)
    od.rounded_rectangle([x, y, x + w, y + h], radius=int(size * 0.05), fill=dark)
    c = int(size * 0.12)
    od.ellipse(
        [size // 2 - c // 2, size // 2 - c // 2, size // 2 + c // 2, size // 2 + c // 2],
        fill=(255, 255, 255, 215),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
