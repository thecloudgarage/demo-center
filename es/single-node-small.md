```
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: prod-es
  namespace: logging
spec:
  version: 8.8.0

  http:
    tls:
      selfSignedCertificate:
        disabled: false
    service:
      spec:
        type: LoadBalancer
        # For kind/minikube/microk8s you might use NodePort instead:
        # type: NodePort

  nodeSets:
    - name: single-node
      count: 1
      config:
        # All roles on this one node
        node.roles:
          - master
          - data_hot
          - data_content
          - ingest
          - ml
          - transform
          - remote_cluster_client

        node.store.allow_mmap: false
        # In very small clusters you can leave discovery defaults; with count=1
        # this node will act as master and data.

      podTemplate:
        metadata:
          labels:
            es-node-type: single
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 4Gi
                limits:
                  cpu: "2"
                  memory: 8Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms4g -Xmx4g"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            # Replace with your StorageClass
            resources:
              requests:
                storage: 20Gi
---
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: prod-kibana
  namespace: logging
spec:
  version: 8.8.0
  count: 1
  elasticsearchRef:
    name: prod-es
  http:
    service:
      spec:
        type: LoadBalancer
  podTemplate:
    spec:
      containers:
        - name: kibana
          resources:
            requests:
              cpu: "250m"
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 2Gi
---
```
```
ES_PW=$(kubectl -n logging get secret prod-es-es-elastic-user -o go-template='{{.data.elastic | base64decode}}{{"\n"}}')
ES_SERVICE_HOST=$(kubectl -n logging get svc prod-es-es-http \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'; echo)
```
Lets create a product catalog index
```
curl -k -u "elastic:${ES_PW}" -X PUT "https://${ES_SERVICE_HOST}:9200/products" \
  -H 'Content-Type: application/json' \
  -d '{
    "mappings": {
      "properties": {
        "name":        { "type": "text" },
        "category":    { "type": "keyword" },
        "brand":       { "type": "keyword" },
        "price":       { "type": "float" },
        "in_stock":    { "type": "boolean" },
        "rating":      { "type": "float" },
        "tags":        { "type": "keyword" },
        "created_at":  { "type": "date" }
      }
    }
  }'
```
Lets insert some entries
```
curl -k -u "elastic:${ES_PW}" -X POST "https://${ES_SERVICE_HOST}:9200/products/_bulk" \
  -H 'Content-Type: application/json' \
  --data-binary @- <<'EOF'
{ "index": { "_id": 1 } }
{ "name": "XPS 13 Laptop", "category": "laptop", "brand": "Dell", "price": 1299.99, "in_stock": true,  "rating": 4.7, "tags": ["ultrabook","13-inch"],     "created_at": "2024-01-01T10:00:00Z" }
{ "index": { "_id": 2 } }
{ "name": "XPS 15 Laptop", "category": "laptop", "brand": "Dell", "price": 1799.99, "in_stock": true,  "rating": 4.6, "tags": ["creator","15-inch"],      "created_at": "2024-01-02T10:00:00Z" }
{ "index": { "_id": 3 } }
{ "name": "Latitude 7440", "category": "laptop", "brand": "Dell", "price": 1499.00, "in_stock": true,  "rating": 4.5, "tags": ["business","14-inch"],    "created_at": "2024-01-03T10:00:00Z" }
{ "index": { "_id": 4 } }
{ "name": "Precision 3581", "category": "workstation", "brand": "Dell", "price": 2199.00, "in_stock": true, "rating": 4.8, "tags": ["mobile-workstation"], "created_at": "2024-01-04T10:00:00Z" }
{ "index": { "_id": 5 } }
{ "name": "Alienware M16", "category": "laptop", "brand": "Dell", "price": 2499.00, "in_stock": true,  "rating": 4.9, "tags": ["gaming","16-inch"],      "created_at": "2024-01-05T10:00:00Z" }
{ "index": { "_id": 6 } }
{ "name": "Dell 27 Monitor", "category": "monitor", "brand": "Dell", "price": 349.99, "in_stock": true, "rating": 4.4, "tags": ["27-inch","QHD"],        "created_at": "2024-01-06T10:00:00Z" }
{ "index": { "_id": 7 } }
{ "name": "Dell 34 Curved Monitor", "category": "monitor", "brand": "Dell", "price": 699.99, "in_stock": true, "rating": 4.7, "tags": ["34-inch","ultrawide"], "created_at": "2024-01-07T10:00:00Z" }
{ "index": { "_id": 8 } }
{ "name": "Dell Pro Wireless Keyboard", "category": "accessory", "brand": "Dell", "price": 79.99, "in_stock": true, "rating": 4.2, "tags": ["keyboard","wireless"], "created_at": "2024-01-08T10:00:00Z" }
{ "index": { "_id": 9 } }
{ "name": "Dell Pro Wireless Mouse", "category": "accessory", "brand": "Dell", "price": 49.99, "in_stock": true, "rating": 4.3, "tags": ["mouse","wireless"], "created_at": "2024-01-09T10:00:00Z" }
{ "index": { "_id": 10 } }
{ "name": "Dell Thunderbolt Dock", "category": "accessory", "brand": "Dell", "price": 299.99, "in_stock": false, "rating": 4.6, "tags": ["dock","tb4"], "created_at": "2024-01-10T10:00:00Z" }
{ "index": { "_id": 11 } }
{ "name": "PowerEdge T150", "category": "server", "brand": "Dell", "price": 1399.00, "in_stock": true, "rating": 4.5, "tags": ["tower-server"], "created_at": "2024-01-11T10:00:00Z" }
{ "index": { "_id": 12 } }
{ "name": "PowerEdge R650", "category": "server", "brand": "Dell", "price": 4299.00, "in_stock": true, "rating": 4.8, "tags": ["rack-server","2U"], "created_at": "2024-01-12T10:00:00Z" }
{ "index": { "_id": 13 } }
{ "name": "PowerEdge R760", "category": "server", "brand": "Dell", "price": 5499.00, "in_stock": false, "rating": 4.9, "tags": ["rack-server","4th-gen-xeon"], "created_at": "2024-01-13T10:00:00Z" }
{ "index": { "_id": 14 } }
{ "name": "PowerStore 500", "category": "storage", "brand": "Dell", "price": 9999.00, "in_stock": true, "rating": 4.7, "tags": ["all-flash","midrange"], "created_at": "2024-01-14T10:00:00Z" }
{ "index": { "_id": 15 } }
{ "name": "PowerStore 1200", "category": "storage", "brand": "Dell", "price": 14999.00, "in_stock": true, "rating": 4.8, "tags": ["all-flash","enterprise"], "created_at": "2024-01-15T10:00:00Z" }
{ "index": { "_id": 16 } }
{ "name": "PowerFlex Appliance", "category": "storage", "brand": "Dell", "price": 24999.00, "in_stock": false, "rating": 4.9, "tags": ["scale-out","sds"], "created_at": "2024-01-16T10:00:00Z" }
{ "index": { "_id": 17 } }
{ "name": "VxRail E660", "category": "hci", "brand": "Dell", "price": 19999.00, "in_stock": true, "rating": 4.8, "tags": ["hci","vxf"], "created_at": "2024-01-17T10:00:00Z" }
{ "index": { "_id": 18 } }
{ "name": "VxRail P670F", "category": "hci", "brand": "Dell", "price": 29999.00, "in_stock": true, "rating": 4.9, "tags": ["hci","all-flash"], "created_at": "2024-01-18T10:00:00Z" }
{ "index": { "_id": 19 } }
{ "name": "Dell 2TB NVMe SSD", "category": "component", "brand": "Dell", "price": 399.99, "in_stock": true, "rating": 4.5, "tags": ["nvme","ssd"], "created_at": "2024-01-19T10:00:00Z" }
{ "index": { "_id": 20 } }
{ "name": "Dell 64GB DDR5 RDIMM", "category": "component", "brand": "Dell", "price": 499.99, "in_stock": true, "rating": 4.6, "tags": ["memory","ddr5"], "created_at": "2024-01-20T10:00:00Z" }
EOF
```
Lets verify these entries
```
curl -k -u "elastic:${ES_PW}" "https://${ES_SERVICE_HOST}:9200/products/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 20,
    "query": { "match_all": {} }
  }'
```
