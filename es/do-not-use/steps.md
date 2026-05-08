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
        # Optionally pin an external IP if your environment supports it
        # externalIPs:
        #   - 192.0.2.10

  # Each nodeSet becomes a StatefulSet with specific roles
  nodeSets:
    # 1) MASTER NODES (cluster-manager)
    - name: masters
      count: 1
      config:
        node.roles: ["master", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: master
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          # Spread masters across nodes
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: master
                    topologyKey: "kubernetes.io/hostname"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi

    # 2) DATA HOT NODES
    - name: data-hot
      count: 1
      config:
        node.roles: ["data_hot", "data_content", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: data-hot
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: data-hot
                    topologyKey: "kubernetes.io/hostname"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi

    # 3) DATA WARM NODES
    - name: data-warm
      count: 1
      config:
        node.roles: ["data_warm", "data_content", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: data-warm
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: data-warm
                    topologyKey: "kubernetes.io/hostname"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi

    # 4) DATA COLD NODES
    - name: data-cold
      count: 1
      config:
        node.roles: ["data_cold", "data_content", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: data-cold
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: data-cold
                    topologyKey: "kubernetes.io/hostname"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            storageClassName: capacity-hdd
            resources:
              requests:
                storage: 2Gi

    # 5) INGEST NODES
    - name: ingest
      count: 1
      config:
        node.roles: ["ingest", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: ingest
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: ingest
                    topologyKey: "kubernetes.io/hostname"
      # Typically ingest nodes don't need big local storage
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi

    # 6) COORDINATING-ONLY NODES (no roles)
    - name: coord
      count: 3
      config:
        node.roles: []  # coordinating-only
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: coord
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: coord
                    topologyKey: "kubernetes.io/hostname"
      # Minimal storage; mainly for query routing
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi

    # 7) MACHINE LEARNING (ML) NODES
    - name: ml
      count: 1
      config:
        node.roles: ["ml", "remote_cluster_client"]
        xpack.ml.enabled: true
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: ml
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: ml
                    topologyKey: "kubernetes.io/hostname"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi

    # 8) TRANSFORM NODES
    - name: transform
      count: 1
      config:
        node.roles: ["transform", "remote_cluster_client"]
        node.store.allow_mmap: false
      podTemplate:
        metadata:
          labels:
            es-node-type: transform
        spec:
          containers:
            - name: elasticsearch
              resources:
                requests:
                  cpu: "1"
                  memory: 2Gi
                limits:
                  cpu: "2"
                  memory: 2Gi
              env:
                - name: ES_JAVA_OPTS
                  value: "-Xms2g -Xmx2g"
          affinity:
            podAntiAffinity:
              preferredDuringSchedulingIgnoredDuringExecution:
                - weight: 100
                  podAffinityTerm:
                    labelSelector:
                      matchLabels:
                        es-node-type: transform
                    topologyKey: "kubernetes.io/hostname"
      volumeClaimTemplates:
        - metadata:
            name: elasticsearch-data
          spec:
            accessModes: ["ReadWriteOnce"]
            resources:
              requests:
                storage: 2Gi
---
```
