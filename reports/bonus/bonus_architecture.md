# Optional bonus: RabbitMQ to FreshCart ELT

## Implementation status

The integration code, local mocked tests, and approved live test are complete. On 2026-11-16, the run initialized the isolated `FRESHCART_BONUS` database, collected and published exactly two messages, processed the batch, then replayed the exact first landing file once. The actual comparison verified Bronze growth from 2 to 4 order rows while Silver and Gold remained at 2 orders, with INR 5,092.38 revenue, 50 loyalty points, and zero duplicate Gold IDs. See the timestamped actual logs and SQL snapshots under `reports/bonus/live_5f057039be864ea497eaa9496e2810bd/`. The first consumer's OS exit code was not captured by its process launcher; its completed success output is preserved and that gap is disclosed in the run report.

## Architecture

```mermaid
flowchart LR
  P[Stable FreshCart test publisher] -->|freshcart.orders.web| X[Topic exchange: freshcart-orders]
  X --> Q[Queue: freshcart-orders-ingest]
  Q --> C[One-minute consumer; manual ACK]
  C --> W[Existing write_landing()]
  W --> F[Unique gzip NDJSON landing file]
  F --> L[Existing load_file()]
  L --> B[FRESHCART_BONUS Bronze]
  B --> S[Existing SQL_10 / SQL_20 / SQL_30 / SQL_31 / SQL_32]
  S --> G[Existing SQL_40_GOLD MERGE]
  C -. invalid payload .-> DX[Bonus DLX: freshcart-orders-dlx]
  DX --> DQ[Durable dead-letter queue]
```

The bonus uses a separate `freshcart-orders` topic exchange, `freshcart.orders.web` routing key, and `freshcart-orders-ingest` queue. Invalid deliveries are NACKed with `requeue=False` into `freshcart-orders-dlx`, routed to `freshcart-orders-dead-letter`. This topology is separate from `rapido-dispatch`; no D1–D3 topology or code is changed. The queue declares dead-letter arguments; if an older queue with incompatible arguments already exists, topology setup fails closed and does not purge or delete it. Inspect/migrate it deliberately before a live run.

The consumer validates FreshCart web-order JSON before persistence. Valid deliveries remain unacknowledged until the gzip NDJSON landing file is written successfully, then are ACKed individually. If landing fails, they remain unacknowledged and connection closure permits broker redelivery. Ctrl+C during collection returns the in-memory batch to the consumer, which attempts to write it before ACKing; if that write fails, the messages remain unacknowledged. A RabbitMQ connection failure during collection does not persist that in-memory partial batch: unacknowledged messages are left for broker redelivery. Dead-lettered invalid messages are retained for inspection instead of discarded.

## Snowflake ownership and isolation

All integration data operations use the hard-coded `FRESHCART_BONUS` database. Before initialization, the code inventories that database. A missing database or an existing database with no table/view objects can be claimed. A nonempty database without a valid marker is refused before setup or transformation. The marker `BONUS_CONTROL.PROJECT_MARKER` identifies project `freshcart-rabbitmq-snowflake-bonus`, schema version 1, and initialization status. First initialization changes it from `INITIALIZING` to `READY` only after base setup succeeds. An interrupted base setup can safely resume from the marker; transformations and loads require `READY`.

Immediately before every load or transformation, the code checks `CURRENT_DATABASE()` and the marker. A changed context or missing, invalid, or incomplete marker causes a safety error. No bonus function selects, creates, or modifies `FRESHCART_B1`; the `.env.example` database placeholder is not used for this choice. No database is dropped. The existing transformation SQL uses `CREATE OR REPLACE` for derived tables, so it is authorized only in the marked bonus database. On a marked bonus database those derived tables are rebuilt by design.

## Existing ELT reuse and fixture seeding

The implementation reuses `setup_sql()`, `write_landing()`, `load_file()`, `run_sql()`, and existing SQL constants from `elt/freshcart_pipeline.py`; it does not call `run_pipeline()` or extract the ordinary web/mobile batch. Replay revalidates ownership before creating the replay file, then calls `load_file()` on that new file. Replay is an operator action, not an automatic retry, and does not publish RabbitMQ messages.

CRM fixtures are reconciled by `(cust_id, effective_from)`, FX rates by `(base_currency, rate_date)`, and successful pincode responses by `pincode`. Only missing business keys are loaded. If an existing key has conflicting fixture values, processing stops rather than silently duplicating or replacing that fixture. Existing B1 fixtures are never touched.

The live run observed 4 CRM raw rows, 1 FX raw row containing 3 rates, and 3 pincode raw rows (8 supporting rows total). The publisher ran once and emitted exactly two messages. The first web landing file contained two orders; replay wrote a second physical file containing the same two business payloads. Actual counts were 2 order Bronze rows after the first load and 4 after replay. Silver remained at 2 and Gold remained at 2; revenue stayed INR 5,092.38, loyalty points stayed 50, and duplicate Gold IDs stayed at zero. `BONUS-ORDER-001` appears once in Gold at INR 1,550.00 / 15 points, and `BONUS-ORDER-002` appears once at INR 3,542.38 / 35 points. Bronze grows because replay appends the same two business payloads from a second physical landing file; Silver deduplication and Gold MERGE preserve business totals. These observed results apply to this execution; the raw logs and SQL outputs are linked below.

Duplicate order IDs within a landing batch are preserved in Bronze, including exact copies and distinct `updated_at` versions. Existing `SQL_20_ORDERS_DEDUP` chooses one version per order ID by `updated_at DESC, ingest_seq DESC`. `SQL_40_GOLD` merges on `order_id`, updating only if `row_hash` changes. After each pass, the consumer queries batch-scoped Bronze count, Silver count, Gold count/revenue/loyalty points, counts Gold rows per expected ID, and runs a grouped `HAVING COUNT(*) > 1` query. It requires zero duplicate Gold rows and exactly one Gold row per distinct expected ID.

## Failure recovery

After a Snowflake load or transformation failure, the original landing file remains on disk. The consumer logs the landing path and failed stage without printing the underlying connector exception text. It emits a manual replay command. Replay verifies the ownership marker, writes a new file and unique run ID (even when an optional run-ID prefix is supplied), then loads that file through the existing `load_file()`. Replaying can append additional Bronze records; existing Silver deduplication and Gold MERGE are intended to prevent duplicate business orders. No automatic retry is performed.

## Actual live execution evidence

The approved run is recorded under [`live_5f057039be864ea497eaa9496e2810bd/`](live_5f057039be864ea497eaa9496e2810bd/):

- `bonus_consumer.log`, `bonus_publisher.log`, and `bonus_replay.log` contain actual process output.
- `first_snapshot.log` and `replay_snapshot.log` contain actual fully qualified SQL and results; `payload_comparison.log` confirms the same business payloads in distinct files; `evidence_file_timestamps.csv` preserves local evidence-file times.
- `bonus_first_run.md`, `bonus_replay_run.md`, and `bonus_idempotency_comparison.md` summarize the run IDs, landing paths, counts, and observed limitations.
- The consumer's operating-system exit code was not captured; no exit code is inferred from its successful output. Publisher and replay exit codes were captured as 0.

The web landing file and replay file are listed in the run reports. No second publish or other assignment experiment was performed during this run.

## Offline tests

`tests/test_freshcart_lakehouse_stream.py` mocks RabbitMQ and Snowflake. It covers message validation, dead-letter topology/routing behavior, timeout and interruption collection, write-before-ACK, duplicate order versions, ownership and context guards, fixture insertion planning, duplicate Gold validation, and landing-file recovery/replay. These tests do not establish actual broker routing, successful Snowflake execution, or live Gold idempotency.

Local verification recorded for this code update: `python -m pytest -q` completed with **41 passed**; Python compilation passed; `git diff --check` found no whitespace errors. Pytest emitted a `pytest-asyncio` configuration deprecation warning. No external service or SQL was exercised.
