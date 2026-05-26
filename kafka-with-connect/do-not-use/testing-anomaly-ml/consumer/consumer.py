#!/usr/bin/env python3
import os
import json
import time
from collections import deque

import numpy as np
from confluent_kafka import Consumer, Producer, KafkaException
from sklearn.ensemble import IsolationForest

BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
TOPIC = os.getenv("KAFKA_TOPIC", "orders")
ANOMALY_TOPIC = os.getenv("ANOMALY_TOPIC", "anomaly-orders")
GROUP_ID = os.getenv("GROUP_ID", "orders-ml-consumer")

WINDOW_SIZE = int(os.getenv("WINDOW_SIZE", "300"))
MIN_TRAIN_SIZE = int(os.getenv("MIN_TRAIN_SIZE", "50"))
RETRAIN_EVERY = int(os.getenv("RETRAIN_EVERY", "25"))
CONTAMINATION = float(os.getenv("CONTAMINATION", "0.05"))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "-0.02"))

class StreamingOrderAnomalyDetector:
    def __init__(self):
        self.window = deque(maxlen=WINDOW_SIZE)
        self.model = None
        self.message_count = 0

        self.region_map = {"US": 0, "CA": 1, "UK": 2, "DE": 3, "IN": 4}
        self.payment_map = {"card": 0, "paypal": 1, "wallet": 2, "bank_transfer": 3}

    def featurize(self, order):
        return np.array([
            float(order.get("amount", 0.0)),
            float(order.get("customer_id", 0)),
            float(order.get("quantity", 1)),
            float(self.region_map.get(order.get("region"), -1)),
            float(self.payment_map.get(order.get("payment_method"), -1)),
            1.0 if order.get("status") == "NEW" else 0.0,
        ], dtype=float)

    def maybe_train(self):
        if len(self.window) < MIN_TRAIN_SIZE:
            return

        if self.model is None or self.message_count % RETRAIN_EVERY == 0:
            X = np.array(self.window)
            self.model = IsolationForest(
                n_estimators=100,
                contamination=CONTAMINATION,
                random_state=42
            )
            self.model.fit(X)

    def score_order(self, order):
        x = self.featurize(order)

        if self.model is not None:
            score = float(self.model.decision_function([x])[0])
            is_anomaly = score < ANOMALY_THRESHOLD
        else:
            score = None
            is_anomaly = False

        self.window.append(x)
        self.message_count += 1
        self.maybe_train()

        return score, is_anomaly

def delivery_report(err, msg):
    if err is not None:
        print(f"[ERROR] anomaly publish failed for key={msg.key()}: {err}")
    else:
        print(f"[FORWARDED] {msg.topic()}[{msg.partition()}]@{msg.offset()}")

def main():
    consumer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "group.id": GROUP_ID,
        "auto.offset.reset": "earliest",
    }

    producer_conf = {
        "bootstrap.servers": BOOTSTRAP_SERVERS,
        "client.id": "orders-anomaly-forwarder",
    }

    consumer = Consumer(consumer_conf)
    producer = Producer(producer_conf)
    detector = StreamingOrderAnomalyDetector()

    consumer.subscribe([TOPIC])
    print(f"ML consumer subscribed to '{TOPIC}' and forwarding anomalies to '{ANOMALY_TOPIC}'")

    try:
        while True:
            msg = consumer.poll(1.0)
            producer.poll(0)

            if msg is None:
                continue
            if msg.error():
                raise KafkaException(msg.error())

            raw = msg.value().decode("utf-8") if msg.value() else ""
            key = msg.key().decode("utf-8") if msg.key() else ""

            try:
                order = json.loads(raw)
            except json.JSONDecodeError:
                print(f"[WARN] Invalid JSON: {raw}")
                continue

            score, is_anomaly = detector.score_order(order)

            if score is None:
                print(
                    f"[WARMUP] order_id={order.get('order_id')} "
                    f"customer_id={order.get('customer_id')} "
                    f"amount={order.get('amount')}"
                )
                continue

            if is_anomaly:
                anomaly_event = {
                    "detected_at": int(time.time()),
                    "source_topic": TOPIC,
                    "source_partition": msg.partition(),
                    "source_offset": msg.offset(),
                    "anomaly_score": score,
                    "anomaly_threshold": ANOMALY_THRESHOLD,
                    "order": order,
                }

                producer.produce(
                    ANOMALY_TOPIC,
                    key=key.encode("utf-8") if key else None,
                    value=json.dumps(anomaly_event).encode("utf-8"),
                    callback=delivery_report,
                )

                print(
                    f"[ALERT] forwarded anomalous order | "
                    f"order_id={order.get('order_id')} "
                    f"amount={order.get('amount')} "
                    f"score={score:.4f}"
                )
            else:
                print(
                    f"[OK] order_id={order.get('order_id')} "
                    f"amount={order.get('amount')} "
                    f"score={score:.4f}"
                )

    except KeyboardInterrupt:
        print("Stopping ML consumer.")
    finally:
        consumer.close()
        producer.flush()

if __name__ == "__main__":
    main()
