# Kubernetes Quick Reference - Rhesis Project

## 🚀 Essential Commands

### Start Everything
```bash
# 1. Start Minikube
minikube start --driver=docker --memory=4096 --cpus=2

# 2. Load Docker images
minikube image load rhesis-frontend:latest
minikube image load rhesis-backend:latest
minikube image load rhesis-worker:latest

# 3. Deploy to Kubernetes
cd k8s
./scripts/deploy.sh dev
```

### Check Status
```bash
# Pod status
kubectl get pods -n rhesis

# Services
kubectl get services -n rhesis

# All resources
kubectl get all -n rhesis
```

### Access Application
```bash
# Frontend (Next.js)
kubectl port-forward -n rhesis svc/frontend 3000:3000
# Browser: http://localhost:3000

# Backend (FastAPI)
kubectl port-forward -n rhesis svc/backend 8080:8080
# Browser: http://localhost:8080
```

### Troubleshooting
```bash
# Check pod details
kubectl describe pod -n rhesis <pod-name>

# Check logs
kubectl logs -n rhesis <pod-name>

# Check events
kubectl get events -n rhesis
```

### Cleanup
```bash
# Stop port-forwarding: Ctrl+C
# Stop Minikube: minikube stop
# Delete cluster: minikube delete
```

## 📋 Prerequisites Checklist

- [ ] Docker Desktop running
- [ ] Minikube installed
- [ ] kubectl installed
- [ ] Docker images built
- [ ] Images loaded into Minikube

## 🔧 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `ErrImageNeverPull` | `minikube image load <image-name>` |
| `secret not found` | `kubectl apply -f manifests/secrets/` |
| Pod not ready | Check logs: `kubectl logs -n rhesis <pod>` |
| Port-forward fails | Ensure pod is running first |

## 📱 Quick Status Check
```bash
# One-liner to check everything
kubectl get pods,services,pvc -n rhesis
```
