Producer app (producer.py)
```
#!/usr/bin/env python3
import os
import json
import time
import uuid
from random import randint, uniform
from confluent_kafka import Producer

BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
TOPIC = os.getenv("KAFKA_TOPIC", "orders")
INTERVAL_SECONDS = float(os.getenv("INTERVAL_SECONDS", "1.0"))

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed for key={msg.key()}: {err}")
    else:
        print(f"Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()} key={msg.key()}")

def make_order():
    return {
        "order_id": str(uuid.uuid4()),
        "customer_id": randint(1, 1000),
        "amount": round(uniform(10.0, 500.0), 2),
        "currency": "USD",
        "status": "NEW"
    }

def main():
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "client.id": "orders-producer",
    }
    p = Producer(conf)

    print(f"Producing messages to topic '{TOPIC}' on '{BOOTSTRAP_SERVERS}' every {INTERVAL_SECONDS}s")
    try:
        while True:
            order = make_order()
            key = order["order_id"]
            value = json.dumps(order)

            # Trigger delivery callbacks from previous messages
            p.poll(0)

            p.produce(
                TOPIC,
                key=key.encode("utf-8"),
                value=value.encode("utf-8"),
                callback=delivery_report,
            )

            time.sleep(INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Stopping producer...")
    finally:
        p.flush()

if __name__ == "__main__":
    main()
```
Producer app Dockerfile
```
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir confluent-kafka

COPY producer.py .

CMD ["python", "producer.py"]
```
Consumer app (consumer.py)
```
#!/usr/bin/env python3
import os
from confluent_kafka import Consumer, KafkaException

BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
TOPIC = os.getenv("KAFKA_TOPIC", "orders")
GROUP_ID = os.getenv("GROUP_ID", "orders-cli-consumer")

def main():
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
    }

    consumer = Consumer(conf)
    consumer.subscribe([TOPIC])

    print(f"Subscribed to topic '{TOPIC}' on '{BOOTSTRAP_SERVERS}' (Ctrl+C to exit)")
    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            value = msg.value().decode("utf-8") if msg.value() else ""
            print(f"[{msg.topic()}:{msg.partition()}@{msg.offset()}] {value}")
    except KeyboardInterrupt:
        print("Stopping consumer...")
    finally:
        consumer.close()

if __name__ == "__main__":
    main()
```
Consumer app Dockerfile
```
FROM python:3.11-slim

WORKDIR /app

# Install librdkafka dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Kafka client
RUN pip install --no-cache-dir confluent-kafka

COPY consumer.py .

CMD ["python", "consumer.py"]
```
