# Kubernetes Quick Reference - Rhesis Project

## 🚀 Essential Commands

### 🔄 Rebuild and Redeploy (Complete Cleanup)
**Use this when you need to completely rebuild images and redeploy:**
```bash
# One command to do everything:
# 1. Delete old images from Minikube
# 2. Delete volumes (PVCs and PVs)
# 3. Rebuild all Docker images
# 4. Load images into Minikube
# 5. Redeploy the application
cd infrastructure/k8s
./rebuild-and-deploy.sh
```

### Start
```bash
# Build frontend in local mode (recommended for development)
cd apps/frontend
docker build -t rhesis-frontend:latest . --build-arg FRONTEND_ENV=local

# Build backend
cd ../backend
docker build -t rhesis-backend:latest .

# Build worker
cd ../worker
docker build -t rhesis-worker:latest .

# Start Minikube
minikube start --driver=docker --memory=8192 --cpus=2 --addons=storage-provisioner --addons=default-storageclass

# Deploy 
cd /rhesis/infrastructure/k8s/charts/rhesis
./deploy-local.sh

```


#### 📋 Files That Need Password Changes:

**🔧 Core Configuration Files:**
- `docker-compose.yml` - PostgreSQL default password

**🗄️ Database Files:**
- `infrastructure/k8s/manifests/deployments/postgres/init-db.sql` - PostgreSQL user creation
- `infrastructure/k8s/manifests/configmaps/postgres-init-config.yaml` - Kubernetes init script

**⚙️ Application Files:**
- `apps/backend/migrate.sh` - Migration script fallback password

**🔐 Secret Files (Manual Update Required):**
- `infrastructure/k8s/manifests/secrets/rhesis-secrets.yaml` - Base64 encoded password
  - Update: `SQLALCHEMY_DB_PASS: <your-base64-encoded-password>`


**⚠️ Security Note:** Always change the default password "your-secured-password" to a strong, unique password before deploying to production!

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

# Scale down all deployments
kubectl scale deployment --all --replicas=0 -n rhesis

# Delete all pods and volumes
kubectl delete pods --all -n rhesis
kubectl delete pvc --all -n rhesis
kubectl delete pv --all

# Or uninstall Helm release completely
helm uninstall rhesis -n rhesis

# Stop Minikube
minikube stop

# Delete cluster (if needed)
minikube delete
```

## 📋 Prerequisites Checklist

- [ ] Docker Desktop running
- [ ] Minikube installed
- [ ] kubectl installed
- [ ] Helm installed (v3.x)
- [ ] Docker images built
- [ ] Images loaded into Minikube

## 🚀 Helm Management

```bash
# Check Helm release status
helm status rhesis -n rhesis

# Upgrade release
cd charts/rhesis
helm upgrade rhesis . --values values-local.yaml

# Check release history
helm history rhesis -n rhesis

# Rollback to previous version
helm rollback rhesis 1 -n rhesis

# Uninstall release
helm uninstall rhesis -n rhesis
```

## 🔧 Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `ErrImageNeverPull` | `minikube image load <image-name>` |
| `secret not found` | `kubectl apply -f manifests/secrets/` |
| Pod not ready | Check logs: `kubectl logs -n rhesis <pod>` |
| Port-forward fails | Ensure pod is running first |
| Helm chart not found | Navigate to `charts/rhesis` directory |
| Password auth failed | Update password using Password Management section |

## 📱 Quick Status Check
```bash
# One-liner to check everything
kubectl get pods,services,pvc -n rhesis
```
