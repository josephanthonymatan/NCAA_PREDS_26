from __future__ import annotations

from urllib.parse import quote


_PIXEL_ROWS = (
    "................",
    ".....dddddd.....",
    "...ddoooooodd...",
    "..dooooooooood..",
    "..dooooodoooood.",
    ".doooooodooooood",
    ".doooooodooooood",
    ".dddddoodddddddo",
    ".doooooodooooood",
    ".doooooodooooood",
    ".doooooddooooood",
    "..doooooooooood.",
    "..dooooooooood..",
    "...ddoooooodd...",
    ".....dddddd.....",
    "................",
)

_PIXEL_COLORS = {
    "d": "#18293D",
    "o": "#E88A2E",
}


def pixel_basketball_icon_data_url() -> str:
    rects: list[str] = []
    for y, row in enumerate(_PIXEL_ROWS):
        for x, pixel in enumerate(row):
            color = _PIXEL_COLORS.get(pixel)
            if color:
                rects.append(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{color}"/>')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16" '
        'shape-rendering="crispEdges">'
        + "".join(rects)
        + "</svg>"
    )
    return f"data:image/svg+xml,{quote(svg)}"
