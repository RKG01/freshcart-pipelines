# B5 future-date quality check: read-only inspection and proposed test plan

## Scope and safety

This phase inspected code and ran only read-only Snowflake queries against `FRESHCART_B1`, using `ACCOUNTADMIN` and `COMPUTE_WH`. No INSERT, DELETE, UPDATE, MERGE, pipeline call, Bronze reload, or table modification was performed. Credentials were read from local `.env` in memory and were not printed or saved here.

## Code inspection

`elt/freshcart_pipeline.py` defines the future-date check in `QUALITY_CHECKS` as:

```python
"future-dated silver orders":
    "SELECT COUNT(*) FROM silver.orders_dedup WHERE order_date > CURRENT_DATE()"
```

`quality_checks(connection)` executes each SQL string in `QUALITY_CHECKS` and prints the check name, result, and `OK` when the result is zero or `PROBLEM` otherwise.

`FUTURE_ORDER` is an optional pipeline fixture, and `SQL_20_ORDERS_DEDUP` creates `silver.orders_dedup` from `silver.orders_clean`. Neither the fixture nor `run_pipeline()` was used in this inspection or in the proposed test.

## Actual read-only inspection results

The Snowflake connection succeeded with the requested role, warehouse, and database.

| Check | Actual result before test |
|---|---:|
| Future-dated rows in `FRESHCART_B1.SILVER.ORDERS_DEDUP` | 0 |
| Total rows in `FRESHCART_B1.SILVER.ORDERS_DEDUP` | 4 |
| Rows with `ORDER_ID = 'B5-MOCK-FUTURE-001'` | 0 (ID is available) |
| Gold orders in `FRESHCART_B1.GOLD.FCT_ORDERS` | 4 |
| Gold revenue (`SUM(AMOUNT_INR)`) | INR 7,785.00 |
| Gold loyalty points (`SUM(LOYALTY_POINTS)`) | 161 |

These are the current Phase 3 read-only totals. The earlier B3 investigation recorded 126 loyalty points at that time; the current 161 reflects the later completed B4 update.

### Actual `silver.orders_dedup` schema

Read from `FRESHCART_B1.INFORMATION_SCHEMA.COLUMNS`, ordered by ordinal position. Snowflake reports all listed columns nullable.

| Position | Column | Data type | Nullable |
|---:|---|---|---|
| 1 | `INGEST_SEQ` | `NUMBER` | Yes |
| 2 | `SOURCE` | `TEXT` | Yes |
| 3 | `ORDER_ID` | `TEXT` | Yes |
| 4 | `EMAIL` | `TEXT` | Yes |
| 5 | `NAME` | `TEXT` | Yes |
| 6 | `ORDER_DATE` | `DATE` | Yes |
| 7 | `AMOUNT` | `NUMBER` | Yes |
| 8 | `CURRENCY` | `TEXT` | Yes |
| 9 | `PINCODE` | `TEXT` | Yes |
| 10 | `UPDATED_AT` | `TIMESTAMP_NTZ` | Yes |
| 11 | `AMOUNT_MISSING` | `BOOLEAN` | Yes |

The proposed insert names only the two existing columns required for the selected check. The remaining columns are nullable and will be omitted, so Snowflake stores `NULL` for them. This test changes only `silver.orders_dedup`; it does not touch Bronze or Gold.

## Proposed SQL sequence (not executed)

The following is the exact proposed write sequence for a later approved test. No statement in this section has been executed.

```sql
BEGIN TRANSACTION;

INSERT INTO FRESHCART_B1.SILVER.ORDERS_DEDUP (ORDER_ID, ORDER_DATE)
VALUES ('B5-MOCK-FUTURE-001', TO_DATE('2099-01-01', 'YYYY-MM-DD'));

-- Existing selected quality-check SQL:
SELECT COUNT(*)
FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE ORDER_DATE > CURRENT_DATE();

-- Expected selected-check output while the temporary row exists:
-- future-dated silver orders: 1  PROBLEM

DELETE FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE ORDER_ID = 'B5-MOCK-FUTURE-001';

-- Cleanup verification: expected 0.
SELECT COUNT(*)
FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE ORDER_ID = 'B5-MOCK-FUTURE-001';

-- Rerun the selected quality check after cleanup: expected 0 / OK.
SELECT COUNT(*)
FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE ORDER_DATE > CURRENT_DATE();

-- COMMIT only after cleanup count = 0 and future-date count = 0.
COMMIT;
```

The corresponding `quality_checks(connection)` invocation prints the selected check in this format; these are expected outputs, not actual Phase 3 execution results:

```text
future-dated silver orders             1   PROBLEM
future-dated silver orders             0   OK
```

### Transaction and rollback safety

- Before the insert, the unique temporary ID was verified absent (count `0`).
- The insert is limited to one row and the temporary ID. The delete predicate uses that same unique ID only.
- Commit is conditional on the temporary ID count returning `0` and the future-date count returning to its pre-test value (`0`).
- If any step errors or either cleanup condition fails, rollback the transaction; then use a fresh read-only check to confirm the temporary ID count is zero. Do not retry without inspecting that result.
- The full `quality_checks()` function includes a separate reconciliation check comparing `silver.orders_enriched` with `silver.orders_dedup`. Since this proposed isolated test adds a row only to `orders_dedup`, that separate check may also report a difference while the mock exists. The targeted future-date result remains the selected check; no other table will be modified to hide that side effect.

## Approval gate

Phase 3 preparation is complete. No database writes have been performed. Stop here; execute this test only after explicit approval for the database write phase.

\n