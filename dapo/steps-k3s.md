### Install pre-requisites
```
sudo apt update
sudo apt upgrade -y
sudo apt install curl wget build-essential procps curl file git zip unzip sshpass jq open-iscsi nfs-common -y
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
```
### Configure the OS settings
```
sudo swapoff -a
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab
echo 'br_netfilter' | sudo tee /etc/modules-load.d/k8s.conf
echo 'overlay' | sudo tee -a /etc/modules-load.d/k8s.conf
sudo modprobe br_netfilter
sudo modprobe overlay

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward = 1
net.ipv6.conf.all.forwarding = 1
EOF

sudo sysctl --system
```    
### Install k3s without the default Klipper LB and Traefik Ingress
```    
curl -sfL https://get.k3s.io | sh -s - --disable=servicelb --disable=traefik
sudo systemctl status k3s
```
### Access the k3s cluster via kubectl
```
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER ~/.kube/config
sudo chmod 600 ~/.kube/config
export KUBECONFIG=~/.kube/config
kubectl get nodes
```    
### Install MetalLB    
```
helm repo add metallb https://metallb.github.io/metallb 
helm install metallb metallb/metallb --wait --timeout 15m --namespace metallb-system --create-namespace
```
### Configure Metal LB
```    
metallbStartIp=X.X.X.X
metallbEndIp=Y.Y.Y.Y
    
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: first-pool
  namespace: metallb-system
spec:
  addresses:
  - $metallbStartIp-$metallbEndIp
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: example
  namespace: metallb-system
EOF
```
### Install HA Proxy Ingress Controller
```
helm repo add haproxytech https://haproxytech.github.io/helm-charts
helm repo update

cat <<EOF > haproxy-values.yaml
# Expose HAProxy via a service loadbalancer
controller:
  image:
    repository: haproxytech/kubernetes-ingress
    pullPolicy: Always
  service:
    type: LoadBalancer
    externalTrafficPolicy: Local
  config:
    ssl-passthrough: "true"
#  hostNetwork: true
  kind: DaemonSet
  defaultTLSSecret:
     enabled: true
EOF

helm install haproxy haproxytech/kubernetes-ingress --namespace haproxy --create-namespace -f haproxy-values.yaml
```
### Verify HA Proxy Ingress via a sample app
```
# Verify the External IP for Ingress
kubectl get svc -n ingress-controller

# Create an entry in local host's /etc/hosts for the External IP mapping to hello-server.local
nano /etc/hosts

# Deploy the sample app
kubectl apply -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/dapo/hello-world-ingress.yaml

# Verify the app
curl -k https://hello-server.local

# Delete the app
kubectl delete -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/dapo/hello-world-ingress.yaml
```
### Deploy Longhorn for a single node install
```
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn --namespace longhorn-system --create-namespace \
--set persistence.defaultClassReplicaCount=1 \
--set defaultSettings.defaultReplicaCount=1 \
--set csi.attacherReplicaCount=1 \
--set csi.provisionerReplicaCount=1 \
--set csi.resizerReplicaCount=1 \
--set csi.snapshotterReplicaCount=1 \
--set longhornUI.replicas=1 \
--version 1.9.1
```
### Swap the default storage class for LongHorn
```
kubectl patch storageclass local-path -p "{\"metadata\": {\"annotations\":{\"storageclass.kubernetes.io/is-default-class\":\"false\"}}}"
kubectl patch storageclass longhorn -p "{\"metadata\": {\"annotations\":{\"storageclass.kubernetes.io/is-default-class\":\"true\"}}}"
```
### Deploy a sample MySQL db 
```
kubectl apply -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/dapo/mysql.yaml
```
