```
apiVersion: elasticsearch.k8s.elastic.co/v1
kind: Elasticsearch
metadata:
  name: prod-es
  namespace: logging
spec:
  version: 8.8.0

  http:
    tls:
      selfSignedCertificate:
        disabled: false
    service:
      spec:
        type: LoadBalancer
        # For kind/minikube/microk8s you might use NodePort instead:
        # type: NodePort

  nodeSets:
    - name: single-node
      count: 1
      config:
        # All roles on this one node
        node.roles:
          - master
          - data_hot
          - data_content
          - ingest
          - ml
          - transform
          - remote_cluster_client

        node.store.allow_mmap: false
        # In very small clusters you can leave discovery defaults; with count=1
        # this node will act as master and data.

      podTemplate:
        metadata:
          labels:
            es-node-type: single
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 4Gi
                limits:
                  cpu: "2"
                  memory: 8Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms4g -Xmx4g"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            # Replace with your StorageClass
            resources:
              requests:
                storage: 20Gi
---
apiVersion: kibana.k8s.elastic.co/v1
kind: Kibana
metadata:
  name: prod-kibana
  namespace: logging
spec:
  version: 8.8.0
  count: 1
  elasticsearchRef:
    name: prod-es
  http:
    service:
      spec:
        type: LoadBalancer
  podTemplate:
    spec:
      containers:
        - name: kibana
          resources:
            requests:
              cpu: "250m"
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 2Gi
---
```
```
ES_PW=$(kubectl -n logging get secret prod-es-es-elastic-user -o go-template='{{.data.elastic | base64decode}}{{"\n"}}')
ES_SERVICE_HOST=$(kubectl -n logging get svc prod-es-es-http \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'; echo)
```
