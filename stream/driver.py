"""Consume requests matching a named driver's RabbitMQ topic binding."""

from __future__ import annotations

import argparse
import json
import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()

from stream.routing import has_zone

EXCHANGE_NAME = "rapido-dispatch"


def handle_delivery(channel, delivery_tag: int, routing_key: str, body: bytes, name: str) -> None:
    """ACK a valid request or permanently NACK one without a zone."""
    try:
        message = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        message = None

    message_id = message.get("id", "<missing>") if isinstance(message, dict) else "<unknown>"
    if not has_zone(message):
        channel.basic_nack(delivery_tag=delivery_tag, requeue=False)
        print(
            f"[{name}] REJECTED routing_key={routing_key} message_id={message_id} "
            "nack_status=nacked requeue=False reason=missing_or_invalid_zone",
            flush=True,
        )
        return

    channel.basic_ack(delivery_tag=delivery_tag)
    print(
        f"[{name}] RECEIVED routing_key={routing_key} message_id={message_id} ack_status=acked",
        flush=True,
    )


def run_driver(name: str, binding_pattern: str) -> None:
    """Create a private queue and ACK good requests, NACK malformed ones."""
    broker_url = os.getenv("RABBITMQ_URL")
    if not broker_url:
        raise RuntimeError("Set RABBITMQ_URL in the environment or local .env file")

    import pika

    connection = pika.BlockingConnection(pika.URLParameters(broker_url))
    channel = connection.channel()
    channel.exchange_declare(exchange=EXCHANGE_NAME, exchange_type="topic", durable=True)
    queue = channel.queue_declare(queue="", exclusive=True, auto_delete=True).method.queue
    channel.queue_bind(exchange=EXCHANGE_NAME, queue=queue, routing_key=binding_pattern)
    channel.basic_qos(prefetch_count=1)

    def handle_message(channel, method, properties, body):
        handle_delivery(channel, method.delivery_tag, method.routing_key, body, name)

    channel.basic_consume(queue=queue, on_message_callback=handle_message, auto_ack=False)
    print(f"[{name}] listening with binding {binding_pattern}", flush=True)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print(f"[{name}] stopped.")
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Driver name shown in received-message output")
    parser.add_argument("pattern", help="RabbitMQ topic binding pattern")
    args = parser.parse_args()
    run_driver(args.name, args.pattern)


if __name__ == "__main__":
    main()
