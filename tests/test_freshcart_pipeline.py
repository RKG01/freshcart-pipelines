"""Check local FreshCart extraction and SQL safeguards without Snowflake."""

import gzip
import json

import pytest

from elt.freshcart_pipeline import (
    QUALITY_CHECKS,
    SQL_10_ORDERS_CLEAN,
    setup_sql,
    write_landing,
)


def test_write_landing_writes_gzip_jsonl(tmp_path):
    record = {"order_id": "ORD-TEST", "amount": 12}
    path = write_landing("web", [record], "run-test", tmp_path)

    with gzip.open(path, "rt", encoding="utf-8") as landing_file:
        envelope = json.loads(landing_file.readline())

    assert envelope["source"] == "web"
    assert envelope["run_id"] == "run-test"
    assert envelope["data"] == record
    assert envelope["extracted_at"].endswith("+00:00")


def test_currency_rule_is_in_cleaning_validation():
    assert "unsupported_currency" in SQL_10_ORDERS_CLEAN
    assert "currency NOT IN ('INR', 'USD')" in SQL_10_ORDERS_CLEAN


def test_sixth_quality_check_is_future_date_rule():
    assert len(QUALITY_CHECKS) == 6
    assert QUALITY_CHECKS["future-dated silver orders"] == (
        "SELECT COUNT(*) FROM silver.orders_dedup WHERE order_date > CURRENT_DATE()"
    )


def test_setup_rejects_non_identifier_database_names():
    try:
        setup_sql("FRESHCART; DROP DATABASE PROD")
    except ValueError:
        return
    raise AssertionError("Unsafe database identifiers must be rejected")


def test_setup_uses_configured_warehouse_without_creating_one(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    sql_text = setup_sql("FRESHCART_B1")

    assert "USE WAREHOUSE COMPUTE_WH;" in sql_text
    assert "CREATE WAREHOUSE" not in sql_text
    assert "FRESHCART_WH" not in sql_text


def test_setup_requires_and_validates_warehouse(monkeypatch):
    monkeypatch.delenv("SNOWFLAKE_WAREHOUSE", raising=False)
    with pytest.raises(RuntimeError, match="SNOWFLAKE_WAREHOUSE"):
        setup_sql("FRESHCART_B1")

    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH; DROP DATABASE PROD")
    with pytest.raises(ValueError, match="SNOWFLAKE_WAREHOUSE"):
        setup_sql("FRESHCART_B1")


def test_seed_tables_are_merged_without_replace_or_delete(monkeypatch):
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")

    sql_text = setup_sql("FRESHCART_B1")

    assert "CREATE TABLE IF NOT EXISTS ref.tier_multiplier" in sql_text
    assert "CREATE TABLE IF NOT EXISTS ref.state_region" in sql_text
    assert "MERGE INTO ref.tier_multiplier" in sql_text
    assert "MERGE INTO ref.state_region" in sql_text
    assert "('Platinum', 3)" in sql_text
    assert "('Chhattisgarh','Central')" in sql_text
    assert "CREATE OR REPLACE TABLE ref.tier_multiplier" not in sql_text
    assert "CREATE OR REPLACE TABLE ref.state_region" not in sql_text
    assert "DELETE FROM ref.tier_multiplier" not in sql_text
    assert "DELETE FROM ref.state_region" not in sql_text
