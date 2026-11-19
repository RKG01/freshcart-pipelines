# Phase 3: Local RabbitMQ setup

## Configuration

- Image: `rabbitmq:4-management`
- Container: `freshcart-rabbitmq`
- AMQP: host `127.0.0.1:5672` to container port `5672`
- Management UI: host `127.0.0.1:15672` to container port `15672`
- Persistent named volume: `freshcart_rabbitmq_data`
- Health check: `rabbitmq-diagnostics -q ping`
- Local application username: `freshcart` (the default `guest` account is not used by the application)
- `.env` has `RABBITMQ_USER`, `RABBITMQ_PASSWORD`, and `RABBITMQ_URL`. The password was generated with Python `secrets.token_hex(24)`. The secret and complete URL are intentionally omitted from this report and terminal evidence.
- `.env.example` contains placeholders only.
- Git ignore verification: `git check-ignore -v .env` returned `.gitignore:1:.env`; `git ls-files --error-unmatch .env` confirmed `.env` is not tracked.

## Actual verification

`docker compose config --quiet` exited 0.

`docker compose up -d` created and started the requested image, service, network, and persistent named volume. Docker then reported:

```text
NAME                 IMAGE                   STATUS                    PORTS
freshcart-rabbitmq   rabbitmq:4-management   Up (healthy)              127.0.0.1:5672->5672/tcp, 127.0.0.1:15672->15672/tcp
```

Actual client and HTTP checks:

```text
=== Pika AMQP check (credentials suppressed) ===
AMQP_CONNECTION=success
AMQP_CHECK_EXIT=0
=== Management UI HTTP check ===
HTTP_STATUS=200
=== Container health and port bindings ===
health=healthy ports={"15672/tcp":[{"HostIp":"127.0.0.1","HostPort":"15672"}],"5672/tcp":[{"HostIp":"127.0.0.1","HostPort":"5672"}]}
```

The AMQP test used the existing `.venv` Python and `pika`, reading `RABBITMQ_URL` from `.env` without printing it. No other containers or Docker volumes were modified or deleted. The management interface is bound to loopback and was not publicly exposed.

\n