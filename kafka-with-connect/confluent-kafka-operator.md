```
kubectl create namespace confluent
kubectl config set-context --current --namespace confluent

helm repo add confluentinc https://packages.confluent.io/helm
helm repo update

helm upgrade --install confluent-operator confluentinc/confluent-for-kubernetes -n confluent
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
    application: confluentinc/cp-server
    init: confluentinc/confluent-init-container
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
    application: confluentinc/cp-server
    init: confluentinc/confluent-init-container
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
    application: confluentinc/cp-schema-registry
    init: confluentinc/confluent-init-container
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
    application: confluentinc/cp-kafka-rest
    init: confluentinc/confluent-init-container
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
    application: confluentinc/cp-ksqldb-server
    init: confluentinc/confluent-init-container
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
    init: confluentinc/confluent-init-container
  dependencies:
    kafka:
      bootstrapEndpoint: kafka.confluent.svc.cluster.local:9071
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
    application: confluentinc/cp-enterprise-control-center-next-gen
    init: confluentinc/confluent-init-container
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
