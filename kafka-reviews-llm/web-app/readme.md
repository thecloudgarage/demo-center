# Product Review Lookup Web App

This app reads raw reviews from Elasticsearch index `raw-product-reviews` and returns the stored LLM summary from Redis.

## Project structure

```text
product-review-webapp/
├── app.py
├── requirements.txt
├── Dockerfile
├── templates/
│   └── index.html
└── k8s/
    └── review-webapp.yaml
```

---

## `requirements.txt`

```txt
Flask==3.0.3
elasticsearch==8.13.2
redis==5.0.8
gunicorn==22.0.0
```

---

## `app.py`

```python
import json
import os
from flask import Flask, jsonify, render_template, request
from elasticsearch import Elasticsearch
import redis

app = Flask(__name__)

ES_URL = os.getenv("ES_URL", "http://elasticsearch:9200")
ES_INDEX = os.getenv("ES_INDEX", "raw-product-reviews")
ES_USERNAME = os.getenv("ES_USERNAME", "")
ES_PASSWORD = os.getenv("ES_PASSWORD", "")

REDIS_HOST = os.getenv("REDIS_HOST", "reviews-redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_SUMMARY_KEY_PREFIX = os.getenv("REDIS_SUMMARY_KEY_PREFIX", "product_summary")

APP_PORT = int(os.getenv("APP_PORT", "8080"))
MAX_RESULTS = int(os.getenv("MAX_RESULTS", "200"))

def get_es_client():
    if ES_USERNAME and ES_PASSWORD:
        return Elasticsearch(
            ES_URL,
            basic_auth=(ES_USERNAME, ES_PASSWORD),
            verify_certs=False
        )
    return Elasticsearch(ES_URL, verify_certs=False)

def get_redis_client():
    return redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD or None,
        decode_responses=True
    )

def build_es_query(product_id: str, max_results: int):
    return {
        "size": max_results,
        "sort": [
            {"created_at": {"order": "desc", "unmapped_type": "date"}}
        ],
        "query": {
            "bool": {
                "should": [
                    {"term": {"product_id.keyword": product_id}},
                    {"term": {"product_id": product_id}}
                ],
                "minimum_should_match": 1
            }
        }
    }

def search_reviews(product_id: str):
    es = get_es_client()
    query = build_es_query(product_id, MAX_RESULTS)
    response = es.search(index=ES_INDEX, body=query)

    reviews = []
    for hit in response.get("hits", {}).get("hits", []):
        src = hit.get("_source", {})
        reviews.append({
            "review_id": src.get("review_id"),
            "product_id": src.get("product_id"),
            "product_name": src.get("product_name"),
            "category": src.get("category") or src.get("product_category"),
            "user_id": src.get("user_id"),
            "rating": src.get("rating"),
            "review_title": src.get("review_title"),
            "review_text": src.get("review_text"),
            "verified_purchase": src.get("verified_purchase"),
            "helpful_votes": src.get("helpful_votes"),
            "review_source": src.get("review_source"),
            "created_at": src.get("created_at"),
        })

    return reviews

def parse_json_field(value):
    if value is None:
        return None
    try:
        return json.loads(value)
    except Exception:
        return value

def get_summary(product_id: str):
    r = get_redis_client()
    key = f"{REDIS_SUMMARY_KEY_PREFIX}:{product_id}"
    data = r.hgetall(key)

    if not data:
        return None

    return {
        "product_id": data.get("product_id"),
        "product_name": data.get("product_name"),
        "category": data.get("category"),
        "batch_size": data.get("batch_size"),
        "average_rating": data.get("average_rating"),
        "ratings": parse_json_field(data.get("ratings")),
        "summary": data.get("summary"),
        "sentiment": data.get("sentiment"),
        "top_positive_points": parse_json_field(data.get("top_positive_points")),
        "top_negative_points": parse_json_field(data.get("top_negative_points")),
        "recommended_action": data.get("recommended_action"),
        "last_updated": data.get("last_updated"),
        "redis_key": key,
    }

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/healthz")
def healthz():
    return jsonify({"ok": True})

@app.get("/api/reviews")
def get_product_reviews():
    product_id = request.args.get("product_id", "").strip()

    if not product_id:
        return jsonify({"error": "product_id is required"}), 400

    try:
        reviews = search_reviews(product_id)
        summary = get_summary(product_id)

        return jsonify({
            "product_id": product_id,
            "review_count": len(reviews),
            "summary_found": summary is not None,
            "summary": summary,
            "reviews": reviews,
        })
    except Exception as e:
        return jsonify({
            "error": "Failed to retrieve product data",
            "details": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT, debug=False)
```

---

## `templates/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Product Review Lookup</title>
  <style>
    :root {
      --bg: #f5f5f7;
      --panel: #ffffff;
      --text: #1d1d1f;
      --muted: #6e6e73;
      --line: rgba(0, 0, 0, 0.08);
      --accent: #0071e3;
      --good: #1f8f4e;
      --warn: #b26a00;
      --bad: #b42318;
      --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 10px 28px rgba(0,0,0,0.05);
    }

    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }

    .shell {
      max-width: 1120px;
      margin: 0 auto;
      padding: 40px 20px 64px;
    }

    .hero {
      margin-bottom: 28px;
      animation: fadeUp .35s ease;
    }

    .eyebrow {
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
      margin-bottom: 8px;
    }

    h1 {
      margin: 0 0 10px;
      font-size: 34px;
      line-height: 1.15;
      font-weight: 600;
    }

    .sub {
      color: var(--muted);
      max-width: 760px;
      line-height: 1.55;
      font-size: 15px;
    }

    .searchbar {
      margin-top: 24px;
      background: rgba(255,255,255,0.72);
      backdrop-filter: blur(16px);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      display: flex;
      gap: 12px;
      align-items: center;
      box-shadow: var(--shadow);
      animation: fadeUp .4s ease;
    }

    .searchbar input {
      flex: 1;
      border: 1px solid var(--line);
      background: #fff;
      color: var(--text);
      border-radius: 12px;
      padding: 14px 16px;
      font-size: 15px;
      outline: none;
      transition: box-shadow .2s ease, border-color .2s ease;
    }

    .searchbar input:focus {
      border-color: rgba(0, 113, 227, 0.4);
      box-shadow: 0 0 0 3px rgba(0, 113, 227, 0.18);
    }

    .searchbar button {
      border: none;
      background: var(--accent);
      color: white;
      border-radius: 12px;
      padding: 14px 18px;
      font-size: 15px;
      font-weight: 600;
      cursor: pointer;
      transition: background-color .2s ease, transform .15s ease, opacity .2s ease;
    }

    .searchbar button:hover { opacity: .94; }
    .searchbar button:active { transform: scale(.98); }

    .status {
      margin-top: 12px;
      min-height: 20px;
      color: var(--muted);
      font-size: 14px;
    }

    .grid {
      display: grid;
      grid-template-columns: 1.1fr 1.9fr;
      gap: 20px;
      margin-top: 28px;
    }

    .card {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 20px;
      box-shadow: var(--shadow);
      animation: fadeUp .45s ease;
    }

    .card h2 {
      margin: 0 0 14px;
      font-size: 18px;
      line-height: 1.2;
    }

    .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-bottom: 16px;
    }

    .pill {
      border-radius: 999px;
      padding: 8px 12px;
      background: #f8f8fa;
      border: 1px solid var(--line);
      font-size: 13px;
      color: var(--muted);
    }

    .sentiment-positive { color: var(--good); }
    .sentiment-mixed { color: var(--warn); }
    .sentiment-negative { color: var(--bad); }

    .summary-block {
      margin-top: 14px;
    }

    .summary-block h3 {
      margin: 0 0 8px;
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }

    .summary-block p, .summary-block li {
      margin: 0;
      line-height: 1.55;
      font-size: 14px;
    }

    .summary-block ul {
      margin: 0;
      padding-left: 18px;
    }

    .review-list {
      display: grid;
      gap: 14px;
    }

    .review {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 16px;
      background: #fff;
      transition: transform .15s ease, box-shadow .2s ease, background-color .2s ease;
    }

    .review:hover {
      transform: translateY(-1px);
      box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 8px 20px rgba(0,0,0,0.04);
      background: #fcfcfd;
    }

    .review-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
      margin-bottom: 10px;
    }

    .review-title {
      font-weight: 600;
      font-size: 15px;
    }

    .review-rating {
      font-size: 13px;
      color: var(--muted);
      white-space: nowrap;
    }

    .review-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 10px;
    }

    .review-text {
      line-height: 1.6;
      font-size: 14px;
    }

    .empty {
      color: var(--muted);
      font-size: 14px;
      padding: 8px 0;
    }

    .hidden { display: none; }

    @keyframes fadeUp {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media screen and (max-width: 860px) {
      .grid {
        grid-template-columns: 1fr;
      }

      .searchbar {
        flex-direction: column;
        align-items: stretch;
      }

      .searchbar button {
        width: 100%;
      }
    }

    @media print {
      body {
        margin: 0;
        padding: 0.4in 0.6in;
        background: #fff;
        print-color-adjust: exact;
        -webkit-print-color-adjust: exact;
      }

      .shell, main {
        max-width: 100% !important;
        width: 100% !important;
      }

      .card, .review {
        break-inside: avoid;
        box-shadow: none !important;
      }

      button {
        display: none !important;
      }

      *, *::before, *::after {
        animation: none !important;
        transition: none !important;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="eyebrow">Review Explorer</div>
      <h1>Find reviews and the latest LLM summary for a product.</h1>
      <div class="sub">
        Enter a product ID to fetch raw reviews from Elasticsearch and the latest summary from Redis.
      </div>

      <div class="searchbar">
        <input id="productIdInput" type="text" placeholder="Enter product ID, e.g. P1001" />
        <button id="searchBtn">Search</button>
      </div>

      <div id="status" class="status"></div>
    </section>

    <section id="results" class="grid hidden">
      <div class="card">
        <h2>Summary</h2>
        <div id="summaryMeta" class="meta"></div>

        <div class="summary-block">
          <h3>Overview</h3>
          <p id="summaryText" class="empty">No summary loaded.</p>
        </div>

        <div class="summary-block">
          <h3>Top positive points</h3>
          <ul id="positivePoints"></ul>
        </div>

        <div class="summary-block">
          <h3>Top negative points</h3>
          <ul id="negativePoints"></ul>
        </div>

        <div class="summary-block">
          <h3>Recommended action</h3>
          <p id="recommendedAction" class="empty"></p>
        </div>
      </div>

      <div class="card">
        <h2>Reviews</h2>
        <div id="reviewsMeta" class="meta"></div>
        <div id="reviewList" class="review-list"></div>
      </div>
    </section>
  </main>

  <script>
    const input = document.getElementById("productIdInput");
    const button = document.getElementById("searchBtn");
    const statusEl = document.getElementById("status");
    const resultsEl = document.getElementById("results");

    const summaryMetaEl = document.getElementById("summaryMeta");
    const summaryTextEl = document.getElementById("summaryText");
    const positivePointsEl = document.getElementById("positivePoints");
    const negativePointsEl = document.getElementById("negativePoints");
    const recommendedActionEl = document.getElementById("recommendedAction");

    const reviewsMetaEl = document.getElementById("reviewsMeta");
    const reviewListEl = document.getElementById("reviewList");

    function escapeHtml(value) {
      return (value ?? "")
        .toString()
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function setStatus(message) {
      statusEl.textContent = message;
    }

    function renderList(el, items) {
      el.innerHTML = "";
      if (!items || !items.length) {
        el.innerHTML = `<li class="empty">No items available.</li>`;
        return;
      }
      items.forEach(item => {
        const li = document.createElement("li");
        li.textContent = item;
        el.appendChild(li);
      });
    }

    function renderSummary(summary) {
      summaryMetaEl.innerHTML = "";

      if (!summary) {
        summaryTextEl.textContent = "No Redis summary found for this product.";
        recommendedActionEl.textContent = "";
        renderList(positivePointsEl, []);
        renderList(negativePointsEl, []);
        return;
      }

      const meta = [
        summary.product_name ? `Product: ${summary.product_name}` : null,
        summary.category ? `Category: ${summary.category}` : null,
        summary.average_rating ? `Average rating: ${summary.average_rating}` : null,
        summary.batch_size ? `Batch size: ${summary.batch_size}` : null,
        summary.sentiment ? `Sentiment: ${summary.sentiment}` : null,
        summary.last_updated ? `Updated: ${summary.last_updated}` : null
      ].filter(Boolean);

      meta.forEach(text => {
        const div = document.createElement("div");
        div.className = "pill";
        if (text.toLowerCase().startsWith("sentiment:")) {
          const lower = text.toLowerCase();
          if (lower.includes("positive")) div.classList.add("sentiment-positive");
          if (lower.includes("mixed")) div.classList.add("sentiment-mixed");
          if (lower.includes("negative")) div.classList.add("sentiment-negative");
        }
        div.textContent = text;
        summaryMetaEl.appendChild(div);
      });

      summaryTextEl.textContent = summary.summary || "No summary text available.";
      recommendedActionEl.textContent = summary.recommended_action || "No recommendation available.";
      renderList(positivePointsEl, summary.top_positive_points || []);
      renderList(negativePointsEl, summary.top_negative_points || []);
    }

    function renderReviews(productId, reviews) {
      reviewsMetaEl.innerHTML = "";
      reviewListEl.innerHTML = "";

      const meta = document.createElement("div");
      meta.className = "pill";
      meta.textContent = `Product ID: ${productId} · Reviews: ${reviews.length}`;
      reviewsMetaEl.appendChild(meta);

      if (!reviews.length) {
        reviewListEl.innerHTML = `<div class="empty">No reviews found in Elasticsearch.</div>`;
        return;
      }

      reviews.forEach(review => {
        const card = document.createElement("div");
        card.className = "review";
        card.innerHTML = `
          <div class="review-top">
            <div class="review-title">${escapeHtml(review.review_title || "Untitled review")}</div>
            <div class="review-rating">Rating: ${escapeHtml(review.rating ?? "N/A")}/5</div>
          </div>
          <div class="review-meta">
            ${review.product_name ? `<span>${escapeHtml(review.product_name)}</span>` : ""}
            ${review.category ? `<span>${escapeHtml(review.category)}</span>` : ""}
            ${review.user_id ? `<span>User: ${escapeHtml(review.user_id)}</span>` : ""}
            ${review.review_source ? `<span>Source: ${escapeHtml(review.review_source)}</span>` : ""}
            ${review.verified_purchase !== null && review.verified_purchase !== undefined ? `<span>Verified: ${escapeHtml(review.verified_purchase)}</span>` : ""}
            ${review.helpful_votes !== null && review.helpful_votes !== undefined ? `<span>Helpful: ${escapeHtml(review.helpful_votes)}</span>` : ""}
            ${review.created_at ? `<span>${escapeHtml(review.created_at)}</span>` : ""}
          </div>
          <div class="review-text">${escapeHtml(review.review_text || "")}</div>
        `;
        reviewListEl.appendChild(card);
      });
    }

    async function search() {
      const productId = input.value.trim();
      if (!productId) {
        setStatus("Enter a product ID first.");
        input.focus();
        return;
      }

      setStatus(`Loading data for ${productId}...`);
      resultsEl.classList.add("hidden");

      try {
        const res = await fetch(`/api/reviews?product_id=${encodeURIComponent(productId)}`);
        const data = await res.json();

        if (!res.ok) {
          throw new Error(data.details || data.error || "Request failed");
        }

        renderSummary(data.summary);
        renderReviews(data.product_id, data.reviews || []);
        resultsEl.classList.remove("hidden");
        setStatus(`Loaded ${data.review_count} review(s) for ${data.product_id}.`);
      } catch (err) {
        setStatus(`Failed to load product data: ${err.message}`);
      }
    }

    button.addEventListener("click", search);
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") search();
    });
  </script>
</body>
</html>
```

---

## `Dockerfile`

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates ./templates

ENV PYTHONUNBUFFERED=1
ENV APP_PORT=8080

EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

---

## `k8s/review-webapp.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: product-review-webapp-config
  namespace: review-ai
data:
  ES_URL: "http://elasticsearch:9200"
  ES_INDEX: "raw-product-reviews"
  REDIS_HOST: "reviews-redis"
  REDIS_PORT: "6379"
  REDIS_DB: "0"
  REDIS_SUMMARY_KEY_PREFIX: "product_summary"
  APP_PORT: "8080"
  MAX_RESULTS: "200"
---
apiVersion: v1
kind: Secret
metadata:
  name: product-review-webapp-secrets
  namespace: review-ai
type: Opaque
stringData:
  ES_USERNAME: ""
  ES_PASSWORD: ""
  REDIS_PASSWORD: ""
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: product-review-webapp
  namespace: review-ai
spec:
  replicas: 1
  selector:
    matchLabels:
      app: product-review-webapp
  template:
    metadata:
      labels:
        app: product-review-webapp
    spec:
      containers:
        - name: webapp
          image: YOUR_REGISTRY/product-review-webapp:1.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8080
          envFrom:
            - configMapRef:
                name: product-review-webapp-config
            - secretRef:
                name: product-review-webapp-secrets
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 5
            periodSeconds: 10
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8080
            initialDelaySeconds: 15
            periodSeconds: 20
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"
---
apiVersion: v1
kind: Service
metadata:
  name: product-review-webapp
  namespace: review-ai
spec:
  selector:
    app: product-review-webapp
  ports:
    - name: http
      port: 80
      targetPort: 8080
```

---

## Build and run

```bash
docker build -t YOUR_REGISTRY/product-review-webapp:1.0.0 .
docker push YOUR_REGISTRY/product-review-webapp:1.0.0

kubectl apply -f k8s/review-webapp.yaml
```

---

## What the app does

- `GET /` serves the single-page UI
- `GET /api/reviews?product_id=P1001` returns:
  - all raw reviews from Elasticsearch for that product
  - the latest LLM summary from Redis for that product

Example response shape:

```json
{
  "product_id": "P1001",
  "review_count": 12,
  "summary_found": true,
  "summary": {
    "product_id": "P1001",
    "product_name": "Premium Laptop Elite 1",
    "category": "Laptop",
    "batch_size": "5",
    "average_rating": "4.4",
    "ratings": [5, 4, 4, 5, 4],
    "summary": "Customers consistently praise performance and screen quality, with some mention of battery variability.",
    "sentiment": "positive",
    "top_positive_points": ["Strong performance", "Sharp display", "Good build quality"],
    "top_negative_points": ["Battery inconsistency"],
    "recommended_action": "Investigate battery tuning and keep positioning around performance.",
    "last_updated": "2026-05-27T10:20:30.123456+00:00",
    "redis_key": "product_summary:P1001"
  },
  "reviews": []
}
```
