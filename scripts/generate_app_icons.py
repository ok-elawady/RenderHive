"""Generate cleanly inverted color-swapped Windows icons for Worker and Server Manager.

- Worker (Client):
  Inner core: Pure White (#FFFFFF)
  Outer ring & Hive glyph: Brand Royal Purple (#4A1296)

- Server Manager (Host):
  Inner core: Rich Brand Purple (#4A1296)
  Outer ring & Hive glyph: Crisp White (#FFFFFF)

Renders vector SVGs with PySide6 at 1024x1024 with subpixel anti-aliasing,
then saves multi-resolution ICO files (256, 128, 96, 64, 48, 32, 24, 16) and PNGs.
"""

import os
from pathlib import Path
from PIL import Image
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parent.parent

# Parameterized clean RenderHive SVG template
SVG_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg id="RenderHiveIcon" xmlns="http://www.w3.org/2000/svg" viewBox="-50 -50 669.24 737.1">
  <defs>
    <style>
      .inner-fill {{
        fill: {inner_color};
      }}
      .brand-glyph {{
        fill: {glyph_color};
      }}
    </style>
  </defs>
  <g id="Emblem">
    <polygon class="inner-fill" points="541.18 467.1 541.18 170.19 285.78 21.74 30.37 170.19 30.37 467.1 285.78 615.55 541.18 467.1"/>
    <path class="brand-glyph" d="M495.62,215.2v206.69c0,11.43-6.1,22-16,27.71l-179,103.35c-9.9,5.72-22.1,5.72-32,0l-179-103.35c-9.9-5.72-16-16.28-16-27.71v-206.69c0-11.43,6.1-22,16-27.71l179-103.35c9.9-5.72,22.1-5.72,32,0l179,103.35c9.9,5.72,16,16.28,16,27.71ZM284.62,0c-11.27,0-22.54,2.92-32.64,8.75L32.64,135.38C12.44,147.04,0,168.59,0,191.92v253.26c0,23.33,12.44,44.88,32.64,56.54l219.33,126.63c10.1,5.83,21.37,8.75,32.64,8.75s22.54-2.92,32.64-8.75l219.33-126.63c20.2-11.66,32.64-33.22,32.64-56.54v-253.26c0-23.33-12.44-44.88-32.64-56.54L317.26,8.75c-10.1-5.83-21.37-8.75-32.64-8.75h0Z"/>
    <circle class="brand-glyph" cx="284.62" cy="255.55" r="27"/>
    <circle class="brand-glyph" cx="356.62" cy="210.55" r="27"/>
    <circle class="brand-glyph" cx="284.62" cy="156.55" r="27"/>
    <circle class="brand-glyph" cx="212.62" cy="210.55" r="27"/>
    <polygon class="brand-glyph" points="446.62 309.55 284.62 399.55 122.62 309.55 122.62 246.55 284.62 336.55 446.62 246.55 446.62 309.55"/>
    <polygon class="brand-glyph" points="446.62 408.55 284.62 498.55 122.62 408.55 122.62 345.55 284.62 435.55 446.62 345.55 446.62 408.55"/>
  </g>
</svg>
"""

def render_svg_to_image(svg_xml: str, size: int = 1024) -> Image.Image:
    renderer = QSvgRenderer(QByteArray(svg_xml.encode("utf-8")))
    qimg = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    qimg.fill(Qt.transparent)

    painter = QPainter(qimg)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    renderer.render(painter)
    painter.end()

    buffer = qimg.bits().tobytes()
    pil_img = Image.frombuffer("RGBA", (size, size), buffer, "raw", "BGRA", 0, 1)
    return pil_img


def build_icon_bundle(dest_dir: Path, inner_color: str, glyph_color: str, name: str = "icon"):
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Save SVG
    svg_content = SVG_TEMPLATE.format(inner_color=inner_color, glyph_color=glyph_color)
    svg_path = dest_dir / f"{name}.svg"
    svg_path.write_text(svg_content, encoding="utf-8")
    
    # 2. Render 1024x1024 Master PNG
    master_img = render_svg_to_image(svg_content, size=1024)
    
    # 3. Save 256x256 PNG
    png_256 = master_img.resize((256, 256), Image.Resampling.LANCZOS)
    png_path = dest_dir / f"{name}.png"
    png_256.save(str(png_path), format="PNG")
    
    # 4. Save Multi-Resolution Windows ICO
    sizes = [(256, 256), (128, 128), (96, 96), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    ico_path = dest_dir / f"{name}.ico"
    master_img.save(str(ico_path), format="ICO", sizes=sizes)
    
    print(f"Generated {name} in {dest_dir} (SVG, PNG, ICO [{os.path.getsize(ico_path)} bytes])")


def main():
    # 1. Worker (Client): White core + Brand Purple Glyph
    worker_assets = ROOT / "worker" / "assets"
    build_icon_bundle(worker_assets, inner_color="#FFFFFF", glyph_color="#4A1296", name="icon")

    # 2. Server Manager (Host): Brand Purple core + Pure White Glyph (Color Inverted)
    server_assets = ROOT / "server" / "assets"
    build_icon_bundle(server_assets, inner_color="#4A1296", glyph_color="#FFFFFF", name="icon")


if __name__ == "__main__":
    main()
