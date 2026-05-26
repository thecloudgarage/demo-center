#!/usr/bin/env python3
import os
import json
import time
import uuid
import random
from confluent_kafka import Producer

BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
TOPIC = os.getenv("KAFKA_TOPIC", "orders")
INTERVAL_SECONDS = float(os.getenv("INTERVAL_SECONDS", "1.0"))

# How often to generate anomalous orders
ANOMALY_RATE = float(os.getenv("ANOMALY_RATE", "0.08"))  # 8%

# A small set of "high activity" customers to create realistic repeat patterns
VIP_CUSTOMERS = [101, 205, 333, 444, 777]
REGIONS = ["US", "CA", "UK", "DE", "IN"]
PAYMENT_METHODS = ["card", "paypal", "wallet", "bank_transfer"]
STATUSES = ["NEW", "NEW", "NEW", "NEW", "PENDING"]  # mostly NEW

def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed for key={msg.key()}: {err}")
    else:
        print(f"Delivered to {msg.topic()}[{msg.partition()}]@{msg.offset()} key={msg.key().decode('utf-8')}")

def make_normal_order():
    # Mostly modest values with occasional mid-range orders
    customer_id = random.choice(VIP_CUSTOMERS) if random.random() < 0.15 else random.randint(1, 1000)

    amount = round(
        min(
            max(random.gauss(120, 45), 10.0),
            600.0
        ),
        2
    )

    quantity = random.choices([1, 2, 3, 4, 5], weights=[50, 25, 12, 8, 5])[0]
    region = random.choices(REGIONS, weights=[45, 10, 10, 10, 25])[0]
    payment_method = random.choices(PAYMENT_METHODS, weights=[60, 15, 20, 5])[0]

    return {
        "order_id": str(uuid.uuid4()),
        "customer_id": customer_id,
        "amount": amount,
        "currency": "USD",
        "status": random.choice(STATUSES),
        "quantity": quantity,
        "region": region,
        "payment_method": payment_method,
        "is_synthetic_anomaly": False
    }

def make_anomalous_order():
    anomaly_type = random.choice([
        "very_large_amount",
        "bulk_order",
        "odd_customer_pattern",
        "unusual_region_payment_combo"
    ])

    base = {
        "order_id": str(uuid.uuid4()),
        "customer_id": random.randint(1, 1000),
        "amount": round(random.uniform(10.0, 500.0), 2),
        "currency": "USD",
        "status": "NEW",
        "quantity": 1,
        "region": random.choice(REGIONS),
        "payment_method": random.choice(PAYMENT_METHODS),
        "is_synthetic_anomaly": True,
        "anomaly_type": anomaly_type
    }

    if anomaly_type == "very_large_amount":
        base["amount"] = round(random.uniform(2500.0, 15000.0), 2)

    elif anomaly_type == "bulk_order":
        base["amount"] = round(random.uniform(800.0, 3000.0), 2)
        base["quantity"] = random.randint(20, 200)

    elif anomaly_type == "odd_customer_pattern":
        # Reuse a customer but assign an amount far outside their normal behavior
        base["customer_id"] = random.choice(VIP_CUSTOMERS)
        base["amount"] = round(random.uniform(4000.0, 9000.0), 2)

    elif anomaly_type == "unusual_region_payment_combo":
        base["region"] = "DE"
        base["payment_method"] = "bank_transfer"
        base["amount"] = round(random.uniform(1800.0, 5000.0), 2)
        base["quantity"] = random.randint(10, 40)

    return base

def make_order():
    if random.random() < ANOMALY_RATE:
        return make_anomalous_order()
    return make_normal_order()

def main():
    conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "client.id": "orders-producer-ml",
    }

    producer = Producer(conf)

    print(
        f"Producing ML-friendly orders to topic '{TOPIC}' "
        f"on '{BOOTSTRAP_SERVERS}' every {INTERVAL_SECONDS}s "
        f"(anomaly_rate={ANOMALY_RATE})"
    )

    try:
        while True:
            order = make_order()
            key = order["order_id"]
            value = json.dumps(order)

            producer.poll(0)
            producer.produce(
                TOPIC,
                key=key.encode("utf-8"),
                value=value.encode("utf-8"),
                callback=delivery_report,
            )

            anomaly_flag = "ANOMALY" if order.get("is_synthetic_anomaly") else "NORMAL"
            print(
                f"[{anomaly_flag}] order_id={order['order_id']} "
                f"customer_id={order['customer_id']} "
                f"amount={order['amount']} "
                f"qty={order['quantity']} "
                f"region={order['region']} "
                f"payment={order['payment_method']}"
            )

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("Stopping producer.")
    finally:
        producer.flush()

if __name__ == "__main__":
    main()
