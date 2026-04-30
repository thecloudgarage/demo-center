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
        disabled: true
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
      "number_of_shards": 1,
      "number_of_replicas": 0,
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
