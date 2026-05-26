```
curl -k -u "elastic:${ES_PW}" -X GET "https://${ES_SERVICE_HOST}:9200/orders/_settings?pretty" \
  -H 'Content-Type: application/json'
```
