from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from struct import pack
from urllib.parse import quote
import zlib

from .paths import APP_ROOT


_SPRITE_SIZE = 16
_BORDER_COLOR = "#18293D"
_SEAM_COLOR = "#6A3213"
_FILL_COLOR = "#E88A2E"
_HIGHLIGHT_COLOR = "#F4B35D"
_SHADOW_COLOR = "#CF6C1E"


@dataclass(frozen=True)
class FaviconLinks:
    svg: str
    png_32: str
    png_16: str
    apple_touch: str
    ico: str


def pixel_basketball_icon_svg() -> str:
    rects: list[str] = []
    for y in range(_SPRITE_SIZE):
        for x in range(_SPRITE_SIZE):
            color = _pixel_color_at(x, y)
            if color is not None:
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{color}"/>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" '
        'shape-rendering="crispEdges">'
        + "".join(rects)
        + "</svg>"
    )


def pixel_basketball_icon_data_url() -> str:
    return f"data:image/svg+xml,{quote(pixel_basketball_icon_svg())}"


def _rgb_from_hex(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.lstrip("#")
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _pixel_color_at(x: int, y: int) -> str | None:
    nx = ((x + 0.5) / _SPRITE_SIZE) * 2 - 1
    ny = ((y + 0.5) / _SPRITE_SIZE) * 2 - 1
    distance = (nx * nx + ny * ny) ** 0.5

    if distance > 0.93:
        return None
    if distance > 0.79:
        return _BORDER_COLOR

    color = _FILL_COLOR
    if nx + ny < -0.42 and distance < 0.75:
        color = _HIGHLIGHT_COLOR
    elif nx - ny > 0.58 and distance < 0.77:
        color = _SHADOW_COLOR

    curve_offset = 0.30 + (0.22 * (abs(ny) ** 1.55))
    seam_band = 0.055
    horizontal_seam = abs(ny + 0.0625) < 0.04 and abs(nx) < 0.8 and distance < 0.77
    left_seam = abs(nx + curve_offset) < seam_band and abs(ny) < 0.74 and distance < 0.77
    right_seam = abs(nx - curve_offset) < seam_band and abs(ny) < 0.74 and distance < 0.77

    if horizontal_seam or left_seam or right_seam:
        return _SEAM_COLOR
    return color


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
    return pack(">I", len(payload)) + chunk_type + payload + pack(">I", checksum)


def pixel_basketball_icon_png(size: int) -> bytes:
    if size <= 0:
        raise ValueError("PNG icon size must be positive.")

    raw_rows: list[bytes] = []
    for y in range(size):
        source_y = (y * _SPRITE_SIZE) // size
        row = bytearray([0])
        for x in range(size):
            source_x = (x * _SPRITE_SIZE) // size
            color = _pixel_color_at(source_x, source_y)
            if color is None:
                row.extend((0, 0, 0, 0))
                continue
            red, green, blue = _rgb_from_hex(color)
            row.extend((red, green, blue, 255))
        raw_rows.append(bytes(row))

    compressed = zlib.compress(b"".join(raw_rows), level=9)
    ihdr = pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


def pixel_basketball_icon_ico() -> bytes:
    images = (
        (16, pixel_basketball_icon_png(16)),
        (32, pixel_basketball_icon_png(32)),
    )
    header = pack("<HHH", 0, 1, len(images))
    directory_entries: list[bytes] = []
    image_offset = 6 + (16 * len(images))

    for size, png_bytes in images:
        directory_entries.append(
            pack(
                "<BBBBHHII",
                size if size < 256 else 0,
                size if size < 256 else 0,
                0,
                0,
                1,
                32,
                len(png_bytes),
                image_offset,
            )
        )
        image_offset += len(png_bytes)

    return header + b"".join(directory_entries) + b"".join(png for _, png in images)


def ensure_favicon_assets(asset_dir: Path) -> None:
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "favicon.svg").write_text(pixel_basketball_icon_svg(), encoding="utf-8")
    (asset_dir / "favicon-32x32.png").write_bytes(pixel_basketball_icon_png(32))
    (asset_dir / "favicon-16x16.png").write_bytes(pixel_basketball_icon_png(16))
    (asset_dir / "apple-touch-icon.png").write_bytes(pixel_basketball_icon_png(180))
    (asset_dir / "favicon.ico").write_bytes(pixel_basketball_icon_ico())


def favicon_links(destination: Path) -> FaviconLinks:
    asset_dir = destination.parent.resolve()
    ensure_favicon_assets(asset_dir)

    try:
        relative_dir = asset_dir.relative_to(APP_ROOT.resolve()).as_posix()
    except ValueError:
        relative_dir = ""

    if relative_dir in {"", "."}:
        prefix = ""
    else:
        prefix = f"/{relative_dir}"

    def build_href(filename: str) -> str:
        if not prefix:
            return filename
        return f"{prefix}/{filename}"

    return FaviconLinks(
        svg=build_href("favicon.svg"),
        png_32=build_href("favicon-32x32.png"),
        png_16=build_href("favicon-16x16.png"),
        apple_touch=build_href("apple-touch-icon.png"),
        ico=build_href("favicon.ico"),
    )


def favicon_head_tags(destination: Path, theme_color: str = "#18293D") -> str:
    links = favicon_links(destination)
    return "\n".join(
        (
            f'<meta name="theme-color" content="{theme_color}">',
            f'<link rel="icon" type="image/x-icon" href="{links.ico}">',
            f'<link rel="shortcut icon" href="{links.ico}">',
            f'<link rel="icon" type="image/svg+xml" href="{links.svg}">',
            f'<link rel="icon" type="image/png" sizes="32x32" href="{links.png_32}">',
            f'<link rel="icon" type="image/png" sizes="16x16" href="{links.png_16}">',
            f'<link rel="apple-touch-icon" sizes="180x180" href="{links.apple_touch}">',
        )
    )


def vercel_analytics_script_tag() -> str:
    return '<script defer src="/_vercel/insights/script.js"></script>'
