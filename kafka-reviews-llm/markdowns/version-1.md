
# Product Platform Monorepo

This file contains the full starter monorepo as a single markdown document.

---

## `README.md`

```md
# product-platform

End-to-end product review pipeline on K3s.

## Components

- `product_seeder` -> creates 500 products in Elasticsearch `products`
- `review_producer` -> emits fake reviews to Kafka `product-reviews`
- Kafka Connect Elasticsearch sink -> writes raw reviews to Elasticsearch `product_reviews`
- `ratings_aggregator` -> per-minute rating average updater into `products`
- `review_batch_aggregator` -> batches reviews and sends to Kafka `product-review-batches`
- `kafka_rabbitmq_relay` -> forwards batches to RabbitMQ
- `llm_summarizer_worker` -> summarizes review batches and stores output in Redis
- `recommendation_service` -> computes top-3 products per category and stores in Redis
- `product_api` -> serves frontend data from Elasticsearch + Redis
- `frontend` -> SPA UI

## Repo layout

product-platform/
- README.md
- .env.example
- Makefile
- scripts/create-topics.sh
- services/common/
- services/product_seeder/
- services/review_producer/
- services/ratings_aggregator/
- services/review_batch_aggregator/
- services/kafka_rabbitmq_relay/
- services/llm_summarizer_worker/
- services/recommendation_service/
- services/product_api/
- web/frontend/
- infra/kafka/
- infra/k8s/

## Build images

```bash
make build
```

## Create Kafka topics

```bash
export KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.svc.cluster.local:9092
./scripts/create-topics.sh
```

## Deploy

```bash
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/messaging.yaml
kubectl apply -f infra/k8s/config.yaml
kubectl apply -f infra/kafka/product-reviews-es-sink.yaml
kubectl apply -f infra/k8s/product-seeder-job.yaml
kubectl apply -f infra/k8s/review-producer.yaml
kubectl apply -f infra/k8s/ratings-aggregator.yaml
kubectl apply -f infra/k8s/review-batch-aggregator.yaml
kubectl apply -f infra/k8s/kafka-rabbitmq-relay.yaml
kubectl apply -f infra/k8s/llm-summarizer-worker.yaml
kubectl apply -f infra/k8s/recommendation-service.yaml
kubectl apply -f infra/k8s/product-api.yaml
kubectl apply -f infra/k8s/frontend.yaml
kubectl apply -f infra/k8s/ingress.yaml
```

## Notes

- Assumes Kafka, Connect, Elasticsearch, and Kibana already exist.
- RabbitMQ and Redis manifests are included here.
- For real LLM use, set `USE_FAKE_LLM=false` and provide `OPENAI_API_KEY`.
```

---

## `.env.example`

```env
KAFKA_BOOTSTRAP_SERVERS=kafka.confluent.svc.cluster.local:9092
ELASTICSEARCH_URL=http://single-es-coord.elasticsearch.svc.cluster.local:9200
REDIS_URL=redis://redis.messaging.svc.cluster.local:6379/0
RABBITMQ_HOST=rabbitmq.messaging.svc.cluster.local
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

PRODUCTS_INDEX=products
REVIEWS_INDEX=product_reviews

TOPIC_PRODUCT_REVIEWS=product-reviews
TOPIC_PRODUCT_REVIEW_BATCHES=product-review-batches
TOPIC_PRODUCT_REVIEW_DLQ=product-review-dlq
TOPIC_PRODUCT_REVIEW_BATCHES_DLQ=product-review-batches-dlq

QUEUE_REVIEW_SUMMARIZATION=review_summarization_jobs

PRODUCT_COUNT=500
PRODUCE_INTERVAL_SECONDS=1
WINDOW_SECONDS=60
MAX_BATCH_SIZE=20

API_PORT=8080

USE_FAKE_LLM=true
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

---

## `Makefile`

```make
SERVICES=product_seeder review_producer ratings_aggregator review_batch_aggregator kafka_rabbitmq_relay llm_summarizer_worker recommendation_service product_api

build:
	docker build -f services/product_seeder/Dockerfile -t product_seeder:latest .
	docker build -f services/review_producer/Dockerfile -t review_producer:latest .
	docker build -f services/ratings_aggregator/Dockerfile -t ratings_aggregator:latest .
	docker build -f services/review_batch_aggregator/Dockerfile -t review_batch_aggregator:latest .
	docker build -f services/kafka_rabbitmq_relay/Dockerfile -t kafka_rabbitmq_relay:latest .
	docker build -f services/llm_summarizer_worker/Dockerfile -t llm_summarizer_worker:latest .
	docker build -f services/recommendation_service/Dockerfile -t recommendation_service:latest .
	docker build -f services/product_api/Dockerfile -t product_api:latest .
	docker build -f web/frontend/Dockerfile -t frontend:latest .

topics:
	chmod +x scripts/create-topics.sh
	./scripts/create-topics.sh
```

---

## `scripts/create-topics.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

BOOTSTRAP="${KAFKA_BOOTSTRAP_SERVERS:-kafka.confluent.svc.cluster.local:9092}"

POD=$(kubectl -n confluent get pods -l app=kafka -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)
if [ -z "${POD}" ]; then
  POD=$(kubectl -n confluent get pods | awk '/kafka-/{print $1; exit}')
fi

if [ -z "${POD}" ]; then
  echo "Could not find Kafka broker pod in namespace confluent"
  exit 1
fi

kubectl -n confluent exec -it "${POD}" -- bash -lc "
kafka-topics --bootstrap-server ${BOOTSTRAP} --create --if-not-exists --topic product-reviews --partitions 6 --replication-factor 3
kafka-topics --bootstrap-server ${BOOTSTRAP} --create --if-not-exists --topic product-review-batches --partitions 6 --replication-factor 3
kafka-topics --bootstrap-server ${BOOTSTRAP} --create --if-not-exists --topic product-review-dlq --partitions 3 --replication-factor 3
kafka-topics --bootstrap-server ${BOOTSTRAP} --create --if-not-exists --topic product-review-batches-dlq --partitions 3 --replication-factor 3
"
```

---

# Shared code

## `services/common/__init__.py`

```python
# common package
```

## `services/common/utils.py`

```python
import json
import logging
import math
import os
import random
import string
from datetime import datetime, timezone
from typing import Any, Dict, List

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

def logger(name: str):
    return logging.getLogger(name)

def env(name: str, default=None, required: bool = False):
    value = os.getenv(name, default)
    if required and value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def rand_id(prefix: str, n: int = 8) -> str:
    chars = string.ascii_lowercase + string.digits
    return f"{prefix}-" + "".join(random.choices(chars, k=n))

def to_json_bytes(value: Dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")

def from_json_bytes(value: bytes) -> Dict[str, Any]:
    return json.loads(value.decode("utf-8"))

CATEGORIES: List[str] = [
    "Laptops",
    "Monitors",
    "Servers",
    "Storage",
    "Accessories",
    "Networking",
    "Desktops",
    "Tablets",
]

ADJECTIVES = ["Ultra", "Pro", "Prime", "Max", "Edge", "Eco", "Flex", "Smart"]
NOUNS = ["Display", "Notebook", "Station", "Array", "Dock", "Hub", "Panel", "Node"]

REVIEW_TITLES = [
    "Excellent overall",
    "Solid value",
    "Good but not perfect",
    "Mixed experience",
    "Highly recommended",
    "Needs improvement",
]

REVIEW_TEXTS = [
    "Excellent performance and very reliable.",
    "Good value for the price and easy to use.",
    "Strong build quality and consistent day to day usage.",
    "I like the features, but setup could be simpler.",
    "Great performance, though thermals could be better.",
    "Stable under load and fits well into the current environment.",
    "User experience is clean, but updates could be smoother.",
    "Exceeded expectations for the price point.",
    "Not bad overall, but support documentation could improve.",
    "Fast deployment and solid performance in production-like tests."
]

def fake_product(i: int) -> Dict[str, Any]:
    category = random.choice(CATEGORIES)
    name = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)} {i}"
    return {
        "product_id": f"P-{i:04d}",
        "name": name,
        "category": category,
        "brand": "Dell",
        "price": round(random.uniform(49.0, 3999.0), 2),
        "description": f"Synthetic {category} product {i}",
        "avg_rating": 0.0,
        "rating_count": 0,
        "rating_sum": 0.0,
        "updated_at": now_iso(),
    }

def fake_review(product: Dict[str, Any]) -> Dict[str, Any]:
    rating = random.choices([1, 2, 3, 4, 5], weights=[0.06, 0.10, 0.19, 0.32, 0.33], k=1)[0]
    return {
        "review_id": rand_id("R"),
        "product_id": product["product_id"],
        "category": product["category"],
        "rating": rating,
        "review_title": random.choice(REVIEW_TITLES),
        "review_text": random.choice(REVIEW_TEXTS),
        "reviewer_alias": rand_id("user", 5),
        "event_ts": now_iso(),
    }

def compute_score(avg_rating: float, rating_count: int) -> float:
    return (avg_rating * 0.8) + (math.log10(rating_count + 1) * 0.2)
```

---

# Product seeder

## `services/product_seeder/requirements.txt`

```txt
elasticsearch==8.13.2
```

## `services/product_seeder/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/product_seeder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/product_seeder/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/product_seeder/main.py`

```python
from elasticsearch import Elasticsearch, helpers
from common.utils import env, fake_product, logger

log = logger("product_seeder")

ES_URL = env("ELASTICSEARCH_URL", required=True)
PRODUCTS_INDEX = env("PRODUCTS_INDEX", "products")
COUNT = int(env("PRODUCT_COUNT", "500"))

def ensure_products_index(es: Elasticsearch):
    if es.indices.exists(index=PRODUCTS_INDEX):
        log.info("Index %s already exists", PRODUCTS_INDEX)
        return

    es.indices.create(
        index=PRODUCTS_INDEX,
        mappings={
            "properties": {
                "product_id": {"type": "keyword"},
                "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
                "category": {"type": "keyword"},
                "brand": {"type": "keyword"},
                "price": {"type": "float"},
                "description": {"type": "text"},
                "avg_rating": {"type": "float"},
                "rating_count": {"type": "integer"},
                "rating_sum": {"type": "float"},
                "updated_at": {"type": "date"},
            }
        }
    )
    log.info("Created index %s", PRODUCTS_INDEX)

def main():
    es = Elasticsearch(ES_URL)
    ensure_products_index(es)

    actions = []
    for i in range(1, COUNT + 1):
        product = fake_product(i)
        actions.append({
            "_index": PRODUCTS_INDEX,
            "_id": product["product_id"],
            "_source": product,
        })

    success, _ = helpers.bulk(es, actions, refresh="wait_for")
    log.info("Seeded %s products", success)

if __name__ == "__main__":
    main()
```

---

# Review producer

## `services/review_producer/requirements.txt`

```txt
elasticsearch==8.13.2
kafka-python==2.0.2
```

## `services/review_producer/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/review_producer/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/review_producer/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/review_producer/main.py`

```python
import random
import time
from elasticsearch import Elasticsearch
from kafka import KafkaProducer
from common.utils import env, fake_review, logger, to_json_bytes

log = logger("review_producer")

ES_URL = env("ELASTICSEARCH_URL", required=True)
PRODUCTS_INDEX = env("PRODUCTS_INDEX", "products")
BOOTSTRAP = env("KAFKA_BOOTSTRAP_SERVERS", required=True)
TOPIC = env("TOPIC_PRODUCT_REVIEWS", "product-reviews")
INTERVAL = float(env("PRODUCE_INTERVAL_SECONDS", "1"))

def load_products(es: Elasticsearch):
    res = es.search(index=PRODUCTS_INDEX, size=1000, query={"match_all": {}})
    return [hit["_source"] for hit in res["hits"]["hits"]]

def main():
    es = Elasticsearch(ES_URL)
    products = load_products(es)
    if not products:
        raise RuntimeError("No products found. Run product_seeder first.")

    producer = KafkaProducer(
        bootstrap_servers=BOOTSTRAP,
        key_serializer=lambda k: k.encode("utf-8"),
        value_serializer=lambda v: to_json_bytes(v),
        acks="all",
        retries=5,
    )

    while True:
        product = random.choice(products)
        review = fake_review(product)
        producer.send(TOPIC, key=review["product_id"], value=review)
        producer.flush()
        log.info("Produced review_id=%s product_id=%s rating=%s", review["review_id"], review["product_id"], review["rating"])
        time.sleep(INTERVAL)

if __name__ == "__main__":
    main()
```

---

# Ratings aggregator

## `services/ratings_aggregator/requirements.txt`

```txt
elasticsearch==8.13.2
kafka-python==2.0.2
```

## `services/ratings_aggregator/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/ratings_aggregator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/ratings_aggregator/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/ratings_aggregator/main.py`

```python
import time
from collections import defaultdict
from kafka import KafkaConsumer
from elasticsearch import Elasticsearch
from common.utils import env, from_json_bytes, logger, now_iso

log = logger("ratings_aggregator")

BOOTSTRAP = env("KAFKA_BOOTSTRAP_SERVERS", required=True)
TOPIC = env("TOPIC_PRODUCT_REVIEWS", "product-reviews")
GROUP_ID = env("GROUP_ID", "ratings-aggregator")
ES_URL = env("ELASTICSEARCH_URL", required=True)
PRODUCTS_INDEX = env("PRODUCTS_INDEX", "products")
WINDOW_SECONDS = int(env("WINDOW_SECONDS", "60"))

def flush_batch(es: Elasticsearch, batch):
    for product_id, stats in batch.items():
        es.update(
            index=PRODUCTS_INDEX,
            id=product_id,
            scripted_upsert=True,
            script={
                "source": """
                    if (ctx._source.rating_sum == null) { ctx._source.rating_sum = 0.0; }
                    if (ctx._source.rating_count == null) { ctx._source.rating_count = 0; }
                    ctx._source.rating_sum += params.rating_sum;
                    ctx._source.rating_count += params.rating_count;
                    ctx._source.avg_rating = ctx._source.rating_sum / ctx._source.rating_count;
                    ctx._source.updated_at = params.updated_at;
                """,
                "params": {
                    "rating_sum": stats["rating_sum"],
                    "rating_count": stats["rating_count"],
                    "updated_at": now_iso(),
                },
            },
            upsert={
                "product_id": product_id,
                "avg_rating": stats["rating_sum"] / max(stats["rating_count"], 1),
                "rating_sum": stats["rating_sum"],
                "rating_count": stats["rating_count"],
                "updated_at": now_iso(),
            }
        )
    log.info("Flushed %s product aggregates", len(batch))

def main():
    es = Elasticsearch(ES_URL)
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        enable_auto_commit=False,
        auto_offset_reset="earliest",
        value_deserializer=from_json_bytes,
    )

    batch = defaultdict(lambda: {"rating_sum": 0.0, "rating_count": 0})
    window_start = time.time()

    while True:
        records = consumer.poll(timeout_ms=1000)
        for _, messages in records.items():
            for msg in messages:
                review = msg.value
                product_id = review["product_id"]
                batch[product_id]["rating_sum"] += float(review["rating"])
                batch[product_id]["rating_count"] += 1

        if time.time() - window_start >= WINDOW_SECONDS and batch:
            flush_batch(es, batch)
            consumer.commit()
            batch.clear()
            window_start = time.time()

if __name__ == "__main__":
    main()
```

---

# Review batch aggregator

## `services/review_batch_aggregator/requirements.txt`

```txt
kafka-python==2.0.2
```

## `services/review_batch_aggregator/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/review_batch_aggregator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/review_batch_aggregator/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/review_batch_aggregator/main.py`

```python
import json
import time
from collections import defaultdict
from kafka import KafkaConsumer, KafkaProducer
from common.utils import env, from_json_bytes, logger, now_iso

log = logger("review_batch_aggregator")

BOOTSTRAP = env("KAFKA_BOOTSTRAP_SERVERS", required=True)
IN_TOPIC = env("TOPIC_PRODUCT_REVIEWS", "product-reviews")
OUT_TOPIC = env("TOPIC_PRODUCT_REVIEW_BATCHES", "product-review-batches")
GROUP_ID = env("GROUP_ID", "review-batch-aggregator")
WINDOW_SECONDS = int(env("WINDOW_SECONDS", "60"))
MAX_BATCH_SIZE = int(env("MAX_BATCH_SIZE", "20"))

def emit_batches(producer: KafkaProducer, grouped):
    for product_id, reviews in grouped.items():
        if not reviews:
            continue
        payload = {
            "product_id": product_id,
            "category": reviews[0]["category"],
            "window_closed_at": now_iso(),
            "review_count": len(reviews),
            "reviews": reviews,
        }
        producer.send(
            OUT_TOPIC,
            key=product_id.encode("utf-8"),
            value=json.dumps(payload).encode("utf-8")
        )
    producer.flush()

def main():
    consumer = KafkaConsumer(
        IN_TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=from_json_bytes,
    )
    producer = KafkaProducer(bootstrap_servers=BOOTSTRAP, acks="all", retries=5)

    grouped = defaultdict(list)
    started = time.time()

    while True:
        records = consumer.poll(timeout_ms=1000)
        for _, messages in records.items():
            for msg in messages:
                review = msg.value
                grouped[review["product_id"]].append(review)

        flush_due_time = (time.time() - started) >= WINDOW_SECONDS
        flush_due_size = any(len(v) >= MAX_BATCH_SIZE for v in grouped.values())

        if grouped and (flush_due_time or flush_due_size):
            emit_batches(producer, grouped)
            consumer.commit()
            log.info("Emitted %s review batches", len(grouped))
            grouped.clear()
            started = time.time()

if __name__ == "__main__":
    main()
```

---

# Kafka to RabbitMQ relay

## `services/kafka_rabbitmq_relay/requirements.txt`

```txt
kafka-python==2.0.2
pika==1.3.2
```

## `services/kafka_rabbitmq_relay/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/kafka_rabbitmq_relay/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/kafka_rabbitmq_relay/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/kafka_rabbitmq_relay/main.py`

```python
import json
import pika
from kafka import KafkaConsumer
from common.utils import env, from_json_bytes, logger

log = logger("kafka_rabbitmq_relay")

BOOTSTRAP = env("KAFKA_BOOTSTRAP_SERVERS", required=True)
TOPIC = env("TOPIC_PRODUCT_REVIEW_BATCHES", "product-review-batches")
GROUP_ID = env("GROUP_ID", "kafka-rabbitmq-relay")

RABBITMQ_HOST = env("RABBITMQ_HOST", required=True)
RABBITMQ_PORT = int(env("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = env("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = env("RABBITMQ_PASSWORD", "guest")
QUEUE = env("QUEUE_REVIEW_SUMMARIZATION", "review_summarization_jobs")

def open_rabbit():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    conn = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
    )
    channel = conn.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    return conn, channel

def main():
    conn, ch = open_rabbit()
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=False,
        value_deserializer=from_json_bytes,
    )

    while True:
        records = consumer.poll(timeout_ms=1000)
        for _, messages in records.items():
            for msg in messages:
                body = json.dumps(msg.value).encode("utf-8")
                ch.basic_publish(
                    exchange="",
                    routing_key=QUEUE,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),
                )
                log.info("Forwarded product batch for product_id=%s", msg.value["product_id"])
        consumer.commit()

if __name__ == "__main__":
    main()
```

---

# LLM summarizer worker

## `services/llm_summarizer_worker/requirements.txt`

```txt
pika==1.3.2
redis==5.0.4
openai==1.30.1
```

## `services/llm_summarizer_worker/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/llm_summarizer_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/llm_summarizer_worker/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/llm_summarizer_worker/main.py`

```python
import json
import pika
import redis
from common.utils import env, logger, now_iso

log = logger("llm_summarizer_worker")

RABBITMQ_HOST = env("RABBITMQ_HOST", required=True)
RABBITMQ_PORT = int(env("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = env("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = env("RABBITMQ_PASSWORD", "guest")
QUEUE = env("QUEUE_REVIEW_SUMMARIZATION", "review_summarization_jobs")

REDIS_URL = env("REDIS_URL", required=True)

USE_FAKE_LLM = env("USE_FAKE_LLM", "true").lower() == "true"
OPENAI_API_KEY = env("OPENAI_API_KEY", "")
OPENAI_MODEL = env("OPENAI_MODEL", "gpt-4o-mini")

r = redis.from_url(REDIS_URL, decode_responses=True)

def summarize_fake(reviews):
    positives = [rv["review_text"] for rv in reviews if rv["rating"] >= 4][:3]
    negatives = [rv["review_text"] for rv in reviews if rv["rating"] <= 2][:3]
    avg = sum(float(r["rating"]) for r in reviews) / max(len(reviews), 1)

    return {
        "summary": f"Average rating is {avg:.2f}/5 based on {len(reviews)} reviews.",
        "highlights": positives,
        "concerns": negatives,
    }

def summarize_llm(reviews):
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    prompt = (
        "Summarize these product reviews as JSON with keys: summary, highlights, concerns.\n"
        f"Reviews: {json.dumps(reviews)}"
    )
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    text = response.choices[0].message.content
    try:
        return json.loads(text)
    except Exception:
        return {"summary": text, "highlights": [], "concerns": []}

def callback(ch, method, properties, body):
    payload = json.loads(body.decode("utf-8"))
    product_id = payload["product_id"]
    reviews = payload["reviews"]

    result = summarize_fake(reviews) if USE_FAKE_LLM else summarize_llm(reviews)

    stored = {
        "product_id": product_id,
        "category": payload["category"],
        "review_count": len(reviews),
        "generated_at": now_iso(),
        "summary": result.get("summary"),
        "highlights": result.get("highlights", []),
        "concerns": result.get("concerns", []),
    }

    r.set(f"summary:{product_id}", json.dumps(stored))
    ch.basic_ack(delivery_tag=method.delivery_tag)
    log.info("Stored summary for product_id=%s", product_id)

def main():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, credentials=credentials)
    )
    channel = connection.channel()
    channel.queue_declare(queue=QUEUE, durable=True)
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=QUEUE, on_message_callback=callback)
    log.info("Waiting for summarization jobs")
    channel.start_consuming()

if __name__ == "__main__":
    main()
```

---

# Recommendation service

## `services/recommendation_service/requirements.txt`

```txt
kafka-python==2.0.2
redis==5.0.4
```

## `services/recommendation_service/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/recommendation_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/recommendation_service/main.py /app/main.py
CMD ["python", "main.py"]
```

## `services/recommendation_service/main.py`

```python
import json
import redis
from kafka import KafkaConsumer
from common.utils import compute_score, env, from_json_bytes, logger

log = logger("recommendation_service")

BOOTSTRAP = env("KAFKA_BOOTSTRAP_SERVERS", required=True)
TOPIC = env("TOPIC_PRODUCT_REVIEWS", "product-reviews")
GROUP_ID = env("GROUP_ID", "recommendation-service")
REDIS_URL = env("REDIS_URL", required=True)

r = redis.from_url(REDIS_URL, decode_responses=True)

def trim_top3(zkey: str):
    card = r.zcard(zkey)
    if card > 3:
        r.zremrangebyrank(zkey, 0, card - 4)

def update_score(review):
    product_id = review["product_id"]
    category = review["category"]
    rating = float(review["rating"])

    stats_key = f"stats:{product_id}"
    r.hincrbyfloat(stats_key, "rating_sum", rating)
    r.hincrby(stats_key, "rating_count", 1)
    r.hset(stats_key, "category", category)

    stats = r.hgetall(stats_key)
    rating_sum = float(stats.get("rating_sum", 0))
    rating_count = int(stats.get("rating_count", 0))
    avg_rating = rating_sum / max(rating_count, 1)

    score = compute_score(avg_rating, rating_count)

    zkey = f"top3:{category}"
    r.zadd(zkey, {product_id: score})
    trim_top3(zkey)

    log.info("Updated top3 for category=%s product_id=%s score=%.4f", category, product_id, score)

def main():
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        group_id=GROUP_ID,
        auto_offset_reset="earliest",
        enable_auto_commit=True,
        value_deserializer=from_json_bytes,
    )

    for msg in consumer:
        review = msg.value
        update_score(review)

if __name__ == "__main__":
    main()
```

---

# Product API

## `services/product_api/requirements.txt`

```txt
fastapi==0.111.0
uvicorn==0.30.0
elasticsearch==8.13.2
redis==5.0.4
```

## `services/product_api/Dockerfile`

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY services/product_api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/common /app/common
COPY services/product_api/main.py /app/main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## `services/product_api/main.py`

```python
import json
from fastapi import FastAPI, HTTPException
from elasticsearch import Elasticsearch
import redis
from common.utils import env

app = FastAPI(title="product-api")

ES = Elasticsearch(env("ELASTICSEARCH_URL", required=True))
REDIS = redis.from_url(env("REDIS_URL", required=True), decode_responses=True)
PRODUCTS_INDEX = env("PRODUCTS_INDEX", "products")
REVIEWS_INDEX = env("REVIEWS_INDEX", "product_reviews")

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/api/categories")
def categories():
    res = ES.search(
        index=PRODUCTS_INDEX,
        size=0,
        aggs={"categories": {"terms": {"field": "category", "size": 100}}}
    )
    return [bucket["key"] for bucket in res["aggregations"]["categories"]["buckets"]]

@app.get("/api/categories/top3")
def top3_by_category():
    cats = categories()
    out = {}
    for category in cats:
        rows = REDIS.zrevrange(f"top3:{category}", 0, 2, withscores=True)
        out[category] = [{"product_id": row[0], "score": row[1]} for row in rows]
    return out

@app.get("/api/categories/{category}/products")
def products_by_category(category: str):
    res = ES.search(
        index=PRODUCTS_INDEX,
        size=500,
        sort=[{"avg_rating": "desc"}],
        query={"term": {"category": category}},
    )
    return [hit["_source"] for hit in res["hits"]["hits"]]

@app.get("/api/products/{product_id}")
def product(product_id: str):
    try:
        return ES.get(index=PRODUCTS_INDEX, id=product_id)["_source"]
    except Exception:
        raise HTTPException(status_code=404, detail="Product not found")

@app.get("/api/products/{product_id}/reviews")
def product_reviews(product_id: str):
    res = ES.search(
        index=REVIEWS_INDEX,
        size=100,
        sort=[{"event_ts": "desc"}],
        query={"term": {"product_id": product_id}},
    )
    return [hit["_source"] for hit in res["hits"]["hits"]]

@app.get("/api/products/{product_id}/summary")
def product_summary(product_id: str):
    raw = REDIS.get(f"summary:{product_id}")
    if not raw:
        return {"product_id": product_id, "summary": None, "highlights": [], "concerns": []}
    return json.loads(raw)
```

---

# Frontend

## `web/frontend/package.json`

```json
{
  "name": "product-frontend",
  "private": true,
  "version": "1.0.0",
  "scripts": {
    "dev": "vite --host 0.0.0.0 --port 5173",
    "build": "vite build",
    "preview": "vite preview --host 0.0.0.0 --port 4173"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "vite": "^5.4.0"
  }
}
```

## `web/frontend/vite.config.js`

```javascript
import { defineConfig } from 'vite'

export default defineConfig({
  server: {
    host: '0.0.0.0',
    port: 5173
  }
})
```

## `web/frontend/index.html`

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Product Review Dashboard</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

## `web/frontend/src/main.jsx`

```javascript
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

## `web/frontend/src/api.js`

```javascript
const API_BASE = import.meta.env.VITE_API_BASE || ''

async function getJson(path) {
  const response = await fetch(`${API_BASE}${path}`)
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  return response.json()
}

export const api = {
  getTop3: () => getJson('/api/categories/top3'),
  getProducts: (category) => getJson(`/api/categories/${encodeURIComponent(category)}/products`),
  getProduct: (productId) => getJson(`/api/products/${productId}`),
  getReviews: (productId) => getJson(`/api/products/${productId}/reviews`),
  getSummary: (productId) => getJson(`/api/products/${productId}/summary`)
}
```

## `web/frontend/src/App.jsx`

```javascript
import React, { useEffect, useState } from 'react'
import { api } from './api'

const styles = {
  page: { fontFamily: 'Arial, sans-serif', padding: 24, color: '#1f2937' },
  grid: { display: 'grid', gridTemplateColumns: '320px 1fr 1fr', gap: 24, alignItems: 'start' },
  card: { border: '1px solid #e5e7eb', borderRadius: 10, padding: 16, background: '#fff' },
  heading: { marginTop: 0 },
  list: { paddingLeft: 18 },
  link: { color: '#2563eb', cursor: 'pointer', textDecoration: 'underline' },
  pre: { background: '#111827', color: '#f9fafb', padding: 12, borderRadius: 8, overflowX: 'auto', whiteSpace: 'pre-wrap' },
  badge: { display: 'inline-block', padding: '4px 8px', background: '#eff6ff', color: '#1d4ed8', borderRadius: 999, fontSize: 12, marginLeft: 8 },
}

export default function App() {
  const [top3, setTop3] = useState({})
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [products, setProducts] = useState([])
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [productDetails, setProductDetails] = useState(null)
  const [reviews, setReviews] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    loadTop3()
  }, [])

  async function loadTop3() {
    try {
      setLoading(true)
      const data = await api.getTop3()
      setTop3(data)
      const firstCategory = Object.keys(data)[0]
      if (firstCategory) {
        await selectCategory(firstCategory)
      }
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }

  async function selectCategory(category) {
    try {
      setSelectedCategory(category)
      setSelectedProduct(null)
      setProductDetails(null)
      setReviews([])
      setSummary(null)
      const items = await api.getProducts(category)
      setProducts(items)
    } catch (e) {
      setError(String(e))
    }
  }

  async function selectProduct(productId) {
    try {
      setSelectedProduct(productId)
      const [product, reviewRows, summaryRow] = await Promise.all([
        api.getProduct(productId),
        api.getReviews(productId),
        api.getSummary(productId)
      ])
      setProductDetails(product)
      setReviews(reviewRows)
      setSummary(summaryRow)
    } catch (e) {
      setError(String(e))
    }
  }

  return (
    <div style={styles.page}>
      <h1 style={styles.heading}>Product Review Dashboard</h1>
      {loading && <div>Loading…</div>}
      {error && <div style={{ color: 'red', marginBottom: 12 }}>{error}</div>}

      <div style={styles.grid}>
        <section style={styles.card}>
          <h2 style={styles.heading}>Top 3 by Category</h2>
          {Object.entries(top3).map(([category, items]) => (
            <div key={category} style={{ marginBottom: 16 }}>
              <div>
                <span
                  style={styles.link}
                  onClick={() => selectCategory(category)}
                >
                  {category}
                </span>
                {selectedCategory === category && <span style={styles.badge}>selected</span>}
              </div>
              <ul style={styles.list}>
                {items.map(item => (
                  <li key={item.product_id}>
                    {item.product_id} — score {Number(item.score).toFixed(2)}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>

        <section style={styles.card}>
          <h2 style={styles.heading}>Products {selectedCategory ? `in ${selectedCategory}` : ''}</h2>
          <ul style={styles.list}>
            {products.map(product => (
              <li key={product.product_id}>
                <span style={styles.link} onClick={() => selectProduct(product.product_id)}>
                  {product.product_id}
                </span>
                {' '}— {product.name} — avg {Number(product.avg_rating || 0).toFixed(2)} — count {product.rating_count || 0}
              </li>
            ))}
          </ul>
        </section>

        <section style={styles.card}>
          <h2 style={styles.heading}>Product Detail {selectedProduct ? `for ${selectedProduct}` : ''}</h2>
          {productDetails && (
            <>
              <h3>Product</h3>
              <pre style={styles.pre}>{JSON.stringify(productDetails, null, 2)}</pre>
            </>
          )}

          {summary && (
            <>
              <h3>Summary</h3>
              <pre style={styles.pre}>{JSON.stringify(summary, null, 2)}</pre>
            </>
          )}

          {reviews.length > 0 && (
            <>
              <h3>Raw Reviews</h3>
              <pre style={styles.pre}>{JSON.stringify(reviews, null, 2)}</pre>
            </>
          )}
        </section>
      </div>
    </div>
  )
}
```

## `web/frontend/nginx.conf`

```nginx
server {
  listen 80;
  server_name _;
  root /usr/share/nginx/html;
  index index.html;

  location / {
    try_files $uri /index.html;
  }
}
```

## `web/frontend/Dockerfile`

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY web/frontend/package.json /app/package.json
COPY web/frontend/vite.config.js /app/vite.config.js
COPY web/frontend/index.html /app/index.html
COPY web/frontend/src /app/src
RUN npm install && npm run build

FROM nginx:1.27-alpine
COPY web/frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
```

---

# Kafka Connect connector

## `infra/kafka/product-reviews-es-sink.yaml`

```yaml
apiVersion: platform.confluent.io/v1beta1
kind: Connector
metadata:
  name: product-reviews-es-sink
  namespace: confluent
spec:
  class: "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector"
  taskMax: 2
  connectClusterRef:
    name: kafka-connect
  configs:
    topics: "product-reviews"
    connection.url: "http://single-es-coord.elasticsearch.svc.cluster.local:9200"

    transforms: "CreateKey,ExtractKey"
    transforms.CreateKey.type: "org.apache.kafka.connect.transforms.ValueToKey"
    transforms.CreateKey.fields: "review_id"
    transforms.ExtractKey.type: "org.apache.kafka.connect.transforms.ExtractField$Key"
    transforms.ExtractKey.field: "review_id"

    key.ignore: "false"
    schema.ignore: "true"
    write.method: "UPSERT"
    behavior.on.null.values: "IGNORE"
    topic.index.map: "product-reviews:product_reviews"

    key.converter: "org.apache.kafka.connect.storage.StringConverter"
    value.converter: "org.apache.kafka.connect.json.JsonConverter"
    value.converter.schemas.enable: "false"
```

---

# Kubernetes manifests

## `infra/k8s/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: apps
---
apiVersion: v1
kind: Namespace
metadata:
  name: messaging
```

## `infra/k8s/messaging.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: messaging
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7.2-alpine
          ports:
            - containerPort: 6379
---
apiVersion: v1
kind: Service
metadata:
  name: redis
  namespace: messaging
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rabbitmq
  namespace: messaging
spec:
  replicas: 1
  selector:
    matchLabels:
      app: rabbitmq
  template:
    metadata:
      labels:
        app: rabbitmq
    spec:
      containers:
        - name: rabbitmq
          image: rabbitmq:3.13-management
          ports:
            - containerPort: 5672
            - containerPort: 15672
---
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
  namespace: messaging
spec:
  selector:
    app: rabbitmq
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
    - name: mgmt
      port: 15672
      targetPort: 15672
```

## `infra/k8s/config.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: product-platform-config
  namespace: apps
data:
  KAFKA_BOOTSTRAP_SERVERS: kafka.confluent.svc.cluster.local:9092
  ELASTICSEARCH_URL: http://single-es-coord.elasticsearch.svc.cluster.local:9200
  REDIS_URL: redis://redis.messaging.svc.cluster.local:6379/0
  RABBITMQ_HOST: rabbitmq.messaging.svc.cluster.local
  RABBITMQ_PORT: "5672"
  RABBITMQ_USER: guest
  RABBITMQ_PASSWORD: guest
  PRODUCTS_INDEX: products
  REVIEWS_INDEX: product_reviews
  TOPIC_PRODUCT_REVIEWS: product-reviews
  TOPIC_PRODUCT_REVIEW_BATCHES: product-review-batches
  TOPIC_PRODUCT_REVIEW_DLQ: product-review-dlq
  TOPIC_PRODUCT_REVIEW_BATCHES_DLQ: product-review-batches-dlq
  QUEUE_REVIEW_SUMMARIZATION: review_summarization_jobs
  PRODUCT_COUNT: "500"
  PRODUCE_INTERVAL_SECONDS: "1"
  WINDOW_SECONDS: "60"
  MAX_BATCH_SIZE: "20"
  USE_FAKE_LLM: "true"
```

## `infra/k8s/product-seeder-job.yaml`

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: product-seeder
  namespace: apps
spec:
  template:
    spec:
      restartPolicy: Never
      containers:
        - name: product-seeder
          image: product_seeder:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/review-producer.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-producer
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: review-producer
  template:
    metadata:
      labels:
        app: review-producer
    spec:
      containers:
        - name: review-producer
          image: review_producer:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/ratings-aggregator.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ratings-aggregator
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ratings-aggregator
  template:
    metadata:
      labels:
        app: ratings-aggregator
    spec:
      containers:
        - name: ratings-aggregator
          image: ratings_aggregator:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/review-batch-aggregator.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-batch-aggregator
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: review-batch-aggregator
  template:
    metadata:
      labels:
        app: review-batch-aggregator
    spec:
      containers:
        - name: review-batch-aggregator
          image: review_batch_aggregator:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/kafka-rabbitmq-relay.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kafka-rabbitmq-relay
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: kafka-rabbitmq-relay
  template:
    metadata:
      labels:
        app: kafka-rabbitmq-relay
    spec:
      containers:
        - name: kafka-rabbitmq-relay
          image: kafka_rabbitmq_relay:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/llm-summarizer-worker.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: llm-summarizer-worker
  namespace: apps
spec:
  replicas: 2
  selector:
    matchLabels:
      app: llm-summarizer-worker
  template:
    metadata:
      labels:
        app: llm-summarizer-worker
    spec:
      containers:
        - name: llm-summarizer-worker
          image: llm_summarizer_worker:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/recommendation-service.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: recommendation-service
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: recommendation-service
  template:
    metadata:
      labels:
        app: recommendation-service
    spec:
      containers:
        - name: recommendation-service
          image: recommendation_service:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: product-platform-config
```

## `infra/k8s/product-api.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-api
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: product-api
  template:
    metadata:
      labels:
        app: product-api
    spec:
      containers:
        - name: product-api
          image: product_api:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: product-platform-config
---
apiVersion: v1
kind: Service
metadata:
  name: product-api
  namespace: apps
spec:
  selector:
    app: product-api
  ports:
    - port: 80
      targetPort: 8080
```

## `infra/k8s/frontend.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: frontend
  namespace: apps
spec:
  replicas: 1
  selector:
    matchLabels:
      app: frontend
  template:
    metadata:
      labels:
        app: frontend
    spec:
      containers:
        - name: frontend
          image: frontend:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: frontend
  namespace: apps
spec:
  selector:
    app: frontend
  ports:
    - port: 80
      targetPort: 80
```

## `infra/k8s/ingress.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: product-platform
  namespace: apps
  annotations:
    kubernetes.io/ingress.class: traefik
spec:
  rules:
    - host: product-ui.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port:
                  number: 80
    - host: product-api.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: product-api
                port:
                  number: 80
```

---

## Quick run order

```bash
make build
./scripts/create-topics.sh
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/messaging.yaml
kubectl apply -f infra/k8s/config.yaml
kubectl apply -f infra/kafka/product-reviews-es-sink.yaml
kubectl apply -f infra/k8s/product-seeder-job.yaml
kubectl apply -f infra/k8s/review-producer.yaml
kubectl apply -f infra/k8s/ratings-aggregator.yaml
kubectl apply -f infra/k8s/review-batch-aggregator.yaml
kubectl apply -f infra/k8s/kafka-rabbitmq-relay.yaml
kubectl apply -f infra/k8s/llm-summarizer-worker.yaml
kubectl apply -f infra/k8s/recommendation-service.yaml
kubectl apply -f infra/k8s/product-api.yaml
kubectl apply -f infra/k8s/frontend.yaml
kubectl apply -f infra/k8s/ingress.yaml
```

## Minimal next hardening items

- auth/security
- retry and DLQ logic in app consumers
- Helm packaging
- persistent volumes for Redis and RabbitMQ
- production observability
- stricter Elasticsearch mappings for `product_reviews`
