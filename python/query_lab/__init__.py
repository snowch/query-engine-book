"""query_lab: the book's query engine, built one operator at a time.

The engine is Python on Arrow: batches are ``pyarrow.RecordBatch``, and kernels are
``pyarrow.compute``. Its scan layer is the Parquet book's reader (``parquet_lab``, from the
``external/parquet-book`` submodule), imported rather than copied.

| Module | What it does | Chapter |
|---|---|---|
| ``metrics`` | the counters every operator reports (COUNTERS.md) | all |
| ``operators`` | scan, filter and project, pulling batches (the scan is the Parquet book's reader) | ch01 |
| ``plans`` | the hand-written plan for each query the engine runs | ch01 |
| ``reference`` | DuckDB, the reference engine: result, plan and profile of a query | all |
| ``report`` | what each panel draws, as JSON, at build time and in the page | all |
| ``figures`` | every generated fragment and panel the chapters include | all |

It runs unchanged at a desk and, in the page, under Pyodide.
"""
