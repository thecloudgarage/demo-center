```
kubectl create namespace confluent 2>/dev/null || true
kubectl config set-context --current --namespace=confluent

helm repo remove confluentinc 2>/dev/null || true
helm repo add confluentinc https://packages.confluent.io/helm
helm repo update
helm search repo confluentinc/confluent-for-kubernetes --versions

helm upgrade --install confluent-operator \
  confluentinc/confluent-for-kubernetes \
  --namespace confluent \
  --create-namespace
```
```
apiVersion: platform.confluent.io/v1beta1
kind: KRaftController
metadata:
  name: kraftcontroller
  namespace: confluent
spec:
  replicas: 3
  image:
    application: confluentinc/cp-server:8.2.0
    init: confluentinc/confluent-init-container:3.2.0
  dataVolumeCapacity: 2Gi
  storageClass:
    name: longhorn
  podTemplate:
    resources:
      requests:
        cpu: "500m"
        memory: "1Gi"
      limits:
        cpu: "1"
        memory: "2Gi"

---
apiVersion: platform.confluent.io/v1beta1
kind: Kafka
metadata:
  name: kafka
  namespace: confluent
spec:
  replicas: 3
  image:
    application: confluentinc/cp-server:8.2.0
    init: confluentinc/confluent-init-container:3.2.0
  dependencies:
    kRaftController:
      clusterRef:
        name: kraftcontroller
        namespace: confluent
  dataVolumeCapacity: 1Gi
  storageClass:
    name: longhorn
  podTemplate:
    resources:
      requests:
        cpu: "1"
        memory: "1Gi"
      limits:
        cpu: "2"
        memory: "2Gi"
  configOverrides:
    server:
      - offsets.topic.replication.factor=3
      - transaction.state.log.replication.factor=3
      - transaction.state.log.min.isr=2
      - default.replication.factor=3
      - min.insync.replicas=2
      - auto.create.topics.enable=false

---
apiVersion: platform.confluent.io/v1beta1
kind: SchemaRegistry
metadata:
  name: schemaregistry
  namespace: confluent
spec:
  replicas: 2
  image:
    application: confluentinc/cp-schema-registry:8.2.0
    init: confluentinc/confluent-init-container:3.2.0
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9071
  podTemplate:
    resources:
      requests:
        cpu: "500m"
        memory: "512Mi"
      limits:
        cpu: "1"
        memory: "1Gi"

---
apiVersion: platform.confluent.io/v1beta1
kind: KafkaRestProxy
metadata:
  name: kafkarestproxy
  namespace: confluent
spec:
  replicas: 2
  image:
    application: confluentinc/cp-kafka-rest:8.2.0
    init: confluentinc/confluent-init-container:3.2.0
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9071
  podTemplate:
    resources:
      requests:
        cpu: "250m"
        memory: "512Mi"
      limits:
        cpu: "500m"
        memory: "1Gi"

---
apiVersion: platform.confluent.io/v1beta1
kind: KsqlDB
metadata:
  name: ksqldb
  namespace: confluent
spec:
  replicas: 2
  image:
    application: confluentinc/cp-ksqldb-server:8.2.0
    init: confluentinc/confluent-init-container:3.2.0
  dataVolumeCapacity: 1Gi
  storageClass:
    name: longhorn
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9071
  podTemplate:
    resources:
      requests:
        cpu: "500m"
        memory: "512Mi"
      limits:
        cpu: "1"
        memory: "1Gi"
  configOverrides:
    server:
      - ksql.streams.replication.factor=3
      - ksql.sink.replicas=3
      - ksql.internal.topic.replicas=3

---
apiVersion: platform.confluent.io/v1beta1
kind: Connect
metadata:
  name: connect
  namespace: confluent
spec:
  replicas: 3
  image:
    application: thecloudgarage/cp-kafka-connect-mongo-es:latest
    init: confluentinc/confluent-init-container:3.2.0
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9071
  externalAccess:
  type: loadBalancer
  loadBalancer:
    domain: kafkaconnect.example.com
  podTemplate:
    resources:
      requests:
        cpu: "1"
        memory: "512Mi"
      limits:
        cpu: "2"
        memory: "1Gi"
  configOverrides:
    server:
      - config.storage.replication.factor=3
      - offset.storage.replication.factor=3
      - status.storage.replication.factor=3
      - key.converter=org.apache.kafka.connect.storage.StringConverter
      - value.converter=org.apache.kafka.connect.json.JsonConverter
      - value.converter.schemas.enable=false
      - plugin.path=/usr/share/java,/usr/share/confluent-hub-components

---
apiVersion: platform.confluent.io/v1beta1
kind: ControlCenter
metadata:
  name: controlcenter
  namespace: confluent
spec:
  replicas: 1
  image:
    application: confluentinc/cp-enterprise-control-center-next-gen:latest
    init: confluentinc/confluent-init-container:3.2.0
  dataVolumeCapacity: 1Gi
  storageClass:
    name: longhorn
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9071
  podTemplate:
    resources:
      requests:
        cpu: "500m"
        memory: "512Mi"
      limits:
        cpu: "1"
        memory: "1Gi"
```
```
kubectl apply -f cfk-kraft-latest.yaml
kubectl get pods -n confluent -w
```
MongoDB connector JSON
```
cat > mongo-sink.json <<EOF
{
  "name": "mongo-sink",
  "config": {
    "connector.class": "com.mongodb.kafka.connect.MongoSinkConnector",
    "tasks.max": "2",

    "topics": "orders",

    "connection.uri": "mongodb://mongo_user:mongo_password@mongodb.mongodb.svc.cluster.local:27017/?authSource=admin",
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
EOF
```
ElasticSearch connector JSON
```
ES_CLUSTER_NAME=$(kubectl get elasticsearch -n elasticsearch single-es \
  -o jsonpath='{.metadata.name}{"\n"}')
ES_PW=$(
  kubectl -n elasticsearch get secret "${ES_CLUSTER_NAME}-es-elastic-user" \
    -o go-template='{{.data.elastic | base64decode}}{{"\n"}}'
)
ES_SERVICE_HOST=$(kubectl -n elasticsearch get svc "${ES_CLUSTER_NAME}-coord" \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'; echo)

```
```
cat > es-sink.json <<EOF
{
  "name": "es-sink",
  "config": {
    "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "2",
    "topics": "orders",
    "connection.url": "https://elasticsearch.$ES_SERVICE_HOST.svc.cluster.local:9200",
    "connection.username": "elastic",
    "connection.password": "$ES_PW",
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
EOF
```
Post the connectors
```
CONNECT_URL=http://kafkaconnect.example.com  # service in the Connect namespace

curl -X POST "$CONNECT_URL/connectors" \
  -H "Content-Type: application/json" \
  -d @mongo-sink.json
```
Consumer app
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
Consumer app dockerfile
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
curl -X POST "$CONNECT_URL/connectors" \
  -H "Content-Type: application/json" \
  -d @es-sink.json
```
Consumer app deployment
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
Producer app
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
Producer app dockerfile
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
Producer app deployment
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
