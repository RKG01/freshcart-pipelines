# Bonus integration: idempotency comparison

**Outcome: VERIFIED for the two approved test orders.** Both processing passes completed, and actual Snowflake queries against fully qualified `FRESHCART_BONUS` objects show duplicate raw Bronze versions but unchanged deduplicated and Gold results.

| Metric | After first pass | After one replay | Observed |
|---|---:|---:|---|
| Bronze order rows | 2 | 4 | Replay added exactly two raw records |
| Silver deduplicated orders | 2 | 2 | Unchanged |
| Gold orders for expected IDs | 2 | 2 | Unchanged |
| Gold revenue | INR 5,092.38 | INR 5,092.38 | Unchanged |
| Gold loyalty points | 50 | 50 | Unchanged |
| Duplicate Gold order IDs | 0 | 0 | None |
| CRM fixture rows | 4 | 4 | Unchanged |
| FX fixture rows | 1 | 1 | Unchanged |
| Pincode fixture rows | 3 | 3 | Unchanged |

Each ID was checked with a grouped `COUNT(*)` query. Both passes returned exactly one Gold record per ID:

| Order ID | Gold row count | Amount (INR) | Loyalty points |
|---|---:|---:|---:|
| `BONUS-ORDER-001` | 1 | 1,550.00 | 15 |
| `BONUS-ORDER-002` | 1 | 3,542.38 | 35 |

The initial web landing file was `data\freshcart_landing\web\web__bonus-1c10364cdd674d3aba1e1b8e2ae43125.json.gz` (run ID `bonus-1c10364cdd674d3aba1e1b8e2ae43125`). The single replay produced `data\freshcart_landing\web\web__bonus-replay-9a0a759058994971bf55d59be4c656c4.json.gz` (run ID `bonus-replay-9a0a759058994971bf55d59be4c656c4`). Direct local payload comparison confirmed the same two business payloads in distinct physical files. Across the first processing pass and replay, five landing files were created: web, CRM, FX, and pincode files for the first pass, plus the replay web file. There were two web order landing files; the publisher was run once and emitted exactly two confirmed messages.

The first-pass SQL output is in `first_snapshot.log`; after-replay SQL output is in `replay_snapshot.log`; local payload comparison is in `payload_comparison.log`. Log file creation/last-write times are preserved in `evidence_file_timestamps.csv`. This result establishes idempotency for these two payloads and this one replay under the captured bonus database state; it is not a claim about all possible input or failure conditions. The first consumer launcher did not capture its OS exit code, although its log contains all success-stage output and it terminated; this limitation is retained rather than inferred as exit code 0.
