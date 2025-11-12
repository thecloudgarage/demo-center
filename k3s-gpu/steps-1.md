```
sudo apt update
sudo apt upgrade -y
sudo apt install curl wget build-essential procps curl file git zip unzip sshpass jq open-iscsi nfs-common -y
curl https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash
wget https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh
chmod +x install.sh
#NOTE HOW WE ARE PASSING AN ENTER FOR THE INTERACTIVE PROMPT THAT THE INSTALL SCRIPT GENERATES TO CONFIRM FOR INSTALLATION
sudo echo -ne '\n' | ./install.sh
echo 'eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"' >> /home/$USER/.profile
eval "$(/home/linuxbrew/.linuxbrew/bin/brew shellenv)"
sleep 10
brew install kustomize
sudo swapoff -a
curl -sfL https://get.k3s.io | sh -s
sleep 30
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $USER ~/.kube/config
sudo chmod 600 ~/.kube/config
export KUBECONFIG=~/.kube/config
sudo nvidia-ctk runtime configure --runtime=containerd && sudo systemctl restart containerd
sleep 30
helm repo add nvidia https://nvidia.github.io/gpu-operator
helm repo update
helm install --wait --generate-name nvidia/gpu-operator
sleep 60
git clone https://github.com/kubeflow/manifests.git
cd manifests
sed -i "s/\$(profile-name)/myprofile/g" common/user-namespace/base/profile-instance.yaml
while ! kustomize build  example | kubectl apply -f - --server-side --force-conflicts; do echo "Retrying to apply resources"; sleep 30; done
```
