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
```
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC='server --cluster-init --write-kubeconfig-mode=644' \
sh -s - --disable=servicelb --disable=traefik --cluster-cidr=10.0.0.0/16

FIRST_SERVER_IP=$(hostname -I | awk '{print $1}')
NODE_TOKEN=$(sudo cat /var/lib/rancher/k3s/server/node-token)
echo "$FIRST_SERVER_IP"
echo "$NODE_TOKEN"

export FIRST_SERVER_IP="<IP_of_node1>"
export NODE_TOKEN="<token_from_node1>"

curl -sfL https://get.k3s.io | \
  K3S_URL="https://${FIRST_SERVER_IP}:6443" \
  K3S_TOKEN="${NODE_TOKEN}" \
  INSTALL_K3S_EXEC='agent' \
  sh -s -
```
