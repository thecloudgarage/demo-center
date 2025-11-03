## Install pre-requisites
```
sudo su
sudo apt-get update -y
```
Install the packages
```
sudo apt-get install build-essential procps curl file git zip unzip sshpass jq -y
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
## Start minikube with 1 control and 2 worker nodes
```
minikube start --nodes=3 --driver=docker
kubectl get nodes
minikube ip
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
  - 192.168.49.100-192.168.49.110 #find the range using minikube ip command and append a free pool/range
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
kubectl apply -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/minikube/nginx-ingress-controller.yaml
```
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
#      - image: gcr.io/google-samples/node-hello:1.0
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
