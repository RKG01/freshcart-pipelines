"""Publish the stable, valid bonus order batch to the isolated integration exchange."""

from __future__ import annotations

import json
import os

from stream.freshcart_lakehouse_consumer import ORDER_EXCHANGE, ORDER_ROUTING_KEY, parse_order_message

BONUS_ORDERS = [
    {
        "order_id": "BONUS-ORDER-001",
        "cust_email": "priya.r@gmail.com",
        "cust_name": "Priya R",
        "order_date": "2026-09-01",
        "amount": "1550.00",
        "currency": "INR",
        "pincode": "600041",
        "updated_at": "2026-09-01 10:00:00",
    },
    {
        "order_id": "BONUS-ORDER-002",
        "cust_email": "arjun.k@yahoo.in",
        "cust_name": "Arjun K",
        "order_date": "2026-09-02",
        "amount": "42.50",
        "currency": "USD",
        "pincode": "560034",
        "updated_at": "2026-09-02 11:00:00",
    },
]


def publish_orders() -> None:
    broker_url = os.getenv("RABBITMQ_URL")
    if not broker_url:
        raise RuntimeError("Set RABBITMQ_URL in the environment or local .env file")
    import pika

    for order in BONUS_ORDERS:
        parse_order_message(json.dumps(order))
    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    try:
        channel = connection.channel()
        channel.exchange_declare(exchange=ORDER_EXCHANGE, exchange_type="topic", durable=True)
        channel.confirm_delivery()
        for order in BONUS_ORDERS:
            confirmed = channel.basic_publish(
                exchange=ORDER_EXCHANGE,
                routing_key=ORDER_ROUTING_KEY,
                body=json.dumps(order, separators=(",", ":")),
                properties=pika.BasicProperties(
                    content_type="application/json",
                    delivery_mode=2,
                    message_id=order["order_id"],
                ),
                mandatory=True,
            )
            if confirmed is False:
                raise RuntimeError(f"Publisher confirmation failed for {order['order_id']}")
            print(f"PUBLISHED order_id={order['order_id']} routing_key={ORDER_ROUTING_KEY} confirmed=True", flush=True)
    finally:
        connection.close()


if __name__ == "__main__":
    publish_orders()
