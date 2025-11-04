```
sudo su
```
Upgrade
```
sudo apt-get update -y
```
Install prerequisites
```
sudo apt-get install build-essential procps curl file git zip unzip sshpass jq open-iscsi nfs-common -y
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
Gain root
```
sudo su
```
Start minikube
```
minikube start -p dapo --cni=calico --driver=docker --force --cpus=all
```
Enable MetalLB as an addon
```
minikube -p dapo addons enable metallb
```
Configure MetalLB IP advertisement
```
minikube -p dapo addons configure metallb
#provide the range (possibly 192.168.49.100 and end 192.168.49.110) 
```
HA Proxy Ingress
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
Verify Ingress controller external IP
```
kubectl get svc -n ingress-controller
```
Test Ingress
```
kubectl apply -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/dapo/hello-world-ingress.yaml
# Edit the local /etc/hosts to add in an entry for hello-server.local pointing to the external IP of the Ingress controller
curl -k https://hello-server.local
```
Delete the Test ingress deployment
```
kubectl delete -f https://raw.githubusercontent.com/thecloudgarage/demo-center/refs/heads/main/dapo/hello-world-ingress.yaml
```
Metrics server
```
curl -LO https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl apply -f components.yaml
```
Longhorn
```
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn --namespace longhorn-system --createnamespace --set persistence.defaultClassReplicaCount=1 --set defaultSettings.defaultReplicaCount=1 --version 1.9.1
```
