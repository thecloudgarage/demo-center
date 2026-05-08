```
kubectl create -f https://download.elastic.co/downloads/eck/2.8.0/crds.yaml
kubectl apply  -f https://download.elastic.co/downloads/eck/2.8.0/operator.yaml
```
```
apiVersion: v1
kind: Namespace
metadata:
  name: elasticsearch
---
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: single-es
  namespace: elasticsearch
spec:
  version: 8.13.0

  # Simplify for lab/dev: disable HTTPS & security (optional)
  http:
    tls:
      selfSignedCertificate:
        disabled: false
  secureSettings: []
  # You can also add:
  # config:
  #   xpack.security.enabled: false

  nodeSets:
    # 1) Master node (single)
    - name: master
      count: 1
      config:
        node.roles: ["master", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            role: master
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "500m"
                  memory: "1Gi"
                limits:
                  cpu: "500m"
                  memory: "1Gi"
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms512m -Xmx512m"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi
            # storageClassName: standard   # set if you need a specific class

    # 2) Coordinating-only (ingest gateway / HTTP entry)
    - name: coord
      count: 1
      config:
        # Empty role list => coordinating-only node
        node.roles: []
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            role: coord
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "500m"
                  memory: "1Gi"
                limits:
                  cpu: "500m"
                  memory: "1Gi"
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms512m -Xmx512m"
      # No volume claim: coord node does not persist data

    # 3) Hot data nodes (2x)
    - name: data-hot
      count: 2
      config:
        node.roles: ["data_hot", "data_content", "ingest", "remote_cluster_client"]
        node.attr.data: "hot"
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            role: data-hot
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "2"
                  memory: "3Gi"
                limits:
                  cpu: "2"
                  memory: "3Gi"
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi
            # storageClassName: standard

    # 4) Warm data node (1x)
    - name: data-warm
      count: 1
      config:
        node.roles: ["data_warm", "data_content", "remote_cluster_client"]
        node.attr.data: "warm"
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            role: data-warm
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1500m"
                  memory: "3Gi"
                limits:
                  cpu: "1500m"
                  memory: "3Gi"
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi
            # storageClassName: standard
---
# Optional: Service that points specifically at the coordinating-only node
apiVersion: v1
kind: Service
metadata:
  name: single-es-coord
  namespace: elasticsearch
spec:
  type: LoadBalancer
  selector:
    elasticsearch.k8s.elastic.co/cluster-name: single-es
    role: coord
  ports:
    - name: http
      port: 9200
      targetPort: 9200
---
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: single-es-kb
  namespace: elasticsearch
spec:
  version: 8.13.0
  count: 1
  elasticsearchRef:
    name: single-es
  http:
    service:
      spec:
        type: LoadBalancer
```
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
curl -k -u "elastic:${ES_PW}" -X PUT "https://${ES_SERVICE_HOST}:9200/products" \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": {
      "number_of_shards": 2,
      "number_of_replicas": 1,
      "index.routing.allocation.include.data": "hot"
    },
    "mappings": {
      "properties": {
        "product_id":   { "type": "keyword" },
        "name":         { "type": "text", "fields": { "keyword": { "type": "keyword" } } },
        "category":     { "type": "keyword" },
        "price":        { "type": "double" },
        "in_stock":     { "type": "boolean" },
        "tags":         { "type": "keyword" },
        "created_at":   { "type": "date" },
        "description":  { "type": "text" }
      }
    }
  }'
```
Insert products
```
curl -k -u "elastic:${ES_PW}" -X POST "https://${ES_SERVICE_HOST}:9200/products/_bulk?refresh=true" \
  -H 'Content-Type: application/json' \
  -d '
{ "index": { "_id": "1" } }
{ "product_id": "SKU-1001", "name": "Dell 24\" Full HD Monitor", "category": "monitors", "price": 149.99, "in_stock": true,  "tags": ["display","1080p","office"], "created_at": "2025-01-10T10:00:00Z", "description": "24-inch Full HD IPS monitor suitable for productivity workloads." }
{ "index": { "_id": "2" } }
{ "product_id": "SKU-1002", "name": "Dell Wired Keyboard and Mouse Combo", "category": "peripherals", "price": 39.99, "in_stock": true,  "tags": ["keyboard","mouse","bundle"], "created_at": "2025-02-01T09:30:00Z", "description": "Compact wired keyboard and mouse combo for everyday office use." }
{ "index": { "_id": "3" } }
{ "product_id": "SKU-1003", "name": "Dell USB-C Dock", "category": "docking_stations", "price": 189.00, "in_stock": false, "tags": ["usb-c","dock","laptop"], "created_at": "2025-03-05T14:15:00Z", "description": "USB-C dock providing power delivery and multiple display outputs." }
{ "index": { "_id": "4" } }
{ "product_id": "SKU-1004", "name": "Dell 27\" QHD Monitor", "category": "monitors", "price": 299.99, "in_stock": true,  "tags": ["display","1440p"], "created_at": "2025-03-15T08:00:00Z", "description": "27-inch QHD monitor for detailed productivity and light creative work." }
{ "index": { "_id": "5" } }
{ "product_id": "SKU-1005", "name": "Dell Bluetooth Mouse", "category": "peripherals", "price": 24.99, "in_stock": true,  "tags": ["mouse","wireless"], "created_at": "2025-03-20T12:30:00Z", "description": "Compact Bluetooth mouse ideal for mobile workers." }
{ "index": { "_id": "6" } }
{ "product_id": "SKU-1006", "name": "Dell USB-C Travel Adapter", "category": "adapters", "price": 49.99, "in_stock": true,  "tags": ["usb-c","adapter","travel"], "created_at": "2025-03-25T11:00:00Z", "description": "Multiport USB-C travel adapter for HDMI, USB-A, and Ethernet." }
{ "index": { "_id": "7" } }
{ "product_id": "SKU-1007", "name": "Dell 15\" Laptop Sleeve", "category": "accessories", "price": 29.99, "in_stock": true,  "tags": ["sleeve","laptop","15-inch"], "created_at": "2025-03-28T16:45:00Z", "description": "Protective neoprene sleeve for 15-inch laptops." }
{ "index": { "_id": "8" } }
{ "product_id": "SKU-1008", "name": "Dell Noise-Cancelling Headset", "category": "audio", "price": 89.99, "in_stock": true,  "tags": ["headset","noise-cancelling","usb"], "created_at": "2025-04-01T09:00:00Z", "description": "USB headset with active noise cancellation for calls and meetings." }
{ "index": { "_id": "9" } }
{ "product_id": "SKU-1009", "name": "Dell Portable SSD 1TB", "category": "storage", "price": 129.99, "in_stock": true,  "tags": ["ssd","portable","usb-c"], "created_at": "2025-04-02T10:20:00Z", "description": "1TB USB-C portable SSD with high transfer speeds." }
{ "index": { "_id": "10" } }
{ "product_id": "SKU-1010", "name": "Dell USB-C Hub 4-Port", "category": "adapters", "price": 34.99, "in_stock": true,  "tags": ["usb-c","hub","4-port"], "created_at": "2025-04-03T13:10:00Z", "description": "4-port USB-C hub for connecting multiple USB-A devices." }
{ "index": { "_id": "11" } }
{ "product_id": "SKU-1011", "name": "Dell 34\" Curved Monitor", "category": "monitors", "price": 599.99, "in_stock": false, "tags": ["display","ultrawide","curved"], "created_at": "2025-04-05T08:30:00Z", "description": "34-inch curved ultrawide monitor for immersive multitasking." }
{ "index": { "_id": "12" } }
{ "product_id": "SKU-1012", "name": "Dell Wireless Keyboard", "category": "peripherals", "price": 49.99, "in_stock": true,  "tags": ["keyboard","wireless"], "created_at": "2025-04-06T11:25:00Z", "description": "Full-size wireless keyboard with low-profile keys." }
{ "index": { "_id": "13" } }
{ "product_id": "SKU-1013", "name": "Dell Wireless Presenter", "category": "accessories", "price": 39.99, "in_stock": true,  "tags": ["presenter","wireless","laser"], "created_at": "2025-04-07T15:40:00Z", "description": "Wireless presenter with built-in laser pointer." }
{ "index": { "_id": "14" } }
{ "product_id": "SKU-1014", "name": "Dell 65W USB-C Power Adapter", "category": "power", "price": 59.99, "in_stock": true,  "tags": ["charger","usb-c","65w"], "created_at": "2025-04-08T10:05:00Z", "description": "65W USB-C power adapter compatible with most Dell laptops." }
{ "index": { "_id": "15" } }
{ "product_id": "SKU-1015", "name": "Dell Laptop Stand", "category": "accessories", "price": 44.99, "in_stock": true,  "tags": ["stand","ergonomic","laptop"], "created_at": "2025-04-09T09:50:00Z", "description": "Ergonomic aluminum laptop stand for better viewing angles." }
{ "index": { "_id": "16" } }
{ "product_id": "SKU-1016", "name": "Dell Dual Monitor Arm", "category": "accessories", "price": 179.99, "in_stock": true,  "tags": ["monitor-arm","dual","mount"], "created_at": "2025-04-10T14:15:00Z", "description": "Adjustable dual monitor arm for 24-27 inch displays." }
{ "index": { "_id": "17" } }
{ "product_id": "SKU-1017", "name": "Dell USB Speakerphone", "category": "audio", "price": 129.99, "in_stock": true,  "tags": ["speakerphone","usb","conference"], "created_at": "2025-04-11T13:35:00Z", "description": "Compact USB speakerphone for small conference rooms." }
{ "index": { "_id": "18" } }
{ "product_id": "SKU-1018", "name": "Dell 2TB External HDD", "category": "storage", "price": 89.99, "in_stock": true,  "tags": ["hdd","external","usb-3"], "created_at": "2025-04-12T16:00:00Z", "description": "2TB USB 3.0 external hard drive for backups and archives." }
{ "index": { "_id": "19" } }
{ "product_id": "SKU-1019", "name": "Dell USB-C to HDMI Adapter", "category": "adapters", "price": 24.99, "in_stock": true,  "tags": ["usb-c","hdmi","video"], "created_at": "2025-04-13T09:20:00Z", "description": "USB-C to HDMI adapter supporting up to 4K resolution." }
{ "index": { "_id": "20" } }
{ "product_id": "SKU-1020", "name": "Dell Webcam Full HD", "category": "audio_video", "price": 79.99, "in_stock": true,  "tags": ["webcam","1080p","usb"], "created_at": "2025-04-14T11:10:00Z", "description": "Full HD USB webcam optimized for conferencing." }
'
```
Lets check the existing tier
```
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/products/_settings?pretty" \
  -H 'Content-Type: application/json'
```
Lets check the shards
```
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/_cat/shards/products?v"
```
Lets retrieve all products
```
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/products/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 1000,
    "query": {
      "match_all": {}
    }
  }'
```
Lets retrieve a product by fuzzy match
```
SEARCH_TERM="monitor"
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/products/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d "{
    \"size\": 20,
    \"query\": {
      \"fuzzy\": {
        \"name\": {
          \"value\": \"${SEARCH_TERM}\",
          \"fuzziness\": \"AUTO\"
        }
      }
    }
  }"
```
Lets change the index to a warm tier manually (ILM is also possible via policy)
```
curl -k -u "elastic:${ES_PW}" -X PUT "https://${ES_SERVICE_HOST}:9200/products/_settings" \
  -H 'Content-Type: application/json' \
  -d '{
    "index": {
      "routing": {
        "allocation": {
          "include": {
            "data": "warm"
          }
        }
      },
      "blocks": {
        "write": true
      }
    }
  }'
```
Lets check the new tier
```
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/products/_settings?pretty" \
  -H 'Content-Type: application/json'
```
Lets check the shards reallocation to the warm node
```
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/_cat/shards/products?v"
```
Accessing Kibana
```
username: elastic
Password:
kubectl get secret single-es-es-elastic-user -n elasticsearch -o go-template='{{.data.elastic | base64decode}}{{"\n"}}'
```
