## Install pre-requisites
```
sudo su
sudo apt-get update -y
sudo apt-get install build-essential procps curl file git zip unzip sshpass jq -y
sudo apt-get install -y docker.io
sudo systemctl start docker
sudo systemctl enable docker
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo chmod +x kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.30.0/kind-linux-amd64
chmod +x ./kind
sudo mv ./kind /usr/local/bin/kind
```

## Create a KinD cluster with 1 master and 2 worker nodes. 
Note: Extra port mappings are provided to run Ingress services that map local host ports to the Ingress controller service port. The API server IP is that of the underlying host itself.
```
kind create cluster --config=- << EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
name: remote-cluster-1
nodes:
- role: control-plane
  labels:
    color: white
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
- role: worker
- role: worker
networking:
  apiServerAddress: "192.168.1.152"
  apiServerPort: 6443
EOF
```
## Install MetalLB
```
helm repo add metallb https://metallb.github.io/metallb
helm install metallb metallb/metallb --wait --timeout 15m --namespace metallb-system --create-namespace
```
### Configure MetalLB. Ensure the IPAM range is a single IP and is that of the underlying host.
```
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: first-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.152-192.168.1.152
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: example
  namespace: metallb-system
EOF
```
## Install the NGINX Ingress controller with nodeSelector
```
kubectl apply -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/kind-cluster/nginx-ingress-controller.yaml
``
## Deploy a sample app with Ingress
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
      - image: gcr.io/google-samples/node-hello:1.0
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
  name: nginx-ingress
  namespace: hello-world
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  rules:
  - http:
      paths:
      - pathType: Prefix
        path: "/hello-world"
        backend:
          service:
            name: hello-world
            port:
              number: 80
EOF
```

