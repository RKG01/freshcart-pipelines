# Bonus integration: replay pass

**Result: PASS.** Replay was run once against the exact first-pass landing file, with no RabbitMQ publishing.

- Local replay log-file metadata (Asia/Kolkata): replay output file was created 2026-11-16 19:29:20 and last written 19:30:02; the SQL snapshot was written 19:30:45–19:30:48. See `evidence_file_timestamps.csv`.
- Replay source: `data\freshcart_landing\web\web__bonus-1c10364cdd674d3aba1e1b8e2ae43125.json.gz`.
- Replay run ID: `bonus-replay-9a0a759058994971bf55d59be4c656c4`.
- New physical replay landing file: `data\freshcart_landing\web\web__bonus-replay-9a0a759058994971bf55d59be4c656c4.json.gz` (distinct from the source path).
- Replay output reports two records loaded to `FRESHCART_BONUS.BRONZE.ORDERS_RAW`; the ownership preflight and existing six transformation stages completed. Exit code: `0`.
- Both compressed NDJSON files were read locally. Each contains the same two business payloads and order IDs (`BONUS-ORDER-001`, `BONUS-ORDER-002`); their envelope run IDs and extraction metadata differ as expected. `BUSINESS_PAYLOADS_IDENTICAL=True`, `PHYSICAL_PATHS_DISTINCT=True`; the captured comparison is `payload_comparison.log`.
- No messages were republished. The replay calls the existing file load and transformations.
- After-replay SQL snapshot in `replay_snapshot.log`: Bronze order table rows 4 (the two original records plus two replay records); Silver rows 2; Gold rows 2; Gold revenue INR 5,092.38; loyalty points 50; duplicate Gold IDs none. Each expected ID still appears exactly once in Gold with unchanged values.
- Fixture counts after replay remain CRM 4, FX 1, and pincode 3.

Replay raw evidence: `bonus_replay.log`, `bonus_replay.stderr.log`, and `replay_snapshot.log`.
