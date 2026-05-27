# Full k3s Kafka Review Pipeline Code Bundle

This is a complete Python-based solution for:

- **Producer app** that generates **100 products** and highly variable product reviews
- **Aggregator app** that batches reviews by product
- **Summarizer app** that uses an **LLM** to summarize ratings and reviews
- **Redis** storage for the summarized output
- **k3s Kubernetes deployment manifest** for all components

---

## Project structure

```text
kafka-llm-reviews/
├── producer/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── aggregator/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── summarizer/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
└── k3s-review-pipeline.yaml
```

---

## App README files

### `producer/README.md`
```md
# Producer Service

This service generates synthetic product reviews and publishes them to Kafka.

## What it does
- Creates review events for 100 products
- Adds variability across rating, title, sentiment, and review text
- Publishes each review to the raw Kafka topic

## Environment variables
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address list
- `RAW_TOPIC`: Kafka topic to publish to
- `PRODUCE_INTERVAL_SECONDS`: Delay between generated review events

## Run locally
```bash
pip install -r requirements.txt
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export RAW_TOPIC=product-reviews
export PRODUCE_INTERVAL_SECONDS=1.5
python app.py
```

## Notes
- Product generation is deterministic in shape but randomized in names and categories
- Review text variability is driven by rating, category, phrase templates, and randomized metadata
```

### `aggregator/README.md`
```md
# Aggregator Service

This service consumes raw product reviews from Kafka, groups them by product, and publishes review batches for downstream summarization.

## What it does
- Reads review events from the input topic
- Builds per-product batches in memory
- Flushes a batch when the size threshold or timeout is reached
- Publishes batched payloads to the next Kafka topic

## Environment variables
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address list
- `INPUT_TOPIC`: Source topic to consume from
- `OUTPUT_TOPIC`: Destination topic for review batches
- `CONSUMER_GROUP`: Kafka consumer group name
- `BATCH_SIZE`: Number of reviews per batch
- `FLUSH_INTERVAL_SECONDS`: Maximum wait before flushing a partial batch

## Run locally
```bash
pip install -r requirements.txt
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export INPUT_TOPIC=product-reviews
export OUTPUT_TOPIC=product-review-batches
export CONSUMER_GROUP=review-aggregator-group
export BATCH_SIZE=5
export FLUSH_INTERVAL_SECONDS=20
python app.py
```

## Notes
- Partial batches are kept in memory until flushed
- For production, consider persistent state or replay-aware design if partial-batch durability is required
```

### `summarizer/README.md`
```md
# Summarizer Service

This service consumes aggregated review batches, calls an LLM to summarize customer sentiment, and stores the resulting summary in Redis.

## What it does
- Reads batched reviews from Kafka
- Builds a prompt from review titles, ratings, metadata, and review text
- Calls the configured LLM endpoint
- Stores the final summary document in Redis
- Maintains a short-lived summary history per product

## Environment variables
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker address list
- `INPUT_TOPIC`: Source topic to consume from
- `CONSUMER_GROUP`: Kafka consumer group name
- `REDIS_HOST`: Redis hostname
- `REDIS_PORT`: Redis port
- `OPENAI_API_KEY`: API key for the model provider
- `OPENAI_MODEL`: Model name to use
- `OPENAI_BASE_URL`: Base URL for the LLM API

## Run locally
```bash
pip install -r requirements.txt
export KAFKA_BOOTSTRAP_SERVERS=localhost:9092
export INPUT_TOPIC=product-review-batches
export CONSUMER_GROUP=review-summarizer-group
export REDIS_HOST=localhost
export REDIS_PORT=6379
export OPENAI_API_KEY=your-key
export OPENAI_MODEL=gpt-4o-mini
export OPENAI_BASE_URL=https://api.openai.com/v1
python app.py
```

## Notes
- The service requires a valid LLM API key at startup
- Redis keys are written with a 24-hour TTL by default
- Add retries and dead-letter handling before using this in a stricter production flow
```

---

## Producer app

### `producer/requirements.txt`

```txt
confluent-kafka==2.5.3
faker==30.1.0
```

### `producer/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
```

### `producer/app.py`

```python
import json
import os
import random
import time
import uuid
from datetime import datetime, timezone

from confluent_kafka import Producer
from faker import Faker

fake = Faker()

BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
TOPIC = os.getenv("RAW_TOPIC", "product-reviews")
PRODUCE_INTERVAL_SECONDS = float(os.getenv("PRODUCE_INTERVAL_SECONDS", "1.5"))

PRODUCT_CATEGORIES = [
    "Laptop",
    "Desktop",
    "Monitor",
    "Server",
    "Workstation",
    "Keyboard",
    "Mouse",
    "Docking Station",
    "Headset",
    "Webcam",
]

CATEGORY_MODELS = {
    "Laptop": ["Pro", "Air", "Elite", "Plus", "Max"],
    "Desktop": ["Tower", "Mini", "All-in-One", "SFF", "Creator"],
    "Monitor": ["UltraSharp", "Vision", "WideView", "ColorPro", "Edge"],
    "Server": ["PowerRack", "ScaleNode", "ComputeX", "CoreServe", "FlexHost"],
    "Workstation": ["Precision", "Render", "Studio", "Compute", "Zeta"],
    "Keyboard": ["SilentKey", "MechPro", "TravelKey", "OfficeKey", "SlimKey"],
    "Mouse": ["SwiftPoint", "ErgoMove", "PrecisionMouse", "TravelMouse", "ProClick"],
    "Docking Station": ["DockHub", "ConnectX", "MultiPort", "WorkDock", "PowerDock"],
    "Headset": ["ClearVoice", "FocusSound", "CallPro", "QuietMeet", "AirTalk"],
    "Webcam": ["VisionCam", "StreamPro", "MeetCam", "FocusCam", "UltraCam"],
}

ADJECTIVES = [
    "Premium", "Smart", "Advanced", "Compact", "Ultra", "Pro", "Business",
    "Performance", "Portable", "Reliable"
]

FEATURES_BY_CATEGORY = {
    "Laptop": ["battery life", "keyboard", "screen", "thermals", "portability", "performance"],
    "Desktop": ["performance", "expandability", "noise", "setup", "value", "cooling"],
    "Monitor": ["color accuracy", "brightness", "sharpness", "stand quality", "connectivity", "panel uniformity"],
    "Server": ["stability", "compute power", "remote management", "cooling", "deployment", "throughput"],
    "Workstation": ["render speed", "GPU performance", "stability", "build quality", "thermals", "upgradeability"],
    "Keyboard": ["typing feel", "key travel", "noise", "build quality", "layout", "backlight"],
    "Mouse": ["ergonomics", "tracking", "battery life", "weight", "scroll wheel", "connectivity"],
    "Docking Station": ["port selection", "power delivery", "stability", "compatibility", "heat", "ease of use"],
    "Headset": ["microphone quality", "comfort", "noise isolation", "battery life", "audio clarity", "fit"],
    "Webcam": ["image quality", "low-light performance", "autofocus", "setup", "microphone", "frame rate"],
}

POSITIVE_OPENERS = [
    "I have been using this for a few weeks and it has exceeded my expectations.",
    "So far this product has been a strong performer in my daily workflow.",
    "This has been one of the better purchases I have made recently.",
    "I was pleasantly surprised by how well this product performs.",
    "After regular use, I can say this product delivers really well.",
]

NEGATIVE_OPENERS = [
    "I wanted to like this product, but my experience has been frustrating.",
    "This has not performed as well as I expected.",
    "I ran into issues sooner than I should have for a product in this price range.",
    "The product has some clear problems that affected my experience.",
    "I had higher expectations, but it fell short in several areas.",
]

MIXED_OPENERS = [
    "There are some things I really like here, but a few drawbacks stand out.",
    "My experience has been mixed overall.",
    "This product gets a lot right, though it is not without tradeoffs.",
    "I can see the strengths, but there are also some weak points.",
    "Overall it is decent, but a few areas could be improved.",
]

POSITIVE_PHRASES = [
    "The {feature} is excellent.",
    "I really liked the {feature}.",
    "The {feature} feels thoughtfully designed.",
    "The {feature} is better than I expected.",
    "The {feature} stands out in a good way.",
    "The {feature} has been consistently reliable.",
]

NEGATIVE_PHRASES = [
    "The {feature} needs improvement.",
    "I was disappointed with the {feature}.",
    "The {feature} feels below expectations.",
    "The {feature} has been inconsistent.",
    "The {feature} is one of the weaker parts of this product.",
    "The {feature} could be much better at this price point.",
]

MIXED_PHRASES = [
    "The {feature} is good, but not great.",
    "The {feature} works fine for most cases.",
    "The {feature} is solid, although there is room for improvement.",
    "The {feature} is acceptable, but it does not stand out.",
    "The {feature} performs well enough, though not consistently.",
]

CLOSERS = [
    "I would recommend it to others with similar needs.",
    "I would consider buying from this line again.",
    "I hope future updates make it even better.",
    "This feels close to great with a few refinements.",
    "It depends on what you care about most.",
    "For my use case, it has been a worthwhile purchase.",
    "I am still deciding whether it is worth the price.",
    "I would only recommend it with a few caveats.",
]

TITLES_POSITIVE = [
    "Great performance overall",
    "Very happy with this purchase",
    "Reliable and well built",
    "Better than expected",
    "Excellent for everyday use",
]

TITLES_NEGATIVE = [
    "Not worth the price",
    "Disappointing experience",
    "Needs improvement",
    "Too many issues so far",
    "Expected better quality",
]

TITLES_MIXED = [
    "Good, but has some tradeoffs",
    "Solid overall with a few issues",
    "Mixed experience",
    "Works well, but not perfect",
    "Decent product with room to improve",
]


def generate_products(num_products=100):
    products = []
    for i in range(1, num_products + 1):
        category = PRODUCT_CATEGORIES[(i - 1) % len(PRODUCT_CATEGORIES)]
        model = random.choice(CATEGORY_MODELS[category])
        adjective = random.choice(ADJECTIVES)
        product_id = f"P{1000 + i}"
        product_name = f"{adjective} {category} {model} {i}"
        products.append(
            {
                "product_id": product_id,
                "product_name": product_name,
                "category": category,
            }
        )
    return products


PRODUCTS = generate_products(100)


def delivery_report(err, msg):
    if err is not None:
        print(f"Delivery failed: {err}")
    else:
        print(f"Produced to {msg.topic()} [{msg.partition()}] @ offset {msg.offset()}")


def choose_sentiment_bucket(rating: int) -> str:
    if rating >= 4:
        return "positive"
    if rating <= 2:
        return "negative"
    return "mixed"


def generate_title(sentiment: str) -> str:
    if sentiment == "positive":
        return random.choice(TITLES_POSITIVE)
    if sentiment == "negative":
        return random.choice(TITLES_NEGATIVE)
    return random.choice(TITLES_MIXED)


def pick_distinct_features(category: str, count: int = 3):
    features = FEATURES_BY_CATEGORY[category]
    if len(features) <= count:
        return features
    return random.sample(features, count)


def make_sentences(sentiment: str, category: str):
    features = pick_distinct_features(category, 3)

    if sentiment == "positive":
        opener = random.choice(POSITIVE_OPENERS)
        phrases = [random.choice(POSITIVE_PHRASES).format(feature=f) for f in features]
    elif sentiment == "negative":
        opener = random.choice(NEGATIVE_OPENERS)
        phrases = [random.choice(NEGATIVE_PHRASES).format(feature=f) for f in features]
    else:
        opener = random.choice(MIXED_OPENERS)
        phrases = [random.choice(MIXED_PHRASES).format(feature=f) for f in features]

    closer = random.choice(CLOSERS)

    sentence_count = random.choice([2, 3, 4])
    body = [opener] + phrases[: sentence_count - 1]
    if random.random() > 0.5:
        body.append(closer)

    return " ".join(body)


def generate_review_text(product: dict, rating: int):
    sentiment = choose_sentiment_bucket(rating)
    review_text = make_sentences(sentiment, product["category"])
    title = generate_title(sentiment)
    return title, review_text, sentiment


def generate_review():
    product = random.choice(PRODUCTS)

    weighted_ratings = [1, 2, 3, 4, 5]
    weights = [10, 15, 20, 30, 25]
    rating = random.choices(weighted_ratings, weights=weights, k=1)[0]

    title, review_text, sentiment = generate_review_text(product, rating)

    payload = {
        "review_id": str(uuid.uuid4()),
        "product_id": product["product_id"],
        "product_name": product["product_name"],
        "category": product["category"],
        "user_id": f"user-{random.randint(1000, 9999)}",
        "rating": rating,
        "review_title": title,
        "review_text": review_text,
        "sentiment_hint": sentiment,
        "verified_purchase": random.choice([True, False, True, True]),
        "helpful_votes": random.randint(0, 250),
        "review_source": random.choice(["website", "mobile_app", "partner_portal"]),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return payload


def main():
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    print(f"Starting producer. Sending events to topic={TOPIC}")
    while True:
        event = generate_review()
        producer.produce(
            TOPIC,
            key=event["product_id"],
            value=json.dumps(event).encode("utf-8"),
            callback=delivery_report,
        )
        producer.poll(0)
        print("Produced:", json.dumps(event))
        time.sleep(PRODUCE_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
```

---

## Aggregator app

### `aggregator/requirements.txt`

```txt
confluent-kafka==2.5.3
```

### `aggregator/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
```

### `aggregator/app.py`

```python
import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone

from confluent_kafka import Consumer, Producer


BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
INPUT_TOPIC = os.getenv("INPUT_TOPIC", "product-reviews")
OUTPUT_TOPIC = os.getenv("OUTPUT_TOPIC", "product-review-batches")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "review-aggregator-group")
BATCH_SIZE = int(os.getenv("BATCH_SIZE", "5"))
FLUSH_INTERVAL_SECONDS = int(os.getenv("FLUSH_INTERVAL_SECONDS", "20"))


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def flush_product_batch(producer, product_id, state):
    reviews = state["reviews"]
    if not reviews:
        return

    avg_rating = round(sum(r["rating"] for r in reviews) / len(reviews), 2)

    batch_event = {
        "product_id": product_id,
        "product_name": reviews[0]["product_name"],
        "category": reviews[0].get("category", "Unknown"),
        "batch_size": len(reviews),
        "average_rating": avg_rating,
        "ratings": [r["rating"] for r in reviews],
        "reviews": reviews,
        "batched_at": utc_now(),
    }

    producer.produce(
        OUTPUT_TOPIC,
        key=product_id,
        value=json.dumps(batch_event).encode("utf-8"),
    )
    producer.flush()

    print(f"Flushed batch for {product_id}: {len(reviews)} reviews")

    state["reviews"] = []
    state["last_flush"] = time.time()


def main():
    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    producer = Producer({"bootstrap.servers": BOOTSTRAP_SERVERS})

    consumer.subscribe([INPUT_TOPIC])

    batches = defaultdict(lambda: {"reviews": [], "last_flush": time.time()})

    print(f"Aggregator consuming {INPUT_TOPIC} and producing {OUTPUT_TOPIC}")

    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is not None:
                if msg.error():
                    print("Consumer error:", msg.error())
                else:
                    event = json.loads(msg.value().decode("utf-8"))
                    product_id = event["product_id"]

                    batches[product_id]["reviews"].append(event)

                    if len(batches[product_id]["reviews"]) >= BATCH_SIZE:
                        flush_product_batch(producer, product_id, batches[product_id])

            now = time.time()
            for product_id, state in list(batches.items()):
                if state["reviews"] and (now - state["last_flush"] >= FLUSH_INTERVAL_SECONDS):
                    flush_product_batch(producer, product_id, state)

    except KeyboardInterrupt:
        pass
    finally:
        for product_id, state in list(batches.items()):
            if state["reviews"]:
                flush_product_batch(producer, product_id, state)
        consumer.close()


if __name__ == "__main__":
    main()
```

---

## Summarizer app

### `summarizer/requirements.txt`

```txt
confluent-kafka==2.5.3
redis==5.0.8
openai==1.51.2
```

### `summarizer/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

CMD ["python", "app.py"]
```

### `summarizer/app.py`

```python
import json
import os
from datetime import datetime, timezone

import redis
from confluent_kafka import Consumer
from openai import OpenAI


BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
INPUT_TOPIC = os.getenv("INPUT_TOPIC", "product-review-batches")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "review-summarizer-group")

REDIS_HOST = os.getenv("REDIS_HOST", "reviews-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
llm_client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def build_prompt(batch_event: dict) -> str:
    reviews_text = "\n".join(
        [
            (
                f"- Rating: {r['rating']}/5 | "
                f"Title: {r.get('review_title', '')} | "
                f"Verified: {r.get('verified_purchase', False)} | "
                f"Helpful Votes: {r.get('helpful_votes', 0)} | "
                f"Review: {r['review_text']}"
            )
            for r in batch_event["reviews"]
        ]
    )

    return f"""
You are an analyst summarizing product reviews.

Product:
- Product ID: {batch_event['product_id']}
- Product Name: {batch_event['product_name']}
- Category: {batch_event.get('category', 'Unknown')}

Batch details:
- Batch size: {batch_event['batch_size']}
- Average rating: {batch_event['average_rating']}
- Ratings: {batch_event['ratings']}

Reviews:
{reviews_text}

Return valid JSON only with this exact schema:
{{
  "summary": "short paragraph summary",
  "sentiment": "positive|mixed|negative",
  "top_positive_points": ["point1", "point2", "point3"],
  "top_negative_points": ["point1", "point2", "point3"],
  "recommended_action": "short recommendation"
}}
""".strip()


def summarize_batch(batch_event: dict) -> dict:
    prompt = build_prompt(batch_event)

    response = llm_client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {"role": "system", "content": "You summarize customer product reviews."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    return json.loads(content)


def store_summary(batch_event: dict, llm_summary: dict):
    product_id = batch_event["product_id"]
    key = f"product_summary:{product_id}"

    document = {
        "product_id": product_id,
        "product_name": batch_event["product_name"],
        "category": batch_event.get("category", "Unknown"),
        "batch_size": batch_event["batch_size"],
        "average_rating": batch_event["average_rating"],
        "ratings": json.dumps(batch_event["ratings"]),
        "summary": llm_summary["summary"],
        "sentiment": llm_summary["sentiment"],
        "top_positive_points": json.dumps(llm_summary["top_positive_points"]),
        "top_negative_points": json.dumps(llm_summary["top_negative_points"]),
        "recommended_action": llm_summary["recommended_action"],
        "last_updated": utc_now(),
    }

    redis_client.hset(key, mapping=document)
    redis_client.expire(key, 60 * 60 * 24)

    history_key = f"product_summary_history:{product_id}"
    redis_client.rpush(
        history_key,
        json.dumps(
            {
                "batch_event": batch_event,
                "llm_summary": llm_summary,
                "stored_at": utc_now(),
            }
        ),
    )
    redis_client.expire(history_key, 60 * 60 * 24)

    print(f"Stored summary in Redis key={key}")


def main():
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required")

    consumer = Consumer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "group.id": CONSUMER_GROUP,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([INPUT_TOPIC])

    print(f"Summarizer consuming from topic={INPUT_TOPIC}")

    try:
        while True:
            msg = consumer.poll(1.0)
            if msg is None:
                continue

            if msg.error():
                print("Consumer error:", msg.error())
                continue

            batch_event = json.loads(msg.value().decode("utf-8"))
            print(f"Received batch for product={batch_event['product_id']}")

            try:
                llm_summary = summarize_batch(batch_event)
                store_summary(batch_event, llm_summary)
            except Exception as e:
                print(f"Failed processing batch: {e}")

    except KeyboardInterrupt:
        pass
    finally:
        consumer.close()


if __name__ == "__main__":
    main()
```

---

## k3s deployment manifest

### `k3s-review-pipeline.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: reviews-ai
---
apiVersion: v1
kind: Secret
metadata:
  name: llm-secret
  namespace: reviews-ai
type: Opaque
stringData:
  OPENAI_API_KEY: "your_api_key_here"
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: reviews-ai
data:
  KAFKA_BOOTSTRAP_SERVERS: "kafka.confluent.svc.cluster.local:9071"
  RAW_TOPIC: "product-reviews"
  PRODUCE_INTERVAL_SECONDS: "1.5"

  AGG_INPUT_TOPIC: "product-reviews"
  AGG_OUTPUT_TOPIC: "product-review-batches"
  AGG_CONSUMER_GROUP: "review-aggregator-group"
  AGG_BATCH_SIZE: "5"
  AGG_FLUSH_INTERVAL_SECONDS: "20"

  SUM_INPUT_TOPIC: "product-review-batches"
  SUM_CONSUMER_GROUP: "review-summarizer-group"

  REDIS_HOST: "reviews-redis.reviews-ai.svc.cluster.local"
  REDIS_PORT: "6379"

  OPENAI_MODEL: "gpt-4o-mini"
  OPENAI_BASE_URL: "https://api.openai.com/v1"
---
apiVersion: v1
kind: Service
metadata:
  name: reviews-kafka-headless
  namespace: reviews-ai
spec:
  clusterIP: None
  selector:
    app: reviews-kafka
  ports:
    - name: kafka
      port: 9092
      targetPort: 9092
    - name: controller
      port: 9093
      targetPort: 9093
---
apiVersion: v1
kind: Service
metadata:
  name: reviews-kafka
  namespace: reviews-ai
spec:
  selector:
    app: reviews-kafka
  ports:
    - name: kafka
      port: 9092
      targetPort: 9092
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: reviews-kafka
  namespace: reviews-ai
spec:
  serviceName: reviews-kafka-headless
  replicas: 1
  selector:
    matchLabels:
      app: reviews-kafka
  template:
    metadata:
      labels:
        app: reviews-kafka
    spec:
      containers:
        - name: kafka
          image: bitnami/kafka:3.7
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 9092
              name: kafka
            - containerPort: 9093
              name: controller
          env:
            - name: KAFKA_ENABLE_KRAFT
              value: "yes"
            - name: KAFKA_KRAFT_CLUSTER_ID
              value: "MkU3OEVBNTcwNTJENDM2Qk"
            - name: KAFKA_CFG_NODE_ID
              value: "0"
            - name: KAFKA_CFG_PROCESS_ROLES
              value: "broker,controller"
            - name: KAFKA_CFG_CONTROLLER_QUORUM_VOTERS
              value: "0@reviews-kafka-0.reviews-kafka-headless.reviews-ai.svc.cluster.local:9093"
            - name: KAFKA_CFG_LISTENERS
              value: "PLAINTEXT://:9092,CONTROLLER://:9093"
            - name: KAFKA_CFG_ADVERTISED_LISTENERS
              value: "PLAINTEXT://reviews-kafka.reviews-ai.svc.cluster.local:9092"
            - name: KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP
              value: "PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT"
            - name: KAFKA_CFG_CONTROLLER_LISTENER_NAMES
              value: "CONTROLLER"
            - name: KAFKA_CFG_INTER_BROKER_LISTENER_NAME
              value: "PLAINTEXT"
            - name: KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE
              value: "true"
            - name: KAFKA_CFG_NUM_PARTITIONS
              value: "3"
            - name: KAFKA_CFG_DEFAULT_REPLICATION_FACTOR
              value: "1"
            - name: KAFKA_CFG_OFFSETS_TOPIC_REPLICATION_FACTOR
              value: "1"
            - name: KAFKA_CFG_TRANSACTION_STATE_LOG_REPLICATION_FACTOR
              value: "1"
            - name: KAFKA_CFG_TRANSACTION_STATE_LOG_MIN_ISR
              value: "1"
            - name: ALLOW_PLAINTEXT_LISTENER
              value: "yes"
          volumeMounts:
            - name: kafka-data
              mountPath: /bitnami/kafka
          readinessProbe:
            tcpSocket:
              port: 9092
            initialDelaySeconds: 20
            periodSeconds: 10
          livenessProbe:
            tcpSocket:
              port: 9092
            initialDelaySeconds: 30
            periodSeconds: 20
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "1Gi"
  volumeClaimTemplates:
    - metadata:
        name: kafka-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 8Gi
---
apiVersion: v1
kind: Service
metadata:
  name: reviews-redis
  namespace: reviews-ai
spec:
  selector:
    app: reviews-redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
---
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: reviews-redis
  namespace: reviews-ai
spec:
  serviceName: reviews-redis
  replicas: 1
  selector:
    matchLabels:
      app: reviews-redis
  template:
    metadata:
      labels:
        app: reviews-redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          imagePullPolicy: IfNotPresent
          command: ["redis-server"]
          args: ["--appendonly", "yes"]
          ports:
            - containerPort: 6379
              name: redis
          volumeMounts:
            - name: redis-data
              mountPath: /data
          readinessProbe:
            tcpSocket:
              port: 6379
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            tcpSocket:
              port: 6379
            initialDelaySeconds: 10
            periodSeconds: 20
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
  volumeClaimTemplates:
    - metadata:
        name: redis-data
      spec:
        accessModes: ["ReadWriteOnce"]
        resources:
          requests:
            storage: 5Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: producer
  namespace: reviews-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: producer
  template:
    metadata:
      labels:
        app: producer
    spec:
      initContainers:
        - name: wait-for-kafka
          image: busybox:1.36
          command:
            - sh
            - -c
            - until nc -z kafka.confluent.svc.cluster.local 9071; do echo waiting for kafka; sleep 3; done
      containers:
        - name: producer
          image: YOUR_REGISTRY/reviews-producer:1.0.0
          imagePullPolicy: IfNotPresent
          env:
            - name: KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: KAFKA_BOOTSTRAP_SERVERS
            - name: RAW_TOPIC
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: RAW_TOPIC
            - name: PRODUCE_INTERVAL_SECONDS
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: PRODUCE_INTERVAL_SECONDS
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aggregator
  namespace: reviews-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aggregator
  template:
    metadata:
      labels:
        app: aggregator
    spec:
      initContainers:
        - name: wait-for-kafka
          image: busybox:1.36
          command:
            - sh
            - -c
            - until nc -z kafka.confluent.svc.cluster.local 9071; do echo waiting for kafka; sleep 3; done
      containers:
        - name: aggregator
          image: YOUR_REGISTRY/reviews-aggregator:1.0.0
          imagePullPolicy: IfNotPresent
          env:
            - name: KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: KAFKA_BOOTSTRAP_SERVERS
            - name: INPUT_TOPIC
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: AGG_INPUT_TOPIC
            - name: OUTPUT_TOPIC
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: AGG_OUTPUT_TOPIC
            - name: CONSUMER_GROUP
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: AGG_CONSUMER_GROUP
            - name: BATCH_SIZE
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: AGG_BATCH_SIZE
            - name: FLUSH_INTERVAL_SECONDS
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: AGG_FLUSH_INTERVAL_SECONDS
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: summarizer
  namespace: reviews-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: summarizer
  template:
    metadata:
      labels:
        app: summarizer
    spec:
      initContainers:
        - name: wait-for-kafka
          image: busybox:1.36
          command:
            - sh
            - -c
            - until nc -z kafka.confluent.svc.cluster.local 9071; do echo waiting for kafka; sleep 3; done
        - name: wait-for-redis
          image: busybox:1.36
          command:
            - sh
            - -c
            - until nc -z reviews-redis 6379; do echo waiting for redis; sleep 3; done
      containers:
        - name: summarizer
          image: YOUR_REGISTRY/reviews-summarizer:1.0.0
          imagePullPolicy: IfNotPresent
          env:
            - name: KAFKA_BOOTSTRAP_SERVERS
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: KAFKA_BOOTSTRAP_SERVERS
            - name: INPUT_TOPIC
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: SUM_INPUT_TOPIC
            - name: CONSUMER_GROUP
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: SUM_CONSUMER_GROUP
            - name: REDIS_HOST
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: REDIS_HOST
            - name: REDIS_PORT
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: REDIS_PORT
            - name: OPENAI_MODEL
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: OPENAI_MODEL
            - name: OPENAI_BASE_URL
              valueFrom:
                configMapKeyRef:
                  name: app-config
                  key: OPENAI_BASE_URL
            - name: OPENAI_API_KEY
              valueFrom:
                secretKeyRef:
                  name: llm-secret
                  key: OPENAI_API_KEY
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1"
              memory: "1Gi"
```

---

## Build and push commands

Replace `YOUR_REGISTRY` with your registry.

```bash
docker build -t YOUR_REGISTRY/reviews-producer:1.0.0 ./producer
docker build -t YOUR_REGISTRY/reviews-aggregator:1.0.0 ./aggregator
docker build -t YOUR_REGISTRY/reviews-summarizer:1.0.0 ./summarizer

docker push YOUR_REGISTRY/reviews-producer:1.0.0
docker push YOUR_REGISTRY/reviews-aggregator:1.0.0
docker push YOUR_REGISTRY/reviews-summarizer:1.0.0
```

---

## Deploy to k3s

```bash
kubectl apply -f k3s-review-pipeline.yaml
```

---

## Verify deployment

```bash
kubectl get pods -n reviews-ai
kubectl get svc -n reviews-ai
kubectl get pvc -n reviews-ai
```

### Logs

```bash
kubectl logs -n reviews-ai deploy/producer -f
kubectl logs -n reviews-ai deploy/aggregator -f
kubectl logs -n reviews-ai deploy/summarizer -f
kubectl logs -n reviews-ai statefulset/reviews-kafka -f
kubectl logs -n reviews-ai statefulset/reviews-redis -f
```

---

## Validate Redis output

List keys:

```bash
kubectl exec -n reviews-ai -it statefulset/reviews-redis -- redis-cli KEYS 'product_summary:*'
```

Inspect one key:

```bash
kubectl exec -n reviews-ai -it statefulset/reviews-redis -- redis-cli HGETALL product_summary:P1001
```

---

## Example produced review event

```json
{
  "review_id": "f8e508d1-7f84-42b4-b15a-a11c27eb5b90",
  "product_id": "P1001",
  "product_name": "Premium Laptop Elite 1",
  "category": "Laptop",
  "user_id": "user-4821",
  "rating": 4,
  "review_title": "Great performance overall",
  "review_text": "So far this product has been a strong performer in my daily workflow. The battery life is excellent. The screen stands out in a good way. I would recommend it to others with similar needs.",
  "sentiment_hint": "positive",
  "verified_purchase": true,
  "helpful_votes": 83,
  "review_source": "website",
  "created_at": "2026-05-27T10:20:30.123456+00:00"
}
```

---

## Notes

- This is a **working baseline** for **k3s**.
- Kafka and Redis are intentionally **single-instance** here to keep the deployment simple.
- For production, the next step is to move Kafka and Redis to **operator/chart-managed HA deployments** and add retry, dead-letter handling, and monitoring.
