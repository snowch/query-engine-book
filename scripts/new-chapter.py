#!/usr/bin/env python3
"""Write the skeleton of a chapter that does not exist yet. Never touches a written page.

    python3 scripts/new-chapter.py encodings      # one chapter, by slug
    python3 scripts/new-chapter.py --all          # every chapter in tools/outline.py missing a page

The skeleton has the book's ten headings with the question and what the chapter builds filled
in from the outline, so a planned chapter already reads as part of the book. Every section
carries a ``[To write`` marker; the navigation shows a chapter with markers as unwritten, and
``tests/test_book.py`` relaxes the checks that only a written chapter can meet.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.outline import BY_SLUG, CHAPTERS, UNWRITTEN  # noqa: E402


def skeleton(slug: str) -> str:
    c = BY_SLUG[slug]
    body = {
        "The question": f"{c.question}\n\n{UNWRITTEN}: the paragraph that says why the previous chapter leaves this open.]",
        "Observe": f"{UNWRITTEN}: the query run in DuckDB, its plan and its JSON profile read together.]",
        "Predict, then measure": f"{UNWRITTEN}: a prediction the reader commits to, then the experiment that tests it.]",
        "Building it": f"{UNWRITTEN}: {c.builds}]",
        "Compare": f"{UNWRITTEN}: the engine's results and counters beside DuckDB's.]",
        "What this cannot tell you": f"{UNWRITTEN}: what the experiment, the model and the code leave out.]",
        "What this means for your design": f"{UNWRITTEN}: the choices in the reader's own systems that this changes.]",
        "Key takeaways": f"{UNWRITTEN}: the claims made and shown above, each in bold with its reason.]",
        "Problems": (
            f"{UNWRITTEN}: problems as stubs in `exercises/{slug}.py`, graded by "
            f"`exercises/tests/test_{slug}.py`, and one diagnose-the-slow-query problem.]"
        ),
        "Where to go next": f"{UNWRITTEN}: papers, engine source code, and the optional depth in the companion books.]",
    }
    sections = "\n\n".join(f"## {h}\n\n{body[h]}" for h in c.shape)
    return f"""---
title: {c.title}
---

({c.anchor})=
# {c.title}

:::{{div}}
:class: unwritten-note

This chapter is planned and not yet written. The outline below is the plan: the question it
answers and the piece of the engine it adds.
:::

{sections}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("slug", nargs="?")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()
    slugs = [c.slug for c in CHAPTERS] if args.all else [args.slug]
    if not args.all and args.slug not in BY_SLUG:
        parser.error(f"no chapter {args.slug!r} in tools/outline.py")
    for slug in slugs:
        path = ROOT / BY_SLUG[slug].path
        if path.exists():
            continue
        path.write_text(skeleton(slug))
        print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
