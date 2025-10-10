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
``

## Create a KinD cluster with 1 master and 2 worker nodes. Extra port mappings are provided to run Ingress services that map local host ports to the Ingress controller service port. The API server IP is that of the underlying host itself.
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
