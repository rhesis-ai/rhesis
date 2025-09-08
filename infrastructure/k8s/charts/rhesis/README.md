# 🚀 Rhesis Helm Chart

A Helm chart for deploying the Rhesis AI application stack to Kubernetes.

## 📋 Overview

This Helm chart deploys the complete Rhesis application stack including:
- 🗄️ **PostgreSQL** - Database with persistent storage
- 🔴 **Redis** - Cache and message broker
- ⚙️ **Backend** - FastAPI application
- 🎨 **Frontend** - Next.js application
- 🔄 **Worker** - Celery worker for background tasks

## 🎯 Features

- **Environment-specific configurations** - Easy switching between dev/staging/prod
- **Conditional deployments** - Enable/disable components as needed
- **Persistent storage** - Configurable storage for databases
- **Health checks** - Built-in liveness and readiness probes
- **Resource management** - Configurable CPU and memory limits
- **Local development ready** - Optimized for Minikube and local clusters

## 📦 Prerequisites

- Kubernetes cluster (Minikube, Docker Desktop, or cloud)
- Helm 3.x installed
- kubectl configured
- Docker images built and available locally

## 💻 System Requirements

### Minimum Requirements (Tested & Working)
- **CPU**: 4 cores (2.0 GHz)
- **RAM**: 8 GB (Minikube allocated)
- **Storage**: 20 GB free space
- **OS**: Linux, macOS, or Windows with Docker support
- **Minikube**: v1.36+ with 8GB memory, 4 CPU cores, 50GB disk

### Recommended Requirements
- **CPU**: 8 cores (2.5 GHz)
- **RAM**: 16 GB (12GB+ for Minikube)
- **Storage**: 50 GB free space (SSD recommended)
- **OS**: Linux or macOS
- **Minikube**: v1.36+ with 8GB+ memory, 4+ CPU cores

### Kubernetes Cluster Requirements
- **Minikube**: v1.36+ with 8GB+ memory, 4+ CPU cores, 50GB+ disk
- **Docker Desktop**: 8GB+ memory for Kubernetes
- **Cloud**: Any managed Kubernetes service (GKE, EKS, AKS)

### Prerequisites Installation

#### 1. Install Required Tools

```bash
# Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop/

# Install Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-darwin-amd64
sudo install minikube-darwin-amd64 /usr/local/bin/minikube

# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/darwin/amd64/kubectl"
sudo install kubectl /usr/local/bin/kubectl

# Install Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

#### 2. Verify Installation

```bash
# Check Docker
docker --version
docker-compose --version

# Check Minikube
minikube version

# Check kubectl
kubectl version --client

# Check Helm
helm version
```

#### 3. Start Minikube with Optimized Settings

```bash
# Configure Minikube with optimal resources
minikube config set memory 8192
minikube config set cpus 4
minikube config set disk-size 50g

# Start Minikube
minikube start --driver=docker

# Verify cluster is running
kubectl get nodes
```

## 📊 Resource Usage

### Local Development Configuration (Current Stable Setup)

| Component | Replicas | CPU Requests | CPU Limits | Memory Requests | Memory Limits | Storage |
|-----------|----------|--------------|------------|-----------------|---------------|---------|
| **Frontend** | 1 | 1000m | 2000m | 2 Gi | 4 Gi | - |
| **Backend** | 1 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **Worker** | 1 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **PostgreSQL** | 1 | 250m | 500m | 512 Mi | 1 Gi | 1 Gi |
| **Redis** | 1 | 100m | 200m | 128 Mi | 256 Mi | - |
| **Total** | **5** | **2.35 cores** | **4.7 cores** | **4.6 Gi** | **9.2 Gi** | **1 Gi** |

### Actual Resource Usage (Measured)
- **CPU Usage**: 31% requested, 47% limited
- **Memory Usage**: 40% requested, 79% limited
- **Status**: ✅ Stable and running without restarts

### Production Configuration (Recommended)

| Component | Replicas | CPU Requests | CPU Limits | Memory Requests | Memory Limits | Storage |
|-----------|----------|--------------|------------|-----------------|---------------|---------|
| **Frontend** | 2 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **Backend** | 3 | 1000m | 2000m | 2 Gi | 4 Gi | - |
| **Worker** | 5 | 500m | 1000m | 1 Gi | 2 Gi | - |
| **PostgreSQL** | 1 | 1000m | 2000m | 2 Gi | 4 Gi | 100 Gi |
| **Redis** | 1 | 500m | 1000m | 1 Gi | 2 Gi | 10 Gi |
| **Total** | **12** | **6.5 cores** | **12 cores** | **11 Gi** | **22 Gi** | **110 Gi** |

### Resource Scaling Guidelines

#### CPU Scaling
- **Frontend**: CPU-intensive during build/compilation, lighter during runtime
- **Backend**: CPU-intensive for AI/ML processing and database operations
- **Worker**: CPU-intensive for parallel task processing
- **Database**: CPU-intensive for complex queries and data processing

#### Memory Scaling
- **Frontend**: High memory usage during Next.js compilation
- **Backend**: High memory usage for AI model loading and data processing
- **Worker**: Moderate memory usage, scales with task complexity
- **Database**: Memory usage scales with data size and query complexity

#### Storage Scaling
- **PostgreSQL**: Scales with data volume (test results, user data)
- **Redis**: Scales with cache size and session data
- **Frontend**: No persistent storage required

### Performance Optimization Tips

1. **SSD Storage**: Use SSD for database storage for better I/O performance
2. **Memory Allocation**: Allocate at least 8GB to Minikube for local development
3. **CPU Cores**: More CPU cores improve parallel processing performance
4. **Worker Scaling**: Increase worker replicas for better task throughput
5. **Database Tuning**: Configure PostgreSQL memory settings based on available RAM

## 📈 Monitoring Resource Usage

### Check Resource Usage
```bash
# View pod resource usage
kubectl top pods -n rhesis

# View node resource usage
kubectl top nodes

# Check resource requests and limits
kubectl describe pods -n rhesis
```

### Common Resource Issues

#### Out of Memory (OOMKilled)
- **Symptoms**: Pods restarting with `OOMKilled` status
- **Solution**: Increase memory limits in `values-local.yaml`
- **Check**: `kubectl describe pod <pod-name> -n rhesis`

#### CPU Throttling
- **Symptoms**: Slow performance, high CPU usage
- **Solution**: Increase CPU limits or requests
- **Check**: `kubectl top pods -n rhesis`

#### Storage Issues
- **Symptoms**: Pods stuck in `Pending` state
- **Solution**: Check available storage and PVC status
- **Check**: `kubectl get pvc -n rhesis`

### Start minikube (if not started yet) 

```bash
minikube start --driver=docker --memory=8192 --cpus=2 --addons=storage-provisioner --addons=default-storageclass

```


### Resource Optimization Commands

```bash
# Scale workers for better performance
kubectl scale deployment worker --replicas=5 -n rhesis

# Check resource utilization
kubectl get pods -n rhesis -o wide

# Monitor resource usage in real-time
watch kubectl top pods -n rhesis
```

## 🎯 Deployment Scenarios

### Development Environment
- **Purpose**: Local development and testing
- **Resources**: 8GB RAM, 4 CPU cores
- **Components**: All services with minimal replicas
- **Storage**: 1GB for database
- **Use Case**: Individual developer setup

### Staging Environment
- **Purpose**: Pre-production testing
- **Resources**: 16GB RAM, 8 CPU cores
- **Components**: 2 frontend, 2 backend, 3 workers
- **Storage**: 10GB for database, 1GB for Redis
- **Use Case**: Team testing and validation

### Production Environment
- **Purpose**: Live production deployment
- **Resources**: 32GB+ RAM, 16+ CPU cores
- **Components**: 3+ frontend, 5+ backend, 10+ workers
- **Storage**: 100GB+ for database, 10GB+ for Redis
- **Use Case**: High-availability production service

### Resource Planning Calculator

| Environment | Users | Frontend | Backend | Workers | Total CPU | Total RAM | Storage |
|-------------|-------|----------|---------|---------|-----------|-----------|---------|
| **Development** | 1-2 | 1 | 1 | 3 | 2.85 cores | 6.4 Gi | 1 Gi |
| **Staging** | 5-10 | 2 | 2 | 5 | 4.5 cores | 9 Gi | 11 Gi |
| **Production** | 50+ | 3 | 5 | 10 | 8.5 cores | 18 Gi | 110 Gi |
| **Enterprise** | 500+ | 5 | 10 | 20 | 17 cores | 36 Gi | 500 Gi |

## 🚀 Quick Start

### 1. Prerequisites Check

```bash
# Verify all tools are installed and working
docker --version
minikube version
kubectl version --client
helm version

# Check Minikube status
minikube status
```

### 2. Clean Start (Recommended)

```bash
# Clean up any existing deployment
kubectl scale deployment frontend --replicas=0 -n rhesis
kubectl delete namespace rhesis 2>/dev/null || true
minikube image rm rhesis-frontend:latest rhesis-backend:latest rhesis-worker:latest 2>/dev/null || true

# Start fresh Minikube with optimal settings
minikube delete
minikube start --driver=docker
```

### 3. Build and Load Docker Images

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

```

### 4. Deploy with Helm

```bash
# Navigate to Helm chart directory
cd infrastructure/k8s/charts/rhesis

# Deploy using the automated script (recommended)
./deploy-local.sh

# OR deploy manually
# Load images into Minikube
minikube image load rhesis-frontend:latest
minikube image load rhesis-backend:latest
minikube image load rhesis-worker:latest

# Deploy manually
helm install rhesis . --values values-local.yaml --namespace rhesis --create-namespace
```

### 5. Verify Deployment

```bash
# Check all pods are running
kubectl get pods -n rhesis

# Check resource usage
kubectl top pods -n rhesis

# Check services
kubectl get svc -n rhesis
```

### 6. Access Your Application

```bash
# Frontend (in one terminal)
kubectl port-forward -n rhesis svc/frontend 3000:3000
# Open: http://localhost:3000

# Backend (in another terminal)
kubectl port-forward -n rhesis svc/backend 8080:8080
# Open: http://localhost:8080

# Worker health check
kubectl port-forward -n rhesis svc/worker 8080:8080
# Check: http://localhost:8080/health/basic
```

## 🔍 Health Checks and Monitoring

### Check Application Status

```bash
# Overall status
kubectl get all -n rhesis

# Pod status with details
kubectl get pods -n rhesis -o wide

# Check for any issues
kubectl get events -n rhesis --sort-by='.lastTimestamp'

# Resource usage
kubectl top pods -n rhesis
kubectl top nodes
```

### Application Health Endpoints

```bash
# Backend health
kubectl port-forward -n rhesis svc/backend 8080:8080
curl http://localhost:8080/health

# Worker health
kubectl port-forward -n rhesis svc/worker 8080:8080
curl http://localhost:8080/health/basic

# Frontend (check in browser)
kubectl port-forward -n rhesis svc/frontend 3000:3000
# Open: http://localhost:3000
```

### Log Monitoring

```bash
# Frontend logs
kubectl logs -n rhesis -l app=frontend --tail=50 -f

# Backend logs
kubectl logs -n rhesis -l app=backend --tail=50 -f

# Worker logs
kubectl logs -n rhesis -l app=worker --tail=50 -f

# PostgreSQL logs
kubectl logs -n rhesis -l app=postgres --tail=50 -f

# Redis logs
kubectl logs -n rhesis -l app=redis --tail=50 -f
```

## ⚙️ Configuration

### Values Files

- **`values.yaml`** - Default configuration
- **`values-local.yaml`** - Local development overrides
- **`values-staging.yaml`** - Staging environment (future)
- **`values-prod.yaml`** - Production environment (future)

### Key Configuration Options

```yaml
# Global settings
global:
  environment: "local"
  namespace: "rhesis"
  imagePullPolicy: "Never"  # For local development

# Component enable/disable
backend:
  enabled: true
  replicas: 1
  resources:
    requests:
      memory: "512Mi"
      cpu: "250m"

# Database configuration
database:
  enabled: true
  type: "postgresql"
  postgresql:
    persistence:
      enabled: true
      size: "1Gi"
```

## 🔧 Customization

### Override Values

```bash
# Override specific values
helm install rhesis . \
  --set backend.replicas=2 \
  --set database.postgresql.persistence.size=2Gi

# Use custom values file
helm install rhesis . --values my-custom-values.yaml
```

### Environment-Specific Deployments

```bash
# Development
helm install rhesis . --values values-local.yaml

# Staging (future)
helm install rhesis . --values values-staging.yaml

# Production (future)
helm install rhesis . --values values-prod.yaml
```

## 📊 Management

### Check Status

```bash
# Release status
helm status rhesis

# Pod status
kubectl get pods -n rhesis

# All resources
kubectl get all -n rhesis
```

### Upgrade

```bash
# Upgrade with new values
helm upgrade rhesis . --values values-local.yaml

# Upgrade specific values
helm upgrade rhesis . --set backend.replicas=3
```

### Rollback

```bash
# List history
helm history rhesis

# Rollback to previous version
helm rollback rhesis 1
```

### Uninstall

```bash
# Remove the release
helm uninstall rhesis

# Remove namespace (optional)
kubectl delete namespace rhesis

# Shutdown all pods in the namespace
kubectl scale deployment --all --replicas=0 -n rhesis
```

## 🐛 Troubleshooting

### Common Issues and Solutions

#### 1. Image Pull Errors
```bash
# Error: ErrImageNeverPull
# Solution: Load images into Minikube
minikube image load rhesis-frontend:latest
minikube image load rhesis-backend:latest
minikube image load rhesis-worker:latest

# If images are cached, force reload
minikube image rm rhesis-frontend:latest
minikube image load rhesis-frontend:latest
```

#### 2. Out of Memory (OOMKilled) Errors
```bash
# Symptoms: Pods restarting with OOMKilled status
# Solution: Increase memory limits in values-local.yaml

# Check current resource usage
kubectl top pods -n rhesis

# Check pod details for OOM events
kubectl describe pod -n rhesis <pod-name>

# Increase memory limits (edit values-local.yaml)
# Frontend: 4Gi limit, Backend: 2Gi limit, Worker: 2Gi limit
```

#### 3. Frontend Not Connecting to Backend
```bash
# Issue: Frontend calling production API instead of local backend
# Solution: Rebuild frontend in local mode

cd apps/frontend
docker build -t rhesis-frontend:latest . --build-arg FRONTEND_ENV=local
minikube image load rhesis-frontend:latest
kubectl rollout restart deployment/frontend -n rhesis
```

#### 4. PostgreSQL Connection Issues
```bash
# Symptoms: Backend can't connect to database
# Solution: Check PostgreSQL pod status and logs

kubectl get pods -n rhesis -l app=postgres
kubectl logs -n rhesis -l app=postgres --tail=20

# If PostgreSQL is not ready, check for data corruption
kubectl delete pvc postgres-pvc -n rhesis
kubectl delete pod -l app=postgres -n rhesis
```

#### 5. Health Check Failures
```bash
# Symptoms: Pods failing liveness/readiness probes
# Solution: Check probe timeouts and resource limits

# Check pod events
kubectl describe pod -n rhesis <pod-name>

# Check if probes are timing out
kubectl logs -n rhesis <pod-name> | grep -i "timeout\|probe"
```

#### 6. Resource Constraints
```bash
# Symptoms: Pods stuck in Pending state
# Solution: Check node resources and adjust limits

# Check node capacity
kubectl describe nodes

# Check resource requests vs limits
kubectl get pods -n rhesis -o wide

# Scale down if needed
kubectl scale deployment worker --replicas=1 -n rhesis
```

#### 7. Minikube Issues
```bash
# Minikube not starting
minikube delete
minikube start --driver=docker

# Insufficient resources
minikube config set memory 8192
minikube config set cpus 4
minikube config set disk-size 50g

# Check Minikube status
minikube status
minikube dashboard
```

### Debug Commands

```bash
# Check all resources
kubectl get all -n rhesis

# Check pod status with details
kubectl get pods -n rhesis -o wide

# Check recent events
kubectl get events -n rhesis --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n rhesis
kubectl top nodes

# Check persistent volumes
kubectl get pv,pvc -n rhesis

# Check services and endpoints
kubectl get svc,endpoints -n rhesis
```

### Recovery Procedures

#### Complete Reset
```bash
# Stop all port forwards (Ctrl+C)
# Clean up everything
kubectl delete namespace rhesis
minikube image rm rhesis-frontend:latest rhesis-backend:latest rhesis-worker:latest
minikube delete
minikube start --driver=docker

# Rebuild and redeploy
cd infrastructure/k8s/charts/rhesis
./deploy-local.sh
```

#### Partial Reset
```bash
# Reset specific component
kubectl delete deployment frontend -n rhesis
kubectl delete deployment backend -n rhesis
kubectl delete deployment worker -n rhesis

# Redeploy
helm upgrade rhesis . --values values-local.yaml -n rhesis
```

### Validation Commands

```bash
# Validate chart
helm lint .

# Template rendering (dry-run)
helm template rhesis . --values values-local.yaml

# Check values
helm get values rhesis

# Check Helm history
helm history rhesis -n rhesis
```

## ✅ Current Stable Configuration

### Tested and Working Setup
- **Minikube**: v1.36+ with 8GB RAM, 4 CPU cores, 50GB disk
- **Frontend**: Local mode with `FRONTEND_ENV=local`
- **Backend**: Local mode with `ENVIRONMENT=local`
- **Database**: PostgreSQL 16-alpine with 1GB storage
- **Resource Usage**: 31% CPU, 40% memory (stable)
- **Status**: All pods running without restarts

### Key Optimizations Applied
1. **Health Check Timeouts**: Increased from 1s to 10s for stability
2. **Memory Limits**: Optimized for each component's actual needs
3. **PostgreSQL Probes**: Changed from `pg_isready` to TCP socket checks
4. **Security Contexts**: Temporarily disabled for frontend due to permission issues
5. **Image Pull Policy**: Set to `IfNotPresent` for cloud compatibility

### Performance Characteristics
- **Startup Time**: ~2-3 minutes for full deployment
- **Memory Usage**: 4.6GB requested, 9.2GB limited
- **CPU Usage**: 2.35 cores requested, 4.7 cores limited
- **Storage**: 1GB PostgreSQL persistent volume
- **Stability**: No restarts after initial deployment

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │───►│    Backend      │───►│   PostgreSQL    │
│   (Next.js)     │    │   (FastAPI)     │    │   Port: 5432    │
│   Port: 3000    │    │   Port: 8080    │    └─────────────────┘
└─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │     Redis       │◄───│     Worker      │
                       │   Port: 6379    │    │   (Celery)      │
                       └─────────────────┘    │   Port: 8080    │
                                              └─────────────────┘
```

**Component Details:**
- **Frontend** (Next.js) - Port 3000
- **Backend** (FastAPI) - Port 8080  
- **Worker** (Celery) - Port 8080
- **PostgreSQL** - Port 5432
- **Redis** - Port 6379

## 🔮 Future Enhancements

- **Ingress support** - External access configuration
- **Monitoring stack** - Prometheus and Grafana integration
- **Network policies** - Security and access control
- **RBAC configuration** - Role-based access control
- **External databases** - Support for managed database services
- **Auto-scaling** - Horizontal Pod Autoscaler (HPA)

## 📚 References

- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Rhesis Project](https://github.com/your-org/rhesis)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `helm lint .` and `helm template .`
5. Submit a pull request

## 📄 License

This project is licensed under the same license as the Rhesis project.
