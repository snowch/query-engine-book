# Query Engine Lab learner wording and interface review

## Opening check

The review starts from the published `main` revision `908aa74`, including the earlier targeted
changes in PR #42. The built route list contains 31 learner pages. It includes 19 chapters, six
part introductions, four appendices, the cover and the preface.

The intended readers are data engineers who already run queries. The reading path requires no
Python or execution. The optional building path uses Python, and the book introduces Arrow,
Parquet internals, hardware and planning concepts where they matter. DuckDB is a pinned reference
engine. The book’s engine, its small models and measurements made in the browser each support
different conclusions. The authoring guide requires generated evidence to be visible without
JavaScript, keeps the ten chapter sections and reserves disclosures for optional work.

The opening rubric checks each heading, instruction, label, example, caption and feedback message
in the order a learner sees it. Look for a purpose and question, prepared state, exact action,
visible evidence, interpretation and next experiment. Verify each suggested change against the
editable code or controls. Define terms before the comparison uses them. Keep essential evidence
visible and give optional editors, diagnostics and references descriptive labels. Distinguish an
execution error, an original-example check, a changed result and an understanding check.

The closing check repeats the rubric. It follows original and edited examples through the normal
interface, checks narrow and wide screens in both themes and uses the keyboard. It verifies that
old and current saved work survive and records functional results separately from evidence of
learning effectiveness.

## Closing review by route

| Page | Reviewed purpose, action and evidence |
| --- | --- |
| Cover | Invites data engineers to the preface and distinguishes the prepared reading path from running and building. |
| Preface | Assumes familiarity with SQL, introduces Arrow for builders and explains the first chapter’s qualitative prediction before the later numeric predictions. |
| Seeing a query | Introduces plans, profiles and the structure of batches before the first case. |
| The plan is the map | Explains the prepared DuckDB plans and names the estimated and actual row fields. The SQL status edit changes the result total. The Python price filter edit changes its input in the printed plan. |
| Batches in memory | Names cache lines and misses before comparing access orders. Reversing the bitmap bits changes the tests. Disabling eviction changes the shuffled gather’s misses. |
| Reading less | Establishes the progression from column selection to skipping row groups, pages and files. |
| Projection and filter pushdown | Names the two files and the exact pruning and filter edits. Removing pruning increases row groups and bytes without changing the result. Bypassing the filters in the separate script changes its result rows. |
| Statistics and pruning | Names the column and offset indexes. Keeping all pages changes the read counts while leaving the row filter in place. |
| Where work happens | Separates table metadata, file metadata and the simulated storage reader. Disabling file exclusion changes the metadata scan’s read and byte counts. |
| Computing | Links each operation to the work its chapter counts, from expressions to writing temporary data. |
| Expressions and vectorised kernels | Separates expression evaluation from the branch model and timing. Adding a modeled branch changes mispredictions while keeping the selected rows. |
| Hash aggregation | Defines the table’s slots and probes. A lower resize threshold trades table bytes for probes in the teaching engine. |
| Joins | Distinguishes the input held by the hash join from the input it reads through the table. Spacing the modeled addresses changes cache misses and keeps the build row count. |
| Sorting and top-k | Uses separate heap push and pop operations. The edited loop makes more comparisons and still hands up ten rows. |
| Memory limits and spilling | Names bytes, runs and passes. Doubling the cutoff changes when the teaching sort writes runs. The original memory setting remains the comparison point. |
| Planning | Introduces parsing and rules before the cost and join-order comparison. The rules reproduce the book’s examples. |
| From SQL to a logical plan | Names the two parser methods and changes the tokens in their conditions and calls. The precedence test identifies the deliberately changed grouping. |
| Optimiser rules | Distinguishes filtering from column selection. The mixed-input condition needs the join. Removing the join case causes more rows to reach the join. |
| Statistics, cost and join order | The edit changes the exact bound in the join estimate. The planner’s estimate changes while the displayed plans’ actual row counts remain stable. |
| Scaling out | Introduces simulated workers and nodes after single-threaded runs. Describes counts of bytes and tasks as model output. |
| Parallelism on one machine | Chooses the busiest worker in the editable scheduling example. Compares worker work with the one-worker case. |
| Partitioning and shuffle | Charges bytes sent between nodes. The intentional single-node test failure shows what happens when the counter also charges local traffic. |
| Skew | Names both functions to edit. Balancing all keys changes the busiest node and the bytes shuffled. Broadcasting avoids shuffle-induced skew in one input. |
| Stages and distributed execution | Names the on-node recovery case and the changed return value. Compares repeated tasks under the assumption that saved output remains available. |
| Other ways to run a plan | Introduces who drives the flow of batches and when the plan becomes executable code. |
| Pushing instead of pulling | Disabling the stop condition changes the bytes and row groups read by the source. |
| Compiling a query | Disabling shared expression reuse changes the modeled instruction count. The timing describes generated Python in the browser. |
| Running the lab | Names the real controls in the order they appear. Explains original checks, edited results, first-run downloads and what to do if draft storage fails. |
| The fixtures | Describes generated Parquet data and the fields in the manifests. |
| The machine in one page | Separates repeatable model counters from optional elapsed-time runs on the reader’s browser. |
| Glossary | Keeps the definitions beside their introducing chapters. An operator can receive different numbers of inputs. |

The reading path exposes worked results while the optional tools are closed. Code disclosures
distinguish editable listings from reference listings. The interactive prediction opens with one
primary reveal action. Keyboard focus follows the result and returns to the first input when the
learner predicts again. Editor results show the counters or tests they ran. They leave out prediction
controls and starter algorithm descriptions. The result label identifies a previous submission
after a learner changes the editor. An execution failure retains the preceding successful result.

Drafts keep their existing storage names and recovery copies. A save warning stays visible while
execution status changes. When saving fails, the reader can download the exact editor text. A
blocked recovery leaves the current text in place. A prediction can be used during that page visit
when browser storage is unavailable.

## Functional verification

- Read the published opening and revised closing builds in Chromium across all 31 routes.
  The narrower viewport was 320 CSS pixels with the dark theme. The wider viewport was 1440
  pixels with the light theme and JavaScript disabled. The revised build resolves all links.
  All published anchors and the bodies of 102 quoted listings were preserved.
- Ran all 21 original Python examples and their 21 literal edits from their ordinary chapter
  editors in Chromium. Compared the returned counters and printed script output with native
  execution. The three edits designed to make tests fail returned test reports with failing
  checks. The other edits returned results and counters without an original-example verdict.
- Reran the first SQL example in DuckDB through the normal editor. The starter returned 1,183
  orders. Changing the status to shipped returned 13,946. The plan and preview both described
  the submitted query. At 320 pixels, the gather prediction survived unavailable storage,
  keyboard reveal and a browser rerun. The first input regained focus when predicting again.
  At 820 pixels, the no-script reading path exposed the worked result and opened the conceptual
  explanation with the keyboard.
- Checked a previous durable SQL draft and an edited SQL statement with a blocked save.
  The save warning remained after the successful run. The unsaved text survived closing and
  reopening the editor during that visit. The download contained the exact unsaved bytes.
  Reload loaded the earlier durable draft.
- Checked the published course’s native and browser parity suites through the repository’s normal
  release checks. Those checks cover the other quoted SQL, worked panels, live timing blocks and
  practice workbenches as well as the first-page walkthroughs.

The checks establish that the directions and tools work and produce the reported evidence.
Learner understanding and transfer to independent work were unmeasured.
