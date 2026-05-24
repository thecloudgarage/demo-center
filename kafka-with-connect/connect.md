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
apiVersion: platform.confluent.io/v1beta1
kind: Connect
metadata:
  name: kafka-connect
  namespace: confluent
spec:
  replicas: 2
  image:
    application: confluentinc/cp-server-connect:8.2.0
    init: confluentinc/confluent-init-container:3.2.0
  
  # Fetches the elasticsearch plugin dynamically on boot
  build:
    type: onDemand
    onDemand:
      plugins:
        confluentHub:
          - name: kafka-connect-elasticsearch
            owner: confluentinc
            version: 14.1.0
  
  # EXPOSE VIA EXTERNAL LOADBALANCER
  externalAccess:
    type: loadBalancer
    loadBalancer:
      domain: example.com       # Your domain name
#      prefix: kafkaconnect      # Exposes endpoint at: ://example.com
            
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9092
  podTemplate:
    resources:
      requests:
        cpu: "1"
        memory: "2Gi"
      limits:
        cpu: "2"
        memory: "2Gi"

```
```
cat <<EOF | kubectl apply -f -
apiVersion: platform.confluent.io/v1beta1
kind: Connector
metadata:
  name: elasticsearch-sink-connector
  namespace: confluent
spec:
  class: "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector"
  taskMax: 2
  connectClusterRef:
    name: kafka-connect # Must match the metadata.name of your Connect cluster
  configs:
    topics: "orders"
    connection.url: "http://elasticsearch.${ES_CLUSTER_NAME}-coord.svc.cluster.local:9200"
    type.name: "_doc"
    key.ignore: "true"
    schema.ignore: "true"
    # Optional security configurations if your Elasticsearch cluster uses basic auth:
    connection.username: "elastic"
    connection.password: "$ES_PW"
EOF


```
kubectl run -n confluent curl --rm -it --restart=Never \
  --image=curlimages/curl -- sh
```
```
cat > es-sink.json <<EOF
{
  "name": "es-sink",
  "config": {
    "connector.class": "io.confluent.connect.elasticsearch.ElasticsearchSinkConnector",
    "tasks.max": "2",
    "topics": "orders",
    "connection.url": "https://elasticsearch.single-es-coord.svc.cluster.local:9200",
    "connection.username": "elastic",
    "connection.password": "4660W1yRQRJ5AfPs92uk0pB",
    "elastic.security.protocol": "SSL",
    "elastic.https.ssl.truststore.location": "/certs/truststore.jks",
    "elastic.https.ssl.truststore.password": "changeit",
    "elastic.https.ssl.truststore.type": "JKS",
    "elastic.https.ssl.protocol": "TLS",
    "elastic.https.ssl.endpoint.identification.algorithm": "",
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
```
curl -X POST http://connect.confluent.svc.cluster.local:8083/connectors \
  -H "Content-Type: application/json" \
  -d @es-sink.json
```

