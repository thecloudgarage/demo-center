```
sudo su
```
Upgrade
```
sudo apt-get update -y
```
Install prerequisites
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
Start minikube
```
sudo su
minikube start -p dapo --cni=calico --driver=docker --force
```
