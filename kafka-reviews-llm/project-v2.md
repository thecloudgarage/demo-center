# Updated final package

This package assumes:

- You **already have a Kafka Connect pod/service** or can deploy the included single-worker Connect deployment.
- Kafka is reachable at `kafka.confluent.svc.cluster.local:9071`.
- The flow is now:

`producer -> Kafka(product-reviews) -> aggregator -> Kafka(product-review-batches) -> Kafka Connect RabbitMQ sink -> RabbitMQ -> summarizer worker -> Redis`

---

## File tree

```text
review-pipeline/
├── README.md
├── sample-review.json
├── producer/
│   ├── README.md
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── aggregator/
│   ├── README.md
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── summarizer/
│   ├── README.md
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── kafka-connect/
│   ├── README.md
│   ├── Dockerfile
│   └── connector-review-batches-to-rabbitmq.json
└── manifests/
    ├── 00-namespace.yaml
    ├── 01-configmap.yaml
    ├── 02-secrets.yaml
    ├── 03-rabbitmq.yaml
    ├── 04-redis.yaml
    ├── 05-producer.yaml
    ├── 06-aggregator.yaml
    ├── 07-summarizer.yaml
    ├── 08-kafka-connect-single.yaml
    └── 09-register-rabbitmq-connector.yaml
```

---

## `README.md`

```md
# Review Pipeline with Kafka Connect + RabbitMQ + Redis

## Architecture

1. **producer** continuously generates product review events and writes them to Kafka topic `product-reviews`
2. **aggregator** batches reviews by `product_id` and writes to Kafka topic `product-review-batches`
3. **Kafka Connect RabbitMQ sink** forwards batch messages from Kafka to RabbitMQ
4. **summarizer** consumes RabbitMQ jobs, generates a summary, and stores the latest result in Redis

## Topics and queues

- Kafka input topic: `product-reviews`
- Kafka batch topic: `product-review-batches`
- RabbitMQ exchange: `review.jobs`
- RabbitMQ queue: `review-summary-q`
- RabbitMQ DLQ: `review-summary-dlq`

## Build images

```bash
docker build -t review-producer:latest ./producer
docker build -t review-aggregator:latest ./aggregator
docker build -t review-summarizer:latest ./summarizer
docker build -t review-kafka-connect:latest ./kafka-connect
```

## Deploy core services

```bash
kubectl apply -f manifests/00-namespace.yaml
kubectl apply -f manifests/01-configmap.yaml
kubectl apply -f manifests/02-secrets.yaml
kubectl apply -f manifests/03-rabbitmq.yaml
kubectl apply -f manifests/04-redis.yaml
kubectl apply -f manifests/05-producer.yaml
kubectl apply -f manifests/06-aggregator.yaml
kubectl apply -f manifests/07-summarizer.yaml
```

## Kafka Connect

### Option A - use your existing Kafka Connect pod
1. Update `kafka-connect/connector-review-batches-to-rabbitmq.json`
2. Set the correct installed RabbitMQ sink connector class
3. Apply:
```bash
kubectl apply -f manifests/09-register-rabbitmq-connector.yaml
```

### Option B - deploy the included single-worker Kafka Connect
1. Build/push `review-kafka-connect:latest`
2. Apply:
```bash
kubectl apply -f manifests/08-kafka-connect-single.yaml
kubectl apply -f manifests/09-register-rabbitmq-connector.yaml
```

## Test

Watch the generated review stream and downstream processing:

```bash
kubectl logs -n review-ai deploy/review-producer -f
kubectl logs -n review-ai deploy/review-aggregator -f
kubectl logs -n review-ai deploy/review-summarizer -f
```

Check Redis for stored summaries:

```bash
kubectl exec -n review-ai deploy/reviews-redis -- redis-cli KEYS 'review-summary:*'
kubectl exec -n review-ai deploy/reviews-redis -- redis-cli GET review-summary:P1001
```

## Notes

- The producer is a standalone generator and does not expose an HTTP API.
- The summarizer uses OpenAI if `OPENAI_API_KEY` is set.
- If no LLM key is present, it falls back to a deterministic local summary.
- The Kafka Connect RabbitMQ sink **plugin class and plugin-specific RabbitMQ property names must match the plugin installed in your Connect image**.
```

---

## `sample-review.json`

```json
{
  "product_id": "laptop-15",
  "user_id": "user-101",
  "rating": 5,
  "review_text": "Battery life is excellent and performance is smooth even with multiple apps open."
}
```

---

## `producer/README.md`

```md
# producer

Standalone event generator that continuously creates product reviews and publishes them to Kafka.
```

## `producer/requirements.txt`

```txt
confluent-kafka==2.4.0
faker==30.1.0
```

## `producer/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
```

## `producer/app.py`

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
TOPIC = os.getenv("KAFKA_INPUT_TOPIC", "product-reviews")
PRODUCE_INTERVAL_SECONDS = float(os.getenv("PRODUCE_INTERVAL_SECONDS", "1.5"))
CLIENT_ID = os.getenv("PRODUCER_CLIENT_ID", "review-producer")

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
    producer = Producer(
        {
            "bootstrap.servers": BOOTSTRAP_SERVERS,
            "client.id": CLIENT_ID,
            "acks": "all",
        }
    )

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

## `aggregator/README.md`

```md
# aggregator

Consumes raw review events, groups them by `product_id`, and emits batch jobs to Kafka.
```

## `aggregator/requirements.txt`

```txt
confluent-kafka==2.4.0
```

## `aggregator/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
```

## `aggregator/app.py`

```python
import json
import os
import signal
import time
import uuid
from collections import defaultdict

from confluent_kafka import Consumer, Producer

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka.confluent.svc.cluster.local:9071")
INPUT_TOPIC = os.getenv("KAFKA_INPUT_TOPIC", "product-reviews")
OUTPUT_TOPIC = os.getenv("KAFKA_BATCH_TOPIC", "product-review-batches")
GROUP_ID = os.getenv("KAFKA_AGGREGATOR_GROUP_ID", "review-aggregator")
MAX_BATCH_SIZE = int(os.getenv("AGGREGATOR_MAX_BATCH_SIZE", "10"))
MAX_BATCH_AGE_SECONDS = int(os.getenv("AGGREGATOR_MAX_BATCH_AGE_SECONDS", "30"))
POLL_TIMEOUT = float(os.getenv("AGGREGATOR_POLL_TIMEOUT_SECONDS", "1.0"))

running = True
state = defaultdict(lambda: {"reviews": [], "first_seen": time.time()})


def stop_handler(signum, frame):
    global running
    running = False


signal.signal(signal.SIGINT, stop_handler)
signal.signal(signal.SIGTERM, stop_handler)


def make_consumer():
    return Consumer(
        {
            "bootstrap.servers": BOOTSTRAP,
            "group.id": GROUP_ID,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )


def make_producer():
    return Producer({"bootstrap.servers": BOOTSTRAP, "acks": "all"})


def build_batch(product_id, reviews):
    ratings = [float(r.get("rating", 0)) for r in reviews]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

    return {
        "batch_id": str(uuid.uuid4()),
        "product_id": product_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "review_count": len(reviews),
        "avg_rating": avg_rating,
        "reviews": reviews,
    }


def emit_batch(producer, product_id):
    reviews = state[product_id]["reviews"]
    if not reviews:
        return

    batch = build_batch(product_id, reviews)
    producer.produce(
        OUTPUT_TOPIC,
        key=product_id,
        value=json.dumps(batch).encode("utf-8"),
    )
    producer.flush(10)
    state.pop(product_id, None)
    print(f"emitted batch for product_id={product_id} count={batch['review_count']}")


def flush_expired(producer):
    now = time.time()
    expired = [
        product_id
        for product_id, bucket in state.items()
        if bucket["reviews"] and (now - bucket["first_seen"] >= MAX_BATCH_AGE_SECONDS)
    ]
    for product_id in expired:
        emit_batch(producer, product_id)


def main():
    consumer = make_consumer()
    producer = make_producer()
    consumer.subscribe([INPUT_TOPIC])

    print("aggregator started")

    try:
        while running:
            msg = consumer.poll(POLL_TIMEOUT)

            if msg is None:
                flush_expired(producer)
                continue

            if msg.error():
                print(f"consumer error: {msg.error()}")
                continue

            review = json.loads(msg.value().decode("utf-8"))
            product_id = review["product_id"]

            bucket = state[product_id]
            if not bucket["reviews"]:
                bucket["first_seen"] = time.time()

            bucket["reviews"].append(review)

            if len(bucket["reviews"]) >= MAX_BATCH_SIZE:
                emit_batch(producer, product_id)

            flush_expired(producer)

    finally:
        for product_id in list(state.keys()):
            emit_batch(producer, product_id)
        consumer.close()


if __name__ == "__main__":
    main()
```

---

## `summarizer/README.md`

```md
# summarizer

Consumes batch jobs from RabbitMQ, summarizes them, and stores the latest summary in Redis.
```

## `summarizer/requirements.txt`

```txt
pika==1.3.2
redis==5.0.4
openai==1.30.5
```

## `summarizer/Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PYTHONUNBUFFERED=1

CMD ["python", "app.py"]
```

## `summarizer/app.py`

```python
import json
import os
import re
import time
from collections import Counter

import pika
import redis
from openai import OpenAI

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "reviews-rabbitmq")
RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")
RABBITMQ_VHOST = os.getenv("RABBITMQ_VHOST", "/")
RABBITMQ_EXCHANGE = os.getenv("RABBITMQ_EXCHANGE", "review.jobs")
RABBITMQ_EXCHANGE_TYPE = os.getenv("RABBITMQ_EXCHANGE_TYPE", "topic")
RABBITMQ_QUEUE = os.getenv("RABBITMQ_QUEUE", "review-summary-q")
RABBITMQ_ROUTING_KEY = os.getenv("RABBITMQ_ROUTING_KEY", "summary.standard")
RABBITMQ_DLX = os.getenv("RABBITMQ_DLX", "review.jobs.dlx")
RABBITMQ_DLQ = os.getenv("RABBITMQ_DLQ", "review-summary-dlq")

REDIS_HOST = os.getenv("REDIS_HOST", "reviews-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def redis_client():
    return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def clean_words(text):
    return re.findall(r"[a-zA-Z]{4,}", text.lower())


def fallback_summary(batch):
    reviews = batch.get("reviews", [])
    ratings = [float(r.get("rating", 0)) for r in reviews]
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

    all_text = " ".join(r.get("review_text", "") for r in reviews)
    words = [w for w in clean_words(all_text) if w not in {
        "this", "that", "with", "from", "have", "were", "been", "very",
        "really", "about", "would", "there", "their", "product"
    }]
    common = [w for w, _ in Counter(words).most_common(6)]

    positives = [r.get("review_text", "") for r in reviews if float(r.get("rating", 0)) >= 4][:2]
    negatives = [r.get("review_text", "") for r in reviews if float(r.get("rating", 0)) <= 2][:2]

    lines = [
        f"Product {batch.get('product_id')} received {len(reviews)} reviews with an average rating of {avg_rating}/5.",
        f"Common themes: {', '.join(common) if common else 'no strong repeated themes detected'}.",
    ]

    if positives:
        lines.append("Positive examples: " + " | ".join(positives))
    if negatives:
        lines.append("Negative examples: " + " | ".join(negatives))

    return "\n".join(lines)


def llm_summary(batch):
    reviews = batch.get("reviews", [])
    if not OPENAI_API_KEY:
        return fallback_summary(batch)

    client = OpenAI(
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL or None,
    )

    prompt = {
        "product_id": batch.get("product_id"),
        "review_count": batch.get("review_count"),
        "avg_rating": batch.get("avg_rating"),
        "reviews": [
            {
                "rating": r.get("rating"),
                "review_text": r.get("review_text"),
            }
            for r in reviews
        ],
    }

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.2,
        messages=[
            {
                "role": "system",
                "content": (
                    "You summarize customer reviews for product teams. "
                    "Return a concise summary with overall sentiment, top positives, top issues, "
                    "and one recommended action."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt),
            },
        ],
    )
    return response.choices[0].message.content.strip()


def connect_rabbitmq():
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    params = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        virtual_host=RABBITMQ_VHOST,
        credentials=credentials,
        heartbeat=60,
    )
    return pika.BlockingConnection(params)


def bootstrap_rabbitmq(channel):
    channel.exchange_declare(
        exchange=RABBITMQ_EXCHANGE,
        exchange_type=RABBITMQ_EXCHANGE_TYPE,
        durable=True,
    )
    channel.exchange_declare(
        exchange=RABBITMQ_DLX,
        exchange_type="topic",
        durable=True,
    )
    channel.queue_declare(queue=RABBITMQ_DLQ, durable=True)
    channel.queue_bind(exchange=RABBITMQ_DLX, queue=RABBITMQ_DLQ, routing_key="#")

    channel.queue_declare(
        queue=RABBITMQ_QUEUE,
        durable=True,
        arguments={
            "x-dead-letter-exchange": RABBITMQ_DLX,
        },
    )
    channel.queue_bind(
        exchange=RABBITMQ_EXCHANGE,
        queue=RABBITMQ_QUEUE,
        routing_key=RABBITMQ_ROUTING_KEY,
    )
    channel.basic_qos(prefetch_count=1)


def persist_summary(batch, summary_text):
    client = redis_client()
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    product_id = batch["product_id"]

    payload = {
        "product_id": product_id,
        "batch_id": batch.get("batch_id"),
        "review_count": batch.get("review_count"),
        "avg_rating": batch.get("avg_rating"),
        "generated_at": now,
        "summary": summary_text,
    }

    client.set(f"review-summary:{product_id}", json.dumps(payload))
    client.lpush(f"review-summary-history:{product_id}", json.dumps(payload))
    client.ltrim(f"review-summary-history:{product_id}", 0, 19)


def handle_message(channel, method, properties, body):
    try:
        batch = json.loads(body.decode("utf-8"))
        summary = llm_summary(batch)
        persist_summary(batch, summary)
        print(f"summary stored for product_id={batch['product_id']}")
        channel.basic_ack(delivery_tag=method.delivery_tag)
    except Exception as exc:
        print(f"failed to process message: {exc}")
        channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)


def main():
    while True:
        try:
            connection = connect_rabbitmq()
            channel = connection.channel()
            bootstrap_rabbitmq(channel)
            channel.basic_consume(
                queue=RABBITMQ_QUEUE,
                on_message_callback=handle_message,
            )
            print("summarizer started")
            channel.start_consuming()
        except Exception as exc:
            print(f"rabbitmq connection error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    main()
```

---

## `kafka-connect/README.md`

```md
# kafka-connect

This folder contains:

- a Dockerfile for a single-worker Kafka Connect image
- a connector config template for forwarding `product-review-batches` to RabbitMQ

Important:
- Set the correct RabbitMQ sink connector plugin in the image
- Update `connector.class` and plugin-specific RabbitMQ property names to match the plugin installed in your environment
```

## `kafka-connect/Dockerfile`

```dockerfile
FROM confluentinc/cp-kafka-connect:7.6.0

USER root
RUN mkdir -p /usr/share/java/custom-plugins/rabbitmq-sink
# Copy your RabbitMQ sink connector JARs here before build if you are baking a custom image.
# Example:
# COPY plugins/rabbitmq-sink/ /usr/share/java/custom-plugins/rabbitmq-sink/

ENV CONNECT_PLUGIN_PATH=/usr/share/java,/usr/share/confluent-hub-components,/usr/share/java/custom-plugins
USER appuser
```

## `kafka-connect/connector-review-batches-to-rabbitmq.json`

```json
{
  "name": "review-batches-to-rabbitmq",
  "config": {
    "connector.class": "REPLACE_WITH_YOUR_INSTALLED_RABBITMQ_SINK_CONNECTOR_CLASS",
    "tasks.max": "1",
    "topics": "product-review-batches",

    "key.converter": "org.apache.kafka.connect.storage.StringConverter",
    "value.converter": "org.apache.kafka.connect.storage.StringConverter",

    "rabbitmq.host": "reviews-rabbitmq.review-ai.svc.cluster.local",
    "rabbitmq.port": "5672",
    "rabbitmq.username": "guest",
    "rabbitmq.password": "guest",
    "rabbitmq.virtual.host": "/",
    "rabbitmq.exchange": "review.jobs",
    "rabbitmq.exchange.type": "topic",
    "rabbitmq.routing.key": "summary.standard",
    "rabbitmq.delivery.mode": "2"
  }
}
```

---

## `manifests/00-namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: review-ai
```

---

## `manifests/01-configmap.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: review-ai-config
  namespace: review-ai
data:
  KAFKA_BOOTSTRAP_SERVERS: "kafka.confluent.svc.cluster.local:9071"
  KAFKA_INPUT_TOPIC: "product-reviews"
  KAFKA_BATCH_TOPIC: "product-review-batches"
  KAFKA_AGGREGATOR_GROUP_ID: "review-aggregator"
  PRODUCE_INTERVAL_SECONDS: "1.5"

  AGGREGATOR_MAX_BATCH_SIZE: "10"
  AGGREGATOR_MAX_BATCH_AGE_SECONDS: "30"
  AGGREGATOR_POLL_TIMEOUT_SECONDS: "1.0"

  REDIS_HOST: "reviews-redis"
  REDIS_PORT: "6379"

  RABBITMQ_HOST: "reviews-rabbitmq"
  RABBITMQ_PORT: "5672"
  RABBITMQ_VHOST: "/"
  RABBITMQ_EXCHANGE: "review.jobs"
  RABBITMQ_EXCHANGE_TYPE: "topic"
  RABBITMQ_QUEUE: "review-summary-q"
  RABBITMQ_ROUTING_KEY: "summary.standard"
  RABBITMQ_DLX: "review.jobs.dlx"
  RABBITMQ_DLQ: "review-summary-dlq"

  OPENAI_MODEL: "gpt-4o-mini"

  KAFKA_CONNECT_URL: "http://reviews-kafka-connect:8083"
```

---

## `manifests/02-secrets.yaml`

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: review-ai-secrets
  namespace: review-ai
type: Opaque
stringData:
  RABBITMQ_DEFAULT_USER: "guest"
  RABBITMQ_DEFAULT_PASS: "guest"
  RABBITMQ_USER: "guest"
  RABBITMQ_PASSWORD: "guest"
  OPENAI_API_KEY: ""
  OPENAI_BASE_URL: ""
```

---

## `manifests/03-rabbitmq.yaml`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: rabbitmq-pvc
  namespace: review-ai
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 5Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reviews-rabbitmq
  namespace: review-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: reviews-rabbitmq
  template:
    metadata:
      labels:
        app: reviews-rabbitmq
    spec:
      containers:
        - name: rabbitmq
          image: rabbitmq:3-management
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 5672
              name: amqp
            - containerPort: 15672
              name: http
          env:
            - name: RABBITMQ_DEFAULT_USER
              valueFrom:
                secretKeyRef:
                  name: review-ai-secrets
                  key: RABBITMQ_DEFAULT_USER
            - name: RABBITMQ_DEFAULT_PASS
              valueFrom:
                secretKeyRef:
                  name: review-ai-secrets
                  key: RABBITMQ_DEFAULT_PASS
          volumeMounts:
            - name: rabbitmq-data
              mountPath: /var/lib/rabbitmq
          readinessProbe:
            exec:
              command: ["rabbitmq-diagnostics", "-q", "ping"]
            initialDelaySeconds: 15
            periodSeconds: 10
          livenessProbe:
            exec:
              command: ["rabbitmq-diagnostics", "-q", "ping"]
            initialDelaySeconds: 30
            periodSeconds: 20
      volumes:
        - name: rabbitmq-data
          persistentVolumeClaim:
            claimName: rabbitmq-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: reviews-rabbitmq
  namespace: review-ai
spec:
  selector:
    app: reviews-rabbitmq
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
    - name: management
      port: 15672
      targetPort: 15672
```

---

## `manifests/04-redis.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reviews-redis
  namespace: review-ai
spec:
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
          image: redis:7
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 6379
              name: redis
---
apiVersion: v1
kind: Service
metadata:
  name: reviews-redis
  namespace: review-ai
spec:
  selector:
    app: reviews-redis
  ports:
    - name: redis
      port: 6379
      targetPort: 6379
```

---

## `manifests/05-producer.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-producer
  namespace: review-ai
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
        - name: producer
          image: review-producer:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: review-ai-config
```

---

## `manifests/06-aggregator.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-aggregator
  namespace: review-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: review-aggregator
  template:
    metadata:
      labels:
        app: review-aggregator
    spec:
      containers:
        - name: aggregator
          image: review-aggregator:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: review-ai-config
```

---

## `manifests/07-summarizer.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: review-summarizer
  namespace: review-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: review-summarizer
  template:
    metadata:
      labels:
        app: review-summarizer
    spec:
      containers:
        - name: summarizer
          image: review-summarizer:latest
          imagePullPolicy: IfNotPresent
          envFrom:
            - configMapRef:
                name: review-ai-config
            - secretRef:
                name: review-ai-secrets
```

---

## `manifests/08-kafka-connect-single.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: reviews-kafka-connect
  namespace: review-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: reviews-kafka-connect
  template:
    metadata:
      labels:
        app: reviews-kafka-connect
    spec:
      containers:
        - name: kafka-connect
          image: review-kafka-connect:latest
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8083
              name: rest
          env:
            - name: CONNECT_BOOTSTRAP_SERVERS
              value: "kafka.confluent.svc.cluster.local:9071"
            - name: CONNECT_REST_PORT
              value: "8083"
            - name: CONNECT_GROUP_ID
              value: "review-connect-cluster"
            - name: CONNECT_CONFIG_STORAGE_TOPIC
              value: "review-connect-configs"
            - name: CONNECT_OFFSET_STORAGE_TOPIC
              value: "review-connect-offsets"
            - name: CONNECT_STATUS_STORAGE_TOPIC
              value: "review-connect-status"
            - name: CONNECT_CONFIG_STORAGE_REPLICATION_FACTOR
              value: "1"
            - name: CONNECT_OFFSET_STORAGE_REPLICATION_FACTOR
              value: "1"
            - name: CONNECT_STATUS_STORAGE_REPLICATION_FACTOR
              value: "1"
            - name: CONNECT_KEY_CONVERTER
              value: "org.apache.kafka.connect.storage.StringConverter"
            - name: CONNECT_VALUE_CONVERTER
              value: "org.apache.kafka.connect.storage.StringConverter"
            - name: CONNECT_PLUGIN_PATH
              value: "/usr/share/java,/usr/share/confluent-hub-components,/usr/share/java/custom-plugins"
          readinessProbe:
            httpGet:
              path: /
              port: 8083
            initialDelaySeconds: 20
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: reviews-kafka-connect
  namespace: review-ai
spec:
  selector:
    app: reviews-kafka-connect
  ports:
    - name: rest
      port: 8083
      targetPort: 8083
```

---

## `manifests/09-register-rabbitmq-connector.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: review-rabbitmq-connector-config
  namespace: review-ai
data:
  connector.json: |
    {
      "name": "review-batches-to-rabbitmq",
      "config": {
        "connector.class": "REPLACE_WITH_YOUR_INSTALLED_RABBITMQ_SINK_CONNECTOR_CLASS",
        "tasks.max": "1",
        "topics": "product-review-batches",
        "key.converter": "org.apache.kafka.connect.storage.StringConverter",
        "value.converter": "org.apache.kafka.connect.storage.StringConverter",
        "rabbitmq.host": "reviews-rabbitmq.review-ai.svc.cluster.local",
        "rabbitmq.port": "5672",
        "rabbitmq.username": "guest",
        "rabbitmq.password": "guest",
        "rabbitmq.virtual.host": "/",
        "rabbitmq.exchange": "review.jobs",
        "rabbitmq.exchange.type": "topic",
        "rabbitmq.routing.key": "summary.standard",
        "rabbitmq.delivery.mode": "2"
      }
    }
---
apiVersion: batch/v1
kind: Job
metadata:
  name: register-review-rabbitmq-connector
  namespace: review-ai
spec:
  template:
    spec:
      restartPolicy: OnFailure
      containers:
        - name: register
          image: curlimages/curl:8.7.1
          envFrom:
            - configMapRef:
                name: review-ai-config
          command:
            - /bin/sh
            - -c
            - |
              set -e
              until curl -sf ${KAFKA_CONNECT_URL}/connectors; do
                echo "waiting for kafka connect..."
                sleep 5
              done

              curl -sS -X PUT \
                ${KAFKA_CONNECT_URL}/connectors/review-batches-to-rabbitmq/config \
                -H "Content-Type: application/json" \
                --data @/config/connector.json
          volumeMounts:
            - name: connector-config
              mountPath: /config
      volumes:
        - name: connector-config
          configMap:
            name: review-rabbitmq-connector-config
```

---

## What changed

- **Removed direct Kafka consumption from the summarizer**
- **Inserted RabbitMQ as the worker buffer**
- **Used Kafka Connect as the Kafka-to-RabbitMQ handoff**
- **Kept Redis as the final summary store**
- **Added single-instance RabbitMQ deployment**
- **Added optional single-worker Kafka Connect deployment**
- **Added connector registration job for existing or new Connect service**

