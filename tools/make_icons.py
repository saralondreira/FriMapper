"""Gera os 12 badges PNG da biblioteca de ícones Custom (assets/icons/).

Categorias sem ícone nativo na ``diagrams`` (PLC, CCTV, régua, EV, solar…)
recebem um badge próprio: retângulo arredondado colorido com abreviatura.
Uso: ``python tools/make_icons.py assets/icons``. Requer Pillow (build-time).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256

#: categoria → (abreviatura, cor de fundo)
BADGES: dict[str, tuple[str, str]] = {
    "ups": ("UPS", "#6d4c41"),
    "impressora": ("PRN", "#455a64"),
    "ap": ("AP", "#0277bd"),
    "regua": ("PDU", "#546e7a"),
    "cabo_vazio": ("CBL", "#9e9e9e"),
    "camaras": ("CAM", "#7b1fa2"),
    "cctv": ("CCTV", "#4a148c"),
    "controlo_acessos": ("ACS", "#00695c"),
    "automatos": ("PLC", "#e65100"),
    "solar": ("SOL", "#f9a825"),
    "carregador_ev": ("EV", "#2e7d32"),
    "voip": ("VOIP", "#283593"),
}


def _font(size: int) -> ImageFont.ImageFont:
    for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "arialbd.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_badge(text: str, color: str, path: Path) -> None:
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = 12
    draw.rounded_rectangle(
        [margin, margin, SIZE - margin, SIZE - margin],
        radius=36,
        fill=color,
        outline="#212121",
        width=6,
    )
    font_size = 96 if len(text) <= 3 else 72
    font = _font(font_size)
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]
    draw.text(
        ((SIZE - width) / 2 - bbox[0], (SIZE - height) / 2 - bbox[1]),
        text,
        font=font,
        fill="white",
    )
    image.save(path, "PNG")


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "assets/icons")
    out_dir.mkdir(parents=True, exist_ok=True)
    for category, (text, color) in BADGES.items():
        target = out_dir / f"{category}.png"
        make_badge(text, color, target)
        print(f"  {target}")
    print(f"{len(BADGES)} badges gerados em {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
