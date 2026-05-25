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
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: connect-pod-overlay
  namespace: confluent
data:
  pod-template.yaml: |
    spec:
      containers:
        - name: connect
          env:
            - name: KAFKA_OPTS
              # This fixes BOTH the Jackson error and the SSL check revocation
              value: "-Dcom.fasterxml.jackson.core.util.BufferRecyclers.trackReusableBuffers=false -Dcom.sun.net.ssl.checkRevocation=false"
EOF
```
```
apiVersion: platform.confluent.io/v1beta1
kind: Connect
metadata:
  name: kafka-connect
  namespace: confluent
  annotations:
    # Reference the overlay ConfigMap
    platform.confluent.io/pod-overlay-configmap-name: connect-pod-overlay
spec:
  replicas: 1
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
            version: 15.1.1
          # ADDED: MongoDB Connector
          - name: kafka-connect-mongodb
            owner: mongodb
            version: 1.13.0

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
    # CFK v1beta1 correct field for probes
    probe:
      readiness:
        initialDelaySeconds: 180
        periodSeconds: 20
    # CFK v1beta1 correct field for resources
    resources:
      requests:
        cpu: "1"
        memory: "4Gi"
      limits:
        cpu: "2"
        memory: "4Gi"
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
    connection.url: "http://${ES_SERVICE_HOST}:9200"
    type.name: "_doc"
    key.ignore: "true"
    schema.ignore: "true"
    elastic.security.protocol: "SSL"
    elastic.https.ssl.endpoint.identification.algorithm: ""
    elastic.https.ssl.keystore.type: "JKS"
    # Optional security configurations if your Elasticsearch cluster uses basic auth:
    connection.username: "elastic"
    connection.password: "$ES_PW"
    value.converter: "org.apache.kafka.connect.json.JsonConverter"
    value.converter.schemas.enable: "false"
    
    # If your message keys are also plain strings/JSON, add these:
    key.converter: "org.apache.kafka.connect.storage.StringConverter"
EOF
```
MongoDB sink connector
```
cat <<EOF | kubectl apply -f -
apiVersion: platform.confluent.io/v1beta1
kind: Connector
metadata:
  name: mongodb-sink-connector
  namespace: confluent
spec:
  class: "com.mongodb.kafka.connect.MongoSinkConnector"
  taskMax: 1
  connectClusterRef:
    name: kafka-connect 
  configs:
    topics: "orders"
    connection.uri: "mongodb://mongo-user:mongo-pass@mongodb.mongodb.svc.cluster.local:27017"
    database: "inventory"
    collection: "orders_sink"

    # Converters
    key.converter: "org.apache.kafka.connect.storage.StringConverter"
    value.converter: "org.apache.kafka.connect.json.JsonConverter"
    value.converter.schemas.enable: "false"

    # THE FIX: Use UuidStrategy for raw string UUIDs
    document.id.strategy: "com.mongodb.kafka.connect.sink.processor.id.strategy.UuidStrategy"
    
    # Alternative Fix: If UuidStrategy class isn't found, use PartialKeyStrategy
    # with a field name, but UuidStrategy is preferred for your data.
    
    writemodel.strategy: "com.mongodb.kafka.connect.sink.writemodel.strategy.ReplaceOneDefaultStrategy"
    is.upsert: "true"
    
    # Force the key to be handled as a literal
    key.projection.type: "none"
EOF
```
CONNECTOR STATUS
```
CONNECT_CLUSTER_NAME=kafka-connect
CONNECT_SERVICE_HOST=$(kubectl -n confluent get svc "${CONNECT_CLUSTER_NAME}-bootstrap-lb" \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'; echo)
#Replace the connector name in the below command
curl http://${CONNECT_SERVICE_HOST}/connectors/elasticsearch-sink-connector/status | jq
curl http://${CONNECT_SERVICE_HOST}/connectors/mongodb-sink-connector/status | jq
#To view the the partitions that are being consumed by connectors
curl http://${CONNECT_SERVICE_HOST}/connectors/elasticsearch-sink-connector/offsets | jq
curl http://${CONNECT_SERVICE_HOST}/connectors/mongodb-sink-connector/offsets | jq
#To view exact assignment of connector tasks and partitions they are reading from
#
kubectl exec -it kafka-connect-0 -n confluent -- kafka-consumer-groups \
  --bootstrap-server kafka.confluent.svc.cluster.local:9092 \
  --describe --group connect-elasticsearch-sink-connector
#
kubectl exec -it kafka-connect-0 -n confluent -- kafka-consumer-groups \
  --bootstrap-server kafka.confluent.svc.cluster.local:9092 \
  --describe --group connect-mongodb-sink-connector

```
