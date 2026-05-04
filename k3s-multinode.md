```
sudo hostnamectl set-hostname nodex
```
```
sudo apt update
sudo apt upgrade -y
sudo apt install curl wget build-essential procps curl file git zip unzip sshpass jq open-iscsi nfs-common -y
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
```
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
On Master node
```
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC='server --cluster-init --write-kubeconfig-mode=644' \
sh -s - --disable=servicelb --disable=traefik --cluster-cidr=10.0.0.0/16

FIRST_SERVER_IP=$(hostname -I | awk '{print $1}')
NODE_TOKEN=$(sudo cat /var/lib/rancher/k3s/server/node-token)
echo "$FIRST_SERVER_IP"
echo "$NODE_TOKEN"

mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER ~/.kube/config
sudo chmod 600 ~/.kube/config
export KUBECONFIG=~/.kube/config
kubectl get nodes

```
On worker nodes
```
export FIRST_SERVER_IP="<IP_of_node1>"
export NODE_TOKEN="<token_from_node1>"

curl -sfL https://get.k3s.io | \
  K3S_URL="https://${FIRST_SERVER_IP}:6443" \
  K3S_TOKEN="${NODE_TOKEN}" \
  INSTALL_K3S_EXEC='agent' \
  sh -s -
```
MetalLB On Master node
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
HAProxy on Master node
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
Longhorn on Master node
```
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn --namespace longhorn-system --create-namespace \
--set persistence.defaultClassReplicaCount=3 \
--set defaultSettings.defaultReplicaCount=3 \
--set csi.attacherReplicaCount=3 \
--set csi.provisionerReplicaCount=3 \
--set csi.resizerReplicaCount=3 \
--set csi.snapshotterReplicaCount=3 \
--set longhornUI.replicas=1 \
--version 1.9.1
```
Patch storage class
```
kubectl patch storageclass local-path -p "{\"metadata\": {\"annotations\":{\"storageclass.kubernetes.io/is-default-class\":\"false\"}}}"
kubectl patch storageclass longhorn -p "{\"metadata\": {\"annotations\":{\"storageclass.kubernetes.io/is-default-class\":\"true\"}}}"
```
