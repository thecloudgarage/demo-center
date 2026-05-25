Deployment for producer app
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-producer
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: orders-producer
  template:
    metadata:
      labels:
        app: orders-producer
    spec:
      containers:
        - name: orders-producer
          image: thecloudgarage/orders-producer:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: BOOTSTRAP_SERVERS
              value: "kafka.confluent.svc.cluster.local:9071"
            - name: KAFKA_TOPIC
              value: "orders"
            - name: INTERVAL_SECONDS
              value: "1.0"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```
