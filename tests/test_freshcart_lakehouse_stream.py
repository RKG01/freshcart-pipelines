"""Offline mocked tests for the RabbitMQ-to-FreshCart bonus integration."""

import gzip
import json
import pytest

from elt.freshcart_pipeline import SQL_20_ORDERS_DEDUP, SQL_40_GOLD, write_landing
from stream import freshcart_lakehouse_consumer as consumer
from stream.publish_freshcart_orders import BONUS_ORDERS


def test_bonus_publisher_messages_match_freshcart_schema_and_parse():
    assert [consumer.parse_order_message(json.dumps(row)) for row in BONUS_ORDERS] == BONUS_ORDERS
    assert len({row["order_id"] for row in BONUS_ORDERS}) == 2


def test_bonus_orders_have_matching_customer_fx_and_pincode_fixtures():
    from elt import freshcart_pipeline as elt

    customer_emails = {row["email"].lower() for row in elt.MOCK_CRM_TIER_EVENTS}
    fx_dates = {day for row in elt.MOCK_FX_RESPONSES for day in row["rates"]}
    assert all(order["cust_email"] in customer_emails for order in BONUS_ORDERS)
    assert all(order["currency"] in {"INR", "USD"} for order in BONUS_ORDERS)
    assert all(order["order_date"] in fx_dates for order in BONUS_ORDERS if order["currency"] == "USD")
    assert all(order["pincode"] in elt.MOCK_PINCODES for order in BONUS_ORDERS)


@pytest.mark.parametrize("payload", [b"not-json", b"[]", b'{"order_id":"x"}'])
def test_invalid_order_message_is_rejected(payload):
    with pytest.raises(ValueError):
        consumer.parse_order_message(payload)


def test_run_id_is_restricted_before_sql_or_path_interpolation():
    assert consumer.validate_run_id("bonus-replay-abc_123") == "bonus-replay-abc_123"
    with pytest.raises(ValueError, match="run_id"):
        consumer.validate_run_id("x'; USE DATABASE FRESHCART_B1;--")


class FakeChannel:
    def __init__(self, deliveries=()):
        self.deliveries = iter(deliveries)
        self.acks = []
        self.nacks = []
        self.dead_letters = []
        self.in_flight = {}
        self.exchanges = []
        self.queues = {}
        self.bindings = []

    def exchange_declare(self, **kwargs):
        self.exchanges.append(kwargs)

    def queue_declare(self, queue, durable, arguments=None):
        self.queues[queue] = {"durable": durable, "arguments": arguments or {}}
        return type("QueueResult", (), {"method": type("Method", (), {"queue": queue})()})()

    def queue_bind(self, **kwargs):
        self.bindings.append(kwargs)

    def basic_qos(self, **kwargs):
        self.qos = kwargs

    def basic_get(self, queue, auto_ack):
        try:
            method, properties, body = next(self.deliveries)
        except StopIteration:
            return None, None, None
        self.in_flight[method.delivery_tag] = body
        return method, properties, body

    def basic_ack(self, **kwargs):
        self.acks.append(kwargs["delivery_tag"])
        self.in_flight.pop(kwargs["delivery_tag"], None)

    def basic_nack(self, **kwargs):
        self.nacks.append(kwargs)
        body = self.in_flight.pop(kwargs["delivery_tag"], None)
        if not kwargs["requeue"]:
            args = self.queues.get(consumer.ORDER_QUEUE, {}).get("arguments", {})
            if args.get("x-dead-letter-exchange") == consumer.DEAD_LETTER_EXCHANGE:
                self.dead_letters.append((args.get("x-dead-letter-routing-key"), body))


def method(tag, routing_key=consumer.ORDER_ROUTING_KEY):
    return type("Method", (), {"delivery_tag": tag, "routing_key": routing_key})()


def fake_clock():
    now = [0.0]

    def monotonic():
        return now[0]

    def sleep(seconds):
        now[0] += seconds

    return now, monotonic, sleep


def test_dead_letter_topology_and_invalid_delivery_routing(tmp_path):
    channel = FakeChannel([
        (method(1), None, b'{"order_id":"invalid"}'),
        (method(2), None, json.dumps(BONUS_ORDERS[0]).encode()),
    ])
    consumer.declare_bonus_topology(channel)
    assert any(x["exchange"] == "freshcart-orders" and x["exchange_type"] == "topic" for x in channel.exchanges)
    assert any(x["exchange"] == "freshcart-orders-dlx" for x in channel.exchanges)
    assert channel.queues[consumer.ORDER_QUEUE]["arguments"] == {
        "x-dead-letter-exchange": "freshcart-orders-dlx",
        "x-dead-letter-routing-key": "freshcart.orders.invalid",
    }
    assert channel.queues[consumer.DEAD_LETTER_QUEUE]["durable"] is True
    now, monotonic, sleep = fake_clock()
    batch = consumer.collect_for_window(
        channel, consumer.ORDER_QUEUE, 1, poll_seconds=0.25, monotonic=monotonic, sleep=sleep
    )
    assert now[0] == 1
    assert batch.rejected == 1
    assert len(batch.deliveries) == 1
    assert channel.dead_letters == [(consumer.DEAD_LETTER_ROUTING_KEY, b'{"order_id":"invalid"}')]
    assert channel.nacks == [{"delivery_tag": 1, "requeue": False}]
    path = consumer.persist_then_ack(channel, batch.deliveries, "valid-batch", tmp_path)
    assert path.exists()
    assert channel.acks == [2]


def test_landing_write_failure_does_not_ack(tmp_path, monkeypatch):
    channel = FakeChannel()
    monkeypatch.setattr(
        "stream.freshcart_lakehouse_consumer.elt.write_landing",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    with pytest.raises(OSError):
        consumer.persist_then_ack(
            channel,
            [consumer.Delivery(8, consumer.ORDER_ROUTING_KEY, BONUS_ORDERS[0])],
            "batch",
            tmp_path,
        )
    assert channel.acks == []


def test_interrupted_collection_returns_and_persists_partial_batch(tmp_path):
    channel = FakeChannel([(method(9), None, json.dumps(BONUS_ORDERS[0]).encode())])
    now = [0.0]

    def monotonic():
        return now[0]

    def interrupt(_seconds):
        raise KeyboardInterrupt

    batch = consumer.collect_for_window(
        channel, consumer.ORDER_QUEUE, 60, monotonic=monotonic, sleep=interrupt
    )
    assert batch.interrupted is True
    assert [d.delivery_tag for d in batch.deliveries] == [9]
    path = consumer.persist_then_ack(channel, batch.deliveries, "interrupted-batch", tmp_path)
    assert path.exists()
    assert channel.acks == [9]


def test_duplicate_order_ids_and_distinct_versions_are_preserved_for_silver_dedup(tmp_path):
    original = dict(BONUS_ORDERS[0])
    newer = {**original, "amount": "1600.00", "updated_at": "2026-09-01 12:00:00"}
    landing = write_landing("web", [original, original, newer], "duplicate-versions", tmp_path)
    assert consumer.read_landing_records(landing) == [original, original, newer]
    replay = consumer.replay_landing_file(landing, tmp_path)
    assert replay.name != landing.name
    assert consumer.read_landing_records(replay) == [original, original, newer]
    assert "PARTITION BY order_id ORDER BY updated_at DESC, ingest_seq DESC" in SQL_20_ORDERS_DEDUP


def test_replay_uses_new_physical_file_with_same_payloads(tmp_path):
    original = write_landing("web", BONUS_ORDERS, "first", tmp_path)
    replay = consumer.replay_landing_file(original, tmp_path)
    assert original != replay
    assert original.name != replay.name
    replay_again = consumer.replay_landing_file(original, tmp_path, "same-prefix")
    replay_third = consumer.replay_landing_file(original, tmp_path, "same-prefix")
    assert replay_again.name != replay_third.name
    with gzip.open(original, "rt", encoding="utf-8") as first, gzip.open(replay, "rt", encoding="utf-8") as second:
        first_records = [json.loads(line)["data"] for line in first]
        second_records = [json.loads(line)["data"] for line in second]
    assert first_records == second_records == BONUS_ORDERS


def test_fresh_database_can_be_claimed_but_unmarked_existing_objects_cannot():
    assert consumer.authorize_database_state(False, 0, None) is True
    assert consumer.authorize_database_state(True, 0, None) is True
    assert consumer.authorize_database_state(True, 1, [(consumer.OWNER_NAME, 1, "READY")]) is False
    with pytest.raises(consumer.BonusSafetyError, match="no valid"):
        consumer.authorize_database_state(True, 2, None)
    with pytest.raises(consumer.BonusSafetyError, match="invalid"):
        consumer.authorize_database_state(True, 0, [("other-project", 1, "READY")])


def test_unmarked_database_is_rejected_before_any_setup_or_transform(monkeypatch):
    class Connection:
        run_sql_calls = []

    def query(_connection, sql):
        if sql.startswith("SHOW DATABASES"):
            return [(consumer.BONUS_DATABASE,)]
        if "COUNT(*)" in sql and "INFORMATION_SCHEMA.TABLES" in sql:
            if "OWNER_SCHEMA" in sql:
                return [(0,)]
            if "TABLE_SCHEMA = 'BONUS_CONTROL'" in sql:
                return [(0,)]
            return [(3,)]
        raise AssertionError(sql)

    monkeypatch.setattr(consumer.elt, "query", query)
    monkeypatch.setattr(consumer.elt, "run_sql", lambda conn, sql: conn.run_sql_calls.append(sql))
    with pytest.raises(consumer.BonusSafetyError, match="CREATE OR REPLACE"):
        consumer.ensure_bonus_database(Connection())
    assert Connection.run_sql_calls == []


def test_wrong_database_context_is_rejected(monkeypatch):
    monkeypatch.setattr(consumer.elt, "query", lambda _conn, _sql: [("FRESHCART_B1",)])
    with pytest.raises(consumer.BonusSafetyError, match="expected FRESHCART_BONUS"):
        consumer.assert_bonus_database(object())


def test_duplicate_gold_rows_are_rejected_even_if_ids_match(monkeypatch):
    with pytest.raises(RuntimeError, match="Duplicate Gold order IDs"):
        consumer.verify_gold_result(
            ["BONUS-ORDER-001"],
            [("BONUS-ORDER-001", 2)],
            [("BONUS-ORDER-001", 2)],
        )
    consumer.verify_gold_result(
        ["BONUS-ORDER-001", "BONUS-ORDER-002"],
        [("BONUS-ORDER-001", 1), ("BONUS-ORDER-002", 1)],
        [],
    )
    sql = consumer.duplicate_gold_query("'BONUS-ORDER-001'")
    assert "GROUP BY order_id" in sql
    assert "HAVING COUNT(*) > 1" in sql


def test_fixture_insert_plan_is_idempotent_and_rejects_conflicts():
    required = [
        (("CUST-01", "2026-01-01"), ("a@example.com", "Silver"), {"cust_id": "CUST-01"}),
        (("CUST-02", "2026-01-01"), ("b@example.com", "Gold"), {"cust_id": "CUST-02"}),
    ]
    existing = [(("CUST-01", "2026-01-01"), ("a@example.com", "Silver"))]
    assert consumer.plan_fixture_insertions(required, existing, "CRM") == [{"cust_id": "CUST-02"}]
    assert consumer.plan_fixture_insertions(required, [*existing, required[1][:2]], "CRM") == []
    with pytest.raises(consumer.BonusSafetyError, match="conflicts"):
        consumer.plan_fixture_insertions(required, [(("CUST-01", "2026-01-01"), ("wrong", "Silver"))], "CRM")


def test_fx_missing_date_rows_are_grouped_into_one_fixture_record():
    missing = []
    for date, rate in (("2026-09-01", 83.20), ("2026-09-02", 83.35), ("2026-09-03", 83.10)):
        missing.append({
            "base": "USD",
            "rates": {date: {"INR": rate}},
        })
    grouped = consumer.group_fx_rate_fixtures(missing)
    assert len(grouped) == 1
    assert set(grouped[0]["rates"]) == {"2026-09-01", "2026-09-02", "2026-09-03"}
    assert consumer.group_fx_rate_fixtures([]) == []


def test_fresh_database_initialization_marks_ready_only_after_base_setup(monkeypatch):
    class Connection:
        current_database = None
        marker_rows = []
        sql_calls = []

    connection = Connection()
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    def query(_connection, sql):
        if sql.startswith("SHOW DATABASES"):
            return []
        if sql == "SELECT CURRENT_DATABASE()":
            return [(connection.current_database,)]
        if "SELECT project_name, schema_version, initialization_status" in sql:
            return list(connection.marker_rows)
        raise AssertionError(sql)

    def run_sql(_connection, sql):
        connection.sql_calls.append(sql)
        if sql.startswith("USE DATABASE FRESHCART_BONUS"):
            connection.current_database = "FRESHCART_BONUS"
        if "INSERT INTO BONUS_CONTROL.PROJECT_MARKER" in sql:
            connection.marker_rows = [(consumer.OWNER_NAME, consumer.OWNER_VERSION, "INITIALIZING")]
        if "CREATE DATABASE IF NOT EXISTS FRESHCART_BONUS" in sql:
            assert connection.marker_rows == [(consumer.OWNER_NAME, consumer.OWNER_VERSION, "INITIALIZING")]
        if "SET initialization_status = 'READY'" in sql:
            connection.marker_rows = [(consumer.OWNER_NAME, consumer.OWNER_VERSION, "READY")]

    monkeypatch.setattr(consumer.elt, "query", query)
    monkeypatch.setattr(consumer.elt, "run_sql", run_sql)
    consumer.ensure_bonus_database(connection)
    assert connection.current_database == "FRESHCART_BONUS"
    assert connection.marker_rows == [(consumer.OWNER_NAME, consumer.OWNER_VERSION, "READY")]
    assert any("CREATE DATABASE FRESHCART_BONUS" in sql for sql in connection.sql_calls)


def test_replay_checks_ownership_before_writing_new_file(tmp_path, monkeypatch):
    source = write_landing("web", BONUS_ORDERS, "source-run", tmp_path)
    calls = []
    monkeypatch.setattr(consumer, "preflight_bonus_database", lambda: calls.append("ownership"))
    monkeypatch.setattr(consumer, "process_landing_file", lambda path, run, directory: calls.append("process"))
    replay = consumer.run_replay(source, tmp_path, "replay-run")
    assert replay.exists()
    assert calls == ["ownership", "process"]


def test_snowflake_failure_logs_stage_and_keeps_landing_for_replay(tmp_path, monkeypatch, capsys):
    landing = write_landing("web", BONUS_ORDERS, "recoverable-run", tmp_path)
    monkeypatch.setattr(consumer.elt, "connect_snowflake", lambda: (_ for _ in ()).throw(TimeoutError()))
    with pytest.raises(RuntimeError, match="snowflake_connect"):
        consumer.process_landing_file(landing, "recoverable-run", tmp_path)
    out = capsys.readouterr().out
    assert f"landing_file={landing}" in out
    assert "landing_preserved=True" in out
    assert "replay_command=python -m stream.freshcart_lakehouse_consumer --replay-from" in out
    assert landing.exists()


@pytest.mark.parametrize(
    ("failure_stage", "expected_log_stage"),
    [("load", "bronze_order_load"), ("transform", "SQL_20_ORDERS_DEDUP")],
)
def test_load_or_transform_failure_logs_exact_stage_and_preserves_file(
    tmp_path, monkeypatch, capsys, failure_stage, expected_log_stage
):
    landing = write_landing("web", BONUS_ORDERS, f"stage-{failure_stage}", tmp_path)

    class Connection:
        def close(self):
            pass

    monkeypatch.setattr(consumer.elt, "connect_snowflake", lambda: Connection())
    monkeypatch.setattr(consumer, "ensure_bonus_database", lambda _conn: None)
    monkeypatch.setattr(consumer, "load_reference_fixtures", lambda *_args: None)
    if failure_stage == "load":
        monkeypatch.setattr(
            consumer, "bonus_load_file", lambda *_args: (_ for _ in ()).throw(TimeoutError())
        )
    else:
        monkeypatch.setattr(consumer, "bonus_load_file", lambda *_args: None)
        monkeypatch.setattr(
            consumer,
            "run_transformations",
            lambda *_args: (_ for _ in ()).throw(consumer.BonusStageError("SQL_20_ORDERS_DEDUP")),
        )
    with pytest.raises(RuntimeError, match=expected_log_stage):
        consumer.process_landing_file(landing, f"stage-{failure_stage}", tmp_path)
    output = capsys.readouterr().out
    assert f"stage={expected_log_stage}" in output
    assert f"landing_file={landing}" in output
    assert "landing_preserved=True" in output
    assert landing.exists()


def test_bonus_sql_uses_dedup_and_gold_merge_keys():
    assert consumer.BONUS_DATABASE == "FRESHCART_BONUS"
    assert "QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id" in SQL_20_ORDERS_DEDUP
    assert "MERGE INTO gold.fct_orders" in SQL_40_GOLD
    assert "ON t.order_id = s.order_id" in SQL_40_GOLD
    assert "WHEN NOT MATCHED THEN INSERT" in SQL_40_GOLD
    assert "WHEN MATCHED AND t.row_hash <> s.row_hash THEN UPDATE" in SQL_40_GOLD
