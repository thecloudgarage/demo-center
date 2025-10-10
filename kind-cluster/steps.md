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
helm repo add metallb https://urldefense.com/v3/__https://metallb.github.io/metallb__;!!LpKI!ikQSGqw5ta7yAZuzxAT0e_VAhKpheYbRoinymh0DBGO9Tv6Zq9_07F6QQwIPBFvD28eZBbZ3nzyi7ce3oy4y$ [metallb[.]github[.]io]
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
