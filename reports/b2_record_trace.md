# FreshCart B2 Record Trace

**Database:** `FRESHCART_B1`
**Role:** `ACCOUNTADMIN`
**Warehouse:** `COMPUTE_WH`
**Evidence source:** read-only `SELECT` queries executed after the single B1 baseline. No setup or pipeline code was run for this trace.

## Section 1: ORD-1003

### Raw bronze rows

Query used:

```sql
SELECT ingest_seq, source, raw, run_id, extracted_at
FROM FRESHCART_B1.BRONZE.ORDERS_RAW
WHERE raw:order_id::STRING = 'ORD-1003'
   OR raw:orderId::STRING = 'ORD-1003'
ORDER BY ingest_seq;
```

Actual rows:

| ingest_seq | source | run_id | extracted_at |
| ---: | --- | --- | --- |
| 2 | web | `20261115_063011_352098` | `2026-11-15 06:30:11.356583+00:00` |
| 8 | mobile | `20261115_063011_352098` | `2026-11-15 06:30:11.360858+00:00` |

Web raw JSON:

```json
{
  "amount": null,
  "currency": "INR",
  "cust_email": "meera@outlook.com",
  "cust_name": "MEERA S",
  "order_date": "2026-09-02",
  "order_id": "ORD-1003",
  "pincode": "400050",
  "updated_at": "2026-09-02 09:10:00"
}
```

Mobile raw JSON:

```json
{
  "customer": {
    "email": "Meera@Outlook.com",
    "name": "Meera S"
  },
  "deliveryPin": "400050",
  "orderDate": "02/09/2026",
  "orderId": "ORD-1003",
  "total": {
    "currency": "INR",
    "value": "2,100.00"
  },
  "updatedAt": "2026-09-02T18:40:00"
}
```

The web source is a flat object and the mobile source is nested, so their field names differ. The raw bronze records retain those original shapes.

### Unified checked rows

Query used:

```sql
SELECT ingest_seq, source, order_id, email, name, order_date, amount,
       currency, pincode, updated_at, reasons
FROM FRESHCART_B1.SILVER.ORDERS_CHECKED
WHERE order_id = 'ORD-1003'
ORDER BY ingest_seq;
```

Actual rows:

| ingest_seq | source | order_id | email | name | order_date | amount | currency | pincode | updated_at | reasons |
| ---: | --- | --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| 2 | web | ORD-1003 | meera@outlook.com | Meera S | 2026-09-02 | NULL | INR | 400050 | 2026-09-02 09:10:00 | `[]` |
| 8 | mobile | ORD-1003 | meera@outlook.com | Meera S | 2026-09-02 | 2100.00 | INR | 400050 | 2026-09-02 18:40:00 | `[]` |

In `SQL_10_ORDERS_CLEAN`, the web branch maps `raw:order_id`, `raw:cust_email`, `raw:cust_name`, `raw:order_date`, `raw:amount`, `raw:currency`, `raw:pincode`, and `raw:updated_at`. The mobile branch maps `raw:orderId`, `raw:customer.email`, `raw:customer.name`, `raw:orderDate`, `raw:total.value`, `raw:total.currency`, `raw:deliveryPin`, and `raw:updatedAt` to those same columns. The later typed CTE trims/normalizes email, name, currency, and pincode, and parses the dates and timestamp.

The amount expression is `TRY_TO_DECIMAL(REGEXP_REPLACE(amount, '[^0-9.-]', ''), 12, 2)`. For mobile, this removes the comma from `2,100.00` and converts it to `2100.00`. The web amount remains NULL. Both records have an empty `reasons` array.

### Deduplication and Gold

Deduplicated-row query:

```sql
SELECT ingest_seq, source, order_id, email, name, order_date, amount,
       currency, pincode, updated_at, amount_missing
FROM FRESHCART_B1.SILVER.ORDERS_DEDUP
WHERE order_id = 'ORD-1003';
```

Actual surviving row: ingest sequence `8`, source `mobile`, amount `2100.00`, updated at `2026-09-02 18:40:00`, `amount_missing = FALSE`.

The source SQL is:

```sql
QUALIFY ROW_NUMBER() OVER (
  PARTITION BY order_id
  ORDER BY updated_at DESC, ingest_seq DESC
) = 1;
```

The mobile row survives because its `updated_at` is later (18:40 vs. 09:10). The ingest sequence is the tie-breaker if timestamps match.

Gold query:

```sql
SELECT order_id, order_date, cust_id, email, tier, multiplier, amount,
       currency, fx_rate, amount_inr, loyalty_points, is_high_value,
       city, state, region, updated_at, row_hash, published_at
FROM FRESHCART_B1.GOLD.FCT_ORDERS
WHERE order_id = 'ORD-1003';
```

Actual Gold row:

| order_id | order_date | cust_id | email | tier | multiplier | amount | currency | fx_rate | amount_inr | loyalty_points | is_high_value | city | state | region | updated_at | row_hash | published_at |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- | --- | ---: | --- |
| ORD-1003 | 2026-09-02 | CUST-03 | meera@outlook.com | Platinum | 3 | 2100.00 | INR | 1.0000 | 2100.00 | 63 | TRUE | Mumbai | Maharashtra | West | 2026-09-02 18:40:00 | -1632326326823866187 | 2026-11-14 22:30:28.048000-08:00 |

The Gold SQL computes `amount_inr = ROUND(amount * fx.rate_to_inr, 2)`. The actual rate is `1.0000` for INR, so `2,100.00 × 1.0000 = 2,100.00`. It computes `loyalty_points = FLOOR(amount_inr / 100) * multiplier`, so `FLOOR(2,100 / 100) × 3 = 21 × 3 = 63`.

## Section 2: ORD-1001 and ORD-1005

Gold query used:

```sql
SELECT order_id, order_date, cust_id, email, tier, multiplier, amount,
       currency, fx_rate, amount_inr, loyalty_points, updated_at
FROM FRESHCART_B1.GOLD.FCT_ORDERS
WHERE order_id IN ('ORD-1001', 'ORD-1005')
ORDER BY order_id;
```

Actual rows:

| order_id | order_date | cust_id | email | tier | multiplier | amount | currency | fx_rate | amount_inr | loyalty_points | updated_at |
| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | ---: | ---: | --- |
| ORD-1001 | 2026-09-01 | CUST-01 | priya.r@gmail.com | Silver | 1 | 1250.00 | INR | 1.0000 | 1250.00 | 12 | 2026-09-01 10:02:00 |
| ORD-1005 | 2026-09-03 | CUST-01 | priya.r@gmail.com | Gold | 2 | 899.00 | INR | 1.0000 | 899.00 | 16 | 2026-09-03 16:45:00 |

SCD2 history query used:

```sql
SELECT cust_id, email, tier, valid_from, valid_to, is_current
FROM FRESHCART_B1.DIM.CUSTOMERS_SCD2
WHERE cust_id = 'CUST-01'
ORDER BY valid_from;
```

Actual history:

| cust_id | email | tier | valid_from | valid_to | is_current |
| --- | --- | --- | --- | --- | --- |
| CUST-01 | priya.r@gmail.com | Silver | 2023-04-10 | 2026-09-02 | FALSE |
| CUST-01 | priya.r@gmail.com | Gold | 2026-09-03 | 9999-12-31 | TRUE |

Multiplier query used:

```sql
SELECT tier, multiplier
FROM FRESHCART_B1.REF.TIER_MULTIPLIER
ORDER BY tier;
```

Actual rows: Gold `2`, Platinum `3`, Silver `1`.

`SQL_40_GOLD` joins `dim.customers_scd2` by email and the point-in-time predicate `o.order_date BETWEEN c.valid_from AND c.valid_to`. ORD-1001 (Sept. 1) falls in Priya's Silver interval, ending Sept. 2. ORD-1005 (Sept. 3) falls in the Gold interval beginning Sept. 3. With INR rate 1.0, points are `FLOOR(1,250 / 100) × 1 = 12` for ORD-1001 and `FLOOR(899 / 100) × 2 = 16` for ORD-1005.

## Execution boundary

All statements listed above were `SELECT` queries. No database objects were modified, no pipeline was run, and no credentials were captured in this file.
\n