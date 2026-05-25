Deployment for consumer app
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: orders-consumer
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: orders-consumer
  template:
    metadata:
      labels:
        app: orders-consumer
    spec:
      containers:
        - name: orders-consumer
          image: thecloudgarage/orders-consumer:latest
          imagePullPolicy: IfNotPresent
          env:
            - name: BOOTSTRAP_SERVERS
              value: "kafka.confluent.svc.cluster.local:9071"
            - name: KAFKA_TOPIC
              value: "orders"
            - name: GROUP_ID
              value: "orders-cli-consumer"
          resources:
            requests:
              cpu: "100m"
              memory: "128Mi"
            limits:
              cpu: "500m"
              memory: "256Mi"
```
