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
Gain root
```
sudo su
```
Start minikube
```
minikube start -p dapo --cni=calico --driver=docker --force --cpus=all
minikube -p dapo addons enable metallb
minikube -p dapo addons configure metallb
#provide the range (possibly 192.168.49.100 and end 192.168.49.110) 
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
cat <<EOF > haproxy-values.yaml
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
helm install haproxy haproxytech/kubernetes-ingress --namespace haproxy --create-namespace -f haproxy-values.yaml
```
Test Ingress
```
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Namespace
metadata:
  name: hello-world
---
apiVersion: apps/v1
kind: Deployment
metadata:
  labels:
    app: hello-world
  name: hello-world
  namespace: hello-world
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hello-world
  template:
    metadata:
      labels:
        app: hello-world
    spec:
      containers:
      - image: us-docker.pkg.dev/google-samples/containers/gke/hello-app:1.0
        name: hello-world
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: hello-world
  namespace: hello-world
spec:
  selector:
    app: hello-world
  ports:
    - port: 80
      targetPort: 8080
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: hello-world-ingress
  namespace: hello-world
spec:
  ingressClassName: haproxy
  rules:
  - host: hello-server.local
    http:
      paths:
      - backend:
          service:
            name: hello-world
            port:
              number: 80
        path: /
        pathType: prefix
  tls:
  - hosts:
    - hello-server.local
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
