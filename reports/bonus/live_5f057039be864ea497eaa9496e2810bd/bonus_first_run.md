# Bonus integration: initial live pass

**Result: PASS.** This records the actual first collection and processing pass. The service was initialized and used only `FRESHCART_BONUS`.

- Database initialization log: `database_initialization.log` reports the `freshcart-rabbitmq-snowflake-bonus` marker at schema version 1 with status `READY`.
- Local log-file metadata (Asia/Kolkata): initialization output was written 2026-11-16 19:25:29–19:25:46; consumer log was created 19:26:51 and last written 19:28:30; publisher log was created 19:27:16 and last written 19:27:18. Exact consumer collection timestamps are UTC and recorded below. See `evidence_file_timestamps.csv`.
- Consumer run ID: `bonus-1c10364cdd674d3aba1e1b8e2ae43125`.
- Consumer readiness: `2026-11-16T13:56:53.864064+00:00` (UTC).
- Collection interval: `2026-11-16T13:56:53.917767+00:00` through `2026-11-16T13:57:53.918839+00:00` (UTC), elapsed `60.001` seconds.
- Consumer recorded 2 messages, 0 rejected, and `COLLECTION_INTERRUPTED=False`.
- One publisher invocation exited 0 and recorded two publisher confirmations: `BONUS-ORDER-001` and `BONUS-ORDER-002` (`bonus_publisher.log`). No second publisher invocation was made.
- The consumer wrote and loaded `data\freshcart_landing\web\web__bonus-1c10364cdd674d3aba1e1b8e2ae43125.json.gz`. Both messages were ACKed after the landing write. The consumer then loaded four CRM, one FX, and three pincode fixture rows and two order rows and completed `SQL_10_ORDERS_CLEAN`, `SQL_20_ORDERS_DEDUP`, `SQL_30_CUSTOMERS_SCD2`, `SQL_31_FX_DAILY`, `SQL_32_PINCODE_GEO`, and `SQL_40_GOLD`.
- Actual first-pass snapshot in `first_snapshot.log`: Bronze expected order rows 2; Silver expected orders 2; Gold 2; Gold revenue INR 5,092.38; loyalty points 50; duplicate Gold IDs none.
- Gold values: `BONUS-ORDER-001` appears once with INR 1,550.00 and 15 points; `BONUS-ORDER-002` appears once with INR 3,542.38 and 35 points.
- Actual fixture counts: CRM 4, FX 1, pincode 3 (8 support rows total).

The consumer log shows successful final stage output and process termination, but its launcher did not capture the operating-system exit code. The process exit code is therefore **not recorded**; the output is preserved in `bonus_consumer.log`. Publisher exit code was 0.

Raw evidence: `bonus_consumer.log`, `bonus_consumer.stderr.log`, `bonus_publisher.log`, `bonus_publisher.stderr.log`, `database_initialization.log`, and `first_snapshot.log`.
