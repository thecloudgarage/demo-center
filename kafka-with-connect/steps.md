values-kafka.yaml
```
# Global defaults
global:
  storageClass: "local-path"   # k3s default storage class; change if you use another
  imagePullPolicy: IfNotPresent

cp-zookeeper:
  enabled: true
  servers: 3
  persistence:
    enabled: true
    storageClass: "local-path"
    size: 10Gi
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "1"
      memory: "2Gi"

cp-kafka:
  enabled: true
  brokers: 3
  persistence:
    enabled: true
    storageClass: "local-path"
    size: 50Gi
  resources:
    requests:
      cpu: "2"
      memory: "4Gi"
    limits:
      cpu: "4"
      memory: "8Gi"
  configurationOverrides:
    "offsets.topic.replication.factor": "3"
    "transaction.state.log.replication.factor": "3"
    "transaction.state.log.min.isr": "2"
    "default.replication.factor": "3"
    "min.insync.replicas": "2"
    "auto.create.topics.enable": "false"

cp-schema-registry:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: "500m"
      memory: "1Gi"
    limits:
      cpu: "1"
      memory: "2Gi"

cp-kafka-rest:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: "250m"
      memory: "512Mi"
    limits:
      cpu: "500m"
      memory: "1Gi"

cp-ksql-server:
  enabled: true
  replicas: 2
  resources:
    requests:
      cpu: "500m"
      memory: "2Gi"
    limits:
      cpu: "1"
      memory: "4Gi"
  configurationOverrides:
    "ksql.streams.replication.factor": "3"
    "ksql.sink.replicas": "3"

cp-kafka-connect:
  enabled: true
  replicaCount: 3
  image:
    repository: "your-registry.example.com/confluent/cp-kafka-connect-mongo-es"
    tag: "7.6.0"
    pullPolicy: IfNotPresent
  resources:
    requests:
      cpu: "1"
      memory: "2Gi"
    limits:
      cpu: "2"
      memory: "4Gi"
  configurationOverrides:
    "config.storage.replication.factor": "3"
    "offset.storage.replication.factor": "3"
    "status.storage.replication.factor": "3"
    "key.converter": "org.apache.kafka.connect.storage.StringConverter"
    "value.converter": "org.apache.kafka.connect.json.JsonConverter"
    "value.converter.schemas.enable": "false"
    "plugin.path": "/usr/share/java,/usr/share/confluent-hub-components"

cp-control-center:
  enabled: true
  replicas: 1
  service:
    type: LoadBalancer
    port: 9021
  resources:
    requests:
      cpu: "500m"
      memory: "2Gi"
    limits:
      cpu: "1"
      memory: "4Gi"

podDisruptionBudget:
  enabled: true
```
Install
```
helm repo add confluentinc https://confluentinc.github.io/cp-helm-charts/
helm repo update
helm install my-confluent confluentinc/cp-helm-charts -f values-k3s.yaml
```
Dockerfile for Kafka connect (mongo + elasticsearch)
```
FROM confluentinc/cp-kafka-connect:7.6.0

USER root

RUN confluent-hub install --no-prompt mongodb/kafka-connect-mongodb:1.13.0 && \
    confluent-hub install --no-prompt confluentinc/kafka-connect-elasticsearch:14.0.6

ENV CONNECT_PLUGIN_PATH=/usr/share/java,/usr/share/confluent-hub-components

USER appuser
```
mongodb connector json (mongo-sink.json)
```
{
  "name": "mongo-sink",
  "config": {
    "connector.class": "com.mongodb.kafka.connect.MongoSinkConnector",
    "tasks.max": "2",

    "topics": "orders",

    "connection.uri": "mongodb://MONGO_USER:MONGO_PASSWORD@mongodb.mongodb.svc.cluster.local:27017/?authSource=admin",
    "database": "orders_db",
    "collection": "orders_coll",

    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.json.JsonConverter",
    "value.converter.schemas.enable": "false",

    "writemodel.strategy": "com.mongodb.kafka.connect.sink.writemodel.strategy.ReplaceOneDefaultStrategy",
    "document.id.strategy": "com.mongodb.kafka.connect.sink.processor.id.strategy.BsonOidStrategy",

    "max.num.retries": "10",
    "retries.defer.timeout": "5000"
  }
}
```
elasticsearch sink connector (elastic-sink.json)
```
{
  "name": "es-sink",
  "config": {
    "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "2",
    "topics": "orders",

    "connection.url": "http://elasticsearch.elasticsearch.svc.cluster.local:9200",
    "connection.username": "ES_USER",
    "connection.password": "ES_PASSWORD",

    "type.name": "_doc",
    "key.ignore": "true",
    "schema.ignore": "true",

    "auto.create.indices.at.start": "true",

    "behavior.on.malformed.documents": "warn",
    "behavior.on.null.values": "delete",
    "write.method": "insert",
    "max.in.flight.requests": "5",
    "batch.size": "2000",
    "max.buffered.records": "20000"
  }
}
```
create the connectors
```
CONNECT_URL=http://my-confluent-cp-kafka-connect:8083  # service in the Connect namespace

curl -X POST "$CONNECT_URL/connectors" \
  -H "Content-Type: application/json" \
  -d @mongo-sink.json

curl -X POST "$CONNECT_URL/connectors" \
  -H "Content-Type: application/json" \
  -d @es-sink.json
```
consumer app (consumer.py)
```
#!/usr/bin/env python3
import os
from confluent_kafka import Consumer, KafkaException

BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS", "my-confluent-cp-kafka-headless:9092")
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
dockerfile for consumer app
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
build and push the consumer app
```
kubernetes manifest for consumer app
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-consumer
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: orders-consumer
  template:
    metadata:
      labels:
        app: orders-consumer
    spec:
      containers:
        - name: orders-consumer
          image: your-registry.example.com/orders-consumer:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: BOOTSTRAP_SERVERS
              value: "my-confluent-cp-kafka-headless:9092"
            - name: KAFKA_TOPIC
              value: "orders"
            - name: GROUP_ID
              value: "orders-cli-consumer"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```
producer app (producer.py)
```
#!/usr/bin/env python3
import os
import json
import time
import uuid
from random import randint, uniform
from confluent_kafka import Producer

BOOTSTRAP_SERVERS = os.getenv("BOOTSTRAP_SERVERS", "my-confluent-cp-kafka-headless:9092")
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
dockerfile for producer app
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
build and push the producer app
```
docker build -t your-registry.example.com/orders-producer:latest .
docker push your-registry.example.com/orders-producer:latest
```
kubernetes manifest for the producer app
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-producer
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: orders-producer
  template:
    metadata:
      labels:
        app: orders-producer
    spec:
      containers:
        - name: orders-producer
          image: your-registry.example.com/orders-producer:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: BOOTSTRAP_SERVERS
              value: "my-confluent-cp-kafka-headless:9092"
            - name: KAFKA_TOPIC
              value: "orders"
            - name: INTERVAL_SECONDS
              value: "1.0"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```
Observe via control center
```
Open http://<control-center-external-ip>:9021 in a browser.
Go to the ksqlDB section.
Select the cp-ksql-server cluster and use the SQL editor there to run ksqlDB queries.
```
register the orders stream (json example)
```
CREATE STREAM ORDERS_STREAM (
  order_id    STRING,
  customer_id INT,
  amount      DOUBLE,
  currency    STRING,
  status      STRING,
  event_ts    BIGINT
) WITH (
  KAFKA_TOPIC = 'orders',
  VALUE_FORMAT = 'JSON',
  TIMESTAMP = 'event_ts'
);
```
inspect live orders
```
SELECT * FROM ORDERS_STREAM EMIT CHANGES LIMIT 10;
```
filter only paid orders
```
CREATE STREAM ORDERS_PAID AS
  SELECT *
  FROM ORDERS_STREAM
  WHERE status = 'PAID'
  EMIT CHANGES;
```
This creates a new Kafka topic (by default ORDERS_PAID) that you can sink separately if desired.
Next we can create a hourly revenue per customer (table)
```
CREATE TABLE HOURLY_REVENUE_PER_CUSTOMER AS
  SELECT
    customer_id,
    WINDOWSTART AS window_start,
    WINDOWEND   AS window_end,
    SUM(amount) AS total_amount,
    COUNT(*)    AS order_count
  FROM ORDERS_STREAM
  WINDOW TUMBLING (SIZE 1 HOUR)
  GROUP BY customer_id
  EMIT CHANGES;
```
simple large order stream
```
CREATE STREAM LARGE_ORDERS AS
  SELECT *
  FROM ORDERS_STREAM
  WHERE amount > 250.0
  EMIT CHANGES;
```
