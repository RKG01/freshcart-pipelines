"""FreshCart ELT flow from the instructor reference, with assignment changes."""

from __future__ import annotations

import gzip
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

LANDING_DIR = Path(os.getenv("FRESHCART_LANDING_DIR", "data/freshcart_landing"))

MOCK_WEB_ORDERS = [
    {"order_id": "ORD-1001", "cust_email": " Priya.R@Gmail.com ", "cust_name": "priya r", "order_date": "2026-09-01", "amount": "1,250.00", "currency": "INR", "pincode": "600041", "updated_at": "2026-09-01 10:02:00"},
    {"order_id": "ORD-1003", "cust_email": "meera@outlook.com", "cust_name": "MEERA S", "order_date": "2026-09-02", "amount": None, "currency": "INR", "pincode": "400050", "updated_at": "2026-09-02 09:10:00"},
    {"order_id": "ORD-1002", "cust_email": "Arjun.K@Yahoo.in ", "cust_name": "Arjun K", "order_date": "2026-09-01", "amount": "42.50", "currency": "USD", "pincode": "560034", "updated_at": "2026-09-01 11:15:00"},
    {"order_id": "ORD-1004", "cust_email": "rahul.m@gmail.com", "cust_name": "Rahul M", "order_date": "Sep 3, 2026", "amount": "-500", "currency": "INR", "pincode": "110001", "updated_at": "2026-09-03 12:00:00"},
    {"order_id": "ORD-1005", "cust_email": "priya.r@gmail.com", "cust_name": "Priya R.", "order_date": "2026-09-03", "amount": "₹ 899", "currency": "inr", "pincode": "600041", "updated_at": "2026-09-03 16:45:00"},
    {"order_id": "ORD-1006", "cust_email": "vikram@@mail", "cust_name": "Vikram", "order_date": "2026-09-04", "amount": 30, "currency": "EUR", "pincode": "99999", "updated_at": "2026-09-04 08:30:00"},
]

MOCK_MOBILE_ORDERS = [
    {"orderId": "ORD-1002", "customer": {"email": "arjun.k@yahoo.in", "name": "Arjun K"}, "orderDate": "01/09/2026", "total": {"value": "42.50", "currency": "usd"}, "deliveryPin": "560034", "updatedAt": "2026-09-01T11:15:00"},
    {"orderId": "ORD-1003", "customer": {"email": "Meera@Outlook.com", "name": "Meera S"}, "orderDate": "02/09/2026", "total": {"value": "2,100.00", "currency": "INR"}, "deliveryPin": "400050", "updatedAt": "2026-09-02T18:40:00"},
]

MOCK_CRM_TIER_EVENTS = [
    {"cust_id": "CUST-01", "email": "priya.r@gmail.com", "tier": "Silver", "effective_from": "2023-04-10"},
    {"cust_id": "CUST-01", "email": "priya.r@gmail.com", "tier": "Gold", "effective_from": "2026-09-03"},
    {"cust_id": "CUST-02", "email": "arjun.k@yahoo.in", "tier": "Silver", "effective_from": "2024-01-15"},
    {"cust_id": "CUST-03", "email": "meera@outlook.com", "tier": "Platinum", "effective_from": "2022-11-01"},
]

ARJUN_GOLD_EVENT = {
    "cust_id": "CUST-02",
    "email": "arjun.k@yahoo.in",
    "tier": "Gold",
    "effective_from": "2026-08-15",
}

MOCK_FX_RESPONSES = [
    {"amount": 1.0, "base": "USD", "start_date": "2026-09-01", "end_date": "2026-09-03", "rates": {"2026-09-01": {"INR": 83.20}, "2026-09-02": {"INR": 83.35}, "2026-09-03": {"INR": 83.10}}},
]

MOCK_PINCODES = {
    "600041": ("Chennai", "Tamil Nadu"),
    "560034": ("Bengaluru", "Karnataka"),
    "400050": ("Mumbai", "Maharashtra"),
}

FUTURE_ORDER = {
    "order_id": "ORD-2099-01",
    "cust_email": "priya.r@gmail.com",
    "cust_name": "Priya R",
    "order_date": "2099-01-01",
    "amount": None,
    "currency": "INR",
    "pincode": "600041",
    "updated_at": "2099-01-01 10:00:00",
}


def mock_pincode_response(pin: str) -> list[dict[str, Any]]:
    """Return the sample API response shape used by the instructor notebook."""
    if pin not in MOCK_PINCODES:
        return [{"Message": "No records found", "Status": "Error", "PostOffice": None}]
    district, state = MOCK_PINCODES[pin]
    return [{
        "Message": "Number of pincode(s) found:1",
        "Status": "Success",
        "PostOffice": [{"Name": district, "District": district, "State": state, "Country": "India", "Pincode": pin}],
    }]


def connect_snowflake():
    """Connect using environment variables; never persist or print credentials."""
    required = ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD", "SNOWFLAKE_ROLE")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Set these environment variables before connecting: {', '.join(missing)}")

    import snowflake.connector

    options = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "role": os.environ["SNOWFLAKE_ROLE"],
    }
    return snowflake.connector.connect(**options)


def write_landing(source: str, records: list[dict[str, Any]], run_id: str, landing_dir: Path = LANDING_DIR) -> Path:
    """Write newline-delimited JSON records with source/run metadata as gzip."""
    folder = landing_dir / source
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{source}__{run_id}.json.gz"
    extracted_at = datetime.now(timezone.utc).isoformat()
    with gzip.open(path, "wt", encoding="utf-8") as output_file:
        for record in records:
            envelope = {"source": source, "run_id": run_id, "extracted_at": extracted_at, "data": record}
            output_file.write(json.dumps(envelope, ensure_ascii=False) + "\n")
    print(f"{source}: {len(records)} records -> {path}")
    return path


def run_sql(connection, sql_text: str) -> None:
    """Execute a SQL script containing one or more statements."""
    connection.execute_string(sql_text, remove_comments=True)


def query(connection, sql_text: str) -> list[tuple[Any, ...]]:
    """Execute one SQL statement and return all result rows."""
    with connection.cursor() as cursor:
        cursor.execute(sql_text)
        return cursor.fetchall()


def show(connection, sql_text: str):
    """Return a pandas dataframe using the query's result column names."""
    import pandas as pd

    with connection.cursor() as cursor:
        cursor.execute(sql_text)
        return pd.DataFrame(cursor.fetchall(), columns=[column[0] for column in cursor.description])


def load_file(connection, local_path: Path, table: str, stage_dir: str) -> None:
    """Upload one local raw file and copy its JSON rows into the target bronze table."""
    local_uri = local_path.resolve().as_uri().replace("'", "''")
    query(connection, f"PUT '{local_uri}' @bronze.landing/{stage_dir}/ AUTO_COMPRESS=FALSE OVERWRITE=FALSE")
    rows = query(connection, f"""
        COPY INTO {table} (source, raw, run_id, extracted_at, src_file, src_row)
        FROM (
          SELECT $1:source::STRING, $1:data, $1:run_id::STRING,
                 $1:extracted_at::TIMESTAMP_TZ, METADATA$FILENAME, METADATA$FILE_ROW_NUMBER
          FROM @bronze.landing/{stage_dir}/
        )
        FILE_FORMAT = (FORMAT_NAME = 'bronze.ff_ndjson')
        ON_ERROR = 'ABORT_STATEMENT'
    """)
    loaded = sum(int(row[3]) for row in rows if len(row) > 3)
    print(f"{loaded} rows -> {table}")


def setup_sql(database: str) -> str:
    """Build setup SQL for the configured warehouse and target database."""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", database):
        raise ValueError("SNOWFLAKE_DATABASE must be a simple Snowflake identifier")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    if not warehouse:
        raise RuntimeError("Set SNOWFLAKE_WAREHOUSE before preparing the Snowflake setup SQL")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", warehouse):
        raise ValueError("SNOWFLAKE_WAREHOUSE must be a simple Snowflake identifier")
    return f"""
    USE WAREHOUSE {warehouse};
    CREATE DATABASE IF NOT EXISTS {database};
    USE DATABASE {database};
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE SCHEMA IF NOT EXISTS silver;
    CREATE SCHEMA IF NOT EXISTS dim;
    CREATE SCHEMA IF NOT EXISTS ref;
    CREATE SCHEMA IF NOT EXISTS gold;
    CREATE SCHEMA IF NOT EXISTS quarantine;
    CREATE FILE FORMAT IF NOT EXISTS bronze.ff_ndjson TYPE = JSON COMPRESSION = AUTO;
    CREATE STAGE IF NOT EXISTS bronze.landing FILE_FORMAT = bronze.ff_ndjson;
    CREATE TABLE IF NOT EXISTS bronze.orders_raw (
      ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
      run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
      loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
    );
    CREATE TABLE IF NOT EXISTS bronze.customers_raw (
      ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
      run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
      loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
    );
    CREATE TABLE IF NOT EXISTS bronze.fx_raw (
      ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
      run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
      loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
    );
    CREATE TABLE IF NOT EXISTS bronze.pincode_raw (
      ingest_seq NUMBER AUTOINCREMENT START 1 INCREMENT 1 ORDER, source STRING, raw VARIANT,
      run_id STRING, extracted_at TIMESTAMP_TZ, src_file STRING, src_row NUMBER,
      loaded_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
    );
    CREATE TABLE IF NOT EXISTS ref.tier_multiplier (tier STRING, multiplier NUMBER);
    MERGE INTO ref.tier_multiplier AS target
    USING (
      SELECT column1::STRING AS tier, column2::NUMBER AS multiplier
      FROM VALUES ('Silver', 1), ('Gold', 2), ('Platinum', 3)
    ) AS source ON target.tier = source.tier
    WHEN MATCHED AND NOT EQUAL_NULL(target.multiplier, source.multiplier)
      THEN UPDATE SET multiplier = source.multiplier
    WHEN NOT MATCHED THEN INSERT (tier, multiplier) VALUES (source.tier, source.multiplier);

    CREATE TABLE IF NOT EXISTS ref.state_region (state STRING, region STRING);
    MERGE INTO ref.state_region AS target
    USING (
      SELECT column1::STRING AS state, column2::STRING AS region
      FROM VALUES
        ('Tamil Nadu','South'), ('Karnataka','South'), ('Kerala','South'), ('Andhra Pradesh','South'),
        ('Telangana','South'), ('Puducherry','South'), ('Maharashtra','West'), ('Gujarat','West'),
        ('Goa','West'), ('Rajasthan','West'), ('Delhi','North'), ('Haryana','North'), ('Punjab','North'),
        ('Uttar Pradesh','North'), ('Himachal Pradesh','North'), ('Jammu and Kashmir','North'),
        ('Uttarakhand','North'), ('West Bengal','East'), ('Odisha','East'), ('Bihar','East'),
        ('Jharkhand','East'), ('Assam','East'), ('Madhya Pradesh','Central'), ('Chhattisgarh','Central')
    ) AS source ON target.state = source.state
    WHEN MATCHED AND NOT EQUAL_NULL(target.region, source.region)
      THEN UPDATE SET region = source.region
    WHEN NOT MATCHED THEN INSERT (state, region) VALUES (source.state, source.region);
    CREATE TABLE IF NOT EXISTS ref.pincode_geo (
      pincode STRING PRIMARY KEY, city STRING, state STRING, region STRING, updated_at TIMESTAMP_LTZ
    );
    CREATE TABLE IF NOT EXISTS quarantine.orders (
      run_id STRING, quarantined_at TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP(), ingest_seq NUMBER,
      source STRING, order_id STRING, reasons ARRAY, row_data VARIANT
    );
    CREATE TABLE IF NOT EXISTS gold.fct_orders (
      order_id STRING PRIMARY KEY, order_date DATE, cust_id STRING, email STRING, tier STRING,
      multiplier NUMBER, amount NUMBER(12,2), currency STRING, fx_rate NUMBER(12,4),
      amount_inr NUMBER(14,2), loyalty_points NUMBER, is_high_value BOOLEAN, city STRING,
      state STRING, region STRING, updated_at TIMESTAMP_NTZ, row_hash NUMBER, published_at TIMESTAMP_LTZ
    );
    """


SQL_10_ORDERS_CLEAN = r"""
CREATE OR REPLACE TRANSIENT TABLE silver.orders_checked AS
WITH unified AS (
  SELECT ingest_seq, source, raw:order_id::STRING AS order_id,
         raw:cust_email::STRING AS cust_email, raw:cust_name::STRING AS cust_name,
         raw:order_date::STRING AS order_date, raw:amount::STRING AS amount,
         raw:currency::STRING AS currency, raw:pincode::STRING AS pincode,
         raw:updated_at::STRING AS updated_at
  FROM bronze.orders_raw WHERE source = 'web'
  UNION ALL
  SELECT ingest_seq, source, raw:orderId::STRING, raw:customer.email::STRING,
         raw:customer.name::STRING, raw:orderDate::STRING, raw:total.value::STRING,
         raw:total.currency::STRING, raw:deliveryPin::STRING, raw:updatedAt::STRING
  FROM bronze.orders_raw WHERE source = 'mobile'
), typed AS (
  SELECT ingest_seq, source, TRIM(order_id) AS order_id,
         LOWER(TRIM(cust_email)) AS email, INITCAP(RTRIM(TRIM(cust_name), '.')) AS name,
         COALESCE(TRY_TO_DATE(order_date, 'YYYY-MM-DD'), TRY_TO_DATE(order_date, 'DD/MM/YYYY'),
                  TRY_TO_DATE(order_date, 'MON DD, YYYY')) AS order_date,
         TRY_TO_DECIMAL(REGEXP_REPLACE(amount, '[^0-9.-]', ''), 12, 2) AS amount,
         UPPER(TRIM(currency)) AS currency, TRIM(pincode) AS pincode,
         TRY_TO_TIMESTAMP_NTZ(updated_at) AS updated_at
  FROM unified
)
SELECT *, ARRAY_CONSTRUCT_COMPACT(
    IFF(order_id IS NULL, 'missing_order_id', NULL),
    IFF(email IS NULL OR NOT REGEXP_LIKE(email, '^[^@\\s]+@[^@\\s]+\\.[a-z]{2,}$'), 'bad_email', NULL),
    IFF(pincode IS NULL OR NOT REGEXP_LIKE(pincode, '^[1-9][0-9]{5}$'), 'bad_pincode', NULL),
    IFF(order_date IS NULL, 'unparseable_date', NULL),
    IFF(updated_at IS NULL, 'unparseable_updated_at', NULL),
    IFF(amount <= 0, 'non_positive_amount', NULL),
    IFF(currency IS NULL OR currency NOT IN ('INR', 'USD'), 'unsupported_currency', NULL)
  ) AS reasons
FROM typed;

CREATE OR REPLACE TABLE silver.orders_clean AS
SELECT * EXCLUDE reasons, (amount IS NULL) AS amount_missing
FROM silver.orders_checked WHERE ARRAY_SIZE(reasons) = 0;

INSERT INTO quarantine.orders (run_id, ingest_seq, source, order_id, reasons, row_data)
SELECT $run_id, c.ingest_seq, c.source, c.order_id, c.reasons, OBJECT_CONSTRUCT(*)
FROM silver.orders_checked c
WHERE ARRAY_SIZE(c.reasons) > 0
  AND NOT EXISTS (
    SELECT 1 FROM quarantine.orders q
    WHERE q.source = c.source
      AND EQUAL_NULL(q.order_id, c.order_id)
      AND EQUAL_NULL(q.row_data:UPDATED_AT::TIMESTAMP_NTZ, c.updated_at)
  )
QUALIFY ROW_NUMBER() OVER (PARTITION BY c.source, c.order_id, c.updated_at ORDER BY c.ingest_seq DESC) = 1;
"""

SQL_20_ORDERS_DEDUP = r"""
CREATE OR REPLACE TABLE silver.orders_dedup AS
SELECT * FROM silver.orders_clean
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC, ingest_seq DESC) = 1;
"""

SQL_30_CUSTOMERS_SCD2 = r"""
CREATE OR REPLACE TABLE dim.customers_scd2 AS
WITH events AS (
  SELECT raw:cust_id::STRING AS cust_id, LOWER(TRIM(raw:email::STRING)) AS email,
         INITCAP(TRIM(raw:tier::STRING)) AS tier,
         TRY_TO_DATE(raw:effective_from::STRING) AS valid_from, loaded_at, ingest_seq
  FROM bronze.customers_raw
  QUALIFY ROW_NUMBER() OVER (PARTITION BY cust_id, valid_from ORDER BY loaded_at DESC, ingest_seq DESC) = 1
)
SELECT cust_id, email, tier, valid_from,
       COALESCE(DATEADD(day, -1, LEAD(valid_from) OVER (PARTITION BY cust_id ORDER BY valid_from)),
                '9999-12-31'::DATE) AS valid_to,
       LEAD(valid_from) OVER (PARTITION BY cust_id ORDER BY valid_from) IS NULL AS is_current
FROM events WHERE cust_id IS NOT NULL AND valid_from IS NOT NULL;
"""

SQL_31_FX_DAILY = r"""
CREATE OR REPLACE TABLE ref.fx_daily AS
WITH published AS (
  SELECT r.raw:base::STRING AS currency, f.key::DATE AS rate_date,
         f.value:INR::NUMBER(12,4) AS rate_to_inr
  FROM bronze.fx_raw r, LATERAL FLATTEN(input => r.raw:rates) f
  QUALIFY ROW_NUMBER() OVER (PARTITION BY currency, rate_date ORDER BY r.loaded_at DESC, r.ingest_seq DESC) = 1
), bounds AS (
  SELECT MIN(rate_date) AS d0, GREATEST(MAX(rate_date), CURRENT_DATE()) AS d1 FROM published
), spine AS (
  SELECT DATEADD(day, ROW_NUMBER() OVER (ORDER BY SEQ4()) - 1, b.d0) AS d
  FROM bounds b, TABLE(GENERATOR(ROWCOUNT => 4000))
  QUALIFY d <= (SELECT d1 FROM bounds)
), filled AS (
  SELECT c.currency, s.d AS rate_date,
         LAST_VALUE(p.rate_to_inr) IGNORE NULLS OVER (
           PARTITION BY c.currency ORDER BY s.d ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
         ) AS rate_to_inr,
         p.rate_to_inr IS NULL AS is_carried_forward
  FROM spine s CROSS JOIN (SELECT DISTINCT currency FROM published) c
  LEFT JOIN published p ON p.currency = c.currency AND p.rate_date = s.d
)
SELECT currency, rate_date, rate_to_inr, is_carried_forward FROM filled
UNION ALL SELECT 'INR', d, 1.0, FALSE FROM spine;
"""

SQL_32_PINCODE_GEO = r"""
MERGE INTO ref.pincode_geo t
USING (
  SELECT p.pincode, p.city, p.state, sr.region
  FROM (
    SELECT raw:pincode::STRING AS pincode,
           raw:response[0]:PostOffice[0]:District::STRING AS city,
           raw:response[0]:PostOffice[0]:State::STRING AS state,
           loaded_at, ingest_seq
    FROM bronze.pincode_raw WHERE raw:response[0]:Status::STRING = 'Success'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY pincode ORDER BY loaded_at DESC, ingest_seq DESC) = 1
  ) p LEFT JOIN ref.state_region sr ON sr.state = p.state
) s ON t.pincode = s.pincode
WHEN MATCHED AND (t.city <> s.city OR t.state <> s.state OR NVL(t.region, '') <> NVL(s.region, ''))
  THEN UPDATE SET city = s.city, state = s.state, region = s.region, updated_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT (pincode, city, state, region, updated_at)
  VALUES (s.pincode, s.city, s.state, s.region, CURRENT_TIMESTAMP());
"""

SQL_40_GOLD = r"""
CREATE OR REPLACE TABLE silver.orders_enriched AS
SELECT o.*, c.cust_id, c.tier, m.multiplier, fx.rate_to_inr AS fx_rate,
       ROUND(o.amount * fx.rate_to_inr, 2) AS amount_inr,
       FLOOR(amount_inr / 100) * m.multiplier AS loyalty_points,
       amount_inr >= 2000 AS is_high_value, g.city, g.state, g.region
FROM silver.orders_dedup o
LEFT JOIN dim.customers_scd2 c
  ON c.email = o.email AND o.order_date BETWEEN c.valid_from AND c.valid_to
LEFT JOIN ref.tier_multiplier m ON m.tier = c.tier
LEFT JOIN ref.fx_daily fx ON fx.currency = o.currency AND fx.rate_date = o.order_date
LEFT JOIN ref.pincode_geo g ON g.pincode = o.pincode;

MERGE INTO gold.fct_orders t
USING (
  SELECT order_id, order_date, cust_id, email, tier, multiplier, amount, currency, fx_rate,
         amount_inr, loyalty_points, is_high_value, city, state, region, updated_at,
         HASH(order_date, cust_id, email, tier, multiplier, amount, currency, fx_rate,
              amount_inr, loyalty_points, is_high_value, city, state, region, updated_at) AS row_hash
  FROM silver.orders_enriched
) s ON t.order_id = s.order_id
WHEN MATCHED AND t.row_hash <> s.row_hash THEN UPDATE SET
  order_date = s.order_date, cust_id = s.cust_id, email = s.email, tier = s.tier,
  multiplier = s.multiplier, amount = s.amount, currency = s.currency, fx_rate = s.fx_rate,
  amount_inr = s.amount_inr, loyalty_points = s.loyalty_points, is_high_value = s.is_high_value,
  city = s.city, state = s.state, region = s.region, updated_at = s.updated_at,
  row_hash = s.row_hash, published_at = CURRENT_TIMESTAMP()
WHEN NOT MATCHED THEN INSERT
  (order_id, order_date, cust_id, email, tier, multiplier, amount, currency, fx_rate, amount_inr,
   loyalty_points, is_high_value, city, state, region, updated_at, row_hash, published_at)
VALUES
  (s.order_id, s.order_date, s.cust_id, s.email, s.tier, s.multiplier, s.amount, s.currency,
   s.fx_rate, s.amount_inr, s.loyalty_points, s.is_high_value, s.city, s.state, s.region,
   s.updated_at, s.row_hash, CURRENT_TIMESTAMP());
"""


QUALITY_CHECKS = {
  "rows gained or lost while enriching": "SELECT (SELECT COUNT(*) FROM silver.orders_enriched) - (SELECT COUNT(*) FROM silver.orders_dedup)",
  "duplicate orders in gold": "SELECT COUNT(*) - COUNT(DISTINCT order_id) FROM gold.fct_orders",
  "orders with no customer match": "SELECT COUNT_IF(cust_id IS NULL) FROM silver.orders_enriched",
  "orders with an amount but no FX rate": "SELECT COUNT_IF(amount IS NOT NULL AND fx_rate IS NULL) FROM silver.orders_enriched",
  "orders with no city": "SELECT COUNT_IF(city IS NULL) FROM silver.orders_enriched",
  "future-dated silver orders": "SELECT COUNT(*) FROM silver.orders_dedup WHERE order_date > CURRENT_DATE()",
}


def quality_checks(connection) -> dict[str, Any]:
    """Run the five reference checks plus the assignment's future-date check."""
    results = {}
    for name, sql_text in QUALITY_CHECKS.items():
        value = query(connection, sql_text)[0][0]
        results[name] = value
        print(f"{name:38s} {value}   {'OK' if value == 0 else 'PROBLEM'}")
    rejected = query(connection, "SELECT COUNT_IF(ARRAY_SIZE(reasons) > 0) / NULLIF(COUNT(*), 0) FROM silver.orders_checked")[0][0]
    results["share of rows rejected"] = float(rejected or 0)
    print(f"{'share of rows rejected':38s} {results['share of rows rejected']:.0%}")
    return results


def run_pipeline(
    connection,
    *,
    include_arjun_tier_change: bool = False,
    include_future_order: bool = False,
    landing_dir: Path = LANDING_DIR,
) -> str:
    """Extract sample data, load bronze, transform to gold, and run checks."""
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    web_orders = list(MOCK_WEB_ORDERS)
    crm_events = list(MOCK_CRM_TIER_EVENTS)
    if include_future_order:
        web_orders.append(FUTURE_ORDER)
    if include_arjun_tier_change:
        crm_events.append(ARJUN_GOLD_EVENT)

    files = {
        "web": write_landing("web", web_orders, run_id, landing_dir),
        "mobile": write_landing("mobile", MOCK_MOBILE_ORDERS, run_id, landing_dir),
        "crm": write_landing("crm", crm_events, run_id, landing_dir),
        "fx": write_landing("fx", MOCK_FX_RESPONSES, run_id, landing_dir),
    }

    load_file(connection, files["web"], "bronze.orders_raw", f"orders_web/{run_id}")
    load_file(connection, files["mobile"], "bronze.orders_raw", f"orders_mobile/{run_id}")
    load_file(connection, files["crm"], "bronze.customers_raw", f"crm/{run_id}")
    load_file(connection, files["fx"], "bronze.fx_raw", f"fx/{run_id}")

    query(connection, f"SET run_id = '{run_id}'")
    run_sql(connection, SQL_10_ORDERS_CLEAN)
    run_sql(connection, SQL_20_ORDERS_DEDUP)

    pins = [row[0] for row in query(connection, """
        SELECT DISTINCT o.pincode FROM silver.orders_dedup o
        WHERE NOT EXISTS (SELECT 1 FROM ref.pincode_geo g WHERE g.pincode = o.pincode)
    """)]
    if pins:
        lookup_records = [{"pincode": pin, "response": mock_pincode_response(pin)} for pin in pins]
        pincode_file = write_landing("pincode", lookup_records, run_id, landing_dir)
        load_file(connection, pincode_file, "bronze.pincode_raw", f"pincode/{run_id}")

    run_sql(connection, SQL_30_CUSTOMERS_SCD2)
    run_sql(connection, SQL_31_FX_DAILY)
    run_sql(connection, SQL_32_PINCODE_GEO)
    run_sql(connection, SQL_40_GOLD)
    quality_checks(connection)
    totals = query(connection, "SELECT COUNT(*), SUM(amount_inr), SUM(loyalty_points) FROM gold.fct_orders")[0]
    print(f"GOLD: {totals[0]} orders, revenue INR {totals[1]}, {totals[2]} loyalty points")
    return run_id


def baseline_snapshot(connection) -> dict[str, Any]:
    """Return baseline row counts and totals for a human-reviewed comparison."""
    row = query(connection, """
      SELECT (SELECT COUNT(*) FROM bronze.orders_raw),
             (SELECT COUNT(*) FROM silver.orders_clean),
             (SELECT COUNT(*) FROM quarantine.orders),
             (SELECT COUNT(*) FROM silver.orders_dedup),
             (SELECT COUNT(*) FROM gold.fct_orders),
             (SELECT SUM(amount_inr) FROM gold.fct_orders),
             (SELECT SUM(loyalty_points) FROM gold.fct_orders)
    """)[0]
    return dict(zip(
        ("bronze_orders", "clean_orders", "quarantined_orders", "deduplicated_orders", "gold_orders", "gold_revenue_inr", "gold_loyalty_points"),
        row,
    ))
