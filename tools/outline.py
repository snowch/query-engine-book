"""The book's shape, in one machine-readable place.

PLAN.md holds the argument: what each chapter is for, and why the book is in this order. This
module holds only what a script or a test needs: the order, the titles, the question each
chapter answers, what each chapter adds to the engine, and which fixtures and experiments it
uses.

The draft table of contents lives in PLAN.md; a chapter enters this list when it is about to be
written, not before.

A chapter's number is derived from its position here and never typed anywhere else. Its identity
is its slug: the file name, the anchor a cross-reference uses, and the name of its problems.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The headings every chapter carries, in order. ``tests/test_book.py`` holds every chapter to
#: them. A section a chapter needs and this list lacks is a subsection of one of these.
#:
#: The order is the book's method: observe, build, compare, then design. A chapter opens on a
#: question, watches a real engine (DuckDB) answer it, asks the reader to commit to a prediction
#: before measuring, builds the operator that the measurement needed, and checks it against the
#: real engine before saying what it means for the reader's own designs.
CHAPTER_SHAPE = (
    "The question",
    "Observe",
    "Predict, then measure",
    "Building it",
    "Compare",
    "What this cannot tell you",
    "What this means for your design",
    "Key takeaways",
    "Problems",
    "Where to go next",
)

#: Chapters that explain and build nothing. None yet: every pilot chapter builds something.
EXPLAINERS: frozenset[str] = frozenset()

#: What a page carries until it is written. Everything that reports progress keys off it.
UNWRITTEN = "[To write"


@dataclass(frozen=True)
class Part:
    slug: str
    title: str
    question: str

    @property
    def path(self) -> str:
        return f"parts/{self.slug}.md"


@dataclass(frozen=True)
class Chapter:
    number: int
    slug: str
    title: str
    part: str
    #: The one question the chapter answers. Its opening paragraph expands it.
    question: str
    #: What the reader has, working, at the end of the chapter: the piece of the engine it adds.
    builds: str
    #: The experiments (``lab`` blocks) the chapter embeds.
    experiments: tuple[str, ...] = ()
    #: The fixtures those experiments and the chapter's figures read.
    fixtures: tuple[str, ...] = ()

    @property
    def anchor(self) -> str:
        return self.slug.replace("_", "-")

    @property
    def explainer(self) -> bool:
        """Whether the chapter explains and builds nothing (``EXPLAINERS``)."""
        return self.slug in EXPLAINERS

    @property
    def shape(self) -> tuple[str, ...]:
        """The chapter's headings, in order: CHAPTER_SHAPE, less *Building it* for an explainer."""
        return tuple(h for h in CHAPTER_SHAPE if not (self.explainer and h == "Building it"))

    @property
    def label(self) -> str:
        return f"ch{self.number:02d}"

    @property
    def path(self) -> str:
        return f"chapters/{self.slug}.md"


@dataclass(frozen=True)
class Appendix:
    letter: str
    slug: str
    title: str

    @property
    def anchor(self) -> str:
        return self.slug.replace("_", "-")

    @property
    def label(self) -> str:
        return f"Appendix {self.letter}"

    @property
    def path(self) -> str:
        return f"appendices/{self.slug}.md"


PARTS = (
    Part(
        "seeing_a_query",
        "Part I: Seeing a query",
        "What does an engine do with a query, and how do you watch it work?",
    ),
    Part(
        "reading_less",
        "Part II: Reading less",
        "How does an engine avoid reading most of its input?",
    ),
    Part(
        "computing",
        "Part III: Computing",
        "Once the rows are in memory, what does each operator cost the processor?",
    ),
)

_P = {p.slug: p.title for p in PARTS}

_CHAPTERS = (
    (
        "the_plan_is_the_map",
        "The plan is the map",
        "seeing_a_query",
        "What does an engine do with your query, and where can you see what each step costs?",
        "A hand-written plan of scan, filter and projection over Arrow batches, each operator "
        "reporting its counters, checked against DuckDB's plan and profile.",
        ("plan",),
        ("orders-sorted.parquet",),
    ),
    (
        "batches_in_memory",
        "Batches in memory",
        "seeing_a_query",
        "What does a batch of rows look like in memory, and why does the order you touch it in matter?",
        "Arrow arrays built from raw buffers, a validity bitmap decoded by hand, and sorted and "
        "shuffled gathers run through a cache simulator.",
        ("gather",),
        ("orders-sorted.parquet", "orders-shuffled.parquet"),
    ),
    (
        "projection_and_filter_pushdown",
        "Projection and filter pushdown",
        "reading_less",
        "How much of a file can a scan avoid reading, once it knows the columns and the predicate?",
        "Projection and filters pushed into the Parquet book's scan, counting the bytes read and "
        "the row groups skipped.",
        ("pruning",),
        ("orders-sorted.parquet", "orders-shuffled.parquet"),
    ),
    (
        "statistics_and_pruning",
        "Statistics and pruning",
        "reading_less",
        "How finely can a scan skip, and what does skipping finely cost?",
        "A scan that reads a file's page index and fetches and decodes only the pages that might "
        "hold a match, checked against DuckDB byte for byte.",
        ("pruning",),
        ("orders-sorted.parquet", "orders-paged.parquet"),
    ),
    (
        "where_work_happens",
        "Where work happens",
        "reading_less",
        "When a table is many files, what decides which of them are opened, and where are the rows tested?",
        "A table scan that reads a table's metadata and opens only the files that might match, and "
        "a scan handed to storage that tests the rows itself.",
        ("pruning",),
        ("orders-by-month", "orders-sorted.parquet", "orders-shuffled.parquet"),
    ),
    (
        "expressions_and_vectorised_kernels",
        "Expressions and vectorised kernels",
        "computing",
        "What does it cost to compute an expression for every row, and why do engines work a batch at a time?",
        "An expression tree evaluated a row at a time and a batch at a time, a model of branch "
        "prediction and of vector lanes, and a filter kernel with no branch on the data.",
        ("branches",),
        ("orders-sorted.parquet",),
    ),
    (
        "hash_aggregation",
        "Hash aggregation",
        "computing",
        "How does an engine find a row's group, and what does the number of groups cost?",
        "A hash aggregate over an open-addressing table, counting its probes and its cache misses, "
        "and a perfect hash aggregate for keys from a small range, as DuckDB chooses.",
        ("measure",),
        ("orders-sorted.parquet",),
    ),
    (
        "joins",
        "Joins",
        "computing",
        "Which side of a join does an engine hold, and what does holding it cost?",
        "A hash join that builds a table on one input and probes it with the other, holding the "
        "build rows through the cache model, beside DuckDB's choice of build side.",
        ("measure",),
        ("orders-sorted.parquet", "orders-shuffled.parquet", "customers.parquet"),
    ),
    (
        "sorting_and_top_k",
        "Sorting and top-k",
        "computing",
        "What does putting rows in order cost, and how much of it does a LIMIT save?",
        "A full sort and a top-k that keeps its rows in a heap, both counting their comparisons, "
        "beside DuckDB's ORDER_BY and TOP_N.",
        ("measure",),
        ("orders-sorted.parquet", "orders-shuffled.parquet"),
    ),
)

CHAPTERS = tuple(
    Chapter(
        number=i + 1,
        slug=slug,
        title=title,
        part=_P[part],
        question=question,
        builds=builds,
        experiments=experiments,
        fixtures=fixtures,
    )
    for i, (slug, title, part, question, builds, experiments, fixtures) in enumerate(_CHAPTERS)
)

APPENDICES = (
    Appendix("A", "running_the_lab", "Running the lab"),
    Appendix("B", "the_fixtures", "The fixtures"),
    Appendix("C", "glossary", "Glossary"),
)

BY_SLUG = {c.slug: c for c in CHAPTERS}
BY_ANCHOR = {x.anchor: x for x in (*CHAPTERS, *APPENDICES)}

#: The experiments ``web/lab/lab.js`` knows how to mount, each drawn from the JSON of the
#: function of the same name in ``query_lab.report``. A ``lab`` block naming anything else fails
#: the build, rather than rendering an empty box.
EXPERIMENTS: tuple[str, ...] = ("plan", "gather", "pruning", "branches", "measure")
