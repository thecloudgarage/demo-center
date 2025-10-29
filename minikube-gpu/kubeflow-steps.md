```
sudo su
sudo apt-get update -y
```
abc
```
sudo apt-get install build-essential procps curl file git zip unzip sshpass jq -y
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo chmod +x kubectl
sudo mv ./kubectl /usr/local/bin/kubectl
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube
wget https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh
chmod +x install.sh
#NOTE HOW WE ARE PASSING AN ENTER FOR THE INTERACTIVE PROMPT THAT THE INSTALL SCRIPT GENERATES TO CONFIRM FOR INSTALLATION
sudo echo -ne '\n' | ./install.sh
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> /home/prd/.profile
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
```
install kustomize
```
brew install kustomize
```
Docker runtime
```
sudo nvidia-ctk runtime configure --runtime=docker && sudo systemctl restart docker
```
start minikube with gpu
```
minikube start --driver docker --container-runtime docker --gpus all
```
Install kubeflow
```
git clone https://github.com/kubeflow/manifests.git
cd manifests
while ! kustomize build  example | kubectl apply -f - --server-side --force-conflicts; do echo "Retrying to apply resources"; sleep 10; done
```
Access kubeflow via Port forward
```
kubectl port-forward svc/istio-ingressgateway -n istio-system 8080:80
http://127.0.0.1:8080
Default credentials- user@example.com and 12341234
```
Start a gpu notebook
