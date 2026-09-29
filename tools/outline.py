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
    Part(
        "planning",
        "Part IV: Planning",
        "How does an engine decide what to run for a query, from its text alone?",
    ),
    Part(
        "scaling_out",
        "Part V: Scaling out",
        "What changes when a query's work is shared among many workers, on one machine or many?",
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
    (
        "memory_limits_and_spilling",
        "Memory limits and spilling",
        "computing",
        "What does an engine do when an operator needs more memory than it is allowed?",
        "An external sort that spills sorted runs within a memory limit and merges them a fan-in at "
        "a time, counting the bytes written and read, beside DuckDB's memory limit.",
        ("measure",),
        ("orders-shuffled.parquet",),
    ),
    (
        "from_sql_to_a_logical_plan",
        "From SQL to a logical plan",
        "planning",
        "How does an engine turn the text of a query into a plan it can run, and what does the plainest plan cost?",
        "A tokenizer and a recursive-descent parser for the book's SQL, binding against each file's "
        "schema, and a planner that builds the plain logical plan and the operators to run it.",
        ("measure",),
        ("orders-sorted.parquet", "customers.parquet"),
    ),
    (
        "optimiser_rules",
        "Optimiser rules",
        "planning",
        "Which rewrites of a plan save work whatever the data, and what does each one save?",
        "Rules that push each condition down to its table and into the scan, read only the columns "
        "used, and turn a sort under a limit into a top-k, rebuilding every hand-written plan.",
        ("measure",),
        ("orders-sorted.parquet", "customers.parquet"),
    ),
    (
        "statistics_cost_and_join_order",
        "Statistics, cost and join order",
        "planning",
        "How does a planner choose between plans that give the same rows, when it cannot run them to find out which is cheaper?",
        "Estimates from each file's footer, carried up the plan, and a rule that chooses the order of "
        "joins and each join's build side by dynamic programming over those estimates.",
        ("measure",),
        ("orders-sorted.parquet", "customers.parquet", "countries.parquet"),
    ),
    (
        "parallelism_on_one_machine",
        "Parallelism on one machine",
        "scaling_out",
        "How much faster does a query finish with more cores, and what stops it going faster still?",
        "Simulated workers that take a row group at a time through a pipeline, counting each "
        "worker's work and the combining an aggregate needs after them.",
        ("measure",),
        ("orders-sorted.parquet", "orders-paged.parquet"),
    ),
    (
        "partitioning_and_shuffle",
        "Partitioning and shuffle",
        "scaling_out",
        "When a table is spread over many machines, what must move between them to answer a query, and how much?",
        "Simulated nodes that hold a table's row groups, a shuffle and a broadcast that count the "
        "bytes they send, and an aggregate and a join each done two ways.",
        ("measure",),
        ("orders-sorted.parquet", "customers.parquet"),
    ),
    (
        "skew",
        "Skew",
        "scaling_out",
        "What happens when a few keys hold most of the rows, and how can an engine share them out anyway?",
        "A join whose heaviest keys are salted over several nodes, with the other side's rows copied "
        "to each, counting the rows on the busiest node.",
        ("measure",),
        ("orders-sorted.parquet", "customers.parquet"),
    ),
    (
        "stages_and_distributed_execution",
        "Stages and distributed execution",
        "scaling_out",
        "How does a distributed engine run a whole plan across many machines, and what does it do when one of them fails partway through?",
        "A query cut into stages at its shuffles and run a stage at a time on simulated nodes, and "
        "the tasks a failed node costs for each place the rows between stages can be kept.",
        ("measure",),
        ("orders-sorted.parquet", "customers.parquet"),
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
