| Part | The book's model | Its settings | Built in |
|---|---|---|---|
| Data cache | One level; a line may sit anywhere; the line used longest ago is pushed out | 512 lines of 64 bytes: 32 KiB | [ch02](#batches-in-memory) |
| Branch predictor | A two-bit counter for each branch in the code | Four states; predicts taken in the top two | [ch06](#expressions-and-vectorised-kernels) |
| Vector unit | One instruction applies an operation to a lane-full of values | 4 lanes of eight bytes | [ch06](#expressions-and-vectorised-kernels) |
| Storage | An object store that logs every request and the bytes it returns | Every byte the scan reads is a byte a request returned | [ch03](#projection-and-filter-pushdown) |
| Memory | A limit on the bytes an operator holds; beyond it, runs are written out and merged | Limits of 10%, 20%, 50% and 100% of the input's bytes | [ch10](#memory-limits-and-spilling) |
| Cores | Workers that each take the next morsel when free, and never wait on each other | From 1 to 16 workers | [ch14](#parallelism-on-one-machine) |
| Machines | Nodes that each hold some row groups, and send rows as Arrow IPC bytes | From 2 to 64 nodes | [ch15](#partitioning-and-shuffle) |
| The reference | DuckDB, pinned, with one thread, at the book's build and in the page | DuckDB 1.1.2 | [ch01](#the-plan-is-the-map) |

*Read from the settings of the book's simulators and its pinned DuckDB, at build time.*
