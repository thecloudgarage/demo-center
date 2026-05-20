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

curl -X POST "$CONNECT_URL/connectors" \
  -H "Content-Type: application/json" \
  -d @es-sink.json
```
