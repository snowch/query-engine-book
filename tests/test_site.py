"""The site's own furniture: the icons an installed book shows, and the manifest that names them."""

from __future__ import annotations

import importlib.util
import json
import math
import struct
import subprocess
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


def test_every_page_names_the_licences_the_book_declares():
    """The foot of every page reads its terms from myst.yml, and the cover names the same."""
    import yaml

    declared = yaml.safe_load((ROOT / "myst.yml").read_text())["project"]["license"]
    foot = site.colophon()
    cover = (ROOT / "cover.md").read_text()
    for spdx in declared.values():
        assert spdx in site.LICENCES, f"myst.yml declares {spdx}, which the foot of a page cannot name"
        name, file = site.LICENCES[spdx]
        assert (ROOT / file).exists(), f"{file}, the text of {spdx}, is not in the repository"
        assert name in foot, f"the foot of every page does not name {name}"
        assert name in cover and file in cover, f"the cover does not name {name}, or its file"
    # And how it was written, in the same words in both places.
    assert site.WRITTEN_WITH in foot and site.WRITTEN_WITH in cover


def test_the_workers_python_holds_no_backtick():
    """The worker's Python sits in a JavaScript template string: a backtick in it, as in a
    docstring's ``code``, ends the string early, and every run on every page fails."""
    source = (ROOT / "web" / "lab" / "python-worker.js").read_text()
    python = source.split("const RUN = `", 1)[1].split("\n`;", 1)[0]
    assert "`" not in python


def test_an_editor_colours_code_as_the_book_does():
    """web/lab/highlight.js colours an editor as tools/highlight.py coloured the listing it
    replaced, on every file of the engine and every query the book quotes."""
    from tools.highlight import highlight

    files = [*sorted((ROOT / "python" / "query_lab").glob("*.py")), *sorted((ROOT / "queries").glob("*.sql"))]
    jobs = [[str(f), "python" if f.suffix == ".py" else "sql"] for f in files]
    script = (
        f'import {{ highlight }} from "{(ROOT / "web" / "lab" / "highlight.js").as_uri()}";'
        'import { readFileSync } from "node:fs";'
        "const jobs = JSON.parse(process.argv[1]);"
        'process.stdout.write(JSON.stringify(jobs.map(([f, l]) => highlight(readFileSync(f, "utf8"), l))));'
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps(jobs)],
        capture_output=True,
        text=True,
        check=True,
    )
    for (file, lang), coloured in zip(jobs, json.loads(out.stdout), strict=True):
        assert coloured == highlight(Path(file).read_text(), lang), file
