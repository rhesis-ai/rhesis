# Backend benchmarks

Measures the costs the request path and the worker write path put on Postgres and on the
event loop. Runs against the real app and the real engine on an ephemeral Postgres, with none
of the test suite's session overrides, so pool checkouts and round trips are the real ones.

Outside pytest's default `testpaths` on purpose; run it explicitly, from `apps/backend`:

```bash
cd apps/backend
uv sync --extra all --extra ee          # once per checkout
BENCH_LABEL=baseline BENCH_DB_LATENCY_MS=5 uv run pytest ../../tests/benchmarks/backend -q -s
```

Needs Docker (Testcontainers). Results land in `tests/benchmarks/backend/results/<label>.json`,
gitignored. Compare two runs:

```bash
uv run python ../../tests/benchmarks/compare.py \
  ../../tests/benchmarks/backend/results/baseline.json \
  ../../tests/benchmarks/backend/results/after.json
```

## Scenarios

| scenario | measures |
| --- | --- |
| `request_overhead` | statements and pool checkouts per authenticated list request |
| `loop_stall` | at 1, 10, 50 concurrent requests: throughput, request p95, event-loop lag p99/max, `/health` latency measured from the same loop, peak Postgres connections |
| `list_queries` | after seeding 2000 tests plus 50 000 prompt rows in a second organization: latency and statement count of the paginated list endpoints, plus `EXPLAIN (ANALYZE, BUFFERS)` of the prompt list query |
| `worker_batch` | a 100-test batch run with the endpoint call faked: pool checkouts, statements and wall time per executed test, including progress and activity-log bookkeeping |

## Knobs

| env | default | effect |
| --- | --- | --- |
| `BENCH_LABEL` | git short SHA | result file name |
| `BENCH_DB_LATENCY_MS` | 0 | sleep added to every statement in the thread that runs it, standing in for a slow database. 5 makes loop stalls unmissable |
| `BENCH_CONCURRENCY` | `1,10,50` | sweep levels for `loop_stall` |
| `BENCH_SEED_TESTS` | 2000 | rows seeded for `list_queries` |
| `BENCH_NOISE_PROMPTS` | 50000 | prompt rows in a second org, so the tenant filter has something to exclude; 0 skips the noise org. The slowest part of a run |
| `BENCH_BATCH_TESTS` | 100 | tests executed in `worker_batch` |

Run before and after with the same knobs or the comparison is meaningless.
