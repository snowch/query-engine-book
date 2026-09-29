# Authoring Guide

How to write a chapter of *Queries, operator by operator* without breaking the things that make
it worth reading: an engine that really runs, numbers the build computes, a reference engine
that checks both, and problems that cannot lie about whether you solved them.

## Quick start

```bash
git submodule update --init
make install     # pinned DuckDB and pyarrow, MyST, Pyodide
make             # figures and site into _build/html
make serve       # http://localhost:8000
make check       # exactly what CI runs
```

There is no live preview: re-run `make site` after an edit and reload the page.

## The order to write in

Not the order the chapter is read in.

1. **The query and the fixture.** The query goes in `queries/`. If the chapter needs data with a
   property the fixtures lack (an order, a skew, a cardinality), add a dataset to
   `fixtures/generate.py` and say in its `why` what it exists to show.
2. **The observation.** Run the query through `query_lab.reference.observe` and read DuckDB's
   plan and profile. Decide what the reader should notice and what they should predict.
3. **The operator.** Add it to `python/query_lab/`, reporting its counters as COUNTERS.md says,
   with tests that check its result and its counters against DuckDB.
4. **The problems and their tests.** Make each fail, and read the failure: it is the first thing a
   reader sees. Solve each one outside the repository and check it passes. Never commit a
   solution.
5. **The figures and panels.** Every number the prose will need, as a fragment from
   `python/query_lab/figures.py`. A panel only where a picture beats a table: a report function
   in `query_lab.report`, drawn by `web/lab/` (CLAUDE.md, *Adding things*).
6. **The prose**, last, to serve all of the above.

Writing the prose first produces a chapter that explains what you meant to build.

## The ten sections

`tools/outline.CHAPTER_SHAPE`, and not negotiable; `tests/test_book.py` fails a chapter that adds
or loses one. A section the chapter needs and the shape lacks is a `###` inside one of them.

**The question** is one question in one sentence, then a paragraph on why the previous chapter
leaves it open. The outline holds the question; the page expands it.

**Observe** runs the chapter's query in DuckDB and reads what DuckDB says about it: its plan, from
`EXPLAIN`, and its profile. Quote the query from `queries/`; include the plan from a generated
fragment. Point at what to notice, with a numbered list when there are several things.

**Predict, then measure** is the book's centre. Give the reader what they need to predict
(the generator's recipe, a manifest's facts, a simulator's parameters), then the panel, which asks
for the prediction before it reveals the measurement and then draws the prediction, the engine's
estimate and the measurement side by side. Show one exhibit of a run, not a table and a panel of
the same numbers. The discussion after the panel
compares the three and says what each gap means.

Ask for a prediction only once the chapter has taught what it needs: the reader should be able
to reason to an answer, not guess one. Where the chapter cannot (ch01, before the reader has met
a file's layout or a planner), the prediction is the engine's own estimate, and the panel lets the
reader change the query, from variants the build computed, and watch which numbers move.

**Building it** quotes the operator the measurement needed, in the order it runs. Each quote
gets a paragraph before it saying what to look for. Say what the book's tests check, without a
command: the reader runs nothing but the page.

Open the listing that decides the measurement to editing, so the reader can change it and watch
the counts move: follow its `{literalinclude}` with a ```` ```run ```` block naming what to run on
the edit, a panel's settings as in its ```` ```lab ```` block, or `tests:` a file in
`python/tests/` with an optional `select:` (a pytest `-k` expression). Then say, in a sentence,
one edit worth trying and what it does, and check that it does. Choose listings that are whole
definitions (a function, a method, a class), since an edit runs in place of what the listing
defines. Every quoted query is editable already.

**Compare** puts the book's engine beside DuckDB: the same result, and the counters both report
(COUNTERS.md says which ones can be compared). Where they differ, say why.

**What this cannot tell you** names what the experiment, the simulator and the code leave out,
with the chapter that deals with it. Every chapter that uses a simulator says what the model
omits.

**What this means for your design** turns the measurement into a choice the reader makes at work:
a sort order, a file size, a join's build side, a memory limit. Stay vendor-neutral.

**Key takeaways** sits in a `:::{div}` with `:class: takeaways`. Each item opens with its claim
in bold and gives its reason. Nothing in it is new.

**Problems**: see below.

**Where to go next**: papers, engine source code, and the companion books as optional depth. Keep
the chapter's list of primary sources here.

## Rules with a check behind them

### Never type a number into prose

Row counts, byte counts, request counts and ratios come from a figure. Add a `Figure` to
`python/query_lab/figures.py`, run `make figures`, and include it:

````markdown
```{include} _generated/returned-unit-price-profile.md
```
````

Every fragment ends with the conditions it was computed under: which engine, which version,
which fixture. `scripts/verify-numbers.py` fails on a number with a unit, or any number of two
or more digits, in prose. A constant written as a word ("one thread") passes. A definition that
must be typed as digits takes `% number-ok: <reason>` on the line before its paragraph.

Refer to a query's constants by their role ("the query's threshold"), not their value.

### Never paste code into prose

Quote Python from `python/` and SQL from `queries/`:

````markdown
```{literalinclude} ../python/query_lab/reference.py
:language: python
:start-at: def observe(
:end-before: def bytes_read(
```
````

Anchor on text that survives `ruff format`: a signature's opening, a docstring's first words.
Never `:lines:`. End every listing at the next thing in the file, never at a marker further down:
code later chapters add lands between the anchors unseen, and a chapter once quoted every plan the
chapters after it wrote. `tests/test_book.py` fails a listing over 80 lines, and the page folds
one over 30 behind a button. Quote the part of an operator the chapter explains: when a later
chapter grows a method, give the growth a method of its own, so each chapter quotes its part. The MyST parse fails if an anchor stops matching. Generated output, such as a
plan, is an `{include}` of a fragment. A picture drawn in text goes in a ```` ```diagram ````
fence, which renders in the book's monospace font at a line height that joins box-drawing
characters; a diagram with a count in it comes from a fragment (`figures.explain_of` draws
DuckDB's `EXPLAIN` this way), since the number check skips fenced blocks and a test refuses
numbers typed into one. A page gives no shell commands: the reader needs only a
browser. The one exception is the *On your own machine* section of *Running the lab*; keep
anything about running the book from a clone there.

### Never use a term before its chapter

Each glossary entry names the chapter that introduces it, and `tests/test_book.py` fails if an
earlier chapter uses it. If a chapter needs the idea early, say it in plain words, or move the
definition and the glossary entry to that chapter.

## Problems

A problem is a stub and a test that passes only when the stub is right.

- The stub's docstring is the problem statement. Say what to return, what to refuse, and what
  not to use when using it would skip the lesson.
- Derive the expected answer at test time: from DuckDB, from a manifest, or from a simulator.
  Never store it.
- Test many cases, including the edges, so a hard-coded answer fails.
- Make failure messages teach: "if you got X, you counted the rows before the filter".
- The Problems section opens, before the first problem, with the chapter's workbench: a
  ```` ```problems ```` block holding `chapter: <slug>`. The reader writes answers there and runs
  the graders in the page. Keep the graders to a few tens of seconds: Pyodide is slower than a
  desk, and the page runs every grader of the chapter at once.
- Every chapter has one "diagnose the slow query" problem: a query, its plan and its profile,
  and a question about what made it slow. It has no test, and says what a good answer contains.

## What no check catches

Read the finished page as somebody who has read every chapter before it and none after, and stop
at:

- a sentence that states a fact about DuckDB or the engine. Is it true in the pinned version?
- a word used technically (*batch*, *scan*, *partition*, *page*) in two senses on one page;
- *the* in front of something the page has not introduced;
- a table nobody chose the rows of;
- the same argument made twice, far apart.

Then run STYLE.md's two passes.

## Definition of done

- [ ] The query in `queries/`, the fixture it needs generated and tested
- [ ] The operator merged, tested against DuckDB, reporting COUNTERS.md's counters, and quoted by
      text anchor
- [ ] Problems written, failing for the right reason, solved outside the repository
- [ ] Every number from a generated fragment
- [ ] Every new term in the glossary, bold where the chapter defines it
- [ ] *What this cannot tell you* names the simulator's and the code's limits
- [ ] Edited against STYLE.md, both passes
- [ ] The `[To write` markers gone, and `make check` clean
