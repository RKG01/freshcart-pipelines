# FreshCart B4: Pre-change Predictions and Gold Snapshot

**Database:** `FRESHCART_B1`
**Role:** `ACCOUNTADMIN`
**Warehouse:** `COMPUTE_WH`
**Pre-change baseline run ID:** `20261115_063011_352098`

This file records the read-only B4 preparation before any Snowflake write. The proposed event was inspected but has not been added or applied. No setup or pipeline function was run in this investigation.

## Proposed CRM event

```json
{
  "cust_id": "CUST-02",
  "email": "arjun.k@yahoo.in",
  "tier": "Gold",
  "effective_from": "2026-08-15"
}
```

The `bronze.customers_raw` query for CUST-02 found one event, ingest sequence `3`, run ID `20261115_063011_352098`: Silver effective `2024-01-15`. The exact proposed Gold event was not present in the returned Bronze records.

## Actual current SCD2 and ORD-1002

CUST-02 SCD2 row:

| cust_id | email | tier | valid_from | valid_to | is_current |
| --- | --- | --- | --- | --- | --- |
| CUST-02 | arjun.k@yahoo.in | Silver | 2024-01-15 | 9999-12-31 | TRUE |

Current Gold row for ORD-1002:

| order_id | order_date | cust_id | tier | multiplier | amount | currency | fx_rate | amount_inr | loyalty_points | row_hash | published_at |
| --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | ---: | --- |
| ORD-1002 | 2026-09-01 | CUST-02 | Silver | 1 | 42.50 | USD | 83.2000 | 3536.00 | 35 | -7698738864412791922 | 2026-11-14 22:30:28.048000-08:00 |

## Actual pre-change Gold snapshot

This exact projection was read before any B4 write:

| order_id | tier | multiplier | loyalty_points | row_hash | published_at |
| --- | --- | ---: | ---: | ---: | --- |
| ORD-1001 | Silver | 1 | 12 | 4284627330879666653 | 2026-11-14 22:30:28.048000-08:00 |
| ORD-1002 | Silver | 1 | 35 | -7698738864412791922 | 2026-11-14 22:30:28.048000-08:00 |
| ORD-1003 | Platinum | 3 | 63 | -1632326326823866187 | 2026-11-14 22:30:28.048000-08:00 |
| ORD-1005 | Gold | 2 | 16 | -231880702048109571 | 2026-11-14 22:30:28.048000-08:00 |

Current totals from Snowflake: **4 orders**, **INR 7,785.00 revenue**, **126 loyalty points**.

## Predictions before execution

| Quantity | Prediction |
| --- | ---: |
| CUST-02 rows in `dim.customers_scd2` after event | 2 |
| Tier for ORD-1002 after event | Gold |
| ORD-1002 loyalty points after event | 70 |
| Total Gold loyalty points after event | 161 |
| Gold rows whose `published_at` changes | 1 |

Reasoning: the event effective `2026-08-15` precedes ORD-1002's `2026-09-01` order date, so the point-in-time SCD2 join should select Gold. The current rate and amount are `USD 42.50 × 83.2000 = INR 3,536.00`. Gold multiplier 2 gives `FLOOR(3,536 / 100) × 2 = 70` points. This changes ORD-1002 from 35 points to 70, so predicted total points are `126 - 35 + 70 = 161`. The row hash includes tier/multiplier and derived points, so ORD-1002 is predicted to be the single changed row and to receive a new `published_at`; all other snapshot rows are predicted to remain unchanged.

These are predictions only. No Gold/SCD2 write, pipeline execution, or post-change verification has occurred.
\n