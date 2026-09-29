"""The site's own furniture: the icons an installed book shows, and the manifest that names them."""

from __future__ import annotations

import importlib.util
import json
import math
import struct
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build-site.py")
site = importlib.util.module_from_spec(spec)
spec.loader.exec_module(site)


def pixels(png: bytes) -> tuple[int, int, bytes]:
    """Width, height and raw RGBA rows (each row led by its filter byte) of one of our PNGs."""
    width, height = struct.unpack(">II", png[16:24])
    data = png[png.index(b"IDAT") + 4 :]
    length = struct.unpack(">I", png[png.index(b"IDAT") - 4 : png.index(b"IDAT")])[0]
    return width, height, zlib.decompress(data[:length])


def alpha_at(png: bytes, x: int, y: int) -> int:
    width, _, raw = pixels(png)
    return raw[y * (width * 4 + 1) + 1 + x * 4 + 3]


@pytest.mark.parametrize("name, size, maskable", site.ICONS)
def test_every_icon_is_a_png_of_its_size(name, size, maskable):
    png = site.icon_png(size, maskable)
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    assert pixels(png)[:2] == (size, size)
    # A maskable icon fills its square, for the platform to cut; the ordinary one rounds its own
    # corners and is transparent beyond them.
    assert alpha_at(png, 0, 0) == (255 if maskable else 0)
    assert alpha_at(png, size // 2, size // 2) == 255


def test_a_maskable_icons_bars_sit_inside_the_safe_circle():
    """Android shows only the centre circle, of radius 40% of the square, for certain."""
    safe = 0.4 * 32
    for x, y, w, h, _r, _c in site._icon_shapes(True):
        for cx, cy in ((x, y), (x + w, y), (x, y + h), (x + w, y + h)):
            assert math.hypot(cx - 16, cy - 16) <= safe, (cx, cy)


def test_the_manifest_names_every_icon_and_marks_the_maskable_ones():
    manifest = json.loads(site.manifest())
    listed = {i["src"]: i["purpose"] for i in manifest["icons"]}
    for name, _size, maskable in site.ICONS:
        assert listed[name] == ("maskable" if maskable else "any")
    assert listed["favicon.svg"] == "any"
    assert manifest["theme_color"] == site.ICON_BACKGROUND


def test_the_svg_and_the_pngs_draw_the_same_bars():
    svg = site.favicon_svg()
    assert svg.count("<rect") == 1 + len(site.ICON_BARS)
    for *_, colour in site.ICON_BARS:
        assert colour in svg


def test_the_site_builds_with_no_pythonpath(tmp_path):
    """The deploy workflow sets no PYTHONPATH, so the builder must find the engine and its scan
    layer itself. CI's own checks export one, which once hid this."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import runpy, sys; sys.argv = ['build-site.py', '--help']; "
            "runpy.run_path('scripts/build-site.py', run_name='not_main')",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )
