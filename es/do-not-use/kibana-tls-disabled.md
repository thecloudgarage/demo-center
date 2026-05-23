```
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: single-es-kb
  namespace: elasticsearch
spec:
  version: 8.13.0
  count: 1
  elasticsearchRef:
    name: single-es
  http:
    tls:
      selfSignedCertificate:
        disabled: true
    service:
      spec:
        type: LoadBalancer
```
