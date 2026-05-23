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

