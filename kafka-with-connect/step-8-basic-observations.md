ElasticSearch Index for Orders
```
curl -k -u "elastic:${ES_PW}" -X GET "http://${ES_SERVICE_HOST}:9200/orders/_settings?pretty" \
  -H 'Content-Type: application/json'
```
ElasticSearch Data for Orders Index
```
curl -k -u "elastic:${ES_PW}" -X GET "http://${ES_SERVICE_HOST}:9200/orders/_search?pretty" \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 1000,
    "query": {
      "match_all": {}
    }
  }'
```
Viewing data in Kibana. Retrieve the password and username is elastic. Note that Kibana is running as HTTP and port 5601
```
kubectl get secret single-es-es-elastic-user -n elasticsearch -o go-template='{{.data.elastic | base64decode}}{{"\n"}}'
```
