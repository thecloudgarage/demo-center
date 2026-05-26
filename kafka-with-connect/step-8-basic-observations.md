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
