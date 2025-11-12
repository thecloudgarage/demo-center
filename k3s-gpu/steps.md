```
sudo apt update
sudo apt upgrade -y
sudo apt install curl wget build-essential procps curl file git zip unzip sshpass jq open-iscsi nfs-common -y
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
```
system settings
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
K3s
```
curl -sfL https://get.k3s.io | sh -s - --disable=servicelb --disable=traefik --flannel-backend=none --cluster-cidr=10.0.0.0/16 --disable-network-policy
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER ~/.kube/config
sudo chmod 600 ~/.kube/config
export KUBECONFIG=~/.kube/config
kubectl get nodes
```
Configure runtime
```
sudo nvidia-ctk runtime configure --runtime=containerd
```
Install calico
```
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.31.0/manifests/operator-crds.yaml
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.31.0/manifests/tigera-operator.yaml
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.31.0/manifests/custom-resources.yaml
```
NVIDIA GPU Operator
```
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
helm install --wait --generate-name nvidia/gpu-operator
```
Kubeflow
```
git clone https://github.com/kubeflow/manifests.git
cd manifests
while ! kustomize build  example | kubectl apply -f - --server-side --force-conflicts; do echo "Retrying to apply resources"; sleep 10; done
```
MetalLB
```
helm repo add metallb https://metallb.github.io/metallb
helm install metallb metallb/metallb --wait --timeout 15m --namespace metallb-system --create-namespace
sleep 30
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



