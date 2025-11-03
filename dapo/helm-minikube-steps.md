```
sudo su
```
Upgrade
```
sudo apt-get update -y
```
Install prerequisites
```
sudo apt-get install build-essential procps curl file git zip unzip sshpass jq open-iscsi nfs-common -y
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo chmod +x kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
```
Start minikube
```
sudo su
minikube start -p dapo --cni=calico --driver=docker --force
```
MetalLB
```
helm repo add metallb https://metallb.github.io/metallb
helm install metallb metallb/metallb --wait --timeout 15m --namespace metallb-system --create-namespace
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: first-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.49.100-192.168.49.110 #find the range using minikube ip command and append a free pool/range
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: example
  namespace: metallb-system
EOF
```
HA Proxy Ingress
```
helm repo add haproxytech https://haproxytech.github.io/helm-charts
helm repo update
cat <<EOF > haproxyvalues.yaml
controller:
  image:
    repository: haproxytech/kubernetes-ingress
    pullPolicy: Always
  service:
    type: LoadBalancer
    externalTrafficPolicy: Local
  config:
    ssl-passthrough: "true"
  hostNetwork: true
  kind: DaemonSet
  defaultTLSSecret:
     enabled: false
EOF
helm install haproxy haproxytech/kubernetes-ingress --namespace haproxy --create namespace -f haproxy-values.yaml
```
Test Ingress
```
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1 
kind: Deployment 
metadata: 
  labels: 
    run: app 
  name: app 
spec: 
  replicas: 5 
  selector: 
    matchLabels: 
      run: app 
  template: 
    metadata: 
      labels: 
        run: app 
    spec: 
      containers: 
      - name: app 
        image: errm/versions:0.0.1 
        ports: 
        - containerPort: 3000 
        readinessProbe: 
          httpGet: 
            path: / 
            port: 3000 
          initialDelaySeconds: 5 
          periodSeconds: 5 
          successThreshold: 1
---
apiVersion: v1 
kind: Service 
metadata: 
  name: app-service 
spec: 
  selector: 
    run: app 
  ports: - name: http 
    port: 80 
    protocol: TCP 
    targetPort: 3000
---
apiVersion: networking.k8s.io/v1beta1 
kind: Ingress 
metadata: 
  name: app-ingress 
  namespace: default 
spec: 
  rules: 
  - http: 
      paths: 
      - path: / 
        backend: 
          serviceName: app-service 
          servicePort: 80
EOF
```
Metrics server
```
curl -LO https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl apply -f components.yaml
```
Longhorn
```
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn --namespace longhorn-system --createnamespace --set persistence.defaultClassReplicaCount=1 --set defaultSettings.defaultReplicaCount=1 --version 1.9.1
```
