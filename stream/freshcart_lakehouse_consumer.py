"""Collect FreshCart orders from RabbitMQ and load them through the existing ELT."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

from elt import freshcart_pipeline as elt

ORDER_EXCHANGE = "freshcart-orders"
ORDER_ROUTING_KEY = "freshcart.orders.web"
ORDER_QUEUE = "freshcart-orders-ingest"
BONUS_DATABASE = "FRESHCART_BONUS"
DEAD_LETTER_EXCHANGE = "freshcart-orders-dlx"
DEAD_LETTER_QUEUE = "freshcart-orders-dead-letter"
DEAD_LETTER_ROUTING_KEY = "freshcart.orders.invalid"
OWNER_SCHEMA = "BONUS_CONTROL"
OWNER_TABLE = "PROJECT_MARKER"
OWNER_NAME = "freshcart-rabbitmq-snowflake-bonus"
OWNER_VERSION = 1
REQUIRED_ORDER_FIELDS = (
    "order_id", "cust_email", "cust_name", "order_date", "amount",
    "currency", "pincode", "updated_at",
)


@dataclass(frozen=True)
class Delivery:
    delivery_tag: int
    routing_key: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class CollectionResult:
    deliveries: list[Delivery]
    rejected: int
    started_at: datetime
    ended_at: datetime
    interrupted: bool


class BonusSafetyError(RuntimeError):
    """Raised when the bonus database cannot be proven safe to modify."""


class BonusStageError(RuntimeError):
    """Identifies the exact existing SQL transformation that failed."""

    def __init__(self, stage: str):
        super().__init__(stage)
        self.stage = stage


def parse_order_message(body: bytes | str) -> dict[str, Any]:
    """Decode and validate a web-shaped order while preserving its JSON values."""
    try:
        value = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError, TypeError) as error:
        raise ValueError("message is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError("message JSON must be an object")
    missing = [field for field in REQUIRED_ORDER_FIELDS if field not in value]
    if missing:
        raise ValueError(f"missing required order fields: {', '.join(missing)}")

    text_fields = ("order_id", "cust_email", "cust_name", "order_date", "currency", "pincode", "updated_at")
    if any(not isinstance(value[field], str) or not value[field].strip() for field in text_fields):
        raise ValueError("order identity and descriptive fields must be non-empty strings")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}", value["cust_email"].strip()):
        raise ValueError("cust_email is invalid")
    if value["currency"].strip().upper() not in {"INR", "USD"}:
        raise ValueError("currency must be INR or USD")
    if not re.fullmatch(r"[1-9][0-9]{5}", value["pincode"].strip()):
        raise ValueError("pincode must contain six digits")
    try:
        datetime.strptime(value["order_date"], "%Y-%m-%d")
        datetime.fromisoformat(value["updated_at"].replace("Z", "+00:00"))
        amount = Decimal(str(value["amount"]).replace(",", "").replace("₹", "").strip())
    except (ValueError, InvalidOperation, TypeError) as error:
        raise ValueError("order_date, updated_at, or amount is invalid") from error
    if not amount.is_finite() or amount <= 0:
        raise ValueError("amount must be a positive finite number")
    return value


def validate_run_id(run_id: str) -> str:
    """Constrain IDs used in SQL literals, stage paths, and local filenames."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise ValueError("run_id must contain 1-80 ASCII letters, digits, underscores, or hyphens")
    return run_id


def collect_for_window(
    channel: Any,
    queue: str,
    duration_seconds: float,
    *,
    poll_seconds: float = 0.2,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> CollectionResult:
    """Collect deliveries without ACK; malformed messages are permanently rejected."""
    started_at = datetime.now(timezone.utc)
    deadline = monotonic() + duration_seconds
    deliveries: list[Delivery] = []
    rejected = 0
    interrupted = False
    try:
        while monotonic() < deadline:
            method, _properties, body = channel.basic_get(queue=queue, auto_ack=False)
            if method is None:
                sleep(min(poll_seconds, max(0.0, deadline - monotonic())))
                continue
            try:
                payload = parse_order_message(body)
            except ValueError as error:
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
                rejected += 1
                print(
                    f"REJECTED routing_key={method.routing_key} delivery_tag={method.delivery_tag} reason={error}",
                    flush=True,
                )
                continue
            deliveries.append(Delivery(method.delivery_tag, method.routing_key, payload))
    except KeyboardInterrupt:
        interrupted = True
    ended_at = datetime.now(timezone.utc)
    return CollectionResult(deliveries, rejected, started_at, ended_at, interrupted)


def declare_bonus_topology(channel: Any) -> None:
    """Declare the isolated order route and a durable dead-letter path."""
    channel.exchange_declare(exchange=ORDER_EXCHANGE, exchange_type="topic", durable=True)
    channel.exchange_declare(exchange=DEAD_LETTER_EXCHANGE, exchange_type="topic", durable=True)
    channel.queue_declare(queue=DEAD_LETTER_QUEUE, durable=True)
    channel.queue_bind(
        exchange=DEAD_LETTER_EXCHANGE,
        queue=DEAD_LETTER_QUEUE,
        routing_key=DEAD_LETTER_ROUTING_KEY,
    )
    channel.queue_declare(
        queue=ORDER_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": DEAD_LETTER_EXCHANGE,
            "x-dead-letter-routing-key": DEAD_LETTER_ROUTING_KEY,
        },
    )
    channel.queue_bind(exchange=ORDER_EXCHANGE, queue=ORDER_QUEUE, routing_key=ORDER_ROUTING_KEY)


def persist_then_ack(channel: Any, deliveries: list[Delivery], run_id: str, landing_dir: Path) -> Path | None:
    """Write the raw payload file first; ACK only after durable local write succeeds."""
    if not deliveries:
        return None
    validate_run_id(run_id)
    expected_path = landing_dir / "web" / f"web__{run_id}.json.gz"
    if expected_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing landing file: {expected_path}")
    records = [delivery.payload for delivery in deliveries]
    landing_path = elt.write_landing("web", records, run_id, landing_dir)
    for delivery in deliveries:
        channel.basic_ack(delivery_tag=delivery.delivery_tag)
        print(
            f"ACKED routing_key={delivery.routing_key} order_id={delivery.payload['order_id']} "
            f"delivery_tag={delivery.delivery_tag}",
            flush=True,
        )
    return landing_path


def authorize_database_state(
    database_exists: bool,
    project_object_count: int,
    marker_rows: list[tuple[Any, ...]] | None,
) -> bool:
    """Return True for a fresh unclaimed DB; reject unowned or malformed state."""
    if marker_rows is not None:
        acceptable = {
            (OWNER_NAME, OWNER_VERSION, "READY"),
            (OWNER_NAME, OWNER_VERSION, "INITIALIZING"),
        }
        if len(marker_rows) != 1 or tuple(marker_rows[0]) not in acceptable:
            raise BonusSafetyError(
                f"Safety stop: {BONUS_DATABASE} has an invalid {OWNER_SCHEMA}.{OWNER_TABLE} ownership marker. "
                "No project tables were changed. Inspect the database manually."
            )
        return False
    if database_exists and project_object_count:
        raise BonusSafetyError(
            f"Safety stop: {BONUS_DATABASE} contains {project_object_count} table/view object(s) but has no valid "
            f"{OWNER_SCHEMA}.{OWNER_TABLE} marker. Refusing setup or CREATE OR REPLACE transformations."
        )
    if project_object_count:
        raise BonusSafetyError(f"Safety stop: unexpected project objects found for {BONUS_DATABASE}.")
    return True


def assert_bonus_database(connection) -> None:
    """Require this Snowflake session to be using the owned bonus database."""
    current = elt.query(connection, "SELECT CURRENT_DATABASE()")[0][0]
    if str(current).upper() != BONUS_DATABASE:
        raise BonusSafetyError(
            f"Safety stop: current Snowflake database is {current!r}; expected {BONUS_DATABASE}."
        )


def bonus_query(connection, sql_text: str) -> list[tuple[Any, ...]]:
    assert_bonus_database(connection)
    return elt.query(connection, sql_text)


def bonus_run_sql(connection, sql_text: str) -> None:
    assert_bonus_database(connection)
    verify_owner_marker(connection)
    elt.run_sql(connection, sql_text)


def bonus_load_file(connection, local_path: Path, table: str, stage_dir: str) -> None:
    assert_bonus_database(connection)
    verify_owner_marker(connection)
    elt.load_file(connection, local_path, table, stage_dir)


def verify_owner_marker(connection) -> None:
    """Check the exact bonus ownership row in the selected database."""
    assert_bonus_database(connection)
    try:
        rows = elt.query(
            connection,
            f"SELECT project_name, schema_version, initialization_status "
            f"FROM {BONUS_DATABASE}.{OWNER_SCHEMA}.{OWNER_TABLE}",
        )
    except Exception as error:
        raise BonusSafetyError(
            f"Safety stop: ownership marker {BONUS_DATABASE}.{OWNER_SCHEMA}.{OWNER_TABLE} is unavailable."
        ) from error
    if rows != [(OWNER_NAME, OWNER_VERSION, "READY")]:
        raise BonusSafetyError(
            f"Safety stop: {BONUS_DATABASE} does not have the expected bonus ownership/version marker."
        )


def ensure_bonus_database(connection) -> None:
    """Claim only a missing or empty database; refuse unmarked existing objects."""
    try:
        databases = elt.query(connection, f"SHOW DATABASES LIKE '{BONUS_DATABASE}'")
        database_exists = bool(databases)
        object_count = 0
        marker_rows = None
        marker_table_exists = False
        if database_exists:
            object_count = int(elt.query(connection, f"""
                SELECT COUNT(*)
                FROM {BONUS_DATABASE}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA <> 'INFORMATION_SCHEMA'
            """)[0][0])
            marker_count = int(elt.query(connection, f"""
                SELECT COUNT(*)
                FROM {BONUS_DATABASE}.INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{OWNER_SCHEMA}' AND TABLE_NAME = '{OWNER_TABLE}'
            """)[0][0])
            marker_table_exists = marker_count == 1
            if marker_table_exists:
                marker_rows = elt.query(
                    connection,
                    f"SELECT project_name, schema_version, initialization_status "
                    f"FROM {BONUS_DATABASE}.{OWNER_SCHEMA}.{OWNER_TABLE}",
                )
    except Exception:
        raise BonusSafetyError(
            f"Safety stop: could not inventory {BONUS_DATABASE} and its ownership marker. "
            "Refusing to create or modify project objects."
        ) from None
    is_fresh = authorize_database_state(
        database_exists,
        max(0, object_count - int(marker_table_exists)),
        marker_rows,
    )
    if not database_exists:
        elt.run_sql(connection, f"CREATE DATABASE {BONUS_DATABASE}")
    elt.run_sql(connection, f"USE DATABASE {BONUS_DATABASE}")
    assert_bonus_database(connection)
    if is_fresh:
        # A marker is written only after confirming the database is empty. It also
        # lets a failed first setup safely resume without claiming unknown objects.
        elt.run_sql(connection, f"""
            CREATE SCHEMA IF NOT EXISTS {OWNER_SCHEMA};
            CREATE TABLE {OWNER_SCHEMA}.{OWNER_TABLE} (
              project_name STRING NOT NULL,
              schema_version NUMBER NOT NULL,
              initialization_status STRING NOT NULL,
              initialized_at TIMESTAMP_TZ DEFAULT CURRENT_TIMESTAMP()
            );
        """)
        elt.run_sql(connection, f"""
            INSERT INTO {OWNER_SCHEMA}.{OWNER_TABLE}
              (project_name, schema_version, initialization_status)
            VALUES ('{OWNER_NAME}', {OWNER_VERSION}, 'INITIALIZING')
        """)
    # An INITIALIZING marker permits only this idempotent base setup to resume.
    if not is_fresh:
        rows = elt.query(connection,
            f"SELECT project_name, schema_version, initialization_status "
            f"FROM {BONUS_DATABASE}.{OWNER_SCHEMA}.{OWNER_TABLE}")
        if rows not in ([(OWNER_NAME, OWNER_VERSION, "READY")],
                        [(OWNER_NAME, OWNER_VERSION, "INITIALIZING")]):
            raise BonusSafetyError(f"Safety stop: invalid ownership marker in {BONUS_DATABASE}.")
    # This helper creates base tables only; all CREATE OR REPLACE transforms
    # occur later after initialization has reached READY.
    elt.run_sql(connection, elt.setup_sql(BONUS_DATABASE))
    assert_bonus_database(connection)
    elt.run_sql(connection, f"""
        UPDATE {OWNER_SCHEMA}.{OWNER_TABLE}
        SET initialization_status = 'READY', initialized_at = CURRENT_TIMESTAMP()
        WHERE project_name = '{OWNER_NAME}' AND schema_version = {OWNER_VERSION}
    """)
    verify_owner_marker(connection)


def plan_fixture_insertions(
    required: list[tuple[tuple[Any, ...], tuple[Any, ...], Any]],
    existing: list[tuple[tuple[Any, ...], tuple[Any, ...]]],
    fixture_name: str,
) -> list[Any]:
    """Return missing fixture records; reject conflicting values for a business key."""
    seen: dict[tuple[Any, ...], tuple[Any, ...]] = {}
    for key, value in existing:
        if key in seen and seen[key] != value:
            raise BonusSafetyError(f"Conflicting existing {fixture_name} rows share business key {key!r}.")
        seen[key] = value
    missing = []
    for key, value, record in required:
        if key in seen:
            if seen[key] != value:
                raise BonusSafetyError(f"Existing {fixture_name} row for business key {key!r} conflicts with fixture.")
        else:
            missing.append(record)
            seen[key] = value
    return missing


def group_fx_rate_fixtures(missing_rate_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pack absent daily rates back into one source record per base currency."""
    rates_by_base: dict[str, dict[str, dict[str, Any]]] = {}
    for record in missing_rate_records:
        rates_by_base.setdefault(record["base"], {}).update(record["rates"])
    grouped = []
    for template in elt.MOCK_FX_RESPONSES:
        rates = rates_by_base.get(template["base"])
        if not rates:
            continue
        grouped.append({
            **{key: value for key, value in template.items() if key != "rates"},
            "start_date": min(rates),
            "end_date": max(rates),
            "rates": rates,
        })
    return grouped


def load_reference_fixtures(connection, landing_dir: Path, run_id: str) -> None:
    """Insert only missing, non-conflicting CRM, FX-date, and pincode fixtures."""
    crm_existing = bonus_query(connection, """
        SELECT raw:cust_id::STRING, TO_CHAR(TRY_TO_DATE(raw:effective_from::STRING), 'YYYY-MM-DD'),
               LOWER(TRIM(raw:email::STRING)), INITCAP(TRIM(raw:tier::STRING))
        FROM bronze.customers_raw WHERE source = 'crm'
    """)
    crm_required = [
        ((r["cust_id"], r["effective_from"]), (r["email"].strip().lower(), r["tier"].strip().title()), r)
        for r in elt.MOCK_CRM_TIER_EVENTS
    ]
    crm_rows = plan_fixture_insertions(
        crm_required,
        [((r[0], str(r[1])), (r[2], r[3])) for r in crm_existing],
        "CRM",
    )
    if crm_rows:
        path = elt.write_landing("crm", crm_rows, run_id, landing_dir)
        bonus_load_file(connection, path, "bronze.customers_raw", f"crm/{run_id}")

    fx_existing = bonus_query(connection, """
        SELECT r.raw:base::STRING, f.key::STRING, f.value:INR::NUMBER(12,4)
        FROM bronze.fx_raw r, LATERAL FLATTEN(input => r.raw:rates) f
        WHERE r.source = 'fx' AND f.value:INR IS NOT NULL
    """)
    fx_required = []
    for response in elt.MOCK_FX_RESPONSES:
        for rate_date, rates in response["rates"].items():
            rate = rates["INR"]
            record = {
                **{key: value for key, value in response.items() if key != "rates"},
                "start_date": rate_date,
                "end_date": rate_date,
                "rates": {rate_date: rates},
            }
            fx_required.append(((response["base"], rate_date), (Decimal(str(rate)),), record))
    missing_rate_records = plan_fixture_insertions(
        fx_required,
        [((r[0], str(r[1])), (Decimal(str(r[2])),)) for r in fx_existing],
        "FX",
    )
    fx_missing = group_fx_rate_fixtures(missing_rate_records)
    if fx_missing:
        path = elt.write_landing("fx", fx_missing, run_id, landing_dir)
        bonus_load_file(connection, path, "bronze.fx_raw", f"fx/{run_id}")

    pincode_existing = bonus_query(connection, """
        SELECT raw:pincode::STRING, raw:response[0]:Status::STRING,
               raw:response[0]:PostOffice[0]:District::STRING,
               raw:response[0]:PostOffice[0]:State::STRING
        FROM bronze.pincode_raw
        WHERE source = 'pincode' AND raw:response[0]:Status::STRING = 'Success'
    """)
    pincode_required = []
    for pin in elt.MOCK_PINCODES:
        response = elt.mock_pincode_response(pin)
        office = response[0].get("PostOffice") or [{}]
        expected_office = office[0]
        record = {"pincode": pin, "response": response}
        signature = (response[0]["Status"], expected_office.get("District"), expected_office.get("State"))
        pincode_required.append(((pin,), signature, record))
    pincode_rows = plan_fixture_insertions(
        pincode_required,
        [((r[0],), tuple(r[1:])) for r in pincode_existing],
        "pincode",
    )
    if pincode_rows:
        path = elt.write_landing("pincode", pincode_rows, run_id, landing_dir)
        bonus_load_file(connection, path, "bronze.pincode_raw", f"pincode/{run_id}")


def run_transformations(connection, run_id: str) -> None:
    """Apply existing SQL constants in dependency order; never invoke run_pipeline()."""
    validate_run_id(run_id)
    bonus_run_sql(connection, f"SET run_id = '{run_id}'")
    for stage, sql_text in (
        ("SQL_10_ORDERS_CLEAN", elt.SQL_10_ORDERS_CLEAN),
        ("SQL_20_ORDERS_DEDUP", elt.SQL_20_ORDERS_DEDUP),
        ("SQL_30_CUSTOMERS_SCD2", elt.SQL_30_CUSTOMERS_SCD2),
        ("SQL_31_FX_DAILY", elt.SQL_31_FX_DAILY),
        ("SQL_32_PINCODE_GEO", elt.SQL_32_PINCODE_GEO),
        ("SQL_40_GOLD", elt.SQL_40_GOLD),
    ):
        print(f"TRANSFORM_STAGE={stage}", flush=True)
        try:
            bonus_run_sql(connection, sql_text)
        except BonusSafetyError:
            raise
        except Exception:
            raise BonusStageError(stage) from None


def duplicate_gold_query(order_id_sql: str) -> str:
    return f"""
        SELECT order_id, COUNT(*)
        FROM gold.fct_orders
        WHERE order_id IN ({order_id_sql})
        GROUP BY order_id
        HAVING COUNT(*) > 1
    """


def verify_gold_result(
    expected_order_ids: list[str],
    order_counts: list[tuple[str, int]],
    duplicate_rows: list[tuple[str, int]],
) -> None:
    """Require one and only one Gold row for every distinct input order ID."""
    expected = set(expected_order_ids)
    counts = dict(order_counts)
    if duplicate_rows:
        duplicate_ids = [row[0] for row in duplicate_rows]
        raise RuntimeError(f"Duplicate Gold order IDs detected: {duplicate_ids}")
    if set(counts) != expected or any(counts[order_id] != 1 for order_id in expected):
        raise RuntimeError("Each expected bonus order ID must appear exactly once in Gold.")


def process_landing_file(landing_path: Path, run_id: str, landing_dir: Path) -> dict[str, Any]:
    """Load one captured order file and transform it in FRESHCART_BONUS."""
    connection = None
    stage = "read_landing_file"
    try:
        validate_run_id(run_id)
        if not landing_path.is_file():
            raise FileNotFoundError(landing_path)
        records = read_landing_records(landing_path)
        order_ids = sorted({record["order_id"] for record in records})
        if not order_ids:
            raise ValueError("landing file contains no order records")
        # IDs have already been validated as strings; escape literals for the scoped checks.
        order_id_sql = ", ".join("'" + order_id.replace("'", "''") + "'" for order_id in order_ids)
        stage = "snowflake_connect"
        connection = elt.connect_snowflake()
        stage = "database_ownership_check"
        ensure_bonus_database(connection)
        stage = "reference_fixture_seed"
        load_reference_fixtures(connection, landing_dir, f"bonus-ref-{run_id}")
        stage = "bronze_order_load"
        bonus_load_file(connection, landing_path, "bronze.orders_raw", f"orders_web/{run_id}")
        stage = "transformations"
        run_transformations(connection, run_id)
        stage = "verification_queries"
        metrics = bonus_query(connection, f"""
            SELECT COUNT(*), COALESCE(SUM(amount_inr), 0), COALESCE(SUM(loyalty_points), 0)
            FROM gold.fct_orders
            WHERE order_id IN ({order_id_sql})
        """)[0]
        order_counts = bonus_query(connection, f"""
            SELECT order_id, COUNT(*)
            FROM gold.fct_orders
            WHERE order_id IN ({order_id_sql})
            GROUP BY order_id
        """)
        duplicate_rows = bonus_query(connection, duplicate_gold_query(order_id_sql))
        print(f"DUPLICATE_GOLD_ORDER_IDS={json.dumps([row[0] for row in duplicate_rows])}", flush=True)
        bronze_orders = bonus_query(connection,
            f"SELECT COUNT_IF(raw:order_id::STRING IN ({order_id_sql})) FROM bronze.orders_raw")[0][0]
        silver_orders = bonus_query(connection,
            f"SELECT COUNT(*) FROM silver.orders_dedup WHERE order_id IN ({order_id_sql})")[0][0]
        result = {
            "gold_orders": int(metrics[0]),
            "amount_inr": str(metrics[1]),
            "loyalty_points": int(metrics[2]),
            "order_ids": [row[0] for row in order_counts],
            "bronze_orders": int(bronze_orders),
            "silver_orders": int(silver_orders),
            "duplicate_gold_order_ids": [row[0] for row in duplicate_rows],
        }
        print(f"SNOWFLAKE_DATABASE={BONUS_DATABASE}", flush=True)
        print(f"LANDING_FILE={landing_path}", flush=True)
        print(f"BRONZE_ORDERS={result['bronze_orders']} SILVER_ORDERS={result['silver_orders']}", flush=True)
        print(f"GOLD={result['gold_orders']} orders amount_inr={result['amount_inr']} loyalty_points={result['loyalty_points']}", flush=True)
        print(f"GOLD_ORDER_IDS={json.dumps(result['order_ids'])}", flush=True)
        verify_gold_result(order_ids, order_counts, duplicate_rows)
        if int(silver_orders) != len(order_ids) or int(metrics[0]) != len(order_ids):
            raise RuntimeError("Each distinct captured order ID must appear once in deduplicated Silver and Gold.")
        return result
    except Exception as error:
        failed_stage = getattr(error, "stage", stage)
        safe_error_type = type(error).__name__
        safe_detail = str(error) if isinstance(error, BonusSafetyError) else safe_error_type
        replay_command = f'python -m stream.freshcart_lakehouse_consumer --replay-from "{landing_path}"'
        print(
            f"PROCESSING_FAILED stage={failed_stage} landing_file={landing_path} error={safe_detail} "
            f"landing_preserved={landing_path.exists()} replay_command={replay_command}",
            flush=True,
        )
        raise RuntimeError(
            f"Bonus processing failed at stage '{failed_stage}'. Landing file is preserved at {landing_path}. "
            f"{safe_detail} Replay manually with: {replay_command}"
        ) from None
    finally:
        if connection is not None:
            connection.close()


def replay_landing_file(source_path: Path, landing_dir: Path, run_id: str | None = None) -> Path:
    """Copy the exact captured records to a new write_landing file for replay."""
    records = read_landing_records(source_path)
    prefix = validate_run_id(run_id) if run_id else "bonus-replay"
    new_run_id = validate_run_id(f"{prefix}-{uuid4().hex}")
    expected_path = landing_dir / "web" / f"web__{new_run_id}.json.gz"
    if expected_path.exists():
        raise FileExistsError(f"Replay run ID already has a landing file: {expected_path}")
    return elt.write_landing("web", records, new_run_id, landing_dir)


def preflight_bonus_database() -> None:
    """Verify or safely initialize the owned database before making a replay file."""
    connection = elt.connect_snowflake()
    try:
        ensure_bonus_database(connection)
    finally:
        connection.close()


def run_replay(source_path: Path, landing_dir: Path, run_id: str | None = None) -> Path:
    """Ownership-check first, then create a new file and load it without RabbitMQ."""
    if run_id is not None:
        validate_run_id(run_id)
    preflight_bonus_database()
    replay_path = replay_landing_file(source_path, landing_dir, run_id)
    effective_run_id = replay_path.name.removeprefix("web__").removesuffix(".json.gz")
    print(f"REPLAY_SOURCE={source_path} REPLAY_LANDING_FILE={replay_path}", flush=True)
    process_landing_file(replay_path, effective_run_id, landing_dir)
    return replay_path


def read_landing_records(path: Path) -> list[dict[str, Any]]:
    """Read and validate original records from the existing gzip JSONL envelope."""
    with gzip.open(path, "rt", encoding="utf-8") as source:
        records = [json.loads(line)["data"] for line in source if line.strip()]
    return [parse_order_message(json.dumps(record, ensure_ascii=False)) for record in records]


def run_consumer(duration_seconds: float, landing_dir: Path) -> Path | None:
    """Collect one batch from the dedicated topic queue and persist before ACK."""
    broker_url = os.getenv("RABBITMQ_URL")
    if not broker_url:
        raise RuntimeError("Set RABBITMQ_URL in the environment or local .env file")
    import pika

    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    batch_id = f"bonus-{uuid4().hex}"
    deliveries: list[Delivery] = []
    rejected = 0
    started_at = datetime.now(timezone.utc)
    ended_at = started_at
    landing_path: Path | None = None
    try:
        channel = connection.channel()
        try:
            declare_bonus_topology(channel)
        except Exception as error:
            raise RuntimeError(
                "Bonus RabbitMQ topology setup failed. Check exchange/queue permissions and whether the durable "
                "freshcart-orders-ingest queue already exists with incompatible dead-letter arguments; no queue "
                "was purged or deleted."
            ) from None
        queue = ORDER_QUEUE
        channel.basic_qos(prefetch_count=100)
        print(f"BATCH_ID={batch_id} CONSUMER_READY_AT={started_at.isoformat()} QUEUE={queue}", flush=True)
        batch = collect_for_window(channel, queue, duration_seconds)
        deliveries, rejected = batch.deliveries, batch.rejected
        started_at, ended_at = batch.started_at, batch.ended_at
        print(
            f"BATCH_ID={batch_id} COLLECTION_END={ended_at.isoformat()} "
            f"COLLECTION_START={started_at.isoformat()} "
            f"ELAPSED_SECONDS={(ended_at - started_at).total_seconds():.3f} "
            f"MESSAGE_COUNT={len(deliveries)} REJECTED_COUNT={rejected} "
            f"COLLECTION_INTERRUPTED={batch.interrupted}",
            flush=True,
        )
        landing_path = persist_then_ack(channel, deliveries, batch_id, landing_dir)
    finally:
        if connection.is_open:
            connection.close()
    if landing_path is not None:
        print(f"BATCH_ID={batch_id} LANDING_FILE={landing_path}", flush=True)
        process_landing_file(landing_path, batch_id, landing_dir)
    return landing_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=float, default=60.0)
    parser.add_argument("--landing-dir", type=Path, default=elt.LANDING_DIR)
    parser.add_argument("--replay-from", type=Path, help="Replay a previous gzip landing file without RabbitMQ")
    parser.add_argument("--run-id", help="Optional unique run ID for replay")
    args = parser.parse_args()
    if args.duration_seconds <= 0:
        parser.error("--duration-seconds must be positive")
    if args.replay_from:
        if args.run_id is not None:
            validate_run_id(args.run_id)
        run_replay(args.replay_from, args.landing_dir, args.run_id)
    else:
        run_consumer(args.duration_seconds, args.landing_dir)


if __name__ == "__main__":
    main()
