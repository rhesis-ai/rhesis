# 🚀 Kubernetes Deployment Guide for Rhesis

This directory contains all Kubernetes manifests for deploying the Rhesis application.

## 📁 Directory Structure

```
k8s/
├── base/                           # Base manifests (common across environments)
├── overlays/                       # Environment-specific overlays
│   ├── dev/                       # Development environment
│   ├── staging/                   # Staging environment
│   └── prod/                      # Production environment
├── manifests/                      # Individual Kubernetes resources
│   ├── namespaces/                # Namespace definitions
│   ├── configmaps/                # Configuration maps
│   ├── secrets/                    # Kubernetes secrets
│   ├── storage/                    # Persistent volumes and claims
│   ├── services/                   # Service definitions
│   ├── deployments/                # Deployment manifests
│   ├── ingress/                    # Ingress configurations
│   ├── monitoring/                 # Monitoring and logging
│   ├── rbac/                       # Role-based access control
│   └── network-policies/           # Network policies
├── scripts/                        # Deployment and utility scripts
├── examples/                       # Example configurations
└── charts/                         # Helm charts (if using Helm)
```

## ✅ Prerequisites

Before deploying to Kubernetes, ensure you have:

- **Docker Desktop** installed and running
- **Minikube** installed (`brew install minikube` on macOS)
- **kubectl** installed (`brew install kubectl` on macOS)
- **Docker images built** for frontend, backend, and worker

## 🚀 Quick Start Guide

### 1. 🏗️ Start Minikube Cluster

```bash
# Start Minikube with Docker driver
minikube start --driver=docker --memory=4096 --cpus=2 --addons=storage-provisioner --addons=default-storageclass

# Verify cluster is running
kubectl cluster-info
minikube status
```

### 2. 🐳 Build Docker Images (if not already built)

```bash
# Navigate to project root
cd /path/to/rhesis

# Build frontend image
cd apps/frontend
docker build -t rhesis-frontend:latest .

# Build backend image  
cd ../backend
docker build -t rhesis-backend:latest .

# Build worker image
cd ../worker
docker build -t rhesis-worker:latest .
```

### 3. 📦 Load Images into Minikube

```bash
# Load all images into Minikube's Docker environment
minikube image load rhesis-frontend:latest
minikube image load rhesis-backend:latest
minikube image load rhesis-worker:latest

# Verify images are loaded
minikube image ls | grep rhesis
```

### 4. 🚀 Deploy to Kubernetes

```bash
# Navigate to k8s directory
cd k8s

# Make deploy script executable
chmod +x scripts/deploy.sh

# Run deployment (dev environment)
./scripts/deploy.sh dev
```

### 5. ✅ Verify Deployment

```bash
# Check all pods status
kubectl get pods -n rhesis

# Check services
kubectl get services -n rhesis

# Check persistent volumes
kubectl get pv,pvc -n rhesis
```

### 6. 🌐 Access Your Application

```bash
# Frontend (Next.js app)
kubectl port-forward -n rhesis svc/frontend 3000:3000

# Backend (FastAPI)
kubectl port-forward -n rhesis svc/backend 8080:8080

# Access in browser:
# Frontend: http://localhost:3000
# Backend: http://localhost:8080
```

## 🔧 Manual Deployment Steps

If you prefer to deploy manually instead of using the script:

### 1. Create Namespace
```bash
kubectl apply -f manifests/namespaces/
```

### 2. Apply Secrets and ConfigMaps
```bash
kubectl apply -f manifests/secrets/
kubectl apply -f manifests/configmaps/
```

### 3. Apply Storage
```bash
kubectl apply -f manifests/storage/postgres/
kubectl apply -f manifests/storage/redis/
```

### 4. Apply Services
```bash
kubectl apply -f manifests/services/postgres/
kubectl apply -f manifests/services/redis/
kubectl apply -f manifests/services/backend/
kubectl apply -f manifests/services/frontend/
kubectl apply -f manifests/services/worker/
```

### 5. Deploy Applications
```bash
# Deploy PostgreSQL first
kubectl apply -f manifests/deployments/postgres/

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=postgres -n rhesis --timeout=300s

# Deploy other components
kubectl apply -f manifests/deployments/redis/
kubectl apply -f manifests/deployments/backend/
kubectl apply -f manifests/deployments/frontend/
kubectl apply -f manifests/deployments/worker/
```

## 🛠️ Troubleshooting

### Common Issues

#### 1. Image Pull Errors
```bash
# Error: ErrImageNeverPull
# Solution: Load images into Minikube
minikube image load rhesis-frontend:latest
minikube image load rhesis-backend:latest
minikube image load rhesis-worker:latest
```

#### 2. Secrets Not Found
```bash
# Error: secret "rhesis-secrets" not found
# Solution: Apply secrets first
kubectl apply -f manifests/secrets/
```

#### 3. PostgreSQL Not Ready
```bash
# Check PostgreSQL pod status
kubectl describe pod -n rhesis -l app=postgres

# Check logs
kubectl logs -n rhesis -l app=postgres
```

#### 4. Storage Issues
```bash
# Check persistent volumes
kubectl get pv,pvc -n rhesis

# Check storage class
kubectl get storageclass
```

### 🐛 Debug Commands

```bash
# Get detailed pod information
kubectl describe pod -n rhesis <pod-name>

# Check pod logs
kubectl logs -n rhesis <pod-name>

# Check events
kubectl get events -n rhesis --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n rhesis
```

## 🌍 Environment-Specific Deployments

### Development (Minikube)
```bash
kubectl apply -k overlays/dev/
```

### Staging
```bash
kubectl apply -k overlays/staging/
```

### Production
```bash
kubectl apply -k overlays/prod/
```

## 🧩 Components Overview

- 🗄️ **PostgreSQL**: Database with persistent storage
- 🔴 **Redis**: Cache and message broker
- ⚙️ **Backend**: FastAPI application
- 🎨 **Frontend**: Next.js application
- 🔄 **Worker**: Celery worker for background tasks

## 🧹 Cleanup

### Stop Port Forwarding
```bash
# Press Ctrl+C in the terminal running port-forward
```

### Stop Minikube
```bash
minikube stop
```

### Delete Cluster (if needed)
```bash
minikube delete
```

## ⚙️ Configuration

### Environment Variables
All configuration is managed through:
- 📋 **ConfigMaps**: `manifests/configmaps/rhesis-config.yaml`
- 🔐 **Secrets**: `manifests/secrets/rhesis-secrets.yaml`

### Resource Limits
- 🎨 **Frontend**: 200m CPU, 512Mi memory
- ⚙️ **Backend**: 500m CPU, 1Gi memory  
- 🔄 **Worker**: 200m CPU, 2Gi memory
- 🗄️ **PostgreSQL**: 500m CPU, 512Mi memory
- 🔴 **Redis**: 200m CPU, 256Mi memory

## 📝 Notes

- All manifests use environment variables for configuration
- Persistent volumes are configured for data persistence
- Health checks and readiness probes are implemented
- Resource limits and requests are defined
- The deployment script automatically handles the correct order of resource creation

## 🆘 Support

If you encounter issues:
1. Check the troubleshooting section above
2. Verify all prerequisites are met
3. Check pod logs and events
4. Ensure Docker images are properly loaded into Minikube

