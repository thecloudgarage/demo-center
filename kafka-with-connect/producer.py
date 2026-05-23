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
        print(f"Delivery failed for key={msg.key()}: {err}", flush=True)
    else:
        print(f"Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()} key={msg.key()}", flush=True)

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
        "message.timeout.ms": 10000,
        "socket.timeout.ms": 10000,
    }

    p = Producer(conf)

    print(f"Producing messages to topic '{TOPIC}' on '{BOOTSTRAP_SERVERS}' every {INTERVAL_SECONDS}s", flush=True)

    try:
        while True:
            order = make_order()
            key = order["order_id"]
            value = json.dumps(order)

            try:
                p.produce(
                    TOPIC,
                    key=key.encode("utf-8"),
                    value=value.encode("utf-8"),
                    callback=delivery_report,
                )
                p.flush(5)
            except Exception as e:
                print(f"Produce exception: {e}", flush=True)

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Stopping producer...", flush=True)
    finally:
        p.flush(10)

if __name__ == "__main__":
    main()
