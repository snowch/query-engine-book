# COUNTERS.md: what every operator reports

Every experiment in this book compares counters, not times. A counter is an exact integer an
operator counts as it runs. It is the same on every machine, at the book's build and in the
reader's browser, so a number printed in the book can be regenerated and checked. A time cannot,
so the book never prints one.

This file is the specification. `python/query_lab/metrics.py` implements it, and
`python/tests/test_metrics.py` holds the two together. Settle a change here first, then in code,
then in every chapter that prints the counter.

## The structure

Each operator owns one `Metrics`. A plan is a tree of operators, so its metrics are a tree too:
`children` holds the metrics of the operators that feed this one, in the order the plan lists
them.

| Field | Meaning |
|---|---|
| `operator` | The operator's kind, as the plan names it: `Scan`, `Filter`, `Project`. |
| `detail` | What distinguishes this operator from others of its kind: a predicate, a column list. |
| `rows_in` | Rows consumed. For a leaf (a scan), rows it decoded from storage. For any other operator, the sum of its children's `rows_out`. |
| `rows_out` | Rows produced for the parent. |
| `batches_in` | Batches consumed. For a leaf, batches decoded; otherwise the children's `batches_out`. |
| `batches_out` | Batches produced, empty ones included. |
| `bytes_read` | Bytes fetched from storage, as the object store logged them. Leaves only. |
| `requests` | Requests made to storage. Leaves only. |
| `peak_memory_bytes` | The high-water mark of Arrow buffer bytes the operator itself held at one time. An operator that streams one batch at a time reports its largest batch. |
| `bytes_spilled` | Bytes written to temporary storage because they did not fit in the memory limit. |
| `bytes_shuffled` | Bytes sent to another partition or worker. |

`requests` is a seventh counter beyond the six in PLAN.md. The scan layer (the Parquet book's
reader) already counts requests to its simulated object store, and a request is what makes
object storage slow, so the counter costs nothing and carries the reading-less argument.

## Invariants

`Metrics.check()` enforces them, and every test of an operator calls it.

1. Every counter is zero or more.
2. A non-leaf operator's `rows_in` is the sum of its children's `rows_out`, and its `batches_in`
   the sum of their `batches_out`. Nothing is lost between operators.
3. Only a leaf reads storage: `bytes_read` and `requests` are zero everywhere else.
4. Rows come out in batches: `rows_out > 0` means `batches_out > 0`.

Invariant 2 makes the tree read like a ledger. Each operator's reduction is `rows_out` against
`rows_in`, and the plan's total work is the sum of `rows_in` down the tree.

## How each is counted

- **Rows and batches** are counted where a batch crosses from one operator to the next, never
  estimated.
- **Bytes read and requests** come from the scan layer's object-store trace: the bytes each
  response returned, including any gap coalescing read. They are never the file's size or a
  column chunk's recorded size. A table scan (ch05) shares one store across the files it opens,
  so its bytes and requests are the table's: the metadata or the listing, then every file.
- **Bytes read by storage that tests rows** (ch05) are what crossed the network: the size of the
  Arrow IPC response, in one request. What the storage read of its own disks is its own scan's
  counters, kept on the operator as `storage` and reported beside it, never added to it, so
  bytes read still means bytes that reached the engine.
- **Peak memory** is the sum of `get_total_buffer_size()` over the Arrow arrays the operator
  retains, at its largest. It counts buffers, not Python objects, so it is the same under
  CPython and Pyodide. It excludes the batches an operator has passed on, which belong to its
  parent from then on.
- **Spilled and shuffled bytes** are the Arrow IPC bytes written, since that is what the engine
  writes to disk and sends between partitions.

## Comparing with DuckDB

`query_lab.metrics.from_duckdb_profile` reads DuckDB's JSON profile (`PRAGMA enable_profiling =
'json'`) into the same tree. DuckDB 1.1.2, the version this book pins, reports fewer counters:

| This book | DuckDB 1.1.2 profile | Compared? |
|---|---|---|
| `operator` | `operator_type` | Named, not compared: the two plans have different shapes. |
| `detail` | `extra_info`, flattened | No. |
| `rows_out` | `operator_cardinality` | Yes: a plan's result rows, and the scan's output rows when both engines pushed the same filter into the scan. |
| `rows_in` (leaf) | `operator_rows_scanned` | **No.** DuckDB reports the rows in the files it opened, not the rows it decoded: on `orders-sorted`, a date filter that skips most row groups still reports every row as scanned. |
| `rows_in` (non-leaf) | the children's `operator_cardinality` | Yes, by invariant 2. |
| `bytes_read` | not reported | Counted outside DuckDB: `query_lab.reference.bytes_read` hands DuckDB a file system, through fsspec, that counts every byte it serves. That is the whole query's reads, so it is compared only with a plan whose one operator is the scan (ch03). The build counts it; the page does not. |
| batches, requests, memory, spill, shuffle | not reported per operator | No. The book measures these in its own engine only, and says so. |

Two settings make the comparison fair. DuckDB runs with one thread, because Pyodide gives it one,
so desk and browser agree. And every query is run from a file in `queries/`, so the SQL the page
shows is the SQL both engines ran.

A DuckDB tree does not satisfy invariant 4 (it reports no batches), so `check()` is for the
book's engine only.

## The simulators' counters

Some costs are not an operator's to count: which bytes a processor had to fetch from memory, for
one. The book counts those with small simulators, each a model that says what it leaves out.
Their counters are exact integers too, the same on every machine and in the browser, and a
figure that prints one names the simulator and its settings in its conditions line.

**The cache model** (`python/query_lab/cache.py`, ch02): `lines` lines of `line_bytes` bytes,
any line anywhere in the cache, the least recently used pushed out first. The book's setting is
512 lines of 64 bytes.

| Field | Meaning |
|---|---|
| `reads` | Reads asked of the cache, one per call, whatever its size. |
| `hits` | Lines a read found in the cache. |
| `misses` | Lines a read had to fetch from memory. A read that spans two lines counts two. |
| `bytes_fetched` | `misses` times `line_bytes`: the bytes moved from memory into the cache. |

Invariants: a read touches at least one line, so `hits + misses >= reads`; and reading a buffer
once, in order, from an empty cache fetches each of its lines exactly once, so its `misses` is
its size in lines. `python/tests/test_memory.py` holds the model to both.

**The expression evaluator** (`python/query_lab/expressions.py`, ch06) counts its own work as it
walks an expression tree, a row or a batch at a time.

| Field | Meaning |
|---|---|
| `dispatches` | Nodes visited: at each, the evaluator decides what to run. A row at a time, every node once per row; a batch at a time, once per batch. |

**The branch predictor** (`python/query_lab/cpu.py`, ch06): a two-bit saturating counter for
each branch in the code, named by the caller, starting at 1 (weakly not taken), predicting taken
at 2 and 3. No history of other branches, no shared table, nothing else a real predictor keeps.

| Field | Meaning |
|---|---|
| `branches` | Branches run: a kernel with an `if` runs two per value (the test's and the loop's), one without runs one (the loop's). |
| `mispredictions` | Branches that went the other way from the counter's guess. |

**The vector unit** (`python/query_lab/cpu.py`, ch06): instructions of `lanes` lanes, every
value eight bytes. The book's setting is four lanes, a 32-byte register of doubles.

| Field | Meaning |
|---|---|
| `instructions` | Instructions run: an operation over `n` values takes `ceil(n / lanes)`; a value at a time takes one each. |
| `lanes_used` | Values computed, one lane each. Divided by `instructions × lanes`, the share of the lanes that did work. |

Invariants: the same values, found with a branch and without one, are the same positions, and
the kernel without one mispredicts at most twice (its loop's first and last); a tree of `k` nodes
over `r` rows makes `k × r` dispatches a row at a time and `k` per batch a batch at a time.
`python/tests/test_expressions.py` holds the models to them.

## What the counters leave out

Counters say how much work was done, not how long it took. Two plans with the same counters can
differ in time because of the cache, branch prediction or vector width; the chapters that make
that argument use the book's small simulators (a cache model, a branch predictor, a SIMD lane
view), each of which says what it leaves out. The book never measures time itself.
